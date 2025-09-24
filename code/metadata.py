#!/usr/bin/env python3
"""
metadata.py
-------------------

Defines the MetaEntry and MetadataRegistry classes representing the metadata for
the journal entries in the Palimpsest system.

These classes are used by the txt2md, md2pdf, md2wiki pipelines.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
import warnings
from pathlib import Path
from typing import Any, Dict, Set, TypedDict


# ---- Classes ----
# -- Single entry
class MetaEntry(TypedDict, total=False):
    """
    Dictionary type representing the metadata associated with a journal entry.

    Each key corresponds to a field in the YAML frontmatter or registry.
    All fields are optional to allow for flexible and partial updates.

    Fields:
        date (str): Date in isoformat. This will also be the key.
        word_count (int): Total word count of the entry.
        reading_time (float): Estimated reading time in minutes.
        status (str): Curation status:
            unreviewed:         self-explanatory
            discard:            not usable
            reference:          important events, but content unusable
            fragments:          potentially useful lines/snippets
            source:             content will be rewritten
            quote:              (some) content will be adapted as is
        excerpted (bool):       Whether content will be used for manuscript.
        epigraph (str):         If/what type of epigraph is used:
            reference:          fragment of a book|song|movie|tv series
            quote:              a quotation from someone in real life
            intention:          something that I planned/intended to say
            poem:               a poem
        people (Set[str]):      Names of referenced people (besides narrator).
        references (Set[str]):  Dates/Events references (including that day).
        themes (Set[str]):      Thematic tags for the entry.
        tags (Set[str]):        Additional tags or keywords.
        manuscript_links (Set[str]): Link(s) or identifier(s) to final usage.
        notes (str):            Reviewer notes or curation comments.
    """

    date: str
    word_count: int
    reading_time: float
    status: str
    excerpted: bool
    epigraph: str
    people: Set[str]
    references: Set[str]
    themes: Set[str]
    tags: Set[str]
    manuscript_links: Set[str]
    notes: str


## -- Central registry --
class MetadataRegistry:
    """
    Central registry for managing entry metadata as a JSON file.

    Loads, updates, and saves a mapping of unique entry keys (typically dates)
    to their associated metadata (`MetaEntry`).

    Args:
        path (Path): Path to the JSON file to use for storing the registry.

    Attributes:
        path (Path): Path to the registry JSON file.
        _data (dict[str, MetaEntry]): In-memory mapping of keys to metadata.

    Methods:
        load(): Reload the registry from disk.
        save(): Write the current registry to disk.
        get(key): Retrieve metadata for the given key, or {} if missing.
        update(key, new_data): Merge new fields into the entry for key.
        all(): Return the full metadata mapping.

    Static methods:
        serialize_metaentry(MetaEntry):         Converts sets -> lists
        deserialize_metaenry(Dict[str], Any):   Converts (back) lists -> sets
    """

    def __init__(self, path: Path):
        """
        Initialize and (if possible) load the registry from file.
        """
        self.path = path
        self.validator = MetadataValidator()
        self.load()

    def load(self) -> None:
        """
        Load the registry from the JSON file, converting lists to sets.
        If file does not exist or is unreadable, initializes an empty registry.
        """
        self._data: Dict[str, MetaEntry]
        if not self.path.exists():
            self._data = {}
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            self._data = {k: self.deserialize_metaentry(v) for k, v in raw.items()}
        except Exception as e:
            warnings.warn(
                f"[MetadataRegistry] Could not load {str(self.path)}: {e}\n"
                "Metadata will be initialized as empty.",
                UserWarning,
            )
            self._data = {}

    def save(self) -> None:
        """
        Save the in-memory registry to the JSON file, converting sets to lists.
        """
        try:
            serializable = {
                k: self.serialize_metaentry(v) for k, v in self._data.items()
            }
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise OSError(
                f"[MetadataRegistry] Could not save to {str(self.path)}: {e}"
            ) from e

    @staticmethod
    def serialize_metaentry(entry: MetaEntry) -> Dict[str, Any]:
        """
        Convert sets to lists for JSON serialization.
        """
        result: Dict[str, Any] = {}
        for k, v in entry.items():
            if isinstance(v, set):
                result[k] = sorted(v)  # Sorting makes diffs nicer but is optional
            else:
                result[k] = v
        return result

    @staticmethod
    def deserialize_metaentry(entry: Dict[str, Any]) -> MetaEntry:
        """
        Convert lists back to sets for set fields after loading from JSON.
        """
        fields_as_sets: Set[str] = {
            "people",
            "references",
            "themes",
            "tags",
            "manuscript_links",
        }
        return {
            k: set(v) if k in fields_as_sets and isinstance(v, list) else v
            for k, v in entry.itmes()
        }

    def get(self, key: str) -> MetaEntry:
        """
        Retrieve metadata for a given key (date string).
        Returns {} if not found.
        """
        return self._data.get(key, self.validator.normalize({}))

    def update(self, key: str, new_data: Dict[str, Any]) -> None:
        """
        Merge new_data into the entry for key, preserving non-overwritten
        fields. Only non-empty values in new_data are set.
        """
        old = self._data.get(key, {})
        for k, v in new_data.items():
            if v not in [None, "", [], {}, set()]:
                if isinstance(v, list):
                    v = set(v)
                old[k] = v
        self._data[key] = old

    def all(self) -> Dict[str, MetaEntry]:
        """
        Return the entire metadata registry in memory.
        """
        return self._data


## -- Validator --
class MetadataValidator:
    """
    Provides validation, normalization, and default-checking utilities for
    journal entry metadata dictionaries (MetaEntry).

    - Ensures fields are present and of correct types.
    - Converts list fields (e.g., 'people', 'tags', 'themes') to sets.
    - Supplies canonical default values for all metadata fields.
    - Detects whether a given metadata dict is "default/empty".
    - Reports missing or malformed fields.

    Intended use cases include:
        - Cleaning and validating metadata parsed from Markdown YAML frontmatter
          or other sources.
        - Checking for curation status before writing to the central registry
          (e.g., skipping all-default entries).
        - Enforcing schema consistency across pipelines and scripts.
        - Supporting migration or upgrade scripts that may need to check, fill,
          or coerce metadata fields.

    Methods:
        - normalize(meta):
            Ensure correct types, fill missing optional fields with defaults.
        - is_default(meta):
            Return True if all (non-identity) fields match their default values.
        - validate(meta):
            Check for presence and type of required/optional fields.
        - extract_yaml_frontmatter(md_file):
            Extractr metadata from a MD file.
    """

    def __init__(self):
        self.defaults = {
            "word_count": 0,
            "reading_time": 0.0,
            "status": "unreviewed",
            "excerpted": False,
            "epigraph": "",
            "people": set(),
            "references": set(),
            "themes": set(),
            "tags": set(),
            "manuscript_links": set(),
            "notes": "",
        }

    def normalize(self, meta: Dict[str, Any]) -> MetaEntry:
        """
        Ensures all expected fields are present and correct types.
        Converts links/people/tags/themes to sets.
        """
        meta = dict(meta)  # make a copy
        for k in ("manuscript_links", "people", "tags", "themes"):
            if k in meta and isinstance(meta[k], list):
                meta[k] = set(meta[k])
            elif k not in meta:
                meta[k] = set()
        for k, v in self.defaults.items():
            if k not in meta:
                meta[k] = v
        return meta  # type: ignore

    def is_default(self, meta: Dict[str, Any]) -> bool:
        """
        Return True if all values (except id fields) are defaults.
        """
        for k, default_val in self.defaults.items():
            val = meta.get(k)
            if isinstance(default_val, set):
                if set(val or []) != default_val:
                    return False
            else:
                if val != default_val:
                    return False
        return True

    def validate(self, meta: Dict[str, Any]) -> bool:
        """
        Check that all present fields are of correct type.
        """
        required_fields = {"date": str}
        field_types = {
            "word_count": int,
            "reading_time": (float, int),
            "status": str,
            "excerpted": bool,
            "epigraph": str,
            "people": (set, list),
            "references": (set, list),
            "themes": (set, list),
            "tags": (set, list),
            "manuscript_links": (set, list),
            "notes": str,
        }
        ok = True
        # for k, T in required_fields.items():
        # if k not in meta or not isinstance(meta[k], T):
        # warnings.warn(
        # f"Warning: missing or invalid required field '{k}'",
        # UserWarning
        # )
        # ok = False
        for k, T in field_types.items():
            if k in meta and not isinstance(meta[k], T):
                warnings.warn(
                    f"Warning: field '{k}' has wrong type ({type(meta[k])})",
                    UserWarning,
                )
                ok = False
        return ok

    @staticmethod
    def extract_yaml_frontmatter(md_path: Path) -> Dict[str, Any]:
        """
        Extract YAML frontmatter from a Markdown file.
        """
        try:
            with md_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            raise OSError(f"Could not read Markdown file: {str(md_path)}: {e}")

        if not lines or lines[0].strip() != "---":
            return {}
        yaml_lines = []
        for line in lines[1:]:
            if line.strip() == "---":
                break
            yaml_lines.append(line)
        if not yaml_lines:
            return {}
        try:
            return yaml.safe_load("".join(yaml_lines)) or {}
        except Exception as e:
            warnings.warn(
                "Warning: Could not parse YAML frontmatter from "
                f"{str(md_path)}: {k}'",
                UserWarning,
            )
            return {}
