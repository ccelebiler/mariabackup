# Use the same base as MariaDB docker image.
FROM ubuntu:focal

RUN set -ex; \
    apt-get update; \
    apt-get install -y software-properties-common cron python3-minimal; \
    rm -rf /etc/cron.* ; \
    rm -rf /var/lib/apt/lists/*

# Install the backup provided by MariaDB.
# https://mariadb.com/kb/en/mariabackup-overview/
# Note: The following commands are derived from the official image for MariaDB.
# https://github.com/MariaDB/mariadb-docker/blob/master/10.7/Dockerfile
ARG MARIADB_VERSION=1:10.7.4+maria~focal
ENV MARIADB_VERSION $MARIADB_VERSION
ARG REPOSITORY="http://archive.mariadb.org/mariadb-10.7.4/repo/ubuntu/ focal main"

RUN set -e; \
	echo "deb ${REPOSITORY}" > /etc/apt/sources.list.d/mariadb.list; \
	{ \
		echo 'Package: *'; \
		echo 'Pin: release o=MariaDB'; \
		echo 'Pin-Priority: 999'; \
	} > /etc/apt/preferences.d/mariadb

RUN set -ex; \
    apt-key adv --recv-keys --keyserver keyserver.ubuntu.com 177F4010FE56CA3336300305F1656F24C74CD1D8; \
    apt-get update; \
    apt-get install -y "mariadb-backup=$MARIADB_VERSION"; \
    rm -rf /var/lib/apt/lists/*

COPY scripts /root
RUN ln -sf /proc/1/fd/1 /root/out.log && ln -sf /proc/1/fd/2 /root/err.log

VOLUME ["/backup", "/var/lib/mysql"]

COPY docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["docker-entrypoint.sh"]
