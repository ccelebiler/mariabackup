# README #

## What is this repository for? ##

This repository contains a dockerized [Mariabackup](https://mariadb.com/kb/en/mariabackup-overview/) package.

The package is meant to support the [WordPress package](https://github.com/ccelebiler/wordpress), though it should be generic enough for other use cases.

### Features

   * Configurable cron schedules for incremental and full backups
   * Optional compression via [GNU Gzip](https://www.gnu.org/software/gzip/)
   * Optional encryption via [OpenSSL symmetric cipher routines](https://www.openssl.org/docs/manmaster/man1/openssl-enc.html)
   * Configurable full backup retention (by quantity and/or by age)
   * Configurable log level

### Backup folder structure

In the following example, compression and encryption are enabled:
```
/backup/
├── <full_1>/
│   ├── backup.xb.gz.enc
│   ├── xtrabackup_checkpoints
│   ├── xtrabackup_info
│   ├── <incr_1>/
│   │   └── backup.xb.gz.enc
│   .
│   └── <incr_n>/
│       └── backup.xb.gz.enc
.
└── <full_n>/
```

The backup folder names have the following format:
```
<year>-<month>-<day>_<hour>-<minute>-<second>
```

## Get started

### Configure environment variables

Create a new `.env` file in the root folder with the following content:
```
MYSQL_USER=[e.g., backup]
MYSQL_PASSWORD=
BACKUP_PASSWORD=
```

<b>Note:</b> The last variable is required only for encryption.

Restrict access to the file:
```
chmod 600 .env
```

### Create backup user

Connect to the database and execute the following commands:
```
CREATE USER `<MYSQL_USER>`@`%` IDENTIFIED BY '<MYSQL_PASSWORD>';
GRANT RELOAD, PROCESS ON *.* TO `<MYSQL_USER>`@`%`;
```

### Customize configuration

The following environment variables are supported:
   * `MYSQL_HOST`
   * `MYSQL_PORT`
   * `MYSQL_USER`
   * `MYSQL_PASSWORD`
   * `CRON_SCHED_FULL` - supports [Linux crontab](https://man7.org/linux/man-pages/man5/crontab.5.html) syntax
   * `CRON_SCHED_INCR`
   * `BACKUP_IMMEDIATE` - whether to take immediately a full backup
   * `BACKUP_COMPRESS` - whether to enable backup compression
   * `BACKUP_ENCRYPT` - whether to enable backup encryption (ignored if compression is disabled)
   * `BACKUP_THREADS` - number of threads to use for parallel data file transfer
   * `BACKUP_KEEP_N` - maximum number of full backups
   * `BACKUP_KEEP_DAYS` - maximum age of full backups
   * `BACKUP_LOG_LEVEL` - supports [Python logging levels](https://docs.python.org/3/library/logging.html#levels)

### Run package

Run the following command from the root folder:
```
docker-compose up -d
```

## Restore

To restore an existing backup, run the following commands:
```
docker stop mysql
docker exec -it mariabackup /bin/bash
python3 /root/mariabackup.py restore --name=<backup>
docker start mysql
```

<b>Note:</b> The `--name` argument is optional. If not specified, the most recent backup is used.
