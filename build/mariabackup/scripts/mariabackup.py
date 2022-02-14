import argparse
import logging
import logging.config
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

from config import LoggingConfig


class MariaDbBackup():
    """
    Wrapper for the MariaDB backup tool
    """

    def __init__(self):
        logging.config.dictConfig(LoggingConfig.dict)
        self.__backup_root_dir = "/backup"
        self.__backup_name_format = "%Y-%m-%d_%H-%M-%S"
        self.__backup_name_pattern = "^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        self.__target_file = "backup.xb.gz"
        self.__mysql_root_datadir = "/var/lib/mysql"
        self.__mysql_conn_opt = [
            f"""--host={os.getenv("MYSQL_HOST", "localhost")}""",
            f"""--port={os.getenv("MYSQL_PORT", 3306)}""",
            f"""--user={os.getenv("MYSQL_USER", "root")}""",
            f"""--password={os.getenv("MYSQL_PASSWORD")}""",
        ]
        self.__enc_file_ext = ".enc"
        self.__enc_cmd = [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-md", "sha512",
            "-pbkdf2",
            "-iter", "100000",
            "-pass", f"""pass:{os.getenv("BACKUP_PASSWORD")}""",
        ]
        self.__compress = os.getenv("BACKUP_COMPRESS") == "true"
        self.__encrypt = os.getenv("BACKUP_ENCRYPT") == "true"

    @property
    def logger(self):
        """
        Returns the logger.
        """
        return logging.getLogger()

    def __run_proc(self, *args, **kwargs):
        proc = subprocess.run(*args, capture_output=True, **kwargs)
        if proc.returncode:
            self.logger.error(proc.stderr.decode("utf-8"))
            return False, proc
        return True, proc

    def __backup_dirs(self, root_dir):
        prog = re.compile(self.__backup_name_pattern)
        return (f for f in os.scandir(root_dir) if f.is_dir() and prog.match(f.name))

    def check_daemon(self):
        """
        Checks if the daemon is listening.

        :return: Success status
        """
        self.logger.debug("Checking daemon...")

        # Try to connect to the daemon.
        # If there is no timeout error, the daemon is listening.
        cmd = [
            "mariadb",
            "--execute=quit"
        ]
        cmd += self.__mysql_conn_opt
        try:
            self.__run_proc(cmd, timeout=0.1)
        except subprocess.TimeoutExpired:
            return False
        return True

    def prepare(self, name=None):
        """
        Prepares an existing backup to restore. If no backup is specified, the most recent one is used.

        :param name: Backup name
        :return: Success status
        """
        self.logger.debug("Preparing backup...")

        # Find the backup directories.
        if name:
            dirs = list(root for root, dirs, _ in os.walk(self.__backup_root_dir) if name in dirs)
            if not len(dirs):
                self.logger.error(f"Backup not found.")
                return False, None
            full = dirs[0] == self.__backup_root_dir
            backup_dir = os.path.join(dirs[0], name)
            full_backup_dir = backup_dir if full else dirs[0]
            incr_backup_dir = None if full else backup_dir
        else:
            full_backup_dirs = sorted(f.path for f in self.__backup_dirs(self.__backup_root_dir))
            if not len(full_backup_dirs):
                self.logger.error(f"No backup available.")
                return False, None
            incr_backup_dirs = sorted(f.path for f in self.__backup_dirs(full_backup_dirs[-1]))
            full = len(incr_backup_dirs) == 0
            full_backup_dir = full_backup_dirs[-1]
            incr_backup_dir = None if full else incr_backup_dirs[-1]

        if self.__compress:
            i = 0
            for dir in list(filter(None, [full_backup_dir, incr_backup_dir])):
                # Read the backup file.
                with open(os.path.join(dir, self.__target_file + (self.__enc_file_ext if self.__encrypt else "")), "rb") as f:
                    data = f.read()
                # If applicable, decrypt the backup data.
                if self.__encrypt:
                    success, proc = self.__run_proc(self.__enc_cmd + ["-d"], input=data)
                    if not success:
                        return False, None
                    data = proc.stdout
                # Decompress the backup data.
                success, proc = self.__run_proc(["gzip", "-d"], input=data)
                if not success:
                    return False, None
                # Save the backup data to disk.
                dest_dir = f"/root/temp{i}"
                shutil.rmtree(dest_dir, ignore_errors=True)
                os.mkdir(dest_dir)
                success, proc = self.__run_proc(["mbstream", "-x", "-C", dest_dir], input=proc.stdout)
                if not success:
                    return False, None
                if i == 0:
                    full_backup_dir = dest_dir
                else:
                    incr_backup_dir = dest_dir
                i += 1

        # Prepare the full backup.
        cmd = [
            "mariabackup",
            "--prepare",
            f"--target-dir={full_backup_dir}"
        ]
        self.logger.debug(f"- Target directory: {full_backup_dir}")
        if not self.__run_proc(cmd):
            return False, None

        # If applicable, prepare the incremental backup.
        if incr_backup_dir:
            cmd.append(f"--incremental-dir={incr_backup_dir}")
            self.logger.debug(f"- Incremental directory: {incr_backup_dir}")
            if not self.__run_proc(cmd):
                return False, None

        return True, full_backup_dir

    def restore(self, target_dir):
        """
        Restores the prepared backup.

        :target_dir: Directory containing the prepared backup
        :return: Success status
        """
        self.logger.debug("Starting restore...")

        # Empty the root data directory.
        for entry in os.scandir(self.__mysql_root_datadir):
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)

        # Restore the backup.
        cmd = [
            "mariabackup",
            "--copy-back",
            f"--target-dir={target_dir}",
            f"--datadir={self.__mysql_root_datadir}"
        ]
        success, _ = self.__run_proc(cmd)
        if not success:
            return False

        # Empty the temporary directories.
        for i in range(2):
            dest_dir = f"/root/temp{i}"
            shutil.rmtree(dest_dir, ignore_errors=True)

        return True

    def backup(self, full=True):
        """
        Backs up databases.

        :param full: Whether the backup should be full (or incremental)
        :return: Success status
        """
        self.logger.debug("Starting backup...")
        cmd = [
            "mariabackup",
            "--backup",
            f"""--parallel={os.getenv("BACKUP_THREADS", 1)}"""
        ]
        cmd += self.__mysql_conn_opt

        # Append the directory options.
        self.logger.debug(f"""- Mode: {"FULL" if full else "INCR"}""")
        if not full:
            # Find the latest full backup.
            full_backup_dirs = sorted(f.path for f in self.__backup_dirs(self.__backup_root_dir))
            if not len(full_backup_dirs):
                self.logger.error(f"No full backup available.")
                return False
            cmd.append(f"--incremental-basedir={full_backup_dirs[-1]}")
        target_dir = os.path.join(self.__backup_root_dir if full else full_backup_dirs[-1],
                                  datetime.now().strftime(self.__backup_name_format))
        cmd.append(f"""{"--extra-lsndir" if full and self.__compress else "--target-dir"}={target_dir}""")
        self.logger.debug(f"- Target directory: {target_dir}")

        # If compression is required, append the relevant option and determine the file name.
        # Note: The internal compression feature of the tool is deprecated. It is recommended to use a 3rd party compression library on the ouput stream.
        # https://mariadb.com/kb/en/mariabackup-options/#-compress
        # https://mariadb.com/kb/en/using-encryption-and-compression-tools-with-mariabackup/
        self.logger.debug(f"""- Compression: {"ON" if self.__compress else "OFF"}""")
        if self.__compress:
            cmd.append("--stream=xbstream")
            self.logger.debug(f"""- Encryption: {"ON" if self.__encrypt else "OFF"}""")
            self.logger.debug(
                f"""- Target file: {self.__target_file + (self.__enc_file_ext if self.__encrypt else "")}""")

        # Take the backup.
        success, proc = self.__run_proc(cmd)
        if not success:
            return False
        if not self.__compress:
            return True

        # Compress and, if applicable, encrypt the backup data.
        success, proc = self.__run_proc(["gzip"], input=proc.stdout)
        if not success:
            return False
        if self.__encrypt:
            # Encrypt the backup data and save it to the file.
            success, proc = self.__run_proc(self.__enc_cmd, input=proc.stdout)
            if not success:
                return False

        # Save the backup data to file.
        if not full:
            os.mkdir(target_dir)
        with open(os.path.join(target_dir, self.__target_file + (self.__enc_file_ext if self.__encrypt else "")), "wb") as f:
            f.write(proc.stdout)

        return True

    def purge(self):
        """
        Purges backups that don't fall under the retention policy.

        :return: Number of purged backups
        """
        i = 0

        # Purge old backups.
        days = int(os.getenv("BACKUP_KEEP_DAYS", 0))
        self.logger.debug(f"- Retention policy (days): {days}")
        if days:
            backup_dirs = (f.path for f in self.__backup_dirs(self.__backup_root_dir)
                           if (datetime.now() - datetime.strptime(f.name, self.__backup_name_format)).days >= days)
            for path in backup_dirs:
                shutil.rmtree(path, ignore_errors=True)
            i += len(backup_dirs)

        # Purge extra backups.
        n = int(os.getenv("BACKUP_KEEP_N", 0))
        self.logger.debug(f"- Retention policy (n): {n}")
        if n:
            backup_dirs = sorted((f.path for f in self.__backup_dirs(self.__backup_root_dir)), reverse=True)[n:]
            for path in backup_dirs:
                shutil.rmtree(path, ignore_errors=True)
            i += len(backup_dirs)

        return i


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="PROG")
    subparsers = parser.add_subparsers(dest="cmd", help="sub-commands")
    parser_b = subparsers.add_parser("backup", help="backup MariaDB databases")
    group = parser_b.add_mutually_exclusive_group(required=True)
    group.add_argument("--full", action="store_true", help="full backup")
    group.add_argument("--incr", action="store_true", help="incremental backup (on top of most recent full backup)")
    parser_r = subparsers.add_parser("restore", help="restore existing MariaDB backup")
    parser_r.add_argument("--name", metavar="BACKUP",
                          help="backup to restore (if not specified, most recent backup is used)")
    parser_c = subparsers.add_parser("check-daemon", help="check MariaDB daemon")
    args = parser.parse_args()

    try:
        o = MariaDbBackup()
        if args.cmd == "backup":
            if not o.check_daemon():
                o.logger.warning("Daemon is NOT listening, skipping backup.")
                sys.exit()
            if o.backup(args.full):
                o.logger.info(f"""{"Full" if args.full else "Incremental"} backup completed.""")
                o.logger.info(f"Purged {o.purge()} full backups.")
        elif args.cmd == "restore":
            if o.check_daemon():
                o.logger.warning("Daemon is listening, please stop it before attempting a restore.")
                sys.exit()
            success, target_dir = o.prepare(args.name)
            if success:
                o.logger.info("Backup prepared.")
                if o.restore(target_dir):
                    o.logger.info("Restore complete, please restart the daemon.")
        elif args.cmd == "check-daemon":
            o.logger.info(f"""Daemon is {"NOT " if not o.check_daemon() else ""}listening.""")
    except Exception as exc:
        o.logger.exception(exc)
