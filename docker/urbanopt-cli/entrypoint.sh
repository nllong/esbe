#!/usr/bin/env bash
# Source URBANopt env vars so they are available for every invocation:
# interactive shells, docker exec, CMD, and direct command calls.
if [ -f /etc/profile.d/urbanopt-cli.sh ]; then
    . /etc/profile.d/urbanopt-cli.sh
fi

# If no arguments given, drop into bash; otherwise execute the command.
if [ $# -eq 0 ]; then
    exec bash
else
    exec "$@"
fi
