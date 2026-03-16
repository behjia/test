import json
import shutil
from pathlib import Path
from typing import Any


class IPManager:
    def __init__(self, library_path: str = "ip_library") -> None:
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)

    def save_ip(
        self,
        module_name: str,
        sv_path: Path | str,
        spec_dict: dict,
        synth_metrics: dict[str, Any],
    ) -> None:
        dest_sv = self.library_path / f"{module_name}.sv"
        shutil.copy(Path(sv_path), dest_sv)
        with open(self.library_path / f"{module_name}.json", "w", encoding="utf-8") as fh:
            json.dump(spec_dict, fh, indent=2)
        with open(
            self.library_path / f"{module_name}_metrics.json",
            "w",
            encoding="utf-8",
        ) as fh:
            json.dump(synth_metrics, fh, indent=2)

    def get_semantic_catalog(self) -> str:
        lines: list[str] = []
        for json_path in sorted(self.library_path.glob("*.json")):
            try:
                spec = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            module_name = spec.get("module_name", json_path.stem)
            description = spec.get("description", "No description")
            metrics_path = self.library_path / f"{module_name}_metrics.json"
            gate_count = "unknown"
            if metrics_path.exists():
                try:
                    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                    gate_count = metrics.get("gate_count", "unknown")
                except Exception:
                    pass
            lines.append(
                f"- {module_name}: {description} (Cost: {gate_count} gates)"
            )
        return "\n".join(lines)
