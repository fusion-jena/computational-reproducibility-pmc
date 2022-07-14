"""Remove processed notebooks from disk"""
import argparse
import shutil
import config
import os

import consts
from db import Repository, Notebook, connect
from utils import vprint, StatusLogger, mount_basedir, check_exit, savepid



def apply(session, status, keep, count, interval, reverse, check):
    """Compress repositories"""
    filters = [
        Repository.processed.op('&')(consts.R_COMPRESS_OK) == 0,
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
        vprint(0, "Compressing {}".format(repository))
        vprint(1, "Into {}".format(repository.zip_path))
        with mount_basedir():
            try:
                if repository.path.exists():
                    commit = repository.get_commit()
                    if commit != repository.commit:
                        repository.processed |= consts.R_COMMIT_MISMATCH

                repository.processed |= consts.R_COMPRESS_ERROR
                if repository.zip_path.exists() or repository.compress():
                    if repository.processed & consts.R_COMPRESS_ERROR:
                        repository.processed -= consts.R_COMPRESS_ERROR
                    if not keep:
                        shutil.rmtree(str(repository.path), ignore_errors=True)
                elif not repository.zip_path.exists():
                    if repository.processed & consts.R_COMPRESS_ERROR:
                        repository.processed -= consts.R_COMPRESS_ERROR
                    if not repository.path.exists():
                        repository.processed |= consts.R_UNAVAILABLE_FILES
                    vprint(1, "failed")
                if repository.zip_path.exists():
                    vprint(1, "ok")
                    repository.processed |= consts.R_COMPRESS_OK
            except Exception as err:
                vprint(1, "Failed: {}".format(err))
        session.add(repository)
        status.count += 1
        session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Compress processed repositories")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-z", "--compression", type=str,
                        default=config.COMPRESSION,
                        help="compression algorithm")
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="id interval")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count results")
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='iterate in reverse order')
    parser.add_argument('-k', '--keep-uncompressed', action='store_true',
                        help='keep uncompressed files')
    parser.add_argument('--check', type=str, nargs='*',
                        default={'all', script_name, script_name + '.py'},
                        help='check name in .exit')

    args = parser.parse_args()
    config.VERBOSE = args.verbose
    status = None
    if not args.count:
        status = StatusLogger(script_name)
        status.report()

    config.COMPRESSION = args.compression
    with connect() as session, savepid():
        apply(
            session,
            status,
            args.keep_uncompressed,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == "__main__":
    main()
