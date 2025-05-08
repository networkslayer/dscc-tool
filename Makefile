.PHONY: generate validate package build upload infer_tests all clean install

# Set your app directory when running, like:
#   make generate_unittests APP=../apps/my_detection_app ARGS

ifndef APP
  $(error ❌ APP is not set. Usage: make <command> APP=../your_app_directory)
endif

# Variables
MANIFEST ?= $(APP)/manifest.yaml
ZIP := $(notdir $(APP)).zip
DSCC_CLI := dscc
ARGS ?=

# Create unittest yaml

generate_unittests:
	@echo "🧪 Inspecting $(APP) and inferring unittests ..."
	@$(DSCC_CLI) tester infer_tests --app_path $(APP) $(ARGS)

# Packaging Commands

clean_system_files:
	@echo "🧹 Cleaning system files..."
	@find $(APP) -name ".DS_Store" -type f -delete
	@find $(APP) -name "._*" -type f -delete
	@find $(APP) -name "Thumbs.db" -type f -delete
	@find $(APP) -name "__pycache__" -type d -exec rm -rf {} +
	@find $(APP) -name "*.pyc" -type f -delete
	@find $(APP) -name "*.pyo" -type f -delete
	@find $(APP) -name "*.pyd" -type f -delete
	@find $(APP) -name ".ipynb_checkpoints" -type d -exec rm -rf {} +
	@echo "✅ System files cleaned"

generate_manifest:
	@echo "📦 Generating manifest.yaml for $(APP) $(ARGS)..."
	@$(DSCC_CLI) packaging generate_manifest --app_path $(APP) $(ARGS)

validate_manifest:
	@echo "🔎 Validating manifest: $(MANIFEST) $(ARGS)..."
	@$(DSCC_CLI) packaging validate_manifest --manifest_path $(MANIFEST) $(ARGS)

zip:
	@echo "📦 Packaging $(APP) into $(ZIP)..."
	@APP_ABS=$$(realpath $(APP)); \
	APP_PARENT=$$(dirname $$APP_ABS); \
	APP_BASENAME=$$(basename $$APP_ABS); \
	cd $$APP_PARENT && zip -r ../$(ZIP) $$APP_BASENAME > /dev/null
	@echo "✅ Created: $(ZIP)"

package: generate_manifest validate_manifest clean_system_files zip


	

build: generate_unittests package
	@echo "🚀 Build complete for $(APP)"

upload:
	@echo "🚀 Uploading $(ZIP) to DSCC..."
	@APP_ZIP_PATH=$(realpath ../$(ZIP)) && \
	open "http://localhost:8000/upload_form?zip_path=$$APP_ZIP_PATH"

all: build upload

# Helpers

clean:
	@echo "🧹 Cleaning build artifacts..."
	@rm -f ../*.zip
	@rm -rf dist/ build/ *.egg-info

install:
	@echo "📦 Installing locally (editable mode)..."
	# @pip install -e .

