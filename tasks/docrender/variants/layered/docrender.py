"""Render a JSON document tree to a markup format: python docrender.py --to html < doc.json"""
import argparse
import json
import sys

from markup.core.errors import RenderError
from markup.core.nodes import build
from markup.core.pipeline import RenderPipeline, RenderRequest
from markup.formats import load_formats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render a JSON document to a markup format.")
    parser.add_argument("--to", required=True, help="output format")
    args = parser.parse_args(argv)
    try:
        pipeline = RenderPipeline(load_formats())
        output = pipeline.run(RenderRequest(document=build(json.load(sys.stdin)), format_name=args.to)).output
    except (RenderError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
