from .base_preset import BasePreset
from ..mitre_loader import load_mitre_attack
from dscc_packaging.models import DSCCDetectionMetadata, DSCCNotebookMetadata
import re
from dscc_packaging.shared_utils import infer_user_name, infer_user_email, get_promptable_fields
from datetime import datetime
import uuid
from pydantic_core import PydanticUndefined
from dscc_packaging.model_utils import default_for_field, get_options_from_model, get_validators_from_model, get_help_from_model

class DetectionPreset(BasePreset):
    MODEL = DSCCDetectionMetadata
    MULTI_SELECT_FIELDS = ["taxonomy", "platform"]

    # Only keep dynamic MITRE options and dependencies
    DEPENDENCIES = {
        "taxonomy": {
            "mitre": ["tactic", "technique", "sub_technique"],
        }
    }

    def __init__(self, notebook_path):
        super().__init__(notebook_path)
        # Only keep detection-specific fields
        self.fields = {k: v for k, v in self.fields.items() if k in DSCCDetectionMetadata.model_fields}

        # Set a default name from the notebook filename if not already set or if PydanticUndefined
        name_val = self.fields.get("name")
        if not isinstance(name_val, str) or name_val in (None, "<name>", "", PydanticUndefined):
            stem = notebook_path.stem
            clean_name = re.sub(r'[_\-]+', ' ', stem).title()
            self.fields["name"] = clean_name

        # Fill in all model defaults for missing fields
        model_defaults = self.MODEL().model_dump()
        for k, v in model_defaults.items():
            if k not in self.fields or self.fields[k] is None:
                self.fields[k] = v

        # Load MITRE data for dynamic options
        all_tactics, all_techniques, all_sub_techniques = load_mitre_attack()
        self._all_tactics = all_tactics
        self._all_techniques = all_techniques
        self._all_sub_techniques = all_sub_techniques
        self.OPTIONS = get_options_from_model(DSCCDetectionMetadata)
        self.OPTIONS["tactic"] = all_tactics
        self.OPTIONS["technique"] = [f"{t['id']} {t['name']}" for t in all_techniques]
        self.OPTIONS["sub_technique"] = [f"{s['id']} {s['name']}" for s in all_sub_techniques]

    def to_yaml_dict(self):
        print("DEBUG DetectionPreset.to_yaml_dict self.fields:", self.fields)
        taxonomy = self.fields.get("taxonomy", [])
        print("DEBUG taxonomy before normalization:", taxonomy)
        # Always treat taxonomy as a list
        if taxonomy is None:
            taxonomy = []
        elif isinstance(taxonomy, str):
            taxonomy = [taxonomy]
        # Build MITRE block before filtering
        mitre_block = None
        if "mitre" in taxonomy:
            mitre_block = {
                "tactic": self.fields.pop("tactic", None),
                "technique": self.fields.pop("technique", None),
                "sub_technique": self.fields.pop("sub_technique", None)
            }
            mitre_block = {k: v for k, v in mitre_block.items() if v}
        # Now filter to only detection fields
        fields = {k: v for k, v in self.fields.items() if k in DSCCDetectionMetadata.model_fields}
        # Build taxonomy list
        if "mitre" in taxonomy:
            taxonomy_list = []
            if mitre_block:
                taxonomy_list.append({"mitre": mitre_block})
            taxonomy_list += [t for t in taxonomy if t != "mitre"]
            fields["taxonomy"] = taxonomy_list
        else:
            fields["taxonomy"] = taxonomy
        return {"dscc": fields}

class NotebookPreset(BasePreset):
    MODEL = DSCCNotebookMetadata
    MULTI_SELECT_FIELDS = []

    def __init__(self, notebook_path):
        super().__init__(notebook_path)
        # Set inferred defaults for author and user_email if not already set
        if self.fields.get("author") in (None, "<author>", ""):
            self.fields["author"] = infer_user_name()
        if "user_email" in self.fields and self.fields.get("user_email") in (None, "<user_email>", ""):
            self.fields["user_email"] = infer_user_email()
        now = datetime.now().isoformat(timespec="seconds")
        if self.fields.get("created") in (None, "<created>", ""):
            self.fields["created"] = now
        if self.fields.get("modified") in (None, "<modified>", ""):
            self.fields["modified"] = now
        # Ensure uuid is set and valid
        try:
            val = self.fields.get("uuid")
            uuid.UUID(str(val))
        except Exception:
            self.fields["uuid"] = str(uuid.uuid4())

    def prompt_user(self):
        # ANSI color codes
        BLUE = '\033[94m'
        RED = '\033[91m'
        BOLD = '\033[1m'
        ENDC = '\033[0m'
        # Notebook section header
        print(f"\n{BOLD}{BLUE}{'🟦'*10} 📝 NOTEBOOK METADATA {'🟦'*10}{ENDC}")
        print(f"{BOLD}{BLUE}Fill in the general metadata for this notebook.{ENDC}\n")
        keys = [k for k in get_promptable_fields(self.MODEL) if k != "detection"]
        self.prompt_fields(keys)
        # Detection section header
        if "detection" in self.MODEL.model_fields:
            print(f"\n{BOLD}{RED}{'🟥'*10} 🔎 DETECTION METADATA {'🟥'*10}{ENDC}")
            print(f"{BOLD}{RED}Now fill in detection-specific fields for this notebook.{ENDC}\n")
            detection_preset = DetectionPreset(self.notebook_path)
            detection_preset.prompt_user()
            self.fields["detection"] = detection_preset.fields
        return self

    def to_yaml_dict(self):
        fields = dict(self.fields)
        if "detection" in fields and isinstance(fields["detection"], dict):
            detection_fields = fields["detection"]
            detection_preset = DetectionPreset(self.notebook_path)
            detection_preset.fields = detection_fields
            fields["detection"] = detection_preset.to_yaml_dict()["dscc"]  # Use the cleaned dict!
        return {"dscc": fields}
