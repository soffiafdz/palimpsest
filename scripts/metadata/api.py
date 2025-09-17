#!/usr/bin/env python3


# Enhanced API for Neovim integration with Alembic support
def api_handler(action: str, **kwargs) -> Dict[str, Any]:
    """Main API endpoint for Neovim"""
    try:
        db = JournalDB()

        # Migration-related actions
        if action == "init_alembic":
            db.init_alembic()
            return {"success": True, "message": "Alembic initialized"}

        elif action == "create_migration":
            message = kwargs.get("message", "Auto-generated migration")
            db.create_migration(message)
            return {"success": True, "message": f"Migration created: {message}"}

        elif action == "upgrade":
            revision = kwargs.get("revision", "head")
            db.upgrade_database(revision)
            return {"success": True, "message": f"Upgraded to {revision}"}

        elif action == "downgrade":
            revision = kwargs.get("revision")
            if not revision:
                return {"error": "revision required for downgrade"}
            db.downgrade_database(revision)
            return {"success": True, "message": f"Downgraded to {revision}"}

        elif action == "migration_status":
            return {"migration_info": db.get_migration_history()}

        # Original actions
        elif action == "get_metadata":
            file_path = kwargs.get("file_path")
            if not file_path:
                return {"error": "file_path required"}
            return {"metadata": db.get_entry_metadata(file_path)}

        elif action == "update_metadata":
            file_path = kwargs.get("file_path")
            metadata_json = kwargs.get("metadata")
            if not file_path or not metadata_json:
                return {"error": "file_path and metadata required"}

            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON in metadata"}

            success = db.update_markdown_file(file_path, metadata)
            if success:
                db.update_entry_from_file(file_path)

            return {"success": success}

        elif action == "get_autocomplete":
            field = kwargs.get("field")
            if not field:
                return {"error": "field required"}
            return {"values": db.get_all_values(field)}

        elif action == "sync_directory":
            directory = kwargs.get("directory")
            if not directory:
                return {"error": "directory required"}
            updated = db.sync_directory(directory)
            return {"success": True, "updated_files": updated}

        elif action == "repopulate":
            directory = kwargs.get("directory")
            force = kwargs.get("force", "false").lower() == "true"
            if not directory:
                return {"error": "directory required"}

            processed, errors = db.repopulate_from_directory(directory, force)
            return {"success": True, "processed": processed, "errors": errors}

        elif action == "backup":
            suffix = kwargs.get("suffix")
            backup_path = db.backup_database(suffix)
            return {"success": True, "backup_path": backup_path}

        elif action == "stats":
            return {"stats": db.get_database_stats()}

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Command line usage
        action = sys.argv[1]
        kwargs = {}
        for arg in sys.argv[2:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                kwargs[key] = value

        result = api_handler(action, **kwargs)
        print(json.dumps(result, indent=2, default=str))
    else:
        # Interactive usage
        db = JournalDB()
        print("Journal DB with Alembic migrations initialized.")
        print("\nMigration commands:")
        print("- db.init_alembic() - Initialize Alembic (run once)")
        print("- db.create_migration('Description') - Create new migration")
        print("- db.upgrade_database() - Apply pending migrations")
        print("- db.get_migration_history() - Check migration status")

        print("\nRegular operations:")
        print("- db.sync_directory('path/to/journals')")
        print("- db.repopulate_from_directory('path/to/journals', force=False)")
        print("- db.get_entry_metadata('path/to/file.md')")
        print("- db.get_database_stats()")

        print("\nCommand line examples:")
        print("python journal_db.py init_alembic")
        print("python journal_db.py create_migration message='Add mood tracking'")
        print("python journal_db.py upgrade")
        print("python journal_db.py migration_status")
        print("python journal_db.py stats")
        print("python journal_db.py repopulate directory=/path/to/journals force=true")
