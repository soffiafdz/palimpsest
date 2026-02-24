#!/usr/bin/env python3
"""
temporal_files.py
--------------------
Temporal file management for safe operations across all pipelines.

Provides secure temporary file creation with automatic tracking and cleanup.
Used by database operations, conversion pipelines, and any process requiring
temporary file management.

Features:
    - Context manager pattern for automatic cleanup
    - Secure temporary file creation (mkstemp for sensitive data)
    - Tracking of all created files and directories
    - Cleanup statistics for monitoring
    - Configurable base directory

Classes:
    TemporalFileManager: Main manager with context manager support

Usage:
    from dev.core.temporal_files import TemporalFileManager

    # Context manager (recommended) - automatic cleanup
    with TemporalFileManager() as temp_manager:
        temp_file = temp_manager.create_temp_file(suffix=".txt")
        temp_dir = temp_manager.create_temp_dir()
        # ... use temp_file and temp_dir ...
    # Automatic cleanup on context exit

    # Secure file creation for sensitive data
    with TemporalFileManager() as temp_manager:
        fd, secure_path = temp_manager.create_secure_temp_file()
        os.write(fd, b"sensitive data")
        os.close(fd)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, IO

# --- Local imports ---
from .exceptions import TemporalFileError


class TemporalFileManager:
    """
    Manages temporal files with automatic cleanup.

    Provides secure temporary file creation with automatic tracking and cleanup.
    Supports both regular temporary files and secure file descriptor creation.

    Usage:
        with TemporalFileManager() as temp_manager:
            temp_file = temp_manager.create_temp_file(suffix=".txt")
            # ... use temp_file ...
        # Automatic cleanup on context exit
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """
        Initialize temporal file manager.

        Args:
            base_dir: Base directory for temporary files. Uses system temp if None.
        """
        self.base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self.active_files: List[Path] = []
        self.active_dirs: List[Path] = []
        self._temp_file_handles: List[IO[Any]] = []

    def create_temp_file(
        self, suffix: str = "", prefix: str = "palimpsest_", delete: bool = False
    ) -> Path:
        """
        Create a temporary file and track it for cleanup.

        Args:
            suffix: File suffix/extension
            prefix: File prefix
            delete: If True, file is automatically deleted when closed

        Returns:
            Path to the temporary file

        Raises:
            TemporalFileError: If file creation fails
        """
        try:
            temp_file_obj = tempfile.NamedTemporaryFile(
                suffix=suffix, prefix=prefix, dir=self.base_dir, delete=delete
            )

            temp_path = Path(temp_file_obj.name)

            if delete:
                # Keep reference to prevent premature deletion
                self._temp_file_handles.append(temp_file_obj)
            else:
                # Close the file handle but keep the file
                temp_file_obj.close()
                self.active_files.append(temp_path)

            return temp_path

        except Exception as e:
            raise TemporalFileError(f"Failed to create temporary file: {e}")

    def create_temp_dir(self, prefix: str = "palimpsest_") -> Path:
        """
        Create a temporary directory and track it for cleanup.

        Args:
            prefix: Directory prefix

        Returns:
            Path to the temporary directory

        Raises:
            TemporalFileError: If directory creation fails
        """
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=self.base_dir))
            self.active_dirs.append(temp_dir)
            return temp_dir
        except Exception as e:
            raise TemporalFileError(f"Failed to create temporary directory: {e}") from e

    def create_secure_temp_file(
        self, suffix: str = "", prefix: str = "palimpsest_"
    ) -> Tuple[int, Path]:
        """
        Create a secure temporary file using mkstemp.

        Args:
            suffix: File suffix/extension
            prefix: File prefix

        Returns:
            Tuple of (file_descriptor, file_path)
            Note: Caller is responsible for closing the file descriptor

        Raises:
            TemporalFileError: If file creation fails
        """
        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=suffix, prefix=prefix, dir=self.base_dir
            )
            path_obj = Path(temp_path)
            self.active_files.append(path_obj)
            return fd, path_obj
        except Exception as e:
            raise TemporalFileError(
                f"Failed to create secure temporary file: {e}"
            ) from e

    def cleanup(self) -> Dict[str, int]:
        """
        Clean up all tracked temporary files and directories.

        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {"files_removed": 0, "dirs_removed": 0, "errors": 0}

        # Clean up temporary file handles
        for temp_handle in self._temp_file_handles[:]:
            try:
                temp_handle.close()  # This will auto-delete if delete=True
                self._temp_file_handles.remove(temp_handle)
            except Exception:
                cleanup_stats["errors"] += 1

        # Clean up tracked files
        for temp_file in self.active_files[:]:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    cleanup_stats["files_removed"] += 1
                self.active_files.remove(temp_file)
            except Exception:
                cleanup_stats["errors"] += 1

        # Clean up directories
        for temp_dir in self.active_dirs[:]:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    cleanup_stats["dirs_removed"] += 1
                self.active_dirs.remove(temp_dir)
            except Exception:
                cleanup_stats["errors"] += 1

        return cleanup_stats

    def __enter__(self) -> "TemporalFileManager":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[Any],
    ) -> None:
        """Context manager exit with automatic cleanup."""
        del exc_type, exc_val, exc_tb
        self.cleanup()
