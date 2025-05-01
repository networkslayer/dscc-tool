# Databricks Security Content Tool
Security Content packaging and testing tool for Databricks.

# DSCC App Developer Workflow

This guide outlines the recommended workflow for building and submitting a DSCC app.

---

## 📁 App Structure (template_app)

Organize your notebooks and code in the following structure:

```
template_app/
├── base/
│   ├── detections/         # Detection notebooks (.py or .ipynb)
│   ├── models/             # ML model notebooks
│   ├── dashboards/         # Dashboard notebooks
│   ├── pipelines/          # ETL pipeline notebooks
│   └── config/             # YAML configs, global settings
├── lib/                    # Shared Python modules (e.g. helper functions, mock logic)
│                           # Notebooks use: %run ../lib/<file>
├── metadata/
│   ├── meta.yaml           # Global app metadata (used to build dscc.yaml)
│   ├── logo.png            # Required app logo (must be square)
│   └── screenshots/        # Optional UI screenshots for frontend display
│       ├── login.png
│       └── detection-output.png
├── tests/                  # Optional mock input tables (CSV, JSON, Parquet)
│                           # Used by dscc-tester to simulate input data
└── dscc.yaml               # Generated manifest, built by `dscc-tool packaging generate_manifest`
```

---

## 🧠 Where to Put Code

- **Detection Notebooks** → `base/detections/`
- **Shared Functions** → `lib/`
- **Models, Dashboards, Pipelines** → Respectively in `base/models/`, `base/dashboards/`, etc.

You can make any local changes to an app by replicating the directory structure into a `custom`
directory, at the top level with `base`. Doing so, should ensure local changes are never 
overwritten by app upgrades.

---

## ✏️ Adding YAML Metadata

Each notebook in an app should have dscc related yaml markdown block, that holds pertinent information about it.
Depending on the type of notebook (determined by the directory) the dscc keys will differ. 

You can inject metadata in two ways:

### Option 1: Gradual Annotation (Databricks)
Use the `run_dscc_tool()` helper in a notebook:

```python
from dscc_tool.notebook import run_dscc_tool

run_dscc_tool("packaging inject_default_yaml", app_path="/Workspace/your_app")
```

This adds a `dscc:` and `dscc-tests:` block to each notebook, if missing.

### Option 2: Full Interactive Walkthrough (Locally)

From the root of your project (locally):

```bash
make prepare
# OR
dscc packaging prepare_notebooks
```

This guides you through each notebook interactively and allows you to configure test metadata too.

---

## 🛠 Makefile Commands

| Command                | Description                                         | CLI Equivalent                         |
|------------------------|-----------------------------------------------------|----------------------------------------|
| `make prepare`         | Walk through all notebooks and annotate YAML        | `dscc packaging prepare_notebooks`     |
| `make validate`        | Validate YAML and notebook structure                | `dscc packaging validate`              |
| `make package`         | Build ZIP of your app for submission                | `dscc packaging package`               |
| `make test`            | Run all unit tests using pytest                     | `dscc test run --exec local`           |
| `make all`             | Prepare, validate, and package in one step          | Sequence of all above                  |
| `make upload`          | Open web UI to upload the app                       | N/A (opens submission portal)          |

---

## ⬆️ Submitting Your App

Once packaged, the zip file can be submitted by:

