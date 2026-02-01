#!/usr/bin/env python3
"""Create a consolidated list of files with problematic names to fix."""

import re

def is_problematic_scene(name):
    """Check if scene name needs fixing."""
    if ':' in name:
        return True
    if name.startswith(('INT.', 'EXT.', 'FLASHBACK')):
        return True
    if re.search(r'^[A-Z\s]+ - (DAY|NIGHT|MORNING|AFTERNOON|EVENING|EARLY|LATE|AM|PM)', name, re.IGNORECASE):
        return True
    return False

def is_problematic_event(name):
    """Check if event name needs fixing."""
    # Starts with single letter + space
    if re.match(r'^[TSDM]\s+[A-Z]', name):
        return True
    # Starts with Ll (I'll truncated)
    if name.startswith('Ll '):
        return True
    # Starts with Ve (I've truncated)
    if name.startswith('Ve '):
        return True
    # Ends with incomplete contraction
    if re.search(r"(Didn|Wasn|Hasn|Doesn|Won|Shouldn|Couldn|Wouldn|Can|Don|Aren|Isn|Hadn)\s*$", name):
        return True
    # Generic location format
    if re.match(r'^At [a-z]+$', name):
        return True
    # Ends abruptly with preposition/article (clearly incomplete)
    if re.search(r'\s(a|the|to|of|in|on|and|or|as|with|for|at|like)\s*$', name, re.IGNORECASE):
        return True
    return False

# Process each year
all_problems = {}

for year in ['2021', '2022', '2023', '2024']:
    with open(f'{year}_scene_names.txt', 'r', encoding='utf-8') as f:
        for line in f:
            file, name = line.strip().split('\t', 1)
            if is_problematic_scene(name):
                if file not in all_problems:
                    all_problems[file] = {'scenes': [], 'events': []}
                all_problems[file]['scenes'].append(name)

    with open(f'{year}_event_names.txt', 'r', encoding='utf-8') as f:
        for line in f:
            file, name = line.strip().split('\t', 1)
            if is_problematic_event(name):
                if file not in all_problems:
                    all_problems[file] = {'scenes': [], 'events': []}
                all_problems[file]['events'].append(name)

# Write output
with open('files_to_fix.txt', 'w', encoding='utf-8') as f:
    for file in sorted(all_problems.keys()):
        data = all_problems[file]
        f.write(f"\n{'='*60}\n")
        f.write(f"FILE: {file}.yaml\n")
        f.write(f"{'='*60}\n")
        if data['scenes']:
            f.write(f"\nSCENES TO FIX ({len(data['scenes'])}):\n")
            for scene in data['scenes']:
                f.write(f"  - {scene}\n")
        if data['events']:
            f.write(f"\nEVENTS TO FIX ({len(data['events'])}):\n")
            for event in data['events']:
                f.write(f"  - {event}\n")

total_scenes = sum(len(d['scenes']) for d in all_problems.values())
total_events = sum(len(d['events']) for d in all_problems.values())

print(f"Files with problems: {len(all_problems)}")
print(f"Total scenes to fix: {total_scenes}")
print(f"Total events to fix: {total_events}")
print(f"Output written to: files_to_fix.txt")
