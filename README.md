# shapeledger

Review observed JSONL shape changes without storing scalar sample values. Useful for fixture updates, export pipelines, and CI checks where a full schema system is too much.

[简体中文](docs/README.zh-CN.md) · [Русский](docs/README.ru.md) · [Deutsch](docs/README.de.md)

## Quick start

Python 3.10+, no runtime dependencies. Run directly from this checkout:

```sh
python -m shapeledger profile examples/baseline.jsonl > /tmp/baseline.shape.json
python -m shapeledger profile examples/candidate.jsonl > /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json --fail-on added_type --fail-on removed_path --fail-on missing_increase
```

The last command intentionally exits 1 for these fixtures. To install the CLI, run `python -m pip install .`, then substitute `shapeledger` for `python -m shapeledger`. Build tools use setuptools; runtime uses only the standard library. Use `profile -` for binary stdin. Output is deterministic JSON on stdout; send it to a new file. Shell redirection can truncate an existing file even when input is rejected. Input is fully validated before any profile is emitted. An output failure can leave a partial file; discard it when the command exits 2.

## What is counted

Each nonblank input line must contain exactly one strict UTF-8 JSON value; any top-level JSON type is supported. Blank lines, BOM, duplicate keys, NaN, Infinity, overflowing floats and malformed records are errors. CRLF and a final line without a newline work. Diagnostics identify the invalid record line without echoing its contents.

Version 1 profiles contain `version`, `records` and a sorted `nodes` list. A node has `path`, `types`, `opportunities` and `array_items`. Type counts distinguish object, array, string, integer, number, boolean and null; `1` and `1.0` differ. Paths use typed segments: `[["key","users"],["items"],["key","name"]]`. Literal keys containing dots, slashes, `*`, empty text or `items` remain unambiguous.

- Root opportunities equal input records.
- An object-key child's opportunities equal observed **object instances of its parent**, not all records or all parent types.
- An array wildcard child's opportunities equal the total number of array elements; every element is observed once, including null.
- Missing count equals opportunities minus the sum of type counts. Null is present, never missing.
- `array_items` sums lengths of arrays at the node. An empty array creates no wildcard node. Fields inside item objects use only those object instances as their denominator.
- No observations means no node. A disappearing parent is reported as a removed path, not a fabricated zero rate.

Object keys and shape counts are retained. These may be sensitive, especially dynamic keys. This is data minimization, **not anonymization**. Scalar values are parsed transiently in memory but never included in output. Error messages omit source text and filenames.

## Comparison and CI policy

`compare` validates both profiles before comparing. It reports `added_path`, `removed_path`, `added_type`, `missing_increase` and `null_increase`. Existing paths compare rates using exact rational arithmetic; output rates are fractions such as `1/3`. Null rate uses opportunities, not presence. Any positive increase produces an event; there are no configurable numerical thresholds in version 0.1. Removed types are not reported. Newly added/removed paths get path events only, not additional type/rate events.

All events are reported regardless of gates. Repeating `--fail-on KIND` selects which events fail CI. Without a gate, comparison is informational.

| Exit | Meaning |
|---|---|
| 0 | Valid input; no selected gate fired |
| 1 | At least one selected drift gate fired |
| 2 | Invalid input/profile, limit violation, I/O or command usage error |

## Bounds and limits

Streaming is by record, not individual JSON token. Default line limit is 1 MiB **including newline** (`--max-line-bytes`), maximum unique nodes 10,000 (`--max-nodes`), maximum path depth 64 (`--max-depth`, root depth 0). Node/depth flags can lower but cannot raise format caps. Limits must be positive integers. The line limit must be smaller than Python’s platform-dependent `sys.maxsize`, leaving room for the extra byte used to detect overlong records; larger values are rejected before reading records. Memory scales with the largest permitted line and the retained path set, not just record count; arrays are pooled, keys are not normalized. Large or deeply nested records can be rejected by the Python parser before the shape limits. Compare limits each profile file to 32 MiB and validates exact fields, version, paths, counts and parent relationships. Profiles are evidence, not cryptographic attestations or full JSON Schemas. No schema validation, distribution inference, profile merging, field ignoring or numeric ranges are provided. Standard-library float parsing is used and scalar precision is irrelevant to shape counts. Output files require normal filesystem space. A full disk or closed pipe, including a buffered flush failure, returns exit 2 with a sanitized output-error diagnostic. This takes precedence over a comparison gate’s exit 0 or 1; a successful flush does not guarantee durable storage.

## Alternatives and development

[GenSON](https://github.com/wolverdude/GenSON) generates/merges JSON Schema. [DataProfiler](https://github.com/capitalone/DataProfiler) offers broader statistical and entity profiling. shapeledger instead records compact observed-shape counts with parent-relative missingness and explicit CI events. It does not replace either project or claim new schema-inference algorithms.

```sh
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

CI tests Python 3.10–3.13 and installation of a built wheel. Contributions should include regression tests and updates to all four language guides when semantics change. Synthetic examples only; do not commit private data. Potential future work: profile merging, path filters and explicit dynamic-key budgets. MIT licensed.

If stdout is already closed when Python starts, output also fails with the same sanitized diagnostic and exit 2, including when a comparison gate would otherwise return 0 or 1. An unavailable stdin for `profile -` is a sanitized input error (exit 2); a closed Python stdout stream is an output error (exit 2).
