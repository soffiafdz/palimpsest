from dev.database.manager import PalimpsestDB
from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR
from alembic import command

db = PalimpsestDB(
    db_path=DB_PATH,
    alembic_dir=ALEMBIC_DIR,
    log_dir=LOG_DIR,
    backup_dir=BACKUP_DIR,
    enable_auto_backup=False,
)

# Stamp as base (no migrations applied)
command.stamp(db.alembic_cfg, "base")
print("✅ Reset to base")
