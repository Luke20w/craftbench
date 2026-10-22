"""Steps, ops and the runtime context. Ops register themselves; see etl/ops/."""

from etl.errors import EtlError, schema_error
from etl.expr import parse_expr, eval_at, identifiers
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

ANY = '*'  # columns a step affects without naming them (every other column, or names from the data)


def names(step, keys):
    """Column names held by the step's fields `keys` (a string or an array of strings each); ANY as is."""
    out = []
    for k in keys:
        v = ANY if k == ANY else step.values.get(k)
        out.extend(v if isinstance(v, list) else [] if v is None else [v])
    return out


class Op:
    """A step kind: `fields` describe its shape, `run` transforms rows.

    `reads`, `writes` and `removes` name the fields that hold the columns the step looks at, sets and deletes
    (ANY for columns it can't name); identifiers in the `exprs` fields are read too."""
    name = None
    fields = ()
    reads = writes = removes = exprs = ()

    def columns(self, step):
        """(reads, writes, removes) column names of a normalized step."""
        read = names(step, self.reads) + [i for e in names(step, self.exprs) for i in identifiers(e)]
        return read, names(step, self.writes), names(step, self.removes)

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


def explain_steps(steps):
    """One entry per step at any depth, in the order steps start (a branch before the steps inside it)."""
    out = []
    for step in steps:
        reads, writes, removes = step.op.columns(step)
        out.append({'path': step.path, 'op': step.op.name, 'reads': sorted(set(reads)),
                    'writes': sorted(set(writes)), 'removes': sorted(set(removes))})
        for b in step.values.get('branches', []) if step.op.name == 'branch' else []:
            out.extend(explain_steps(b['steps']))
    return out
