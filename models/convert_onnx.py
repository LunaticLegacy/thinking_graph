#!/usr/bin/env python
"""Export a Hugging Face CausalLM model to ONNX and optionally quantize it.

Examples:
    python models/convert_onnx.py \
      --model Qwen/Qwen2.5-1.5B-Instruct \
      --output-dir models/qwen2.5-1.5b-onnx \
      --quantize int8_dynamic \
      --trust-remote-code
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


QUANT_CHOICES = ("none", "int8_dynamic")


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _resolve_optimum_cli_prefix() -> list[str]:
    if shutil.which("optimum-cli"):
        return ["optimum-cli"]
    if _has_module("optimum"):
        return [sys.executable, "-m", "optimum.commands.optimum_cli"]
    raise RuntimeError(
        "Cannot find `optimum-cli`. Install with: pip install -U optimum"
    )


def _build_export_command(args: argparse.Namespace) -> list[str]:
    cmd = _resolve_optimum_cli_prefix()
    cmd += [
        "export",
        "onnx",
        "--model",
        args.model,
        "--task",
        args.task,
    ]

    if args.trust_remote_code:
        cmd.append("--trust-remote-code")
    if args.revision:
        cmd += ["--revision", args.revision]
    if args.cache_dir:
        cmd += ["--cache_dir", str(Path(args.cache_dir))]
    if args.monolith:
        cmd.append("--monolith")
    if args.device:
        cmd += ["--device", args.device]

    for raw_arg in args.extra_arg:
        cmd.append(raw_arg)

    cmd.append(str(Path(args.output_dir)))
    return cmd


def _print_command(cmd: list[str]) -> None:
    print("Running command:")
    print("  " + shlex.join(cmd))


def _run_or_fail(cmd: list[str], dry_run: bool) -> int:
    _print_command(cmd)
    if dry_run:
        return 0

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ONNX export failed (exit code {result.returncode}).")
    return result.returncode


def _collect_onnx_files(
    output_dir: Path,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[Path]:
    candidates = sorted(output_dir.rglob("*.onnx"))
    selected: list[Path] = []

    for file_path in candidates:
        rel = file_path.relative_to(output_dir).as_posix()
        if include_patterns and not any(fnmatch.fnmatch(rel, p) for p in include_patterns):
            continue
        if exclude_patterns and any(fnmatch.fnmatch(rel, p) for p in exclude_patterns):
            continue
        selected.append(file_path)
    return selected


def _quantize_dynamic_int8(
    model_path: Path,
    output_path: Path,
    per_channel: bool,
    reduce_range: bool,
    use_external_data_format: bool,
    op_types_to_quantize: list[str] | None,
) -> None:
    if not _has_module("onnxruntime"):
        raise RuntimeError(
            "onnxruntime is required for quantization. Install with: pip install -U onnxruntime"
        )

    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(
        model_input=str(model_path),
        model_output=str(output_path),
        per_channel=per_channel,
        reduce_range=reduce_range,
        weight_type=QuantType.QInt8,
        use_external_data_format=use_external_data_format,
        op_types_to_quantize=op_types_to_quantize or None,
    )


def _quantize_exported_models(args: argparse.Namespace, output_dir: Path) -> None:
    onnx_files = _collect_onnx_files(
        output_dir=output_dir,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
    )
    if not onnx_files:
        raise RuntimeError(
            "No ONNX files found to quantize. Adjust --include/--exclude or check export output."
        )

    op_types = [x.strip() for x in args.quant_op_type if x.strip()]
    print(f"Found {len(onnx_files)} ONNX files for quantization.")

    for source_model in onnx_files:
        quantized_model = source_model.with_name(
            f"{source_model.stem}{args.quant_suffix}{source_model.suffix}"
        )

        print(f"Quantizing: {source_model} -> {quantized_model}")
        _quantize_dynamic_int8(
            model_path=source_model,
            output_path=quantized_model,
            per_channel=args.per_channel,
            reduce_range=args.reduce_range,
            use_external_data_format=args.use_external_data_format,
            op_types_to_quantize=op_types,
        )

    print("ONNX quantization complete.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Hugging Face model to ONNX and optionally quantize ONNX files."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Hugging Face model id or local model path.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for ONNX files.",
    )
    parser.add_argument(
        "--task",
        default="text-generation-with-past",
        help="Exporter task (default: text-generation-with-past).",
    )
    parser.add_argument(
        "--quantize",
        default="none",
        choices=QUANT_CHOICES,
        help="Quantization mode (none/int8_dynamic).",
    )
    parser.add_argument(
        "--quant-suffix",
        default=".int8",
        help="Suffix for quantized ONNX files (before .onnx extension).",
    )
    parser.add_argument(
        "--quant-op-type",
        action="append",
        default=[],
        help=(
            "Restrict quantization to specific op type, e.g. MatMul. "
            "Repeat to pass multiple op types."
        ),
    )
    parser.add_argument(
        "--per-channel",
        action="store_true",
        help="Enable per-channel quantization for weights.",
    )
    parser.add_argument(
        "--reduce-range",
        action="store_true",
        help="Use reduced quantization range.",
    )
    parser.add_argument(
        "--use-external-data-format",
        action="store_true",
        help="Enable external data format for large quantized ONNX models.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help=(
            "Glob pattern (relative to output-dir) to include for quantization. "
            "Repeat to add multiple patterns."
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help=(
            "Glob pattern (relative to output-dir) to exclude from quantization. "
            "Repeat to add multiple patterns."
        ),
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Hugging Face revision/branch/tag.",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Model cache directory used by exporter.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Exporter device, e.g. cpu.",
    )
    parser.add_argument(
        "--monolith",
        action="store_true",
        help="Pass --monolith to exporter (if supported).",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Pass --trust-remote-code to exporter.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help=(
            "Raw extra arg passed to optimum-cli export onnx. "
            "Repeat this option to pass multiple args."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print export command without executing it.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    export_cmd = _build_export_command(args)
    _run_or_fail(export_cmd, dry_run=args.dry_run)

    if args.dry_run:
        return 0

    if args.quantize == "int8_dynamic":
        _quantize_exported_models(args=args, output_dir=output_dir)
    else:
        print("Quantization disabled (--quantize none).")

    print(f"ONNX export complete: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
