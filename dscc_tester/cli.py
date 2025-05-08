import sys
from .generator import run

def run_unit_tests(app_path, module=None, exec="local"):
    run(app_path, module=module, exec=exec)

commands = {
    "run_unit_tests": run_unit_tests
}

def main():
    import fire
    allowed_options = {
        'run_unit_tests': {'--app_path', '--module', '--exec', '--help'},
    }
    if len(sys.argv) > 1 and sys.argv[1] in allowed_options:
        allowed = allowed_options[sys.argv[1]]
        unknown = [arg for arg in sys.argv[2:] if arg.startswith('--') and arg.split('=')[0] not in allowed]
        if unknown:
            print(f"❌ Unknown option(s) for '{sys.argv[1]}': {' '.join(unknown)}")
            print(f"Run: dscc tester {sys.argv[1]} --help")
            sys.exit(1)
    fire.Fire(commands)

if __name__ == "__main__":
    main()
