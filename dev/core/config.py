#!/usr/bin/env python3
"""
config.py
---------
Project configuration loader with local overrides.

Provides two-layer configuration: shared defaults tracked in git
(``.palimpsest.yaml``) and per-host overrides (``.palimpsest.local.yaml``,
gitignored). Local values override shared values via shallow dict merge
per section.

Key Features:
    - Shared defaults committed to the repository
    - Per-host local overrides (gitignored)
    - Shallow merge: local sections override shared sections key-by-key
    - Typed accessor for sync-specific configuration

Usage:
    from dev.core.config import get_sync_config

    cfg = get_sync_config()
    print(cfg["years"])       # e.g. "2021-2025"
    print(cfg["no_wiki"])     # e.g. False
    print(cfg["auto_commit"]) # e.g. False

Dependencies:
    - PyYAML for YAML parsing
    - dev.core.paths for project root
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Any, Dict

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import ROOT

CONFIG_PATH = ROOT / ".palimpsest.yaml"
LOCAL_CONFIG_PATH = ROOT / ".palimpsest.local.yaml"


def load_config() -> Dict[str, Any]:
    """
    Load project config with local overrides.

    Reads the shared config file first, then merges any local
    overrides on top. Local values override shared values via
    shallow dict merge per section.

    Returns:
        Merged configuration dictionary

    Notes:
        - Missing files are silently skipped
        - Empty files yield empty dicts
        - Non-dict local sections replace shared values entirely
    """
    config: Dict[str, Any] = {}
    if CONFIG_PATH.exists():
        config = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    if LOCAL_CONFIG_PATH.exists():
        local = yaml.safe_load(LOCAL_CONFIG_PATH.read_text()) or {}
        for section, values in local.items():
            if isinstance(values, dict):
                config.setdefault(section, {}).update(values)
            else:
                config[section] = values
    return config


def get_sync_config() -> Dict[str, Any]:
    """
    Get sync-specific config with defaults.

    Extracts the ``sync`` section from the project config and
    fills in defaults for any missing keys.

    Returns:
        Dictionary with keys:
            - years: Year range for entries import (str or None)
            - no_wiki: Whether to skip wiki generation (bool)
            - auto_commit: Whether to auto-commit data/ submodule (bool)
    """
    config = load_config()
    sync: Dict[str, Any] = config.get("sync", {})
    years = sync.get("years", None)
    if years is not None:
        years = str(years)
    return {
        "years": years,
        "no_wiki": sync.get("no_wiki", False),
        "auto_commit": sync.get("auto_commit", False),
    }
