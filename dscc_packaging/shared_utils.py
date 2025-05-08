import yaml
from pathlib import Path
import os
import getpass
import subprocess

def read_notebook_source_lines(notebook_path: Path) -> list[str]:
    """
    Reads a notebook (.py or .ipynb) and returns the logical source lines as a list of strings.
    This is used when injecting metadata or parsing source code.
    Args:
        notebook_path (Path): The notebook file path.
    Returns:
        list[str]: Flattened list of source lines (as strings).
    """
    def is_ipynb(path: Path) -> bool:
        return path.suffix == ".ipynb"

    if not is_ipynb(notebook_path):
        with open(notebook_path) as f:
            source_lines = f.readlines()
        return source_lines
    else:
        import nbformat
        nb: nbformat.NotebookNode = nbformat.read(notebook_path, as_version=4)
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

def extract_dscc_metadata(file_path: str) -> dict:
    """
    Extracts the dscc: metadata block from the first markdown cell in a Databricks notebook (.py format).
    """
    lines = read_notebook_source_lines(Path(file_path))
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
    except Exception:
        return None

def infer_user_name():
    # Try environment variables
    for var in ["GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "USER", "USERNAME"]:
        name = os.environ.get(var)
        if name:
            return name
    # Try getpass
    try:
        name = getpass.getuser()
        if name:
            return name
    except Exception:
        pass
    # Try git config
    try:
        result = subprocess.run(["git", "config", "--get", "user.name"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return "Your Name"

def infer_user_email():
    # Try environment variables
    for var in ["GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL", "EMAIL", "USEREMAIL"]:
        email = os.environ.get(var)
        if email:
            return email
    # Try git config
    try:
        result = subprocess.run(["git", "config", "--get", "user.email"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        email = result.stdout.strip()
        if email:
            return email
    except Exception:
        pass
    return "user@example.com" 