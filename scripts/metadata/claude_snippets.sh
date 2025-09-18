# Alembic Setup and Migration Workflow for Journal Database

# 1. Installation
pip install alembic sqlalchemy pyyaml

# 2. Initialize Alembic (run once)
python journal_db.py init_alembic

# This creates the alembic/ directory structure:
# alembic/
# ├── env.py              # Alembic environment configuration
# ├── script.py.mako      # Template for new migration files
# ├── alembic.ini         # Alembic configuration file
# └── versions/           # Directory for migration files

# 3. Create your first migration (after setting up models)
python journal_db.py create_migration message="Initial schema"

# 4. Apply migrations
python journal_db.py upgrade

# 5. Check migration status
python journal_db.py migration_status

# ========================================
# MIGRATION WORKFLOW EXAMPLES
# ========================================

# Scenario 1: Adding a new field to Entry model
# 1. Modify the Entry model in journal_db.py:
#    mood = Column(String)
#
# 2. Create migration:
python journal_db.py create_migration message="Add mood field to entries"
#
# 3. Apply migration:
python journal_db.py upgrade

# Scenario 2: Adding a new table
# 1. Add new model class in journal_db.py
# 2. Create migration:
python journal_db.py create_migration message="Add mood_categories table"
# 3. Apply migration:
python journal_db.py upgrade

# Scenario 3: Data migration (populate default values)
# After creating the migration file, you can edit it to add custom logic
# The generated file will be in alembic/versions/

# Scenario 4: Rollback a migration
python journal_db.py downgrade revision="previous_revision_id"

# ========================================
# REPOPULATION STRATEGIES
# ========================================

# Strategy 1: Schema changes that don't affect parsing
# (Adding indexes, new optional columns)
python journal_db.py upgrade
python journal_db.py sync_directory directory=/path/to/journals

# Strategy 2: Schema changes that affect data structure
# (New metadata fields, changed relationships)
python journal_db.py backup suffix="before_schema_change"
python journal_db.py upgrade
python journal_db.py repopulate directory=/path/to/journals force=true

# Strategy 3: Major restructuring
python journal_db.py backup suffix="before_major_change"
python journal_db.py create_migration message="Major restructuring"
# Edit the migration file to include data transformation logic
python journal_db.py upgrade
python journal_db.py repopulate directory=/path/to/journals force=true

# ========================================
# CUSTOM ALEMBIC.INI CONFIGURATION
# ========================================

# Create alembic.ini file (or it's auto-generated):
cat >alembic.ini <<'EOF'
# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = alembic

# template used to generate migration files
# file_template = %%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the python-dateutil library that can be
# installed by adding `alembic[tz]` to the pip requirements
# string value is passed to dateutil.tz.gettz()
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version number format (uses % formatter)
version_num_format = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s

# version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses
# os.pathsep. If this key is omitted entirely, it falls back to the legacy
# behavior of splitting on spaces and/or commas.
# Valid values for version_path_separator are:
#
# version_path_separator = :
# version_path_separator = ;
# version_path_separator = space
version_path_separator = os

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = sqlite:///journal_archive.db

[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

# ========================================
# EXAMPLE MIGRATION FILE STRUCTURE
# ========================================

# This is what a generated migration file looks like:
# alembic/versions/20250916_1430_add_mood_field.py

cat >example_migration.py <<'EOF'
"""Add mood field to entries

Revision ID: 20250916_1430
Revises: 20250915_0900
Create Date: 2025-09-16 14:30:00.123456

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250916_1430'
down_revision = '20250915_0900'
branch_labels = None
depends_on = None

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('entries', sa.Column('mood', sa.String(), nullable=True))
    op.add_column('entries', sa.Column('mood_scale', sa.Integer(), nullable=True))
    # ### end Alembic commands ###
    
    # Custom data migration logic can go here
    # For example, set default moods for existing entries:
    op.execute("UPDATE entries SET mood = 'neutral' WHERE mood IS NULL")

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('entries', 'mood_scale')
    op.drop_column('entries', 'mood')
    # ### end Alembic commands ###
EOF

# ========================================
# ADVANCED MIGRATION SCENARIOS
# ========================================

# Complex data transformation migration:
cat >advanced_migration_example.py <<'EOF'
"""Transform location data to hierarchical format

Revision ID: 20250916_1500
Revises: 20250916_1430
Create Date: 2025-09-16 15:00:00.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text

# Import your models
from journal_db import Location

revision = '20250916_1500'
down_revision = '20250916_1430'
branch_labels = None
depends_on = None

def upgrade():
    # First add the new columns
    op.add_column('locations', sa.Column('canonical_name', sa.String(), nullable=True))
    op.add_column('locations', sa.Column('parent_location', sa.String(), nullable=True))
    op.add_column('locations', sa.Column('location_type', sa.String(), nullable=True))
    op.add_column('locations', sa.Column('coordinates', sa.String(), nullable=True))
    
    # Then populate them with transformed data
    bind = op.get_bind()
    session = Session(bind=bind)
    
    # Transform existing location data
    locations = session.execute(text("SELECT id, name FROM locations")).fetchall()
    
    for location_id, name in locations:
        # Your custom logic to parse location hierarchy
        canonical_name, parent, loc_type = parse_location_hierarchy(name)
        
        session.execute(
            text("UPDATE locations SET canonical_name = :canonical, parent_location = :parent, location_type = :type WHERE id = :id"),
            {
                'canonical': canonical_name,
                'parent': parent,
                'type': loc_type,
                'id': location_id
            }
        )
    
    session.commit()

def downgrade():
    op.drop_column('locations', 'coordinates')
    op.drop_column('locations', 'location_type')
    op.drop_column('locations', 'parent_location')
    op.drop_column('locations', 'canonical_name')

def parse_location_hierarchy(name):
    # Custom logic to parse location names
    if ',' in name:
        parts = [p.strip() for p in name.split(',')]
        canonical = name
        if len(parts) > 1:
            parent = ', '.join(parts[1:])
            loc_type = 'city'
        else:
            parent = None
            loc_type = 'venue'
    else:
        canonical = name
        parent = None
        loc_type = 'venue'
    
    return canonical, parent, loc_type
EOF

echo "Alembic setup complete!"
echo "Run: python journal_db.py init_alembic to get started"
