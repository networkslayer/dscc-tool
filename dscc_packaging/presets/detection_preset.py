from .base_preset import BasePreset
from ..mitre_loader import load_mitre_attack, filter_techniques_for_tactic
from dscc_packaging.models import DSCCDetectionMetadata, Severity
import re
from typing import get_args, get_origin, Literal
from dscc_packaging.shared_utils import infer_user_name, infer_user_email
from datetime import datetime
import uuid
from pydantic_core import PydanticUndefined, PydanticUndefinedType
from enum import Enum

def _default_for_field(name, field):
    if field.default is not None:
        return field.default
    elif field.annotation == list or getattr(field.annotation, '__origin__', None) is list:
        return []
    elif field.annotation == str:
        return ""
    elif getattr(field.annotation, '__origin__', None) is Literal:
        # For Literal types, use the first allowed value as default
        return get_args(field.annotation)[0]
    else:
        return f"<{name}>"

def get_options_from_model(model_cls):
    options = {}
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        if get_origin(ann) is Literal:
            options[name] = list(get_args(ann))
        elif get_origin(ann) is list and get_origin(get_args(ann)[0]) is Literal:
            options[name] = list(get_args(get_args(ann)[0]))
    return options

def get_validators_from_model(model_cls):
    validators = {}
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        if get_origin(ann) is Literal:
            allowed = set(get_args(ann))
            validators[name] = lambda v, allowed=allowed: v in allowed
        elif ann is int:
            validators[name] = lambda v: isinstance(v, int)
        elif ann is str:
            validators[name] = lambda v: isinstance(v, str) and v.strip() != ""
    return validators

def get_help_from_model(model_cls):
    help_text = {}
    for name, field in model_cls.model_fields.items():
        if hasattr(field, 'description') and field.description:
            help_text[name] = field.description
        elif get_origin(field.annotation) is Literal:
            help_text[name] = f"Allowed values: {', '.join(map(str, get_args(field.annotation)))}"
        else:
            help_text[name] = f"Type: {field.annotation}"
    return help_text

