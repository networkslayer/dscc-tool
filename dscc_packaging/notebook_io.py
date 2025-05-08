import yaml
from pathlib import Path
import nbformat
from nbformat.notebooknode import NotebookNode
from .shared_utils import extract_dscc_metadata, read_notebook_source_lines


MAGIC_PREFIXES = ("%run", "%pip", "%conda", "%load_ext")


def is_magic_cell(cell):
    if cell.cell_type != "code":
        return False
    lines = cell.source.strip().splitlines()
    return all(any(line.strip().startswith(prefix) for prefix in MAGIC_PREFIXES) for line in lines)


def is_ipynb(path: Path) -> bool:
    return path.suffix == ".ipynb"

def discover_notebook_files(base_path: Path) -> list[Path]:
    return [
        f for f in base_path.rglob("*")
        if f.suffix in [".py", ".ipynb"] and f.is_file()
    ]

def read_notebook_source_lines(notebook_path: Path) -> list[str]:
    """
    Reads a notebook (.py or .ipynb) and returns the logical source lines as a list of strings.
    This is used when injecting metadata or parsing source code.

    Args:
        path (Path): The notebook file path.

    Returns:
        list[str]: Flattened list of source lines (as strings).
    """
    if not is_ipynb(notebook_path):
        with open(notebook_path) as f:
            source_lines = f.readlines()
        return source_lines
        #return notebook_path.read_text(encoding="utf-8").splitlines()

    elif is_ipynb(notebook_path):
        nb: NotebookNode = nbformat.read(notebook_path, as_version=4)
        lines = []
        for cell in nb.cells:
            if cell.cell_type == "code":
                for line in cell.source.splitlines():
                    lines.append(line)
            elif cell.cell_type == "markdown":
                for line in cell.source.splitlines():
                    # Emulate Databricks style
                    lines.append(f"# MAGIC {line}")
        return lines

    else:
        raise ValueError(f"Unsupported notebook format: {notebook_path.suffix}")



