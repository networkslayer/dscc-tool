from dscc.logger import logging
logger = logging.getLogger(__name__)

from . import generator, validate


commands = {
    "generate_manifest": generator.generate_manifest,
    "validate_manifest": validate.validate_manifest,
    "generate_tests": generator.generate_tests,
}

def generate_manifest(app_path="."):
    generator.generate_manifest(app_path=app_path)

def validate_manifest(manifest_path="manifest.yaml"):
    validate.validate_manifest(manifest_path=manifest_path)

def generate_tests(app_path=".", overwrite=False, dry_run=False, noninteractive=False, no_sample=False):
    generator.generate_tests(
        app_path=app_path,
        overwrite=overwrite,
        dry_run=dry_run,
        noninteractive=noninteractive,
        no_sample=no_sample
    )


def main():
    import fire
    fire.Fire({
        "generate_manifest": generate_manifest,
        "validate_manifest": validate_manifest,
        "generate_tests": generate_tests,
    })

# CLI Entry
if __name__ == "__main__":
    main()

