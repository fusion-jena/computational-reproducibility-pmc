"""Load markdown features"""
import argparse
import os
import sys
import hashlib

import config
import consts

from collections import Counter, OrderedDict

from db import Notebook, connect, NotebookMarkdown, MarkdownFeature, Cell
from db import NotebookAST, NotebookModule, NotebookFeature, NotebookName
from db import CodeAnalysis, CellModule, CellFeature, CellName
from utils import vprint, StatusLogger, check_exit, savepid


EXERCISE_WORDS = ['homework', 'assignment', 'course', 'exercise', 'lesson']

def process_notebook(session, notebook):
    if notebook.sha1_source != "":
        return "already processed"

    counter = Counter()
    concat = []
    query = (
        notebook.cell_objs
        .order_by(Cell.index.asc())
    )
    for cell in query:
        concat.append(cell.source)
        concat.append(cell.output_formats)
        lower = cell.source.lower()
        for word in EXERCISE_WORDS:
            if word in lower:
                counter[word] += 1

    lower = notebook.name.lower()
    for word in EXERCISE_WORDS:
        if word in lower:
            counter[word] = -counter[word] - 1


    concat_str = "<#<cell>#>\n".join(concat)
    notebook.sha1_source = hashlib.sha1(concat_str.encode('utf-8')).hexdigest()
    for key, value in counter.items():
        setattr(notebook, key + "_count", value)

    session.add(notebook)
    return "ok"


def load_repository(session, notebook, repository_id):
    if repository_id != notebook.repository_id:
        try:
            session.commit()
        except Exception as err:
            vprint(0, 'Failed to save modules from repository {} due to {}'.format(
                repository_id, err
            ))

        vprint(0, 'Processing repository: {}'.format(repository_id))
        return notebook.repository_id

    return repository_id


def apply(
    session, status,
    count, interval, reverse, check
):
    """Extract code cell features"""
    filters = [
        Notebook.sha1_source == "",
        Notebook.processed.op("&")(consts.N_GENERIC_LOAD_ERROR) == 0,
    ]
    if interval:
        filters += [
            Notebook.repository_id >= interval[0],
            Notebook.repository_id <= interval[1],
        ]

    query = (
        session.query(Notebook)
        .filter(*filters)
    )

    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            Notebook.repository_id.desc(),
            Notebook.id.desc(),
        )
    else:
        query = query.order_by(
            Notebook.repository_id.asc(),
            Notebook.id.asc(),
        )

    repository_id = None

    for notebook in query:
        if check_exit(check):
            session.commit()
            vprint(0, 'Found .exit file. Exiting')
            return
        status.report()

        repository_id = load_repository(session, notebook, repository_id)

        vprint(1, 'Processing notebook: {}'.format(notebook))
        result = process_notebook(session, notebook)
        vprint(1, result)
        status.count += 1
    session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description='Calculate MD5 hashes and the presence of exercise keywords')
    parser.add_argument('-v', '--verbose', type=int, default=config.VERBOSE,
                        help='increase output verbosity')
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
