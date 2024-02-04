#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/rezervo.log

# Start logging in background
tail -f /var/log/rezervo.log &

echo "Migrating database to most recent alembic version"
(cd rezervo && alembic upgrade head)

# Start pulling sessions data in the background
rezervo sessions pull &

rezervo cron add_pull_sessions_job

rezervo cron add_slack_receipts_purging_job

rezervo cron add_refresh_cron_job

rezervo cron refresh

echo "⚙️ Starting cron service..."
cron

echo "⚙️ Starting server..."
rezervo api "$@"