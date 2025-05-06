from dscc_tool.logger import logging
logger = logging.getLogger(__name__)

from . import generator, validate


commands = {
    "generate_manifest": generator.generate_manifest,
    "validate_manifest": validate.validate_manifest,
    "prepare_notebooks": generator.prepare_notebooks,
    "inject_default_yaml": generator.inject_default_yaml,
}

def generate_manifest(app_path="."):
    generator.generate_manifest(app_path=app_path)

def validate_manifest(manifest_path="manifest.yaml"):
    validate.validate_manifest(manifest_path=manifest_path)

def prepare_notebooks(app_path=".", overwrite=False, dry_run=False, noninteractive=False, no_sample=False):
    generator.prepare_notebooks(
        app_path=app_path,
        overwrite=overwrite,
        dry_run=dry_run,
        noninteractive=noninteractive,
        no_sample=no_sample
    )

def inject_default_yaml(app_path="."):
    print("CALLED")
    generator.inject_default_yaml(app_path=app_path)

def export_for_packaging(workspace_path, local_path=None):
    """
    Export a Databricks workspace directory for local packaging.
    Example:
        python3 -m dscc_tool.cli packaging export_for_packaging --workspace_path /Workspace/Users/me/my_app --local_path ./my_app_export
    Args:
        workspace_path (str): Path to the workspace directory (e.g., '/Workspace/Users/me/my_app')
        local_path (str, optional): Local path to export to. If None, creates a temp directory.
    """
    from .generator import export_for_packaging as export_func
    return export_func(workspace_path, local_path)

def main():
    import fire
    fire.Fire({
        "generate_manifest": generate_manifest,
        "validate_manifest": validate_manifest,
        "prepare_notebooks": prepare_notebooks,
        "inject_default_yaml": inject_default_yaml,
        "export_for_packaging": export_for_packaging,
    })

# CLI Entry
if __name__ == "__main__":
    main()

