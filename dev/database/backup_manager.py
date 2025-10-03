#!/usr/bin/env python3
"""
backup_manager.py
--------------------
Database backup and recovery operations.
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from dev.core.logging_manager import PalimpsestLogger

from .exceptions import BackupError


class BackupManager:
    """
    Handles database backup and recovery operations.

    Provides automated backup creation with configurable retention policies
    and safe restore operations with pre-restore backup creation.
    """

    def __init__(
        self,
        db_path: Path,
        backup_dir: Path,
        retention_days: int = 30,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize backup manager.

        Args:
            db_path: Path to the database file
            backup_dir: Directory for backup storage
            retention_days: Days to retain backups
            logger: Optional logger for backup operations
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.logger = logger

        # Create backup directories
        (self.backup_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "weekly").mkdir(parents=True, exist_ok=True)
        (self.backup_dir / "manual").mkdir(parents=True, exist_ok=True)

    def create_backup(
        self, backup_type: str = "manual", suffix: Optional[str] = None
    ) -> Path:
        """
        Create a timestamped database backup.

        Args:
            backup_type: Type of backup (manual, daily, weekly)
            suffix: Optional suffix for backup filename

        Returns:
            Path to the created backup file

        Raises:
            BackupError: If backup creation fails
        """
        if not self.db_path.exists():
            raise BackupError(f"Database file not found: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
            backup_name = f"{self.db_path.stem}_{timestamp}_{suffix}.db"
        else:
            backup_name = f"{self.db_path.stem}_{timestamp}.db"

        backup_path = self.backup_dir / backup_type / backup_name

        try:
            source = sqlite3.connect(str(self.db_path))
            dest = sqlite3.connect(str(backup_path))

            with dest:
                source.backup(dest)

            source.close()
            dest.close()

            # Create marker file with creation timestamp
            marker_path = backup_path.with_suffix(".db.marker")
            marker_path.write_text(datetime.now().isoformat())

            if self.logger:
                self.logger.log_operation(
                    "backup_created",
                    {
                        "backup_type": backup_type,
                        "backup_path": str(backup_path),
                        "original_size": self.db_path.stat().st_size,
                        "backup_size": backup_path.stat().st_size,
                    },
                )

            return backup_path

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "create_backup",
                        "backup_type": backup_type,
                        "target_path": str(backup_path),
                    },
                )
            raise BackupError(f"Failed to create backup: {e}")

    def auto_backup(self) -> Optional[Path]:
        """
        Create automatic daily backup with cleanup.

        Returns:
            Path to backup file if successful, None if failed
        """
        try:
            # Create daily backup
            backup_path = self.create_backup("daily", "auto")

            # Cleanup old backups
            self._cleanup_old_backups()

            # Check if it's Sunday for weekly backup
            if datetime.now().weekday() == 6:
                self.create_weekly_backup()

            return backup_path

        except Exception as e:
            if self.logger:
                self.logger.log_error(e, {"operation": "auto_backup"})
            return None

    def create_weekly_backup(self) -> Path:
        """
        Create weekly backup (typically called on Sundays).

        Returns:
            Path to the created backup file
        """
        return self.create_backup("weekly", f"week_{datetime.now().strftime('%U')}")

    def _cleanup_old_backups(self) -> None:
        """Remove backups older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        for backup_type in ["daily", "weekly"]:
            backup_dir = self.backup_dir / backup_type
            if not backup_dir.exists():
                continue

            removed_count = 0
            for backup_file in backup_dir.glob("*.db"):
                marker_file = backup_file.with_suffix(".db.marker")

                try:
                    # Use marker file if exists, otherwise fall back to mtime
                    if marker_file.exists():
                        creation_time_str = marker_file.read_text().strip()
                        creation_time = datetime.fromisoformat(creation_time_str)
                    else:
                        # Fallback to file modification time
                        creation_time = datetime.fromtimestamp(
                            backup_file.stat().st_mtime
                        )

                    if creation_time < cutoff_date:
                        backup_file.unlink()
                        if marker_file.exists():
                            marker_file.unlink()
                        removed_count += 1

                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            e, {"operation": "cleanup_backup", "file": str(backup_file)}
                        )

            if removed_count > 0 and self.logger:
                self.logger.log_operation(
                    "backup_cleanup",
                    {
                        "backup_type": backup_type,
                        "removed_count": removed_count,
                        "retention_days": self.retention_days,
                    },
                )

    def restore_backup(self, backup_path: Path) -> None:
        """
        Restore database from backup.

        Args:
            backup_path: Path to backup file to restore

        Raises:
            BackupError: If restore operation fails
        """
        if not backup_path.exists():
            raise BackupError(f"Backup file not found: {backup_path}")

        # Create current backup before restore
        current_backup = self.create_backup("manual", "pre_restore")

        try:
            source = sqlite3.connect(str(backup_path))
            dest = sqlite3.connect(str(self.db_path))

            with dest:
                source.backup(dest)

            source.close()
            dest.close()

            if self.logger:
                self.logger.log_operation(
                    "restore_backup",
                    {
                        "restored_from": str(backup_path),
                        "pre_restore_backup": str(current_backup),
                    },
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    e, {"operation": "restore_backup", "backup_path": str(backup_path)}
                )
            raise BackupError(f"Failed to restore backup: {e}")

    def list_backups(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        List all available backups with metadata.

        Returns:
            Dictionary mapping backup types to lists of backup info
        """
        backups = {"daily": [], "weekly": [], "manual": []}

        for backup_type in backups.keys():
            backup_dir = self.backup_dir / backup_type
            if not backup_dir.exists():
                continue

            for backup_file in sorted(backup_dir.glob("*.db")):
                stat = backup_file.stat()
                backups[backup_type].append(
                    {
                        "name": backup_file.name,
                        "path": str(backup_file),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "age_days": (
                            datetime.now() - datetime.fromtimestamp(stat.st_mtime)
                        ).days,
                    }
                )

        return backups
