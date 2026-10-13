import argparse
import json
import os
import sys
from .core import KINDS, ShapeError, compare, profile, strict_json, validate


def main(argv=None):
    parser = argparse.ArgumentParser(description='Observe JSONL shapes without storing scalar values.')
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('profile')
    p.add_argument('input', help='UTF-8 JSONL file, or - for stdin')
    p.add_argument('--max-nodes', type=int, default=10000)
    p.add_argument('--max-depth', type=int, default=64)
    p.add_argument('--max-line-bytes', type=int, default=1048576)
    c = commands.add_parser('compare')
    c.add_argument('baseline')
    c.add_argument('candidate')
    c.add_argument('--fail-on', action='append', choices=sorted(KINDS), default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == 'profile':
            if args.input == '-':
                if sys.stdin is None:
                    raise OSError("stdin is unavailable")
                result = profile(sys.stdin.buffer, args.max_nodes, args.max_depth, args.max_line_bytes)
            else:
                with open(args.input, 'rb') as f:
                    result = profile(f, args.max_nodes, args.max_depth, args.max_line_bytes)
            code = 0
        else:
            def load(path):
                with open(path, 'rb') as f:
                    data = f.read(32 * 1024 * 1024 + 1)
                if len(data) > 32 * 1024 * 1024:
                    raise ShapeError('profile exceeds 32 MiB')
                p = strict_json(data.decode('utf-8'))
                validate(p)
                return p
            result = compare(load(args.baseline), load(args.candidate))
            code = int(any(c['kind'] in args.fail_on for c in result['changes']))
    except (OSError, ValueError, RecursionError) as exc:
        # Never echo source lines, scalar values, or filenames into diagnostics.
        detail = str(exc) if isinstance(exc, ShapeError) else type(exc).__name__
        print('shapeledger: input rejected (%s)' % detail, file=sys.stderr)
        return 2
    try:
        # Python uses None when stdout was absent at interpreter startup.
        if sys.stdout is None:
            raise OSError("stdout is unavailable")
        print(json.dumps(result, sort_keys=True, ensure_ascii=True, indent=2))
        # Catch buffered write failures before interpreter shutdown changes the
        # documented error status to 120 and emits an unsanitized diagnostic.
        sys.stdout.flush()
    except (OSError, ValueError) as exc:
        # Discard pending buffered output so shutdown cannot retry a failed sink.
        # dup2 retains stdout's descriptor and leaves other descriptors alone.
        try:
            target = sys.stdout.fileno()
            sink = os.open(os.devnull, os.O_WRONLY)
            # A previously closed stdout may be reused by os.open. In that
            # case stdout owns the replacement descriptor; do not close it.
            if sink != target:
                try:
                    os.dup2(sink, target)
                finally:
                    os.close(sink)
        except (OSError, ValueError, AttributeError):
            # Embedded callers may replace stdout with a descriptor-free stream.
            sys.stdout = None
        print('shapeledger: output failed (%s)' % type(exc).__name__, file=sys.stderr)
        return 2
    return code

if __name__ == '__main__':
    sys.exit(main())
