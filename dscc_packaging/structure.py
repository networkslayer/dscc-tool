from pathlib import Path
import shutil
import yaml
from dscc_packaging.models import AppMetadata
from pydantic import ValidationError

def build_template_from_model(model_cls):
    """
    Recursively build a template dict from a Pydantic model class.
    Ensures all values are basic Python types for YAML serialization.
    """
    import typing
    template = {}
    for name, field in model_cls.model_fields.items():
        # Nested model
        if hasattr(field.annotation, 'model_fields'):
            template[name] = build_template_from_model(field.annotation)
        # List
        elif getattr(field.annotation, '__origin__', None) is list:
            elem_type = getattr(field.annotation, '__args__', [str])[0]
            if hasattr(elem_type, '__args__') and getattr(elem_type, '_name', None) == 'Literal':
                # List[Literal[...]]
                template[name] = [elem_type.__args__[0]]
            else:
                template[name] = []
        # Dict
        elif getattr(field.annotation, '__origin__', None) is dict:
            template[name] = {}
        # default_factory
        elif getattr(field, 'default_factory', None) is not None:
            try:
                val = field.default_factory()
                # Only use if it's a basic type
                if isinstance(val, (str, int, float, list, dict, type(None))):
                    template[name] = val
                else:
                    template[name] = f"<{name}>"
            except Exception:
                template[name] = f"<{name}>"
        # default
        elif field.default is not None:
            if isinstance(field.default, (str, int, float, list, dict, type(None))):
                template[name] = field.default
            else:
                template[name] = f"<{name}>"
        # Literal
        elif hasattr(field.annotation, '__args__') and getattr(field.annotation, '_name', None) == 'Literal':
            template[name] = field.annotation.__args__[0]
        # Fallback
        else:
            template[name] = f"<{name}>"
    return template

def load_template_structure(template_dir: Path):
    structure = {}
    for path in template_dir.rglob("*"):
        rel = path.relative_to(template_dir)
        if path.is_dir():
            structure[str(rel)] = 'dir'
        else:
            structure[str(rel)] = 'file'
    return structure

def validate_structure(app_dir: Path, template_structure: dict):
    """
    Compare app_dir to template_structure.
    Any directory present in template_app is an allowed container (arbitrary content allowed).
    Returns (missing, extra) as lists of relative paths.
    """
    # All directories in the template are allowed containers
    allowed_dirs = set(k for k, v in template_structure.items() if v == 'dir')

    app_paths = set()
    for p in app_dir.rglob("*"):
        rel = str(p.relative_to(app_dir))
        # If in an allowed dir (or is the allowed dir itself), skip
        if any(rel == ad or rel.startswith(ad + "/") for ad in allowed_dirs):
            continue
        app_paths.add(rel)

    # Only require the structure and key files, not the contents of allowed dirs
    missing = [k for k, v in template_structure.items()
               if k not in app_paths and not any(k == ad or k.startswith(ad + "/") for ad in allowed_dirs)]
    extra = [k for k in app_paths
             if k not in template_structure and not any(k == ad or k.startswith(ad + "/") for ad in allowed_dirs)]
    return missing, extra

