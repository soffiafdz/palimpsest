#!/usr/bin/env python3
"""Script to remove entity CRUD methods from manager.py"""

# Read the file
with open('manager.py', 'r') as f:
    lines = f.readlines()

# Find sections to delete
sections_to_delete = []
in_section = False
start_line = None
section_markers = [
    '# DEPRECATED: Person Operations',
    '# ---- City CRUD ----',
    '# ---- Reference CRUD ----',
    '# ---- Event CRUD ----',
    '# ---- Poem CRUD ----',
    '# ---- Manuscript CRUD ----',
]

section_end_markers = [
    '# ----- Cleanup Operations -----',
    '# ---- Reference CRUD ----',
    '# ---- Event CRUD ----',
    '# ---- Poem CRUD ----',
    '# ---- Manuscript CRUD ----',
    '# ----- Cleanup Operations -----',
]

for i, line in enumerate(lines):
    stripped = line.strip()

    # Check if we're starting a section to delete
    for marker in section_markers:
        if marker in stripped:
            start_line = i
            in_section = True
            print(f"Found start of section at line {i+1}: {stripped}")
            break

    # Check if we're at cleanup (end of deletions)
    if '# ----- Cleanup Operations -----' in stripped and in_section:
        sections_to_delete.append((start_line, i))
        print(f"Found end at line {i+1}, will delete lines {start_line+1} to {i}")
        in_section = False
        start_line = None

print(f"\nSections to delete: {sections_to_delete}")
print(f"Total lines to delete: {sum(end - start for start, end in sections_to_delete)}")
