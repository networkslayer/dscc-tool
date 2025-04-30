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


def main():
    import fire
    fire.Fire({
        "generate_manifest": generate_manifest,
        "validate_manifest": validate_manifest,
        "prepare_notebooks": prepare_notebooks,
        "inject_default_yaml": inject_default_yaml,
    })

# CLI Entry
if __name__ == "__main__":
    main()

