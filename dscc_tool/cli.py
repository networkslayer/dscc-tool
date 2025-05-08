import sys

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'packaging':
        # Dispatch to argparse-based CLI in dscc_packaging
        from dscc_packaging.cli import main as packaging_main
        sys.argv = [sys.argv[0]] + sys.argv[2:]  # Remove 'packaging'
        packaging_main()
    else:
        # Fallback to Fire for other top-level commands (e.g., tester)
        import fire
        from dscc_tester import cli as tester_cli
        fire.Fire({
            'tester': tester_cli,
            # Add other top-level namespaces as needed
        })

if __name__ == "__main__":
    main()

