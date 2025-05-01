from pathlib import Path
import pathlib
import re
import uuid
import yaml
from dscc_packaging.utils import extract_dscc_metadata, is_notebook_file
from dscc_packaging.models import ContentType, Platform, Feature
from dscc_tool.logger import logging
from . import autogen_tests
from .utils import inject_all_defaults

logger = logging.getLogger(__name__)
VALID_PLATFORMS = [p.value for p in Platform]
VALID_FEATURES = [f.value for f in Feature]
VALID_CONTENT_TYPES = [c.value for c in ContentType]


class CleanDumper(yaml.SafeDumper):
    def represent_dict_preserve_order(self, data):
        return self.represent_mapping('tag:yaml.org,2002:map', {
            k: v for k, v in data.items() if v not in [None, "", [], {}]
        })

CleanDumper.add_representer(dict, CleanDumper.represent_dict_preserve_order)

def is_valid_semver(version: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", version))

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except Exception:
        return False
    
def files_exist(file_paths: list) -> bool:
    logger.debug(file_paths)
    if isinstance(file_paths, str):
        file_paths = file_paths.strip().split(",")
    for path in file_paths:

        if not Path(path).exists():
            logger.debug(f"❌ File not found: {path}")
            return False
    return True

def prompt(field, suggestion=None, validator=None):
    while True:
        prompt_text = f"🔧 {field}"
        if suggestion:
            prompt_text += f" [{suggestion}]"
        prompt_text += ": "
        val = input(prompt_text).strip() or suggestion
        if validator and not validator(val):
            
            logger.debug(f"❌ Invalid value for {field}. Please try again.")
            continue
        return val

def select_from_options(field, enum_cls, suggestion=None):
    options = [e.value for e in enum_cls]
    logger.debug(f"🧩 Available options for {field}: (comma separated)")
    for i, val in enumerate(options, 1):
        logger.debug(f"  {i}. {val}")
    raw = input(f"{field} [{suggestion or ''}]: ").strip()
    if not raw and suggestion:
        return suggestion
    try:
        indices = [int(x.strip()) for x in raw.split(",")]
        return [options[i - 1] for i in indices if 1 <= i <= len(options)]
    except Exception:
        logger.debug("❌ Invalid input. Please enter numbers (e.g. 1,2).")
        return select_from_options(field, enum_cls, suggestion)

def clean_placeholders(meta_dict):
    cleaned = {}
    for key, value in meta_dict.items():
        if isinstance(value, str) and value.startswith("<") and value.endswith(">"):
            if key == "version":
                cleaned[key] = prompt(key, suggestion="1.0.0", validator=is_valid_semver)
            elif key == "author":
                cleaned[key] = prompt(key, suggestion="Your Name")
            elif key == "app_friendly_name":
                cleaned[key] = prompt(key, suggestion="My Detection App")
            elif key == "description":
                cleaned[key] = prompt(key, suggestion="This app does XYZ")
            elif key == "installation":
                cleaned[key] = prompt(key, suggestion="Run the provided notebook")
            elif key == "configuration":
                cleaned[key] = prompt(key, suggestion="Set your workspace ID")
            elif key == "release_notes":
                cleaned[key] = prompt(key, suggestion="Initial release")
            elif key == "logo":
                logger.debug("📎 Drop your logo into metadata/, then specify filename:")
                cleaned[key] = prompt(key, suggestion="metadata/logo.png")
            else:
                cleaned[key] = prompt(key, suggestion=value.strip("<>"))
        elif isinstance(value, list):
            if any(isinstance(v, str) and v.startswith("<") and v.endswith(">") for v in value):
                # Prompt once for known enums
                if key == "platform":
                    cleaned[key] = select_from_options(key, Platform)
                elif key == "features":
                    cleaned[key] = select_from_options(key, Feature)
                elif key == "content_type":
                    cleaned[key] = select_from_options(key, ContentType)
                elif key in {"screenshots", "logo"}:
                    # Simple file entry, no options needed
                    logger.debug(f"📎 Enter comma-separated filenames for '{key}' (e.g. metadata/screenshots/0.png):")
                    raw = input(f"{key}: ").strip()
                    cleaned[key] = [v.strip() for v in raw.split(",") if v.strip()]

                else:
                    # Generic list fallback
                    raw = input(f"🔧 Enter comma-separated values for '{key}': ").strip()
                    cleaned[key] = [v.strip() for v in raw.split(",") if v.strip()]
            else:
                cleaned[key] = value


        elif isinstance(value, dict):
            cleaned[key] = clean_placeholders(value)
        else:
            cleaned[key] = value
    return cleaned

def generate_manifest(app_path: str = ".", output_file: str = "manifest.yaml"):
    app_path = Path(app_path)
    base_path = app_path / "base"
    meta_path = app_path / "metadata" / "app_meta.yaml"
    
    if not base_path.exists():
        logger.debug(f"❌ base/ directory not found under {app_path}")
        return

    logger.debug(f"🔍 Scanning {base_path} for notebooks...")

    if not meta_path.exists():
        logger.debug(f"❌ metadata/app_meta.yaml not found.")
        return

    with open(meta_path) as f:
            raw_meta = yaml.safe_load(f)

    cleaned_meta = clean_placeholders(raw_meta)

    # ✅ Write back updated metadata
    with open(meta_path, "w") as f:
        yaml.safe_dump(cleaned_meta, f, sort_keys=False)
    
    logger.debug("💾 Updated metadata/meta.yaml written.")

    manifest = {
        "app": app_path.resolve().name,
        **cleaned_meta,
        "notebooks": [],
    }

    for content_type in [ct.name for ct in ContentType]:
        content_dir = base_path / content_type
        if not content_dir.exists():
            continue

        for path in content_dir.rglob("*.py"):
            if not is_notebook_file(path.name):
                continue
            if path.name.startswith("template_"):
                continue

            try:
                meta = extract_dscc_metadata(path)
                if not meta:
                    logger.debug(f"⚠️  No dscc: metadata in {path.name}, skipping...")
                    continue

                meta["created"] = str(meta.get("created", ""))
                meta["modified"] = str(meta.get("modified", ""))
                meta["version"] = str(meta.get("version", "1.0.0"))

                if not meta.get("uuid") or not is_valid_uuid(meta["uuid"]):
                    generated = str(uuid.uuid4())
                    logger.debug(f"⚙️  Generating UUID for {path.name}: {generated}")
                    meta["uuid"] = generated

                meta.setdefault("content_type", content_type)

                rel_path = path.relative_to(app_path)
                logger.debug(f"✅ adding notebook: {path.name} to manifest")
                manifest["notebooks"].append({
                    "path": str(rel_path),
                    "dscc": meta
                })
            except Exception as e:
                logger.debug(f"❌ Error parsing {path}: {e}")

    if not manifest["notebooks"]:
        logger.debug("⚠️ No notebooks with metadata found.")
        return

    out_path = app_path / output_file
    with open(out_path, "w") as f:
        yaml.dump(manifest, f, sort_keys=False, Dumper=CleanDumper)

    logger.debug(f"✅ Manifest written to: {out_path}")

def prepare_notebooks(app_path=".", overwrite=False, dry_run=False, noninteractive=False, no_sample=False, inject_defaults=False):
    app_path = pathlib.Path(app_path)
    base_path = app_path / "base"

    print("\n🧪 DSCC Packaging App")
    print("This tool analyzes your notebooks and generates dscc YAML, dscc-tests and optional sample data.\n")

    print(f"🔍 Scanning {base_path} for notebooks...\n")

    for notebook in base_path.rglob("*"):
        if not is_notebook_file(notebook.name):
            continue
        if notebook.name.startswith("template_"):
            continue

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"📓 Notebook: {notebook.relative_to(app_path)}")

        if inject_defaults:
            print(f"🔧 Injecting default YAML...{notebook}")
            inject_all_defaults(notebook)
            continue

        try:
            test_cases = autogen_tests.infer_dscc_tests(
                notebook_path=notebook,
                dry_run=dry_run,
                overwrite=overwrite,
                noninteractive=noninteractive,
                no_sample=no_sample
            )
        except Exception as e:
            print(f"❌ Failed to process {notebook.name}: {e}")
            continue

        if not test_cases:
            print("⚠️  No test cases were generated.\n")
        else:
            print(f"✅ Done — {len(test_cases)} test case(s) inferred.\n")

    print(f"🏁 Finished {'yaml' if inject_defaults else 'test'} generation.\n")

def inject_default_yaml(app_path="."):
    prepare_notebooks(app_path=app_path, inject_defaults=True)