class DetectionPreset(BasePreset):
    MULTI_SELECT_FIELDS = ["taxonomy", "platform"]

    CATEGORY_OPTIONS = [
        ("DETECTION", "When your SIEM/detection engine flags suspicious activity not tied to a specific type (e.g., generic correlation alerts)."),
        ("MALWARE", "When the detection is malware-related."),
        ("THREAT", "For threat intelligence matches or threat scoring."),
        ("INTRUSION", "For confirmed or strongly suspected intrusions."),
        ("ANOMALY", "For UEBA, baselining, or behavioral anomalies."),
        ("POLICY", "When the detection involves a policy violation (e.g., blocked application, DLP)."),
        ("SPECIAL_EVENT", "Temporary report ran with higher regularity and priority for CSIRT special event monitoring (i.e conferences, pen tests)"),
    ]

    # Only include global fields in FIELDS
    FIELDS = {
        "author": "<author>",
        "created": "<created>",
        "modified": "<modified>",
        "version": "1.0.0",
        "content_type": "detection",
        "uuid": "<uuid>",
        "platform": "databricks",
        # detection-specific fields will be nested under 'detection'
    }

    # Dynamically generate OPTIONS, VALIDATORS, HELP
    OPTIONS = {
        **get_options_from_model(DSCCDetectionMetadata),
        # Add or override any custom options here:
        "taxonomy": ["mitre", "nist", "none"],
        "platform": ["linux", "windows", "macos", "databricks", "aws", "azure", "gcp", "kubernetes", "other"],
        "tactic": [],
        "technique": [],
        "sub_technique": [],
        "fidelity": ["high", "medium", "low"],  # Add fidelity options
        "category": [v[0] for v in CATEGORY_OPTIONS],
        "severity": [v.value for v in Severity],
    }

    VALIDATORS = {
        **get_validators_from_model(DSCCDetectionMetadata),
        # Add or override any custom validators here:
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
        **get_help_from_model(DSCCDetectionMetadata),
        # Only add or override help here if you want to supplement the model's description
        "version": "Must be in semantic version format (e.g., 1.0.0)",
        "name": "Must be a clean name without < or > characters.",
        "category": "Choose the most appropriate OCSF category for this detection.",
    }

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

        all_tactics, all_techniques, all_sub_techniques = load_mitre_attack()
        self._all_tactics = all_tactics
        self._all_techniques = all_techniques
        self._all_sub_techniques = all_sub_techniques

        self.OPTIONS = dict(self.OPTIONS)
        self.OPTIONS["tactic"] = all_tactics
        self.OPTIONS["technique"] = [f"{t['id']} {t['name']}" for t in all_techniques]
        self.OPTIONS["sub_technique"] = [f"{s['id']} {s['name']}" for s in all_sub_techniques]

        # If detection, initialize detection-specific fields as a nested dict
        if self.fields.get("content_type", "detection") == "detection":
            if "detection" not in self.fields or not isinstance(self.fields["detection"], dict):
                self.fields["detection"] = {name: _default_for_field(name, field) for name, field in DSCCDetectionMetadata.model_fields.items()}
            # Set a default name from the notebook filename if not already set or if PydanticUndefined
            name_val = self.fields["detection"].get("name")
            if name_val in (None, "<name>", "", PydanticUndefined):
                stem = notebook_path.stem
                clean_name = re.sub(r'[_\-]+', ' ', stem).title()
                self.fields["detection"]["name"] = clean_name

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

    def prompt_user(self):
        print(f"\n📓 Notebook: {self.notebook_path}")
        # Detect content type
        content_type = self.fields.get("content_type", "detection")
        print(f"🔍 Detected content type: {content_type.capitalize()}")

        def render_options(options, key=None):
            if key == "category":
                return "\n".join([f"    {i+1}. {v} - {hint}" for i, (v, hint) in enumerate(self.CATEGORY_OPTIONS)])
            return "\n".join([f"    {i+1}. {v}" for i, v in enumerate(options)])

        def parse_option_input(user_val, options, is_multi):
            if not user_val:
                return [] if is_multi else None
            try:
                idxs = [int(x.strip())-1 for x in user_val.split(",") if x.strip()]
                if is_multi:
                    return [options[i] for i in idxs if 0 <= i < len(options)]
                else:
                    i = idxs[0]
                    return options[i] if 0 <= i < len(options) else None
            except Exception:
                return user_val  # fallback to raw value

        def is_unset(val):
            return val is None or val == "" or val == PydanticUndefined or isinstance(val, PydanticUndefinedType)

        def display_value(val):
            if isinstance(val, Enum):
                return val.value
            return str(val)

        # --- Prompt for global notebook metadata (DSCCNotebookMetadata) ---
        global_keys = [
            k for k in self.fields.keys()
            if k in ["author", "created", "modified", "version", "content_type", "platform"]  # uuid removed
        ]
        i = 0
        while i < len(global_keys):
            key = global_keys[i]
            options = getattr(self, "OPTIONS", {}).get(key)
            validator = getattr(self, "VALIDATORS", {}).get(key)
            back_requested = False
            is_multi_select = key in getattr(self, "MULTI_SELECT_FIELDS", [])
            value = self.fields.get(key)
            suggestion = value if not is_unset(value) and value != f"<{key}>" else None
            # Print help/hint for any field with HELP text
            help_str = getattr(self, "HELP", {}).get(key)
            if help_str:
                print(f"  \033[36mHint: {help_str}\033[0m")
            # Show current selection as text value(s)
            if options:
                if suggestion:
                    if is_multi_select and isinstance(suggestion, list):
                        current = ", ".join(display_value(v) for v in suggestion if v in options)
                    elif suggestion in options:
                        current = display_value(suggestion)
                    else:
                        current = ""
                else:
                    current = ""
                prompt_str = f"  {key} [{current}] (or B to go back): "
            else:
                prompt_str = f"  {key} [{display_value(suggestion) if suggestion is not None else ''}] (or B to go back): "
            if options:
                print("  Options:")
                print(render_options(options, key))
            user_val = input(prompt_str).strip()
            if user_val.lower() == "b":
                if i > 0:
                    i -= 1
                else:
                    print("\u26A0\ufe0f Already at the first field.")
                continue
            if options:
                parsed = parse_option_input(user_val, options, is_multi_select)
                if is_multi_select:
                    value = parsed if parsed else suggestion or []
                else:
                    value = parsed if parsed else suggestion
                # Print the text value(s) chosen
                if is_multi_select:
                    print(f"  Selected: {', '.join(display_value(v) for v in value)}")
                else:
                    print(f"  Selected: {display_value(value)}")
            elif user_val:
                if is_multi_select:
                    value = [v.strip() for v in user_val.split(",") if v.strip()]
                else:
                    value = user_val
            # Validate
            if validator:
                # Only call .strip() if value is a string
                first_val = value if not isinstance(value, list) else value[0]
                if is_unset(first_val):
                    first_val = ""
                if not validator(first_val):
                    print("\u26A0\ufe0f Invalid value. Try again.")
                    help_str = getattr(self, "HELP", {}).get(key)
                    if help_str:
                        print(f"\u2139\ufe0f Hint: {help_str}")
                    continue
            self.fields[key] = value
            i += 1

        # --- Prompt for detection-specific fields if content_type == 'detection' ---
        if self.fields.get("content_type", "detection") == "detection":
            print("\n🛡️ Detection-specific metadata:")
            detection_keys = [k for k in DSCCDetectionMetadata.model_fields.keys()]
            # Remove any already prompted global fields
            detection_keys = [k for k in detection_keys if k not in global_keys]
            if "detection" not in self.fields or not isinstance(self.fields["detection"], dict):
                self.fields["detection"] = {}
            i = 0
            while i < len(detection_keys):
                key = detection_keys[i]
                options = getattr(self, "OPTIONS", {}).get(key)
                validator = getattr(self, "VALIDATORS", {}).get(key)
                value = self.fields["detection"].get(key)
                suggestion = value if not is_unset(value) and value != f"<{key}>" else None
                # Print help/hint for any field with HELP text
                help_str = getattr(self, "HELP", {}).get(key)
                if help_str:
                    print(f"  \033[36mHint: {help_str}\033[0m")
                # Show current selection as text value(s)
                if options:
                    if suggestion:
                        if isinstance(suggestion, list):
                            current = ", ".join(display_value(v) for v in suggestion if v in options)
                        elif suggestion in options:
                            current = display_value(suggestion)
                        else:
                            current = ""
                    else:
                        current = ""
                    prompt_str = f"  {key} [{current}] (or B to go back): "
                else:
                    prompt_str = f"  {key} [{display_value(suggestion) if suggestion is not None else ''}] (or B to go back): "
                if options:
                    print("  Options:")
                    print(render_options(options, key))
                user_val = input(prompt_str).strip()
                if user_val.lower() == "b":
                    if i > 0:
                        i -= 1
                    else:
                        print("\u26A0\ufe0f Already at the first field.")
                    continue
                if options:
                    parsed = parse_option_input(user_val, options, key in getattr(self, "MULTI_SELECT_FIELDS", []))
                    if key in getattr(self, "MULTI_SELECT_FIELDS", []):
                        value = parsed if parsed else suggestion or []
                    else:
                        value = parsed if parsed else suggestion
                    # Print the text value(s) chosen
                    if key in getattr(self, "MULTI_SELECT_FIELDS", []):
                        print(f"  Selected: {', '.join(display_value(v) for v in value)}")
                    else:
                        print(f"  Selected: {display_value(value)}")
                elif user_val:
                    if isinstance(DSCCDetectionMetadata.model_fields[key].annotation, type) and issubclass(DSCCDetectionMetadata.model_fields[key].annotation, list):
                        value = [v.strip() for v in user_val.split(",") if v.strip()]
                    else:
                        value = user_val
                # Validate
                if validator:
                    # Only call .strip() if value is a string
                    first_val = value if not isinstance(value, list) else value[0]
                    if is_unset(first_val):
                        first_val = ""
                    if not validator(first_val):
                        print("\u26A0\ufe0f Invalid value. Try again.")
                        help_str = getattr(self, "HELP", {}).get(key)
                        if help_str:
                            print(f"\u2139\ufe0f Hint: {help_str}")
                        continue
                self.fields["detection"][key] = value
                i += 1
        return self
