#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/sit-rezervo.log

# Start logging in background
tail -f /var/log/sit-rezervo.log &

echo "Migrating database to most recent alembic version"
(cd sit_rezervo && alembic upgrade head)

echo "Pulling user sessions"
sit-rezervo sessions pull

echo "Creating cronjob for sessions pulling"
sit-rezervo cron sessionsjob

echo "Updating crontab according to user configurations"
sit-rezervo cron refresh

echo "Starting cron service..."
cron

echo "Starting server..."
sit-rezervo api "$@"