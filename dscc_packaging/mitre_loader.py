import os
from pathlib import Path
import re
import json
import requests
from typing import Dict, Any, List

MITRE_ENTERPRISE_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
# Use a user cache directory for the MITRE cache file
CACHE_DIR = Path(os.path.expanduser("~/.cache/dscc-tool"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "mitre_enterprise_attack.json"

def load_mitre_attack():
    try:
        if CACHE_FILE.exists():
            with CACHE_FILE.open() as f:
                data = json.load(f)
        else:
            print("\U0001F310 Downloading MITRE ATT&CK data...")
            response = requests.get(MITRE_ENTERPRISE_URL)
            response.raise_for_status()
            data = response.json()
            with CACHE_FILE.open("w") as f:
                json.dump(data, f)

        tactics = set()
        techniques = []
        sub_techniques = []
        uuid_to_external_id = {}
        subtechnique_to_parent = {}

        # First pass: map UUIDs to external IDs and build subtechnique relationships
        for obj in data["objects"]:
            if obj["type"] == "attack-pattern":
                ext_ref = next((ref for ref in obj.get("external_references", []) if ref.get("source_name") == "mitre-attack"), {})
                ext_id = ext_ref.get("external_id")
                if ext_id:
                    uuid_to_external_id[obj["id"]] = ext_id

            elif obj["type"] == "relationship" and obj.get("relationship_type") == "subtechnique-of":
                subtechnique_to_parent[obj["source_ref"]] = obj["target_ref"]

        # Second pass: build tactics, techniques, and sub-techniques
        for obj in data["objects"]:
            if obj["type"] == "x-mitre-tactic":
                tactics.add(obj["x_mitre_shortname"])

            if obj["type"] == "attack-pattern":
                ext_ref = next((ref for ref in obj.get("external_references", []) if ref.get("source_name") == "mitre-attack"), {})
                ext_id = ext_ref.get("external_id")
                name = obj.get("name")
                kill_chain = obj.get("kill_chain_phases", [])
                tactic_names = [phase.get("phase_name") for phase in kill_chain]

                if not ext_id:
                    continue

                entry = {
                    "id": ext_id,
                    "name": name,
                    "tactics": tactic_names
                }

                if obj.get("x_mitre_is_subtechnique"):
                    parent_uuid = subtechnique_to_parent.get(obj["id"])
                    entry["parent_id"] = uuid_to_external_id.get(parent_uuid)
                    sub_techniques.append(entry)
                else:
                    techniques.append(entry)

        return sorted(tactics), techniques, sub_techniques
    except Exception as e:
        # Detect Databricks
        in_databricks = any(
            os.environ.get(var) for var in ["DATABRICKS_RUNTIME_VERSION", "DATABRICKS_HOST"]
        )
        if in_databricks:
            print("⚠️ Could not load MITRE data in Databricks workspace. MITRE-dependent features will be skipped.")
            return [], [], []
        else:
            print("❌ Could not load MITRE data. Please download the MITRE file manually and place it in the expected location.")
            print("   See: https://github.com/mitre/cti for details.")
            raise


def filter_techniques_for_tactic(
    tactic: str,
    all_techniques: List[dict],
    all_sub_techniques: List[dict],
    selected_technique_id: str = None
):
    filtered_techniques = [
        f"{t['id']} {t['name']}"
        for t in all_techniques
        if tactic in t.get("tactics", [])
    ]

    filtered_sub_techniques = [
        f"{s['id']} {s['name']}"
        for s in all_sub_techniques
        if tactic in s.get("tactics", [])
        and (selected_technique_id is None or s.get("parent_id") == selected_technique_id)
    ]

    return filtered_techniques, filtered_sub_techniques

