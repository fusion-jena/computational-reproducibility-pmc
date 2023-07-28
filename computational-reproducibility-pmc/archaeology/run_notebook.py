# coding: utf-8
import argparse
import time
import traceback
import re
import io
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from math import ceil
from copy import deepcopy

import nbdime
import nbformat
import nbconvert
from nbconvert.preprocessors import ExecutePreprocessor, Preprocessor
from jupyter_client.kernelspec import find_kernel_specs
from sqlalchemy.exc import DataError

import config
import consts
from config import Path
from db import connect, Execution, Notebook
from execution_rules import EXECUTION_MODE, exec_to_num
from utils import vprint, savepid, to_unicode, human_readable_duration

TimeoutException = RuntimeError if sys.version_info < (3, 0) else TimeoutError


class NewPreprocessor(Preprocessor):
    def preprocess(self, nb, resources):
        for order, index in enumerate(self.cell_order):
            self.last_try = (order, index)
            nb.cells[index], resources = self.preprocess_cell(
                nb.cells[index], resources, index
            )
        return nb, resources


class TopBottomPreprocessor(Preprocessor):

    def skip_notebook(self, notebook):
        self.cell_order = [
            index for index, cell in enumerate(notebook.cells)
            if str(cell.get('execution_count', ''))
        ]
        if not self.cell_order:
            self.cell_order = list(range(len(notebook.cells)))
        return None


class ExecutionCountPreprocessor(Preprocessor):

    def skip_notebook(self, notebook):
        cells = sorted([
            (int(cell.get('execution_count')), index, cell)
            for index, cell in enumerate(notebook.cells)
            if isinstance(cell.get('execution_count'), int)
        ])
        if not cells:
            return "No numbered cells"

        numbers = {count for count, _, _ in cells}
        if len(numbers) != len(cells):
            return "Repeated cell numbers"

        self.cell_order = [index for _, index, _ in cells]


        print(len(cells), len(notebook.cells))
        return None


class ExecutionCountOrganizer(
    ExecutePreprocessor, ExecutionCountPreprocessor, NewPreprocessor
):
    pass


class TopBottomOrganizer(
    ExecutePreprocessor, TopBottomPreprocessor, NewPreprocessor
):
    pass


