#!/usr/bin/env python3
"""
Identify problematic scene/event names in YAML metadata files.
Outputs a JSON file with problematic names and their descriptions.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


def is_problematic_scene_name(name: str) -> Tuple[bool, str]:
    """Check if a scene name has problematic formatting."""
    reasons = []

    if ':' in name:
        reasons.append("contains colon")
    if '(' in name:
        reasons.append("contains parentheses")
    if name.startswith('INT.') or name.startswith('EXT.'):
        reasons.append("screenwriting format (INT./EXT.)")
    if name.startswith('FLASHBACK:'):
        reasons.append("flashback prefix with colon")
    if re.search(r'^[A-Z\s]+ - (DAY|NIGHT|MORNING|AFTERNOON|EVENING|EARLY|LATE)', name, re.IGNORECASE):
        reasons.append("screenwriting format (LOCATION - TIME)")

    return (True, "; ".join(reasons)) if reasons else (False, "")


def is_problematic_event_name(name: str) -> Tuple[bool, str]:
    """Check if an event name has problematic formatting."""
    reasons = []

    if ':' in name:
        reasons.append("contains colon")
    if re.search(r'\(20\d{2}', name):
        reasons.append("contains date in parentheses")
    if re.match(r'^[TS]\s+[A-Z]', name):
        reasons.append("starts with single letter T/S (likely truncated)")

    # Check for incomplete contractions (truncation)
    incomplete_patterns = [
        r"Doesn\s*$", r"Didn\s*$", r"Wasn\s*$", r"Hasn\s*$",
        r"Won\s*$", r"Shouldn\s*$", r"Couldn\s*$", r"Wouldn\s*$",
        r"Can\s*$", r"Don\s*$", r"Aren\s*$", r"Isn\s*$"
    ]

    for pattern in incomplete_patterns:
        if re.search(pattern, name):
            reasons.append("ends with incomplete contraction (truncated)")
            break

    # Only flag very obvious truncations (single lowercase letters at end)
    # Skip the heuristic check - too many false positives

    return (True, "; ".join(reasons)) if reasons else (False, "")


def analyze_file(file_path: Path) -> Dict:
    """Analyze a single YAML file for problematic names."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    result = {
        'file': str(file_path.relative_to('/home/soffiafdz/Documents/palimpsest')),
        'date': str(data.get('date', '')),
        'summary': data.get('summary', ''),
        'problematic_scenes': [],
        'problematic_events': []
    }

    # Check scenes
    for scene in data.get('scenes', []):
        name = scene.get('name', '')
        is_prob, reason = is_problematic_scene_name(name)
        if is_prob:
            result['problematic_scenes'].append({
                'name': name,
                'description': scene.get('description', ''),
                'reason': reason
            })

    # Check events
    for event in data.get('events', []):
        name = event.get('name', '')
        is_prob, reason = is_problematic_event_name(name)
        if is_prob:
            result['problematic_events'].append({
                'name': name,
                'scenes': event.get('scenes', []),
                'reason': reason
            })

    return result if (result['problematic_scenes'] or result['problematic_events']) else None


def main():
    """Scan all YAML files and identify problematic names."""
    base_path = Path('/home/soffiafdz/Documents/palimpsest/data/metadata/journal')

    # Find all YAML files for 2021-2024 (excluding 2024-11 onwards)
    yaml_files = []
    for year in ['2021', '2022', '2023', '2024']:
        year_path = base_path / year
        if year_path.exists():
            for yaml_file in sorted(year_path.glob('*.yaml')):
                # Skip 2024-11 and onwards
                if year == '2024' and yaml_file.stem >= '2024-11-01':
                    continue
                yaml_files.append(yaml_file)

    print(f"Scanning {len(yaml_files)} files...")

    results = []
    for yaml_file in yaml_files:
        result = analyze_file(yaml_file)
        if result:
            results.append(result)

    # Write output
    output = {
        'total_files_scanned': len(yaml_files),
        'files_with_problems': len(results),
        'files': results
    }

    output_path = Path('/home/soffiafdz/Documents/palimpsest/problematic_names_identified.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nFound {len(results)} files with problematic names")
    print(f"Results written to: {output_path}")

    # Summary stats
    total_scenes = sum(len(r['problematic_scenes']) for r in results)
    total_events = sum(len(r['problematic_events']) for r in results)
    print(f"\nTotal problematic scenes: {total_scenes}")
    print(f"Total problematic events: {total_events}")


if __name__ == '__main__':
    main()
