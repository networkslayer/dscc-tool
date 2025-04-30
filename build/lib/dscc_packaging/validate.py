from pathlib import Path
import yaml
from pydantic import ValidationError
from dscc_packaging.models import DSCCManifest
from dscc.logger import logging

logger = logging.getLogger(__name__)
def validate_manifest(manifest_path: str):
    """
    Validates a manifest.yaml manifest against the DSCCManifest Pydantic schema.
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        logger.debug(f"❌ Manifest file not found: {manifest_path}")
        return

    try:
        with open(manifest_file, "r") as f:
            data = yaml.safe_load(f)

        validated = DSCCManifest(**data)
        logger.debug("✅ Manifest is valid.")
        return validated

    except ValidationError as ve:
        logger.debug("❌ Validation failed:")
        logger.debug(ve)
    except Exception as e:
        logger.debug(f"❌ Error reading or parsing manifest: {e}")
