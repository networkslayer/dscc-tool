import fire
import dscc_packaging.cli as packaging_cli
import dscc_tester.cli as tester_cli

def main():
    fire.Fire({
        "packaging": packaging_cli.commands,
        "tester": tester_cli.commands,
    })

if __name__ == "__main__":
    main()

