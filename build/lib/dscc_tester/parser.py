import yaml

CELL_DELIM = "# COMMAND ----------"

def extract_tests_from_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    cells = content.split(CELL_DELIM)
    yaml_block = []
    in_yaml_block = False

    for cell in cells:
        for line in cell.strip().splitlines():
            # Detect YAML fence
            if "```yaml" in line:
                in_yaml_block = True
                continue
            elif "```" in line and in_yaml_block:
                in_yaml_block = False
                break
            elif in_yaml_block:
                # Clean but preserve leading spaces!
                if line.strip().startswith("# MAGIC"):
                    cleaned_line = line.strip()[7:]  # Remove "# MAGIC "
                    yaml_block.append(cleaned_line)
                elif line.strip().startswith("#"):
                    cleaned_line = line.strip()[1:]  # Remove "#"
                    yaml_block.append(cleaned_line)
                else:
                    yaml_block.append(line)

        if yaml_block:
            break


    if not yaml_block:
        return []

    raw_yaml = "\n".join(yaml_block)
    try:
        parsed = yaml.safe_load(raw_yaml)

        test_list = []
        dscc_tests = parsed.get("dscc-tests") if isinstance(parsed, dict) else None
        if isinstance(dscc_tests, dict):
            test_list = dscc_tests.get("tests", [])
        if not test_list:
            test_list = find_nested_key(parsed, "tests") or []

        return test_list if isinstance(test_list, list) else []
    except yaml.YAMLError as e:
        print("❌ Error parsing YAML:", e)
        return []

def normalize_magic(line):
    if line.startswith("# MAGIC"):
        return line[len("# MAGIC"):].strip()
    elif line.startswith("#"):
        return line[1:].strip()
    return line


def find_nested_key(data, key):
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for v in data.values():
            result = find_nested_key(v, key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_nested_key(item, key)
            if result is not None:
                return result
    return None


