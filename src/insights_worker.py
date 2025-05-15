import sqlite3
from datetime import datetime, timedelta, timezone
import pytz
import os
import re
from collections import defaultdict
from openai import OpenAI
from typing import List, Tuple, Dict, Any
from config.env_validate import validate_env
import numpy as np
from dotenv import load_dotenv
import json
from src.utils.text_processing import extract_json_block

# Load configuration from .env
validate_env()
load_dotenv(override=True)

# Core Configuration
# TODO: Add new constants to .env.example file

LOCAL_TIMEZONE_STR: str = os.getenv("LOCAL_TIMEZONE", "America/Chicago")
DB_PATH: str = os.getenv("DB_PATH", "data/clipboard.db")
HOURS_TO_ANALYZE: int = int(os.getenv("HOURS_TO_ANALYZE", "24"))

# Time Proximity Algorithm Configuration
DEFAULT_G_SECONDS: int = int(os.getenv("DEFAULT_G_SECONDS", "1200"))  # 20 minutes
TIME_PROXIMITY_NORMALIZATION_FACTOR: float = float(
    os.getenv("TIME_PROXIMITY_NORMALIZATION_FACTOR", "1.2")
)

# Display Configuration
CONTENT_TRUNCATE_LENGTH: int = int(os.getenv("CONTENT_TRUNCATE_LENGTH", "200"))

# OpenAI API Configuration
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL: str = os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1")
INSIGHTS_MODEL: str = os.getenv(
    "INSIGHTS_MODEL", "gpt-4o"
)  # Model for generating insights
INSIGHTS_MAX_TOKENS: int = int(os.getenv("INSIGHTS_MAX_TOKENS", "4000"))
INSIGHTS_TEMPERATURE: float = float(os.getenv("INSIGHTS_TEMPERATURE", "0.3"))

# System prompt for the LLM
INSIGHTS_SYSTEM_PROMPT: str = os.getenv(
    "INSIGHTS_SYSTEM_PROMPT",
    """You are an expert productivity analyst. Your primary goal is to meticulously analyze the provided clipboard activity log.
You MUST return a single, valid JSON object adhering strictly to the schema provided in the user's prompt.
Do NOT include any conversational preamble, explanations, apologies, or any text outside of the JSON object.
The descriptions and pattern analysis should be insightful and presented in a conversational and friendly tone, as if explaining to a colleague.
Pay close attention to the sequential IDs provided for each entry and use them accurately when populating the 'ids' field for tasks.""",
)

# Define the schema for the LLM's JSON output
# 'type' can be "list" or "str".
# If "list", 'schema' is a list of strings, where each string is an example of an item.
# If "str", 'schema' is a single string representing the expected string content or placeholder.
# TODO: Allow customizable schema definition
INSIGHTS_LLM_SCHEMA_DEFINITION: Dict[str, Dict[str, Any]] = {
    "tasks": {
        "type": "list",
        "schema": [  # List of example items (here, one example of a task object string)
            """{
    "name": "Task name",
    "description": "Detailed description of the task",
    "ids": "[1, 5-9, 12]"      // Use sequential ID ranges from this log. Must be complete and accurate.
            }"""
        ],
        "comment": "// Add all essential tasks from the day",
    },
    "timeline": {
        "type": "list",
        "schema": [  # List of example items
            """{
      "period": "HH:MM - HH:MM", // e.g., "09:00 - 10:30"
      "description": "Detailed description of clipboard usage and activities during this time window"
    }"""
        ],
        "comment": "// Cover all meaningful activity blocks throughout the day",
    },
    "keywords": {
        "type": "list",
        "schema": [  # List of example items (strings)
            '"💻 Programming"',
            '"📝 Notes"',
            '"🔍 Research"',
        ],
        "comment": "// 3 total max, each prefixed with an emoji",
    },
    "pattern": {
        "type": "str",
        "schema": "Description of patterns in clipboard usage today",  # Placeholder/instruction
        "comment": "// Describe patterns in clipboard usage in a friendly and insightful tone. Think out loud about the flow of activities.",
    },
    "recommendation": {
        "type": "str",
        "schema": "Suggestions for improving workflow based on clipboard data",  # Placeholder/instruction
        "comment": "// Offer specific, honest, and useful suggestions for improving my workflow based on observed clipboard behavior. Be constructive.",
    },
}

