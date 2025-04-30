from .base_preset import BasePreset
from ..mitre_loader import load_mitre_attack, filter_techniques_for_tactic
import re

class DetectionPreset(BasePreset):

    MULTI_SELECT_FIELDS = ["taxonomy", "platform"]

    FIELDS = {
        "name": "<name>",
        "version": "1.0.0",
        "description": "TODO: fill in a detection description.",
        "objectives": "What are the objectives of this detection?",
        "taxonomy": [],
        "severity": "medium",
        "fidelity": "medium",
        "platform": ["linux"],
        "false_positives": "unknown",
    }

    OPTIONS = {
        "taxonomy": ["mitre", "nist", "none"],
        "severity": ["low", "medium", "high"],
        "fidelity": ["low", "medium", "high"],
        "validation": ["manual", "automated", "mixed"],
        "platform": ["linux", "windows", "macos"],
        "tactic": [],
        "technique": [],
        "sub_technique": [],
    }

    VALIDATORS = {
        "version": lambda v: bool(re.match(r'^\d+\.\d+\.\d+$', v)),
        "description": lambda v: v.strip() != "" and not v.lower().startswith("todo"),
        "name": lambda v: v.strip() != "" and "<" not in v and ">" not in v,
    }

    DEPENDENCIES = {
        "taxonomy": {
            "mitre": ["tactic", "technique", "sub_technique"],
        }
    }

    HELP = {
        "version": "Must be in semantic version format (e.g., 1.0.0)",
        "description": "Cannot be empty or say 'TODO'.",
        "name": "Must be a clean name without < or > characters.",
    }

    def __init__(self, notebook_path):
        super().__init__(notebook_path)

        all_tactics, all_techniques, all_sub_techniques = load_mitre_attack()
        self._all_tactics = all_tactics
        self._all_techniques = all_techniques
        self._all_sub_techniques = all_sub_techniques

        self.OPTIONS = dict(self.OPTIONS)
        self.OPTIONS["tactic"] = all_tactics
        self.OPTIONS["technique"] = [f"{t['id']} {t['name']}" for t in all_techniques]
        self.OPTIONS["sub_technique"] = [f"{s['id']} {s['name']}" for s in all_sub_techniques]

    def to_yaml_dict(self):
        fields = dict(self.fields)  # Make a shallow copy
        if "mitre" in fields.get("taxonomy", []):
            mitre_block = {
                "tactic": fields.pop("tactic", None),
                "technique": fields.pop("technique", None),
                "sub_technique": fields.pop("sub_technique", None)
            }
            # Clean out empty values
            mitre_block = {k: v for k, v in mitre_block.items() if v}
            fields["taxonomy"] = [
                {"mitre": mitre_block},
                *[t for t in fields["taxonomy"] if t != "mitre"]
            ]
        return {"dscc": fields}
