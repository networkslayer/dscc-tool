import re

def generate_test_file(tests, output_path, function_module):
    lines = [
        f"from {function_module} import *\n",
        "import pytest\n",
        "import json\n",
        "import os\n",
        "from pyspark.sql.types import StructType\n\n"
    ]

    def add_assertions(expect_block):
        assertions = []
        if "count" in expect_block:
            count_val = str(expect_block["count"]).strip()

            match = re.match(r"^\s*(==|>|>=|<|<=)\s*(\d+)\s*$", count_val)
            if match:
                op, num = match.groups()
                assertions.append(f"    assert df.count() {op} {num}")
            else:
                print(f"⚠️  Invalid count assertion format: '{count_val}'. Expected formats like '> 0', '== 5', etc.")
        if "data" in expect_block:
            assertions.append(f"    with open(os.path.join(os.path.dirname(__file__), '{expect_block['data']}')) as f:")
            assertions.append("        expected_data = [json.loads(line) for line in f]")
            assertions.append("    actual_data = [row.asDict() for row in df.collect()]")
            assertions.append("    assert actual_data == expected_data")
        if "schema" in expect_block:
            assertions.append(f"    expected_schema = {expect_block['schema']}")
            assertions.append("    assert df.schema == expected_schema")
        return assertions

    for i, test in enumerate(tests):
        func_name = test['function']
        raw_input_args = test.get('input', {})
        expect_block = test.get('expect', {})

        input_args = {}
        if isinstance(raw_input_args, list):
            for item in raw_input_args:
                if isinstance(item, dict):
                    input_args.update(item)
        elif isinstance(raw_input_args, dict):
            input_args = raw_input_args

        desc = test.get('description', f"Test case {i}")
        input_str = ', '.join(f"{k}={repr(v)}" for k, v in input_args.items())

        lines.append(f"def test_case_{i}():")
        lines.append(f"    \"\"\"{desc}\"\"\"")
        lines.append(f"    df = {func_name}({input_str})")

        if expect_block:
            lines.extend(add_assertions(expect_block))
        lines.append("")

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
