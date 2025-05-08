#!/bin/bash
# Helper script to package your DSCC app locally
# Usage: ./package_locally.sh [dscc-tool options]
# Example: ./package_locally.sh --noninteractive --no-sample

# Function to clean system files
clean_system_files() {
    local dir="$1"
    echo "🧹 Cleaning system files..."
    
    # macOS files
    find "$dir" -name ".DS_Store" -type f -delete
    find "$dir" -name "._*" -type f -delete
    
    # Windows files
    find "$dir" -name "Thumbs.db" -type f -delete
    
    # Python files
    find "$dir" -name "__pycache__" -type d -exec rm -rf {} +
    find "$dir" -name "*.pyc" -type f -delete
    find "$dir" -name "*.pyo" -type f -delete
    find "$dir" -name "*.pyd" -type f -delete
    
    # Jupyter files
    find "$dir" -name ".ipynb_checkpoints" -type d -exec rm -rf {} +
    
    echo "✅ System files cleaned"
}

echo "🚀 Starting local packaging process..."
cd "/Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app"

# Clean system files before starting
clean_system_files "."

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
if [[ "$python_version" < "3.11" ]]; then
    echo "⚠️ Warning: Python 3.11+ is recommended. Current version: $python_version"
fi

# Install dscc-tool if not already installed
echo -n "🔍 Checking prerequisites... "
if pip install dscc-tool > /dev/null 2>&1 || pip install -e . > /dev/null 2>&1; then
    echo "done."
else
    echo "failed! Please check your Python environment."
    exit 1
fi

# Run the packaging process, passing all user arguments
if dscc packaging prepare_notebooks --app_path "/Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app" "$@"; then
    echo "✅ Notebook preparation complete"
    
    # Generate manifest
    echo "📝 Generating manifest.yaml..."
    if dscc packaging generate_manifest --app_path "/Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app"; then
        echo "✅ Manifest generated"
        
        # Validate manifest
        echo "🔍 Validating manifest..."
        if dscc packaging validate_manifest --manifest_path "/Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app/manifest.yaml"; then
            echo "✨ Packaging complete! Your app is ready in: /Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app"
            echo "📦 To create the final package, run: dscc packaging package --app_path /Users/derek.king/Documents/Dev_Work/dscc_apps/databricks_workspace_detection_app"
        else
            echo "❌ Manifest validation failed. Please fix the errors above and try again."
            exit 1
        fi
    else
        echo "❌ Manifest generation failed. Please fix the errors above and try again."
        exit 1
    fi
else
    echo "❌ Notebook preparation failed. Please fix the errors above and try again."
    exit 1
fi
