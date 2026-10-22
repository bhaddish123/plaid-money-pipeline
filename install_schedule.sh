#!/bin/bash
# Installs a macOS LaunchAgent that runs sync.py every Sunday at 7:15 PM and on the 1st of each month at 7:15 AM.
# If the Mac is asleep then, it runs when the Mac wakes. Log: ~/Library/Logs/plaid-sync.log
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"
LABEL="com.ket.plaid-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/plaid-sync.log"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/sync.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartCalendarInterval</key><array>
    <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>19</integer><key>Minute</key><integer>15</integer></dict>
    <dict><key>Day</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>15</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed. Python: $PY"
echo "Running a test sync now..."
launchctl kickstart -k "gui/$(id -u)/$LABEL"
sleep 20
echo "--- last lines of $LOG ---"
tail -3 "$LOG" || echo "(no log yet - wait a bit and run: tail -3 $LOG)"
