"""Write the golden cases of the big probe changes (tests/big_<id>.json).

Each change is implemented on its own copy of the reference, big_reference/<id>/ (not chained), and its
cases are run against that copy. Every case carries a hand-written `want` (the expected response minus
`message`, or a partial one marked `_partial`), which is checked against the copy before its output is
saved. Rerun after changing a case or a big reference:

    python tasks/etl_pipeline_xl_naive/make_big_tests.py [<id> ...]
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S, BAD, UNK, MAL = 'SCHEMA_VALIDATION_FAILED', 'BAD_EXPR', 'UNKNOWN_OP', 'MALFORMED_STEP'
MISS, EXE = 'MISSING_COLUMN', 'EXECUTION_FAILED'
P = 'pipeline.steps'


def case(id, steps=None, dataset=None, flags=(), want=None, top=None, request=None, raw=None, part=None,
         execute=None):
    """One golden case. `top` adds top-level request keys (options, schema)."""
    if execute is None:
        execute = dataset is not None
    c = {'id': id, 'flags': list(flags) + (['--execute'] if execute else [])}
    if raw is not None:
        c['raw'] = raw
    elif request is not None:
        c['request'] = request
    else:
        c['request'] = {**(top or {}), 'pipeline': {'steps': steps}, 'dataset': dataset or []}
    if part is not None:
        c['part'] = part
    c['want'] = want
    return c


def err(path, code=S):
    return {'status': 'error', 'error_code': code, 'path': path}


def norm(*steps):
    return {'status': 'ok', 'normalized': {'steps': list(steps)}}


def data(rows, rows_in=None):
    return {'status': 'ok', 'data': rows, 'metrics': {'rows_in': len(rows) if rows_in is None else rows_in,
                                                      'rows_out': len(rows)}}


def branch(*branches, **extra):
    return {'op': 'branch', 'branches': list(branches), **extra}


# ---- missing_as_null ---------------------------------------------------------------------------------
def missing_as_null():
    ON = {'options': {'missing_as_null': True}}
    m = lambda id, steps, dataset, want, **kw: case(id, steps, dataset, want=want, top=kw.pop('top', ON), **kw)
    return [
        m('spec-example', [{'op': 'concat', 'as': 'name', 'columns': ['first', 'last'], 'sep': ' '},
                           {'op': 'select', 'columns': ['id', 'name', 'last']}],
          [{'id': 1, 'first': 'Ada', 'last': 'Lovelace'}, {'id': 2, 'first': 'Plato'}],
          data([{'id': 1, 'name': 'Ada Lovelace', 'last': 'Lovelace'}, {'id': 2, 'name': 'Plato ', 'last': None}])),
        m('select', [{'op': 'select', 'columns': ['id', 'x']}], [{'id': 1, 'x': 2}, {'id': 2}],
          data([{'id': 1, 'x': 2}, {'id': 2, 'x': None}])),
        m('rename-from-to', [{'op': 'rename', 'from': 'x', 'to': 'y'}], [{'id': 1, 'x': 5}, {'id': 2}],
          data([{'id': 1, 'y': 5}, {'id': 2, 'y': None}])),
        m('rename-mapping', [{'op': 'rename', 'mapping': {'a': 'b', 'c': 'd'}}], [{'a': 1}, {'c': 2}],
          data([{'b': 1, 'd': None}, {'b': None, 'd': 2}])),
        m('drop', [{'op': 'drop', 'columns': ['x', 'y']}], [{'id': 1, 'x': 2}, {'id': 2, 'y': 3}, {'id': 3}],
          data([{'id': 1}, {'id': 2}, {'id': 3}])),
        m('cast', [{'op': 'cast', 'column': 'x', 'to': 'int'}], [{'x': '7'}, {'id': 2}],
          data([{'x': 7}, {'id': 2, 'x': None}])),
        m('explode', [{'op': 'explode', 'column': 'tags'}], [{'id': 1, 'tags': ['a', 'b']}, {'id': 2}],
          data([{'id': 1, 'tags': 'a'}, {'id': 1, 'tags': 'b'}, {'id': 2, 'tags': None}], rows_in=2)),
        m('lookup-null-key', [{'op': 'lookup', 'column': 'cc', 'as': 'country',
                               'table': {'NO': 'Norway', 'null': 'unknown'}}], [{'cc': 'NO'}, {'id': 2}],
          data([{'cc': 'NO', 'country': 'Norway'}, {'id': 2, 'cc': None, 'country': 'unknown'}])),
        m('lookup-default', [{'op': 'lookup', 'column': 'cc', 'as': 'country', 'table': {'NO': 'Norway'},
                              'default': '?'}], [{'id': 2}],
          data([{'id': 2, 'cc': None, 'country': '?'}])),
        m('reorder', [{'op': 'reorder', 'columns': ['b', 'a']}], [{'a': 1, 'b': 2}, {'a': 3}],
          data([{'b': 2, 'a': 1}, {'b': None, 'a': 3}])),
        m('nest', [{'op': 'nest', 'columns': ['a', 'b'], 'as': 'ab'}], [{'id': 1, 'a': 1}, {'id': 2, 'b': 2}],
          data([{'id': 1, 'ab': {'a': 1, 'b': None}}, {'id': 2, 'ab': {'a': None, 'b': 2}}])),
        m('unnest', [{'op': 'unnest', 'column': 'meta', 'prefix': 'm_'}], [{'id': 1, 'meta': {'k': 1}}, {'id': 2}],
          data([{'id': 1, 'm_k': 1}, {'id': 2}])),
        m('concat-middle', [{'op': 'concat', 'as': 'full', 'columns': ['a', 'b', 'c'], 'sep': '-'}],
          [{'a': 'x', 'c': 3}], data([{'a': 'x', 'c': 3, 'b': None, 'full': 'x--3'}])),
        m('split', [{'op': 'split', 'column': 'name', 'sep': ' ', 'into': ['f', 'l']}], [{'name': 'A B'}, {'id': 2}],
          data([{'name': 'A B', 'f': 'A', 'l': 'B'}, {'id': 2, 'name': None, 'f': None, 'l': None}])),
        m('text', [{'op': 'text', 'columns': ['a', 'b'], 'fn': 'upper'}], [{'a': 'x'}, {'b': 'y'}],
          data([{'a': 'X', 'b': None}, {'a': None, 'b': 'Y'}])),
        m('replace', [{'op': 'replace', 'column': 's', 'find': '-', 'with': '+'}], [{'s': 'a-b'}, {}],
          data([{'s': 'a+b'}, {'s': None}])),
        m('regex_extract', [{'op': 'regex_extract', 'column': 's', 'pattern': '\\d+', 'as': 'n'}],
          [{'s': 'ab12'}, {'id': 1}], data([{'s': 'ab12', 'n': '12'}, {'id': 1, 's': None, 'n': None}])),
        m('substr', [{'op': 'substr', 'column': 's', 'as': 'p', 'start': 1, 'length': 2}], [{'s': 'hello'}, {}],
          data([{'s': 'hello', 'p': 'el'}, {'s': None, 'p': None}])),
        m('pad', [{'op': 'pad', 'column': 'id', 'width': 3, 'fill': '0'}], [{'id': 7}, {'x': 1}],
          data([{'id': '007'}, {'x': 1, 'id': None}])),
        m('length', [{'op': 'length', 'column': 'tags', 'as': 'n'}], [{'tags': [1, 2]}, {}],
          data([{'tags': [1, 2], 'n': 2}, {'tags': None, 'n': None}])),
        m('json_parse', [{'op': 'json_parse', 'column': 'j'}], [{'j': '[1]'}, {}], data([{'j': [1]}, {'j': None}])),
        m('json_dump', [{'op': 'json_dump', 'column': 'j'}], [{'j': {'b': 1}}, {}],
          data([{'j': '{"b": 1}'}, {'j': None}])),
        m('date_part', [{'op': 'date_part', 'column': 'd', 'part': 'year', 'as': 'y'}], [{'d': '2024-01-02'}, {}],
          data([{'d': '2024-01-02', 'y': 2024}, {'d': None, 'y': None}])),
        m('round', [{'op': 'round', 'column': 'x', 'digits': 1}], [{'x': 1.26}, {}], data([{'x': 1.3}, {'x': None}])),
        m('clip', [{'op': 'clip', 'column': 'x', 'max': 10}], [{'x': 50}, {'y': 1}],
          data([{'x': 10}, {'y': 1, 'x': None}])),
        m('scale', [{'op': 'scale', 'column': 'x', 'factor': 2, 'offset': 1}], [{'x': 3}, {}],
          data([{'x': 7}, {'x': None}])),
        m('bucket', [{'op': 'bucket', 'column': 'x', 'as': 'b', 'edges': [10]}], [{'x': 15}, {}],
          data([{'x': 15, 'b': 1}, {'x': None, 'b': None}])),
        m('math', [{'op': 'math', 'column': 'x', 'fn': 'abs'}], [{'x': -2}, {}], data([{'x': 2}, {'x': None}])),
        m('later-step-sees-null', [{'op': 'round', 'column': 'x'}, {'op': 'fill', 'column': 'x', 'value': '0'},
                                   {'op': 'select', 'columns': ['x', 'z']}],
          [{'id': 1}, {'x': 2.6}], data([{'x': 0, 'z': None}, {'x': 3, 'z': None}])),
        m('tolerant-ops-unchanged', [
            {'op': 'between', 'column': 'v', 'low': 0, 'high': 5, 'as': 'in'},
            {'op': 'cumsum', 'column': 'v', 'as': 'run'},
            {'op': 'lag', 'column': 'v', 'as': 'prev'},
            {'op': 'regex_filter', 'column': 's', 'pattern': 'x', 'invert': True},
            {'op': 'sort', 'by': 'k'}],
          [{'v': 3, 'k': 2}, {'id': 1}, {'v': 9, 'k': 1}],
          data([{'v': 9, 'k': 1, 'in': False, 'run': 12, 'prev': None},
                {'v': 3, 'k': 2, 'in': True, 'run': 3, 'prev': None},
                {'id': 1, 'in': False, 'run': 3, 'prev': 3}])),
        m('grouping-unchanged', [{'op': 'group_count', 'by': ['g'], 'as': 'n'}], [{'g': 1}, {'id': 2}, {'g': None}],
          data([{'g': 1, 'n': 1}, {'g': None, 'n': 2}], rows_in=3)),
        m('require-still-fails', [{'op': 'require', 'columns': ['a', 'b']}], [{'a': 1, 'b': 2}, {'a': 1}],
          err(P + '[0].columns[1]', EXE)),
        m('type-error-still-reported', [{'op': 'cast', 'column': 'x', 'to': 'int'}], [{}, {'x': 'abc'}],
          err(P + '[0].column', EXE)),
        m('type-error-in-listed-column', [{'op': 'text', 'columns': ['a', 'b'], 'fn': 'lower'}], [{'b': 'X'}, {'a': 5}],
          err(P + '[0].columns[0]', EXE)),
        m('in-branch', [branch({'when': 'k == 1', 'steps': [{'op': 'cast', 'column': 'x', 'to': 'string'}]},
                               {'when': 'otherwise', 'steps': [{'op': 'length', 'column': 'x', 'as': 'n'}]})],
          [{'k': 1}, {'k': 2}, {'k': 1, 'x': 5}],
          data([{'k': 1, 'x': None}, {'k': 1, 'x': '5'}, {'k': 2, 'x': None, 'n': None}])),
        m('nested-branch', [branch({'when': 'true', 'steps': [
            branch({'when': 'otherwise', 'steps': [{'op': 'nest', 'columns': ['a'], 'as': 'o'}]})]})],
          [{'id': 1}], data([{'id': 1, 'o': {'a': None}}])),
        m('option-false-unchanged', [{'op': 'select', 'columns': ['x']}], [{'id': 1}], err(P + '[0].columns[0]', MISS),
          top={'options': {'missing_as_null': False}}),
        m('option-absent-unchanged', [{'op': 'round', 'column': 'x'}], [{'id': 1}], err(P + '[0].column', MISS),
          top={'options': {}}),
        m('unknown-option-keys-ignored', [{'op': 'scale', 'column': 'x', 'factor': 3}], [{'id': 1}, {'x': 2}],
          data([{'id': 1, 'x': None}, {'x': 6}]), top={'options': {'speed': 'fast', 'missing_as_null': True}}),
        m('normalize-unchanged', [{'op': ' Cast ', 'column': ' x ', 'to': 'INT'}], None,
          norm({'op': 'cast', 'column': 'x', 'to': 'int'})),
        m('options-not-object', [{'op': 'limit', 'n': 1}], [], err('options'), top={'options': ['missing_as_null']}),
        m('options-null', [], None, err('options'), top={'options': None}),
        m('flag-not-boolean', [{'op': 'limit', 'n': 1}], [{'a': 1}], err('options.missing_as_null'),
          top={'options': {'missing_as_null': 'yes'}}),
        m('flag-number-without-execute', [{'op': 'limit', 'n': 1}], None, err('options.missing_as_null'),
          top={'options': {'missing_as_null': 1}}),
        m('options-before-steps', [{'op': 'nope'}, {'op': 'limit', 'n': -1}], None, err('options.missing_as_null'),
          top={'options': {'missing_as_null': None}}),
        m('dataset-before-options', None, None, err('dataset[0]'),
          request={'options': 5, 'pipeline': {'steps': []}, 'dataset': [3]}),
    ]

# ---- explain -------------------------------------------------------------------------------------------
def explain():
    X = ['--explain']

    def ent(path, op, reads=(), writes=(), removes=()):
        return {'path': path, 'op': op, 'reads': list(reads), 'writes': list(writes), 'removes': list(removes)}

    def ex(id, step, reads=(), writes=(), removes=()):
        """One step at the top level; its single entry."""
        return case(id, [step], flags=X, want={'status': 'ok', 'explain': [ent(P + '[0]', step['op'], reads, writes, removes)]})

    def exs(id, steps, entries, **kw):
        return case(id, steps, flags=kw.pop('flags', X), want={'status': 'ok', 'explain': entries}, **kw)

    return [
        exs('spec-example', [{'op': 'filter', 'where': 'qty > 0'}, {'op': 'map', 'as': 'total', 'expr': 'price * qty'},
                             {'op': 'rename', 'from': 'total', 'to': 'amount'},
                             {'op': 'group_count', 'by': ['city'], 'as': 'orders'}],
            [ent(P + '[0]', 'filter', ['qty']), ent(P + '[1]', 'map', ['price', 'qty'], ['total']),
             ent(P + '[2]', 'rename', ['total'], ['amount'], ['total']),
             ent(P + '[3]', 'group_count', ['city'], ['orders'], ['*'])]),
        ex('select', {'op': 'select', 'columns': ['b', 'a', 'b']}, ['a', 'b'], [], ['*']),
        ex('filter', {'op': 'filter', 'where': 'price > 10 and name != "x y"'}, ['name', 'price']),
        ex('filter-literals-and-keywords', {'op': 'filter', 'where': 'not done or (count == null && flag != true)'},
           ['count', 'done', 'flag']),
        ex('map', {'op': 'map', 'as': 'total', 'expr': 'price * qty'}, ['price', 'qty'], ['total']),
        ex('map-reads-own-column', {'op': 'map', 'as': 'n', 'expr': 'n + 1'}, ['n'], ['n']),
        ex('map-constant', {'op': 'map', 'as': 'tag', 'expr': '"cheap"'}, [], ['tag']),
        ex('rename-from-to', {'op': 'rename', 'from': 'a', 'to': 'b'}, ['a'], ['b'], ['a']),
        ex('rename-mapping', {'op': 'rename', 'mapping': {'x': 'y', 'p': 'q'}}, ['p', 'x'], ['q', 'y'], ['p', 'x']),
        ex('drop', {'op': 'drop', 'columns': ['c', 'a']}, ['a', 'c'], [], ['a', 'c']),
        ex('fill', {'op': 'fill', 'column': 'x', 'value': 'y * 2'}, ['x', 'y'], ['x']),
        ex('cast', {'op': 'cast', 'column': 'x', 'to': 'int'}, ['x'], ['x']),
        ex('coalesce', {'op': 'coalesce', 'as': 'c', 'exprs': ['a', 'b + 1', '0']}, ['a', 'b'], ['c']),
        ex('explode', {'op': 'explode', 'column': 'tags'}, ['tags'], ['tags']),
        ex('lookup', {'op': 'lookup', 'column': 'cc', 'as': 'country', 'table': {'NO': 'Norway'}, 'default': '?'},
           ['cc'], ['country']),
        ex('set', {'op': 'set', 'column': 'flag', 'value': 1}, [], ['flag']),
        ex('ensure', {'op': 'ensure', 'columns': ['b', 'a']}, ['a', 'b'], ['a', 'b']),
        ex('reorder', {'op': 'reorder', 'columns': ['b', 'a']}, ['a', 'b']),
        ex('prefix-listed', {'op': 'prefix', 'prefix': 'p_', 'columns': ['b', 'a']}, ['a', 'b'], ['p_a', 'p_b'],
           ['a', 'b']),
        ex('prefix-all', {'op': 'prefix', 'prefix': 'p_'}, ['*'], ['*'], ['*']),
        ex('nest', {'op': 'nest', 'columns': ['b', 'a'], 'as': 'ab'}, ['a', 'b'], ['ab'], ['a', 'b']),
        ex('unnest', {'op': 'unnest', 'column': 'meta', 'prefix': 'm_'}, ['meta'], ['*'], ['meta']),
        ex('concat', {'op': 'concat', 'as': 'full', 'columns': ['last', 'first'], 'sep': ' '}, ['first', 'last'],
           ['full']),
        ex('split', {'op': 'split', 'column': 'name', 'sep': ' ', 'into': ['l', 'f']}, ['name'], ['f', 'l']),
        ex('text', {'op': 'text', 'columns': ['b', 'a'], 'fn': 'upper'}, ['a', 'b'], ['a', 'b']),
        ex('replace', {'op': 'replace', 'column': 's', 'find': '-', 'with': ''}, ['s'], ['s']),
        ex('regex_extract', {'op': 'regex_extract', 'column': 's', 'pattern': '(\\d+)', 'as': 'n', 'group': 1},
           ['s'], ['n']),
        ex('regex_filter', {'op': 'regex_filter', 'column': 's', 'pattern': 'x', 'invert': True}, ['s']),
        ex('substr', {'op': 'substr', 'column': 's', 'as': 'p', 'start': 0, 'length': 2}, ['s'], ['p']),
        ex('pad', {'op': 'pad', 'column': 'id', 'width': 3}, ['id'], ['id']),
        ex('length', {'op': 'length', 'column': 'tags', 'as': 'n'}, ['tags'], ['n']),
        ex('json_parse', {'op': 'json_parse', 'column': 'j'}, ['j'], ['j']),
        ex('json_dump', {'op': 'json_dump', 'column': 'j'}, ['j'], ['j']),
        ex('date_part', {'op': 'date_part', 'column': 'd', 'part': 'year', 'as': 'y'}, ['d'], ['y']),
        ex('round', {'op': 'round', 'column': 'x', 'digits': 2}, ['x'], ['x']),
        ex('clip', {'op': 'clip', 'column': 'x', 'min': 0}, ['x'], ['x']),
        ex('scale', {'op': 'scale', 'column': 'x', 'factor': 2}, ['x'], ['x']),
        ex('math', {'op': 'math', 'column': 'x', 'fn': 'sqrt'}, ['x'], ['x']),
        ex('bucket', {'op': 'bucket', 'column': 'x', 'as': 'b', 'edges': [1, 5]}, ['x'], ['b']),
        ex('between', {'op': 'between', 'column': 'x', 'low': 0, 'high': 9, 'as': 'ok'}, ['x'], ['ok']),
        ex('group_count', {'op': 'group_count', 'by': ['h', 'g'], 'as': 'n'}, ['g', 'h'], ['n'], ['*']),
        ex('summarize', {'op': 'summarize', 'by': ['g'], 'metrics': [
            {'as': 'n', 'fn': 'count'}, {'as': 't', 'fn': 'sum', 'column': 'v'}, {'as': 'm', 'fn': 'max', 'column': 'w'}]},
           ['g', 'v', 'w'], ['m', 'n', 't'], ['*']),
        ex('summarize-no-by', {'op': 'summarize', 'metrics': [{'as': 'n', 'fn': 'count'}]}, [], ['n'], ['*']),
        ex('distinct-listed', {'op': 'distinct', 'columns': ['b', 'a']}, ['a', 'b']),
        ex('distinct-whole-row', {'op': 'distinct'}, ['*']),
        ex('sort', {'op': 'sort', 'by': 'k', 'desc': True}, ['k']),
        ex('assert', {'op': 'assert', 'where': 'qty > min_qty', 'message': 'too few'}, ['min_qty', 'qty']),
        ex('take_while', {'op': 'take_while', 'where': 'a < 3'}, ['a']),
        ex('skip_while', {'op': 'skip_while', 'where': '!b'}, ['b']),
        ex('require', {'op': 'require', 'columns': ['b', 'a']}, ['a', 'b']),
        ex('row_number', {'op': 'row_number', 'as': 'r', 'start': 0}, [], ['r']),
        ex('rank', {'op': 'rank', 'by': 'score', 'as': 'place'}, ['score'], ['place']),
        ex('cumsum', {'op': 'cumsum', 'column': 'v', 'as': 'run'}, ['v'], ['run']),
        ex('lag', {'op': 'lag', 'column': 'v', 'as': 'prev', 'n': 2, 'default': 0}, ['v'], ['prev']),
        exs('row-only-ops', [{'op': 'limit', 'n': 1}, {'op': 'offset', 'n': 1}, {'op': 'tail', 'n': 1},
                             {'op': 'sample_every', 'n': 2}, {'op': 'append', 'rows': [{'a': 1}]}],
            [ent(P + '[0]', 'limit'), ent(P + '[1]', 'offset'), ent(P + '[2]', 'tail'), ent(P + '[3]', 'sample_every'),
             ent(P + '[4]', 'append')]),
        exs('normalized-names', [{'op': ' Map ', 'as': ' total ', 'expr': ' a '},
                                 {'op': 'lookup', 'column': ' cc ', 'as': ' c ', 'table': {}}],
            [ent(P + '[0]', 'map', ['a'], ['total']), ent(P + '[1]', 'lookup', ['cc'], ['c'])]),
        exs('branch', [branch({'when': 'x > 1 and kind == "a"', 'steps': [{'op': 'set', 'column': 'big', 'value': True}]},
                              {'when': 'y', 'steps': []},
                              {'when': 'otherwise', 'steps': [{'op': 'drop', 'columns': ['z']},
                                                              {'op': 'limit', 'n': 1}]}),
                       {'op': 'cast', 'column': 'x', 'to': 'string'}],
            [ent(P + '[0]', 'branch', ['kind', 'x', 'y']),
             ent(P + '[0].branches[0].steps[0]', 'set', [], ['big']),
             ent(P + '[0].branches[2].steps[0]', 'drop', ['z'], [], ['z']),
             ent(P + '[0].branches[2].steps[1]', 'limit'),
             ent(P + '[1]', 'cast', ['x'], ['x'])]),
        exs('nested-branch', [branch({'when': 'otherwise', 'steps': [
            {'op': 'map', 'as': 'a', 'expr': 'b'},
            branch({'when': 'c', 'steps': [{'op': 'nest', 'columns': ['a'], 'as': 'o'}]}),
            {'op': 'row_number', 'as': 'r'}]})],
            [ent(P + '[0]', 'branch'), ent(P + '[0].branches[0].steps[0]', 'map', ['b'], ['a']),
             ent(P + '[0].branches[0].steps[1]', 'branch', ['c']),
             ent(P + '[0].branches[0].steps[1].branches[0].steps[0]', 'nest', ['a'], ['o'], ['a']),
             ent(P + '[0].branches[0].steps[2]', 'row_number', [], ['r'])]),
        exs('not-run-with-execute', [{'op': 'select', 'columns': ['missing']}, {'op': 'assert', 'where': 'false'}],
            [ent(P + '[0]', 'select', ['missing'], [], ['*']), ent(P + '[1]', 'assert')],
            dataset=[{'a': 1}], flags=X + ['--execute'], execute=False),
        exs('empty-pipeline', [], []),
        case('validation-error-unchanged', [{'op': 'select', 'columns': ['a']}, {'op': 'map', 'as': 'x'}], flags=X,
             want=err(P + '[1].expr')),
        case('bad-expression-unchanged', [{'op': 'filter', 'where': 'a >'}], flags=X, want=err(P + '[0].where', BAD)),
        case('unknown-op-in-branch-unchanged', [branch({'when': 'otherwise', 'steps': [{'op': 'pivot'}]})], flags=X,
             want=err(P + '[0].branches[0].steps[0].op', UNK)),
        case('request-error-unchanged', None, flags=X, want=err('dataset'),
             request={'pipeline': {'steps': []}, 'dataset': {}}),
        case('without-flag-unchanged', [{'op': 'Set', 'column': 'a', 'value': 1}],
             want=norm({'op': 'set', 'column': 'a', 'value': 1})),
    ]

# ---- ignore_case_columns -------------------------------------------------------------------------------
def ignore_case_columns():
    ON = {'options': {'ignore_case_columns': True}}

    def ic(id, steps, dataset, want, **kw):
        steps = steps if isinstance(steps, list) else [steps]
        return case(id, steps, dataset, want=want, top=kw.pop('top', ON), **kw)

    return [
        ic('spec-example', [{'op': 'map', 'as': 'Total', 'expr': 'PRICE * Qty'}, {'op': 'select', 'columns': ['ID', 'total']}],
           [{'id': 1, 'price': 2, 'qty': 3}], data([{'id': 1, 'Total': 6}])),
        ic('select', {'op': 'select', 'columns': ['Name']}, [{'name': 'a', 'x': 1}], data([{'name': 'a'}])),
        ic('select-exact-spelling-wins', {'op': 'select', 'columns': ['A']}, [{'a': 1, 'A': 2}], data([{'A': 2}])),
        ic('select-first-match-in-row', {'op': 'select', 'columns': ['ab']}, [{'Ab': 1, 'aB': 2}], data([{'Ab': 1}])),
        ic('select-missing-still-missing', {'op': 'select', 'columns': ['id', 'zz']}, [{'ID': 1}],
           err(P + '[0].columns[1]', MISS)),
        ic('filter', {'op': 'filter', 'where': 'Price > 1'}, [{'price': 2}, {'PRICE': 0}, {'x': 5}],
           data([{'price': 2}], rows_in=3)),
        ic('expression-exact-spelling-wins', {'op': 'filter', 'where': 'a == 1'}, [{'A': 1, 'a': 2}, {'A': 1}],
           data([{'A': 1}], rows_in=2)),
        ic('map-overwrites', {'op': 'map', 'as': 'TOTAL', 'expr': 'total + 1'}, [{'total': 1}], data([{'total': 2}])),
        ic('rename-fixes-case', {'op': 'rename', 'from': 'NAME', 'to': 'Name'}, [{'name': 'x', 'id': 1}],
           data([{'Name': 'x', 'id': 1}])),
        ic('rename-replaces-matching-target', {'op': 'rename', 'mapping': {'a': 'b'}}, [{'a': 1, 'B': 2}],
           data([{'b': 1}])),
        ic('drop', {'op': 'drop', 'columns': ['X']}, [{'x': 1, 'y': 2}], data([{'y': 2}])),
        ic('fill', {'op': 'fill', 'column': 'Score', 'value': '0'}, [{'score': None}, {'score': 5}],
           data([{'score': 0}, {'score': 5}])),
        ic('cast', {'op': 'cast', 'column': 'AMOUNT', 'to': 'int'}, [{'amount': '12'}], data([{'amount': 12}])),
        ic('coalesce', {'op': 'coalesce', 'as': 'Best', 'exprs': ['A', 'b']}, [{'a': None, 'B': 2, 'best': 0}],
           data([{'a': None, 'B': 2, 'best': 2}])),
        ic('explode', {'op': 'explode', 'column': 'Tags'}, [{'tags': [1, 2]}], data([{'tags': 1}, {'tags': 2}], rows_in=1)),
        ic('lookup', {'op': 'lookup', 'column': 'CC', 'as': 'Country', 'table': {'NO': 'Norway'}},
           [{'cc': 'NO', 'country': '?'}], data([{'cc': 'NO', 'country': 'Norway'}])),
        ic('set', {'op': 'set', 'column': 'Flag', 'value': True}, [{'flag': False}, {'x': 1}],
           data([{'flag': True}, {'x': 1, 'Flag': True}])),
        ic('ensure', {'op': 'ensure', 'columns': ['Region', 'city'], 'value': 'n/a'}, [{'region': 'EU'}],
           data([{'region': 'EU', 'city': 'n/a'}])),
        ic('reorder', {'op': 'reorder', 'columns': ['B']}, [{'a': 1, 'b': 2}], data([{'b': 2, 'a': 1}])),
        ic('prefix', {'op': 'prefix', 'prefix': 'p_', 'columns': ['A']}, [{'a': 1, 'b': 2}], data([{'p_a': 1, 'b': 2}])),
        ic('nest', {'op': 'nest', 'columns': ['X', 'y'], 'as': 'Pt'}, [{'x': 1, 'Y': 2, 'id': 1}],
           data([{'id': 1, 'Pt': {'x': 1, 'Y': 2}}])),
        ic('unnest', {'op': 'unnest', 'column': 'Meta'}, [{'meta': {'k': 1}, 'id': 1}], data([{'id': 1, 'k': 1}])),
        ic('unnest-data-keys-exact', {'op': 'unnest', 'column': 'm'}, [{'m': {'ID': 1}, 'id': 0}],
           data([{'id': 0, 'ID': 1}])),
        ic('concat', {'op': 'concat', 'as': 'Full', 'columns': ['First', 'LAST'], 'sep': ' '},
           [{'first': 'A', 'last': 'B', 'full': ''}], data([{'first': 'A', 'last': 'B', 'full': 'A B'}])),
        ic('split', {'op': 'split', 'column': 'Name', 'sep': ' ', 'into': ['First', 'last']}, [{'name': 'A B', 'first': '?'}],
           data([{'name': 'A B', 'first': 'A', 'last': 'B'}])),
        ic('text', {'op': 'text', 'columns': ['CODE'], 'fn': 'lower'}, [{'code': 'AB'}], data([{'code': 'ab'}])),
        ic('replace', {'op': 'replace', 'column': 'S', 'find': '-', 'with': ''}, [{'s': 'a-b'}], data([{'s': 'ab'}])),
        ic('regex_extract', {'op': 'regex_extract', 'column': 'S', 'pattern': '\\d+', 'as': 'N'}, [{'s': 'x12', 'n': None}],
           data([{'s': 'x12', 'n': '12'}])),
        ic('regex_filter', {'op': 'regex_filter', 'column': 'S', 'pattern': '^a'}, [{'s': 'abc'}, {'s': 'b'}],
           data([{'s': 'abc'}], rows_in=2)),
        ic('substr', {'op': 'substr', 'column': 'S', 'as': 'P', 'start': 1}, [{'s': 'abc'}], data([{'s': 'abc', 'P': 'bc'}])),
        ic('pad', {'op': 'pad', 'column': 'ID', 'width': 3, 'fill': '0'}, [{'id': 7}], data([{'id': '007'}])),
        ic('length', {'op': 'length', 'column': 'Tags', 'as': 'n'}, [{'tags': [1, 2]}], data([{'tags': [1, 2], 'n': 2}])),
        ic('json_parse', {'op': 'json_parse', 'column': 'J'}, [{'j': '{"a": 1}'}], data([{'j': {'a': 1}}])),
        ic('json_dump', {'op': 'json_dump', 'column': 'J'}, [{'j': [1]}], data([{'j': '[1]'}])),
        ic('date_part', {'op': 'date_part', 'column': 'Day', 'part': 'month', 'as': 'M'}, [{'day': '2024-03-01', 'm': 0}],
           data([{'day': '2024-03-01', 'm': 3}])),
        ic('round', {'op': 'round', 'column': 'X'}, [{'x': 2.5}], data([{'x': 2}])),
        ic('clip', {'op': 'clip', 'column': 'X', 'min': 0}, [{'x': -1}], data([{'x': 0}])),
        ic('scale', {'op': 'scale', 'column': 'X', 'factor': 10}, [{'x': 2}], data([{'x': 20}])),
        ic('bucket', {'op': 'bucket', 'column': 'X', 'as': 'B', 'edges': [1, 10]}, [{'x': 5}], data([{'x': 5, 'B': 1}])),
        ic('math', {'op': 'math', 'column': 'X', 'fn': 'neg'}, [{'x': 3}], data([{'x': -3}])),
        ic('between', {'op': 'between', 'column': 'X', 'low': 0, 'high': 9, 'as': 'In'}, [{'x': 5}, {'y': 1}],
           data([{'x': 5, 'In': True}, {'y': 1, 'In': False}])),
        ic('group_count', {'op': 'group_count', 'by': ['City'], 'as': 'n'}, [{'city': 'Oslo'}, {'CITY': 'Oslo'}, {'city': 'Rome'}],
           data([{'city': 'Oslo', 'n': 2}, {'city': 'Rome', 'n': 1}], rows_in=3)),
        ic('summarize', {'op': 'summarize', 'by': ['G'], 'metrics': [{'as': 'total', 'fn': 'sum', 'column': 'V'},
                                                                      {'as': 'n', 'fn': 'count', 'column': 'v'}]},
           [{'g': 1, 'v': 2}, {'G': 1, 'V': 3}, {'g': 1}], data([{'g': 1, 'total': 5, 'n': 2}], rows_in=3)),
        ic('distinct', {'op': 'distinct', 'columns': ['K']}, [{'k': 1, 'i': 1}, {'K': 1, 'i': 2}, {'k': 2, 'i': 3}],
           data([{'k': 1, 'i': 1}, {'k': 2, 'i': 3}], rows_in=3)),
        ic('distinct-whole-rows-exact', {'op': 'distinct'}, [{'a': 1}, {'A': 1}, {'a': 1}],
           data([{'a': 1}, {'A': 1}], rows_in=3)),
        ic('sort', {'op': 'sort', 'by': 'Score'}, [{'score': 2}, {'SCORE': 1}, {'x': 0}],
           data([{'SCORE': 1}, {'score': 2}, {'x': 0}])),
        ic('assert', {'op': 'assert', 'where': 'Qty > 0'}, [{'qty': 1}, {'QTY': 2}], data([{'qty': 1}, {'QTY': 2}])),
        ic('take_while', {'op': 'take_while', 'where': 'A < 3'}, [{'a': 1}, {'a': 5}, {'a': 1}], data([{'a': 1}], rows_in=3)),
        ic('skip_while', {'op': 'skip_while', 'where': 'A < 3'}, [{'a': 1}, {'a': 5}, {'a': 1}],
           data([{'a': 5}, {'a': 1}], rows_in=3)),
        ic('require', {'op': 'require', 'columns': ['Name']}, [{'name': 'x'}, {'NAME': 'y'}], data([{'name': 'x'}, {'NAME': 'y'}])),
        ic('row_number', {'op': 'row_number', 'as': 'N'}, [{'n': 0}, {'x': 1}], data([{'n': 1}, {'x': 1, 'N': 2}])),
        ic('rank', {'op': 'rank', 'by': 'S', 'as': 'R'}, [{'s': 5}, {'s': 3}], data([{'s': 5, 'R': 2}, {'s': 3, 'R': 1}])),
        ic('cumsum', {'op': 'cumsum', 'column': 'V', 'as': 'Run'}, [{'v': 1, 'run': 0}, {'v': 2}],
           data([{'v': 1, 'run': 1}, {'v': 2, 'Run': 3}])),
        ic('lag', {'op': 'lag', 'column': 'V', 'as': 'prev'}, [{'v': 1}, {'V': 2}],
           data([{'v': 1, 'prev': None}, {'V': 2, 'prev': 1}])),
        ic('in-branch', [branch({'when': 'Kind == "a"', 'steps': [{'op': 'map', 'as': 'Y', 'expr': 'X + 1'}]},
                                {'when': 'otherwise', 'steps': [branch({'when': 'X > 0', 'steps': [
                                    {'op': 'math', 'column': 'X', 'fn': 'neg'}]})]})],
           [{'kind': 'a', 'x': 1}, {'KIND': 'b', 'x': 2}], data([{'kind': 'a', 'x': 1, 'Y': 2}, {'KIND': 'b', 'x': -2}])),
        ic('execution-error-path-unchanged', {'op': 'cast', 'column': 'X', 'to': 'int'}, [{'x': 'abc'}],
           err(P + '[0].column', EXE)),
        ic('missing-in-some-rows', {'op': 'round', 'column': 'X'}, [{'x': 1.4}, {'y': 1}], err(P + '[0].column', MISS)),
        ic('option-false-unchanged', {'op': 'select', 'columns': ['Name']}, [{'name': 1}], err(P + '[0].columns[0]', MISS),
           top={'options': {'ignore_case_columns': False}}),
        ic('normalize-keeps-spelling', {'op': 'select', 'columns': ['Name', ' ID ']}, None,
           norm({'op': 'select', 'columns': ['Name', ' ID ']})),
        ic('options-not-object', {'op': 'limit', 'n': 1}, [], err('options'), top={'options': 'ignore_case_columns'}),
        ic('flag-not-boolean', {'op': 'limit', 'n': 1}, None, err('options.ignore_case_columns'),
           top={'options': {'ignore_case_columns': 'true'}}),
        ic('options-before-steps', {'op': 'nope'}, [], err('options.ignore_case_columns'),
           top={'options': {'ignore_case_columns': 0}}),
    ]

# ---- column_types --------------------------------------------------------------------------------------
def column_types():
    TM = 'TYPE_MISMATCH'
    SCHEMA = {'s': 's', 'n': 'n', 'b': 'b', 'a': 'a', 'o': 'o', 'z': 's'}
    SCHEMA = {k: {'s': 'string', 'n': 'number', 'b': 'boolean', 'a': 'array', 'o': 'object'}[v] for k, v in SCHEMA.items()}
    TAIL = {'op': 'math', 'column': 'z', 'fn': 'abs'}  # always a mismatch: z is a string nobody touches

    def ct(id, steps, want, schema=SCHEMA, **kw):
        return case(id, steps, kw.pop('dataset', None), want=want, top={'schema': schema}, **kw)

    def bad(id, step, field='column', schema=SCHEMA):
        """A single step that can't handle the declared type of its column."""
        return ct(id, [{'op': 'limit', 'n': 1}, step], err(P + '[1].' + field, TM), schema)

    def fine(id, steps, schema=SCHEMA):
        """Steps that are fine, followed by TAIL: the error is at TAIL, so nothing before it was rejected."""
        return ct(id, steps + [TAIL], err(P + '[%d].column' % len(steps), TM), schema)

    br = lambda *bs: branch(*[{'when': w, 'steps': st} for w, st in bs])
    return [
        ct('spec-example', [{'op': 'round', 'column': 'qty'}, {'op': 'cast', 'column': 'price', 'to': 'float'},
                            {'op': 'between', 'column': 'price', 'low': 0, 'high': 10, 'as': 'cheap'},
                            {'op': 'text', 'columns': ['qty'], 'fn': 'upper'}, {'op': 'length', 'column': 'price', 'as': 'n'}],
           err(P + '[4].column', TM), schema={'price': 'string', 'qty': 'number'}),
        bad('round-string', {'op': 'round', 'column': 's'}),
        bad('clip-boolean', {'op': 'clip', 'column': 'b', 'max': 1}),
        bad('scale-array', {'op': 'scale', 'column': 'a', 'factor': 2}),
        bad('bucket-object', {'op': 'bucket', 'column': 'o', 'as': 'k', 'edges': [1]}),
        bad('math-string', {'op': 'math', 'column': 's', 'fn': 'floor'}),
        bad('between-string', {'op': 'between', 'column': 's', 'low': 0, 'high': 1, 'as': 'x'}),
        bad('cumsum-boolean', {'op': 'cumsum', 'column': 'b', 'as': 'run'}),
        bad('rank-string', {'op': 'rank', 'by': 's', 'as': 'r'}, 'by'),
        bad('sort-array', {'op': 'sort', 'by': 'a'}, 'by'),
        bad('sort-object', {'op': 'sort', 'by': 'o', 'desc': True}, 'by'),
        bad('split-number', {'op': 'split', 'column': 'n', 'sep': ',', 'into': ['x']}),
        bad('text-second-column', {'op': 'text', 'columns': ['s', 'n', 'b'], 'fn': 'upper'}, 'columns[1]'),
        bad('replace-array', {'op': 'replace', 'column': 'a', 'find': 'x', 'with': 'y'}),
        bad('regex_extract-number', {'op': 'regex_extract', 'column': 'n', 'pattern': 'x', 'as': 'm'}),
        bad('substr-boolean', {'op': 'substr', 'column': 'b', 'as': 'p', 'start': 0}),
        bad('length-number', {'op': 'length', 'column': 'n', 'as': 'len'}),
        bad('json_parse-object', {'op': 'json_parse', 'column': 'o'}),
        bad('date_part-number', {'op': 'date_part', 'column': 'n', 'part': 'day', 'as': 'd'}),
        bad('unnest-array', {'op': 'unnest', 'column': 'a'}),
        bad('unnest-string', {'op': 'unnest', 'column': 's', 'prefix': 'p'}),
        bad('cast-int-boolean', {'op': 'cast', 'column': 'b', 'to': 'int'}),
        bad('cast-float-array', {'op': 'cast', 'column': 'a', 'to': 'float'}),
        bad('cast-bool-object', {'op': 'cast', 'column': 'o', 'to': 'bool'}),
        bad('summarize-sum-string', {'op': 'summarize', 'by': ['s'], 'metrics': [
            {'as': 'c', 'fn': 'count', 'column': 's'}, {'as': 't', 'fn': 'sum', 'column': 's'}]}, 'metrics[1].column'),
        bad('summarize-avg-boolean', {'op': 'summarize', 'metrics': [{'as': 'm', 'fn': 'avg', 'column': 'b'}]},
            'metrics[0].column'),
        fine('any-type-column-ops', [
            {'op': 'explode', 'column': 'n'}, {'op': 'lookup', 'column': 'a', 'as': 'l1', 'table': {}},
            {'op': 'pad', 'column': 'b', 'width': 3}, {'op': 'json_dump', 'column': 'o'},
            {'op': 'concat', 'as': 'c1', 'columns': ['s', 'n', 'b', 'a', 'o']}]),
        fine('any-type-row-ops', [
            {'op': 'select', 'columns': ['s', 'n', 'b', 'a', 'o', 'z']}, {'op': 'distinct', 'columns': ['a', 'o']},
            {'op': 'require', 'columns': ['n', 'b']}, {'op': 'lag', 'column': 'o', 'as': 'prev'},
            {'op': 'regex_filter', 'column': 'n', 'pattern': 'x'}, {'op': 'reorder', 'columns': ['o', 'a']},
            {'op': 'drop', 'columns': ['b']}]),
        fine('types-each-op-handles', [
            {'op': 'length', 'column': 'a', 'as': 'l1'}, {'op': 'length', 'column': 'o', 'as': 'l2'},
            {'op': 'length', 'column': 's', 'as': 'l3'}, {'op': 'sort', 'by': 'b'}, {'op': 'sort', 'by': 's'},
            {'op': 'between', 'column': 'n', 'low': 0, 'high': 1, 'as': 'x'}, {'op': 'rank', 'by': 'n', 'as': 'r'},
            {'op': 'regex_extract', 'column': 's', 'pattern': 'x', 'as': 'm'}]),
        fine('summarize-metric-types', [{'op': 'summarize', 'by': ['z', 'a'], 'metrics': [
            {'as': 'c', 'fn': 'count', 'column': 'o'}, {'as': 'mx', 'fn': 'max', 'column': 'n'},
            {'as': 'c2', 'fn': 'count'}, {'as': 'mn', 'fn': 'min', 'column': 'undeclared'}]}]),
        fine('cast-sources-it-can-convert', [
            {'op': 'cast', 'column': 's', 'to': 'int'}, {'op': 'cast', 'column': 'n', 'to': 'bool'},
            {'op': 'cast', 'column': 'a', 'to': 'string'}, {'op': 'cast', 'column': 'o', 'to': 'string'},
            {'op': 'cast', 'column': 'b', 'to': 'bool'}]),
        fine('expressions-not-checked', [
            {'op': 'filter', 'where': 's * 2 > o'}, {'op': 'map', 'as': 'x', 'expr': 'a + b'},
            {'op': 'coalesce', 'as': 'y', 'exprs': ['-s']}, {'op': 'assert', 'where': 'o'}]),
        fine('undeclared-columns-not-checked', [{'op': 'round', 'column': 'other'}, {'op': 'text', 'columns': ['x'], 'fn': 'upper'}]),
        ct('cast-gives-type', [{'op': 'cast', 'column': 's', 'to': 'int'}, {'op': 'bucket', 'column': 's', 'as': 'k', 'edges': [1]},
                               {'op': 'text', 'columns': ['s'], 'fn': 'lower'}], err(P + '[2].columns[0]', TM)),
        ct('cast-types-undeclared-column', [{'op': 'cast', 'column': 'x', 'to': 'bool'}, {'op': 'sort', 'by': 'x'},
                                            {'op': 'round', 'column': 'x'}], err(P + '[2].column', TM)),
        ct('cast-to-string', [{'op': 'cast', 'column': 'n', 'to': 'string'}, {'op': 'split', 'column': 'n', 'sep': ',',
                                                                                 'into': ['p']},
                              {'op': 'scale', 'column': 'n', 'factor': 2}], err(P + '[2].column', TM)),
        fine('map-overwrites', [{'op': 'map', 'as': 's', 'expr': '1'}, {'op': 'round', 'column': 's'}]),
        fine('in-place-change', [{'op': 'replace', 'column': 's', 'find': 'a', 'with': 'b'}, {'op': 'round', 'column': 's'}]),
        fine('fill-writes', [{'op': 'fill', 'column': 'n', 'value': '"x"'}, {'op': 'text', 'columns': ['n'], 'fn': 'trim'}]),
        fine('set-writes', [{'op': 'set', 'column': 'b', 'value': 'x'}, {'op': 'json_parse', 'column': 'b'}]),
        fine('lookup-writes-as', [{'op': 'lookup', 'column': 's', 'as': 'n', 'table': {}}, {'op': 'split', 'column': 'n',
                                                                                         'sep': ' ', 'into': ['q']}]),
        fine('explode-writes', [{'op': 'explode', 'column': 'a'}, {'op': 'round', 'column': 'a'}]),
        fine('ensure-writes', [{'op': 'ensure', 'columns': ['o'], 'value': 1}, {'op': 'clip', 'column': 'o', 'min': 0}]),
        fine('rename-loses-types', [{'op': 'rename', 'mapping': {'s': 'n', 'b': 'q'}}, {'op': 'round', 'column': 's'},
                                    {'op': 'text', 'columns': ['n'], 'fn': 'upper'}]),
        fine('drop-removes', [{'op': 'drop', 'columns': ['s']}, {'op': 'round', 'column': 's'}]),
        fine('nest-moves', [{'op': 'nest', 'columns': ['s', 'a'], 'as': 'n'}, {'op': 'round', 'column': 's'},
                            {'op': 'length', 'column': 'n', 'as': 'k'}]),
        ct('select-keeps-listed', [{'op': 'select', 'columns': ['s']}, {'op': 'round', 'column': 'n2'},
                                   {'op': 'text', 'columns': ['n'], 'fn': 'upper'}, {'op': 'round', 'column': 's'}],
           err(P + '[3].column', TM)),
        ct('group_count-keeps-by', [{'op': 'group_count', 'by': ['s'], 'as': 'cnt'}, {'op': 'json_parse', 'column': 'n'},
                                    {'op': 'math', 'column': 's', 'fn': 'abs'}], err(P + '[2].column', TM)),
        ct('summarize-keeps-by', [{'op': 'summarize', 'by': ['b'], 'metrics': [{'as': 'n', 'fn': 'count'}]},
                                  {'op': 'substr', 'column': 'n', 'as': 'x', 'start': 0},
                                  {'op': 'text', 'columns': ['s'], 'fn': 'upper'},
                                  {'op': 'replace', 'column': 'b', 'find': 'x', 'with': ''}], err(P + '[3].column', TM)),
        ct('unnest-clears-all', [{'op': 'unnest', 'column': 'o'}, {'op': 'round', 'column': 's'},
                                 {'op': 'text', 'columns': ['z'], 'fn': 'upper'}, {'op': 'cast', 'column': 'z', 'to': 'int'},
                                 {'op': 'text', 'columns': ['z'], 'fn': 'upper'}], err(P + '[4].columns[0]', TM)),
        ct('prefix-all-clears-all', [{'op': 'prefix', 'prefix': 'p_'}, {'op': 'round', 'column': 'z'},
                                     {'op': 'cast', 'column': 'b', 'to': 'float'}, {'op': 'length', 'column': 'b', 'as': 'k'}],
           err(P + '[3].column', TM)),
        ct('prefix-listed', [{'op': 'prefix', 'prefix': 'p_', 'columns': ['s']}, {'op': 'round', 'column': 's'},
                             {'op': 'round', 'column': 'z'}], err(P + '[2].column', TM)),
        ct('reading-steps-keep-types', [{'op': 'sort', 'by': 's'}, {'op': 'filter', 'where': 's != ""'},
                                        {'op': 'between', 'column': 'n', 'low': 0, 'high': 1, 'as': 'k'},
                                        {'op': 'length', 'column': 's', 'as': 'len'}, {'op': 'round', 'column': 's'}],
           err(P + '[4].column', TM)),
        ct('split-keeps-source', [{'op': 'split', 'column': 's', 'sep': ' ', 'into': ['z']}, {'op': 'round', 'column': 'z'},
                                  {'op': 'round', 'column': 's'}], err(P + '[2].column', TM)),
        ct('inside-branch', [br(('x > 1', [{'op': 'limit', 'n': 1}, {'op': 'round', 'column': 's'}]))],
           err(P + '[0].branches[0].steps[1].column', TM)),
        ct('branch-starts-from-known-types', [{'op': 'cast', 'column': 's', 'to': 'int'},
                                              br(('x', []), ('otherwise', [{'op': 'text', 'columns': ['s'], 'fn': 'upper'}]))],
           err(P + '[1].branches[1].steps[0].columns[0]', TM)),
        ct('branch-change-not-seen-by-sibling', [br(('x', [{'op': 'cast', 'column': 's', 'to': 'int'}]),
                                                    ('otherwise', [{'op': 'round', 'column': 's'}]))],
           err(P + '[0].branches[1].steps[0].column', TM)),
        fine('changed-in-one-branch', [br(('x', [{'op': 'set', 'column': 's', 'value': 1}]), ('otherwise', [])),
                                       {'op': 'round', 'column': 's'}]),
        fine('changed-in-every-branch', [br(('x', [{'op': 'cast', 'column': 's', 'to': 'int'}]),
                                            ('otherwise', [{'op': 'cast', 'column': 's', 'to': 'float'}])),
                                         {'op': 'text', 'columns': ['s'], 'fn': 'upper'}]),
        fine('changed-in-nested-branch', [br(('x', [br(('y', [{'op': 'nest', 'columns': ['a'], 'as': 'q'}]))])),
                                          {'op': 'round', 'column': 'a'}]),
        ct('unchanged-by-branch', [br(('x', [{'op': 'filter', 'where': 's'}]), ('otherwise', [{'op': 'select', 'columns': ['s']}])),
                                   {'op': 'round', 'column': 's'}], err(P + '[1].column', TM)),
        ct('other-problems-first', [{'op': 'round', 'column': 's'}, {'op': 'limit', 'n': -1}], err(P + '[1].n')),
        ct('first-type-problem', [{'op': 'limit', 'n': 1}, {'op': 'round', 'column': 's'}, {'op': 'round', 'column': 'b'}],
           err(P + '[1].column', TM)),
        ct('with-execute-not-run', [{'op': 'round', 'column': 'price'}], err(P + '[0].column', TM),
           schema={'price': 'string'}, dataset=[{'price': 1.5}]),
        ct('with-execute-runs', [{'op': 'round', 'column': 'price'}, {'op': 'cast', 'column': 'price', 'to': 'string'}],
           data([{'price': '2'}]), schema={'price': 'number'}, dataset=[{'price': 1.6}]),
        ct('schema-not-object', [{'op': 'limit', 'n': 1}], err('schema'), schema=['price']),
        ct('schema-bad-type', [], err('schema.price'), schema={'price': 'integer'}),
        ct('schema-first-bad-type', [], err('schema.b'), schema={'a': 'number', 'b': 'Number', 'c': 'int'}),
        ct('schema-before-steps', [{'op': 'nope'}], err('schema.a'), schema={'a': None}),
        case('dataset-before-schema', None, want=err('dataset'),
             request={'schema': 5, 'pipeline': {'steps': []}, 'dataset': 'x'}),
    ]


