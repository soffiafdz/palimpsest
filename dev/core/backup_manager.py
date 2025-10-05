#!/usr/bin/env python3
"""
backup_manager.py
--------------------
Database backup and recovery operations.

Handles both database-only and full data directory backups.
"""
import sqlite3
import tarfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from .logging_manager import PalimpsestLogger
from .exceptions import BackupError


class BackupManager:
    """
    Handles database backup and recovery operations.

    Provides automated backup creation with configurable retention policies
    and safe restore operations with pre-restore backup creation.

    Supports two backup types:
    1. Database-only backups (fast, frequent)
    2. Full data directory backups (complete archive, less frequent)
    """

    def __init__(
        self,
        db_path: Path,
        backup_dir: Path,
        data_dir: Optional[Path] = None,
        retention_days: int = 30,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize backup manager.

        Args:
            db_path: Path to the database file
            backup_dir: Directory for backup storage
            data_dir: Root data directory (for full backups)
            retention_days: Days to retain backups
            logger: Optional logger for backup operations
        """
        self.db_path = Path(db_path)
        self.db_backup_dir = Path(backup_dir) / "database"
        self.data_dir = Path(data_dir) if data_dir else None
        self.full_backup_dir = Path(backup_dir) / "full_data"
        self.retention_days = retention_days
        self.logger = logger

        # Create backup directories
        (self.db_backup_dir / "daily").mkdir(parents=True, exist_ok=True)
        (self.db_backup_dir / "weekly").mkdir(parents=True, exist_ok=True)
        (self.db_backup_dir / "manual").mkdir(parents=True, exist_ok=True)

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

        backup_path = self.db_backup_dir / backup_type / backup_name

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
            raise BackupError(f"Failed to create backup: {e}") from e

    def create_full_backup(self, suffix: Optional[str] = None) -> Path:
        """
        Create compressed archive of entire data directory.

        Excludes:
        - Git files (.git/, .gitignore)
        - Temporary files (tmp/, logs/)
        - Existing backups (backups/)

        Args:
            suffix: Optional suffix for backup filename

        Returns:
            Path to the created archive

        Raises:
            BackupError: If data directory not configured or backup fails
        """
        if not self.data_dir:
            raise BackupError("Data directory not configured for full backups")

        if not self.data_dir.exists():
            raise BackupError(f"Data directory not found: {self.data_dir}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if suffix:
            archive_name = f"palimpsest-data-full_{timestamp}_{suffix}.tar.gz"
        else:
            archive_name = f"palimpsest-data-full_{timestamp}.tar.gz"

        backup_path = self.full_backup_dir / archive_name

        # Patterns to exclude
        exclude_patterns = [
            ".git",
            ".gitignore",
            ".gitmodules",
            "__pycache__",
            "*.pyc",
            "tmp",
            "logs",
            "backups",  # Don't backup backups
            ".DS_Store",
            "Thumbs.db",
        ]

        try:
            if self.logger:
                self.logger.log_operation(
                    "full_backup_start",
                    {"data_dir": str(self.data_dir), "backup_path": str(backup_path)},
                )

            with tarfile.open(backup_path, "w:gz") as tar:
                # Add data directory with filtering
                tar.add(
                    self.data_dir,
                    arcname=self.data_dir.name,
                    filter=lambda tarinfo: self._filter_tarinfo(
                        tarinfo, exclude_patterns
                    ),
                )

            # Create marker file
            marker_path = backup_path.with_suffix(".tar.gz.marker")
            marker_path.write_text(datetime.now().isoformat())

            backup_size = backup_path.stat().st_size
            backup_size_mb = backup_size / (1024 * 1024)

            if self.logger:
                self.logger.log_operation(
                    "full_backup_created",
                    {
                        "backup_path": str(backup_path),
                        "size_bytes": backup_size,
                        "size_mb": f"{backup_size_mb:.2f}",
                    },
                )

            return backup_path

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    e,
                    {
                        "operation": "create_full_backup",
                        "target_path": str(backup_path),
                    },
                )
            raise BackupError(f"Failed to create full backup: {e}") from e

    def _filter_tarinfo(
        self, tarinfo: tarfile.TarInfo, exclude_patterns: List[str]
    ) -> Optional[tarfile.TarInfo]:
        """
        Filter function for tarfile to exclude certain patterns.

        Args:
            tarinfo: TarInfo object being added
            exclude_patterns: List of patterns to exclude

        Returns:
            TarInfo if file should be included, None to exclude
        """
        # Get the path relative to the archive root
        path_parts = Path(tarinfo.name).parts

        # Check each part against exclude patterns
        for part in path_parts:
            for pattern in exclude_patterns:
                if pattern.startswith("*"):
                    # Wildcard pattern
                    if part.endswith(pattern[1:]):
                        return None
                elif part == pattern:
                    return None

        return tarinfo

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
            db_backup_dir = self.db_backup_dir / backup_type
            if not db_backup_dir.exists():
                continue

            removed_count = 0
            for backup_file in db_backup_dir.glob("*.db"):
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
            backup_dir = self.db_backup_dir / backup_type
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

        # Full data backups
        if hasattr(self, "full_backup_dir") and self.full_backup_dir.exists():
            for backup_file in sorted(self.full_backup_dir.glob("*.tar.gz")):
                stat = backup_file.stat()
                backups["full"].append(
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
