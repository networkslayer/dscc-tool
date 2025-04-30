from pathlib import Path
from .presets.detection_preset import DetectionPreset

class PresetEngine:
    @staticmethod
    def from_path(path: Path):
        path_parts = path.parts
        if "detections" in path_parts:
            return DetectionPreset(path)
        raise ValueError(f"❌ Could not determine preset type from path: {path}")
