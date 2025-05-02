import os
import subprocess
from pathlib import Path
from contextlib import contextmanager
import tempfile
import shutil
import json
import sys

@contextmanager
def temp_chdir(path: Path):
    """Temporarily change the working directory."""
    original_dir = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

def check_databricks_cli():
    """Check if Databricks CLI is installed and configured."""
    try:
        # Check if databricks command exists
        subprocess.run(["databricks", "--version"], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE, 
                      check=True)
        
        # Check if configured
        result = subprocess.run(["databricks", "configure", "--list"], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
        if "No profiles configured" in result.stdout.decode():
            return False, "Databricks CLI is installed but not configured. Please run 'databricks configure' first."
        return True, None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, "Databricks CLI is not installed. Please install it first: pip install databricks-cli"

def export_for_packaging(workspace_path: str, local_path: str = None):
    """
    Export a Databricks workspace directory for local packaging.
    This function helps users prepare their content for the interactive packaging process.
    
    Args:
        workspace_path (str): Path to the workspace directory (e.g., '/Workspace/Users/me/my_app')
        local_path (str, optional): Local path to export to. If None, creates a temp directory.
    
    Returns:
        str: Path to the exported directory
    """
    # Check Databricks CLI
    cli_installed, error_msg = check_databricks_cli()
    if not cli_installed:
        print(f"❌ {error_msg}")
        print("\n✨ To fix this:")
        print("1. Install the Databricks CLI:")
        print("   pip install databricks-cli")
        print("2. Configure the CLI:")
        print("   databricks configure")
        print("3. Make sure you have access to the workspace")
        print("4. Try again")
        sys.exit(1)

    # Create a temporary directory if no local path specified
    if local_path is None:
        local_path = tempfile.mkdtemp(prefix="dscc_export_")
    
    local_path = Path(local_path)
    local_path.mkdir(parents=True, exist_ok=True)
    
    # Export the workspace directory
    export_cmd = [
        "databricks",
        "workspace",
        "export_dir",
        workspace_path,
        str(local_path),
        "--overwrite"
    ]
    
    print(f"\n📦 Exporting workspace directory to: {local_path}")
    try:
        result = subprocess.run(
            export_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("✅ Export successful!")
        
        # Create a helper script for local packaging
        helper_script = local_path / "package_locally.sh"
        with open(helper_script, "w") as f:
            f.write(f"""#!/bin/bash
# Helper script to package your DSCC app locally
echo "🚀 Starting local packaging process..."
cd "{local_path}"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
if [[ "$python_version" < "3.11" ]]; then
    echo "⚠️ Warning: Python 3.11+ is recommended. Current version: $python_version"
fi

# Install dscc-tool if not already installed
pip install dscc-tool || pip install -e .

# Run the interactive packaging process
dscc packaging prepare_notebooks --app-path .

echo "✨ Packaging complete! Your app is ready in: {local_path}"
echo "📦 To create the final package, run: dscc packaging package --app-path ."
""")
        
        # Make the script executable
        helper_script.chmod(0o755)
        
        # Create a README with instructions
        readme_path = local_path / "README.md"
        with open(readme_path, "w") as f:
            f.write(f"""# DSCC App Packaging Instructions

## 🚀 Quick Start

1. Open a terminal and navigate to this directory:
   ```bash
   cd {local_path}
   ```

2. Run the packaging script:
   ```bash
   ./package_locally.sh
   ```

3. Follow the interactive prompts to complete packaging

4. Create the final package:
   ```bash
   dscc packaging package --app-path .
   ```

## 📦 What's Included

- Your exported notebooks and files
- A helper script for packaging
- This README with instructions

## 🔧 Requirements

- Python 3.11+ (recommended)
- pip (Python package manager)
- dscc-tool package

## ❓ Need Help?

If you encounter any issues:
1. Check the error messages
2. Make sure you have the required dependencies
3. Try running the commands manually
4. Check the [DSCC documentation](https://dscc.databricks.com/docs)

Happy packaging! 🎉
""")
        
        print(f"\n✨ Next steps:")
        print(f"1. Open a terminal and navigate to: {local_path}")
        print(f"2. Run: ./package_locally.sh")
        print(f"3. Follow the interactive prompts to complete packaging")
        print(f"4. After packaging, run: dscc packaging package --app-path .")
        
        return str(local_path)
        
    except subprocess.CalledProcessError as e:
        print("❌ Export failed!")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        print("\n✨ Troubleshooting tips:")
        print("1. Check if the workspace path is correct")
        print("2. Verify your Databricks CLI configuration")
        print("3. Ensure you have access to the workspace")
        print("4. Try running the export command manually:")
        print(f"   databricks workspace export_dir {workspace_path} {local_path} --overwrite")
        raise

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