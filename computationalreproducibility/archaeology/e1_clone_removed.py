"""Load notebook and cells"""
import argparse
import os
import subprocess

import config
import consts

from db import RequirementFile, Repository, connect
from utils import vprint, StatusLogger, mount_basedir, check_exit, savepid
from load_repository import load_repository


def clone_repository(session, repository, skip_if_error=consts.R_FAILED_TO_CLONE, dry_run=False):
    """Process repository"""
    try:
        if repository.processed & consts.R_FAILED_TO_CLONE:
            session.add(repository)
            repository.processed -= consts.R_FAILED_TO_CLONE

        if not repository.path.exists() and not repository.zip_path.exists() and not dry_run:
            load_repository(
                session, repository.domain, repository.repository,
                commit=repository.commit, clone_existing=True
            )

        if repository.path.exists() or repository.zip_path.exists():
            if repository.processed & consts.R_UNAVAILABLE_FILES:
                repository.processed -= consts.R_UNAVAILABLE_FILES
        session.add(repository)
        session.commit()
        return "done"
    except (EnvironmentError, subprocess.CalledProcessError) as e:
        repository.processed |= consts.R_FAILED_TO_CLONE
        session.add(repository)
        session.commit()
        return "failed {}".format(e)

    return "done"


def apply(
    session, status, skip_if_error, dry_run, list_repo,
    count, interval, reverse, check
):
    """Clone removed files"""
    filters = [
        Repository.processed.op("&")(consts.R_UNAVAILABLE_FILES) != 0, # files unavailable
        Repository.processed.op("&")(skip_if_error) == 0,
    ]
    if interval:
        filters += [
            Repository.id >= interval[0],
            Repository.id <= interval[1],
        ]
    query = session.query(Repository).filter(*filters)
    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            Repository.id.desc()
        )
    else:
        query = query.order_by(
            Repository.id.asc()
        )

    for repository in query:
        if check_exit(check):
            vprint(0, "Found .exit file. Exiting")
            return
        status.report()
        status.count += 1
        if list_repo:
            vprint(0, "Repository {}".format(repository))
            vprint(1, "tar -xjf {} -C .".format(repository.zip_path))
            continue
        vprint(0, "Cloning repository {}".format(repository))
        with mount_basedir():
            result = clone_repository(
                session, repository, skip_if_error, dry_run
            )
            vprint(1, result)

        session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Clone deleted repositories")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="id interval")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count results")
    parser.add_argument("-d", "--dry-run", action='store_true',
                        help="discover repositories but do not clone")
    parser.add_argument("-l", "--list", action='store_true',
                        help="list repositories but do not clone nor discover")
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='iterate in reverse order')
    parser.add_argument('--check', type=str, nargs='*',
                        default={'all', script_name, script_name + '.py'},
                        help='check name in .exit')
    args = parser.parse_args()
    config.VERBOSE = args.verbose
    status = None
    if not args.count:
        status = StatusLogger(script_name)
        status.report()

    with connect() as session, savepid():
         apply(
            session,
            status,
            0 if args.retry_errors else consts.R_FAILED_TO_CLONE,
            args.dry_run,
            args.list,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )


if __name__ == "__main__":
    main()