def write_metadata_block(notebook_path, dscc_meta, test_cases, source_lines=None, overwrite=False):
    """
    Writes or updates the dscc: and dscc-tests: metadata block in a Databricks notebook (.py or .ipynb).
    - Only updates the YAML block containing a dscc: key.
    - If no such block exists, inserts a new one.
    - Unrelated YAML blocks are left untouched.
    """
    if source_lines is None:
        source_lines = read_notebook_source_lines(notebook_path)

    if not is_ipynb(notebook_path):
        # --- .py logic ---
        # Find all YAML blocks and their indices
        yaml_blocks = []  # (start_idx, end_idx, parsed_yaml)
        in_yaml_block = False
        block_start = None
        block_lines = []
        for idx, line in enumerate(source_lines):
            if "# MAGIC ```yaml" in line:
                in_yaml_block = True
                block_start = idx
                block_lines = []
                continue
            if in_yaml_block and "# MAGIC ```" in line:
                try:
                    parsed = yaml.safe_load("\n".join(block_lines))
                except Exception:
                    parsed = None
                yaml_blocks.append((block_start, idx, parsed))
                in_yaml_block = False
                block_start = None
                block_lines = []
                continue
            if in_yaml_block:
                content = line.strip()
                if content.startswith("# MAGIC "):
                    content = content[len("# MAGIC "):]
                block_lines.append(content)

        # Find the block with a dscc: key
        dscc_block = None
        for start, end, parsed in yaml_blocks:
            if parsed and isinstance(parsed, dict) and "dscc" in parsed:
                dscc_block = (start, end, parsed)
                break

        # Prepare the new/updated metadata
        if dscc_block:
            start, end, parsed = dscc_block
            # Step back to the nearest %md line
            md_start = start
            while md_start > 0 and not source_lines[md_start].strip().startswith("# MAGIC %md"):
                md_start -= 1
            full_metadata = dict(dscc_meta) if overwrite else dict(parsed)
            full_metadata["dscc-tests"] = {"tests": test_cases}
            yaml_lines_out = yaml.dump(full_metadata, sort_keys=False).splitlines()
            _write_magic_yaml_to_py(notebook_path, yaml_lines_out, source_lines, overwrite=True, block_range=(md_start, end))
        else:
            # Always insert a new DSCC block if none exists, regardless of overwrite
            full_metadata = dict(dscc_meta) if dscc_meta else {}
            full_metadata["dscc-tests"] = {"tests": test_cases}
            yaml_lines_out = yaml.dump(full_metadata, sort_keys=False).splitlines()
            _write_magic_yaml_to_py(notebook_path, yaml_lines_out, source_lines, overwrite=True, block_range=None)
    else:
        # --- .ipynb logic ---
        nb: nbformat.NotebookNode = nbformat.read(notebook_path, as_version=4)
        # Find all markdown YAML blocks
        yaml_cells = []  # (cell_idx, parsed_yaml)
        for idx, cell in enumerate(nb.cells):
            if cell.cell_type == "markdown":
                lines = cell.source.splitlines()
                in_yaml = False
                yaml_lines = []
                for line in lines:
                    if line.strip() == "```yaml":
                        in_yaml = True
                        yaml_lines = []
                        continue
                    if in_yaml and line.strip() == "```":
                        break
                    if in_yaml:
                        yaml_lines.append(line)
                if yaml_lines:
                    try:
                        parsed = yaml.safe_load("\n".join(yaml_lines))
                    except Exception:
                        parsed = None
                    yaml_cells.append((idx, parsed))
        # Find the cell with a dscc: key
        dscc_cell = None
        for cell_idx, parsed in yaml_cells:
            if parsed and isinstance(parsed, dict) and "dscc" in parsed:
                dscc_cell = (cell_idx, parsed)
                break
        # Prepare the new/updated metadata
        if dscc_cell:
            cell_idx, parsed = dscc_cell
            full_metadata = dict(dscc_meta) if overwrite else dict(parsed)
            full_metadata["dscc-tests"] = {"tests": test_cases}
            yaml_lines_out = ["```yaml"] + yaml.dump(full_metadata, sort_keys=False).splitlines() + ["```"]
            nb.cells[cell_idx].source = "\n".join(yaml_lines_out)
        else:
            full_metadata = dict(dscc_meta) if dscc_meta else {}
            full_metadata["dscc-tests"] = {"tests": test_cases}
            yaml_lines_out = ["```yaml"] + yaml.dump(full_metadata, sort_keys=False).splitlines() + ["```"]
            from nbformat.v4 import new_markdown_cell
            new_cell = new_markdown_cell(source="\n".join(yaml_lines_out))
            # Insert after first code cell with magic, or at top
            insert_idx = 0
            for i, cell in enumerate(nb.cells):
                if cell.cell_type == "code" and any(cell.source.strip().startswith(cmd) for cmd in ("%run", "%pip", "%conda")):
                    insert_idx = i + 1
            nb.cells.insert(insert_idx, new_cell)
        nbformat.write(nb, notebook_path)

def _write_magic_yaml_to_py(path, yaml_lines, source_lines, overwrite, block_range=None):
    block = ["# MAGIC %md\n", "# MAGIC ```yaml\n"]
    block.extend([f"# MAGIC {line}\n" for line in yaml_lines])
    block.append("# MAGIC ```\n")

    if block_range:
        start, end = block_range
        new_source = source_lines[:start] + block + source_lines[end+1:]
    else:
        insert_idx = next((i for i, line in enumerate(source_lines) if line.startswith("# COMMAND")), 0) + 1
        new_source = source_lines[:insert_idx] + block + source_lines[insert_idx:]

    with open(path, "w") as f:
        f.writelines(new_source)

def _write_yaml_cell_to_ipynb(path: Path, yaml_lines: list, overwrite: bool):
    nb = nbformat.read(path, as_version=4)
    yaml_source = ["```yaml"] + yaml_lines + ["```"]

    # Check for existing dscc: block
    existing_idx = next(
        (i for i, cell in enumerate(nb.cells)
         if cell.cell_type == "markdown" and any("dscc:" in line for line in cell.source)),
        None
    )

    insert_idx = 0
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == "code" and any(cell.source.strip().startswith(cmd) for cmd in ("%run", "%pip", "%conda")):
            insert_idx = i + 1

    new_cell = nbformat.v4.new_markdown_cell(source=yaml_source)

    if existing_idx is not None and overwrite:
        nb.cells[existing_idx] = new_cell
    else:
        nb.cells.insert(insert_idx, new_cell)

    nbformat.write(nb, path)

