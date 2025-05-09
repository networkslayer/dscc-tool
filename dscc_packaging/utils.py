import yaml
from dscc_tool.logger import logging
from pathlib import Path
from .preset_engine import PresetEngine
from .shared_utils import read_notebook_source_lines, extract_dscc_metadata, clean_for_yaml
from .notebook_io import write_metadata_block

logger = logging.getLogger(__name__)



"""
def write_metadata_block_ipynb(notebook_path: Path, dscc_meta: dict, test_cases: list):
    full_metadata = dict(dscc_meta or {})
    full_metadata["dscc-tests"] = {"tests": test_cases}

    md_lines = ["```yaml"]
    md_lines.extend(yaml.dump(full_metadata, sort_keys=False).splitlines())
    md_lines.append("```")

    md_cell = new_markdown_cell(source="\n".join(md_lines))

    nb = nbformat.read(notebook_path, as_version=4)

    insert_idx = 0
    for i, cell in enumerate(nb.cells):
        if is_magic_cell(cell):
            insert_idx = i + 1
        else:
            break

    # Prevent duplicate injection
    if any("dscc:" in (cell.source or "") for cell in nb.cells if cell.cell_type == "markdown"):
        print(f"⏭️ Skipping {notebook_path.name} (already has dscc block)")
        return

    nb.cells.insert(insert_idx, md_cell)

    nbformat.write(nb, notebook_path)
    print(f"✅ Injected YAML metadata block into {notebook_path.name}")
"""

def generate_dscc_metadata(notebook_path, overwrite=False, source_lines=None):
    has_block = any("# MAGIC dscc:" in line for line in source_lines) if source_lines else False
    if overwrite or not has_block:
        try:
            preset = PresetEngine.from_path(notebook_path).prompt_user()
            return preset.to_yaml_dict()
        except ValueError as e:
            print(str(e))
    return {}
"""
def write_metadata_block(notebook_path, dscc_meta, test_cases, source_lines, overwrite=False):
    import yaml

    markdown_block = [
        "# MAGIC %md\n",
        "# MAGIC ```yaml\n",
    ]

    # 🧹 Merge dscc and dscc-tests first
    full_metadata = dict(dscc_meta) if dscc_meta else {}
    full_metadata["dscc-tests"] = {"tests": test_cases}

    print(f"dscc_meta: {dscc_meta}")
    print(f"test_cases: {test_cases}")
    print(f"full_metadata: {full_metadata}")

    for line in yaml.dump(full_metadata, sort_keys=False).splitlines():
        markdown_block.append(f"# MAGIC {line}\n")

    markdown_block.append("# MAGIC ```\n")

    has_block = any("# MAGIC dscc:" in line for line in source_lines)

    if not has_block:
        insert_idx = next((i for i, line in enumerate(source_lines) if line.startswith("# COMMAND")), 0) + 1
        new_source = source_lines[:insert_idx] + markdown_block + source_lines[insert_idx:]
    else:
        dscc_idx = next(i for i, line in enumerate(source_lines) if "# MAGIC dscc:" in line)

        # 🧹 Now, move up until we find the first enclosing %md
        start = dscc_idx
        while start > 0 and not source_lines[start].strip().startswith("# MAGIC %md"):
            start -= 1

        # 🧹 Now, move down to find the closing ```
        end = start
        while end < len(source_lines) and not source_lines[end].strip() == "# MAGIC ```":
            end += 1

        print(f"start: {start}, end: {end}")

        if overwrite:
            del source_lines[start:end+1]
            insert_idx = start
        else:
            insert_idx = end + 1

        new_source = source_lines[:insert_idx] + markdown_block + source_lines[insert_idx:]

    # then write it back
    with open(notebook_path, "w") as f:
        f.writelines(new_source)
"""
def extract_dscc_metadata(file_path: str) -> dict:
    """
    Extracts the dscc: metadata block from the first markdown cell in a Databricks notebook (.py format).
    """
    #with open(file_path, "r") as f:
    #    lines = f.readlines()
    lines = read_notebook_source_lines(file_path)

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
    return filename.endswith((".py", ".dbc", ".ipynb"))

def inject_all_defaults(notebook_path: Path):

    #with open(notebook_path) as f:
    #    source_lines = f.readlines()
    source_lines = read_notebook_source_lines(notebook_path)

    if any("# MAGIC dscc:" in line for line in source_lines):
        print(f"⏭️ Skipping {notebook_path.name} (already annotated)")
        return

    try:
        preset = PresetEngine.from_path(notebook_path)
        dscc_meta = preset.to_yaml_dict()
        import pprint
        print("[DEBUG] dscc_meta to be written:")
        pprint.pprint(dscc_meta)
        print("[DEBUG] type(dscc_meta):", type(dscc_meta))
        cleaned_dscc_meta = clean_for_yaml(dscc_meta)
        print("[DEBUG] cleaned_dscc_meta to be written:")
        pprint.pprint(cleaned_dscc_meta)
        write_metadata_block(notebook_path, cleaned_dscc_meta, test_cases=[], source_lines=source_lines)
        print(f"✅ Injected default YAML into {notebook_path.name}")
    except Exception as e:
        print(f"❌ Failed to inject into {notebook_path.name}: {e}")
        import traceback
        traceback.print_exc()



