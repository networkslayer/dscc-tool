import os
import subprocess
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def temp_chdir(path: Path):
    """Temporarily change the working directory."""
    original_dir = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

def run_dscc_tool(command: str):
    """
    Run any dscc-tool CLI command inside Databricks, from a notebook.

    Args:
        command (str): Full CLI command to run, e.g. 'packaging inject_default_yaml --app-path /path/to/app'
    """
    cmd = ["python3", "-m", "dscc_tool.cli"] + command.strip().split()
    print(f"\n🚀 Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("✅ Success")
        print(result.stdout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print("❌ Command failed")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return e.stderr
