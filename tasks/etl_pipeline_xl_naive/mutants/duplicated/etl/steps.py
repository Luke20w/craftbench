"""Steps, ops and the runtime context. Ops register themselves; see etl/ops/."""

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, eval_at

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
        p = path + '.op'
        if 'op' not in raw:
            raise schema_error("missing required field 'op'", p)
        name = raw['op']
        if not isinstance(name, str):
            raise schema_error("'op' must be a string", p)
        name = name.strip()
        if not name:
            raise schema_error("'op' must not be empty", p)
        name = name.lower()
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
    """A step kind: `normalize` checks a raw step and returns its values, `run` transforms rows."""
    name = None

    def normalize(self, raw, path):
        raise NotImplementedError

    def run(self, step, rows, ctx):
        raise NotImplementedError

OPS = {}


def register(cls):
    """Class decorator: make an Op subclass available to pipelines under its `name`."""
    OPS[cls.name] = cls()
    return cls
