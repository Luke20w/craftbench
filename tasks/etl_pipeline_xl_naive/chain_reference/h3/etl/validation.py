"""How validation reports problems: stop at the first one (default), or, with --all-errors, keep going and
remember the first problem of every step. With --strict, unknown keys are problems too."""

from etl.errors import EtlError, schema_error

STRICT = False  # --strict: an unknown key in a step, or in an object inside a step, is an error

def check_keys(raw, known, path):
    """With --strict, the first key of `raw` (in request order) that isn't in `known` is an error."""
    if STRICT:
        for k in raw:
            if k not in known:
                raise schema_error("unknown field '%s'" % k, '%s.%s' % (path, k))

class Report:
    """The first problem of every step, in the order steps start, plus the first problem found overall."""

    def __init__(self):
        self.entries = []   # [path, first problem or None], one per step, in the order steps start
        self.open = []      # entries of the steps being read, innermost last
        self.first = None

    def start(self, path):
        entry = [path, None]
        self.entries.append(entry)
        self.open.append(entry)

    def end(self):
        self.open.pop()

    def add(self, err):
        if self.first is None:
            self.first = err
        if self.open and self.open[-1][1] is None:
            self.open[-1][1] = err

    def problems(self):
        return [e for _, e in self.entries if e is not None]

REPORT = None   # the active Report while validating with --all-errors

FAILED = object()

def attempt(fn, *args):
    """Run one check. Normally its error propagates; while collecting it is recorded and FAILED returned,
    so the checks after it (and the steps nested after it) still run."""
    if REPORT is None:
        return fn(*args)
    try:
        return fn(*args)
    except EtlError as e:
        REPORT.add(e)
        return FAILED

def collect(fn, *args):
    """Run a whole validation with --all-errors; raise the first problem found, carrying all of them."""
    global REPORT
    REPORT = Report()
    try:
        result = fn(*args)
        report = REPORT
    finally:
        REPORT = None
    if report.first is not None:
        report.first.problems = report.problems()
        raise report.first
    return result
