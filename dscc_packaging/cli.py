from dscc_tool.logger import logging
logger = logging.getLogger(__name__)

from . import generator, validate

import sys

commands = {
    "generate_manifest": generator.generate_manifest,
    "validate_manifest": validate.validate_manifest,
    "prepare_notebooks": generator.prepare_notebooks,
    "inject_default_yaml": generator.inject_default_yaml,
    "export": generator.export_for_packaging,
}

# Define allowed options for each command
allowed_options = {
    'generate_manifest': {'--app_path', '--help'},
    'validate_manifest': {'--manifest_path', '--help'},
    'prepare_notebooks': {'--app_path', '--overwrite', '--dry_run', '--noninteractive', '--no_sample', '--help'},
    'inject_default_yaml': {'--app_path', '--help'},
    'export': {'--workspace_path', '--local_path', '--auto-fix-structure', '--noninteractive', '--help'},
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
    generator.inject_default_yaml(app_path=app_path)

def export(
    workspace_path=None,
    local_path=None,
    auto_fix_structure=False,
    noninteractive=False
):
    generator.export_for_packaging(
        workspace_path=workspace_path,
        local_path=local_path,
        auto_fix=auto_fix_structure,
        noninteractive=noninteractive
    )

def main():
    import argparse

    parser = argparse.ArgumentParser(description="DSCC Packaging CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate_manifest
    gen_manifest_parser = subparsers.add_parser("generate_manifest", help="Generate manifest.yaml from app metadata and notebooks")
    gen_manifest_parser.add_argument("--app_path", default=".", help="Path to app root directory")

    # validate_manifest
    val_manifest_parser = subparsers.add_parser("validate_manifest", help="Validate manifest.yaml against schema")
    val_manifest_parser.add_argument("--manifest_path", default="manifest.yaml", help="Path to manifest.yaml")

    # prepare_notebooks
    prep_parser = subparsers.add_parser("prepare_notebooks", help="Prepare notebooks with dscc YAML and tests")
    prep_parser.add_argument("--app_path", default=".", help="Path to app root directory")
    prep_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing metadata")
    prep_parser.add_argument("--dry_run", action="store_true", help="Print changes without writing")
    prep_parser.add_argument("--noninteractive", action="store_true", help="Skip prompts and use defaults")
    prep_parser.add_argument("--no_sample", action="store_true", help="Don't fetch sample data")

    # inject_default_yaml
    inject_parser = subparsers.add_parser("inject_default_yaml", help="Inject default YAML into all notebooks")
    inject_parser.add_argument("--app_path", default=".", help="Path to app root directory")

    # export
    export_parser = subparsers.add_parser("export", help="Export a Databricks workspace directory for local packaging")
    export_parser.add_argument("--workspace_path", required=True, help="Workspace path to export (e.g. /Workspace/Users/me/my_app)")
    export_parser.add_argument("--local_path", required=False, help="Local path to export to")
    export_parser.add_argument("--auto-fix-structure", action="store_true", dest="auto_fix_structure", help="Auto-fix structure issues using template_app")
    export_parser.add_argument("--noninteractive", action="store_true", help="Skip prompts and use defaults")

    args = parser.parse_args()

    if args.command == "generate_manifest":
        generate_manifest(app_path=args.app_path)
    elif args.command == "validate_manifest":
        validate_manifest(manifest_path=args.manifest_path)
    elif args.command == "prepare_notebooks":
        prepare_notebooks(
            app_path=args.app_path,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            noninteractive=args.noninteractive,
            no_sample=args.no_sample
        )
    elif args.command == "inject_default_yaml":
        inject_default_yaml(app_path=args.app_path)
    elif args.command == "export":
        export(
            workspace_path=args.workspace_path,
            local_path=args.local_path,
            auto_fix_structure=args.auto_fix_structure,
            noninteractive=args.noninteractive
        )
    else:
        parser.print_help()
        sys.exit(1)

# CLI Entry
if __name__ == "__main__":
    main()

