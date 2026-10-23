import json, random, sys
sys.path.insert(0, '/Users/luke/conductor/workspaces/task/islamabad/tasks/etl_pipeline_xl_naive/reference'); sys.dont_write_bytecode = True
import etl.ops  # noqa
from etl.steps import OPS
from etl import fields as F
random.seed(11)
COLS = ['a', 'b', 'c', 'd']
CELL = [None, 0, 1, -3, 2.5, -0.5, 4.0, 10**16, '', 'x', ' Ab ', 'a,b,c', '12', '3.5', 'true', 'FALSE', '2024-01-31', '2024-1-3',
        '{"k": [1, 2]}', '[1', 'hello world', True, False, [], [1, 2], ['p', 'q'], {}, {'k': 1, 'm': 'z'}]
def gen_value(f, depth=0):
    kind = type(f).__name__
    r = random.random()
    if r < 0.12:
        return random.choice([None, 1, -1, 'zz', '', True, [], {}, [1], 2.5])
    if kind in ('Text', 'Label'):
        return random.choice(COLS + ['a', 'b', ' a ', 'new', 'x_', ',', '-', '0', ''])
    if kind == 'Choice':
        return random.choice(list(f.choices) + [f.choices[0].upper(), ' %s ' % f.choices[-1], 'bogus'])
    if kind == 'Expr':
        return random.choice(['a > 1', 'a + b', 'b == "x"', 'a * 2 - c', 'not a', 'a && b || c', '(a', 'a / 0', 'a + "s"', 'c',
                              '-a', '!b', 'a >= 1 and b != null', 'a ** 2', 'true', '"lit"', '1.5 * a', 'otherwise'])
    if kind == 'Flag':
        return random.choice([True, False])
    if kind in ('Count', 'Int'):
        return random.choice([0, 1, 2, 3, 5, -1, 100])
    if kind == 'Number':
        return random.choice([0, 1, -1, 2.5, 10, -7.25, 1e3])
    if kind == 'Scalar':
        return random.choice([None, 0, 'v', 1.5, True])
    if kind == 'Pattern':
        return random.choice(['a', '(\\d+)', '^x', '[', '(a)(b)?', '\\s', '.*'])
    if kind == 'Objects':
        return [random.choice([{'a': 1}, {'b': 'x'}, {}, 3]) for _ in range(random.randint(0, 3))]
    if kind in ('List', 'Branches'):
        return [gen_value(f.item, depth + 1) for _ in range(random.randint(0, 3))]
    if kind == 'Map':
        return {k: gen_value(f.value, depth + 1) for k in random.sample(['a', 'x', '1', 'true', 'null', 'b'], random.randint(0, 3))}
    if kind == 'Record':
        return {sf.key: gen_value(sf, depth + 1) for sf in f.fields if random.random() < 0.85}
    if kind == 'StepList':
        return [gen_step(depth + 1) for _ in range(random.randint(0, 2))] if depth < 3 else []
    if kind == 'MergeStrategy':
        return random.choice(['concat', 'union'])
    return None
def gen_step(depth=0):
    name = random.choice(sorted(OPS))
    op = OPS[name]
    fields = op.fields
    if name == 'rename':
        fields = (F.Map('mapping', F.Label('v')),) if random.random() < .5 else (F.Text('from'), F.Text('to'))
    step = {'op': random.choice([name, name, name.upper(), ' %s ' % name])}
    for f in fields:
        if random.random() < 0.9 or f.required is False and random.random() < 0.5:
            step[f.key] = gen_value(f, depth)
    return step
def gen_row():
    return {c: random.choice(CELL) for c in COLS if random.random() < 0.85}
out = open('/tmp/xlmut/fuzz2.jsonl', 'w')
for _ in range(int(sys.argv[1])):
    req = {'pipeline': {'steps': [gen_step() for _ in range(random.randint(1, 3))]}, 'dataset': [gen_row() for _ in range(random.randint(0, 5))]}
    out.write(json.dumps({'argv': random.choice([[], ['--execute'], ['--execute']]), 'stdin': json.dumps(req)}) + '\n')
