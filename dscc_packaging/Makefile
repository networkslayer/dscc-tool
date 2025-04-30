.PHONY: generate validate package build upload all

ifndef APP
  $(error ❌ APP is not set. Usage: make <command> APP=../your_app_directory)
endif


MANIFEST ?= $(APP)/manifest.yaml
ZIP := $(notdir $(APP)).zip

generate:
	@set -e; \
	echo "📦 Generating manifest.yaml for $(APP)..."
	@PYTHONPATH=.. python -m packaging_app.cli generate_manifest $(APP);
	@echo "✅ Done."

validate:
	@set -e; \
	echo "🔎 Validating manifest: $(MANIFEST)"
	@PYTHONPATH=.. python -m packaging_app.cli validate_manifest $(MANIFEST)

package:
	@set -e; \
	echo "📦 Packaging $(APP) into $(ZIP)..."; \
	APP_ABS=$$(realpath $(APP)); \
	APP_PARENT=$$(dirname $$APP_ABS); \
	APP_BASENAME=$$(basename $$APP_ABS); \
	cd $$APP_PARENT && zip -r ../$(ZIP) $$APP_BASENAME > /dev/null; \
	echo "✅ Created: $(ZIP)"

dkmove:
	@set -e; \
	echo "📦 Moving $(ZIP) to DSCC..."
	@mv ../../$(ZIP) /Users/derek.king/Downloads/

build: generate validate package dkmove
	@echo "🚀 Build complete for $(APP)"

upload:
	echo "🚀 Uploading $(ZIP) to DSCC..."
	@APP_ZIP_PATH=$(realpath ../$(ZIP)) && \
	open "http://localhost:8000/upload_form?zip_path=$$APP_ZIP_PATH"



all: build upload
