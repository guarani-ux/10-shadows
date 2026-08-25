import argparse
import json
import sys
from pathlib import Path
from forge.forge import ForgeEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal Capability Forge CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run a Forge request from JSON file or text intent")
    run_parser.add_argument("input", help="Path to request.json or raw text intent string")

    args = parser.parse_args()

    if args.command == "run":
        engine = ForgeEngine()
        input_path = Path(args.input)
        if input_path.is_file():
            with open(input_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            result = engine.run(payload)
        else:
            result = engine.run(args.input)

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
