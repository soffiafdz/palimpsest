# Journal Database with Alembic Migrations - Complete Guide

## Initial Setup

### 1. Install Dependencies

```bash
pip install alembic sqlalchemy pyyaml
```

### 2. Initialize Alembic (One-time setup)

```bash
# Initialize the migration system
python journal_db.py init_alembic

# This creates:
# alembic/
# ├── env.py              # Environment configuration
# ├── script.py.mako      # Migration template
# ├── alembic.ini         # Configuration file
# └── versions/           # Migration files directory
```

### 3. Create Initial Migration

```bash
# After setting up your initial models
python journal_db.py create_migration message="Initial schema"

# Apply the migration
python journal_db.py upgrade
```

## Daily Workflow

### Adding New Features

#### Scenario 1: Add New Field to Existing Model

```python
# 1. Modify journal_db.py - add to Entry class:
class Entry(Base):
    # ... existing fields ...
    mood = Column(String)                    # NEW FIELD
    mood_scale = Column(Integer)             # NEW FIELD
```

```bash
# 2. Create migration
python journal_db.py create_migration message="Add mood tracking to entries"

# 3. Review generated migration file in alembic/versions/
# 4. Apply migration
python journal_db.py upgrade

# 5. No repopulation needed for new optional fields
python journal_db.py sync_directory directory=/path/to/journals
```

#### Scenario 2: Add New Model/Table

```python
# 1. Add new model to journal_db.py:
class MoodCategory(Base):
    __tablename__ = 'mood_categories'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color_hex = Column(String)
    description = Column(Text)
```

```bash
# 2. Create and apply migration
python journal_db.py create_migration message="Add mood categories table"
python journal_db.py upgrade

# 3. Populate with default data if needed
python journal_db.py sync_directory directory=/path/to/journals
```

### Major Schema Changes

#### Scenario 3: Restructure Existing Data

```python
# 1. Modify models with new structure
# 2. Create migration
python journal_db.py create_migration message="Restructure location hierarchy"

# 3. Edit the generated migration file to include data transformation:
```

```python
# In alembic/versions/xxx_restructure_location.py:
def upgrade():
    # Add new columns
    op.add_column('locations', sa.Column('canonical_name', sa.String()))

    # Transform existing data
    bind = op.get_bind()
    session = Session(bind=bind)

    locations = session.execute(text("SELECT id, name FROM locations")).fetchall()
    for loc_id, name in locations:
        canonical = standardize_location_name(name)
        session.execute(
            text("UPDATE locations SET canonical_name = :canonical WHERE id = :id"),
            {'canonical': canonical, 'id': loc_id}
        )
    session.commit()
```

```bash
# 4. Backup and apply
python journal_db.py backup suffix="before_location_restructure"
python journal_db.py upgrade

# 5. Full repopulation may be needed
python journal_db.py repopulate directory=/path/to/journals force=true
```

## Migration Management

### Check Current Status

```bash
# See current migration state
python journal_db.py migration_status

# View database stats including migration info
python journal_db.py stats
```

### Rollback Migrations

```bash
# Rollback to specific revision
python journal_db.py downgrade revision="previous_revision_id"

# Rollback one step
python journal_db.py downgrade revision="-1"
```

### Advanced Migration Operations

```bash
# Create empty migration for custom logic
alembic revision -m "Custom data transformation"

# Merge multiple migration branches
alembic merge -m "Merge feature branches" head1 head2

# Show migration history
alembic history --verbose
```

## Repopulation Strategies

### 1. Schema-Only Changes (No Repopulation Needed)

- Adding new optional columns
- Adding indexes
- Adding new tables that don't affect parsing

```bash
python journal_db.py upgrade
python journal_db.py sync_directory directory=/path/to/journals
```

### 2. New Metadata Fields (Partial Repopulation)

- Adding new YAML fields to track
- New relationship types

```bash
python journal_db.py backup suffix="before_new_fields"
python journal_db.py upgrade
python journal_db.py repopulate directory=/path/to/journals force=true
```

### 3. Data Structure Changes (Full Repopulation)

- Changing how existing fields are parsed
- Restructuring relationships
- Complex data transformations

```bash
python journal_db.py backup suffix="before_major_change"
python journal_db.py upgrade
python journal_db.py repopulate directory=/path/to/journals force=true
```

## Best Practices

### 1. Always Backup Before Major Changes

```bash
# Create backup with descriptive suffix
python journal_db.py backup suffix="before_mood_tracking_feature"
```

### 2. Test Migrations on Sample Data

```bash
# Copy database for testing
cp journal_archive.db journal_test.db

# Test migration on copy first
# Modify journal_db.py to use journal_test.db
python journal_db.py upgrade
```

### 3. Descriptive Migration Messages

```bash
# Good migration messages
python journal_db.py create_migration message="Add mood tracking fields to entries"
python journal_db.py create_migration message="Create mood_categories lookup table"
python journal_db.py create_migration message="Transform location data to hierarchical structure"

# Bad migration messages
python journal_db.py create_migration message="updates"
python journal_db.py create_migration message="fix stuff"
```

### 4. Review Generated Migrations

Always review the auto-generated migration files in `alembic/versions/` before applying:

```python
# Example: Good migration with custom logic
def upgrade():
    # Auto-generated schema changes
    op.add_column('entries', sa.Column('mood', sa.String(), nullable=True))

    # Custom data population
    op.execute("UPDATE entries SET mood = 'neutral' WHERE mood IS NULL")

    # Create default mood categories
    mood_categories_table = table('mood_categories',
        column('id', Integer),
        column('name', String),
        column('color_hex', String)
    )

    op.bulk_insert(mood_categories_table, [
        {'name': 'happy', 'color_hex': '#FFD700'},
        {'name': 'sad', 'color_hex': '#4169E1'},
        {'name': 'neutral', 'color_hex': '#C0C0C0'},
    ])
```

## Troubleshooting

### Common Issues

1. **Migration fails due to data constraints**

   ```bash
   # Check what data would be affected
   python -c "
   from journal_db import JournalDB
   db = JournalDB()
   with db.get_session() as session:
       # Inspect problematic data
   "
   ```

2. **Need to rollback and fix migration**

   ```bash
   python journal_db.py downgrade revision="previous_revision"
   # Edit migration file
   python journal_db.py upgrade
   ```

3. **Database out of sync with models**

   ```bash
   # Stamp database with current model state
   alembic stamp head
   ```

### Recovery Procedures

1. **Corrupted migration**

   ```bash
   # Restore from backup
   cp journal_archive.db.backup_20250916_143000 journal_archive.db
   python journal_db.py migration_status
   ```

2. **Lost migration files**

   ```bash
   # Recreate migration history from current database
   alembic revision --autogenerate -m "Recreate migration history"
   ```

## Integration with Development Workflow

### Version Control

```bash
# Always commit migration files
git add alembic/versions/
git commit -m "Add mood tracking migration"

# Include model changes
git add journal_db.py
git commit -m "Add mood fields to Entry model"
```

### Continuous Integration

```bash
# In CI/CD pipeline
python journal_db.py upgrade  # Apply pending migrations
python journal_db.py stats    # Verify database state
```

This Alembic-based approach provides professional-grade database migration management that scales with your project and ensures data integrity throughout the evolution of your journal archive system.
