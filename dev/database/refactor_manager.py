#!/usr/bin/env python3
"""Refactor manager.py to remove all entity CRUD methods"""

# Read manager.py
with open('manager.py', 'r') as f:
    lines = f.readlines()

# Find the exact boundaries
city_crud_start = None
cleanup_start = None

for i, line in enumerate(lines):
    if '# ---- City CRUD ----' in line and city_crud_start is None:
        # Find the SECOND occurrence (first is in entry relationships)
        if city_crud_start is not None:
            continue
        # Check if this is around line 1900+
        if i > 1900:
            city_crud_start = i
            print(f"City CRUD starts at line {i+1}")

    if '# ----- Cleanup Operations -----' in line:
        cleanup_start = i
        print(f"Cleanup starts at line {i+1}")
        break

if city_crud_start and cleanup_start:
    print(f"\nWill delete lines {city_crud_start+1} to {cleanup_start}")
    print(f"Total lines to delete: {cleanup_start - city_crud_start}")

    # Create new content
    new_lines = lines[:city_crud_start]

    # Add comment explaining delegation
    new_lines.append("\n")
    new_lines.append("    # -------------------------------------------------------------------------\n")
    new_lines.append("    # Entity Operations Delegated to Modular Managers\n")
    new_lines.append("    # -------------------------------------------------------------------------\n")
    new_lines.append("    # All entity-specific CRUD operations are now handled by specialized managers.\n")
    new_lines.append("    #\n")
    new_lines.append("    # Use the manager properties within session_scope:\n")
    new_lines.append("    #   - db.people: PersonManager\n")
    new_lines.append("    #   - db.events: EventManager\n")
    new_lines.append("    #   - db.locations: LocationManager\n")
    new_lines.append("    #   - db.references: ReferenceManager\n")
    new_lines.append("    #   - db.poems: PoemManager\n")
    new_lines.append("    #   - db.manuscripts: ManuscriptManager\n")
    new_lines.append("    #   - db.tags: TagManager\n")
    new_lines.append("    #   - db.dates: DateManager\n")
    new_lines.append("    #\n")
    new_lines.append("    # Example:\n")
    new_lines.append("    #   with db.session_scope() as session:\n")
    new_lines.append("    #       person = db.people.create({\"name\": \"Alice\"})\n")
    new_lines.append("    #       event = db.events.create({\"name\": \"PyCon 2024\"})\n")
    new_lines.append("    # -------------------------------------------------------------------------\n")
    new_lines.append("\n")

    # Add remaining lines from cleanup onwards
    new_lines.extend(lines[cleanup_start:])

    # Write back
    with open('manager.py', 'w') as f:
        f.writelines(new_lines)

    print(f"\n✓ Refactoring complete!")
    print(f"  Original: {len(lines)} lines")
    print(f"  New: {len(new_lines)} lines")
    print(f"  Reduction: {len(lines) - len(new_lines)} lines")
else:
    print("ERROR: Could not find boundaries!")
