#!/usr/bin/env bash
# Wipe the Task Panda SQLite database and restart the backend.
# All tasks/sessions/captures/users are deleted; the next page load
# shows the first-run admin signup form.
#
# Usage:
#   bin/reset-db.sh                  # reset the local stack (this machine)
#   bin/reset-db.sh --remote HOST    # reset over ssh; HOST must have passwordless sudo
#                                    # and the repo cloned at ~/task-panda
#   bin/reset-db.sh --yes            # skip the confirmation prompt
#
# The sequence is stop → rm → up (not `up` while a container is mid-Stop),
# which avoids a 0-byte focus.db race that leaves init_db unable to create
# tables.

set -euo pipefail

cd "$(dirname "$0")/.."

REMOTE=""
ASSUME_YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote) REMOTE="${2:?--remote needs a host}"; shift 2 ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

label=${REMOTE:-local}
echo "About to wipe Task Panda database on: ${label}"
if [[ $ASSUME_YES -eq 0 ]]; then
  read -r -p "Type 'yes' to continue: " confirm
  [[ "$confirm" == "yes" ]] || { echo "aborted"; exit 1; }
fi

# The container writes /data/focus.db as root on Linux hosts, so removal
# needs sudo there. On Docker Desktop (Mac/Windows) the bind-mounted file
# is owned by the host user and plain `rm` works.
if [[ -n "$REMOTE" ]]; then
  ssh "$REMOTE" '
    set -e
    cd ~/task-panda
    docker compose stop backend
    sudo rm -f data/focus.db data/focus.db-shm data/focus.db-wal
    docker compose up -d backend
  '
else
  docker compose stop backend
  rm -f data/focus.db data/focus.db-shm data/focus.db-wal
  docker compose up -d backend
fi

# Give the backend a moment to start, then verify init_db actually wrote
# tables (this is the 0-byte race we want to catch loudly, not silently).
sleep 4
verify='import sqlite3
con = sqlite3.connect("/data/focus.db")
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type=\"table\"").fetchall()]
expected = {"users", "tasks", "sessions", "captures"}
missing = expected - set(tables)
if missing:
    raise SystemExit(f"FAIL: missing tables {sorted(missing)} (focus.db may be 0 bytes)")
print("ok: tables =", sorted(tables))'

if [[ -n "$REMOTE" ]]; then
  ssh "$REMOTE" "cd ~/task-panda && docker compose exec -T backend python -c '$verify'"
else
  docker compose exec -T backend python -c "$verify"
fi

echo "Database reset complete on ${label}. Open the app — login page will render the first-run signup form."
