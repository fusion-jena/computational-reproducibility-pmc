"""Load markdown features"""
import argparse
import os
import sys

import config
import consts

from db import CellModule, RepositoryFile, connect
from utils import vprint, StatusLogger, check_exit, savepid

def process_cell_module(session, cell_module, archive):
    if cell_module.local_possibility is not None:
        return "already processed"
    session.add(cell_module)
    if cell_module.local:
        cell_module.local_possibility = 4
        return "local 4"

    module_name = cell_module.module_name.replace(".", "/")
    if not module_name:
        cell_module.local_possibility = 0
        return "empty 0"

    modes = [
        [module_name, 3, "full match 3"],
    ]
    split = module_name.split('/', 1)
    if len(split) > 1:
        modes.append([split[-1], 2, "all but first 2"])

    split = module_name.split('/')
    if len(split) > 2:
        modes.append([split[-1], 1, "module name 1"])


    for name in archive:
        for modname, value, result in modes:
            if name.endswith(modname):
                if len(name) <= len(modname):
                    cell_module.local_possibility = value
                    return result
                elif name[-len(modname) - 1] == '/':
                    cell_module.local_possibility = value
                    return result + " (py)"

    cell_module.local_possibility = 0
    return "non-local"


def load_repository(session, cell_module, skip_repo, repository_id, archives):
    if repository_id != cell_module.repository_id:
        repository = cell_module.repository_obj
        try:
            session.commit()
        except Exception as err:
            vprint(0, 'Failed to save modules from repository {} due to {}'.format(
                repository_id, err
            ))

        vprint(0, 'Processing repository: {}'.format(repository))
        if not repository.processed & consts.R_EXTRACTED_FILES:
            vprint(1, 'Skipping. Files not extracted from repository')
            return True, cell_module.repository_id, None

        archives = {
            fil.path for fil in session.query(RepositoryFile).filter(
                RepositoryFile.repository_id == repository.id
            )
        }
        return False, cell_module.repository_id, archives

    return skip_repo, repository_id, archives


def apply(
    session, status,
    count, interval, reverse, check
):
    """Extract code cell features"""
    filters = [
        CellModule.local_possibility.is_(None)
    ]
    if interval:
        filters += [
            CellModule.repository_id >= interval[0],
            CellModule.repository_id <= interval[1],
        ]

    query = (
        session.query(CellModule)
        .filter(*filters)
    )

    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            CellModule.repository_id.desc(),
            CellModule.id.desc(),
        )
    else:
        query = query.order_by(
            CellModule.repository_id.asc(),
            CellModule.id.asc(),
        )

    skip_repo = False
    repository_id = None
    archives = None

    for cell_module in query:
        if check_exit(check):
            session.commit()
            vprint(0, 'Found .exit file. Exiting')
            return
        status.report()

        skip_repo, repository_id, archives = load_repository(
            session, cell_module, skip_repo, repository_id, archives
        )
        if skip_repo:
            continue

        vprint(1, 'Processing module: {}'.format(cell_module))
        result = process_cell_module(
            session, cell_module, archives
        )
        vprint(1, result)
        status.count += 1
    session.commit()


def main():
    """Main function"""
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
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == '__main__':
    main()