1. Visit the [DSCC Submission Portal](https://dscc.databricks.com)
2. Upload your `.zip` file
3. Fill in required metadata (most fields will auto-populate from `dscc.yaml`)
4. Submit for approval

--- 

✅ Done! Your app is now queued for testing and review.


# DSCC Tool

The `dscc-tool` project provides CLI and programmatic utilities for managing and testing apps built on the Databricks Security Content Control (DSCC) framework.

It is composed of three key modules:
- `dscc_tool`: CLI entrypoint and integration logic
- `dscc_packaging`: Notebooks metadata handling and manifest generation
- `dscc_tester`: Test case generation, patching, and Spark-based execution

---

## 📦 Installation

You can install from GitHub via pip:

```bash
pip install git+https://github.com/networkslayer/dscc-tool.git
```

Or clone locally and use in editable mode:

```bash
git clone https://github.com/networkslayer/dscc-tool.git
cd dscc-tool
pip install -e .
```

---

## 🚀 CLI Usage

Once installed, the CLI is exposed via:

```bash
dscc <command>
```

You can also run it directly with:

```bash
python3 -m dscc_tool.cli <command>
```

### Available commands:

#### Packaging commands (`dscc_packaging`)

```bash
dscc packaging inject_default_yaml --app_path <path>
```
Injects default `dscc:` and `dscc-tests:` YAML metadata blocks into all notebooks.

```bash
dscc packaging generate_tests --app_path <path>
```
Scans notebooks for functions and generates `dscc-tests:` blocks with user input.

Options:
- `--dry-run`: Print the YAML instead of writing it.
- `--overwrite`: Overwrite existing metadata.
- `--noninteractive`: Skip prompts and use defaults.
- `--no-sample`: Don't attempt to fetch sample data.

---

## 🧪 Testing and Execution (`dscc_tester`)

```bash
dscc test run --app_path <path> --exec [local|spark]
```

This:
- Extracts notebooks and patches them to run standalone.
- Generates executable test files.
- Runs them via `pytest` (local) or `spark-submit` (inside a container).

Optional:
- `--module <dotted.path>`: Only test a specific module.
- `--exec spark`: Runs inside the `dscc-spark-api` Docker container.

---

## 🧠 Notebook Support

Supports both `.py` (Databricks-exported) and `.ipynb` formats. All internal parsing, test generation, and injection now support both formats using `read_notebook_source_lines()`.

---

## 📓 Using in Databricks Notebooks

You cannot use all `dscc` CLI commands interactively directly inside Databricks notebooks due to input/output stream limitations.

Instead, you can use --nointeractive --no-sample to skip input prompts. This will give you default params only:

To run the tool inside databricks:

```python
from dscc_tool.notebook import run_dscc_tool

run_dscc_tool("packaging inject_default_yaml --app_path /Workspace/Users/.../my_app")
```

This helper:

- Changes directory to your app root
- Invokes CLI with same arguments
- Prints output back into notebook

---

### ⚠️ Limitations of `dscc packaging prepare_notebooks` on Databricks

Due to platform restrictions, Databricks notebooks do **not** support interactive `input()` prompts when running in a notebook or job context. This affects commands like:

```bash
dscc packaging prepare_notebooks
```

which rely on user input to:

- Configure detection function test inputs
- Choose expected outputs
- Select tables or columns to mock

#### ✅ Recommended Workaround

To run this command successfully:

1. **Export your notebook app from Databricks:**
   ```bash
   databricks workspace export_dir /Workspace/Users/<you>/<app> ./my-app --overwrite
   ```

2. **Run the CLI locally (from source or pip-installed):**
   ```bash
   dscc packaging prepare_notebooks --app_path ./my-app
   ```

This enables full interactivity (e.g. input prompts, test case customization, etc.).

> ℹ️ Once the `dscc:` and `dscc-tests:` blocks are injected, you can continue editing and re-uploading notebooks to Databricks. Only the packaging step requires exporting.
 
---

# 🧪 Writing Detection Functions for Unit Test Generation

The `dscc-tool packaging prepare_notebooks` command uses static analysis to **automatically infer test cases** from your notebook code. This works by walking the notebook's abstract syntax tree (AST) and identifying patterns in functions, table usage, and columns.

---

## ✅ How It Works

- The tool parses your notebook and **looks for function definitions** (`def my_detection(...)`).
- For each function:
  - It finds **default values** for parameters, and uses those as sample inputs (if present).
  - It searches for `spark.table("...")` calls and `col("...")` references.
  - It builds a test case that:
    - Mocks any detected Spark tables.
    - Passes in appropriate arguments.
    - Optionally adds expectations like row count or schema checks.

---

## ✅ Best Practices for Testable Code

To ensure your notebook works well with `generate_tests`, follow these guidelines:

### 1. Wrap Your Detection Logic in a Function

```python
@detect(output=Output.asAlert)
def unusual_logins(earliest: str = None, latest: str = None):
    # logic here
    ...
```

> Functions must be defined with `def`. Any top-level Spark code won't be picked up.

---

### 2. Provide Default Values for Parameters

Default values help the test generator infer input examples without requiring user input.

```python
def sso_config_change(earliest: str = "24h", latest: str = "now"):
```

---

### 3. Use `spark.table(...)` and `col(...)` Patterns

The AST analyzer looks for Spark usage like:

```python
df = spark.table("auth.events")
df = df.filter(col("action") == "login")
```

This will:

- Detect `"auth.events"` as a required input table.
- Prompt the user for a **mocked file** to use as test input (CSV, JSON, Parquet).
- Suggest saving it as `tests/auth_events_sample.json`.

---

## 🧪 Mock File Behavior

For each `spark.table("table_name")`, the system:

- Prompts the user for a file path (unless `--no-sample` is passed).
- Defaults to saving as: `tests/table_name_sample.json`
- At runtime, this is loaded using `spark.read.json(...)` or fallback to stub data.

---

## 🧪 Building Assertions

During test inference, if running locally on a laptop you'll be prompted to:

- Choose an assertion type:
  - ✅ Row count
  - ✅ Expected data (JSON)
  - ✅ Schema match
- You can configure fallback behavior (`DSCC_FALLBACK_EMPTY=true`) to use empty DataFrames in place of mocks.

---

## 🔍 Generated Output

The tool writes a metadata block into the notebook like:

```yaml
dscc:
  name: Unusual Login Events
  ...
dscc-tests:
  tests:
    - name: test_case_0
      function: unusual_logins
      input:
        earliest: "2024-01-01"
        latest: "2024-01-02"
      mocked_inputs:
        - table: auth.events
          path: tests/auth_events_sample.json
      expect:
        count: "> 0"
```

This YAML block drives unit test generation via `dscc-tester`.

---

## 💡 Summary

| Practice | Benefit |
|---------|---------|
| ✅ Use functions | AST can detect logic |
| ✅ Add defaults | Auto-populates test args |
| ✅ Use `spark.table` | Prompts for mock data |
| ✅ Save samples in `tests/` | Used in test run |
| ✅ Use `dscc-tests:` block | Enables PyTest export |

---

For more, see `dscc-tool packaging generate_tests --help` or the full README.

---

# 🧪 Writing Manual Unit Tests in DSCC

You can manually define tests in your notebook metadata using the `dscc-tests:` section. This enables you to control inputs, mock data sources, and define expectations without relying on the automatic AST-based test generation.

Place your test metadata in the top markdown cell like:

```yaml
dscc:
  name: Unusual Login Events
  version: 1.0.0
  description: Detects suspicious login activity
  ...
dscc-tests:
  tests:
    - name: test_case_0
      function: unusual_logins
      input:
        earliest: "2024-01-01"
        latest: "2024-01-02"
      mocked_inputs:
        - table: auth.events
          path: tests/auth_events_sample.json
      expect:
        count: "> 0"
```

## 🔍 How It Works

- **function**: The name of the detection function to test (must be defined in notebook).
- **input**: A dictionary of arguments passed to the function. Provide default values for easier test discovery.
- **mocked_inputs**:
  - **table**: Spark table name (e.g. `auth.events`) your function uses via `spark.table("...")`.
  - **path**: Path to sample data file in your app, typically in `tests/`. Supported formats: `.json`, `.csv`, `.parquet`.
- **expect**:
  - **count**: A string like `"> 0"` or `"== 5"` to validate number of rows returned.
  - You can also use:
    - `schema`: To match returned column structure.
    - `data`: To assert specific returned rows (future support).

## 📁 Where to Place Sample Data

Place your test input files here:

```
template_app/
├── tests/
│   ├── auth_events_sample.json     # Mocked input for spark.table("auth.events")
│   └── expected_output.json        # (Optional) expected results to match
```

## ✅ `expect:` Block Options

The `dscc-tests:` section supports multiple ways to assert test output from your detection functions. These can be combined or used individually.

### ✔️ 1. Row Count Expectation

```yaml
expect:
  count: "> 0"         # Other examples: "== 5", "<= 10", "!= 0"
```

This validates that the returned DataFrame has the expected number of rows.

---

### ✔️ 2. Data Equality Expectation

```yaml
expect:
  data: tests/expected_login_output.json
```

This loads a file like `tests/expected_login_output.json` and asserts that the returned DataFrame exactly matches the rows (order-insensitive). Example file contents:

```json
[
  {
    "SRC_USER": "admin@databricks.com",
    "ACTION": "login",
    "STATUS": "Success"
  },
  {
    "SRC_USER": "root@databricks.com",
    "ACTION": "login",
    "STATUS": "Failure"
  }
]
```

---

### ✔️ 3. Schema Expectation

```yaml
expect:
  schema:
    - name: SRC_USER
      type: string
    - name: ACTION
      type: string
    - name: STATUS
      type: string
```

This checks that the returned DataFrame has these columns with matching types. You can omit fields to be lenient.

---

### 📝 Combined Example

```yaml
dscc-tests:
  tests:
    - name: test_case_0
      function: unusual_logins
      input:
        earliest: "2024-01-01"
        latest: "2024-01-02"
      mocked_inputs:
        - table: auth.events
          path: tests/auth_events_sample.json
      expect:
        count: "> 0"
        schema:
          - name: SRC_USER
            type: string
          - name: ACTION
            type: string
        data: tests/expected_login_output.json
```

---

## ✏️ Development

### Project Layout

```
dscc-tool/
├── dscc_tool/         # CLI + integration glue
├── dscc_packaging/    # Manifest generation, metadata injection
├── dscc_tester/       # Test extraction, patching, execution
├── pyproject.toml     # PEP 621 setup
├── README.md
```

### Environment Setup

```bash
pyenv virtualenv 3.11.7 dscc-tool
pyenv local dscc-tool
pip install -e .[dev]
```

Or with Poetry:
```bash
poetry install
```


---

## 📄 License

MIT License
