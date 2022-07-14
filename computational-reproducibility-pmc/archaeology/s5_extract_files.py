"""Load markdown features"""
import argparse
import os
import sys
import ast
import tarfile
import re

import config
import consts
from db import Repository, RepositoryFile, connect
from utils import vprint, StatusLogger, check_exit, savepid, to_unicode
from utils import mount_basedir, ignore_surrogates
from future.utils.surrogateescape import register_surrogateescape

def process_repository(session, repository, skip_if_error=consts.R_COMPRESS_ERROR):
    if repository.processed & consts.R_EXTRACTED_FILES:
        return 'already processed'
    if repository.processed & consts.R_COMPRESS_ERROR:
        repository.processed -= consts.R_COMPRESS_ERROR
        session.add(repository)

    try:
        if not repository.zip_path.exists():
            raise Exception("Repository {} zip path not found: {}".format(
                repository.id, repository.zip_path
            ))
        tarzip = tarfile.open(str(repository.zip_path))
        members = tarzip.getmembers()
        repository_id = repository.id
        for member in members:
            info = member.get_info()
            name = info['name']
            if not name.startswith(repository.hash_dir2):
                raise Exception("Repository {} - Invalid file in zip: {}".format(
                    repository.id, name
                ))
            name, had_surrogates = ignore_surrogates(name)
            session.add(RepositoryFile(
                repository_id=repository_id,
                path=name[(len(repository.hash_dir2) + 1):],
                size=info['size'],
                had_surrogates=had_surrogates
            ))
        repository.processed += consts.R_EXTRACTED_FILES
        session.add(repository)
        return "done"
    except Exception as err:
        if repository.processed & consts.R_EXTRACTED_FILES:
            repository.processed -= consts.R_EXTRACTED_FILES
        repository.processed |= consts.R_COMPRESS_ERROR
        session.add(repository)
        return "Failed due to {}".format(err)


def apply(
    session, status,
    skip_if_error,
    count, interval, reverse, check
):
    """Extract code cell features"""
    filters = [
        Repository.processed.op('&')(consts.R_EXTRACTED_FILES) == 0,
        Repository.processed.op('&')(skip_if_error) == 0,
        Repository.processed.op('&')(consts.R_COMPRESS_OK) != 0,  # Compressed
    ]
    if interval:
        filters += [
            Repository.id >= interval[0],
            Repository.id <= interval[1],
        ]

    query = (
        session.query(Repository)
        .filter(*filters)
    )

    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            Repository.id.desc(),
        )
    else:
        query = query.order_by(
            Repository.id.asc(),
        )

    for repository in query:
        if check_exit(check):
            session.commit()
            vprint(0, 'Found .exit file. Exiting')
            return
        status.report()

        vprint(0, 'Processing repository: {}'.format(repository))
        with mount_basedir():
            result = process_repository(
                session, repository, skip_if_error,
            )
        vprint(1, result)
        status.count += 1
        session.commit()


def main():
    """Main function"""
    register_surrogateescape()
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description='Execute repositories')
    parser.add_argument('-v', '--verbose', type=int, default=config.VERBOSE,
                        help='increase output verbosity')
    parser.add_argument('-e', '--retry-errors', action='store_true',
                        help='retry errors')
    parser.add_argument('-i', '--interval', type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help='repository id interval')
    parser.add_argument('-c', '--count', action='store_true',
                        help='count results')
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
            0 if args.retry_errors else consts.R_COMPRESS_ERROR,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )


if __name__ == '__main__':
    main()
