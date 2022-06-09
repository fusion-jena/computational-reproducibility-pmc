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
from utils import check_exit, savepid, SafeSession
from e5_unzip_repositories import unzip_repository


def cell_output_formats(cell):
    """Generates output formats from code cells"""
    if cell.get("cell_type") != "code":
        return
    for output in cell.get("outputs", []):
        if output.get("output_type") in {"display_data", "execute_result"}:
            for data_type in output.get("data", []):
                yield data_type
        elif output.get("output_type") == "error":
            yield "error"


@timeout(5 * 60, use_signals=False)
def load_notebook(repository_id, path, notebook_file, nbrow):
    """Extract notebook information and cells from notebook"""
    # pylint: disable=too-many-locals
    status = 0
    try:
        with open(str(path / notebook_file)) as ofile:
            notebook = nbf.read(ofile, nbf.NO_CONVERT)
        nbrow["nbformat"] = "{0[nbformat]}".format(notebook)
        if "nbformat_minor" in notebook:
            nbrow["nbformat"] += ".{0[nbformat_minor]}".format(notebook)
        notebook = nbf.convert(notebook, 4)
        metadata = notebook["metadata"]
    except OSError as e:
        vprint(3, "Failed to open notebook {}".format(e))
        nbrow["processed"] = consts.N_LOAD_ERROR
        if os.path.islink(str(path / notebook_file)):
            import textwrap
            vprint(3, "Notebook is broken link. Use the following SQL to fix:")
            text = (textwrap.dedent("""\
            select notebooks_count, (char_length(newtext) - char_length(replace(newtext, '''', ''))), concat(
                'update repositories ',
                'set notebooks_count = ',
                (char_length(newtext) - char_length(replace(newtext, ';', ''))) + 1,
                ', notebooks = ''',
                newtext,
                ''' where id = ',
                id,
                ';'
            ) from (
                select id, notebooks_count, replace(
                    replace(
                        replace(
                            notebooks,
                            '{0};', ''
                        ),
                        ';{0}', ''
                    ),
                    '''', ''''''
                ) as newtext
                from repositories where id = {1}
            ) as foo;
            """.format(notebook_file, repository_id)))
            text = " ".join(x.strip() for x in text.split("\n"))
            print(text)
        return nbrow, []

    except Exception as e:  # pylint: disable=broad-except
        vprint(3, "Failed to load notebook {}".format(e))
        nbrow["processed"] = consts.N_LOAD_FORMAT_ERROR
        return nbrow, []

    nbrow["kernel"] = metadata.get("kernelspec", {}).get("name", "no-kernel")

    language_info = metadata.get("language_info", {})
    nbrow["language"] = language_info.get("name", "unknown")
    nbrow["language_version"] = language_info.get("version", "unknown")
    shell = InteractiveShell.instance()
    is_python = nbrow["language"] == "python"
    is_unknown_version = nbrow["language_version"] == "unknown"

    cells = notebook["cells"]
    cells_info = []
    exec_count = -1
    for index, cell in enumerate(cells):
        vprint(3, "Loading cell {}".format(index))
        cell_exec_count = cell.get("execution_count") or -1
        if isinstance(cell_exec_count, str) and cell_exec_count.isdigit():
            cell_exec_count = int(cell_exec_count)
        if isinstance(cell_exec_count, int):
            exec_count = max(exec_count, cell_exec_count)
        output_formats = ";".join(set(cell_output_formats(cell)))

        cell_processed = consts.C_OK
        if is_unknown_version:
            cell_processed = consts.C_UNKNOWN_VERSION

        try:
            source = cell["source"] = cell["source"] or ""
            if is_python and cell.get("cell_type") == "code":
                try:
                    source = shell.input_transformer_manager.transform_cell(source)
                except (IndentationError, SyntaxError) as err:
                    vprint(3, "Error on cell transformation: {}".format(err))
                    source = ""
                    status = consts.N_LOAD_SYNTAX_ERROR
                    cell_processed |= consts.C_SYNTAX_ERROR
                if "\0" in source:
                    vprint(3, "Found null byte in source. Replacing it by \\n")
                    source = source.replace("\0", "\n")

            cellrow = {
                "repository_id": repository_id,
                "notebook_id": None,
                "index": index,
                "cell_type": cell.get("cell_type", "<unknown>"),
                "execution_count": cell.get("execution_count"),
                "lines": cell["source"].count("\n") + 1,
                "output_formats": output_formats,
                "source": source,
                "python": is_python,
                "processed": cell_processed,
            }
            cells_info.append(cellrow)
            nbrow["total_cells"] += 1
            if cell.get("cell_type") == "code":
                nbrow["code_cells"] += 1
                if output_formats:
                    nbrow["code_cells_with_output"] += 1
            elif cell.get("cell_type") == "markdown":
                nbrow["markdown_cells"] += 1
            elif cell.get("cell_type") == "raw":
                nbrow["raw_cells"] += 1
            else:
                nbrow["unknown_cell_formats"] += 1
            if not cell["source"].strip():
                nbrow["empty_cells"] += 1
        except KeyError as err:
            vprint(3, "Error on cell extraction: {}".format(err))
            status = consts.N_LOAD_FORMAT_ERROR
    if nbrow["total_cells"] == 0:
        status = consts.N_LOAD_FORMAT_ERROR

    nbrow["max_execution_count"] = exec_count
    nbrow["processed"] = status
    return nbrow, cells_info



