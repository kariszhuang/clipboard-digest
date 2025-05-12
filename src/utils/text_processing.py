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
    - Supports optional ```json``` fences.
    - Uses regex to capture complete or truncated string values, then balances braces if needed.
    - Returns the extracted value or an empty string.
    """
    # strip ```json fence if present
    fence = re.search(r"```json\s*(\{.*)", text, re.DOTALL)
    raw = fence.group(1) if fence else text

    # 1. complete or truncated string patterns
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

    # 3. Fallback: JSON load with brace balancing
    start = raw.find("{")
    if start == -1:
        return ""
    depth = 0
    in_str = False
    esc = False
    end_idx = None
    for i in range(start, len(raw)):
        ch = raw[i]
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
    snippet = raw[start : end_idx + 1] if end_idx is not None else raw[start:]
    if end_idx is None:
        if in_str:
            snippet += '"'
        snippet += "}" * depth
    try:
        data = json.loads(snippet)
        val = data.get(tag, "")
        return val if isinstance(val, str) else json.dumps(val)
    except json.JSONDecodeError:
        return ""
