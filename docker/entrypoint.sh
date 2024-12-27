#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/rezervo.log

# Start logging in background
tail -f /var/log/rezervo.log &

figlet rezervo

echo "Migrating database to most recent alembic version"
alembic -c 'rezervo/alembic.ini' upgrade head

# Start pulling sessions data in the background
rezervo sessions pull &

rezervo cron init

rezervo cron refresh

echo "⚙️ Starting cron service..."
cron

echo "⚙️ Starting server..."
rezervo api "$@"