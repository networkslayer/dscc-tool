import yaml
from pathlib import Path
import nbformat
from nbformat.notebooknode import NotebookNode


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
        return notebook_path.read_text(encoding="utf-8").splitlines()

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
    Writes a dscc: and dscc-tests: metadata block to a Databricks notebook,
    supporting both .py and .ipynb formats.
    """
    full_metadata = dict(dscc_meta) if dscc_meta else {}
    full_metadata["dscc-tests"] = {"tests": test_cases}

    yaml_lines = yaml.dump(full_metadata, sort_keys=False).splitlines()

    if not is_ipynb(notebook_path):
        _write_magic_yaml_to_py(notebook_path, yaml_lines, source_lines, overwrite)
    elif is_ipynb(notebook_path):
        _write_yaml_cell_to_ipynb(notebook_path, yaml_lines, overwrite)
    else:
        raise ValueError(f"Unsupported notebook format: {notebook_path}")

def _write_magic_yaml_to_py(path, yaml_lines, source_lines, overwrite):
    block = ["# MAGIC %md\n", "# MAGIC ```yaml\n"]
    block.extend([f"# MAGIC {line}\n" for line in yaml_lines])
    block.append("# MAGIC ```\n")

    has_block = any("# MAGIC dscc:" in line for line in source_lines)

    if not has_block:
        insert_idx = next((i for i, line in enumerate(source_lines) if line.startswith("# COMMAND")), 0) + 1
        new_source = source_lines[:insert_idx] + block + source_lines[insert_idx:]
    else:
        dscc_idx = next(i for i, line in enumerate(source_lines) if "# MAGIC dscc:" in line)
        start = dscc_idx
        while start > 0 and not source_lines[start].strip().startswith("# MAGIC %md"):
            start -= 1
        end = start
        while end < len(source_lines) and not source_lines[end].strip() == "# MAGIC ```":
            end += 1
        if overwrite:
            del source_lines[start:end+1]
            insert_idx = start
        else:
            insert_idx = end + 1
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

