import copy
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from shapeledger.core import ShapeError, compare, profile, strict_json, token, validate


def prof(text, **kw):
    return profile(io.BytesIO(text.encode()), **kw)

class Shapes(unittest.TestCase):
    def test_opportunities(self):
        p = prof('{"x":[{"a":null},{},false,1],"empty":[]}\n{}\n')
        n = validate(p)
        self.assertEqual(n[token([['key','x']])]['opportunities'], 2)
        a = n[token([['key','x'],['items'],['key','a']])]
        self.assertEqual((a['opportunities'], a['types']), (2, {'null':1}))
        self.assertEqual(n[token([['key','x'],['items']])]['types'], {'object':2,'boolean':1,'integer':1})
        self.assertNotIn(token([['key','empty'],['items']]), n)
    def test_paths(self):
        p = prof('{"*":1,"a.b":2,"a":{"b":3},"/":[],"items":4,"":5}')
        self.assertEqual(len(validate(p)), 8)
    def test_strict(self):
        for data in ['{"a":1,"a":2}', 'NaN', 'Infinity','1e400','\n','{"a":', '1 2']:
            with self.subTest(data=data), self.assertRaises(ShapeError): prof(data)
        with self.assertRaises(ShapeError): profile(io.BytesIO(b'"\xff"'))
    def test_limits(self):
        for kwargs in [{'max_nodes':1}, {'max_depth':1}, {'max_line_bytes':3}]:
            with self.assertRaises(ShapeError): prof('{"a":{"b":1}}', **kwargs)
    def test_empty(self):
        self.assertEqual(validate(prof('')), {})
        self.assertEqual(compare(prof(''), prof(''))['changes'], [])
    def test_determinism_values(self):
        self.assertEqual(prof('{"b":123,"a":"secret"}'), prof('{"a":"different","b":9}'))
    def test_exact_rates(self):
        changes = compare(prof('{"a":null}\n{"a":1}\n{}'), prof('{"a":null}\n{}'))['changes']
        by_kind = {c['kind']:c for c in changes}
        self.assertEqual(by_kind['missing_increase']['before'], '1/3')
        self.assertEqual(by_kind['missing_increase']['after'], '1/2')
        self.assertEqual(by_kind['null_increase']['after'], '1/2')
    def test_added_type(self):
        c = compare(prof('1'), prof('true'))['changes']
        self.assertEqual(c, [{'kind':'added_type','path':[],'type':'boolean'}])
    def test_invalid_profiles(self):
        base = prof('{"a":[1]}')
        mutations = [lambda p:p.update(version=True), lambda p:p.update(extra=1),
          lambda p:p['nodes'].append(p['nodes'][0]),
          lambda p:p['nodes'][0].update(opportunities=99),
          lambda p:p['nodes'][0].update(types={'integer':True}),
          lambda p:p['nodes'][0].update(path=[['oops']]),
          lambda p:p['nodes'].pop()]
        for mutate in mutations:
            p = copy.deepcopy(base); mutate(p)
            with self.assertRaises(ShapeError): validate(p)
    def test_cli_gates(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a.json', Path(d)/'b.json'
            a.write_text(json.dumps(prof('1')))
            b.write_text(json.dumps(prof('true')))
            command = [sys.executable, '-m', 'shapeledger', 'compare', str(a), str(b)]
            for args, code in [([],0), (['--fail-on','added_type'],1),
                               (['--fail-on','removed_path'],0)]:
                result = subprocess.run(command + args, capture_output=True)
                self.assertEqual(result.returncode, code)
                self.assertEqual(len(json.loads(result.stdout)['changes']), 1)
            b.write_text('{"version":99}')
            result = subprocess.run(command, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
    def test_crlf_last_line_and_parent_types(self):
        p = prof('{"a":{"x":1}}\r\n{"a":null}\r\n{"a":{}}')
        n = validate(p)[token([['key','a'],['key','x']])]
        self.assertEqual(n['opportunities'], 2)
        self.assertEqual(sum(n['types'].values()), 1)
    def test_caps(self):
        for kw in [{'max_nodes':10001}, {'max_depth':65}, {'max_line_bytes':0}]:
            with self.assertRaises(ShapeError): prof('1', **kw)
    def test_cli(self):
        result = subprocess.run([sys.executable,'-m','shapeledger','profile','-'],input=b'{"a":1}\n',capture_output=True)
        self.assertEqual(result.returncode, 0)
        validate(json.loads(result.stdout))
        result = subprocess.run([sys.executable,'-m','shapeledger','profile','-'],input=b'{"secret":"bad',capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertNotIn(b'secret',result.stderr)

if __name__ == '__main__': unittest.main()
