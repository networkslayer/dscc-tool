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

def run_dscc_tool(command: str, app_path: str):
    """
    Run any dscc-tool CLI command inside Databricks, from a notebook.

    Args:
        command (str): CLI command to run, e.g. 'packaging inject_default_yaml --dry-run'
        app_path (str): Full path to the root of your DSCC app (equivalent to CLI APP_PATH)
    """
    app_path = Path(app_path)
    if not app_path.exists():
        raise FileNotFoundError(f"App path does not exist: {app_path}")

    cmd = ["python3", "-m", "dscc_tool.cli"] + command.strip().split()
    print(f"\n📂 Running from: {app_path}")
    print(f"🚀 Command: {' '.join(cmd)}")

    with temp_chdir(app_path):
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