class ProcessNotebook(object):

    def __init__(self, session, name, mode_num, notebook_id=None):
        self.session = session
        self.execution = None
        self.mode = EXECUTION_MODE.get(mode_num, 1)
        self.path = Path(name).expanduser()
        self.nb = None
        self.old_nb = None
        self.start_time = None
        if self.mode.cellorder:
            self.organizer = ExecutionCountOrganizer
        else:
            self.organizer = TopBottomOrganizer
        if notebook_id is not None:
            self.execution = session.query(Execution).filter(
                Execution.notebook_id == notebook_id,
                Execution.mode == mode_num,
            ).first()
            if self.execution:
                if self.execution.processed & consts.E_EXECUTED:
                    vprint(3, "Already executed")
                    exit(0)
                self.execution.reason = None
                self.execution.msg = None
                self.execution.cell = None
                self.execution.count = None
                self.execution.diff = None
                self.execution.duration = None
                self.execution.timeout = None
                self.execution.diff_count = None
                self.execution.processed = consts.E_INSTALLED
            else:
                self.execution = Execution(
                    notebook_id=notebook_id, mode=mode_num,
                    processed=consts.E_INSTALLED
                )
                self.execution.repository_id = session.get(Notebook, notebook_id).repository_id
            self.session.add(self.execution)


    def timeout_func(self, cell):
        available = config.NOTEBOOK_TIMEOUT - int(ceil(time.time() - self.start_time))
        return max(1, available)

    def load_file(self):
        vprint(3, u"Reading file {}".format(to_unicode(self.path)))
        try:
            with open(str(self.path)) as f:
                self.nb = nbformat.read(f, as_version=4)
            self.old_nb = deepcopy(self.nb)

            if self.execution:
                self.execution.processed |= consts.E_LOADED
        except Exception:
            vprint(4, "Failed to open file")
            if self.execution:
                self.execution.reason = "<Read notebook error>"
                self.execution.msg = traceback.format_exc()
                self.commit()
            exit(1)

    def set_kernel(self, ep):
        kernel = (
            self.nb
            .get('metadata', {})
            .get('kernelspec', {})
            .get('name', 'python')
        )
        kernel_specs = find_kernel_specs()
        if kernel not in kernel_specs:
            old_kernel = kernel
            if "python" in kernel_specs:
                kernel = "python"
            else:
                kernel = "python{}".format(sys.version_info[0])

            vprint(3, "Kernel {} not found. Using {}".format(old_kernel, kernel))
            ep.kernel_name = kernel

    def commit(self):
        self.session.commit()

    def run(self):
        self.load_file()
        ep = self.organizer()
        ep.last_try = (-1, -1)
        self.set_kernel(ep)
        skip = ep.skip_notebook(self.nb)
        if skip is not None:
            vprint(3, u"Skipping notebook. Reason: {}".format(skip))
            if self.execution:
                self.execution.reason = "<Skipping notebook>"
                self.execution.msg = skip
                self.commit()
            exit(0)

        timeout = 0
        try:
            vprint(3, "Executing notebook")
            self.execute_notebook(ep)
        except TimeoutException:
            timeout = 1
            vprint(4, "Timeout")
            if self.execution:
                self.execution.processed |= consts.E_TIMEOUT
        except RuntimeError as e:
            reason = "RuntimeError"
            vprint(4, "Exception: {}".format(reason))
            if self.execution:
                self.execution.processed |= consts.E_EXCEPTION
                self.execution.reason = reason
                self.execution.msg = traceback.format_exc()
        except AttributeError:
            reason = "Malformed Notebook"
            vprint(4, "Exception: {}".format(reason))
            if self.execution:
                self.execution.processed |= consts.E_EXCEPTION
                self.execution.reason = reason
                self.execution.msg = traceback.format_exc()
        except nbconvert.preprocessors.execute.CellExecutionError as e:
            try:
                reason = re.findall(r"\n(.*): .*\n$", str(e))[-1]
            except IndexError:
                reason = "<Unknown exception>"
            vprint(4, "Exception: {}".format(reason))
            if self.execution:
                self.execution.processed |= consts.E_EXCEPTION
                self.execution.reason = reason
                self.execution.msg = traceback.format_exc()

        vprint(4, "Run up to {}".format(ep.last_try))
        if self.execution:
            self.execution.timeout = config.NOTEBOOK_TIMEOUT
            self.execution.duration = time.time() - self.start_time
            self.execution.cell = ep.last_try[1]
            self.execution.count = ep.last_try[0] + 1


        vprint(3, "Comparing notebooks")
        diff = []
        for _, index in zip(range(ep.last_try[0] + 1 - timeout), ep.cell_order):
            old_cell = self.old_nb.cells[index]
            new_cell = self.nb.cells[index]
            old_cell_metatdata_provenance = []
            new_cell_metatdata_provenance = []
            old_outputs = old_cell.get('outputs', [])
            new_outputs = new_cell.get('outputs', [])
            old_source = old_cell.get('source', [])
            new_source = new_cell.get('source', [])
            self.nb.cells[index].metadata = {'provenance': [
            {
                'outputs': old_outputs,
                'source': old_source,
            },
            {
                'outputs': new_outputs,
                'source': new_source,
            }
            ]}
            celldiff = nbdime.diff_notebooks(self.nb.cells[index].metadata.provenance[0], self.nb.cells[index].metadata.provenance[1])
            if celldiff:
                diff.append(index)

            self.nb.cells[index].metadata.provenance[0]['start_time'] = 'Unknown'
            self.nb.cells[index].metadata.provenance[0]['execution_time'] = 'Unknown'
            self.nb.cells[index].metadata.provenance[1]['start_time'] = time.strftime("%a, %d %b %Y %H:%M:%S %Z",time.localtime(self.start_time))
            self.nb.cells[index].metadata.provenance[1]['execution_time'] = human_readable_duration(self.execution.duration)
            with io.open(str(self.path), 'w', encoding='utf-8') as f:
                nbformat.write(self.nb, f)

        if not diff:
            vprint(4, "Identical results")
            if self.execution:
                self.execution.processed |= consts.E_SAME_RESULTS
                self.execution.diff_count = 0
                self.execution.diff = ""

        else:
            vprint(4, "Diff on cells: {}".format(diff))
            if self.execution:
                self.execution.diff_count = len(diff)
                self.execution.diff = ",".join(map(str, diff))

        if self.execution:
            self.execution.processed |= consts.E_EXECUTED
            self.commit()

    def execute_notebook(self, ep):
        ep.timeout_func = self.timeout_func
        self.start_time = time.time()
        ep.preprocess(self.nb, {'metadata': {'path': str(self.path.parent)}})

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Run notebook")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-n", "--notebook", type=int, default=None,
                        help="notebooks id")
    parser.add_argument("-p", "--path", type=str, default="~/projects/chained_example.ipynb",
                        help="notebook path")
    parser.add_argument("-m", "--mode", type=int, default=1,
                        help="execution mode")

    args = parser.parse_args()
    config.VERBOSE = args.verbose

    if not config.IS_SQLITE:
        try:
            import psycopg2
        except ImportError:
            import subprocess
            subprocess.call(["pip", "install", "psycopg2", "--upgrade"])
            import psycopg2
    with connect() as session, savepid():
        ProcessNotebook(
            session, args.path, args.mode,
            notebook_id=args.notebook
        ).run()


if __name__ == "__main__":
    main()
