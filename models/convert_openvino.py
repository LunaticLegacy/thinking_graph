#!/usr/bin/env python
"""Export a Hugging Face CausalLM model to OpenVINO with optional quantization.

Examples:
    python models/convert_openvino.py \
      --model Qwen/Qwen2.5-1.5B-Instruct \
      --output-dir models/qwen2.5-1.5b-openvino \
      --weight-format int4 \
      --group-size 128 \
      --ratio 0.8 \
      --trust-remote-code
"""

from __future__ import annotations

import argparse
import importlib.util
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


WEIGHT_FORMAT_CHOICES = ("none", "fp16", "int8", "int4")


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _resolve_optimum_cli_prefix() -> list[str]:
    if shutil.which("optimum-cli"):
        return ["optimum-cli"]
    if _has_module("optimum"):
        return [sys.executable, "-m", "optimum.commands.optimum_cli"]
    raise RuntimeError(
        "Cannot find `optimum-cli`. Install with: pip install -U optimum[openvino] optimum-intel"
    )


def _build_command(args: argparse.Namespace) -> list[str]:
    cmd = _resolve_optimum_cli_prefix()
    cmd += [
        "export",
        "openvino",
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

    if args.weight_format != "none":
        cmd += ["--weight-format", args.weight_format]
    if args.group_size is not None:
        cmd += ["--group-size", str(args.group_size)]
    if args.ratio is not None:
        cmd += ["--ratio", str(args.ratio)]
    if args.sym:
        cmd.append("--sym")
    if args.awq:
        cmd.append("--awq")
    if args.dataset:
        cmd += ["--dataset", args.dataset]

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
        raise RuntimeError(f"OpenVINO export failed (exit code {result.returncode}).")
    return result.returncode


def _verify_openvino_artifacts(output_dir: Path) -> None:
    xml_files = sorted(output_dir.rglob("*.xml"))
    bin_files = sorted(output_dir.rglob("*.bin"))

    if not xml_files:
        print(
            "Warning: no .xml files were found in the output directory. "
            "The export may have failed or produced an unexpected layout."
        )
        return

    print(f"OpenVINO XML files: {len(xml_files)}")
    if not bin_files:
        print("Warning: no .bin files found next to XML files.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Hugging Face model to OpenVINO IR/GenAI format."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Hugging Face model id or local model path.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for the exported OpenVINO model.",
    )
    parser.add_argument(
        "--task",
        default="text-generation-with-past",
        help="Exporter task (default: text-generation-with-past).",
    )
    parser.add_argument(
        "--weight-format",
        default="none",
        choices=WEIGHT_FORMAT_CHOICES,
        help="Quantized/weight format for export (none/fp16/int8/int4).",
    )
    parser.add_argument(
        "--group-size",
        type=int,
        default=None,
        help="Group size for weight-only quantization (commonly used with int4).",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=None,
        help="Outlier ratio for weight-only quantization (if supported by exporter).",
    )
    parser.add_argument(
        "--sym",
        action="store_true",
        help="Use symmetric quantization (if supported by exporter).",
    )
    parser.add_argument(
        "--awq",
        action="store_true",
        help="Enable AWQ flow (if supported by exporter).",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Calibration dataset name/path when exporter requires it.",
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
        "--trust-remote-code",
        action="store_true",
        help="Pass --trust-remote-code to exporter.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help=(
            "Raw extra arg passed to optimum-cli. Repeat this option to pass multiple args."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print final command without executing it.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = _build_command(args)
    _run_or_fail(cmd, dry_run=args.dry_run)

    if not args.dry_run:
        _verify_openvino_artifacts(output_dir)
        print(f"OpenVINO export complete: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
