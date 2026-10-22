import argparse
import json
import sys
from zq.m80j import K85X, q57x
from zq.m95j import q92z


def q44x(q77j):
    if q77j.lower() in ('true', '1', 'yes'):
        return True
    if q77j.lower() in ('false', '0', 'no'):
        return False
    raise argparse.ArgumentTypeError('expected true or false')


def q37x():
    q62j = argparse.ArgumentParser()
    q62j.add_argument('--execute', nargs='?', const=True, default=False, type=q44x)
    q4v = q62j.parse_args()
    try:
        try:
            q42j = json.loads(sys.stdin.read())
        except ValueError:
            raise q57x('invalid JSON input', '')
        q83j = q92z(q42j, q64j=q4v.execute)
        q8v = 0
    except K85X as q84v:
        q83j = {'status': 'error', 'error_code': q84v.q8v, 'message': str(q84v), 'path': q84v.q85x}
        q8v = 1
    sys.stdout.write(json.dumps(q83j))
    sys.stdout.write('\n')
    sys.exit(q8v)

if __name__ == '__main__':
    q37x()
