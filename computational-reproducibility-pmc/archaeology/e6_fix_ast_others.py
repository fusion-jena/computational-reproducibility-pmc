"""Load markdown features"""
import argparse
import os
import sys

import config
import consts

from collections import Counter, OrderedDict

from db import CodeAnalysis, NotebookAST, connect
from utils import vprint, StatusLogger, check_exit, savepid



def apply(
    session, status,
    count, interval, reverse, check
):
    """Extract code cell features"""
    filters = [
        NotebookAST.ast_others != "",
    ]
    if interval:
        filters += [
            NotebookAST.repository_id >= interval[0],
            NotebookAST.repository_id <= interval[1],
        ]

    query = (
        session.query(NotebookAST)
        .filter(*filters)
    )

    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            NotebookAST.repository_id.desc(),
            NotebookAST.id.desc(),
        )
    else:
        query = query.order_by(
            NotebookAST.repository_id.asc(),
            NotebookAST.id.asc(),
        )

    repository_id = None

    for ast in query:
        if check_exit(check):
            session.commit()
            vprint(0, 'Found .exit file. Exiting')
            return
        status.report()
        if ast.repository_id != repository_id:
            repository_id = ast.repository_id
            vprint(0, "Processing repository: {}".format(repository_id))
            session.commit()
        vprint(1, 'Processing ast: {}'.format(ast))
        ast.ast_extslice = ast.ast_others.count("ast_extslice")
        ast.ast_others = ast.ast_others.replace("ast_extslice", "").replace(",", "").strip()
        ast.ast_repr = ast.ast_others.count("ast_repr")
        ast.ast_others = ast.ast_others.replace("ast_repr", "").replace(",", "").strip()
        session.add(ast)
        vprint(2, "done")
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
