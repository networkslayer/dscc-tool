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
import subprocess
import sys
import tempfile
import os
import getpass
# --- Structure validation imports ---
from dscc_packaging.structure import validate_and_fix_app_structure
from dscc_packaging.models import AppMetadata

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

def infer_user_name():
    # Try environment variables
    for var in ["GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "USER", "USERNAME"]:
        name = os.environ.get(var)
        if name:
            return name
    # Try getpass
    try:
        name = getpass.getuser()
        if name:
            return name
    except Exception:
        pass
    # Try git config
    try:
        result = subprocess.run(["git", "config", "--get", "user.name"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return "Your Name"

def infer_user_email():
    # Try environment variables
    for var in ["GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL", "EMAIL", "USEREMAIL"]:
        email = os.environ.get(var)
        if email:
            return email
    # Try git config
    try:
        result = subprocess.run(["git", "config", "--get", "user.email"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        email = result.stdout.strip()
        if email:
            return email
    except Exception:
        pass
    return "user@example.com"

def clean_placeholders(meta_dict, app_name=None):
    # Define the order of fields to process
    field_order = [
        "app_friendly_name",
        "app_name",
        "author",
        "version",
        "release_notes",
        "description",
        "content_type",
        "requirements",
        "installation",
        "configuration",
        "logo",
        "screenshots"
    ]
    
    # Create a new dict with fields in desired order
    ordered_dict = {}
    for key in field_order:
        if key in meta_dict:
            ordered_dict[key] = meta_dict[key]
    
    # Add any remaining fields
    for key, value in meta_dict.items():
        if key not in ordered_dict:
            ordered_dict[key] = value
    
    cleaned = {}
    for key, value in ordered_dict.items():
        # Skip system fields that should not be prompted for
        if key in {"release_date", "submitted_at"}:
            cleaned[key] = value if value is not None else None
            continue
        if isinstance(value, str) and value.startswith("<") and value.endswith(">"):
            if key == "version":
                cleaned[key] = prompt(key, suggestion="1.0.0", validator=is_valid_semver)
            elif key == "author":
                cleaned[key] = prompt(key, suggestion=infer_user_name())
            elif key == "user_email":
                cleaned[key] = prompt(key, suggestion=infer_user_email())
            elif key == "app_friendly_name":
                # Convert underscores to spaces for friendly name
                default = app_name.replace("_", " ") if app_name else "My Detection App"
                cleaned[key] = prompt(key, suggestion=default)
            elif key == "app_name":
                # Keep original directory name for app_name
                default = app_name if app_name else "app_name"
                cleaned[key] = prompt(key, suggestion=default)
            elif key == "description":
                cleaned[key] = prompt(key, suggestion="This app does XYZ")
            elif key == "installation":
                cleaned[key] = prompt(key, suggestion="Run the provided notebook")
            elif key == "configuration":
                cleaned[key] = prompt(key, suggestion="Describe how to configure this app (e.g., required permissions, settings, or environment variables)")
            elif key == "release_notes":
                cleaned[key] = prompt(key, suggestion="Initial release")
            elif key == "logo":
                print("\n📎 Please add your app logo to the metadata/ directory before continuing.")
                print("   - Preferred file types: .png, .jpg, .jpeg")
                print("   - Recommended: square image, at least 256x256 pixels (e.g., 256x256.png)")
                print("   - Example: metadata/logo.png\n")
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
    print("CALLED")
    app_path = Path(app_path)
    base_path = app_path / "base"
    meta_path = app_path / "metadata" / "meta.yaml"
    
    if not base_path.exists():
        logger.debug(f"❌ base/ directory not found under {app_path}")
        return

    logger.debug(f"🔍 Scanning {base_path} for notebooks...")

    if not meta_path.exists():
        logger.debug(f"❌ metadata/meta.yaml not found.")
        return

    with open(meta_path) as f:
            raw_meta = yaml.safe_load(f)

    # Get app name from directory
    app_name = app_path.resolve().name
    cleaned_meta = clean_placeholders(raw_meta, app_name=app_name)

    # ✅ Write back updated metadata
    with open(meta_path, "w") as f:
        yaml.safe_dump(cleaned_meta, f, sort_keys=False)
    
    logger.debug("💾 Updated metadata/meta.yaml written.")

    manifest = {
        "app": app_name,
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

def check_databricks_cli():
    """Check if Databricks CLI is installed and configured."""
    try:
        subprocess.run(["databricks", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        result = subprocess.run(["databricks", "configure", "--list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if "No profiles configured" in result.stdout.decode():
            return False, "Databricks CLI is installed but not configured. Please run 'databricks configure' first."
        return True, None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, "Databricks CLI is not installed. Please install it first: pip install databricks-cli"

def export_for_packaging(workspace_path: str, local_path: str = None, auto_fix=True, noninteractive=False):
    """
    Export a Databricks workspace directory for local packaging.
    Args:
        workspace_path (str): Path to the workspace directory (e.g., '/Workspace/Users/me/my_app')
        local_path (str, optional): Local path to export to. If None, creates a temp directory.
        auto_fix (bool): Whether to auto-fix structure issues.
        noninteractive (bool): Whether to skip prompts.
    Returns:
        str: Path to the exported directory
    """
    cli_installed, error_msg = check_databricks_cli()
    if not cli_installed:
        print(f"❌ {error_msg}")
        print("\n✨ To fix this:")
        print("1. Install the Databricks CLI:")
        print("   pip install databricks-cli")
        print("2. Configure the CLI:")
        print("   databricks configure")
        print("3. Make sure you have access to the workspace")
        print("4. Try again")
        sys.exit(1)

    app_name = os.path.basename(workspace_path.rstrip("/"))

    if local_path is None:
        import tempfile
        base_dir = tempfile.mkdtemp(prefix="dscc_export_")
        export_dir = os.path.join(base_dir, app_name)
    else:
        # If local_path already ends with app_name, don't duplicate
        if os.path.basename(os.path.normpath(local_path)) == app_name:
            export_dir = local_path
        else:
            export_dir = os.path.join(local_path, app_name)

    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    export_cmd = [
        "databricks",
        "workspace",
        "export_dir",
        workspace_path,
        str(export_dir),
        "--overwrite"
    ]

    print(f"\n📦 Exporting workspace directory to: {export_dir}")
    try:
        result = subprocess.run(
            export_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("✅ Export successful!")
        # --- Structure validation and auto-fix ---
        template_dir = Path(__file__).parent / "template_app"
        validate_and_fix_app_structure(
            export_dir,
            template_dir,
            AppMetadata,
            auto_fix=auto_fix,
            noninteractive=noninteractive,
            app_name=app_name
        )
        # ... rest of export logic (write scripts, README, etc.) ...
        script_path = Path.cwd() / "package_locally.sh"
        with open(script_path, "w") as f:
            f.write(f"""#!/bin/bash
# Helper script to package your DSCC app locally
# Usage: ./package_locally.sh [dscc-tool options]
# Example: ./package_locally.sh --noninteractive --no-sample

# Function to clean system files
clean_system_files() {{
    local dir="$1"
    echo "🧹 Cleaning system files..."
    
    # macOS files
    find "$dir" -name ".DS_Store" -type f -delete
    find "$dir" -name "._*" -type f -delete
    
    # Windows files
    find "$dir" -name "Thumbs.db" -type f -delete
    
    # Python files
    find "$dir" -name "__pycache__" -type d -exec rm -rf {{}} +
    find "$dir" -name "*.pyc" -type f -delete
    find "$dir" -name "*.pyo" -type f -delete
    find "$dir" -name "*.pyd" -type f -delete
    
    # Jupyter files
    find "$dir" -name ".ipynb_checkpoints" -type d -exec rm -rf {{}} +
    
    echo "✅ System files cleaned"
}}

echo "🚀 Starting local packaging process..."
cd "{export_dir}"

# Clean system files before starting
clean_system_files "."

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
if [[ "$python_version" < "3.11" ]]; then
    echo "⚠️ Warning: Python 3.11+ is recommended. Current version: $python_version"
fi

# Install dscc-tool if not already installed
echo -n "🔍 Checking prerequisites... "
if pip install dscc-tool > /dev/null 2>&1 || pip install -e . > /dev/null 2>&1; then
    echo "done."
else
    echo "failed! Please check your Python environment."
    exit 1
fi

# Run the packaging process, passing all user arguments
if dscc packaging prepare_notebooks --app_path "{export_dir}" "$@"; then
    echo "✅ Notebook preparation complete"
    
    # Generate manifest
    echo "📝 Generating manifest.yaml..."
    if dscc packaging generate_manifest --app_path "{export_dir}"; then
        echo "✅ Manifest generated"
        
        # Validate manifest
        echo "🔍 Validating manifest..."
        if dscc packaging validate_manifest --manifest_path "{export_dir}/manifest.yaml"; then
            echo "✨ Packaging complete! Your app is ready in: {export_dir}"
            echo "📦 To create the final package, run: dscc packaging package --app_path {export_dir}"
        else
            echo "❌ Manifest validation failed. Please fix the errors above and try again."
            exit 1
        fi
    else
        echo "❌ Manifest generation failed. Please fix the errors above and try again."
        exit 1
    fi
else
    echo "❌ Notebook preparation failed. Please fix the errors above and try again."
    exit 1
fi
""")
        script_path.chmod(0o755)
        readme_path = export_dir / "README.md"
        with open(readme_path, "w") as f:
            f.write(f"""# DSCC App Packaging Instructions

## 🚀 Quick Start

1. Run the packaging script from your current directory (you can pass any dscc-tool options):
   ```bash
   ./package_locally.sh --noninteractive --no-sample
   ```

2. The script will automatically change into the app directory:
   ```bash
   cd {export_dir}
   ```

3. Follow the interactive prompts to complete packaging (unless you use --noninteractive)

4. Create the final package:
   ```bash
   dscc packaging package --app_path .
   ```

## 📦 What's Included

- Your exported notebooks and files
- A helper script for packaging (in your current directory)
- This README with instructions (in the app directory)

## 🔧 Requirements

- Python 3.11+ (recommended)
- pip (Python package manager)
- dscc-tool package

## ❓ Need Help?

If you encounter any issues:
1. Check the error messages
2. Make sure you have the required dependencies
3. Try running the commands manually
4. Check the [DSCC documentation](https://dscc.databricks.com/docs)

Happy packaging! 🎉
""")
        print(f"\n✨ Next steps:")
        print(f"1. Run: ./package_locally.sh (from your current directory)")
        print(f"2. The script will cd into: {export_dir}")
        print(f"3. Follow the interactive prompts to complete packaging")
        print(f"4. After packaging, run: dscc packaging package --app_path . (inside the app directory)")
        return str(export_dir)
    except subprocess.CalledProcessError as e:
        print("❌ Export failed!")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        print("\n✨ Troubleshooting tips:")
        print("1. Check if the workspace path is correct")
        print("2. Verify your Databricks CLI configuration")
        print("3. Ensure you have access to the workspace")
        print("4. Try running the export command manually:")
        print(f"   databricks workspace export_dir {workspace_path} {export_dir} --overwrite")
        raise