# 📦 DSCC Packaging App

This CLI app helps you generate, validate, and package detection and analytics apps for submission to the **Databricks Security Content Catalog (DSCC)**. It provides an interactive workflow that guides you from metadata generation to upload.

---

## 🚀 Quickstart

```bash
cd apps/packaging_app

# Generate manifest and metadata
make generate APP=../my_app

# Validate the manifest
make validate APP=../my_app

# Package the app
make package APP=../my_app

# One-click full build + upload
make all APP=../my_app
```

## 🧠 How It Works

### 🔹 Directory Assumptions

Your app should follow this structure:

my_app/
├── base/
│   ├── detections/
│   │   └── my_detection_1.py
│   └── dashboards/
├── metadata/
│   └── meta.yaml


- Notebooks live in base/<content_type>/

- meta.yaml stores top-level metadata (e.g., author, description, platform, etc.)


### 🔹 meta.yaml Format

```yaml
app_friendly_name: Databricks Detection App
author: Derek King
version: 1.0.0
release_notes: Initial release
description: Detects suspicious login activity
content_type: [detections]
requirements:
  platform: [classic, serverless]
  features: [sql_warehouse, jobs]
installation: Run the detection notebook in base/detections
configuration: Set your workspace ID and enable logging
logo: metadata/logo.png
screenshots:
  - metadata/screenshots/0.png
```

🧠 If you use <placeholders> in this file, the generator will prompt you to fill them in interactively.


### 🔹 manifest.yaml Manifest

This file is auto-generated and combines:

Fields from meta.yaml

Metadata extracted from notebooks (from %md cells prefixed with dscc:)

```yaml
app: my_app
app_friendly_name: ...
author: ...
notebooks:
  - path: base/detections/suspicious_login.py
    dscc:
      uuid: ...
      created: ...
      modified: ...
      content_type: detection
      detection:
        name: suspicious_login
        description: ...
```

### 🛠️ Commands

|---------------------------|---------------------------------------------------------|
|Command                    | Description                                             |
|---------------------------|---------------------------------------------------------|
|make generate APP=../my_app| Prompts to clean meta.yaml and builds manifest.yaml         |
|make validate APP=../my_app| Validates manifest.yaml using Pydantic                      |
|make package APP=../my_app | Zips the app folder (excluding hidden files)            |
|make all APP=../my_app     | Runs generate, validate, package, then opens upload page|
|---------------------------|---------------------------------------------------------|



### 🧪 Notebook Requirements
Each .py notebook must contain a %md cell with YAML-style metadata:

```python
# MAGIC %md
# MAGIC ```yaml
# MAGIC dscc:
# MAGIC   author: Derek King
# MAGIC   version: 1.0.0
# MAGIC   platform: databricks
# MAGIC   detection:
# MAGIC     name: suspicious_login
# MAGIC     description: Detects ...
# MAGIC ```
```
Only .py notebooks are currently supported (e.g. exported from Databricks).


## 📤 Upload Flow
When you run make all, the upload form opens with the generated .zip file prefilled. The user can:

- Edit any fields before submission

- View embedded release notes and screenshots

- Finalize submission with OAuth-based login

## 🧩 Future Features (Planned)
- ✅ Auto UUID generation

- ✅ CLI option validation using enums

- 🔄 Inline notebook validation

- 🔄 CI integration for app submission

- 🔄 Support .dbc files (legacy format)


## 🧱 Developer Notes
Written in Python 3.11+

Uses Fire for CLI

Uses Pydantic v2 for validation

