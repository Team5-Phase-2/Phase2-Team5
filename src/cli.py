# src/cli.py
import argparse

def main():
    p = argparse.ArgumentParser(prog="acme-ptm")
    p.add_argument("model", help="Model ID or URL")
    args = p.parse_args()
    print({"id": args.model})

if __name__ == "__main__":
    main()
