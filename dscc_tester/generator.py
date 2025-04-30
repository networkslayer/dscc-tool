from dscc_tester.parser import extract_tests_from_file
from dscc_tester.testgen import generate_test_file
import tempfile
import os
import subprocess
import pathlib
import shutil
import zipfile
import re
import warnings

import hashlib

def find_all_detection_notebooks(base_path):
    return list(pathlib.Path(base_path).rglob("*.py"))


def path_to_module(notebook_path, root=None):
    path = pathlib.Path(notebook_path).with_suffix('').resolve()
    if root:
        path = path.relative_to(pathlib.Path(root).resolve())

    parts = list(path.parts)
    if parts and parts[0] in ('.', '..'):
        parts = parts[1:]

    return ".".join(parts)


def extract_requirements_from_pip_magics(base_path):
    requirements = set()
    pattern = re.compile(r"%pip install (.+?)(?:\s+#.*)?$", re.IGNORECASE)

    for file in pathlib.Path(base_path).rglob("*.py"):
        with open(file) as f:
            for line in f:
                match = pattern.search(line.strip())
                if match:
                    pkgs = match.group(1).split()
                    cleaned_pkgs = [pkg for pkg in pkgs if not pkg.startswith('-')]
                    requirements.update(cleaned_pkgs)

    return sorted(requirements)


def detect_pandas_udf_usage(base_path):
    udf_pattern = re.compile(r"(F\.)?pandas_udf|from pyspark\\.sql\\.functions import .*pandas_udf")
    for file in pathlib.Path(base_path).rglob("*.py"):
        with open(file) as f:
            for line in f:
                if udf_pattern.search(line):
                    return True
    return False


def detect_delta_usage(base_path):
    delta_pattern = re.compile(r"from\s+delta\.tables\s+import\s+DeltaTable")
    for file in pathlib.Path(base_path).rglob("*.py"):
        with open(file) as f:
            for line in f:
                if delta_pattern.search(line):
                    return True
    return False


def install_notebook_dependencies(app_path: str, local: bool = False, quiet: bool = False, requirements_output_path: str = None):
    """
    Extracts and installs pip dependencies used in notebooks from %pip magics.

    Args:
        app_path: Root path to the notebook app.
        local: If True, installs directly via pip for local use.
        quiet: If True, suppresses output (useful for Spark).
        requirements_output_path: Optional path to save requirements.txt (e.g., for Docker copy).
    """
    requirements = extract_requirements_from_pip_magics(app_path)

    # Add implicit ones based on code usage
    if detect_pandas_udf_usage(app_path):
        requirements.append("pyarrow")
    if detect_delta_usage(app_path):
        requirements.append("delta-spark")

    requirements = sorted(set(requirements))  # dedupe and sort

    if not requirements:
        if not quiet:
            print("✅ No notebook dependencies found.")
        return

    if not quiet:
        print("📦 Notebook dependencies:")
        for r in requirements:
            print(f"  - {r}")

    # Output the requirements file if needed (for Spark container)
    if requirements_output_path:
        with open(requirements_output_path, "w") as f:
            f.write("\n".join(requirements))

    if local:
        # Check for pip
        if not shutil.which("pip"):
            print("❌ pip is not available in this environment. Cannot install dependencies.")
            return

        hash_path = os.path.join(app_path, ".requirements.hash")
        new_hash = hashlib.md5("\n".join(requirements).encode()).hexdigest()

        if os.path.exists(hash_path):
            with open(hash_path, "r") as f:
                if f.read().strip() == new_hash:
                    if not quiet:
                        print("✅ Requirements already satisfied (no changes).")
                    return

        # Write to a temp file for pip install
        temp_path = os.path.join(app_path, "requirements.txt")
        with open(temp_path, "w") as f:
            f.write("\n".join(requirements))

        if not quiet:
            print("🔧 Installing dependencies...")

        subprocess.run([
            "pip", "install", "--no-warn-script-location", "--disable-pip-version-check", "-q", "-r", temp_path
        ], check=True)

        # Save hash to skip reinstalling
        with open(hash_path, "w") as f:
            f.write(new_hash)

        if not quiet:
            print("✅ Dependencies installed.")

def infer_required_columns_from_source(filepath):
    required = set()
    column_patterns = [
        re.compile(r"col\([\"'](.*?)[\"']\)"),
        re.compile(r"\['(.*?)'\]"),
        re.compile(r'\"(.*?)\"\s*(==|!=|in|not in)'),
        re.compile(r"'(.*?)'\s*(==|!=|in|not in)"),
    ]
    with open(filepath) as f:
        code = f.read()
        for pattern in column_patterns:
            required.update(pattern.findall(code))
    return sorted(set(x if isinstance(x, str) else x[0] for x in required))


