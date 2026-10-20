"""CLI entrypoint: read an ETL request (JSON) on stdin, write a JSON response.

Usage: etl_pipeline.py [--execute[=true|false]]

Without --execute the normalized pipeline is returned; with it the pipeline
is run over the dataset and `data` plus `metrics` are returned.
Exit code 0 on success, 1 on error.
"""

import argparse
import json
import sys

from etl.errors import SCHEMA_VALIDATION_FAILED, EtlError
from etl.executor import execute
from etl.schema import parse_request


def _parse_bool(text):
    value = text.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"expected true or false, got {text!r}")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--execute", nargs="?", const=True, default=False, type=_parse_bool,
        help="execute the pipeline instead of only normalizing it",
    )
    return parser.parse_args(argv)


def run(raw_text, execute_pipeline=False):
    """Process a raw request string; return (response_dict, exit_code)."""
    try:
        try:
            request = json.loads(raw_text)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise EtlError(SCHEMA_VALIDATION_FAILED, f"invalid JSON input: {exc}", "")
        steps, dataset = parse_request(request)
        if not execute_pipeline:
            return {"status": "ok", "normalized": {"steps": steps}}, 0
        data, metrics = execute(steps, request["pipeline"]["steps"], dataset)
    except EtlError as err:
        return err.to_response(), 1
    return {"status": "ok", "data": data, "metrics": metrics}, 0


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    response, code = run(sys.stdin.read(), execute_pipeline=args.execute)
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