CHANGES = {
    'explain': explain,
    'missing_as_null': missing_as_null,
    'ignore_case_columns': ignore_case_columns,
    'column_types': column_types,
}

if __name__ == '__main__':
    sys.path.insert(0, str(HERE / 'tests'))
    from chain_golden import part_of
    failed = 0
    for name, make in CHANGES.items():
        if sys.argv[1:] and name not in sys.argv[1:]:
            continue
        cases = make()
        assert len({c['id'] for c in cases}) == len(cases), name + ': duplicate ids'
        for c in cases:
            stdin = c['raw'] if 'raw' in c else json.dumps(c['request'])
            res = subprocess.run([sys.executable, str(HERE / 'big_reference' / name / 'etl_pipeline.py'), *c['flags']],
                                 input=stdin, capture_output=True, text=True, timeout=10)
            out = json.loads(res.stdout)
            if out.get('status') == 'error':
                assert out.pop('message').startswith('ETL_ERROR: '), (name, c['id'])
            if 'part' in c:
                out = part_of(out, c['part'])
            want = c.pop('want')
            if want is not None:
                if isinstance(want, dict) and want.get('_partial'):
                    got = {k: out.get(k) for k in want if k != '_partial'}
                    want = {k: v for k, v in want.items() if k != '_partial'}
                else:
                    got = out
                if got != want:
                    failed += 1
                    print('MISMATCH %s/%s\n  want %s\n  got  %s' % (name, c['id'], json.dumps(want), json.dumps(got)))
            c['code'], c['expected'] = res.returncode, out
        (HERE / 'tests' / ('big_%s.json' % name)).write_text(json.dumps(cases, indent=1) + '\n')
        print(f"big_{name}.json: {len(cases)} cases, {sum(1 for c in cases if c['code'])} errors")
    sys.exit(1 if failed else 0)