def generate_stub_schema_code(columns):
    from textwrap import indent
    from collections import defaultdict

    def build_nested(fields):
        tree = lambda: defaultdict(tree)
        root = tree()

        for col in fields:
            parts = col.split('.')
            current = root
            for part in parts:
                current = current[part]

        def recurse(node):
            struct_fields = []
            for key, child in sorted(node.items()):
                if child:
                    nested_struct = recurse(child)
                    struct_fields.append(f"StructField('{key}', StructType([{nested_struct}]))")
                else:
                    struct_fields.append(f"StructField('{key}', StringType())")
            return ",\n".join(struct_fields)

        return recurse(root)

    nested_fields = build_nested(columns)
    return indent(f"StructType([\n{nested_fields}\n])", "                ")


def rewrite_run_magics(filepath, exec_mode="local"):
    required_columns = infer_required_columns_from_source(filepath)

    with open(filepath, 'r') as f:
        lines = f.readlines()

    rewritten = [
        "from pyspark.sql import SparkSession\n",
        "import os\n",
        "import datetime\n",
        "def mock_table(name):\n",
        "    base = f\"tests/{name.replace('.', '_')}\"\n",
        "    try:\n",
        "        if os.path.exists(base + '.parquet'):\n",
        "            return spark.read.parquet(base + '.parquet')\n",
        "        elif os.path.exists(base + '.csv'):\n",
        "            return spark.read.option('header', True).csv(base + '.csv')\n",
        "        elif os.path.exists(base + '.json'):\n",
        "            return spark.read.json(base + '.json')\n",
        "        raise FileNotFoundError('No supported mock files found')\n",
        "    except Exception as e:\n",
        "        print(f'⚠️  Failed to load mock data for table {name}: {e}')\n",
        "        if os.getenv('DSCC_FALLBACK_EMPTY', 'false') == 'true':\n",
        "            print('🔁 Falling back to empty DataFrame')\n",
        "            from pyspark.sql.types import StructType\n",
        "            return spark.createDataFrame([], StructType([]))\n",
        "        else:\n",
        "            print('⚠️  Attempting to return stub test data')\n",
        "            from pyspark.sql.types import StructType, StructField, StringType\n",
        f"            schema = {generate_stub_schema_code(required_columns)}\n",
        "            def build_stub_row(schema):\n",
        "                from pyspark.sql.types import StructType\n",
        "                row = {}\n",
        "                for field in schema.fields:\n",
        "                    if isinstance(field.dataType, StructType):\n",
        "                        row[field.name] = build_stub_row(field.dataType)\n",
        "                    else:\n",
        "                        row[field.name] = 'test'\n",
        "                return row\n",
        "            data = [build_stub_row(schema)]\n",
        "            return spark.createDataFrame(data, schema)\n",
        "\n",
        "# Patch spark.table to use mock\n",
        "SparkSession.table = lambda self, name: mock_table(name)\n"
    ]

    if exec_mode == "spark":
        rewritten.append("""
# Auto-configure Delta if available
builder = SparkSession.builder.appName("dscc-test")
try:
    import delta
    builder = delta.configure_spark_with_delta_pip(builder)
except ImportError:
    print("⚠️ delta-spark not available — skipping Delta config.")

spark = builder.getOrCreate()
spark.sparkContext.setLogLevel("WARN")                         
""")
    else:
        rewritten.append("spark = SparkSession.builder.appName('dscc-test').getOrCreate()\n\nspark.sparkContext.setLogLevel('WARN')\n\n")

    display_pattern = re.compile(r'\bdisplay\((.*?)\)', re.DOTALL)

    def replace_display(match):
        inner = match.group(1).strip()
        return f"({inner}).show()"

    for line in lines:
        normalized_line = line.strip().lstrip("# MAGIC").strip()
        if normalized_line.strip().startswith("%run"):
            parts = normalized_line.strip().split()
            if len(parts) > 1:
                rewritten.append(f"# NOTE: replaced magic `%run {parts[1]}`\n")
                module_path = pathlib.Path(parts[1]).with_suffix('').parts
                import_stmt = "from " + ".".join(p for p in module_path if p not in ('..', '.')) + " import *"
                rewritten.append(import_stmt + "\n")
            else:
                rewritten.append(line)
        else:
            line = display_pattern.sub(replace_display, line)
            rewritten.append(line)

    rewritten.append("\nif __name__ == '__main__':\n")
    if exec_mode == "spark":
        rewritten.append("    try:\n")
        rewritten.append("        result = test_case_0()\n")
        rewritten.append("        count = result.count() if result else 0\n")
        rewritten.append("        print(f'✅ Test ran with result count: {count}')\n")
        #rewritten.append("        if count == 0:\n")
        #rewritten.append("            print('⚠️  Soft assert failed: test did not match expected output count')\n")
        rewritten.append("        with open('/tmp/coverage.log', 'a') as log:\n")
        rewritten.append("            log.write(f'{__file__}: count={count}\\n')\n")
        rewritten.append("    except Exception as e:\n")
        rewritten.append("        print(f'❌ Test error: {e}')\n")
    else:
        rewritten.append("    import pytest\n")
        rewritten.append("    import sys\n")
        rewritten.append("    sys.exit(pytest.main([__file__]))\n")

    with open(filepath, 'w') as f:
        f.writelines(rewritten)

