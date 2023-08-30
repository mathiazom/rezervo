#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/rezervo.log

# Start logging in background
tail -f /var/log/rezervo.log &

echo "Migrating database to most recent alembic version"
(cd rezervo && alembic upgrade head)

rezervo sessions pull

rezervo cron sessionsjob

rezervo cron refresh

echo "Starting cron service..."
cron

echo "Starting server..."
rezervo api "$@"