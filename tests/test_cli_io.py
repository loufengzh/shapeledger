"""Exercise real buffering and process exit codes, not only mocked writes."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from shapeledger.core import ShapeError, profile


class LineBounds(unittest.TestCase):
    def test_native_size_boundary_before_read(self):
        class Unreadable:
            def readline(self, size):
                raise AssertionError('invalid limit must be rejected before reading')
        for limit in (sys.maxsize, sys.maxsize + 1, 10 ** 100):
            with self.subTest(limit=limit), self.assertRaises(ShapeError):
                profile(Unreadable(), max_line_bytes=limit)

    def test_largest_representable_read_size(self):
        class Empty:
            def readline(inner, size):
                self.assertEqual(size, sys.maxsize)
                return b''
        self.assertEqual(profile(Empty(), max_line_bytes=sys.maxsize - 1)['records'], 0)

    def test_line_limit_includes_newline(self):
        self.assertEqual(profile(io.BytesIO(b'{}\n'), max_line_bytes=3)['records'], 1)
        with self.assertRaises(ShapeError):
            profile(io.BytesIO(b'{}\n'), max_line_bytes=2)

    def test_cli_huge_limits_file_and_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'private-input.jsonl'
            path.write_bytes(b'{"secret": "value"}\n')
            for source in ('-', str(path)):
                for limit in (sys.maxsize, 10 ** 100):
                    with self.subTest(source=source, limit=limit):
                        result = subprocess.run(
                            [sys.executable, '-m', 'shapeledger', 'profile', source,
                             '--max-line-bytes', str(limit)],
                            input=b'{}\n', capture_output=True)
                        self.assertEqual(result.returncode, 2)
                        self.assertEqual(result.stdout, b'')
                        self.assertEqual(result.stderr,
                            b'shapeledger: input rejected (line byte limit must be smaller than sys.maxsize)\n')


class OutputErrors(unittest.TestCase):
    def assert_output_error(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b'shapeledger: output failed (', result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertNotIn(b'Traceback', result.stderr)
        self.assertNotIn(b'private', result.stderr)

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX descriptor inheritance')
    def test_stdout_closed_before_interpreter_start(self):
        # exec starts a fresh interpreter with fd 1 absent, so stdout is None.
        launcher = ('import os, sys; os.close(1); '
                    'os.execv(sys.executable, [sys.executable, "-m", "shapeledger"] + sys.argv[1:])')
        with tempfile.TemporaryDirectory() as tmp:
            base, candidate = Path(tmp) / 'base.json', Path(tmp) / 'candidate.json'
            base.write_text(json.dumps(profile(io.BytesIO(b'1'))))
            candidate.write_text(json.dumps(profile(io.BytesIO(b'true'))))
            commands = [
                ['profile', '-'],
                ['compare', str(base), str(candidate)],
                ['compare', str(base), str(candidate), '--fail-on', 'added_type'],
            ]
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, '-c', launcher] + command,
                        input=b'{}\n', capture_output=True)
                    self.assert_output_error(result)
                    self.assertEqual(result.stdout, b'')

    def test_closed_stdout_stream(self):
        result = subprocess.run(
            [sys.executable, '-c',
             'import sys; from shapeledger.__main__ import main; '
             'sys.stdout.close(); sys.exit(main(["profile", "-"]))'],
            input=b'{}\n', capture_output=True)
        self.assert_output_error(result)
        self.assertEqual(result.stdout, b'')

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX descriptor inheritance')
    def test_stdin_closed_before_interpreter_start(self):
        result = subprocess.run(
            [sys.executable, '-c',
             'import os, sys; os.close(0); '
             'os.execv(sys.executable, [sys.executable, "-m", "shapeledger", "profile", "-"])'],
            capture_output=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'shapeledger: input rejected (OSError)\n')

    def test_preclosed_stdout_descriptor(self):
        result = subprocess.run(
            [sys.executable, '-c',
             'import os, sys; from shapeledger.__main__ import main; '
             'os.close(sys.stdout.fileno()); sys.exit(main(["profile", "-"]))'],
            input=b'{}\n', capture_output=True)
        self.assert_output_error(result)
        self.assertEqual(result.stdout, b'')

    def test_closed_pipe_small_and_large_output(self):
        for data in (b'{}\n', json.dumps({f'private{i}': i for i in range(400)}).encode()):
            with self.subTest(size=len(data)):
                reader, writer = os.pipe()
                os.close(reader)
                with os.fdopen(writer, 'wb') as output:
                    result = subprocess.run(
                        [sys.executable, '-m', 'shapeledger', 'profile', '-'],
                        input=data, stdout=output, stderr=subprocess.PIPE)
                self.assert_output_error(result)
                self.assertIn(b'BrokenPipeError', result.stderr)

    @unittest.skipUnless(Path('/dev/full').exists(), 'requires /dev/full')
    def test_full_device_profile_small_and_large_output(self):
        for data in (b'{}\n', json.dumps({f'private{i}': i for i in range(400)}).encode()):
            with self.subTest(size=len(data)), open('/dev/full', 'wb') as output:
                result = subprocess.run(
                    [sys.executable, '-m', 'shapeledger', 'profile', '-'],
                    input=data, stdout=output, stderr=subprocess.PIPE)
                self.assert_output_error(result)

    @unittest.skipUnless(Path('/dev/full').exists(), 'requires /dev/full')
    def test_output_error_overrides_compare_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, candidate = Path(tmp) / 'base.json', Path(tmp) / 'candidate.json'
            base.write_text(json.dumps(profile(io.BytesIO(b'1'))))
            candidate.write_text(json.dumps(profile(io.BytesIO(b'true'))))
            for gate in ([], ['--fail-on', 'added_type']):
                with self.subTest(gate=gate), open('/dev/full', 'wb') as output:
                    result = subprocess.run(
                        [sys.executable, '-m', 'shapeledger', 'compare', str(base), str(candidate)] + gate,
                        stdout=output, stderr=subprocess.PIPE)
                    self.assert_output_error(result)


if __name__ == '__main__':
    unittest.main()