def print_coverage_summary():
    coverage_path = '/tmp/coverage.log'
    if not os.path.exists(coverage_path):
        print("⚠️  No coverage log found.")
        return

    print("\n📊 DSCC Test Coverage Report:\n")
    with open(coverage_path, 'r') as f:
        lines = f.readlines()

    total = len(lines)
    passing = 0
    failing = 0
    empty = 0

    for line in lines:
        path, count = line.strip().split(": count=")
        count = int(count)
        status = "✅"
        if count == 0:
            status = "⚠️ "
            empty += 1
        else:
            passing += 1
        print(f"{status} {path} — returned {count} rows")

    failing = total - passing
    print("\n📌 Summary:")
    print(f"  ✅ Passed: {passing}")
    print(f"  ⚠️  Empty Results: {empty}")
    print(f"  ❌ Failed (exceptions): {failing}")
    print(f"  📄 Total Tests: {total}")



def ensure_inits(path):
    for root, dirs, files in os.walk(path):
        if "__init__.py" not in files:
            open(os.path.join(root, "__init__.py"), "a").close()


def patch_source_tree(app_path, tmpdir):
    patched_root = os.path.join(tmpdir, "patched")
    shutil.copytree(app_path, patched_root, dirs_exist_ok=True)

    for notebook in find_all_detection_notebooks(os.path.join(patched_root, "base")):
        rewrite_run_magics(notebook)

    ensure_inits(patched_root)
    return patched_root


def run(app_path, module=None, exec="local"):
    detection_files = find_all_detection_notebooks(os.path.join(app_path, "base"))
    print(f"🔍 Found {len(detection_files)} detection notebooks in {app_path}/base")

    with tempfile.TemporaryDirectory() as tmpdir:
        patched_root = patch_source_tree(app_path, tmpdir)

        for file in detection_files:
            tests = extract_tests_from_file(file)
            print(f"Extracted {len(tests)} Tests from:", file)
            for test in tests:
                print(test)

            if not tests:
                continue  # skip if no tests found

            module_path = path_to_module(file, root=app_path)
            # output_path = os.path.join(tmpdir, "test_generated.py")
            output_path = os.path.join(patched_root, "test_generated.py")

            generate_test_file(tests, output_path, module_path)
            rewrite_run_magics(output_path, exec_mode=exec)
            print(f"Generated test file at: {output_path}")

            if exec == "spark":
                run_on_spark(output_path, app_path, tmpdir)
            elif exec == "local":
                run_locally(output_path, patched_root)
            else:
                print(f"Unknown execution mode: {exec}")


def run_locally(test_path, patched_root):
    print(f"▶️ Running tests locally with pytest...{test_path}")
    install_notebook_dependencies(patched_root, local=True)
    
    env = os.environ.copy()
    test_dir = os.path.dirname(test_path)
    env["PYTHONPATH"] = f"{test_dir}:{patched_root}:{env.get('PYTHONPATH', '')}"

    # Set working directory to patched_root to match how imports work
    import sys
    subprocess.run([sys.executable, "-m", "pytest", test_path], env=env, cwd=patched_root)


def run_on_spark(test_path, app_root, tmpdir):
    print("🚀 Running tests using Spark inside dscc-spark-api container...")

    zip_path = os.path.join(tmpdir, "app.zip")
    patched_path = os.path.join(tmpdir, "patched")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message="Duplicate name:")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(patched_path):
                rel_root = os.path.relpath(root, patched_path)
                init_path = os.path.join(root, "__init__.py")
                if not os.path.exists(init_path):
                    open(init_path, "w").close()
                zipf.write(init_path, os.path.join(rel_root, "__init__.py"))
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, patched_path)
                    zipf.write(file_path, arcname)

    # Extract and install notebook requirements
    requirements_path = os.path.join(tmpdir, "requirements.txt")
    install_notebook_dependencies(app_root, local=False)

    if os.path.exists(os.path.join(app_root, "requirements.txt")):
        subprocess.run(["docker", "cp", os.path.join(app_root, "requirements.txt"), "dscc-spark-api:/tmp/requirements.txt"], check=True)
        subprocess.run([
            "docker", "exec", "dscc-spark-api",
            "bash", "-c",
            "pip install --no-warn-script-location --quiet --disable-pip-version-check -r /tmp/requirements.txt"
        ], check=True)

    try:
        subprocess.run(["docker", "cp", test_path, "dscc-spark-api:/tmp/test_generated.py"], check=True)
        subprocess.run(["docker", "cp", zip_path, "dscc-spark-api:/tmp/app.zip"], check=True)
        subprocess.run([
            "docker", "exec", "dscc-spark-api",
            "bash", "-c",
            "cd /tmp && export PYTHONPATH=/tmp:/tmp/app && unzip -qq -o /tmp/app.zip -d /tmp/app && spark-submit test_generated.py 2>/dev/null"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Spark test failed: {e}")