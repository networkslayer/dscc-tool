from pathlib import Path
from typing import Dict, Any, List
import ast
import yaml
import logging
import pathlib

try:
    from pyspark.sql import SparkSession
    spark_available = True
except ImportError:
    spark_available = False

def normalize_notebook_filename(notebook_path: Path) -> Path:
    original_name = notebook_path.name
    new_name = original_name.replace(" ", "_").lower()
    if new_name != original_name:
        new_path = notebook_path.with_name(new_name)
        print(f"⚠️  Renaming notebook from '{original_name}' to '{new_name}'")
        notebook_path.rename(new_path)
        return new_path
    return notebook_path

def prompt_input_args(defaults: Dict[str, Any]) -> Dict[str, Any]:
    print("🧠 Specify input arguments for the detection function:")
    result = {}
    for k, v in defaults.items():
        user_val = input(f"🔹 {k} [{v}]: ").strip()
        if user_val:
            result[k] = type(v)(user_val)
        else:
            result[k] = v
    return result

def get_sample_data(table_name: str, func_name: str, notebook_path: Path, noninteractive: bool = False) -> Path:
    override = table_name
    if not noninteractive:
        print(f"📌 Detected use of `{table_name}` in `{func_name}`.")
        override = input(f"🔁 Table to use for sample data [default: {table_name}]: ").strip() or table_name

    sample_path = notebook_path.parent.parent / "tests" / f"{func_name}_{override.replace('.', '_')}_sample.json"

    try:
        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        spark.sparkContext.setLogLevel("ERROR")
        logging.getLogger("py4j").setLevel(logging.ERROR)
        logging.getLogger("org.apache.spark").setLevel(logging.ERROR)

        if not noninteractive:
            print("🧪 Optional filter expression (e.g., action_name = 'IpAccessDenied'):")
        filter_expr = input("🔎 Filter: ").strip() if not noninteractive else ""

        df = spark.table(override)
        if filter_expr:
            df = df.filter(filter_expr)
        df.limit(10).toPandas().to_json(sample_path, orient='records', lines=True)
        print(f"📁 Sample saved to {sample_path}")
    except Exception as e:
        print(f"⚠️ Could not fetch sample for {override}: {e}")

    return sample_path

def build_expect_block(noninteractive: bool = False) -> Dict[str, Any]:
    print("📥 Define expectations for this test case.")
    default_count = ">0"
    count = input(f"✅ Expected row count (e.g., 0, >0) [{default_count}]: ").strip() or default_count
    json_path = input("📄 Path to expected output .json file (optional): ").strip() or None
    return {
        "count": count,
        "schema": [],
        "data": json_path if json_path else None
    }

def build_test_case(func_name: str, call_args: Dict[str, Any], sample_path: Path, table_names: List[str], required_columns: List[str], expect_block: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "function": func_name,
        "input": call_args,
        "expect": expect_block,
        "mocked_inputs": [{"table": t, "path": str(sample_path)} for t in table_names],
        "required_columns": sorted(required_columns)
    }

def infer_dscc_tests(notebook_path: Path, dry_run: bool = False, overwrite: bool = False, no_sample: bool = False, noninteractive: bool = False):
    notebook_path = normalize_notebook_filename(notebook_path)
    with open(notebook_path) as f:
        source_lines = f.readlines()
        clean_lines = [line for line in source_lines if not line.strip().startswith('%')]
        tree = ast.parse("".join(clean_lines), filename=str(notebook_path))

    test_cases = []
    detection_functions, function_calls = {}, {}
    function_tables, function_columns = {}, {}

    class Analyzer(ast.NodeVisitor):
        current_function = None
        def visit_FunctionDef(self, node):
            detection_functions[node.name] = node
            Analyzer.current_function = node.name
            function_tables[node.name], function_columns[node.name] = set(), set()
            self.generic_visit(node)
            Analyzer.current_function = None

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'table':
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'spark':
                    if node.args and isinstance(node.args[0], ast.Constant):
                        function_tables[Analyzer.current_function].add(node.args[0].value)
            elif isinstance(node.func, ast.Name) and node.func.id == 'col':
                if node.args and isinstance(node.args[0], ast.Constant):
                    function_columns[Analyzer.current_function].add(node.args[0].value)
            elif isinstance(node.func, ast.Name) and node.func.id in detection_functions:
                kwargs = {kw.arg: kw.value.value if isinstance(kw.value, ast.Constant) else None for kw in node.keywords}
                function_calls.setdefault(node.func.id, []).append(kwargs)
            self.generic_visit(node)

    Analyzer().visit(tree)

    for func_name in detection_functions:
        calls = function_calls.get(func_name, [{}])
        for idx, call_args in enumerate(calls):
            print(f"\n🚀 Configuring test for `{func_name}`:")
            input_args = prompt_input_args(call_args) if not noninteractive else call_args

            sample_path = None
            if not no_sample and spark_available:
                for table in function_tables.get(func_name, []):
                    sample_path = get_sample_data(table, func_name, notebook_path, noninteractive)

            expect_block = build_expect_block(noninteractive)
            test_case = build_test_case(func_name, input_args, sample_path, list(function_tables.get(func_name, [])), list(function_columns.get(func_name, [])), expect_block)
            test_cases.append(test_case)

    if dry_run:
        print(yaml.dump({"dscc": {"name": "<name>", "version": "<version>", "description": "<description>"}, "dscc-tests": {"tests": test_cases}}, sort_keys=False))
        return test_cases

    markdown_block = [
        "# MAGIC %md\n",
        "# MAGIC ### Detection Metadata\n",
        "# MAGIC ```yaml\n",
        "# MAGIC dscc:\n",
        "# MAGIC   name: <name>\n",
        "# MAGIC   version: <version>\n",
        "# MAGIC   description: <description>\n",
        "# MAGIC dscc-tests:\n",
        "# MAGIC   tests:\n",
    ]
    for line in yaml.dump(test_cases, sort_keys=False).splitlines():
        markdown_block.append(f"# MAGIC     {line}\n")
    markdown_block.append("# MAGIC ```\n")

    has_block = any("# MAGIC dscc:" in line for line in source_lines)
    if not has_block:
        insert_idx = next((i for i, line in enumerate(source_lines) if line.startswith("# COMMAND")), 0) + 1
        new_source = source_lines[:insert_idx] + markdown_block + source_lines[insert_idx:]
    else:
        start = next(i for i, line in enumerate(source_lines) if "# MAGIC dscc-tests:" in line)
        tests_start = next(i for i, line in enumerate(source_lines[start:], start=start) if "# MAGIC   tests:" in line)
        end = next(i for i, line in enumerate(source_lines[tests_start:], start=tests_start) if "# MAGIC ```" in line)

        if overwrite:
            del source_lines[tests_start + 1:end]
            end = tests_start + 1

        new_source = source_lines[:end] + [f"# MAGIC     {line}\n" for line in yaml.dump(test_cases, sort_keys=False).splitlines()] + source_lines[end:]

    with open(notebook_path, "w") as f:
        f.writelines(new_source)
    print(f"✅ Inserted detection metadata block in {notebook_path.name}")

    return test_cases


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

