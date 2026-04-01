"""
LLM response parser — the ONLY file the autoresearch agent modifies.

This module is loaded by train.py to parse raw LLM responses into clean JSON.
The pipeline handles: thinking blocks, XML wrappers, markdown fences,
preamble/postamble text, array unwrapping, and common JSON malformations.
"""

import ast
import json
import re
from typing import Any, Dict, Optional


def clean_thinking_blocks(content: str) -> str:
    """Remove <think>/<thinking> blocks from the response.

    If stripping would leave the response empty, try to extract JSON
    from inside the thinking block.
    """
    cleaned = re.sub(
        r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', content
    ).strip()
    if cleaned:
        return cleaned

    # Entire response was inside thinking tags — salvage JSON
    match = re.search(r'(\{[\s\S]*\})', content)
    if match:
        return match.group(1).strip()

    return cleaned


def extract_from_xml_tags(content: str) -> str:
    """Extract JSON from <json_output> or similar wrapper tags."""
    # Try <json_output> tags first
    match = re.search(
        r'<json_output>\s*([\s\S]*?)\s*</json_output>', content
    )
    if match:
        return match.group(1).strip()

    # Strip stray/partial tags
    content = re.sub(r'</?json_output>', '', content)
    content = re.sub(
        r'</?(?:response|output|result|answer|json)>', '', content
    )
    return content.strip()


def strip_markdown_fences(content: str) -> str:
    """Remove markdown code block fences (```json ... ```)."""
    content = re.sub(
        r'^```[^\n]*\n?', '', content.strip(), flags=re.IGNORECASE
    )
    content = re.sub(r'\n?```\s*$', '', content)
    return content.strip()


def extract_json_object(content: str) -> str:
    """Extract the first complete JSON object or array from a string.

    Handles preamble/postamble text by finding the outermost { } or [ ].
    """
    # Find first { or [
    obj_start = content.find('{')
    arr_start = content.find('[')

    if obj_start == -1 and arr_start == -1:
        return content

    # Pick whichever comes first
    if arr_start != -1 and (obj_start == -1 or arr_start < obj_start):
        start = arr_start
        open_char, close_char = '[', ']'
    else:
        start = obj_start
        open_char, close_char = '{', '}'

    # Walk forward to find matching close
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(content)):
        ch = content[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return content[start:i + 1]

    # No balanced match — return from start to end
    return content[start:]


def _strip_js_comments(content: str) -> str:
    """Remove JS comments (// and /* */) while preserving strings."""
    result = []
    i = 0
    in_string = False
    escape_next = False
    while i < len(content):
        ch = content[i]
        if escape_next:
            result.append(ch)
            escape_next = False
            i += 1
            continue
        if in_string:
            result.append(ch)
            if ch == '\\':
                escape_next = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue
        # Check for // single-line comment
        if ch == '/' and i + 1 < len(content) and content[i + 1] == '/':
            while i < len(content) and content[i] != '\n':
                i += 1
            continue
        # Check for /* block comment */
        if ch == '/' and i + 1 < len(content) and content[i + 1] == '*':
            i += 2
            while i + 1 < len(content) and not (
                content[i] == '*' and content[i + 1] == '/'
            ):
                i += 1
            i += 2  # skip */
            continue
        result.append(ch)
        i += 1
    return ''.join(result)


def fix_common_json_errors(content: str) -> str:
    """Fix common LLM JSON mistakes: trailing commas, single quotes,
    JS comments."""
    # Remove JS comments (string-aware)
    content = _strip_js_comments(content)
    # Remove trailing commas before } or ]
    content = re.sub(r',\s*([}\]])', r'\1', content)
    # Replace single quotes with double quotes (simple heuristic)
    # Only if the content doesn't parse as valid JSON already
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass
    # Try ast.literal_eval for Python-dict-like output (handles mixed quotes)
    try:
        obj = ast.literal_eval(content)
        return json.dumps(obj)
    except (ValueError, SyntaxError):
        pass
    # Fallback: naive single-quote replacement
    fixed = content.replace("'", '"')
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        return content


def unwrap_array(
    parsed: Any, expected_keys: Optional[tuple] = None
) -> Dict[str, Any]:
    """Unwrap arrays to dicts. Single-element arrays are unwrapped.
    Multi-element arrays use expected_keys to find the right element."""
    if not isinstance(parsed, list):
        return parsed if isinstance(parsed, dict) else {"raw": parsed}

    if len(parsed) == 1 and isinstance(parsed[0], dict):
        return parsed[0]

    if expected_keys is not None:
        for item in parsed:
            if isinstance(item, dict) and any(
                k in item for k in expected_keys
            ):
                return item

    return {"items": parsed}


def parse_llm_response(
    raw: str,
    expected_keys: Optional[tuple] = ("entities", "relationships"),
) -> Optional[Dict[str, Any]]:
    """
    Full parsing pipeline: thinking blocks -> XML tags -> markdown fences
    -> JSON extraction -> error fixing -> JSON parse -> array unwrap.

    Returns parsed dict or None on failure.
    """
    if not raw or not raw.strip():
        return None

    content = raw

    # Stage 1: Remove thinking blocks
    content = clean_thinking_blocks(content)
    if not content:
        return None

    # Stage 2: Extract from XML wrapper tags
    content = extract_from_xml_tags(content)

    # Stage 3: Strip markdown fences
    content = strip_markdown_fences(content)

    # Stage 4: Extract JSON object/array from surrounding text
    content = extract_json_object(content)

    # Stage 5: Fix common JSON errors
    content = fix_common_json_errors(content)

    # Stage 6: Parse
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None

    # Stage 7: Unwrap arrays
    if isinstance(parsed, (list, dict)):
        return unwrap_array(parsed, expected_keys)

    return None
