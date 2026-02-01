#!/usr/bin/env python3
"""Extract all scene and event names from YAML files."""

import yaml
from pathlib import Path

def extract_names_for_year(year: str):
    """Extract all scene and event names for a given year."""
    base_path = Path('/home/soffiafdz/Documents/palimpsest/data/metadata/journal')
    year_path = base_path / year

    scene_names = []
    event_names = []

    for yaml_file in sorted(year_path.glob('*.yaml')):
        # Skip 2024-11 onwards
        if year == '2024' and yaml_file.stem >= '2024-11-01':
            continue

        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        file_ref = yaml_file.stem

        # Extract scene names
        for scene in data.get('scenes', []):
            name = scene.get('name', '')
            if name:
                scene_names.append(f"{file_ref}\t{name}")

        # Extract event names
        for event in data.get('events', []):
            name = event.get('name', '')
            if name:
                event_names.append(f"{file_ref}\t{name}")

    return scene_names, event_names

# Process each year
for year in ['2021', '2022', '2023', '2024']:
    scene_names, event_names = extract_names_for_year(year)

    with open(f'{year}_scene_names.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(scene_names))

    with open(f'{year}_event_names.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(event_names))

    print(f"{year}: {len(scene_names)} scenes, {len(event_names)} events")
