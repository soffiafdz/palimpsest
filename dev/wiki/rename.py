#!/usr/bin/env python3
"""
rename.py
---------
Format-preserving entity rename engine with merge semantics.

Renames entities across all YAML metadata files and MD frontmatter,
handling the case where both old and new names coexist in the same list
by merging (removing the duplicate) rather than creating a collision.
Uses ruamel.yaml for format-preserving round-trip to keep hand-curated
YAML intact. MD content below frontmatter is never touched.

Supported Entity Types:
    - location: scenes[].locations, threads[].locations, per-entity file,
      neighborhoods.yaml, MD frontmatter locations dict
    - tag: tags (top-level list)
    - theme: themes (top-level list)
    - arc: arcs (top-level list), arcs.yaml
    - person: people[].name, scenes[].people, threads[].people,
      per-entity file, relation_types.yaml, MD frontmatter people list
    - city: cities.yaml, location YAML city fields, neighborhoods.yaml
      section keys, directory rename
    - motif: motifs[].name
    - event: events[].name

Key Features:
    - Merge semantics: when both old and new names exist in a list,
      removes the old rather than creating duplicates
    - Dry-run by default: previews changes without modifying files
    - Format preservation: ruamel.yaml round-trip keeps >- strings,
      quoting, and comments intact
    - Per-entity file handling: rename/merge/delete as appropriate
    - Curation file handling: slug-keyed YAML updates
    - MD frontmatter: renames in locations/people fields while
      preserving markdown content byte-for-byte
    - Date filtering: skips entries before a configurable cutoff
      (default: 2020-01-01)

Usage:
    from dev.wiki.rename import EntityRenamer

    renamer = EntityRenamer(metadata_dir, journal_dir, md_dir)
    report = renamer.rename("location", "Home", "Apartment - Jarry")
    print(report.summary())

    # Apply changes
    report = renamer.rename("location", "Home", "Apartment - Jarry",
                            dry_run=False)

Dependencies:
    - ruamel.yaml for format-preserving YAML round-trip
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import io
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
from ruamel.yaml import YAML

# --- Local imports ---
from dev.utils.slugify import slugify


# ==================== Data Classes ====================

@dataclass
class RenameAction:
    """
    A single rename action performed on a file.

    Attributes:
        file: Path to the affected file (relative to metadata dir)
        action: Type of action performed
        detail: Human-readable description of what changed
    """

    file: Path
    action: str
    detail: str


@dataclass
class RenameReport:
    """
    Report of all changes from a rename operation.

    Attributes:
        entity_type: Type of entity being renamed
        old_name: Original entity name
        new_name: Target entity name
        entry_changes: Changes to entry YAML files
        file_changes: Changes to per-entity YAML files
        curation_changes: Changes to curation YAML files
        md_changes: Changes to MD frontmatter files
    """

    entity_type: str
    old_name: str
    new_name: str
    entry_changes: List[RenameAction] = field(default_factory=list)
    file_changes: List[RenameAction] = field(default_factory=list)
    curation_changes: List[RenameAction] = field(default_factory=list)
    md_changes: List[RenameAction] = field(default_factory=list)

    def summary(self) -> str:
        """
        Generate human-readable summary of the rename report.

        Returns:
            Formatted string showing all changes grouped by category
        """
        lines = [
            f'Renaming {self.entity_type}: "{self.old_name}" → "{self.new_name}"',
            "",
        ]

        if self.entry_changes:
            lines.append(f"Entry YAMLs ({len(self.entry_changes)} files):")
            for change in self.entry_changes:
                icon = {"renamed": "✎", "merged": "⊕", "unchanged": "·"}.get(
                    change.action, "?"
                )
                lines.append(f"  {icon} {change.file} — {change.detail}")
            lines.append("")

        if self.file_changes:
            lines.append("Per-entity files:")
            for change in self.file_changes:
                icon = {
                    "renamed": "✎",
                    "deleted": "✕",
                    "moved": "→",
                    "updated": "✎",
                }.get(change.action, "?")
                lines.append(f"  {icon} {change.file} — {change.detail}")
            lines.append("")

        if self.curation_changes:
            lines.append("Curation files:")
            for change in self.curation_changes:
                icon = {"key_renamed": "✎", "key_merged": "⊕"}.get(
                    change.action, "?"
                )
                lines.append(f"  {icon} {change.file} — {change.detail}")
            lines.append("")

        if self.md_changes:
            lines.append(f"MD frontmatter ({len(self.md_changes)} files):")
            for change in self.md_changes:
                icon = {"renamed": "✎", "merged": "⊕"}.get(
                    change.action, "?"
                )
                lines.append(f"  {icon} {change.file} — {change.detail}")
            lines.append("")

        total = (
            len(self.entry_changes)
            + len(self.file_changes)
            + len(self.curation_changes)
            + len(self.md_changes)
        )
        if total == 0:
            lines.append("No changes needed.")
        else:
            lines.append(f"Total: {total} file(s) affected.")

        return "\n".join(lines)


# ==================== Entity Type Configuration ====================

@dataclass
class EntityTypeConfig:
    """
    Configuration for how a specific entity type appears in entry YAMLs.

    Attributes:
        top_level_lists: Top-level list fields to scan (e.g., ["tags"])
        nested_name_lists: Paths to nested lists of dicts with 'name' field
            (e.g., [("people", "name")] for people[].name)
        scene_lists: Fields within scenes[] that are flat name lists
            (e.g., ["locations", "people"])
        thread_lists: Fields within threads[] that are flat name lists
        has_per_entity_file: Whether this type has per-entity YAML files
        curation_file: Name of curation file if applicable
        per_entity_dir: Subdirectory for per-entity files
        city_scoped: Whether per-entity files are organized by city
        md_frontmatter_field: Field name in MD frontmatter, or None if
            not present. For locations this is "locations" (nested dict
            {city: [names]}), for people it is "people" (flat list).
        md_frontmatter_nested: Whether the MD frontmatter field is a
            nested dict (True for locations) or flat list (False for people)
    """

    top_level_lists: List[str] = field(default_factory=list)
    nested_name_lists: List[str] = field(default_factory=list)
    scene_lists: List[str] = field(default_factory=list)
    thread_lists: List[str] = field(default_factory=list)
    has_per_entity_file: bool = False
    curation_file: Optional[str] = None
    per_entity_dir: Optional[str] = None
    city_scoped: bool = False
    md_frontmatter_field: Optional[str] = None
    md_frontmatter_nested: bool = False


ENTITY_CONFIGS: Dict[str, EntityTypeConfig] = {
    "location": EntityTypeConfig(
        scene_lists=["locations"],
        thread_lists=["locations"],
        has_per_entity_file=True,
        curation_file="neighborhoods.yaml",
        per_entity_dir="locations",
        city_scoped=True,
        md_frontmatter_field="locations",
        md_frontmatter_nested=True,
    ),
    "tag": EntityTypeConfig(
        top_level_lists=["tags"],
    ),
    "theme": EntityTypeConfig(
        top_level_lists=["themes"],
    ),
    "arc": EntityTypeConfig(
        top_level_lists=["arcs"],
        has_per_entity_file=True,
    ),
    "person": EntityTypeConfig(
        nested_name_lists=["people"],
        scene_lists=["people"],
        thread_lists=["people"],
        has_per_entity_file=True,
        curation_file="relation_types.yaml",
        per_entity_dir="people",
        md_frontmatter_field="people",
        md_frontmatter_nested=False,
    ),
    "city": EntityTypeConfig(),
    "motif": EntityTypeConfig(
        nested_name_lists=["motifs"],
    ),
    "event": EntityTypeConfig(
        nested_name_lists=["events"],
    ),
}


# ==================== Renamer ====================

# Minimum year directory to process (skip pre-2020 entries)
MIN_YEAR = 2020


class EntityRenamer:
    """
    Format-preserving entity rename engine with merge semantics.

    Scans entry YAML files, per-entity YAML files, curation YAML files,
    and MD frontmatter files to rename an entity across all occurrences.
    When both old and new names exist in the same list, merges by
    removing the old entry rather than creating duplicates.

    MD frontmatter processing preserves the markdown content below
    the frontmatter delimiter byte-for-byte.

    Attributes:
        metadata_dir: Root metadata directory (data/metadata/)
        journal_dir: Journal YAML directory (data/metadata/journal/)
        md_dir: MD journal directory (data/journal/content/md/) or None
    """

    def __init__(
        self,
        metadata_dir: Path,
        journal_dir: Path,
        md_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the rename engine.

        Args:
            metadata_dir: Root metadata directory containing per-entity
                and curation YAML files
            journal_dir: Journal YAML directory containing entry files
            md_dir: MD journal directory containing .md files with YAML
                frontmatter. When provided, renames also apply to MD
                frontmatter fields (locations, people). Content below
                the frontmatter is never modified.
        """
        self.metadata_dir = metadata_dir
        self.journal_dir = journal_dir
        self.md_dir = md_dir
        self._yaml = YAML()
        self._yaml.preserve_quotes = True

    def rename(
        self,
        entity_type: str,
        old_name: str,
        new_name: str,
        city: Optional[str] = None,
        dry_run: bool = True,
    ) -> RenameReport:
        """
        Execute or preview a rename operation.

        Args:
            entity_type: Entity type to rename (location, tag, theme,
                arc, person, city, motif, event)
            old_name: Current name of the entity
            new_name: Target name for the entity
            city: City for location disambiguation (required when
                same location name exists in multiple cities)
            dry_run: If True, preview changes without modifying files

        Returns:
            RenameReport with all changes performed or previewed

        Raises:
            ValueError: If entity_type is not recognized or old_name
                equals new_name
        """
        if entity_type not in ENTITY_CONFIGS:
            raise ValueError(
                f"Unknown entity type: {entity_type}. "
                f"Valid types: {list(ENTITY_CONFIGS.keys())}"
            )

        if old_name == new_name:
            raise ValueError("Old name and new name are identical")

        report = RenameReport(
            entity_type=entity_type,
            old_name=old_name,
            new_name=new_name,
        )

        if entity_type == "city":
            self._rename_city(old_name, new_name, dry_run, report)
        else:
            config = ENTITY_CONFIGS[entity_type]
            self._rename_in_entries(
                config, old_name, new_name, dry_run, report
            )

            if config.has_per_entity_file:
                self._handle_per_entity_file(
                    entity_type, config, old_name, new_name,
                    city, dry_run, report,
                )

            if config.curation_file:
                self._handle_curation_file(
                    entity_type, config, old_name, new_name,
                    city, dry_run, report,
                )

            if self.md_dir and config.md_frontmatter_field:
                self._rename_in_md_frontmatter(
                    config, old_name, new_name, dry_run, report
                )

        return report

    # ---- Entry YAML scanning ----

    def _rename_in_entries(
        self,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Scan and update all entry YAML files for the rename.

        Iterates over all journal YAML files and applies rename/merge
        logic to the fields specified in the entity type config.

        Args:
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            dry_run: If True, don't modify files
            report: Report to append changes to
        """
        for yaml_path in sorted(self.journal_dir.rglob("*.yaml")):
            self._process_entry_file(
                yaml_path, config, old_name, new_name, dry_run, report
            )

    def _process_entry_file(
        self,
        path: Path,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Process a single entry YAML file for rename operations.

        Loads the YAML, checks all configured fields for the old name,
        applies merge/rename logic, and writes back if changed.

        Args:
            path: Path to the entry YAML file
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            dry_run: If True, don't write changes
            report: Report to append changes to
        """
        data = self._load_yaml(path)
        if data is None:
            return

        changes: List[str] = []

        # Top-level lists (tags, themes, arcs)
        for field_name in config.top_level_lists:
            items = data.get(field_name)
            if items and isinstance(items, list):
                result = self._merge_in_list(items, old_name, new_name)
                if result:
                    changes.append(f"{field_name}: {result}")

        # Nested name lists (people[].name, motifs[].name, events[].name)
        for field_name in config.nested_name_lists:
            items = data.get(field_name)
            if items and isinstance(items, list):
                result = self._merge_in_name_dicts(
                    items, old_name, new_name
                )
                if result:
                    changes.append(f"{field_name}: {result}")

        # Scene sub-lists (scenes[].locations, scenes[].people)
        scenes = data.get("scenes")
        if scenes and isinstance(scenes, list):
            for i, scene in enumerate(scenes):
                if not isinstance(scene, dict):
                    continue
                for field_name in config.scene_lists:
                    items = scene.get(field_name)
                    if items and isinstance(items, list):
                        result = self._merge_in_list(
                            items, old_name, new_name
                        )
                        if result:
                            changes.append(
                                f"scenes[{i}].{field_name}: {result}"
                            )

        # Thread sub-lists (threads[].locations, threads[].people)
        threads = data.get("threads")
        if threads and isinstance(threads, list):
            for i, thread in enumerate(threads):
                if not isinstance(thread, dict):
                    continue
                for field_name in config.thread_lists:
                    items = thread.get(field_name)
                    if items and isinstance(items, list):
                        result = self._merge_in_list(
                            items, old_name, new_name
                        )
                        if result:
                            changes.append(
                                f"threads[{i}].{field_name}: {result}"
                            )

        if changes:
            rel_path = self._relative_path(path)
            detail = "; ".join(changes)
            action = "merged" if any("merged" in c for c in changes) else "renamed"
            report.entry_changes.append(
                RenameAction(file=rel_path, action=action, detail=detail)
            )
            if not dry_run:
                self._save_yaml(path, data)

    # ---- Merge logic ----

    def _merge_in_list(
        self,
        items: list,
        old_name: str,
        new_name: str,
    ) -> Optional[str]:
        """
        Apply merge/rename logic to a flat list of strings.

        If old_name is absent, returns None (no-op).
        If both old_name and new_name are present, removes old_name (merge).
        If only old_name is present, replaces it with new_name (rename).

        Args:
            items: Mutable list of string values
            old_name: Name to find
            new_name: Name to replace with

        Returns:
            Action description ("renamed" or "merged") or None if no-op
        """
        if old_name not in items:
            return None

        if new_name in items:
            items.remove(old_name)
            return "merged"
        else:
            idx = items.index(old_name)
            items[idx] = new_name
            return "renamed"

    def _merge_in_name_dicts(
        self,
        items: list,
        old_name: str,
        new_name: str,
    ) -> Optional[str]:
        """
        Apply merge/rename logic to a list of dicts with 'name' field.

        Used for people[], motifs[], events[] where each item is a dict
        with at least a 'name' key.

        If old_name not found, returns None.
        If both old and new exist, removes the old dict (merge).
        If only old exists, updates its name field (rename).

        Args:
            items: Mutable list of dicts with 'name' keys
            old_name: Name to find
            new_name: Name to replace with

        Returns:
            Action description or None if no-op
        """
        old_idx = None
        new_exists = False

        for i, item in enumerate(items):
            if isinstance(item, dict) and item.get("name") == old_name:
                old_idx = i
            if isinstance(item, dict) and item.get("name") == new_name:
                new_exists = True

        if old_idx is None:
            return None

        if new_exists:
            del items[old_idx]
            return "merged"
        else:
            items[old_idx]["name"] = new_name
            return "renamed"

    # ---- Per-entity file handling ----

    def _handle_per_entity_file(
        self,
        entity_type: str,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        city: Optional[str],
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Handle per-entity YAML file rename, merge, or delete.

        For entity types with individual YAML files (locations, people,
        arcs), manages the file-level operations:
        - If target file exists: delete old file (merged into existing)
        - If target doesn't exist: rename file and update name inside

        Args:
            entity_type: Entity type key
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            city: City for location scoping
            dry_run: If True, don't modify filesystem
            report: Report to append changes to
        """
        if entity_type == "arc":
            self._handle_arc_file(old_name, new_name, dry_run, report)
            return

        if not config.per_entity_dir:
            return

        base_dir = self.metadata_dir / config.per_entity_dir
        old_slug = slugify(old_name)
        new_slug = slugify(new_name)

        if config.city_scoped:
            if city:
                city_slug = slugify(city)
                old_path = base_dir / city_slug / f"{old_slug}.yaml"
                new_path = base_dir / city_slug / f"{new_slug}.yaml"
            else:
                # Search all city subdirs for the old file
                old_path, city_slug = self._find_entity_file(
                    base_dir, old_slug
                )
                if old_path is None:
                    return
                new_path = base_dir / city_slug / f"{new_slug}.yaml"
        else:
            old_path = base_dir / f"{old_slug}.yaml"
            new_path = base_dir / f"{new_slug}.yaml"

        if not old_path.exists():
            return

        rel_old = self._relative_path(old_path)

        if new_path.exists():
            # Target exists — delete old file (merge)
            report.file_changes.append(RenameAction(
                file=rel_old,
                action="deleted",
                detail=f"target {self._relative_path(new_path)} already exists",
            ))
            if not dry_run:
                old_path.unlink()
        else:
            # Target doesn't exist — rename file + update name inside
            report.file_changes.append(RenameAction(
                file=rel_old,
                action="moved",
                detail=f"→ {self._relative_path(new_path)}",
            ))
            if not dry_run:
                data = self._load_yaml(old_path)
                if data and isinstance(data, dict):
                    data["name"] = new_name
                    if entity_type == "person":
                        data["slug"] = new_slug
                    self._save_yaml(new_path, data)
                old_path.unlink()

    def _handle_arc_file(
        self,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Handle arc rename in the single arcs.yaml file.

        Arcs are stored as a list in a single file. Finds the old name
        and renames or merges it.

        Args:
            old_name: Current arc name
            new_name: Target arc name
            dry_run: If True, don't modify file
            report: Report to append changes to
        """
        arcs_path = self.metadata_dir / "arcs.yaml"
        if not arcs_path.exists():
            return

        data = self._load_yaml(arcs_path)
        if not isinstance(data, list):
            return

        old_idx = None
        new_exists = False

        for i, arc in enumerate(data):
            if isinstance(arc, dict) and arc.get("name") == old_name:
                old_idx = i
            if isinstance(arc, dict) and arc.get("name") == new_name:
                new_exists = True

        if old_idx is None:
            return

        rel_path = self._relative_path(arcs_path)

        if new_exists:
            del data[old_idx]
            report.file_changes.append(RenameAction(
                file=rel_path,
                action="deleted",
                detail=f'removed "{old_name}" (merged into existing '
                       f'"{new_name}")',
            ))
        else:
            data[old_idx]["name"] = new_name
            report.file_changes.append(RenameAction(
                file=rel_path,
                action="updated",
                detail=f'renamed "{old_name}" → "{new_name}"',
            ))

        if not dry_run:
            self._save_yaml(arcs_path, data)

    # ---- Curation file handling ----

    def _handle_curation_file(
        self,
        entity_type: str,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        city: Optional[str],
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Handle curation YAML file updates for slug-keyed files.

        Curation files map entity slugs to values. When renaming,
        the old slug key must be updated or merged with the new slug.

        Args:
            entity_type: Entity type key
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            city: City for location-scoped curation
            dry_run: If True, don't modify file
            report: Report to append changes to
        """
        if not config.curation_file:
            return

        curation_path = self.metadata_dir / config.curation_file
        if not curation_path.exists():
            return

        data = self._load_yaml(curation_path)
        if data is None:
            return

        old_slug = slugify(old_name)
        new_slug = slugify(new_name)
        rel_path = self._relative_path(curation_path)

        if entity_type == "location":
            # neighborhoods.yaml: {city_slug: {loc_slug: neighborhood}}
            self._handle_nested_curation(
                data, old_slug, new_slug, city, curation_path,
                dry_run, report, rel_path,
            )
        elif entity_type == "person":
            # relation_types.yaml: {person_slug: relation_type}
            self._handle_flat_curation(
                data, old_slug, new_slug, curation_path,
                dry_run, report, rel_path,
            )

    def _handle_nested_curation(
        self,
        data: Any,
        old_slug: str,
        new_slug: str,
        city: Optional[str],
        path: Path,
        dry_run: bool,
        report: RenameReport,
        rel_path: Path,
    ) -> None:
        """
        Handle slug rename in nested curation file (neighborhoods.yaml).

        The file structure is {city_slug: {loc_slug: value}}.
        Finds the old slug in the appropriate city section and renames
        or merges it.

        Args:
            data: Parsed YAML data
            old_slug: Current slug to find
            new_slug: Target slug
            city: City name for scoping
            path: Path to curation file
            dry_run: If True, don't write changes
            report: Report to append changes to
            rel_path: Relative path for reporting
        """
        if not isinstance(data, dict):
            return

        changed = False

        if city:
            city_slug = slugify(city)
            sections = [(city_slug, data.get(city_slug))]
        else:
            sections = list(data.items())

        for city_slug, section in sections:
            if not isinstance(section, dict):
                continue
            if old_slug not in section:
                continue

            old_value = section[old_slug]

            if new_slug in section:
                # Merge: keep new's value if set, else use old's
                if section[new_slug] is None and old_value is not None:
                    section[new_slug] = old_value
                del section[old_slug]
                report.curation_changes.append(RenameAction(
                    file=rel_path,
                    action="key_merged",
                    detail=(
                        f'{city_slug}: "{old_slug}" merged into '
                        f'"{new_slug}"'
                    ),
                ))
            else:
                # Rename: insert new key, remove old, preserving order
                self._rename_dict_key(section, old_slug, new_slug)
                report.curation_changes.append(RenameAction(
                    file=rel_path,
                    action="key_renamed",
                    detail=(
                        f'{city_slug}: "{old_slug}" → "{new_slug}"'
                    ),
                ))
            changed = True

        if changed and not dry_run:
            self._save_yaml(path, data)

    def _handle_flat_curation(
        self,
        data: Any,
        old_slug: str,
        new_slug: str,
        path: Path,
        dry_run: bool,
        report: RenameReport,
        rel_path: Path,
    ) -> None:
        """
        Handle slug rename in flat curation file (relation_types.yaml).

        The file structure is {slug: value}. Finds the old slug and
        renames or merges it.

        Args:
            data: Parsed YAML data
            old_slug: Current slug to find
            new_slug: Target slug
            path: Path to curation file
            dry_run: If True, don't write changes
            report: Report to append changes to
            rel_path: Relative path for reporting
        """
        if not isinstance(data, dict):
            return

        if old_slug not in data:
            return

        old_value = data[old_slug]

        if new_slug in data:
            if data[new_slug] is None and old_value is not None:
                data[new_slug] = old_value
            del data[old_slug]
            report.curation_changes.append(RenameAction(
                file=rel_path,
                action="key_merged",
                detail=f'"{old_slug}" merged into "{new_slug}"',
            ))
        else:
            self._rename_dict_key(data, old_slug, new_slug)
            report.curation_changes.append(RenameAction(
                file=rel_path,
                action="key_renamed",
                detail=f'"{old_slug}" → "{new_slug}"',
            ))

        if not dry_run:
            self._save_yaml(path, data)

    # ---- City rename (cascade) ----

    def _rename_city(
        self,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Rename a city with cascading updates to all downstream files.

        City renames affect:
        1. cities.yaml — update name in the list
        2. All location YAMLs in the old city directory — update city field
        3. neighborhoods.yaml — rename section key
        4. Directory rename: locations/{old_slug}/ → locations/{new_slug}/

        Args:
            old_name: Current city name
            new_name: Target city name
            dry_run: If True, don't modify files
            report: Report to append changes to
        """
        old_slug = slugify(old_name)
        new_slug = slugify(new_name)

        # 1. Update cities.yaml
        cities_path = self.metadata_dir / "cities.yaml"
        if cities_path.exists():
            data = self._load_yaml(cities_path)
            if isinstance(data, list):
                for city in data:
                    if isinstance(city, dict) and city.get("name") == old_name:
                        city["name"] = new_name
                        report.file_changes.append(RenameAction(
                            file=self._relative_path(cities_path),
                            action="updated",
                            detail=f'renamed "{old_name}" → "{new_name}"',
                        ))
                        if not dry_run:
                            self._save_yaml(cities_path, data)
                        break

        # 2. Update location YAMLs and rename directory
        locations_dir = self.metadata_dir / "locations"
        old_city_dir = locations_dir / old_slug
        new_city_dir = locations_dir / new_slug

        if old_city_dir.exists():
            for loc_path in sorted(old_city_dir.glob("*.yaml")):
                data = self._load_yaml(loc_path)
                if isinstance(data, dict) and data.get("city") == old_name:
                    data["city"] = new_name
                    report.file_changes.append(RenameAction(
                        file=self._relative_path(loc_path),
                        action="updated",
                        detail=f'city field: "{old_name}" → "{new_name}"',
                    ))
                    if not dry_run:
                        self._save_yaml(loc_path, data)

            # Rename directory (only if slug actually changed)
            if old_slug != new_slug:
                if new_city_dir.exists():
                    # Merge directories
                    if not dry_run:
                        for loc_path in old_city_dir.glob("*.yaml"):
                            target = new_city_dir / loc_path.name
                            if not target.exists():
                                shutil.move(str(loc_path), str(target))
                            else:
                                loc_path.unlink()
                        old_city_dir.rmdir()
                    report.file_changes.append(RenameAction(
                        file=self._relative_path(old_city_dir),
                        action="deleted",
                        detail=(
                            f"directory merged into "
                            f"{self._relative_path(new_city_dir)}"
                        ),
                    ))
                else:
                    report.file_changes.append(RenameAction(
                        file=self._relative_path(old_city_dir),
                        action="moved",
                        detail=f"→ {self._relative_path(new_city_dir)}",
                    ))
                    if not dry_run:
                        old_city_dir.rename(new_city_dir)

        # 3. Update neighborhoods.yaml
        neighborhoods_path = self.metadata_dir / "neighborhoods.yaml"
        if neighborhoods_path.exists():
            data = self._load_yaml(neighborhoods_path)
            if isinstance(data, dict) and old_slug in data:
                rel_path = self._relative_path(neighborhoods_path)
                if new_slug in data:
                    # Merge sections
                    new_section = data[new_slug]
                    old_section = data[old_slug]
                    if isinstance(old_section, dict) and isinstance(
                        new_section, dict
                    ):
                        for k, v in old_section.items():
                            if k not in new_section:
                                new_section[k] = v
                    del data[old_slug]
                    report.curation_changes.append(RenameAction(
                        file=rel_path,
                        action="key_merged",
                        detail=(
                            f'section "{old_slug}" merged into '
                            f'"{new_slug}"'
                        ),
                    ))
                else:
                    self._rename_dict_key(data, old_slug, new_slug)
                    report.curation_changes.append(RenameAction(
                        file=rel_path,
                        action="key_renamed",
                        detail=f'section "{old_slug}" → "{new_slug}"',
                    ))

                if not dry_run:
                    self._save_yaml(neighborhoods_path, data)

    # ---- MD frontmatter ----

    def _rename_in_md_frontmatter(
        self,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Scan and update MD frontmatter files for the rename.

        Iterates over year directories in md_dir (2020+), parses
        YAML frontmatter from each .md file, applies rename/merge
        logic to the configured field, and writes back. The markdown
        content below the frontmatter is preserved byte-for-byte.

        Args:
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            dry_run: If True, don't modify files
            report: Report to append changes to
        """
        if not self.md_dir or not self.md_dir.exists():
            return

        for year_dir in sorted(self.md_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            try:
                year = int(year_dir.name)
            except ValueError:
                continue
            if year < MIN_YEAR:
                continue

            for md_path in sorted(year_dir.glob("*.md")):
                self._process_md_file(
                    md_path, config, old_name, new_name,
                    dry_run, report,
                )

    def _process_md_file(
        self,
        path: Path,
        config: EntityTypeConfig,
        old_name: str,
        new_name: str,
        dry_run: bool,
        report: RenameReport,
    ) -> None:
        """
        Process a single MD file for frontmatter rename.

        Uses targeted text replacement within the frontmatter to
        avoid any YAML reformatting. The frontmatter is parsed with
        ruamel.yaml only for detection; the actual replacement is
        done on the raw text. The markdown content after the second
        ``---`` is never parsed or modified.

        Args:
            path: Path to the .md file
            config: Entity type configuration
            old_name: Current entity name
            new_name: Target entity name
            dry_run: If True, don't write changes
            report: Report to append changes to
        """
        raw = path.read_text(encoding="utf-8")

        # Split frontmatter from content
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return

        # parts[0] is empty (before first ---), parts[1] is frontmatter,
        # parts[2] is the markdown content (preserved exactly)
        frontmatter_text = parts[1]
        content = parts[2]

        data = self._yaml.load(io.StringIO(frontmatter_text))
        if not isinstance(data, dict):
            return

        field_name = config.md_frontmatter_field
        if not field_name:
            return

        field_data = data.get(field_name)
        if field_data is None:
            return

        # Detect what needs changing using parsed data
        changes: List[str] = []
        needs_merge = False

        if config.md_frontmatter_nested:
            if isinstance(field_data, dict):
                for city_key, loc_list in field_data.items():
                    if isinstance(loc_list, list):
                        if old_name in loc_list:
                            if new_name in loc_list:
                                changes.append(
                                    f"{field_name}.{city_key}: merged"
                                )
                                needs_merge = True
                            else:
                                changes.append(
                                    f"{field_name}.{city_key}: renamed"
                                )
        else:
            if isinstance(field_data, list):
                if old_name in field_data:
                    if new_name in field_data:
                        changes.append(f"{field_name}: merged")
                        needs_merge = True
                    else:
                        changes.append(f"{field_name}: renamed")

        if not changes:
            return

        # Apply text-based replacement on the frontmatter only
        new_frontmatter = self._apply_md_text_rename(
            frontmatter_text, old_name, new_name, needs_merge
        )

        rel_path = path.relative_to(self.md_dir) if self.md_dir else path
        detail = "; ".join(changes)
        action = "merged" if needs_merge else "renamed"
        report.md_changes.append(
            RenameAction(file=rel_path, action=action, detail=detail)
        )
        if not dry_run:
            rebuilt = f"---{new_frontmatter}---{content}"
            path.write_text(rebuilt, encoding="utf-8")

    def _apply_md_text_rename(
        self,
        frontmatter: str,
        old_name: str,
        new_name: str,
        needs_merge: bool,
    ) -> str:
        """
        Apply rename or merge via text replacement on raw frontmatter.

        For rename: replaces old_name with new_name as a complete
        list item (avoiding substring matches).
        For merge: removes old_name as a list item entirely.

        Uses exact item matching to prevent substring collisions
        (e.g., "Home" must not match inside "Bar Home").

        Args:
            frontmatter: Raw frontmatter text (between --- delimiters)
            old_name: Name to find
            new_name: Name to replace with
            needs_merge: If True, remove old_name instead of replacing

        Returns:
            Updated frontmatter text with the same formatting
        """
        escaped = re.escape(old_name)
        block_item_re = re.compile(
            rf"-\s+{escaped}$|"
            rf'-\s+"{escaped}"$|'
            rf"-\s+'{escaped}'$"
        )

        lines = frontmatter.split("\n")
        new_lines = []

        for line in lines:
            stripped = line.strip()

            if needs_merge:
                # Block-style: remove entire line "- OldName"
                if block_item_re.fullmatch(stripped):
                    continue

                # Flow-style: rebuild bracketed list without old_name
                if "[" in line and old_name in line:
                    line = self._remove_flow_item(line, old_name)
            else:
                # Block-style rename: "- OldName" → "- NewName"
                if block_item_re.fullmatch(stripped):
                    line = line.replace(old_name, new_name, 1)
                # Flow-style rename: replace exact item
                elif "[" in line and old_name in line:
                    line = self._replace_flow_item(
                        line, old_name, new_name
                    )

            new_lines.append(line)

        return "\n".join(new_lines)

    @staticmethod
    def _remove_flow_item(line: str, item: str) -> str:
        """
        Remove an exact item from a YAML flow-style list in a line.

        Parses the bracketed portion, splits by ", ", removes the
        exact match, and reconstructs.

        Args:
            line: Line containing a flow-style list
            item: Exact item name to remove

        Returns:
            Line with the item removed
        """
        match = re.search(r'\[([^\]]*)\]', line)
        if not match:
            return line

        items = [i.strip() for i in match.group(1).split(",")]
        items = [i for i in items if i != item]
        replacement = "[" + ", ".join(items) + "]"
        return line[:match.start()] + replacement + line[match.end():]

    @staticmethod
    def _replace_flow_item(
        line: str, old_item: str, new_item: str
    ) -> str:
        """
        Replace an exact item in a YAML flow-style list in a line.

        Parses the bracketed portion, splits by ", ", replaces the
        exact match, and reconstructs.

        Args:
            line: Line containing a flow-style list
            old_item: Exact item name to find
            new_item: Replacement item name

        Returns:
            Line with the item replaced
        """
        match = re.search(r'\[([^\]]*)\]', line)
        if not match:
            return line

        items = [i.strip() for i in match.group(1).split(",")]
        items = [new_item if i == old_item else i for i in items]
        replacement = "[" + ", ".join(items) + "]"
        return line[:match.start()] + replacement + line[match.end():]

    # ---- YAML I/O ----

    def _load_yaml(self, path: Path) -> Any:
        """
        Load a YAML file using ruamel.yaml round-trip parser.

        Args:
            path: Path to the YAML file

        Returns:
            Parsed YAML data or None if file cannot be read
        """
        try:
            with open(path, encoding="utf-8") as f:
                return self._yaml.load(f)
        except Exception:
            return None

    def _save_yaml(self, path: Path, data: Any) -> None:
        """
        Write YAML data back to file preserving formatting.

        Creates parent directories if needed.

        Args:
            path: Output file path
            data: YAML data to write
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            self._yaml.dump(data, f)

    # ---- Utility methods ----

    def _find_entity_file(
        self,
        base_dir: Path,
        slug: str,
    ) -> tuple:
        """
        Search all city subdirectories for a per-entity file.

        Used when no --city is specified for location lookups.

        Args:
            base_dir: Base directory to search (e.g., metadata/locations/)
            slug: Entity slug to find

        Returns:
            Tuple of (path, city_slug) or (None, None) if not found
        """
        if not base_dir.exists():
            return None, None
        filename = f"{slug}.yaml"
        for city_dir in sorted(base_dir.iterdir()):
            if city_dir.is_dir():
                candidate = city_dir / filename
                if candidate.exists():
                    return candidate, city_dir.name
        return None, None

    def _rename_dict_key(
        self,
        d: Any,
        old_key: str,
        new_key: str,
    ) -> None:
        """
        Rename a dictionary key in place, preserving insertion order.

        Creates a new ordered dict with the key renamed at the same
        position in the ordering.

        Args:
            d: Dictionary to modify (ruamel.yaml CommentedMap)
            old_key: Key to rename
            new_key: New key name
        """
        if old_key not in d:
            return

        # Build ordered list of (key, value) pairs with rename
        items = []
        for key in list(d.keys()):
            if key == old_key:
                items.append((new_key, d[old_key]))
            else:
                items.append((key, d[key]))

        # Clear and rebuild
        for key in list(d.keys()):
            del d[key]
        for key, value in items:
            d[key] = value

    def _relative_path(self, path: Path) -> Path:
        """
        Compute path relative to the metadata directory.

        Args:
            path: Absolute path

        Returns:
            Path relative to metadata_dir, or the original path
            if not under metadata_dir
        """
        try:
            return path.relative_to(self.metadata_dir)
        except ValueError:
            return path
