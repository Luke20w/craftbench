"""ETL pipeline CLI: validate, normalize and execute a JSON pipeline over in-memory rows.

etl/validate.py checks and normalizes each step; etl/execute.py runs them."""

import argparse
import json
import sys

from etl.errors import EtlError, schema_error
from etl.request import process

def parse_bool(v):
    if v.lower() in ('true', '1', 'yes'):
        return True
    if v.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError('expected true or false')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', nargs='?', const=True, default=False, type=parse_bool)
    args = parser.parse_args()
    try:
        try:
            req = json.loads(sys.stdin.read())
        except ValueError:
            raise schema_error('ETL_ERROR: invalid JSON input', '')
        result = process(req, run=args.execute)
        code = 0
    except EtlError as e:
        result = {'status': 'error', 'error_code': e.code, 'message': str(e), 'path': e.path}
        code = 1
    sys.stdout.write(json.dumps(result))
    sys.stdout.write('\n')
    sys.exit(code)

if __name__ == '__main__':
    main()
