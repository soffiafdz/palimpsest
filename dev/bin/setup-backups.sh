#!/usr/bin/env bash
# Setup automated backups for Palimpsest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Detect platform
case "$(uname -s)" in
  Darwin)
    PLATFORM="macos"
    ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      PLATFORM="wsl"
    elif command -v sv >/dev/null 2>&1; then
      PLATFORM="runit"
    else
      PLATFORM="linux"
    fi
    ;;
  *)
    PLATFORM="unknown"
    ;;
esac

echo "📅 Setting up automated backups for Palimpsest"
echo "Platform detected: $PLATFORM"
echo ""

# Create backup script
cat >"$SCRIPT_DIR/run-backup.sh" <<'EOF'
#!/usr/bin/env bash
# Automated backup runner for Palimpsest

set -euo pipefail

# Change to project directory
cd "$(dirname "$0")/.."

# Log file
LOG_DIR="logs/backups"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/backup-$(date +%Y%m%d_%H%M%S).log"

# Determine backup type based on day
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)

{
    echo "=========================================="
    echo "Palimpsest Automated Backup"
    echo "Date: $(date)"
    echo "=========================================="
    echo ""

    # Monthly backup on the 1st
    if [ "$DAY_OF_MONTH" = "01" ]; then
        echo "🗓️  Monthly backup (full data)"
        if make backup-full; then
            echo "✅ Monthly full backup complete"
        else
            echo "❌ Monthly full backup failed"
            exit 1
        fi
    
    # Weekly backup on Sundays
    elif [ "$DAY_OF_WEEK" = "7" ]; then
        echo "📅 Weekly backup (database + full data)"
        if make backup; then
            echo "✅ Database backup complete"
        else
            echo "❌ Database backup failed"
            exit 1
        fi
        
        if make backup-full; then
            echo "✅ Full data backup complete"
        else
            echo "❌ Full data backup failed"
            exit 1
        fi
    
    # Daily database backup
    else
        echo "📆 Daily backup (database only)"
        if make backup; then
            echo "✅ Daily database backup complete"
        else
            echo "❌ Daily database backup failed"
            exit 1
        fi
    fi

    echo ""
    echo "=========================================="
    echo "Backup completed: $(date)"
    echo "=========================================="

} 2>&1 | tee "$LOG_FILE"

# Keep only last 30 days of logs
find "$LOG_DIR" -name "backup-*.log" -mtime +30 -delete

# Notify success (optional - uncomment if you have notify-send)
# notify-send "Palimpsest Backup" "Backup completed successfully"
EOF

chmod +x "$SCRIPT_DIR/run-backup.sh"

# Create crontab entry
CRON_CMD="0 2 * * * cd $PROJECT_ROOT && $SCRIPT_DIR/run-backup.sh"

echo "Backup script created at: $SCRIPT_DIR/run-backup.sh"
echo ""
echo "Suggested crontab entry (runs daily at 2 AM):"
echo "─────────────────────────────────────────────────"
echo "$CRON_CMD"
echo "─────────────────────────────────────────────────"
echo ""

# Platform-specific instructions
case "$PLATFORM" in
macos)
  echo "✅ macOS Setup:"
  echo ""
  echo "1. Add to crontab:"
  echo "   crontab -e"
  echo ""
  echo "   Then paste:"
  echo "   $CRON_CMD"
  echo ""
  echo "2. Or use launchd (recommended for macOS):"
  echo "   Create ~/Library/LaunchAgents/com.palimpsest.backup.plist"
  ;;

wsl)
  echo "⚠️  WSL2 Setup Required:"
  echo ""
  echo "1. WSL2 doesn't run cron by default. Add to /etc/wsl.conf:"
  echo ""
  echo "   [boot]"
  echo "   command=\"service cron start\""
  echo ""
  echo "2. Or start cron manually:"
  echo "   sudo service cron start"
  echo ""
  echo "3. Add to crontab:"
  echo "   crontab -e"
  echo ""
  echo "   Then paste:"
  echo "   $CRON_CMD"
  echo ""
  echo "4. Alternative: Use Windows Task Scheduler instead (see docs)"
  ;;

runit)
  echo "✅ Runit/Artix Setup:"
  echo ""
  echo "1. Make sure cronie is installed:"
  echo "   sudo pacman -S cronie"
  echo ""
  echo "2. Enable cron service (runit):"
  echo "   sudo ln -s /etc/runit/sv/crond /run/runit/service/"
  echo ""
  echo "3. Add to crontab:"
  echo "   crontab -e"
  echo ""
  echo "   Then paste:"
  echo "   $CRON_CMD"
  ;;

*)
  echo "✅ Linux Setup:"
  echo ""
  echo "1. Add to crontab:"
  echo "   crontab -e"
  echo ""
  echo "   Then paste:"
  echo "   $CRON_CMD"
  ;;
esac

echo ""
echo "📋 Backup Schedule:"
echo "  Daily (2 AM):   Database backup"
echo "  Weekly (Sun):   Database + Full data backup"
echo "  Monthly (1st):  Full data backup"
echo ""
echo "Logs saved to: logs/backups/"
