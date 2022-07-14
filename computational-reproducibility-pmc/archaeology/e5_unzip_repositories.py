"""Load notebook and cells"""
import argparse
import os

import nbformat as nbf
from IPython.core.interactiveshell import InteractiveShell

import config
import consts

import shutil
import subprocess
from db import Cell, Notebook, Repository, connect
from utils import timeout, TimeoutError, vprint, StatusLogger, mount_basedir
from utils import check_exit, savepid


def unzip_repository(session, repository):
    """Process repository"""
    if not repository.path.exists():
        if not repository.zip_path.exists():
            repository.processed |= consts.R_UNAVAILABLE_FILES
            session.add(repository)
            return "Failed to load notebooks due <repository not found>"
        uncompressed = subprocess.call([
            "tar", "-xjf", str(repository.zip_path),
            "-C", str(repository.zip_path.parent)
        ])
        if uncompressed != 0:
            return "Extraction failed with code {}".format(uncompressed)
    if repository.processed & consts.R_COMPRESS_OK:
        repository.processed -= consts.R_COMPRESS_OK
        session.add(repository)

    return "done"


def apply(
    session, status, selected_repositories, processed, no,
    count, interval, reverse, check
):
    while selected_repositories:
        filters = [
            Repository.processed.op("&")(processed) == processed, # no extraction
            Repository.processed.op("&")(no) == 0, # no failure
        ]
        if selected_repositories is not True:
            filters += [
                Repository.id.in_(selected_repositories[:30])
            ]
            selected_repositories = selected_repositories[30:]
        else:
            selected_repositories = False
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
            vprint(0, "Unzipping {}".format(repository))
            with mount_basedir():
                result = unzip_repository(session, repository)
                vprint(1, result)
            status.count += 1
            session.commit()



def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Extract notebooks from registered repositories")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-n", "--repositories", type=int, default=None,
                        nargs="*",
                        help="repositories ids")
    parser.add_argument("-s", "--status", type=int,
                        default=consts.R_COMPRESS_OK + consts.R_COMMIT_MISMATCH,
                        help="has processed status")
    parser.add_argument("-z", "--no", type=int, default=0,
                        help="does not have status")
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
    parser.add_argument("-t", "--retry-timeout", action='store_true',
                        help="retry timeout")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="id interval")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count results")
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
            args.repositories or True,
            args.status,
            args.no,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == "__main__":
    main()
