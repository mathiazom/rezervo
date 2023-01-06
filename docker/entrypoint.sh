#!/bin/bash

# Create cron log file to be able to run tail
touch /var/log/sit-rezervo.log

# Start logging in background
tail -f /var/log/sit-rezervo.log &

echo "Detecting config files..."
shopt -s extglob  # required for filename pattern matching below
CONFIG_FLAGS=$(for c in ./?(*.)config.yaml ; do echo -n "-c $c "; done)

echo "Generating crontab..."
sit-rezervo cron $CONFIG_FLAGS -o /etc/cron.d/sit-rezervo-cron

echo "Installing crontab..."
chmod 0644 /etc/cron.d/sit-rezervo-cron
crontab -r
crontab /etc/cron.d/sit-rezervo-cron
cat /etc/cron.d/sit-rezervo-cron

echo "Starting cron service..."
cron

echo "Starting server..."
sit-rezervo api $CONFIG_FLAGS "$@"