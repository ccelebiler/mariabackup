#!/bin/bash
set -eo pipefail
shopt -s nullglob

# Check to see if this file is being run or sourced from another script.
# https://unix.stackexchange.com/a/215279
_is_sourced() {
	[ "${#FUNCNAME[@]}" -ge 2 ] &&
		[ "${FUNCNAME[0]}" = '_is_sourced' ] &&
		[ "${FUNCNAME[1]}" = 'source' ]
}

_main() {
	CRON_USER="root"
	BACKUP_CMD="/usr/bin/python3 /root/mariabackup.py backup"
	BACKUP_CMD_FULL="$BACKUP_CMD --full"
	BACKUP_CMD_INCR="$BACKUP_CMD --incr"
	CRON_DIR="/etc/cron.d"
	CRON_FILE="$CRON_DIR/mariabackup"
	echo "Cron schedule (full backup): $CRON_SCHED_FULL"
	echo "Cron schedule (incr. backup): $CRON_SCHED_INCR"

	mkdir -p $CRON_DIR
	echo "$CRON_SCHED_FULL $CRON_USER $BACKUP_CMD_FULL" > $CRON_FILE
	[ ! -z $CRON_SCHED_INCR ] && echo "$CRON_SCHED_INCR $CRON_USER $BACKUP_CMD_INCR" >> $CRON_FILE
	chmod 0644 $CRON_FILE

	# Save the relevant environment variables, as cron jobs do not have access to the ones set by Docker.
	# https://stackoverflow.com/questions/27771781/how-can-i-access-docker-set-environment-variables-from-a-cron-job
	printenv | grep -E "(MYSQL|BACKUP)" | grep -v ROOT >> etc/environment

	# If requested, execute immediately a full backup.
	if [ $BACKUP_IMMEDIATE = "true" ]; then
		bash -c "$BACKUP_CMD_FULL" >/dev/null
	fi

	# Keep cron in the foreground, so that the Docker image continues running.
	cron -f
}

# If we are sourced from elsewhere, don't perform any further actions.
if ! _is_sourced; then
	_main
fi
