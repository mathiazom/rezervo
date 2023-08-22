#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/rezervo.log

# Start logging in background
tail -f /var/log/rezervo.log &

echo "Migrating database to most recent alembic version"
(cd sit_rezervo && alembic upgrade head)

echo "Pulling user sessions"
rezervo sessions pull

echo "Creating cronjob for sessions pulling"
rezervo cron sessionsjob

echo "Updating crontab according to user configurations"
rezervo cron refresh

echo "Starting cron service..."
cron

echo "Starting server..."
rezervo api "$@"