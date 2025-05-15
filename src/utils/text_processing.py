import json
import re


def truncate_middle(
    text: str,
    max_len: int = 2000,
    placeholder: str = "\n<clipboard too long; truncated>\n",
    boundary_threshold: int = 100,
) -> str:
    """
    Truncate `text` by cutting out the middle and inserting `placeholder`.
    - If `len(text) <= max_len`, returns it unchanged.
    - Otherwise, keeps ~half of chars before and after the cut,
      then extends each cut to preserve full lines (or, if no newline,
      to the nearest space).
    - May go a bit over max_len; will never go under.
    - Uses boundary_threshold to limit how far to extend when finding boundaries.
    """
    if len(text) <= max_len:
        return text

    # split evenly
    half = (max_len - len(placeholder)) // 2
    head = text[:half]
    tail = text[-half:]

    # 1. extend head forward to end of the current line
    if not head.endswith("\n"):
        nxt = text.find("\n", half)
        if nxt != -1 and nxt - half <= boundary_threshold:
            head = text[: nxt + 1]
        else:
            # no newline or newline too far -> try the last space before half
            sp = head.rfind(" ")
            if sp != -1:
                head = head[: sp + 1]

    # 2. extend tail backward to start of the current line
    if not tail.startswith("\n"):
        start = len(text) - half
        prev = text.rfind("\n", 0, start)
        if prev != -1 and start - prev <= boundary_threshold:
            tail = text[prev + 1 :]
        else:
            # no newline or newline too far -> try the first space after start
            sp = text.find(" ", start)
            if sp != -1 and sp - start <= boundary_threshold:
                tail = text[sp + 1 :]

    return head + placeholder + tail


def extract_json(text: str, tag: str) -> str:
    """
    Extracts the value of a given JSON tag from LLM-output text, handling cases where the JSON
    block may be truncated by maximum length (interrupted output).
    - Uses extract_json_block to extract the JSON object first
    - Then attempts to extract the specific tag value
    - Falls back to regex-based extraction for partial matches
    - Returns the extracted value or an empty string.
    """
    # First try to extract a proper JSON object using extract_json_block
    json_block = extract_json_block(text)

    # If we got a valid JSON block, try parsing it directly
    if json_block is not None:
        try:
            data = json.loads(json_block)
            val = data.get(tag, "")
            return val if isinstance(val, str) else json.dumps(val)
        except json.JSONDecodeError:
            pass

    # Fall back to regex extraction (works on both the JSON block or original text)
    raw = json_block if json_block is not None else text

    # 1. Complete or truncated string patterns
    m_full = re.search(rf'"{tag}"\s*:\s*"((?:\\.|[^"])*)"', raw)
    if m_full:
        return m_full.group(1)
    m_trunc = re.search(rf'"{tag}"\s*:\s*"((?:\\.|[^"])*)$', raw)
    if m_trunc:
        return m_trunc.group(1)

    # 2. Non-string values
    m_nonstr = re.search(rf'"{tag}"\s*:\s*([\w\.\-+]+)', raw)
    if m_nonstr:
        return m_nonstr.group(1)

    return ""


def extract_json_block(text: str) -> str | None:
    """
    Extracts the first JSON block from a given text.
    - Prioritizes ```json fenced blocks.
    - Falls back to finding JSON objects starting with '{'.
    - Handles potentially truncated JSON by balancing braces.
    - Returns the extracted JSON string or None if not found.
    """
    # Prioritize ```json fenced blocks
    fence_match = re.search(r"```json\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    # Fallback: try to find a JSON object starting from the first '{'
    obj_match = re.search(r"^\s*(\{.*)", text, re.DOTALL)
    if not obj_match:
        return None

    raw_json_text = obj_match.group(1)
    # Attempt to balance braces for a potentially truncated object
    depth = 0
    in_string = False
    escape_char = False
    end_index = -1
    start_index = -1

    for i, char in enumerate(raw_json_text):
        if start_index == -1 and char == "{":
            start_index = i  # Mark the actual start of the JSON object

        if start_index == -1:  # Skip characters before the first '{'
            continue

        if escape_char:
            escape_char = False
        elif char == "\\":
            escape_char = True
        elif char == '"':
            in_string = not in_string
        elif not in_string:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_index = i + 1
                    break

    if start_index != -1 and end_index != -1:
        return raw_json_text[start_index:end_index]
    elif start_index != -1:  # Potentially truncated
        balanced_text = raw_json_text[start_index:]
        if depth > 0:
            balanced_text += "}" * depth
        return balanced_text

    return None
