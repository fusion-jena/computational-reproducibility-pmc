import argparse
import os
import sys
import shutil
import subprocess
import asyncio
from asyncio.subprocess import PIPE as APIPE
import re

import config
from db import Repository, Notebook, NotebookCodeStyle, connect
from utils import mount_basedir, savepid, vprint


# notebook = ''
# process = subprocess.Popen(['flake8-nb', '--ignore=E402'] + [notebook], stdout=APIPE, stderr=APIPE)
# out, err = process.communicate()
# rc = process.returncode
# if rc and out:
#     val = out.decode('UTF-8').rstrip().split('\n')
#     for err in val:
#         print(err)
#         x = re.search(r"(.*)#In\[(.*)\]:(\d+):(\d+): (\w\d+) (.*)", err)
#         notebook_name = x.group(0)
#         cell_index = x.group(1)
#         err_code = x.group(5)
#         err_code_desc = x.group(6)
#         print(x.group(0))
#         print(x.group(1))
#         print(x.group(2))
#         print(x.group(3))
#         print(x.group(4))
#         print(x.group(5))
#         print(x.group(6))

        #if re.match(r"(.*)#In[\d[0-9\w+]]:(\d[0-9\w+):(\d[0-9\w+): (.*)", err):

def call_codestyle_check(session, repository, notebook):
    if repository.path.exists():
        notebook_path = str(repository.path / notebook.name)
        print(notebook_path)

        process = subprocess.Popen(['flake8-nb'] + [notebook_path], stdout=APIPE, stderr=APIPE)
        out, err = process.communicate()
        rc = process.returncode
        if rc and out:
            code_style_err = out.decode('UTF-8').rstrip().split('\n')
            for err in code_style_err:
                x = re.search(r"(.*)#In\[(.*)\]:(\d+):(\d+): (\w\d+) (.*)", err)
                if (len(x.groups() == 6)):
                    notebook_name = x.group(1)
                    cell_index = x.group(2)
                    err_code = x.group(5)
                    err_code_desc = x.group(6)

                    notebook_code_style = NotebookCodeStyle(
                        cell_index = cell_index,
                        err_code = err_code,
                        err_code_desc = err_code_desc,
                        notebook_id = notebook.id,
                        repository_id = notebook.repository_id,
                    )
                    session.add(notebook_code_style)
                    session.commit()
                    vprint(1, "Done. NotebookCodeStyle  ID={}".format(notebook_code_style.id))


def check_pycodestyline_nb(session):
    query = (
        session.query(Repository)
    )
    for repository in query:
        for name in repository.notebook_names:
            if not name:
                continue
            notebook = session.query(Notebook).filter(
                Notebook.repository_id == repository.id,
                Notebook.name == name,
                Notebook.language == "python",
                Notebook.language_version != "unknown",
            ).first()
            if notebook is not None:
                call_codestyle_check(session, repository, notebook)

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        check_pycodestyline_nb(session)

if __name__ == "__main__":
    main()
