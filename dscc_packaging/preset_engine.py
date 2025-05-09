from pathlib import Path
from .presets.detection_preset import DetectionPreset, NotebookPreset

class PresetEngine:
    @staticmethod
    def from_path(path: Path):
        path_parts = path.parts
        if "detections" in path_parts:
            # For detection notebooks, wrap the DetectionPreset in a NotebookPreset
            notebook_preset = NotebookPreset(path)
            notebook_preset.fields["content_type"] = "detection"
            notebook_preset.fields["detection"] = DetectionPreset(path).fields
            return notebook_preset
        return NotebookPreset(path)  # Default to NotebookPreset for all other notebooks
