#!/usr/bin/env python3
"""
Curation Module
---------------
Entity curation infrastructure for the Palimpsest project.

This module provides permanent infrastructure for extracting, validating,
consolidating, and importing curated entity data (people, locations) from
narrative analysis YAML files into the database. The curation workflow
ensures consistent entity resolution across all journal entries.

Key Components:
    - extract: Extract entities from MD frontmatter and narrative_analysis YAMLs
    - validate: Validate curation files and detect cross-year consistency issues
    - consolidate: Merge per-year curation files into consolidated views
    - resolve: Entity resolution using curated mappings
    - importer: Database import with per-file transactions
    - summary: Generate frequency-based summary reports

Workflow:
    1. Extract entities from source files (extract_entities)
    2. Manually curate the generated YAML files
    3. Validate curation quality (validate_curation)
    4. Optionally consolidate multiple years (consolidate_curation)
    5. Import to database using curated mappings (jumpstart_import)

CLI Usage:
    plm curation extract [--dry-run]
    plm curation validate [--year YYYY] [--type people|locations]
    plm curation consolidate --years 2023 2024 2025 [--type people|locations]
    plm curation import [--dry-run] [--failed-only]
    plm curation summary [--type people|locations] [--alphabetical]

Data Files:
    - data/curation/people/{YYYY}.yaml - Per-year people curation
    - data/curation/locations/{YYYY}.yaml - Per-year locations curation
    - data/curation/people/consolidated.yaml - Merged people curation
    - data/curation/locations/consolidated.yaml - Merged locations curation
"""
# --- Annotations ---
from __future__ import annotations

# --- Public API ---
from .models import (
    ConsolidationResult,
    ConsistencyResult,
    ExtractionStats,
    FailedImport,
    ImportStats,
    SummaryData,
    ValidationResult,
)

__all__ = [
    # Models
    "ConsolidationResult",
    "ConsistencyResult",
    "ExtractionStats",
    "FailedImport",
    "ImportStats",
    "SummaryData",
    "ValidationResult",
    # Core Functions (imported on demand to avoid circular imports)
    # - extract_all from .extract
    # - validate_all, check_consistency from .validate
    # - consolidate_and_write from .consolidate
    # - generate_summary from .summary
    # - EntityResolver from .resolve
    # - CurationImporter from .importer
]
