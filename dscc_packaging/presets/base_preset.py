from pathlib import Path
import re
from typing import Dict, Any
from ..mitre_loader import filter_techniques_for_tactic
from dscc_packaging.shared_utils import get_promptable_fields
from dscc_packaging.model_utils import get_options_from_model

class BasePreset:
    FIELDS: Dict[str, Any] = {}
    MODEL = None  # Subclasses should set this to the relevant Pydantic model

    def __init__(self, notebook_path: Path):
        self.notebook_path = notebook_path
        self.fields = dict(self.FIELDS)

        stem = notebook_path.stem
        if "name" in self.fields and self.fields["name"] in ("<name>", None):
            clean_name = re.sub(r'[_\-]+', ' ', stem).title()
            self.fields["name"] = clean_name

    def prompt_fields(self, keys):
        model_options = get_options_from_model(self.MODEL)
        i = 0
        injected_deps = False

        while i < len(keys):
            key = keys[i]
            field_info = self.MODEL.model_fields[key]
            options = model_options.get(key) or getattr(self, "OPTIONS", {}).get(key)
            validator = getattr(self, "VALIDATORS", {}).get(key)
            back_requested = False
            is_multi_select = key in getattr(self, "MULTI_SELECT_FIELDS", [])

            default = self.fields.get(key)
            if default is None:
                if getattr(field_info, 'default', None) is not None and str(field_info.default) != 'PydanticUndefined':
                    default = field_info.default
                elif getattr(field_info, 'default_factory', None) is not None:
                    try:
                        default = field_info.default_factory()
                    except Exception:
                        default = "<fill me>"
                else:
                    default = "<fill me>"
            if hasattr(default, 'value'):
                default = default.value
            help_str = getattr(self, "HELP", {}).get(key) or getattr(field_info, "description", None)

            while True:
                if help_str:
                    print(f"  \033[36mHint: {help_str}\033[0m")
                if options is not None:
                    print(f"  [DEBUG] options for {key}: {options}")
                if options:
                    print(f"  {key}:")
                    for idx, opt in enumerate(options, 1):
                        print(f"    {idx}. {opt}")
                    if is_multi_select:
                        current = ", ".join(default) if isinstance(default, list) and default else ""
                        prompt = f"Select {key} (comma-separated numbers) [{current}] (or B to go back): "
                    else:
                        current = default
                        prompt = f"Select {key} (comma-separated numbers) [{current}] (or B to go back): "
                else:
                    current = ", ".join(default) if isinstance(default, list) and default else default
                    prompt = f"  {key} [{current}] (or B to go back): "

                user_input = input(prompt).strip()

                if user_input.lower() == 'b':
                    back_requested = True
                    break

                if not user_input:
                    value = default
                    # If the default is a placeholder, require user input
                    if isinstance(value, str) and value.startswith("<") and value.endswith(">"):
                        print("\u26A0\ufe0f This field is required. Please provide a value.")
                        continue
                else:
                    if options:
                        selections = [s.strip() for s in user_input.split(',') if s.strip().isdigit()]
                        selected_indices = [int(s) for s in selections if 1 <= int(s) <= len(options)]
                        if not selected_indices:
                            print("\u26A0\ufe0f Invalid choice. Try again.")
                            continue
                        if is_multi_select:
                            value = [options[i-1] for i in selected_indices]
                        else:
                            value = options[selected_indices[0]-1]
                    else:
                        value = [v.strip() for v in user_input.split(',')] if is_multi_select else user_input

                if validator:
                    first_val = value if not isinstance(value, list) else value[0]
                    if not validator(first_val):
                        print("\u26A0\ufe0f Invalid value. Try again.")
                        if help_str:
                            print(f"\u2139\ufe0f Hint: {help_str}")
                        continue

                self.fields[key] = value

                dep_rules = getattr(type(self), "DEPENDENCIES", {}).get(key)
                print(f"[DEBUG] Checking dependencies for key={key}, value={value}, dep_rules={dep_rules}")
                if dep_rules:
                    selected_values = value if isinstance(value, list) else [value]
                    print(f"[DEBUG] selected_values: {selected_values} (type: {[type(v) for v in selected_values]})")
                    injected = []
                    for sv in selected_values:
                        dep_key = sv.value if hasattr(sv, 'value') else sv
                        print(f"[DEBUG] dep_key: {dep_key} (type: {type(dep_key)})")
                        dependent_fields = dep_rules.get(dep_key, [])
                        print(f"[DEBUG] dependent_fields for dep_key={dep_key}: {dependent_fields}")
                        for dep in dependent_fields:
                            if dep in keys:
                                keys.remove(dep)
                        for idx, dep in enumerate(dependent_fields):
                            keys.insert(i + 1 + idx, dep)
                            injected.append(dep)
                        if injected:
                            print(f"[DEBUG] Injected dependencies after {key}: {injected}")
                            print(f"[DEBUG] New prompt order: {keys}")
                            i = keys.index(injected[0]) - 1
                            continue

                if key == "tactic":
                    tactic = self.fields.get("tactic")
                    if tactic:
                        techniques, sub_techniques = filter_techniques_for_tactic(
                            tactic, self._all_techniques, self._all_sub_techniques
                        )
                        self.OPTIONS["technique"] = techniques
                        self.OPTIONS["sub_technique"] = sub_techniques
                        self.fields["technique"] = ""
                        self.fields["sub_technique"] = ""
                if key == "technique":
                    tactic = self.fields.get("tactic")
                    technique = self.fields.get("technique")
                    if technique:
                        technique_id = technique.split()[0] if isinstance(technique, str) else ""
                        _, sub_techniques = filter_techniques_for_tactic(
                            tactic, self._all_techniques, self._all_sub_techniques, technique_id
                        )
                        self.OPTIONS["sub_technique"] = sub_techniques
                        self.fields["sub_technique"] = ""
                break

            if injected_deps:
                injected_deps = False
                continue

            if back_requested:
                if i > 0:
                    i -= 1
                else:
                    print("\u26A0\ufe0f Already at the first field.")
                continue

            dep_rules = getattr(type(self), "DEPENDENCIES", {}).get(key)
            if dep_rules:
                selected_value = self.fields[key]
                selected_values = selected_value if isinstance(selected_value, list) else [selected_value]
                inserted = False
                print(f"selected_values: {selected_values}")
                for sv in selected_values:
                    dep_key = sv.value if hasattr(sv, 'value') else sv
                    dependent_fields = dep_rules.get(dep_key, [])

                    for dep in reversed(dependent_fields):
                        if dep not in self.fields:
                            self.fields[dep] = "<fill me>"

                        if dep not in keys:
                            keys.insert(i + 1, dep)
                            inserted = True
                if inserted:
                    i += 1
                    continue

            i += 1
        return self

    def prompt_user(self):
        print(f"[DEBUG] Using preset class: {self.__class__.__name__}")
        print(f"\n\U0001F4DD Generating metadata for: {self.notebook_path.name}")

        if not self.MODEL:
            raise ValueError("BasePreset.MODEL must be set to a Pydantic model class in subclasses.")
        keys = get_promptable_fields(self.MODEL)
        return self.prompt_fields(keys)

    def to_yaml_dict(self):
        return {"dscc": self.fields}