def process_repository(session, repository, skip_if_error=consts.R_N_ERROR):
    """Process repository"""
    if repository.processed & (consts.R_N_EXTRACTION + skip_if_error):
        return "already processed"
    if repository.processed & consts.R_N_ERROR:
        session.add(repository)
        repository.processed -= consts.R_N_ERROR

    count = 0
    for name in repository.notebook_names:
        if not name:
            continue
        count += 1
        notebook = session.query(Notebook).filter(
            Notebook.repository_id == repository.id,
            Notebook.name == name,
        ).first()
        if notebook is not None:
            if notebook.processed & consts.N_STOPPED:
                session.delete(notebook)
                session.commit()
            else:
                if notebook.processed & consts.N_GENERIC_LOAD_ERROR:
                    count -= 1
                    vprint(2, "Notebook already exists. Delete from DB: {}".format(notebook))
                    with open(str(config.LOGS_DIR / "todo_delete"), "a") as f:
                        f.write("{},".format(notebook.id))

                continue  # Skip working notebook

        if not repository.path.exists():
            vprint(2, "Unzipping repository: {}".format(repository.zip_path))
            msg = unzip_repository(session, repository)
            if msg != "done":
                vprint(2, msg)
                return "failed"

        try:
            vprint(2, "Loading notebook {}".format(name))
            nbrow = {
                "repository_id": repository.id,
                "name": name,
                "nbformat": 0,
                "kernel": "no-kernel",
                "language": "unknown",
                "language_version": "unknown",
                "max_execution_count": 0,
                "total_cells": 0,
                "code_cells": 0,
                "code_cells_with_output": 0,
                "markdown_cells": 0,
                "raw_cells": 0,
                "unknown_cell_formats": 0,
                "empty_cells": 0,
                "processed": consts.N_OK,
            }
            try:
                nbrow, cells = load_notebook(repository.id, repository.path, name, nbrow)
            except TimeoutError:
                nbrow["processed"] = consts.N_LOAD_TIMEOUT
                cells = []
            nbrow["processed"] |= consts.N_STOPPED
            notebook = Notebook(**nbrow)
            session.dependent_add(
                notebook, [Cell(**cellrow) for cellrow in cells], "notebook_id"
            )

        except Exception as err:  # pylint: disable=broad-except
            repository.processed |= consts.R_N_ERROR
            session.add(repository)
            vprint(1, "Failed to load notebook {} due {!r}".format(name, err))
            if config.VERBOSE > 4:
                import traceback
                traceback.print_exc()

    if not repository.processed & consts.R_N_ERROR and count == repository.notebooks_count:
        repository.processed |= consts.R_N_EXTRACTION
        session.add(repository)

    status, err = session.commit()
    if not status:
        if repository.processed & consts.R_N_EXTRACTION:
            repository.processed -= consts.R_N_EXTRACTION
        if not repository.processed & consts.R_N_ERROR:
            repository.processed += consts.R_N_ERROR
        session.add(repository)
        session.commit()
        return "Failed due {!r}".format(err)

    return "done"


def apply(
    session, status, selected_repositories, skip_if_error,
    count, interval, reverse, check
):
    while selected_repositories:
        filters = [
            Repository.processed.op("&")(consts.R_N_EXTRACTION) == 0, # no extraction
            Repository.processed.op("&")(skip_if_error) == 0, # no failure
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
            vprint(0, "Extracting notebooks/cells from {}".format(repository))
            with mount_basedir():
                result = process_repository(session, repository, skip_if_error)
                vprint(0, result)
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
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
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
            SafeSession(session, interrupted=consts.N_STOPPED),
            status,
            args.repositories or True,
            0 if args.retry_errors else consts.R_N_ERROR,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == "__main__":
    main()
