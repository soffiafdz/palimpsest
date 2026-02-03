#!/usr/bin/env python3
"""
metadata.py
-----------
Validation module for metadata YAML files.

This module provides validation functions for metadata YAML files used in the
jumpstart pipeline. It validates both structural integrity and entity references.

Key Features:
    - Structural validation (required fields, types, references)
    - Entity validation against curation (people, locations)
    - Directory-level batch validation
    - Detailed error and warning reporting

Validation Levels:
    - Structure: Required fields, field types, internal references
    - Entities: People and locations exist in curation with suggestions for unknowns

Usage:
    from dev.validators.metadata import validate_metadata_file, validate_metadata_directory

    # Single file validation
    result = validate_metadata_file(Path("2024-12-03.yaml"))

    # Directory validation
    results = validate_metadata_directory(Path("metadata/journal/2024"))

    # With MD frontmatter consistency check
    result = validate_metadata_file(path, check_consistency=True)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
import yaml as pyyaml

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import MD_DIR
from dev.dataclasses.metadata_entry import MetadataEntry, MetadataValidationResult


# =============================================================================
# Batch Validation Results
# =============================================================================


@dataclass
class DirectoryValidationResult:
    """
    Results from validating a directory of metadata YAML files.

    Attributes:
        directory: Path to the validated directory
        files_processed: Number of files processed
        valid_count: Number of files that passed validation
        error_count: Number of files with structural errors
        warning_count: Number of files with entity warnings
        results: Per-file validation results
    """

    directory: str = ""
    files_processed: int = 0
    valid_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    results: Dict[str, MetadataValidationResult] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        """Check if any files have errors."""
        return self.error_count > 0

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        return (
            f"Processed: {self.files_processed} | "
            f"Valid: {self.valid_count} | "
            f"Errors: {self.error_count} | "
            f"Warnings: {self.warning_count}"
        )


# =============================================================================
# Validation Functions
# =============================================================================


def _load_md_frontmatter(yaml_file: Path) -> Optional[Dict[str, Any]]:
    """
    Load MD frontmatter for a metadata YAML file.

    Finds the corresponding MD file and extracts its frontmatter.

    Args:
        yaml_file: Path to metadata YAML file (e.g., metadata/journal/2024/2024-12-03.yaml)

    Returns:
        Parsed frontmatter dict or None if MD file not found
    """
    # Extract date from YAML filename (YYYY-MM-DD.yaml)
    filename = yaml_file.stem  # Remove .yaml extension
    year = yaml_file.parent.name  # Year directory

    # Build MD file path (data/journal/content/md/YYYY/YYYY-MM-DD.md)
    md_file = MD_DIR / year / f"{filename}.md"

    if not md_file.exists():
        return None

    # Read and extract frontmatter
    content = md_file.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    # Find end of frontmatter
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None

    frontmatter_text = content[3:end_idx].strip()
    try:
        return pyyaml.safe_load(frontmatter_text)
    except Exception:
        return None


def validate_metadata_file(
    file_path: Path,
    resolver: Optional[Any] = None,  # EntityResolver, avoid circular import
    md_frontmatter: Optional[Dict[str, Any]] = None,  # For consistency checks
    check_consistency: bool = False,  # Load MD frontmatter automatically
    logger: Optional[PalimpsestLogger] = None,
) -> MetadataValidationResult:
    """
    Validate a single metadata YAML file.

    Performs structural validation and optionally entity validation if a
    resolver is provided. Also validates consistency with MD frontmatter
    if provided or requested.

    Args:
        file_path: Path to metadata YAML file
        resolver: Optional EntityResolver for entity validation
        md_frontmatter: Optional MD frontmatter dict for consistency checks
        check_consistency: Auto-load MD frontmatter and check consistency
        logger: Optional logger for operation tracking

    Returns:
        MetadataValidationResult with errors and warnings
    """
    log = safe_logger(logger)
    result = MetadataValidationResult(file_path=str(file_path))

    # Try to parse the file
    try:
        entry = MetadataEntry.from_file(file_path)
    except FileNotFoundError:
        result.add_error(f"File not found: {file_path}")
        log.log_warning("Validation failed: file not found", {"file": str(file_path)})
        return result
    except Exception as e:
        result.add_error(f"Failed to parse: {e}")
        log.log_warning("Validation failed: parse error", {"file": str(file_path), "error": str(e)})
        return result

    # Structural validation
    struct_result = entry.validate_structure()
    result.errors.extend(struct_result.errors)
    result.warnings.extend(struct_result.warnings)

    # Entity validation (if resolver provided)
    if resolver is not None:
        entity_result = entry.validate_entities(resolver)
        # Don't duplicate structural errors
        result.warnings.extend(entity_result.warnings)

    # Load MD frontmatter if consistency check requested
    if check_consistency and md_frontmatter is None:
        md_frontmatter = _load_md_frontmatter(file_path)
        if md_frontmatter is None:
            result.add_warning("MD frontmatter not found for consistency check")

    # Consistency validation (if MD frontmatter available)
    if md_frontmatter is not None:
        # Validate people consistency between MD and YAML
        people_result = entry.validate_people_consistency(md_frontmatter)
        result.errors.extend(people_result.errors)
        result.warnings.extend(people_result.warnings)

        # Validate scene subsets
        scene_result = entry.validate_scene_subsets(md_frontmatter)
        result.errors.extend(scene_result.errors)
        result.warnings.extend(scene_result.warnings)

    if result.has_errors:
        log.log_warning(
            "Validation errors",
            {"file": str(file_path), "errors": len(result.errors)},
        )
    elif result.warnings:
        log.log_debug(
            "Validation warnings",
            {"file": str(file_path), "warnings": len(result.warnings)},
        )
    else:
        log.log_debug("Validation passed", {"file": str(file_path)})

    return result


def validate_metadata_directory(
    directory: Path,
    resolver: Optional[Any] = None,  # EntityResolver
    pattern: str = "*.yaml",
    check_consistency: bool = False,  # Check MD frontmatter consistency
    logger: Optional[PalimpsestLogger] = None,
) -> DirectoryValidationResult:
    """
    Validate all metadata YAML files in a directory.

    Processes all YAML files matching the pattern and aggregates results.

    Args:
        directory: Path to directory containing metadata YAML files
        resolver: Optional EntityResolver for entity validation
        pattern: Glob pattern for matching files (default: "*.yaml")
        check_consistency: Auto-load MD frontmatter and check consistency
        logger: Optional logger for operation tracking

    Returns:
        DirectoryValidationResult with per-file results and summary
    """
    log = safe_logger(logger)
    result = DirectoryValidationResult(directory=str(directory))

    if not directory.exists():
        log.log_error(FileNotFoundError(f"Directory not found: {directory}"))
        return result

    # Find all matching files
    yaml_files = sorted(directory.glob(pattern))

    if not yaml_files:
        log.log_info(f"No {pattern} files found in {directory}")
        return result

    log.log_operation(
        "validation_start",
        {"directory": str(directory), "files_found": len(yaml_files)},
    )

    # Validate each file
    for yaml_file in yaml_files:
        result.files_processed += 1
        file_result = validate_metadata_file(
            yaml_file,
            resolver=resolver,
            check_consistency=check_consistency,
            logger=logger
        )
        result.results[str(yaml_file)] = file_result

        if file_result.has_errors:
            result.error_count += 1
        elif file_result.warnings:
            result.warning_count += 1
            result.valid_count += 1  # Warnings don't fail validation
        else:
            result.valid_count += 1

    log.log_operation("validation_complete", {"summary": result.summary()})

    return result


def validate_year_directory(
    base_dir: Path,
    year: str,
    resolver: Optional[Any] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> DirectoryValidationResult:
    """
    Validate metadata YAML files for a specific year.

    Convenience function for validating a year subdirectory.

    Args:
        base_dir: Base metadata directory (e.g., metadata/journal/)
        year: Year string (e.g., "2024")
        resolver: Optional EntityResolver for entity validation
        logger: Optional logger

    Returns:
        DirectoryValidationResult for the year's files
    """
    year_dir = base_dir / year
    return validate_metadata_directory(year_dir, resolver, logger=logger)


def validate_all_years(
    base_dir: Path,
    resolver: Optional[Any] = None,
    years: Optional[List[str]] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> Dict[str, DirectoryValidationResult]:
    """
    Validate metadata YAML files across multiple years.

    Args:
        base_dir: Base metadata directory (e.g., metadata/journal/)
        resolver: Optional EntityResolver for entity validation
        years: Optional list of years to validate (default: all year directories)
        logger: Optional logger

    Returns:
        Dictionary mapping year -> DirectoryValidationResult
    """
    log = safe_logger(logger)
    results: Dict[str, DirectoryValidationResult] = {}

    # Find year directories if not specified
    if years is None:
        year_dirs = [
            d for d in sorted(base_dir.iterdir())
            if d.is_dir() and d.name.isdigit() and len(d.name) == 4
        ]
        years = [d.name for d in year_dirs]

    if not years:
        log.log_info(f"No year directories found in {base_dir}")
        return results

    log.log_operation(
        "multi_year_validation_start",
        {"base_dir": str(base_dir), "years": years},
    )

    for year in years:
        year_result = validate_year_directory(base_dir, year, resolver, logger)
        results[year] = year_result

    # Summary
    total_files = sum(r.files_processed for r in results.values())
    total_errors = sum(r.error_count for r in results.values())
    total_warnings = sum(r.warning_count for r in results.values())

    log.log_operation(
        "multi_year_validation_complete",
        {
            "years": len(results),
            "total_files": total_files,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
    )

    return results


# =============================================================================
# Entity Report Generation
# =============================================================================


def generate_entity_report(
    directory: Path,
    resolver: Any,  # EntityResolver
    output_path: Optional[Path] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Generate a report of all unknown entities in metadata files.

    Useful for identifying entities that need to be added to curation files.

    Args:
        directory: Path to directory containing metadata YAML files
        resolver: EntityResolver for entity validation
        output_path: Optional path to write report to file
        logger: Optional logger

    Returns:
        Report text as string
    """
    log = safe_logger(logger)

    # Collect all unknown entities
    unknown_people: Dict[str, List[str]] = {}  # name -> [files]
    unknown_locations: Dict[str, List[str]] = {}  # name -> [files]

    yaml_files = sorted(directory.rglob("*.yaml"))

    for yaml_file in yaml_files:
        try:
            entry = MetadataEntry.from_file(yaml_file)
        except Exception:
            continue

        # Check people
        for person in entry.get_all_people():
            lookup = resolver.validate_person(person)
            if not lookup.found:
                if person not in unknown_people:
                    unknown_people[person] = []
                unknown_people[person].append(str(yaml_file))

        # Check locations
        for location in entry.get_all_locations():
            lookup = resolver.validate_location(location)
            if not lookup.found:
                if location not in unknown_locations:
                    unknown_locations[location] = []
                unknown_locations[location].append(str(yaml_file))

    # Generate report
    lines = [
        "# Entity Validation Report",
        "",
        f"Directory: {directory}",
        f"Files scanned: {len(yaml_files)}",
        "",
    ]

    if unknown_people:
        lines.append(f"## Unknown People ({len(unknown_people)})")
        lines.append("")
        for name in sorted(unknown_people.keys()):
            files = unknown_people[name]
            lines.append(f"- **{name}** ({len(files)} occurrences)")
            # Show suggestions
            lookup = resolver.validate_person(name)
            if lookup.suggestions:
                lines.append(f"  - Suggestions: {', '.join(lookup.suggestions[:3])}")
        lines.append("")
    else:
        lines.append("## Unknown People: None")
        lines.append("")

    if unknown_locations:
        lines.append(f"## Unknown Locations ({len(unknown_locations)})")
        lines.append("")
        for name in sorted(unknown_locations.keys()):
            files = unknown_locations[name]
            lines.append(f"- **{name}** ({len(files)} occurrences)")
            lookup = resolver.validate_location(name)
            if lookup.suggestions:
                lines.append(f"  - Suggestions: {', '.join(lookup.suggestions[:3])}")
        lines.append("")
    else:
        lines.append("## Unknown Locations: None")
        lines.append("")

    report = "\n".join(lines)

    # Write to file if requested
    if output_path:
        output_path.write_text(report, encoding="utf-8")
        log.log_operation(
            "entity_report_written",
            {"output": str(output_path)},
        )

    return report
