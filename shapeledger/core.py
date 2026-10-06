"""Observed JSON shapes. Counts never include scalar values."""
import json
import sys
from fractions import Fraction

VERSION = 1
TYPES = {'object', 'array', 'string', 'integer', 'number', 'boolean', 'null'}
KINDS = {'added_path', 'removed_path', 'added_type', 'missing_increase', 'null_increase'}

class ShapeError(ValueError):
    pass

def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ShapeError('duplicate object key')
            result[key] = value
        return result
    def bad(_):
        raise ShapeError('non-finite JSON number')
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=bad,
                          parse_float=lambda s: finite_float(s))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ShapeError('invalid strict JSON') from exc

def finite_float(s):
    import math
    value = float(s)
    if not math.isfinite(value):
        raise ShapeError('non-finite JSON number')
    return value

def kind(value):
    return {dict:'object', list:'array', str:'string', int:'integer', float:'number',
            bool:'boolean', type(None):'null'}[type(value)]

def token(path):
    return json.dumps(path, ensure_ascii=True, separators=(',', ':'))

def profile(stream, max_nodes=10000, max_depth=64, max_line_bytes=1048576):
    if any(type(x) is not int or x < 1 for x in (max_nodes, max_depth, max_line_bytes)):
        raise ShapeError('limits must be positive integers')
    if max_nodes > 10000 or max_depth > 64:
        raise ShapeError('profile format limits: 10000 nodes and depth 64')
    if max_line_bytes >= sys.maxsize:
        raise ShapeError('line byte limit must be smaller than sys.maxsize')
    nodes = {}
    records = 0
    while True:
        line = stream.readline(max_line_bytes + 1)
        if not line:
            break
        if len(line) > max_line_bytes:
            raise ShapeError('line byte limit exceeded')
        try:
            value = strict_json(line.decode('utf-8', errors='strict'))
        except (UnicodeError, ShapeError) as exc:
            raise ShapeError('invalid JSONL record at line %d' % (records + 1)) from exc
        records += 1
        stack = [((), value)]
        while stack:
            path, value = stack.pop()
            if len(path) > max_depth:
                raise ShapeError('depth limit exceeded')
            key = token(path)
            if key not in nodes:
                if len(nodes) >= max_nodes:
                    raise ShapeError('node limit exceeded')
                nodes[key] = {'path': [list(p) for p in path], 'types': {}, 'array_items': 0}
            node = nodes[key]
            t = kind(value)
            node['types'][t] = node['types'].get(t, 0) + 1
            if t == 'object':
                stack.extend((path + (('key', k),), v) for k, v in value.items())
            elif t == 'array':
                node['array_items'] += len(value)
                stack.extend((path + (('items',),), v) for v in value)
    for node in nodes.values():
        path = node['path']
        if not path:
            node['opportunities'] = records
        else:
            parent = nodes[token(path[:-1])]
            node['opportunities'] = (parent['types'].get('object', 0) if path[-1][0] == 'key'
                                     else parent['array_items'])
    return {'version': VERSION, 'records': records, 'nodes': [nodes[k] for k in sorted(nodes)]}

def validate(p, max_nodes=10000, max_depth=64):
    def integer(v):
        return type(v) is int and v >= 0
    if type(p) is not dict or set(p) != {'version', 'records', 'nodes'}:
        raise ShapeError('invalid profile fields')
    if type(p['version']) is not int or p['version'] != VERSION or not integer(p['records']):
        raise ShapeError('invalid profile version or record count')
    if type(p['nodes']) is not list or len(p['nodes']) > max_nodes:
        raise ShapeError('invalid profile nodes')
    indexed = {}
    for n in p['nodes']:
        if type(n) is not dict or set(n) != {'path','types','array_items','opportunities'}:
            raise ShapeError('invalid node fields')
        path = n['path']
        if type(path) is not list or len(path) > max_depth:
            raise ShapeError('invalid path')
        for part in path:
            if type(part) is not list or not (part == ['items'] or
                (len(part) == 2 and part[0] == 'key' and type(part[1]) is str)):
                raise ShapeError('invalid path token')
        k = token(path)
        if k in indexed:
            raise ShapeError('duplicate path')
        if type(n['types']) is not dict or not n['types'] or not set(n['types']) <= TYPES:
            raise ShapeError('invalid types')
        if any(not integer(v) or not v for v in n['types'].values()):
            raise ShapeError('invalid type count')
        if not integer(n['array_items']) or not integer(n['opportunities']):
            raise ShapeError('invalid count')
        if n['array_items'] and not n['types'].get('array'):
            raise ShapeError('items without array')
        indexed[k] = n
    if bool(indexed) != bool(p['records']) or (indexed and '[]' not in indexed):
        raise ShapeError('invalid root')
    for n in indexed.values():
        path = n['path']
        observed = sum(n['types'].values())
        if not path:
            expected = p['records']
            if observed != expected:
                raise ShapeError('invalid root counts')
        else:
            parent = indexed.get(token(path[:-1]))
            if parent is None:
                raise ShapeError('missing parent')
            expected = (parent['types'].get('object', 0) if path[-1][0] == 'key'
                        else parent['array_items'])
            if path[-1] == ['items'] and observed != expected:
                raise ShapeError('invalid array element count')
        if n['opportunities'] != expected or observed > expected:
            raise ShapeError('invalid opportunities')
        child = indexed.get(token(path + [['items']]))
        if bool(n['array_items']) != bool(child):
            raise ShapeError('missing or spurious array element node')
    return indexed

def compare(baseline, candidate):
    old, new = validate(baseline), validate(candidate)
    changes = []
    for k in sorted(old.keys() | new.keys()):
        a, b = old.get(k), new.get(k)
        path = (a or b)['path']
        if a is None or b is None:
            changes.append({'kind': 'added_path' if a is None else 'removed_path', 'path': path})
            continue
        for t in sorted(b['types'].keys() - a['types'].keys()):
            changes.append({'kind':'added_type', 'path':path, 'type':t})
        for label in ('missing', 'null'):
            def rate(n):
                count = (n['opportunities'] - sum(n['types'].values()) if label == 'missing'
                         else n['types'].get('null', 0))
                return Fraction(count, n['opportunities'])
            before, after = rate(a), rate(b)
            if after > before:
                changes.append({'kind':label + '_increase', 'path':path,
                                'before':str(before), 'after':str(after)})
    return {'version': VERSION, 'changes': changes}
