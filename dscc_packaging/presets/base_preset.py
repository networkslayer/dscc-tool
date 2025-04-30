from pathlib import Path
import re
from typing import Dict, Any
from ..mitre_loader import filter_techniques_for_tactic

class BasePreset:
    FIELDS: Dict[str, Any] = {}

    def __init__(self, notebook_path: Path):
        self.notebook_path = notebook_path
        self.fields = dict(self.FIELDS)

        stem = notebook_path.stem
        if "name" in self.fields and self.fields["name"] in ("<name>", None):
            clean_name = re.sub(r'[_\-]+', ' ', stem).title()
            self.fields["name"] = clean_name

    def prompt_user(self):
        print(f"\n\U0001F4DD Generating metadata for: {self.notebook_path.name}")

        keys = list(self.fields.keys())
        i = 0

        while i < len(keys):
            key = keys[i]
            options = getattr(self, "OPTIONS", {}).get(key)
            validator = getattr(self, "VALIDATORS", {}).get(key)
            back_requested = False

            is_multi_select = key in getattr(self, "MULTI_SELECT_FIELDS", [])

            while True:
                default = self.fields.get(key, "<fill me>")
                if options:
                    print(f"  {key}:")
                    for idx, opt in enumerate(options, 1):
                        print(f"    {idx}. {opt}")
                    current = ", ".join(default) if isinstance(default, list) else default
                    prompt = f"Select {key} (comma-separated numbers) [{current}] (or B to go back): "
                else:
                    current = ", ".join(default) if isinstance(default, list) else default
                    prompt = f"  {key} [{current}] (or B to go back): "

                user_input = input(prompt).strip()

                if user_input.lower() == 'b':
                    back_requested = True
                    break

                if not user_input:
                    value = default
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
                        help_str = getattr(self, "HELP", {}).get(key)
                        if help_str:
                            print(f"\u2139\ufe0f Hint: {help_str}")
                        continue

                self.fields[key] = value
                break

            if back_requested:
                if i > 0:
                    i -= 1
                else:
                    print("\u26A0\ufe0f Already at the first field.")
                continue

            dep_rules = getattr(self, "DEPENDENCIES", {}).get(key)
            if dep_rules:
                selected_value = self.fields[key]
                selected_values = selected_value if isinstance(selected_value, list) else [selected_value]
                inserted = False
                print(f"selected_values: {selected_values}")
                for sv in selected_values:
                    dependent_fields = dep_rules.get(sv, [])

                    for dep in reversed(dependent_fields):
                        if dep not in self.fields:
                            self.fields[dep] = "<fill me>"

                        if dep not in keys:
                            keys.insert(i + 1, dep)
                            inserted = True
                
                if inserted:
                    i += 1
                    continue

            if key == "tactic":
                tactic = self.fields.get("tactic")
                if tactic:
                    techniques, sub_techniques = filter_techniques_for_tactic(
                        tactic, self._all_techniques, self._all_sub_techniques
                    )
                    self.OPTIONS["technique"] = techniques
                    self.OPTIONS["sub_technique"] = sub_techniques
            
            if key == "technique":
                technique = self.fields.get("technique")
                if technique:
                    technique_id = technique.split()[0]  # Get 'T1592' from 'T1592 Gather Victim Host Information'
                    techniques, sub_techniques = filter_techniques_for_tactic(
                        tactic, self._all_techniques, self._all_sub_techniques, technique_id
                    )
                    self.OPTIONS["sub_technique"] = sub_techniques

            i += 1

        return self

    def to_yaml_dict(self):
        return {"dscc": self.fields}
