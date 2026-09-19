#!/bin/sh
# Apply migrations, then hand off to the command.
#
# The schema is owned by Alembic, never by create_all(). Running this on every start
# is safe: `upgrade head` is a no-op when the database is already current, and it means
# a self-hoster pulling a new image never has to run a migration by hand.
set -eu

echo "Applying database migrations..."
alembic upgrade head

echo "Starting: $*"
exec "$@"
