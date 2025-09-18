#!/usr/bin/env python3
@staticmethod
def parse_markdown_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract YAML frontmatter metadata from a Markdown file.

    Args:
        file_path (str): Path to the Markdown file.

    Returns:
        Dict[str, Any]: Parsed metadata dictionary.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---\n"):
            end_marker = content.find("\n---\n", 4)
            if end_marker != -1:
                yaml_content = content[4:end_marker]
                metadata = yaml.safe_load(yaml_content)
                return metadata or {}

    except Exception as e:
        print(f"[Markdown Parse Error] {file_path}: {e}")

    return {}


def update_markdown_file(self, file_path: str, metadata: Dict[str, Any]) -> bool:
    """Update markdown file with new metadata"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---\n"):
            end_marker = content.find("\n---\n", 4)
            if end_marker != -1:
                body_content = content[end_marker + 5 :]
            else:
                body_content = content[4:]
        else:
            body_content = content

        yaml_content = yaml.dump(metadata, default_flow_style=False, sort_keys=False)
        new_content = f"---\n{yaml_content}---\n{body_content}"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False


@staticmethod
def _extract_number(value: Any) -> float:
    """
    Extract numeric value from a string or number.

    Examples:
        "150 words" -> 150
        "2.5 min"   -> 2.5

    Args:
        value (Any): Input string or number.

    Returns:
        float: Extracted numeric value.
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        import re

        match = re.search(r"(\d+(?:\.\d+)?)", value)
        if match:
            return float(match.group(1))
    return 0.0


# --- helpers ---
def parse_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", " ") else None
    except ValueError:
        return None


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "", " ") else None
    except ValueError:
        return None


def normalize_str(value: Any) -> str | None:
    if not value or not str(value).strip():
        return None
    return str(value).strip()
