import argparse

def main():
    parser = argparse.ArgumentParser(prog="acme-ptm")
    parser.add_argument("model", help="Model ID or URL to inspect")
    args = parser.parse_args()
    print({"id": args.model})

if __name__ == "__main__":
    main()