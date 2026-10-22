"""Steps, ops and the runtime context. Ops register themselves; see etl/ops/."""

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, eval_at
from etl.fields import List, Text, read_fields

class Step:
    """A normalized step: its op, its field values and the path it was read from."""

    def __init__(self, op, values, path, raw):
        self.op = op
        self.values = values
        self.path = path
        self.raw = raw

    @staticmethod
    def parse(raw, path):
        if not isinstance(raw, dict):
            raise schema_error('step must be an object', path)
        name = Text('op').read(raw, path).lower()
        if name not in OPS:
            raise EtlError('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % name, path + '.op')
        op = OPS[name]
        return Step(op, op.normalize(raw, path), path, raw)

    def __getitem__(self, key):
        return self.values[key]

    def at(self, *parts):
        """Error path below this step, e.g. step.at('columns', 2) -> '<path>.columns[2]'."""
        p = self.path
        for part in parts:
            p += '[%d]' % part if isinstance(part, int) else '.' + part
        return p

    def to_json(self):
        out = {'op': self.op.name}
        for k in sorted(self.values):
            out[k] = to_json(self.values[k])
        return out

def to_json(v):
    if isinstance(v, Step):
        return v.to_json()
    if isinstance(v, list):
        return [to_json(x) for x in v]
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    return v

class Context:
    """Runtime state shared by every step of one execution."""

    def run(self, steps, rows):
        for step in steps:
            rows = step.op.run(step, rows, self)
        return rows

    def eval(self, step, expr, row, *parts):
        """Evaluate one of `step`'s expressions; errors point at step.at(*parts)."""
        path = step.at(*parts)
        return eval_at(parse_expr(expr, path), row, path)

class Op:
    """A step kind: `fields` describe its shape, `run` transforms rows."""
    name = None
    fields = ()

    def normalize(self, raw, path):
        return read_fields(self.fields, raw, path)

    def run(self, step, rows, ctx):
        raise NotImplementedError

OPS = {}


def register(cls):
    """Class decorator: make an Op subclass available to pipelines under its `name`."""
    OPS[cls.name] = cls()
    return cls

class StepList(List):
    """Array of steps: the recursion point that makes nesting free."""

    def __init__(self, key, **kw):
        super().__init__(key, item=None, **kw)

    def normalize(self, value, path):
        if not isinstance(value, list):
            raise schema_error("'%s' must be an array" % self.key, path)
        return [Step.parse(s, '%s[%d]' % (path, i)) for i, s in enumerate(value)]


def from_json(obj, path='pipeline.steps'):
    """Rebuild parsed steps from normalized JSON (the inverse of to_json)."""
    return StepList('steps').normalize(obj, path)


class CountingContext(Context):
    """Context that records how many rows each step saw."""

    def __init__(self):
        self.counts = []

    def run(self, steps, rows):
        for step in steps:
            before = len(rows)
            rows = step.op.run(step, rows, self)
            self.counts.append({'op': step.op.name, 'path': step.path, 'rows_in': before, 'rows_out': len(rows)})
        return rows
