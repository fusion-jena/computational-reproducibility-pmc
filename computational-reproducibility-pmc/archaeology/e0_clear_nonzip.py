"""Remove processed notebooks from disk"""
import argparse
import shutil
import os


import config
import consts

from db import Repository, Notebook, connect
from utils import vprint, StatusLogger, mount_basedir, check_exit, savepid


def apply(session, status, count, interval, reverse, check):
    """Remove non zip files from compressed repositories"""
    filters = [
        Repository.processed.op("&")(consts.R_COMPRESS_OK) != 0, # Were compressed
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
        with mount_basedir():
            if repository.zip_path.exists() and repository.path.exists():
                vprint(0, "Removing non zip files from {}".format(repository))
                shutil.rmtree(str(repository.path), ignore_errors=True)
                session.add(repository)
            elif repository.path.exists():
                vprint(0, "Zip not found for {}".format(repository))
                repository.processed -= consts.R_COMPRESS_OK
                session.add(repository)
            elif not repository.zip_path.exists():
                vprint(0, "Repository not found {}".format(repository))
                repository.processed |= consts.R_UNAVAILABLE_FILES
                session.add(repository)
        status.count += 1
        session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Remove directories of repositories that were zipped")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
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
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == "__main__":
    main()
