import yaml
import re
from dscc.logger import logging

logger = logging.getLogger(__name__)
def extract_dscc_metadata(file_path: str) -> dict:
    """
    Extracts the dscc: metadata block from the first markdown cell in a Databricks notebook (.py format).
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    in_yaml_block = False
    yaml_lines = []

    for line in lines:
        if "# MAGIC ```yaml" in line:
            in_yaml_block = True
            continue
        if in_yaml_block and "# MAGIC ```" in line:
            break
        if in_yaml_block:
            content = line.strip()
            if content.startswith("# MAGIC "):
                content = content[len("# MAGIC "):]
            yaml_lines.append(content)

    if not yaml_lines:
        return None

    try:
        full_yaml = "\n".join(yaml_lines)
        data = yaml.safe_load(full_yaml)
        return data.get("dscc")
    except Exception as e:
        logger.debug(f"⚠️ Failed to parse dscc metadata in {file_path}: {e}")
        return None


def is_notebook_file(filename: str) -> bool:
    return filename.endswith(".py") or filename.endswith(".dbc")
