#!/usr/bin/env python3
"""
test_config.py
--------------
Unit tests for the project configuration loader.

Verifies config loading, local overrides, shallow merge behavior,
and sync-specific defaults.

Usage:
    pytest tests/unit/core/test_config.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from unittest.mock import patch

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.core.config import load_config, get_sync_config


@pytest.fixture
def config_files(tmp_path):
    """Create temporary config files and patch paths."""
    shared = tmp_path / ".palimpsest.yaml"
    local = tmp_path / ".palimpsest.local.yaml"
    return shared, local


class TestLoadConfig:
    """Tests for load_config()."""

    def test_no_config_files(self, config_files):
        """Returns empty dict when no config files exist."""
        shared, local = config_files
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result == {}

    def test_shared_only(self, config_files):
        """Loads shared config when only shared file exists."""
        shared, local = config_files
        shared.write_text("sync:\n  min_year: 2021\n  no_wiki: true\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result == {"sync": {"min_year": 2021, "no_wiki": True}}

    def test_local_override(self, config_files):
        """Local config overrides shared values per section."""
        shared, local = config_files
        shared.write_text("sync:\n  min_year: 2021\n  no_wiki: false\n")
        local.write_text("sync:\n  no_wiki: true\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result["sync"]["min_year"] == 2021
        assert result["sync"]["no_wiki"] is True

    def test_shallow_merge_preserves_shared_keys(self, config_files):
        """Local override merges shallowly — shared keys not in local are kept."""
        shared, local = config_files
        shared.write_text("sync:\n  min_year: 2021\n  auto_commit: false\n")
        local.write_text("sync:\n  auto_commit: true\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result["sync"]["min_year"] == 2021
        assert result["sync"]["auto_commit"] is True

    def test_local_adds_new_section(self, config_files):
        """Local config can add sections not in shared config."""
        shared, local = config_files
        shared.write_text("sync:\n  min_year: 2021\n")
        local.write_text("build:\n  format: pdf\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result["sync"]["min_year"] == 2021
        assert result["build"]["format"] == "pdf"

    def test_empty_shared_file(self, config_files):
        """Empty shared file yields empty dict."""
        shared, local = config_files
        shared.write_text("")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result == {}

    def test_scalar_local_override(self, config_files):
        """Non-dict local values replace shared values entirely."""
        shared, local = config_files
        shared.write_text("sync:\n  min_year: 2021\n")
        local.write_text("sync: disabled\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = load_config()
        assert result["sync"] == "disabled"


class TestGetSyncConfig:
    """Tests for get_sync_config()."""

    def test_defaults_when_no_config(self, config_files):
        """Returns default values when no config files exist."""
        shared, local = config_files
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = get_sync_config()
        assert result == {
            "years": None,
            "no_wiki": False,
            "auto_commit": False,
        }

    def test_reads_sync_section(self, config_files):
        """Reads values from sync section."""
        shared, local = config_files
        shared.write_text(
            "sync:\n  years: '2021-2025'\n  no_wiki: true\n  auto_commit: true\n"
        )
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = get_sync_config()
        assert result["years"] == "2021-2025"
        assert result["no_wiki"] is True
        assert result["auto_commit"] is True

    def test_partial_sync_config_fills_defaults(self, config_files):
        """Missing sync keys get default values."""
        shared, local = config_files
        shared.write_text("sync:\n  years: '2023-2025'\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = get_sync_config()
        assert result["years"] == "2023-2025"
        assert result["no_wiki"] is False
        assert result["auto_commit"] is False

    def test_local_override_sync(self, config_files):
        """Local config overrides sync values."""
        shared, local = config_files
        shared.write_text("sync:\n  years: '2021-2025'\n  no_wiki: false\n")
        local.write_text("sync:\n  no_wiki: true\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = get_sync_config()
        assert result["years"] == "2021-2025"
        assert result["no_wiki"] is True

    def test_integer_years_coerced_to_string(self, config_files):
        """Integer years value is coerced to string."""
        shared, local = config_files
        shared.write_text("sync:\n  years: 2024\n")
        with patch("dev.core.config.CONFIG_PATH", shared), \
             patch("dev.core.config.LOCAL_CONFIG_PATH", local):
            result = get_sync_config()
        assert result["years"] == "2024"
