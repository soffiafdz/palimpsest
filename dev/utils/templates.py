"""
templates.py
------------
Template reading and variable substitution for wiki entity generation.

Provides functionality to:
- Read Lua template files
- Substitute {{variables}} with data from Python
- Handle multi-line content blocks

Templates are stored in dev/lua/palimpsest/templates/ and use {{variable}} syntax.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Dict, Any, List

# Template directory path
TEMPLATE_DIR = Path(__file__).parent.parent / "lua" / "palimpsest" / "templates"


def read_template(template_name: str) -> str:
    """
    Read a template file from the templates directory.

    Args:
        template_name: Name of template (without .template extension)
                      e.g., "person", "location", "event"

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    template_path = TEMPLATE_DIR / f"{template_name}.template"

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    return template_path.read_text(encoding="utf-8")


def substitute_variables(template: str, variables: Dict[str, Any]) -> str:
    """
    Substitute {{variables}} in template with provided values.

    Args:
        template: Template string with {{variable}} placeholders
        variables: Dictionary mapping variable names to their values
                  Values can be:
                  - str: inserted as-is
                  - List[str]: joined with newlines
                  - None/empty: replaced with empty string

    Returns:
        Template with all variables substituted

    Example:
        >>> template = "# {{title}}\\n\\n{{content}}"
        >>> vars = {"title": "My Page", "content": ["Line 1", "Line 2"]}
        >>> substitute_variables(template, vars)
        '# My Page\\n\\nLine 1\\nLine 2'
    """
    result = template

    for var_name, value in variables.items():
        placeholder = f"{{{{{var_name}}}}}"

        # Convert value to string based on type
        if value is None or value == "":
            replacement = ""
        elif isinstance(value, list):
            replacement = "\n".join(str(item) for item in value)
        else:
            replacement = str(value)

        result = result.replace(placeholder, replacement)

    return result


def render_template(template_name: str, variables: Dict[str, Any]) -> List[str]:
    """
    Read template and substitute variables, returning lines for wiki output.

    This is the main entry point for wiki entity generation.

    Args:
        template_name: Name of template (without .template extension)
        variables: Dictionary of variable names to values

    Returns:
        List of lines ready to write to wiki file

    Example:
        >>> vars = {
        ...     "name": "Alice",
        ...     "category": "Friend",
        ...     "appearances": ["- [[2024-01-01|First meeting]]"]
        ... }
        >>> lines = render_template("person", vars)
    """
    template = read_template(template_name)
    content = substitute_variables(template, variables)
    return content.splitlines()
