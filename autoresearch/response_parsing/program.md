# AutoResearch: LLM Response Parsing Optimization

## Objective

Optimize the response parser in `parsers/response_parser.py` to maximize
successful JSON extraction from messy LLM outputs. The parser must handle
thinking blocks, XML wrappers, markdown fences, preamble text, malformed
JSON, and edge cases — all without making any LLM calls.

## How It Works

1. You read this file for research directions.
2. You modify **only** `parsers/response_parser.py`.
3. Run `python train.py` — it parses 38 pre-recorded LLM responses (see
   `eval_data/responses.json`) through your parser and scores against expected outputs.
4. Score is appended to `results/history.jsonl`.
5. Decide whether to keep or revert based on the metric.
6. Repeat.

**Key advantage**: No LLM calls needed. Each experiment runs in <1 second.
You can iterate extremely fast.

## Metric: parse_score

```
parse_score = 0.35 * exact_match
            + 0.25 * key_match
            + 0.20 * parse_rate
            + 0.20 * error_handling
```

- **exact_match**: fraction of success cases where output == expected (deep equality)
- **key_match**: fraction of success cases where top-level keys match expected
- **parse_rate**: fraction of success cases where parser returned non-None
- **error_handling**: fraction of error cases correctly returned as None

## Test Categories

| Category | Count | Description |
|----------|-------|-------------|
| clean | 6 | Valid JSON, possibly with escapes/unicode |
| markdown | 3 | JSON inside fenced code blocks (e.g. json language tag) |
| xml | 3 | JSON inside <json_output> or <response> tags |
| thinking | 5 | `<think>` and `<thinking>` blocks before/around JSON (see `clean_thinking_blocks`) |
| preamble | 2 | Natural language before/after JSON |
| complex | 6 | Multiple wrappers combined (thinking+fence+xml) |
| array | 2 | JSON objects wrapped in arrays |
| malformed | 8 | Trailing commas, single quotes, JS comments |
| error | 3 | Empty, no JSON, truncated (should return None) |

*(Totals: 38 cases — see `eval_data/responses.json`.)*

## Research Directions

### Round 1-5: Fix failing categories
- Run `python train.py` to see the baseline
- Focus on whichever category has the lowest score
- Common issues: double fences, preamble extraction, partial XML tags

### Round 6-10: Malformed JSON recovery
- Improve trailing comma removal (nested structures)
- Handle single quotes more robustly (don't break strings with apostrophes)
- Strip JS comments without breaking JSON strings containing //
- Consider using `ast.literal_eval` as fallback for Python-dict-like output

### Round 11-15: Edge case hardening
- Handle truncated JSON (close all open brackets)
- Handle JSON with literal newlines inside strings
- Handle mixed Unicode escapes
- Test against adversarial inputs (nested fences, think-inside-think)

### Round 16-20: Pipeline ordering
- Experiment with different stage ordering
- Test whether early JSON extraction (before tag stripping) helps
- Try multiple parse attempts with different strategies
- Add a "last resort" regex-based JSON extraction

### Round 21+: Performance
- Profile parsing time per case
- Remove unnecessary regex compilations (pre-compile)
- Minimize string copies
- Consider whether a state machine approach beats regex stacking

## Constraints

- **Only modify** `parsers/response_parser.py`
- Must return `None` for genuinely unparseable input (not empty dicts)
- No external dependencies (stdlib only: json, re, ast)
- Parser must be importable as a standalone module
- Keep total module under 300 lines

## Current Architecture

The parser pipeline has 7 stages:
1. `clean_thinking_blocks()` — Strip `<think>` / `<thinking>` … `</think>` / `</thinking>` via the same regex as in `response_parser.py`
2. `extract_from_xml_tags()` — Extract from <json_output> etc.
3. `strip_markdown_fences()` — Remove ``` wrappers
4. `extract_json_object()` — Find { } or [ ] in surrounding text
5. `fix_common_json_errors()` — Trailing commas, single quotes, comments
6. `json.loads()` — Parse
7. `unwrap_array()` — Unwrap single-element arrays

Each stage is a separate function. You can reorder, combine, or replace them.
