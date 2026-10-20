"""CLI entry point: read an ETL request (JSON) on stdin, write a JSON response."""

import argparse
import json
import sys

from etl.errors import SCHEMA_VALIDATION_FAILED, EtlError
from etl.execute import execute
from etl.normalize import normalize_steps, validate_request


def _bool_arg(text):
    value = text.strip().lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(f"expected true or false, got {text!r}")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", nargs="?", const=True, default=False, type=_bool_arg,
        help="execute the pipeline and return data/metrics instead of the normalized steps",
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def process(raw_text, run=False):
    try:
        request = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise EtlError(SCHEMA_VALIDATION_FAILED, f"invalid JSON input: {exc}", "")
    steps, dataset = validate_request(request)
    normalized = normalize_steps(steps)
    if run:
        return {"status": "ok", **execute(normalized, dataset)}
    return {"status": "ok", "normalized": {"steps": normalized}}


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        response, code = process(sys.stdin.read(), run=args.execute), 0
    except EtlError as err:
        response, code = err.to_response(), 1
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