def auto_fix_structure(app_dir: Path, template_dir: Path, missing: list):
    for rel_path in missing:
        src = template_dir / rel_path
        dst = app_dir / rel_path
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            print(f"🛠️  Created missing directory: {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"🛠️  Created missing file: {dst}")

def find_misplaced_notebooks(app_dir: Path, valid_dirs: list):
    misplaced = []
    for nb in app_dir.rglob("*.py"):
        if not any(str(nb.parent).endswith(vd) for vd in valid_dirs):
            misplaced.append(nb)
    return misplaced

def prompt_user_for_placement(notebook_path: Path, valid_dirs: list):
    print(f"❓ Notebook {notebook_path} is not in a recognized folder.")
    print("Valid folders are:")
    for i, d in enumerate(valid_dirs):
        print(f"  {i+1}. {d}")
    idx = int(input("Choose a folder to move it to: ")) - 1
    target_dir = notebook_path.parent.parent / valid_dirs[idx]
    target_dir.mkdir(parents=True, exist_ok=True)
    new_path = target_dir / notebook_path.name
    shutil.move(str(notebook_path), str(new_path))
    print(f"✅ Moved {notebook_path} to {new_path}")

def prompt_with_options(field_name, field_info):
    """
    Prompt the user for a value, showing allowed options for enums, Literals, or lists thereof.
    """
    # Handle Literal
    if hasattr(field_info.annotation, '__args__') and getattr(field_info.annotation, '_name', None) == 'Literal':
        options = field_info.annotation.__args__
        print(f"Options for {field_name}: {', '.join(map(str, options))}")
        val = input(f"Enter value for {field_name} [{options[0]}]: ").strip() or str(options[0])
        return val
    # Handle Enum
    elif hasattr(field_info.annotation, '__members__'):
        options = list(field_info.annotation.__members__.keys())
        print(f"Options for {field_name}: {', '.join(options)}")
        val = input(f"Enter value for {field_name} [{options[0]}]: ").strip() or options[0]
        return val
    # Handle List[Literal] or List[Enum]
    elif getattr(field_info.annotation, '__origin__', None) is list:
        elem_type = getattr(field_info.annotation, '__args__', [str])[0]
        if hasattr(elem_type, '__args__') and getattr(elem_type, '_name', None) == 'Literal':
            options = elem_type.__args__
            print(f"Options for {field_name} (comma separated): {', '.join(map(str, options))}")
            raw = input(f"Enter value(s) for {field_name} [{options[0]}]: ").strip() or str(options[0])
            return [v.strip() for v in raw.split(',')]
        elif hasattr(elem_type, '__members__'):
            options = list(elem_type.__members__.keys())
            print(f"Options for {field_name} (comma separated): {', '.join(options)}")
            raw = input(f"Enter value(s) for {field_name} [{options[0]}]: ").strip() or options[0]
            return [v.strip() for v in raw.split(',')]
    # Fallback
    return input(f"Enter value for {field_name}: ").strip()

def validate_and_fill_metadata(meta_path: Path, metadata_model, noninteractive=False, app_name=None):
    if not meta_path.exists():
        print(f"⚠️  {meta_path} not found. Creating from template.")
        # Build template from AppMetadata model
        template = build_template_from_model(metadata_model)
        meta_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        with open(meta_path, "w") as f:
            yaml.dump(template, f)
        print(f"✅ Created template metadata at {meta_path}")
        return False

    with open(meta_path) as f:
        meta = yaml.safe_load(f)
    if not isinstance(meta, dict):
        print(f"⚠️  {meta_path} is empty or invalid. Re-creating from template.")
        template = build_template_from_model(metadata_model)
        meta_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        with open(meta_path, "w") as f:
            yaml.dump(template, f)
        meta = template

    try:
        metadata_model(**meta)
        print("✅ Metadata is valid.")
        return True
    except ValidationError as e:
        print("⚠️  Metadata validation failed:")
        print(e)
        # Use clean_placeholders to handle the metadata
        from dscc_packaging.generator import clean_placeholders
        meta = clean_placeholders(meta, app_name=app_name)
        with open(meta_path, "w") as f:
            yaml.dump(meta, f)
        print("✅ Metadata updated.")
        return False

def get_system_files_to_ignore() -> list[str]:
    """Returns a list of system files that should be ignored during packaging."""
    return [
        ".DS_Store",  # macOS Finder metadata
        "Thumbs.db",  # Windows thumbnail cache
        ".git",       # Git directory
        "__pycache__", # Python bytecode cache
        "*.pyc",      # Python compiled files
        "*.pyo",      # Python optimized files
        "*.pyd",      # Python DLL files
        ".ipynb_checkpoints", # Jupyter checkpoints
    ]

def should_ignore_file(file_path: Path) -> bool:
    """Check if a file should be ignored during packaging."""
    ignore_patterns = get_system_files_to_ignore()
    return any(
        file_path.name == pattern or 
        file_path.name.endswith(pattern.lstrip("*")) or
        file_path.name.startswith(pattern.rstrip("*"))
        for pattern in ignore_patterns
    )

def validate_and_fix_app_structure(
    app_dir: Path,
    template_dir: Path,
    metadata_model,
    auto_fix=False,
    noninteractive=False,
    app_name=None
):
    # First, clean up system files
    for file_path in app_dir.rglob("*"):
        if file_path.is_file() and should_ignore_file(file_path):
            try:
                file_path.unlink()
                print(f"🧹 Removed system file: {file_path}")
            except Exception as e:
                print(f"⚠️  Could not remove {file_path}: {e}")

    template_structure = load_template_structure(template_dir)
    missing, extra = validate_structure(app_dir, template_structure)
    if not missing and not extra:
        print("✅ App structure matches template.")
    else:
        print("⚠️  Structure issues detected:")
        if missing:
            print("Missing:", missing)
        if extra:
            print("Extra:", extra)
        if auto_fix or (not noninteractive and input("Auto-fix structure? [y/N]: ").lower() == 'y'):
            auto_fix_structure(app_dir, template_dir, missing)
        else:
            print("❌ Please fix the structure manually and re-run.")
            return False

    valid_dirs = [d for d in template_structure if template_structure[d] == 'dir']
    misplaced = find_misplaced_notebooks(app_dir, valid_dirs)
    for nb in misplaced:
        if noninteractive:
            print(f"⚠️  Misplaced notebook: {nb} (please move manually)")
        else:
            prompt_user_for_placement(nb, valid_dirs)

    meta_path = app_dir / "metadata" / "meta.yaml"
    validate_and_fill_metadata(meta_path, metadata_model, noninteractive=noninteractive, app_name=app_name)

    return True 