"""Path-related runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile


@dataclass(slots=True)
class PathsConfig:
    project_root: Path
    template_dir: str
    static_dir: str
    data_dir: str
    project_db_path: str
    default_db_path: str

    @classmethod
    def build(cls, project_root: Path | None = None) -> "PathsConfig":
        root = project_root or Path(__file__).resolve().parent.parent
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            project_root=root,
            template_dir=str(root / "templates"),
            static_dir=str(root / "static"),
            data_dir=str(data_dir),
            project_db_path=str(data_dir / "thinking_graph.db"),
            default_db_path=str(Path(tempfile.gettempdir()) / "thinking_graph.db"),
        )
