#!/usr/bin/env python3
"""
cli_utils.py
-------------------
Shared CLI utilities for Palimpsest commands.

Provides common functions used across multiple CLI scripts to reduce duplication
and ensure consistency.

Functions:
    setup_logger: Initialize PalimpsestLogger for CLI operations

Usage:
    from dev.core.cli_utils import setup_logger

    logger = setup_logger(log_dir, "my_component")
"""
from pathlib import Path
from dev.core.logging_manager import PalimpsestLogger


def setup_logger(log_dir: Path, component_name: str) -> PalimpsestLogger:
    """
    Setup logging for CLI operations.

    Creates the operations log directory if it doesn't exist and initializes
    a PalimpsestLogger instance for the specified component.

    Args:
        log_dir: Base log directory (typically from paths.LOG_DIR)
        component_name: Component identifier for logging (e.g., 'txt2md', 'yaml2sql')

    Returns:
        Configured PalimpsestLogger instance

    Examples:
        >>> from pathlib import Path
        >>> from dev.core.paths import LOG_DIR
        >>> logger = setup_logger(LOG_DIR, "txt2md")
        >>> logger.log_info("Starting conversion...")
    """
    operations_log_dir = log_dir / "operations"
    operations_log_dir.mkdir(parents=True, exist_ok=True)
    return PalimpsestLogger(operations_log_dir, component_name=component_name)
