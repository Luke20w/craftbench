"""Steps, ops and the runtime context. Ops register themselves; see etl/ops/."""

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, eval_at
from etl.fields import List, Text, read_fields
from etl import validation

class Step:
    """A normalized step: its op, its field values and the path it was read from."""

    def __init__(self, op, values, path, raw):
        self.op = op
        self.values = values
        self.path = path
        self.raw = raw

    @staticmethod
    def parse(raw, path):
        """Read one step. While collecting (--all-errors) its problems are recorded under its own entry."""
        if validation.REPORT is None:
            return Step.read(raw, path)
        validation.REPORT.start(path)
        try:
            return validation.attempt(Step.read, raw, path)
        finally:
            validation.REPORT.end()

    @staticmethod
    def read(raw, path):
        if not isinstance(raw, dict):
            raise schema_error('step must be an object', path)
        name = Text('op').read(raw, path).lower()
        if name not in OPS:
            raise EtlError('UNKNOWN_OP', "ETL_ERROR: unsupported op '%s'" % name, path + '.op')
        op = OPS[name]
        values = op.normalize(raw, path)
        validation.attempt(validation.check_keys, raw, ['op', *op.keys()], path)
        return Step(op, values, path, raw)

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

    def keys(self):
        """The field names a step of this op accepts (besides `op`)."""
        return [f.key for f in self.fields]

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
