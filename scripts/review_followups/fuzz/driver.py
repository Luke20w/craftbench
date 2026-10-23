# usage: driver.py <codebase_dir> <cases.jsonl> <out.jsonl>   (runs the entrypoint in-process per case)
import sys, io, json, runpy, os, signal
def _alarm(*a): raise TimeoutError('case timed out')
signal.signal(signal.SIGALRM, _alarm)
d, cases, outp = sys.argv[1:4]
sys.path.insert(0, d); sys.dont_write_bytecode = True
entry = os.path.join(d, 'etl_pipeline.py')
real_out = sys.stdout
with open(outp, 'w') as out:
    for line in open(cases):
        c = json.loads(line)
        sys.argv = [entry] + c['argv']; sys.stdin = io.StringIO(c['stdin']); buf = io.StringIO(); sys.stdout = buf
        code = None
        signal.alarm(5)
        try:
            runpy.run_path(entry, run_name='__main__')
        except SystemExit as e:
            code = e.code
        except BaseException as e:
            code = 'CRASH %s: %s' % (type(e).__name__, e)
        signal.alarm(0)
        sys.stdout = real_out
        out.write(json.dumps([code, buf.getvalue()]) + '\n')
