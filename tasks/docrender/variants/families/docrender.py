"""Render a JSON document tree to a markup format: python docrender.py --to html < doc.json"""
import argparse
import json
import sys

from markup.errors import RenderError
from markup.nodes import build
from markup.renderers import RENDERERS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a JSON document to a markup format.")
    parser.add_argument("--to", required=True, help="output format")
    args = parser.parse_args(argv)
    try:
        renderer = RENDERERS.get(args.to)
        if renderer is None:
            raise RenderError(f"unknown format: {args.to}")
        output = renderer().render(build(json.load(sys.stdin)))
    except (RenderError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