try:
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE_URL)
except Exception as e:
    print(
        f"Error initializing OpenAI client: {e}. Please check your API key and base URL."
    )
    client = None


# --- Helper Functions ---


def db_connect(db_path: str) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    """
    Establishes a connection to the SQLite database.

    Parameters:
    - db_path: Path to the SQLite database file

    Returns:
    - A tuple containing the database connection and cursor objects

    Raises:
    - sqlite3.Error: If connection to the database fails
    """
    try:
        print(f"Connecting to database at {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        return conn, cursor
    except sqlite3.Error as e:
        print(f"Error connecting to database at {db_path}: {e}")
        raise


def fetch_entries_from_db(
    cursor: sqlite3.Cursor, hours: int = 24
) -> Tuple[List[Tuple], datetime]:
    """
    Fetches clipboard entries from the database from the last specified hours.

    Parameters:
    - cursor: An active SQLite cursor object
    - hours: Number of hours to look back from current time. Default is 24 hours.

    Returns:
    - A tuple containing:
      - List of database entries (each as a tuple of id, timestamp, content, summary, type)
      - Current UTC datetime object (used for calculating relative times)
    """
    now_utc = datetime.now(timezone.utc)
    time_cutoff_dt = now_utc - timedelta(hours=hours)
    time_cutoff_iso_str = time_cutoff_dt.isoformat()

    cursor.execute(
        """
        SELECT id, timestamp, content, summary, type 
        FROM clipboard 
        WHERE timestamp > ? 
        ORDER BY timestamp ASC
    """,
        (time_cutoff_iso_str,),
    )
    return cursor.fetchall(), now_utc


def calculate_adaptive_g_threshold(
    all_processed_entries: List[Dict[str, Any]], default_g: int
) -> float:
    """
    Calculates the adaptive time threshold 'G' (90th percentile of intra-clipboard gaps).

    Algorithm explanation:
    1. Sorts all clipboard entries chronologically
    2. Calculates time gaps between consecutive entries in seconds
    3. Computes the 90th percentile of these gaps as the adaptive threshold
    4. Returns this adaptive threshold or the default value if calculation isn't possible

    The adaptive threshold represents a "natural break" in clipboard activity -
    gaps larger than this threshold likely indicate distinct activity sessions.

    Parameters:
    - all_processed_entries: List of processed clipboard entries with datetime objects
    - default_g: Fallback threshold value (in seconds) if calculation fails

    Returns:
    - Adaptive time threshold in seconds (90th percentile of observed gaps)
    """
    sorted_entries = sorted(
        [e for e in all_processed_entries if e.get("dt_local")],
        key=lambda x: x["dt_local"],
    )

    gaps_in_seconds: List[float] = []
    if len(sorted_entries) > 1:
        for i in range(len(sorted_entries) - 1):
            gap = (
                sorted_entries[i + 1]["dt_local"] - sorted_entries[i]["dt_local"]
            ).total_seconds()
            if gap > 0:
                gaps_in_seconds.append(gap)

    if gaps_in_seconds:
        g_adaptive = float(np.percentile(gaps_in_seconds, 90))
        print(f"Calculated G (90th percentile gap): {g_adaptive:.2f} seconds")
        return g_adaptive if g_adaptive > 0 else float(default_g)
    else:
        print(f"Not enough data for G calculation, using default: {default_g} seconds")
        return float(default_g)


def process_db_entries(
    raw_db_entries: List[Tuple], local_tz_obj: pytz.BaseTzInfo
) -> List[Dict[str, Any]]:
    """
    Processes raw database entries by cleaning types and converting timestamps to local time.

    Parameters:
    - raw_db_entries: List of tuples from database (id, timestamp, content, summary, type)
    - local_tz_obj: pytz timezone object for converting UTC timestamps to local time

    Returns:
    - List of standardized dictionary objects representing processed clipboard entries
    """
    processed_entries_list: List[Dict[str, Any]] = []
    for db_id, timestamp_str, content, summary, entry_type in raw_db_entries:
        clean_summary = (
            None
            if summary in ("summarizing...", "FAIL", None, "None", "null")
            or (isinstance(summary, str) and re.match(r"FAIL-\d+", summary))
            else summary
        )
        clean_type = (
            None
            if entry_type in ("FAIL", "None", "null", None)
            or (isinstance(entry_type, str) and re.match(r"FAIL-\d+", entry_type))
            else entry_type
        )

        dt_local_obj: datetime | None = None
        time_str_local: str = "unknown time"

        try:
            dt_utc = datetime.fromisoformat(timestamp_str)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_local_obj = dt_utc.astimezone(local_tz_obj)
            time_str_local = dt_local_obj.strftime("%H:%M")
        except (ValueError, AttributeError) as e:
            print(
                f"Warning: Could not parse timestamp '{timestamp_str}' for db_id {db_id}: {e}"
            )
            pass

        processed_entries_list.append(
            {
                "db_id": db_id,
                "timestamp_iso": timestamp_str,
                "dt_local": dt_local_obj,
                "time_str": time_str_local,
                "content": content,
                "type": clean_type,
                "summary": clean_summary,
            }
        )
    return processed_entries_list


def group_processed_entries(
    processed_entries_list: List[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str], List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    Groups processed entries into typed (with known type and summary) and untyped categories.

    Parameters:
    - processed_entries_list: List of processed dictionary objects from process_db_entries

    Returns:
    - A tuple containing:
      - Dictionary mapping (type, summary) tuples to lists of related entries
      - List of individual untyped entries needing further processing
    """
    typed_combined_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(
        list
    )
    individual_untyped_entries: List[Dict[str, Any]] = []

    for entry_data in processed_entries_list:
        if entry_data["type"] and entry_data["summary"]:
            key = (entry_data["type"], entry_data["summary"])
            typed_combined_groups[key].append(entry_data)
        else:
            individual_untyped_entries.append(entry_data)

    for key in typed_combined_groups:
        typed_combined_groups[key].sort(key=lambda x: x["timestamp_iso"])
    individual_untyped_entries.sort(key=lambda x: x["timestamp_iso"])
    return typed_combined_groups, individual_untyped_entries


def form_dynamic_untyped_blocks(
    individual_untyped_entries: List[Dict[str, Any]],
    g_adaptive_threshold: float,
    normalization_factor: float,
) -> List[List[Dict[str, Any]]]:
    """
    Forms blocks of untyped entries based on time proximity.

    Algorithm explanation:
    1. Groups untyped clipboard entries into coherent blocks based on temporal proximity
    2. Uses an adaptive time threshold (g_adaptive_threshold) to determine block boundaries
    3. Calculates a "time score" for each pair of consecutive entries:
       - Score = 1.0 - (gap_seconds / (normalization_factor * g_adaptive_threshold))
       - Score ranges from 0.0 (far apart) to 1.0 (very close or simultaneous)
    4. When time_score = 0.0 (entries too far apart), a new block is started

    Parameters:
    - individual_untyped_entries: List of entries without type/summary metadata
    - g_adaptive_threshold: Time threshold in seconds (90th percentile of all gaps)
    - normalization_factor: Multiplier that adjusts the threshold sensitivity

    Returns:
    - A list of blocks, where each block is a list of temporally related entries
    """
    if not individual_untyped_entries:
        return []
    dynamically_blocked_groups: List[List[Dict[str, Any]]] = []
    current_block: List[Dict[str, Any]] = [individual_untyped_entries[0]]

    for i in range(1, len(individual_untyped_entries)):
        l_entry_data = current_block[-1]
        r_entry_data = individual_untyped_entries[i]
        l_end_time = l_entry_data.get("dt_local")
        r_start_time = r_entry_data.get("dt_local")
        time_score = 0.0
        gap_seconds = float("inf")

        if l_end_time and r_start_time:
            gap_seconds = (r_start_time - l_end_time).total_seconds()
            if g_adaptive_threshold > 0:
                time_score = max(
                    0.0,
                    1.0 - gap_seconds / (normalization_factor * g_adaptive_threshold),
                )
            elif gap_seconds <= 0:
                time_score = 1.0

        if time_score == 0.0 and gap_seconds > 0:
            dynamically_blocked_groups.append(list(current_block))
            current_block = [r_entry_data]
        else:
            current_block.append(r_entry_data)
    if current_block:
        dynamically_blocked_groups.append(list(current_block))
    return dynamically_blocked_groups


def build_master_list_for_final_sorting(
    typed_combined_groups: Dict[Tuple[str, str], List[Dict[str, Any]]],
    dynamically_blocked_untyped_groups: List[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Prepares a master list for final chronological sorting across all entry types.

    Algorithm explanation:
    1. Combines typed entry groups and dynamic untyped blocks into a unified format
    2. For each typed group, finds the earliest timestamp and collects all database IDs
    3. For each untyped block, preserves the entire entry list and earliest timestamp
    4. Sorts all items chronologically using the earliest timestamp in each group/block

    This function creates a time-ordered master list that preserves the grouping
    structure while ensuring chronological sorting for final presentation.

    Parameters:
    - typed_combined_groups: Dictionary of typed entries grouped by (type, summary)
    - dynamically_blocked_untyped_groups: List of dynamically formed blocks of untyped entries

    Returns:
    - A chronologically sorted master list with standardized structure for all entries
    """
    master_list: List[Dict[str, Any]] = []
    for (entry_type, summary), entries_list in typed_combined_groups.items():
        if not entries_list:
            continue
        earliest_dt_local = (
            min(e["dt_local"] for e in entries_list if e["dt_local"])
            if any(e["dt_local"] for e in entries_list)
            else None
        )
        db_ids = [e["db_id"] for e in entries_list]
        time_strs = sorted(list(set(e["time_str"] for e in entries_list)))
        combined_time_display = "/".join(time_strs)
        master_list.append(
            {
                "item_kind": "typed_group",
                "earliest_dt_local": earliest_dt_local,
                "type": entry_type,
                "summary": summary,
                "db_ids": db_ids,
                "combined_time_display": combined_time_display,
            }
        )
    for untyped_block in dynamically_blocked_untyped_groups:
        if not untyped_block:
            continue
        earliest_dt_local_in_block = (
            min(e["dt_local"] for e in untyped_block if e["dt_local"])
            if any(e["dt_local"] for e in untyped_block)
            else None
        )
        master_list.append(
            {
                "item_kind": "untyped_block",
                "earliest_dt_local": earliest_dt_local_in_block,
                "entries_in_block": untyped_block,
            }
        )
    master_list.sort(
        key=lambda x: x["earliest_dt_local"]
        if x["earliest_dt_local"]
        else datetime.min.replace(tzinfo=pytz.utc)
    )
    return master_list


def assign_sequential_ids_and_prepare_prompt_data(
    sorted_master_list: List[Dict[str, Any]],
) -> Tuple[Dict[int, List[int]], Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """
    Assigns sequential IDs and prepares structured data for prompt formatting.

    Parameters:
    - sorted_master_list: Chronologically sorted list from build_master_list_for_final_sorting

    Returns:
    - A tuple containing:
      - Mapping from sequential IDs to original database IDs
      - Dictionary of typed entries organized by type
      - List of untyped blocks with formatted headers and content
    """
    seq_to_db_ids_map: Dict[int, List[int]] = {}
    prompt_typed_entries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    prompt_untyped_blocks: List[Dict[str, Any]] = []
    current_sequential_id = 1

    for item_data in sorted_master_list:
        if item_data["item_kind"] == "typed_group":
            seq_to_db_ids_map[current_sequential_id] = item_data["db_ids"]
            prompt_typed_entries[item_data["type"]].append(
                {
                    "seq_id": current_sequential_id,
                    "time_display": item_data["combined_time_display"],
                    "summary": item_data["summary"],
                }
            )
            current_sequential_id += 1
        elif item_data["item_kind"] == "untyped_block":
            block_entries_for_prompt: List[Dict[str, Any]] = []
            for entry_in_block in item_data["entries_in_block"]:
                seq_to_db_ids_map[current_sequential_id] = [entry_in_block["db_id"]]
                content = entry_in_block["content"]
                display_text = (
                    content[:CONTENT_TRUNCATE_LENGTH] + "..."
                    if len(content) > CONTENT_TRUNCATE_LENGTH
                    else content
                )
                block_entries_for_prompt.append(
                    {
                        "seq_id": current_sequential_id,
                        "text": display_text,
                        "time_str": entry_in_block["time_str"],
                    }
                )
                current_sequential_id += 1
            if block_entries_for_prompt:
                start_time = block_entries_for_prompt[0]["time_str"]
                end_time = block_entries_for_prompt[-1]["time_str"]
                header = f"Activity Block ({start_time} - {end_time})"
                if start_time == end_time and len(block_entries_for_prompt) == 1:
                    header = f"Activity Entry at {start_time}"
                prompt_untyped_blocks.append(
                    {
                        "block_header": header,
                        "entries": block_entries_for_prompt,
                        "num_entries": len(block_entries_for_prompt),
                    }
                )
    for key in prompt_typed_entries:
        prompt_typed_entries[key].sort(key=lambda x: x["seq_id"])
    return seq_to_db_ids_map, prompt_typed_entries, prompt_untyped_blocks


def format_llm_prompt(
    start_time_str_local: str,
    local_timezone_name: str,
    prompt_typed_entries: Dict[str, List[Dict[str, Any]]],
    prompt_untyped_blocks: List[Dict[str, Any]],
    schema_definition: Dict[str, Dict[str, Any]],
) -> str:
    """
    Formats the complete prompt string for the LLM, including dynamic schema.

    Parameters:
    - start_time_str_local: Start time for the analysis period in local timezone
    - local_timezone_name: Name of the local timezone for context
    - prompt_typed_entries: Structured dictionary of typed entries by category
    - prompt_untyped_blocks: List of activity blocks containing untyped entries
    - schema_definition: Definition of the desired response JSON schema

    Returns:
    - Complete formatted prompt string ready to send to the LLM
    """
    prompt_parts: List[str] = [
        f"# My Clipboard Activity Analysis",
        f"Below is a log of my clipboard activities from {start_time_str_local} ({local_timezone_name}). Please analyze these entries to identify patterns, tasks, and provide insights.",
        "\nWhen identifying tasks, synthesize information from both the 'Content By Type' section (summarized/typed entries) and the 'Uncategorized Content' section (raw snippets in Activity Blocks). Use sequential IDs to link tasks to entries.\n",
    ]

    if prompt_typed_entries:
        prompt_parts.append("## Content By Type\n")
        for entry_type_key in sorted(prompt_typed_entries.keys()):
            entries_for_type = prompt_typed_entries[entry_type_key]
            prompt_parts.append(
                f"### {entry_type_key.title()} ({len(entries_for_type)} entries)\n"
            )
            for entry_detail in entries_for_type:
                prompt_parts.append(
                    f"[{entry_detail['seq_id']}] **{entry_detail['time_display']}** {entry_detail['summary']}\n"
                )

    if prompt_untyped_blocks:
        prompt_parts.append(
            "\n## Uncategorized Content (Grouped by Activity Proximity)\n"
        )
        for block_data in prompt_untyped_blocks:
            prompt_parts.append(
                f"### {block_data['block_header']} ({block_data['num_entries']} entries)\n"
            )
            for entry_detail in block_data["entries"]:
                prompt_parts.append(
                    f"[{entry_detail['seq_id']}] {entry_detail['text']}\n"
                )

    # Dynamically build JSON schema for the prompt
    json_schema_str_parts = ["{"]
    field_defs = []
    for i, (field_name, data) in enumerate(schema_definition.items()):
        field_type = data["type"]
        schema_examples = data[
            "schema"
        ]  # This is now a list for "list" type, or a string for "str" type
        comment = data.get("comment", "")

        current_field_def_lines = []
        if field_type == "list":
            current_field_def_lines.append(f'  "{field_name}": [')
            for k, example_item_str in enumerate(
                schema_examples
            ):  # schema_examples is a list of strings
                # Indent each line of the example item string if it's multi-line (like a JSON object string)
                indented_example_item = "    " + example_item_str.replace(
                    "\n", "\n    "
                )
                current_field_def_lines.append(
                    indented_example_item
                    + ("," if k < len(schema_examples) - 1 else "")
                )
            current_field_def_lines.append(f"  ]")
        else:  # str
            # schema_examples is a single string for type "str"
            current_field_def_lines.append(f'  "{field_name}": "{schema_examples}"')

        # Add comment to the last line of the current field definition
        if comment:
            current_field_def_lines[-1] += f" {comment}"

        field_defs.append("\n".join(current_field_def_lines))

    json_schema_str_parts.append(",\n".join(field_defs))
    json_schema_str_parts.append("\n}")  # Added \n before closing brace
    full_json_schema_for_prompt = "\n".join(json_schema_str_parts)

    final_instructions = f"""\n#### ⚙️ Format Requirements
Return a single valid JSON object with the exact schema shown below. All fields are **required**. Do **not** include any explanations, markdown, or extra text outside the JSON.
#### 📐 JSON Schema
```json\n{full_json_schema_for_prompt}\n```"""
    prompt_parts.append(final_instructions)
    return "\n".join(prompt_parts)


def get_llm_insights(
    openai_client: OpenAI | None,
    model_name: str,
    max_tokens: int,
    system_prompt_text: str,
    user_prompt_text: str,
    temperature: float,
) -> str:
    """
    Sends the prompt to the LLM and gets the response.

    Parameters:
    - openai_client: Initialized OpenAI client object
    - model_name: Name of the model to use (e.g., "gpt-4o")
    - max_tokens: Maximum number of tokens in the response
    - system_prompt_text: Instructions for the AI's role and behavior
    - user_prompt_text: The main prompt with clipboard data
    - temperature: Controls randomness (0.0-1.0, lower is more deterministic)

    Returns:
    - The LLM's response as a string, or an error message in JSON format
    """
    if openai_client is None:
        return '{"error": "OpenAI client not initialized. Check API key and base URL."}'
    messages = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": user_prompt_text},
    ]
    try:
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        insights = response.choices[0].message.content
        if insights is None or not insights.strip():
            raise ValueError("Empty insights received.")
        return insights.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return f'{{"error": "API call failed", "details": "{str(e)}"}}'


def main():
    """
    Main function to orchestrate the complete clipboard analysis pipeline.

    Steps:
    1. Fetch recent entries based on configured time window (24 hrs by default)
    2. Process and clean the raw database entries
    3. Calculate adaptive time threshold for proximity grouping
    4. Group entries by type and form dynamic blocks of untyped content
    5. Group untyped entries into blocks based on time proximity
    6. Assign sequential IDs to all entries for LLM processing
    7. Send the complete LLM prompt with instructions and schema
    8. Extract and validate the JSON response
    9. Substitute sequential IDs with original database IDs
    """
    print(f"Starting clipboard analysis at {datetime.now().isoformat()}")
    print(f"Using timezone: {LOCAL_TIMEZONE_STR}, DB: {DB_PATH}")

    local_tz_obj = pytz.timezone(LOCAL_TIMEZONE_STR)
    conn, cursor = db_connect(DB_PATH)

    try:
        raw_db_entries, now_utc = fetch_entries_from_db(cursor, hours=HOURS_TO_ANALYZE)
        start_time_str_local_for_prompt = (
            (now_utc - timedelta(hours=HOURS_TO_ANALYZE))
            .astimezone(local_tz_obj)
            .strftime("%Y-%m-%d %H:%M")
        )

        if not raw_db_entries:
            print("No clipboard entries found.")
            return
        print(f"Fetched {len(raw_db_entries)} entries.")
        all_processed = process_db_entries(raw_db_entries, local_tz_obj)
        g_threshold = calculate_adaptive_g_threshold(all_processed, DEFAULT_G_SECONDS)
        typed_groups, untyped_individual = group_processed_entries(all_processed)
        dynamic_blocks = form_dynamic_untyped_blocks(
            untyped_individual, g_threshold, TIME_PROXIMITY_NORMALIZATION_FACTOR
        )
        master_sorted = build_master_list_for_final_sorting(
            typed_groups, dynamic_blocks
        )
        _seq_map, prompt_typed, prompt_untyped = (
            assign_sequential_ids_and_prepare_prompt_data(master_sorted)
        )

        insights_user_prompt = format_llm_prompt(
            start_time_str_local_for_prompt,
            LOCAL_TIMEZONE_STR,
            prompt_typed,
            prompt_untyped,
            INSIGHTS_LLM_SCHEMA_DEFINITION,
        )

        print("\n--- Generated Prompt for LLM---")
        print(insights_user_prompt)
        # For full prompt debugging:
        # with open("generated_prompt_debug.md", "w", encoding="utf-8") as f:
        #     f.write(insights_user_prompt)
        # print("Full prompt written to generated_prompt_debug.md")
        print("--- End of Prompt Preview ---\n")

        print("\n--- Extracted JSON Schema Definition from Prompt ---")
        # The schema is now built dynamically, so we extract it from the final prompt for verification
        # This regex looks for the ```json block specifically for the schema
        schema_format_match = re.search(
            r"#### 📐 JSON Schema\s*```json\s*(\{.*?\})\s*```",
            insights_user_prompt,
            re.DOTALL,
        )
        if schema_format_match:
            schema_block_in_prompt = schema_format_match.group(1)
            try:
                parsed_schema_dict = json.loads(schema_block_in_prompt)
                print(json.dumps(parsed_schema_dict, indent=2))
            except json.JSONDecodeError as e:
                print("Extracted schema block was:\n", schema_block_in_prompt)
        else:
            print(
                "Could not extract JSON schema block from the prompt using specific regex."
            )
        print("--- End of Extracted Schema ---\n")

        if client is None:
            print("OpenAI client not initialized. Skipping LLM insights.")
            return

        llm_response_str = get_llm_insights(
            client,
            INSIGHTS_MODEL,
            INSIGHTS_MAX_TOKENS,
            INSIGHTS_SYSTEM_PROMPT,
            insights_user_prompt,
            INSIGHTS_TEMPERATURE,
        )

        print("\n--- LLM Response ---")
        # Use the robust extract_json_block for the LLM's actual response
        extracted_llm_json_str = extract_json_block(llm_response_str)
        if extracted_llm_json_str:
            try:
                parsed_llm_json = json.loads(extracted_llm_json_str)
                pretty_llm_json = json.dumps(parsed_llm_json, indent=2)
                print(pretty_llm_json)
            except json.JSONDecodeError as e:
                print(f"LLM response content was not valid JSON after extraction: {e}")
                print("Extracted content was:\n", extracted_llm_json_str)
                print("\nOriginal LLM response was:\n", llm_response_str)
        else:
            print("Could not extract a JSON block from LLM response. Displaying raw:")
            print(llm_response_str)

    except Exception as e:
        print(f"An error occurred in main: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if "conn" in locals() and conn:
            conn.close()


if __name__ == "__main__":
    main()
