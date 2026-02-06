"""
dataclasses package
-------------------
Dataclass definitions for journal entries and metadata.

This package provides dataclasses for representing journal entries
in different formats:
- TxtEntry: Raw text entries from 750words exports
- MetadataEntry: Standalone metadata YAML files with narrative analysis
"""
from dev.dataclasses.metadata_entry import MetadataEntry
from dev.dataclasses.txt_entry import TxtEntry

__all__ = ["MetadataEntry", "TxtEntry"]
