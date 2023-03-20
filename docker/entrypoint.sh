#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/sit-rezervo.log

# Start logging in background
tail -f /var/log/sit-rezervo.log &

echo "Migrating database to most recent alembic version"
(cd sit_rezervo && alembic upgrade head)

echo "Starting server..."
sit-rezervo api "$@"