"""Write the golden cases of the held-out change chain (tests/h1_dates.json … tests/h4_list_ops.json).

Each change k is applied on top of the previous ones; its cases are run against chain_reference/h<k>/. Every
case carries a hand-written `want` (the expected response minus `message`, or a partial one marked
`_partial`), which is checked against that reference before the reference's output is saved. Rerun after
changing a case or the chain reference:

    python tasks/etl_pipeline_xl_naive/make_chain_tests.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S, BAD, UNK, MAL = 'SCHEMA_VALIDATION_FAILED', 'BAD_EXPR', 'UNKNOWN_OP', 'MALFORMED_STEP'
MISS, EXE = 'MISSING_COLUMN', 'EXECUTION_FAILED'
P = 'pipeline.steps'


def case(id, steps=None, dataset=None, flags=(), want=None, request=None, raw=None, part=None, execute=None):
    if execute is None:
        execute = dataset is not None
    c = {'id': id, 'flags': list(flags) + (['--execute'] if execute else [])}
    if raw is not None:
        c['raw'] = raw
    else:
        c['request'] = request if request is not None else {'pipeline': {'steps': steps}, 'dataset': dataset or []}
    if part is not None:
        c['part'] = part
    c['want'] = want
    return c


def err(path, code=S, errors=None):
    out = {'status': 'error', 'error_code': code, 'path': path}
    if errors is not None:
        out['errors'] = [{'error_code': c, 'path': p} for c, p in errors]
    return out


def norm(*steps):
    return {'status': 'ok', 'normalized': {'steps': list(steps)}}


def data(rows, rows_in=None):
    return {'status': 'ok', 'data': rows, 'metrics': {'rows_in': len(rows) if rows_in is None else rows_in,
                                                      'rows_out': len(rows)}}


OK = {'status': 'ok', '_partial': True}


def branch(*branches, **extra):
    return {'op': 'branch', 'branches': list(branches), **extra}


# ---- h1: date operations ----------------------------------------------------------------------------
def h1():
    td = lambda **kw: {'op': 'to_date', **kw}
    dd = lambda **kw: {'op': 'date_diff', **kw}
    da = lambda **kw: {'op': 'date_add', **kw}
    return [
        case('norm-to_date-defaults', [{'op': ' To_Date ', 'column': ' d '}],
             want=norm({'op': 'to_date', 'column': 'd', 'format': 'iso'})),
        case('norm-to_date-full', [td(column='d', format=' EU ', **{'as': ' out '}, note=1)],
             want=norm({'op': 'to_date', 'as': 'out', 'column': 'd', 'format': 'eu'})),
        case('norm-date_diff', [{'op': 'DATE_DIFF', 'start': ' a ', 'end': 'b ', 'as': ' n'}],
             want=norm({'op': 'date_diff', 'as': 'n', 'end': 'b', 'start': 'a'})),
        case('norm-date_add', [da(column='d', days=-3, **{'as': 'e'})],
             want=norm({'op': 'date_add', 'as': 'e', 'column': 'd', 'days': -3})),
        case('to_date-missing-column', [td(format='us')], want=err(P + '[0].column')),
        case('to_date-bad-format', [{'op': 'limit', 'n': 1}, td(column='d', format='jp')], want=err(P + '[1].format')),
        case('to_date-format-not-string', [td(column='d', format=1)], want=err(P + '[0].format')),
        case('to_date-empty-as', [td(column='d', **{'as': '  '})], want=err(P + '[0].as')),
        case('to_date-field-order', [td(format='jp', **{'as': ''})], want=err(P + '[0].column')),
        case('date_diff-missing-end', [dd(start='a', **{'as': 'n'})], want=err(P + '[0].end')),
        case('date_diff-start-not-string', [dd(start=5, **{'as': 'n'})], want=err(P + '[0].start')),
        case('date_add-days-float', [da(column='d', days=1.5, **{'as': 'e'})], want=err(P + '[0].days')),
        case('date_add-days-bool', [da(column='d', days=True, **{'as': 'e'})], want=err(P + '[0].days')),
        case('date_add-days-string', [da(column='d', days='3', **{'as': 'e'})], want=err(P + '[0].days')),
        case('date_add-missing-as', [da(column='d', days=1)], want=err(P + '[0].as')),
        case('to_date-iso', [td(column='d')], [{'d': '2024-02-29'}, {'d': None}, {'d': '0001-01-01'}],
             want=data([{'d': '2024-02-29'}, {'d': None}, {'d': '0001-01-01'}])),
        case('to_date-iso-not-a-real-day', [td(column='d')], [{'d': '2024-01-31'}, {'d': '2023-02-29'}],
             want=err(P + '[0].column', EXE)),
        case('to_date-us-as', [td(column='d', format='us', **{'as': 'iso'})],
             [{'d': '12/31/1999'}, {'d': '02/29/2000'}, {'d': None}],
             want=data([{'d': '12/31/1999', 'iso': '1999-12-31'}, {'d': '02/29/2000', 'iso': '2000-02-29'},
                        {'d': None, 'iso': None}])),
        case('to_date-eu', [td(column='d', format='eu')], [{'d': '31/12/1999'}, {'d': '01/02/2024'}],
             want=data([{'d': '1999-12-31'}, {'d': '2024-02-01'}])),
        case('to_date-us-rejects-eu-order', [td(column='d', format='us')], [{'d': '31/12/1999'}],
             want=err(P + '[0].column', EXE)),
        case('to_date-iso-rejects-us', [td(column='d')], [{'d': '01/05/2024'}], want=err(P + '[0].column', EXE)),
        case('to_date-non-string', [td(column='d')], [{'d': 20240101}], want=err(P + '[0].column', EXE)),
        case('to_date-short-month', [td(column='d')], [{'d': '2024-1-05'}], want=err(P + '[0].column', EXE)),
        case('to_date-trailing-time', [td(column='d')], [{'d': '2024-01-05T10:00'}],
             want=err(P + '[0].column', EXE)),
        case('to_date-missing-column-row', [td(column='d')], [{'d': '2024-01-01'}, {'x': 1}],
             want=err(P + '[0].column', MISS)),
        case('date_diff-values', [dd(start='a', end='b', **{'as': 'n'})], [
            {'a': '2024-01-01', 'b': '2024-03-01'}, {'a': '2024-03-01', 'b': '2024-01-01'},
            {'a': '2023-12-31', 'b': '2024-12-31'}, {'a': None, 'b': '2024-01-01'},
            {'a': '2024-01-01', 'b': None}, {'a': '2000-01-01', 'b': '2000-01-01', 'n': 'old'}],
             want=data([{'a': '2024-01-01', 'b': '2024-03-01', 'n': 60}, {'a': '2024-03-01', 'b': '2024-01-01', 'n': -60},
                        {'a': '2023-12-31', 'b': '2024-12-31', 'n': 366}, {'a': None, 'b': '2024-01-01', 'n': None},
                        {'a': '2024-01-01', 'b': None, 'n': None}, {'a': '2000-01-01', 'b': '2000-01-01', 'n': 0}])),
        case('date_diff-missing-start', [dd(start='a', end='b', **{'as': 'n'})], [{'b': '2024-01-01'}],
             want=err(P + '[0].start', MISS)),
        case('date_diff-missing-both', [dd(start='a', end='b', **{'as': 'n'})], [{'x': 1}],
             want=err(P + '[0].start', MISS)),
        case('date_diff-missing-end-second-row', [dd(start='a', end='b', **{'as': 'n'})],
             [{'a': '2024-01-01', 'b': '2024-01-02'}, {'a': '2024-01-01'}], want=err(P + '[0].end', MISS)),
        case('date_diff-bad-end', [dd(start='a', end='b', **{'as': 'n'})], [{'a': '2024-01-01', 'b': '2024/01/05'}],
             want=err(P + '[0].end', EXE)),
        case('date_diff-null-start-bad-end', [dd(start='a', end='b', **{'as': 'n'})], [{'a': None, 'b': 'tomorrow'}],
             want=err(P + '[0].end', EXE)),
        case('date_diff-both-bad', [dd(start='a', end='b', **{'as': 'n'})], [{'a': 'x', 'b': 7}],
             want=err(P + '[0].start', EXE)),
        case('date_add-forward', [da(column='d', days=30, **{'as': 'due'})],
             [{'d': '2024-01-31'}, {'d': None}, {'d': '2023-12-15'}],
             want=data([{'d': '2024-01-31', 'due': '2024-03-01'}, {'d': None, 'due': None},
                        {'d': '2023-12-15', 'due': '2024-01-14'}])),
        case('date_add-backward-in-place', [da(column='d', days=-1, **{'as': 'd'})],
             [{'d': '2024-03-01'}, {'d': '2023-03-01'}, {'d': '2000-01-01'}],
             want=data([{'d': '2024-02-29'}, {'d': '2023-02-28'}, {'d': '1999-12-31'}])),
        case('date_add-overflow', [da(column='d', days=1, **{'as': 'e'})], [{'d': '9999-12-31'}],
             want=err(P + '[0].days', EXE)),
        case('date_add-underflow', [da(column='d', days=-1, **{'as': 'e'})], [{'d': '0001-01-01'}],
             want=err(P + '[0].days', EXE)),
        case('date_add-bad-value', [da(column='d', days=1, **{'as': 'e'})], [{'d': '03/01/2024'}],
             want=err(P + '[0].column', EXE)),
        case('date_add-missing-column', [da(column='d', days=1, **{'as': 'e'})], [{'x': 1}],
             want=err(P + '[0].column', MISS)),
        case('in-branch', [
            branch({'when': 'kind == "us"', 'steps': [td(column='d', format='us')]},
                   {'when': 'otherwise', 'steps': [td(column='d', format='eu')]}),
            dd(start='d', end='ship', **{'as': 'wait'})],
             [{'kind': 'eu', 'd': '03/04/2024', 'ship': '2024-04-10'},
              {'kind': 'us', 'd': '03/04/2024', 'ship': '2024-03-10'}],
             want=data([{'kind': 'us', 'd': '2024-03-04', 'ship': '2024-03-10', 'wait': 6},
                        {'kind': 'eu', 'd': '2024-04-03', 'ship': '2024-04-10', 'wait': 7}])),
        case('in-branch-execution-error', [branch({'when': 'true', 'steps': [
            {'op': 'limit', 'n': 5}, da(column='d', days=1, **{'as': 'e'})]})], [{'d': 'bad'}],
             want=err(P + '[0].branches[0].steps[1].column', EXE)),
        case('nested-branch-validation', [branch({'when': 'x > 1', 'steps': [
            branch({'when': 'otherwise', 'steps': [td(column='d', format='ymd')]})]})],
             want=err(P + '[0].branches[0].steps[0].branches[0].steps[0].format')),
        case('spec-example', [td(column='ordered', format='us'), da(column='ordered', days=30, **{'as': 'due'}),
                              dd(start='ordered', end='shipped', **{'as': 'wait'})],
             [{'ordered': '02/14/2024', 'shipped': '2024-03-01'}, {'ordered': None, 'shipped': '2024-03-02'}],
             want=data([{'ordered': '2024-02-14', 'shipped': '2024-03-01', 'due': '2024-03-15', 'wait': 16},
                        {'ordered': None, 'shipped': '2024-03-02', 'due': None, 'wait': None}])),
    ]


# ---- h2: --all-errors ---------------------------------------------------------------------------------
def h2():
    A = ['--all-errors']
    c = lambda id, steps, want, **kw: case(id, steps, flags=kw.pop('flags', A), want=want, **kw)
    return [
        c('no-flag-unchanged', [{'op': 'select', 'columns': 'id'}, {'op': 'nope'}], err(P + '[0].columns'), flags=[]),
        c('success-normalize', [{'op': 'Select', 'columns': ['a']}, {'op': 'limit', 'n': 1}],
          norm({'op': 'select', 'columns': ['a']}, {'op': 'limit', 'n': 1})),
        c('success-execute', [{'op': 'map', 'as': 'b', 'expr': 'a + 1'}], data([{'a': 1, 'b': 2}]), dataset=[{'a': 1}]),
        c('empty-pipeline', [], norm()),
        c('single-problem', [{'op': 'limit', 'n': -1}], err(P + '[0].n', errors=[(S, P + '[0].n')])),
        c('two-steps', [{'op': 'limit', 'n': '5'}, {'op': 'select', 'columns': ['a']}, {'op': 'filter', 'where': 'x >'}],
          err(P + '[0].n', errors=[(S, P + '[0].n'), (BAD, P + '[2].where')])),
        c('first-problem-per-step', [{'op': 'cast', 'to': 'decimal'}, {'op': 'nest', 'columns': [], 'as': ''}],
          err(P + '[0].column', errors=[(S, P + '[0].column'), (S, P + '[1].columns')])),
        c('op-problems', [{'op': 'pivot'}, {'columns': ['a']}, {'op': ''}, {'op': 7}],
          err(P + '[0].op', UNK, errors=[(UNK, P + '[0].op'), (S, P + '[1].op'), (S, P + '[2].op'), (S, P + '[3].op')])),
        c('step-not-object', [{'op': 'limit', 'n': 1}, 5, ['x']],
          err(P + '[1]', errors=[(S, P + '[1]'), (S, P + '[2]')])),
        c('bad-expressions', [{'op': 'map', 'as': 'a', 'expr': '1 ** 2'}, {'op': 'filter', 'where': '(x'},
                              {'op': 'coalesce', 'as': 'c', 'exprs': ['a', 'b +']}],
          err(P + '[0].expr', BAD, errors=[(BAD, P + '[0].expr'), (BAD, P + '[1].where'), (BAD, P + '[2].exprs[1]')])),
        c('spec-example', [{'op': 'select', 'columns': 'id'}, {'op': 'limit', 'n': 5},
                           branch({'when': 'price >', 'steps': [{'op': 'fill', 'column': 'x'}, {'op': 'explode'}]}),
                           {'op': 'trim'}],
          err(P + '[0].columns', errors=[(S, P + '[0].columns'), (BAD, P + '[2].branches[0].when'),
                                         (S, P + '[2].branches[0].steps[0].value'),
                                         (S, P + '[2].branches[0].steps[1].column'), (UNK, P + '[3].op')])),
        c('inner-steps-only', [branch({'when': 'x > 1', 'steps': [{'op': 'limit'}, {'op': 'limit', 'n': 1}, {'op': 'sort'}]})],
          err(P + '[0].branches[0].steps[0].n', errors=[(S, P + '[0].branches[0].steps[0].n'),
                                                        (S, P + '[0].branches[0].steps[2].by')])),
        c('two-branches', [{'op': 'tail'}, branch({'when': 'x > 1', 'steps': [{'op': 'offset', 'n': -2}]},
                                                  {'when': 'otherwise', 'steps': [{'op': 'round'}]})],
          err(P + '[0].n', errors=[(S, P + '[0].n'), (S, P + '[1].branches[0].steps[0].n'),
                                   (S, P + '[1].branches[1].steps[0].column')])),
        c('nested-branches', [
            branch({'when': 'x > 1', 'steps': [
                {'op': 'limit', 'n': -1},
                branch({'when': 'y >', 'steps': [{'op': 'drop'}]}),
                {'op': 'fill'}]}),
            {'op': 'nope'}],
          err(P + '[0].branches[0].steps[0].n', errors=[
              (S, P + '[0].branches[0].steps[0].n'), (BAD, P + '[0].branches[0].steps[1].branches[0].when'),
              (S, P + '[0].branches[0].steps[1].branches[0].steps[0].columns'),
              (S, P + '[0].branches[0].steps[2].column'), (UNK, P + '[1].op')])),
        c('malformed-branch-inner-still-checked', [branch({'when': 'otherwise', 'steps': [{'op': 'limit'}]},
                                                          {'when': 'x > 1', 'steps': [{'op': 'x'}]})],
          err(P + '[0].branches', MAL, errors=[(MAL, P + '[0].branches'), (S, P + '[0].branches[0].steps[0].n'),
                                               (UNK, P + '[0].branches[1].steps[0].op')])),
        c('branch-entry-not-object', [branch(5, {'when': 'x > 1', 'steps': [{'op': 'limit', 'n': True}]})],
          err(P + '[0].branches[0]', errors=[(S, P + '[0].branches[0]'), (S, P + '[0].branches[1].steps[0].n')])),
        c('branch-steps-not-array', [branch({'when': 'x > 1', 'steps': 'limit'},
                                            {'when': 'otherwise', 'steps': [{'op': 'limit'}]})],
          err(P + '[0].branches[0].steps', errors=[(S, P + '[0].branches[0].steps'),
                                                   (S, P + '[0].branches[1].steps[0].n')])),
        c('empty-branches', [branch(), {'op': 'limit', 'n': 1.5}],
          err(P + '[0].branches', errors=[(S, P + '[0].branches'), (S, P + '[1].n')])),
        c('branch-own-first-problem-only', [branch({'when': 'x >', 'id': 5, 'steps': []}, merge={'strategy': 'union'})],
          err(P + '[0].branches[0].when', BAD, errors=[(BAD, P + '[0].branches[0].when')])),
        c('branch-merge-after-inner', [branch({'when': 'x > 1', 'steps': [{'op': 'limit'}]}, merge={'strategy': 'union'})],
          err(P + '[0].branches[0].steps[0].n', errors=[(S, P + '[0].merge.strategy'),
                                                        (S, P + '[0].branches[0].steps[0].n')])),
        c('branch-later-when-after-inner', [branch({'when': 'x > 1', 'steps': [{'op': 'nope'}]},
                                                   {'when': 'y <', 'steps': []})],
          err(P + '[0].branches[0].steps[0].op', UNK, errors=[(BAD, P + '[0].branches[1].when'),
                                                              (UNK, P + '[0].branches[0].steps[0].op')])),
        c('request-dataset', [{'op': 'nope'}], err('dataset', errors=[(S, 'dataset')]),
          request={'pipeline': {'steps': [{'op': 'nope'}]}, 'dataset': 'x'}),
        c('request-dataset-row', None, err('dataset[1]', errors=[(S, 'dataset[1]')]),
          request={'pipeline': {'steps': [{'op': 'nope'}]}, 'dataset': [{'a': 1}, 3]}),
        c('request-no-pipeline', None, err('pipeline', errors=[(S, 'pipeline')]), request={'dataset': []}),
        c('request-steps-not-array', None, err(P, errors=[(S, P)]), request={'pipeline': {'steps': {}}, 'dataset': []}),
        c('request-invalid-json', None, err('', errors=[(S, '')]), raw='{nope'),
        c('execution-error-unchanged', [{'op': 'select', 'columns': ['zz']}], err(P + '[0].columns[0]', MISS),
          dataset=[{'a': 1}]),
        c('assert-failure-unchanged', [{'op': 'assert', 'where': 'a > 5'}], err(P + '[0].where', EXE), dataset=[{'a': 1}]),
        c('validation-with-execute', [{'op': 'select', 'columns': ['a']}, {'op': 'map', 'as': 'b'}, {'op': 'sort', 'by': 3}],
          err(P + '[1].expr', errors=[(S, P + '[1].expr'), (S, P + '[2].by')]), dataset=[{'a': 1}]),
        c('date-ops', [{'op': 'to_date', 'column': 'd', 'format': 'jp'}, {'op': 'date_diff', 'start': 'a', 'as': 'n'},
                       {'op': 'date_add', 'column': 'd', 'days': 1.5, 'as': 'e'},
                       {'op': 'date_add', 'column': 'd', 'days': 1, 'as': 'e'}],
          err(P + '[0].format', errors=[(S, P + '[0].format'), (S, P + '[1].end'), (S, P + '[2].days')])),
        c('rename-forms', [{'op': 'rename'}, {'op': 'rename', 'from': 'a'}, {'op': 'rename', 'mapping': {'a': 5}},
                           {'op': 'rename', 'from': 'a', 'to': 'b'}],
          err(P + '[0]', errors=[(S, P + '[0]'), (S, P + '[1].to'), (S, P + '[2].mapping.a')])),
        c('many-ops', [
            {'op': 'drop', 'columns': [1]},
            {'op': 'lookup', 'column': 'a', 'as': 'b', 'table': {'x': [1]}},
            {'op': 'ensure', 'columns': []},
            {'op': 'split', 'column': 'a', 'sep': '', 'into': ['b']},
            {'op': 'regex_extract', 'column': 'a', 'pattern': '(', 'as': 'b'},
            {'op': 'pad', 'column': 'a', 'width': 3, 'side': 'middle'},
            {'op': 'summarize', 'metrics': [{'as': 'n', 'fn': 'median'}]},
            {'op': 'sample_every', 'n': 0},
            {'op': 'append', 'rows': [1]},
            {'op': 'row_number', 'as': 'r', 'start': 1.5},
            {'op': 'sort', 'by': 'a', 'desc': 'yes'},
            {'op': 'clip', 'column': 'a', 'min': '0'}],
          err(P + '[0].columns[0]', errors=[
              (S, P + '[0].columns[0]'), (S, P + '[1].table.x'), (S, P + '[2].columns'), (S, P + '[3].sep'),
              (S, P + '[4].pattern'), (S, P + '[5].side'), (S, P + '[6].metrics[0].fn'), (S, P + '[7].n'),
              (S, P + '[8].rows[0]'), (S, P + '[9].start'), (S, P + '[10].desc'), (S, P + '[11].min')])),
    ]


# ---- h3: --strict ----------------------------------------------------------------------------------
def h3():
    T = ['--strict']
    c = lambda id, steps, want, **kw: case(id, steps, flags=kw.pop('flags', T), want=want, **kw)
    unknown = lambda id, step, key: c(id, [{'op': 'limit', 'n': 1}, step], err(P + '[1].' + key))
    return [
        c('no-flag-still-dropped', [{'op': 'select', 'columns': ['a'], 'colums': ['b']}],
          norm({'op': 'select', 'columns': ['a']}), flags=[]),
        c('select-typo', [{'op': 'select', 'columns': ['a'], 'colums': ['b']}], err(P + '[0].colums')),
        c('missing-field-before-unknown', [{'op': 'select', 'colums': ['a']}], err(P + '[0].columns')),
        c('bad-field-before-unknown', [{'op': 'limit', 'm': 1, 'n': -1}], err(P + '[0].n')),
        c('first-unknown-in-request-order', [{'op': 'map', 'zeta': 1, 'as': 'a', 'expr': '1', 'alpha': 2}],
          err(P + '[0].zeta')),
        c('rename-extra-key', [{'op': 'rename', 'from': 'a', 'to': 'b', 'form': 'c'}], err(P + '[0].form')),
        c('rename-both-forms-known', [{'op': 'rename', 'mapping': {'a': 'b'}, 'from': 'x', 'to': 'y'}],
          norm({'op': 'rename', 'mapping': {'a': 'b'}})),
        c('rename-mapping-keys-are-data', [{'op': 'rename', 'mapping': {'colums': 'b', 'op': 'c'}}],
          norm({'op': 'rename', 'mapping': {'colums': 'b', 'op': 'c'}})),
        c('lookup-table-keys-are-data', [{'op': 'lookup', 'column': 'cc', 'as': 'c', 'table': {'anything': 1}}],
          norm({'op': 'lookup', 'as': 'c', 'column': 'cc', 'table': {'anything': 1}})),
        c('spec-example', [{'op': 'lookup', 'column': 'cc', 'as': 'country', 'table': {'NO': 'Norway'}, 'defualt': '?'}],
          err(P + '[0].defualt')),
        c('append-rows-are-data', [{'op': 'append', 'rows': [{'whatever': 1}]}],
          norm({'op': 'append', 'rows': [{'whatever': 1}]})),
        c('branch-step-key', [branch({'when': 'otherwise', 'steps': []}, merges={'strategy': 'concat'})],
          err(P + '[0].merges')),
        c('branch-entry-key', [branch({'when': 'x > 1', 'steps': []}, {'when': 'otherwise', 'stpes': [], 'steps': []})],
          err(P + '[0].branches[1].stpes')),
        c('merge-key', [branch({'when': 'x > 1', 'steps': []}, merge={'strategy': 'concat', 'how': 'x'})],
          err(P + '[0].merge.how')),
        c('summarize-metric-key', [{'op': 'summarize', 'metrics': [{'as': 'n', 'fn': 'count'},
                                                                   {'as': 's', 'fn': 'sum', 'col': 'x'}]}],
          err(P + '[0].metrics[1].col')),
        c('nested-step-key', [branch({'when': 'x > 1', 'steps': [branch({'when': 'otherwise', 'steps': [
            {'op': 'limit', 'n': 1}, {'op': 'text', 'columns': ['a'], 'fn': 'upper', 'fnn': 'x'}]})]})],
          err(P + '[0].branches[0].steps[0].branches[0].steps[1].fnn')),
        c('branch-key-before-later-merge', [branch({'when': 'x > 1', 'steps': [], 'idd': 'a'}, merge={'strategy': 'union'})],
          err(P + '[0].branches[0].idd')),
        c('inner-step-before-branch-key', [branch({'when': 'x > 1', 'steps': [{'op': 'limit'}], 'idd': 'a'})],
          err(P + '[0].branches[0].steps[0].n')),
        c('with-execute', [{'op': 'filter', 'where': 'a > 1', 'wehre': 'x'}], err(P + '[0].wehre'), dataset=[{'a': 2}]),
        unknown('to_date', {'op': 'to_date', 'column': 'd', 'fromat': 'us'}, 'fromat'),
        unknown('date_diff', {'op': 'date_diff', 'start': 'a', 'end': 'b', 'as': 'n', 'unit': 'days'}, 'unit'),
        unknown('date_add', {'op': 'date_add', 'column': 'd', 'day': 1, 'days': 1, 'as': 'e'}, 'day'),
        unknown('cast', {'op': 'cast', 'column': 'a', 'to': 'int', 'type': 'int'}, 'type'),
        unknown('coalesce', {'op': 'coalesce', 'as': 'a', 'exprs': ['b'], 'expr': 'c'}, 'expr'),
        unknown('pad', {'op': 'pad', 'column': 'a', 'width': 3, 'padding': '0'}, 'padding'),
        unknown('sort', {'op': 'sort', 'by': 'a', 'order': 'desc'}, 'order'),
        unknown('rank', {'op': 'rank', 'by': 'a', 'as': 'r', 'descending': True}, 'descending'),
        unknown('lag', {'op': 'lag', 'column': 'a', 'as': 'b', 'offset': 2}, 'offset'),
        unknown('group_count', {'op': 'group_count', 'by': ['a'], 'as': 'n', 'count': 1}, 'count'),
        unknown('clip', {'op': 'clip', 'column': 'a', 'minimum': 0}, 'minimum'),
        unknown('ensure', {'op': 'ensure', 'columns': ['a'], 'default': 0}, 'default'),
        unknown('regex_filter', {'op': 'regex_filter', 'column': 'a', 'pattern': 'x', 'negate': True}, 'negate'),
        unknown('sample_every', {'op': 'sample_every', 'n': 2, 'every': 2}, 'every'),
        c('every-optional-field-known', [
            {'op': 'to_date', 'column': 'd', 'format': 'us', 'as': 'd2'},
            {'op': 'lookup', 'column': 'c', 'as': 'n', 'table': {'a': 1}, 'default': 0},
            {'op': 'pad', 'column': 'p', 'width': 4, 'fill': '0', 'side': 'right'},
            {'op': 'lag', 'column': 'x', 'as': 'y', 'n': 2, 'default': None},
            {'op': 'summarize', 'by': ['c'], 'metrics': [{'as': 't', 'fn': 'sum', 'column': 'x'}]},
            branch({'id': 'A', 'when': 'x > 1', 'steps': [{'op': 'date_add', 'column': 'd2', 'days': 1, 'as': 'd3'}]},
                   {'id': 'B', 'when': 'otherwise', 'steps': [{'op': 'date_diff', 'start': 'a', 'end': 'b', 'as': 'n'}]},
                   merge={'strategy': 'concat'}),
            {'op': 'regex_extract', 'column': 's', 'pattern': '(a)', 'as': 'g', 'group': 1},
            {'op': 'prefix', 'prefix': 'p_', 'columns': ['a']},
            {'op': 'assert', 'where': 'true', 'message': 'm'},
            {'op': 'unnest', 'column': 'm', 'prefix': 'm_'}], OK),
        c('all-errors-and-strict', [
            {'op': 'select', 'columns': ['a'], 'colums': ['b']},
            {'op': 'limit', 'n': 1},
            {'op': 'limit', 'n': -1, 'extra': 1},
            branch({'when': 'x > 1', 'stpes': [], 'steps': [{'op': 'map', 'as': 'a', 'expr': '1', 'exp': '2'}]}),
            {'op': 'date_diff', 'start': 'a', 'end': 'b', 'as': 'n', 'unit': 'days'}],
          err(P + '[0].colums', errors=[(S, P + '[0].colums'), (S, P + '[2].n'), (S, P + '[3].branches[0].stpes'),
                                        (S, P + '[3].branches[0].steps[0].exp'), (S, P + '[4].unit')]),
          flags=['--strict', '--all-errors']),
        c('all-errors-and-strict-branch-key-after-inner', [
            branch({'when': 'x > 1', 'steps': [{'op': 'limit', 'n': 1, 'nn': 2}], 'idd': 'z'})],
          err(P + '[0].branches[0].steps[0].nn', errors=[(S, P + '[0].branches[0].idd'),
                                                         (S, P + '[0].branches[0].steps[0].nn')]),
          flags=['--all-errors', '--strict']),
        c('all-errors-without-strict-ignores-unknown', [{'op': 'select', 'colums': ['a'], 'columns': ['a']},
                                                        {'op': 'limit'}],
          err(P + '[1].n', errors=[(S, P + '[1].n')]), flags=['--all-errors']),
    ]


# ---- h4: --list-ops ------------------------------------------------------------------------------
OPS = {
    'select': ['columns'], 'filter': ['where'], 'map': ['as', 'expr'], 'rename': ['from', 'mapping', 'to'],
    'limit': ['n'], 'branch': ['branches', 'merge'],
    'drop': ['columns'], 'fill': ['column', 'value'], 'cast': ['column', 'to'], 'coalesce': ['as', 'exprs'],
    'explode': ['column'], 'lookup': ['as', 'column', 'default', 'table'], 'set': ['column', 'value'],
    'ensure': ['columns', 'value'], 'reorder': ['columns'], 'prefix': ['columns', 'prefix'],
    'nest': ['as', 'columns'], 'unnest': ['column', 'prefix'],
    'concat': ['as', 'columns', 'sep'], 'split': ['column', 'into', 'sep'], 'text': ['columns', 'fn'],
    'replace': ['column', 'find', 'with'], 'regex_extract': ['as', 'column', 'group', 'pattern'],
    'regex_filter': ['column', 'invert', 'pattern'], 'substr': ['as', 'column', 'length', 'start'],
    'pad': ['column', 'fill', 'side', 'width'], 'length': ['as', 'column'], 'json_parse': ['column'],
    'json_dump': ['column'], 'date_part': ['as', 'column', 'part'],
    'round': ['column', 'digits'], 'clip': ['column', 'max', 'min'], 'scale': ['column', 'factor', 'offset'],
    'bucket': ['as', 'column', 'edges'], 'math': ['column', 'fn'], 'between': ['as', 'column', 'high', 'low'],
    'group_count': ['as', 'by'], 'summarize': ['by', 'metrics'],
    'distinct': ['columns'], 'sort': ['by', 'desc'], 'offset': ['n'], 'tail': ['n'], 'assert': ['message', 'where'],
    'sample_every': ['n'], 'take_while': ['where'], 'skip_while': ['where'], 'append': ['rows'],
    'require': ['columns'], 'row_number': ['as', 'start'], 'rank': ['as', 'by', 'desc'], 'cumsum': ['as', 'column'],
    'lag': ['as', 'column', 'default', 'n'],
    'to_date': ['as', 'column', 'format'], 'date_diff': ['as', 'end', 'start'], 'date_add': ['as', 'column', 'days'],
}
assert len(OPS) == 55


def h4():
    L = ['--list-ops']
    full = {'status': 'ok', 'ops': OPS}
    per_op = ['select', 'filter', 'map', 'rename', 'limit', 'branch', 'drop', 'lookup', 'ensure', 'cast', 'unnest',
              'concat', 'regex_extract', 'pad', 'date_part', 'round', 'clip', 'between', 'summarize', 'group_count',
              'lag', 'row_number', 'assert', 'append', 'to_date', 'date_diff', 'date_add']
    return [
        case('full-listing', flags=L, raw='', want=full),
        case('ignores-invalid-stdin', flags=L, raw='not json at all', want=full),
        case('ignores-request-and-other-flags', [{'op': 'nope'}], flags=['--strict', '--list-ops', '--all-errors'],
             dataset=[{'a': 1}], want=full),
        case('flag-after-execute', flags=['--execute', '--list-ops'], raw='{}', want=full),
        case('op-names', flags=L, raw='', part='ops.__keys__', want=sorted(OPS)),
        case('without-flag-unchanged', [{'op': 'Limit', 'n': 1}], want=norm({'op': 'limit', 'n': 1})),
    ] + [case('fields-' + op, flags=L, raw='', part='ops.' + op, want=OPS[op]) for op in per_op]


CHANGES = {'h1_dates': ('h1', h1), 'h2_all_errors': ('h2', h2), 'h3_strict': ('h3', h3), 'h4_list_ops': ('h4', h4)}

if __name__ == '__main__':
    sys.path.insert(0, str(HERE / 'tests'))
    from chain_golden import part_of
    failed = 0
    for name, (stage, make) in CHANGES.items():
        cases = make()
        assert len({c['id'] for c in cases}) == len(cases), name + ': duplicate ids'
        for c in cases:
            stdin = c['raw'] if 'raw' in c else json.dumps(c['request'])
            res = subprocess.run([sys.executable, str(HERE / 'chain_reference' / stage / 'etl_pipeline.py'), *c['flags']],
                                 input=stdin, capture_output=True, text=True, timeout=10)
            out = json.loads(res.stdout)
            out.pop('message', None)  # only its ETL_ERROR: prefix is checked
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
        (HERE / 'tests' / (name + '.json')).write_text(json.dumps(cases, indent=1) + '\n')
        print(f"{name}.json: {len(cases)} cases, {sum(1 for c in cases if c['code'])} errors")
    sys.exit(1 if failed else 0)
