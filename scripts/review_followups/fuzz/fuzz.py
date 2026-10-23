import json, random, copy
random.seed(7)
cases = [json.loads(l) for l in open('/tmp/xlmut/cases.jsonl')]
VALS = [None, 0, 1, -1, 2, 1.5, -2.5, '', ' ', ' x ', 'X', 'a', 'b', 'abc', 'a,b', 'UPPER', 'otherwise', 'concat', 'sum', 'avg',
        'count', 'left', 'right', 'int', 'float', 'string', 'bool', 'true', 'year', 'a > 1', 'x +', '((', 'a ** 2', '[a-z]+', '(',
        '(\\d+)', '2024-05-06', '{"k": 1}', True, False, [], [1], ['a'], ['a', 'b'], [1, 'a'], [{}], [{'a': 1}], {}, {'a': 1}, {'a': 'b'},
        {'a': [1]}, 10**20, 1e300]
def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        yield o
        for v in o: yield from walk(v)
def mutate(req):
    req = copy.deepcopy(req)
    nodes = list(walk(req))
    if not nodes: return req
    for _ in range(random.randint(1, 3)):
        n = random.choice(nodes)
        if isinstance(n, dict) and n:
            k = random.choice(list(n))
            r = random.random()
            if r < 0.2: del n[k]
            elif r < 0.3: n[k.upper() if random.random() < .5 else k + '_'] = n.pop(k)
            else: n[k] = copy.deepcopy(random.choice(VALS))
        elif isinstance(n, list) and n:
            i = random.randrange(len(n)); r = random.random()
            if r < 0.3: del n[i]
            elif r < 0.5: n.append(copy.deepcopy(n[i]))
            else: n[i] = copy.deepcopy(random.choice(VALS))
    return req
out = open('/tmp/xlmut/fuzz.jsonl', 'w')
seen = set()
for c in cases:
    try: req = json.loads(c['stdin'])
    except ValueError: continue
    for _ in range(12):
        m = mutate(req)
        for argv in ([], ['--execute']):
            s = json.dumps({'argv': argv, 'stdin': json.dumps(m)}, sort_keys=True)
            if s not in seen:
                seen.add(s); out.write(s + '\n')
print(len(seen))
