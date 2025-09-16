#!/usr/bin/env bash
# update_db.sh: Automates Alembic migrations for Palimpsest metadata DB

set -e

# Commit message for the migration (Argument)
MSG="$1"
if [ -z "$MSG" ]; then
  echo "Usage: ./update_db.sh 'Migration message'"
  exit 1
fi

# 1) Autogenerate migration
alembic revision --autogenerate -m "$MSG"

# 2) Apply migration to the DB
alembic upgrade head

echo "Migration '$MSG' applied successfully."
