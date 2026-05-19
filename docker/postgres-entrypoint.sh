#!/bin/sh
set -e
# Remove stale or corrupt postmaster.pid left after unclean container stop (kill, Docker Desktop sleep, etc.).
# At container start no postgres process is using this data directory yet.
# See: https://www.postgresql.org/docs/current/server-start.html (lock file)
rm -f /var/lib/postgresql/data/postmaster.pid

exec /usr/local/bin/docker-entrypoint.sh "$@"
