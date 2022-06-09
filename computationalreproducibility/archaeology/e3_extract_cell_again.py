"""Load notebook and cells"""
import argparse
import os
import sys
import tarfile


import config
import consts

import nbformat as nbf
from IPython.core.interactiveshell import InteractiveShell

from itertools import groupby


from db import Cell, Notebook, Repository, Execution, connect
from utils import vprint, StatusLogger
from utils import mount_basedir, check_exit, savepid
from config import Path


def process_repository(session, status, repository, query_iter):
    query_iter = list(query_iter)
    zip_path = None
    tarzip = None
    if not repository.path.exists():
        if not repository.zip_path.exists():
            repository.processed |= consts.R_UNAVAILABLE_FILES
            session.add(repository)
            status.count += len(query_iter)
            return "Failed. Repository not found: {}".format(repository)
        tarzip =  tarfile.open(str(repository.zip_path))
        zip_path = Path(repository.hash_dir2)

    shell = InteractiveShell.instance()
    group = groupby(
        query_iter,
        lambda x: (x[1])
    )
    for notebook, new_iter in group:
        cells = list(query_iter)
        vprint(1, "Processing notebook: {}. Found {} cells".format(notebook, len(cells)))
        name = notebook.name
        vprint(2, "Loading notebook file")
        if tarzip:
            notebook = nbf.read(
                tarzip.extractfile(tarzip.getmember(str(zip_path / name))),
                nbf.NO_CONVERT
            )
        else:
            with open(str(repository.path / name)) as ofile:
                notebook = nbf.read(ofile, nbf.NO_CONVERT)
        notebook = nbf.convert(notebook, 4)
        metadata = notebook["metadata"]
        language_info = metadata.get("language_info", {})
        language_name = language_info.get("name", "unknown")

        for cell, _, _ in new_iter:
            vprint(2, "Loading cell {}".format(cell.index))

            index = int(cell.index)
            notebook_cell = notebook["cells"][index]
            source = notebook_cell.get("source", "")
            if language_name == "python" and notebook_cell.get("cell_type") == "code":
                try:
                    source = shell.input_transformer_manager.transform_cell(source)
                except (IndentationError, SyntaxError):
                    pass
            cell.source = source
            if cell.processed & consts.C_MARKED_FOR_EXTRACTION:
                cell.processed -= consts.C_MARKED_FOR_EXTRACTION
            session.add(cell)
        session.commit()
    return "ok"


def apply(session, status, use_compressed, count, interval, reverse, check):
    filters = [
        Cell.processed.op('&')(consts.C_MARKED_FOR_EXTRACTION) != 0,
        Repository.processed.op("&")(use_compressed) == 0,
    ]
    if interval:
        filters += [
            Repository.id >= interval[0],
            Repository.id <= interval[1],
        ]

    query = (
        session.query(Cell, Notebook, Repository)
        .join(Notebook)
        .join(Repository)
        .filter(*filters)
        .order_by(
            Repository.id.asc(),
            Notebook.id.asc()
        )
    )
    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            Repository.id.desc(),
            Notebook.id.asc(),
            Cell.id.asc(),
        )
    else:
        query = query.order_by(
            Repository.id.asc(),
            Notebook.id.asc(),
            Cell.id.asc(),
        )

    group = groupby(
        query, lambda x: (
            x[2]
        )
    )
    for repository, query_iter in group:
        if check_exit(check):
            vprint(0, "Found .exit file. Exiting")
            return
        status.report()
        vprint(0, "Processing repository: {}".format(repository))
        with mount_basedir():
            result = process_repository(session, status, repository, query_iter)
            vprint(1, result)
        session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Execute repositories")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="repository id interval")
    parser.add_argument("-u", "--use-compressed", action='store_true',
                        help="use compressed")
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
            0 if args.use_compressed else consts.R_COMPRESS_OK,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )


if __name__ == "__main__":
    main()
