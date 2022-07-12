"""
Sheeba Samuel
Heinz-Nixdorf Chair for Distributed Information Systems
Friedrich Schiller University Jena, Germany
Email: sheeba.samuel@uni-jena.de
Website: https://github.com/Sheeba-Samuel
"""
import sys
sys.path.insert(0, '../archaeology')
sys.path.insert(0, '../analysis')

import pandas as pd
from db import connect, Repository, Notebook, Query, NotebookModule, Execution, Cell
from utils import human_readable_duration, vprint
from consts import R_STATUSES
from analysis_helpers import display_counts, describe_processed
from analysis_helpers import distribution_with_boxplot, savefig, boxplot_distribution
from analysis_helpers import var, relative_var, calculate_auto, close_fig


import matplotlib
from matplotlib import pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from math import floor

from collections import Counter, defaultdict
import json


execution_analysis_info = {}

def get_raw_executions():
    with connect() as session:

        query = (
            "SELECT id, repository_id, notebook_id, mode, reason, msg, diff, cell, count, diff_count, timeout, duration, processed, skip "
            "FROM executions "
        )
        raw_executions = pd.read_sql(query, session.connection())
        return raw_executions

def get_raw_executions_copy():
    raw_executions = get_raw_executions()
    return raw_executions[raw_executions['skip'] == 0].copy()

def get_total_notebooks():
    with connect() as session:
        query = (
            "SELECT count(id) "
            "FROM notebooks "
            "WHERE NOT (kernel = 'no-kernel' AND nbformat = '0') "
            "AND total_cells != 0"
        )

        result = session.execute(query)
        total_notebooks = result.scalar()
        execution_analysis_info['total_notebooks'] = total_notebooks
        return total_notebooks

def get_notebooks_with_setup_py():
    with connect() as session:
        query = (
            "SELECT id as notebook_id "
            "FROM notebooks "
            "WHERE repository_id IN ( "
                "SELECT id FROM repositories "
                "WHERE setups_count > 0 "
            ")"
        )

        notebooks_with_setup_py =  pd.read_sql(query, session.connection())
        execution_analysis_info['notebooks_with_setup_py'] = len(notebooks_with_setup_py)
        return notebooks_with_setup_py

def get_notebooks_with_requirement_txt():
    with connect() as session:
        query = (
            "SELECT id as notebook_id "
            "FROM notebooks "
            "WHERE repository_id IN ( "
                "SELECT id FROM repositories "
                "WHERE requirements_count > 0 "
            ")"
        )

        notebooks_with_requirement_txt =  pd.read_sql(query, session.connection())
        execution_analysis_info['notebooks_with_requirement_txt'] = len(notebooks_with_requirement_txt)
        return notebooks_with_requirement_txt

def get_notebooks_with_pipfile():
    with connect() as session:
        query = (
            "SELECT id as notebook_id "
            "FROM notebooks "
            "WHERE repository_id IN ( "
                "SELECT id FROM repositories "
                "WHERE pipfiles_count > 0 "
                "OR pipfile_locks_count > 0 "
            ")"
        )

        notebooks_with_pipfile =  pd.read_sql(query, session.connection())
        execution_analysis_info['notebooks_with_pipfile'] = len(notebooks_with_pipfile)
        return notebooks_with_pipfile


def get_executions_with_skipped():
    executions = get_raw_executions_copy()
    executions_with_skipped = executions
    print(len(executions_with_skipped))
    return executions_with_skipped


def get_executions():
    executions = get_raw_executions_copy()
    executions = executions[executions["reason"] != "<Skipping notebook>"]
    return executions

def get_attempted_executions_total():
    total_notebooks = get_total_notebooks()
    executions = get_executions()
    attempted_executions_total = len(executions)
    print('Executions:', relative_var('attempted_executions', attempted_executions_total, total_notebooks))
    execution_analysis_info['attempted_executions'] = relative_var('attempted_executions', attempted_executions_total, total_notebooks)
    return attempted_executions_total


def get_skip_reason():
    executions_with_skipped = get_executions_with_skipped()
    e = executions_with_skipped
    e = e[e["reason"] == "<Skipping notebook>"]
    execution_analysis_info['executions_with_skipped'] = len(e[(
        (e["msg"] == "Repeated cell numbers")
        | (e["msg"] == "No numbered cells")
    )])
    return len(e[(
        (e["msg"] == "Repeated cell numbers")
        | (e["msg"] == "No numbered cells")
    )])


def get_attempted_installations():
    executions = get_executions()
    attempted_executions_total = get_attempted_executions_total()
    execution_analysis_info['attempted_installations'] = relative_var( "attempted_installations", len(executions[executions["mode"] == 3]), attempted_executions_total)
    return relative_var( "attempted_installations", len(executions[executions["mode"] == 3]), attempted_executions_total)


def get_failed_installations():
    executions = get_executions()
    attempted_executions_total = get_attempted_executions_total()
    failed_installations = executions[executions["processed"] == 0]
    total = len(failed_installations)    
    execution_analysis_info['failed_installations'] = relative_var("failed_installations", total, attempted_executions_total)
    print("failed_installations:{}".format(relative_var("failed_installations", total, attempted_executions_total)))
    return failed_installations


def interpret_msg(value):

    it = iter(value)
    first = next(it) + next(it)
    result = {
        "setup.py": 0,
        "requirements.txt": 0,
        "Pipfile": 0,
        "Pipfile.lock": 0,
        "setup.py-output": "",
        "requirements.txt-output": "",
        "Pipfile-output": "",
        "Pipfile.lock-output": "",
        "setup.py-error": "",
        "requirements.txt-error": "",
        "Pipfile-error": "",
        "Pipfile.lock-error": "",
    }
    if first != "\\x":
        return pd.Series(result)
    values = ''.join([chr(int(a + b, base=16)) for a, b in zip(it, it)]).split("##<<>>##")
    ok = values.pop(0).strip("Ok: ").strip().split(", ")
    for v in ok:
        result[v] = 1

    failed = values.pop(0).strip("Failed: ").strip().split(", ")
    for v in failed:
        result[v] = -1
        temp = values.pop(0).split("##<>##")
        output = temp.pop(1).strip().strip("Output:").strip()
        error = temp.pop(1).strip().strip("Error:").strip()
        result[v + "-output"] = output
        result[v + "-error"] = error

    return pd.Series(result)

def get_df():
    failed_installations = get_failed_installations()
    df = failed_installations["msg"].apply(interpret_msg)
    return df

def get_failed_setup_py():
    executions = get_executions()
    df = get_df()
    notebooks_with_setup_py = get_notebooks_with_setup_py()
    total = len(executions[executions["notebook_id"].isin(
        set(notebooks_with_setup_py["notebook_id"].tolist())
    )])
    failed = len(df[df["setup.py"] == -1])
    execution_analysis_info['failed_setup_py'] = relative_var("failed_setup_py", failed, total)
    return relative_var("failed_setup_py", failed, total)


def get_failed_requirements_txt():
    executions = get_executions()
    df = get_df()
    notebooks_with_requirement_txt = get_notebooks_with_requirement_txt()
    total = len(executions[executions["notebook_id"].isin(
        set(notebooks_with_requirement_txt["notebook_id"].tolist())
    )])
    failed = len(df[df["requirements.txt"] == -1])
    execution_analysis_info['failed_requirements_txt'] = relative_var("failed_requirements_txt", failed, total)
    return relative_var("failed_requirements_txt", failed, total)


def get_failed_pipfile():
    executions = get_executions()
    df = get_df()
    notebooks_with_pipfile = get_notebooks_with_pipfile()
    total = len(executions[executions["notebook_id"].isin(
        set(notebooks_with_pipfile["notebook_id"].tolist())
    )])
    failed = len(df[(df["Pipfile"] == -1) | (df["Pipfile.lock"] == -1)])
    return relative_var("failed_pipfile", failed, total)


def get_failure_reasons():
    failure_reasons = Counter()
    return failure_reasons


def get_ret_df():
    ndf = get_df()
    return ndf


output_messages = {

    "NameError: ": "malformed",
    "AttributeError: ": "malformed",
    'IndexError: ': "malformed",
    'TypeError: ': "malformed",
    "IOError: ": "malformed",
    "EOFError:": "malformed",
    "RuntimeError: ": "malformed",
    "ValueError: ": "malformed",
    "IndentationError: ": "malformed",
    "SyntaxError: ": "malformed",
    "option --single-version-externally-managed not recognize": "malformed",
    "USAGE IS setup.py": "malformed",
    "Usage: setup.py install": "malformed",
    "'extras_require' must be a dictionary whose values are strings or lists of strings containing valid project/version requirement specifiers": "malformed",
    "should either be a path to a local project or a VCS url beginning with svn": "malformed",
    'Invalid distribution name or version syntax': "malformed",
    "EntryPoint must be in": "malformed",
    "invalid choice: 'egg_info'": "malformed",
    "Invalid requirement, parse error at": "malformed",
    "Could not parse object": "malformed",
    "Please set --dir": "malformed",
    "was unable to detect version for": "malformed",
    "error: unknown file type '.so'": "malformed",
    "You probably meant to install and run": "malformed",
    "Permission denied: '/usr/local/share/jupyter'": "malformed",

    "OSError: ": "system",
    "Conda is only supported in": "system",
    "Only supported on a Pynq-Z1 Board": "system",
    "Could not detect if running on the Raspberry Pi or Beaglebone Black": "system",
    "This distribution is only supported on MacOSX": "system",

    "NotFoundError: ": "missing",
    "IsADirectoryError: ": "missing",
    "tarfile.ReadError:": "missing",
    "/bin/sh: 1: pkg-config: not found": "missing",
    "No such file or directory": "missing",
    "does not exist": "missing",
    "RuntimeError: Cannot find the files": "missing",
    "did not match any file": "missing",
    "does not name an existing file": "missing",
    "\\[Errno 21\\] Is a directory": "missing",
    "Couldn't find a setup script in": "missing",


    'HTTPError: ': "access-error",
    "DistributionNotFound: ": "access-error",
    "Could not read from remote repository": "access-error",
    "Server does not allow request for unadvertised object": "access-error",
    "fatal: could not read Username": "access-error",
    "Failed to connect to": "access-error",



    #"No module named": "python-dependency",
    'ImportError: ': "python-dependency",
    "requires numpy and cython": "python-dependency",
    "This package requires NumPy": "python-dependency",
    "You must install numpy": "python-dependency",
    'Install requires numpy': "python-dependency",
    "Please install numpy": "python-dependency",
    'you will need numpy': "python-dependency",
    "numpy is required during installation": "python-dependency",
    "Need numpy for installation": "python-dependency",
    "Numpy and its headers are required": "python-dependency",
    'NumPy version is lower than needed': "python-dependency",
    "You must have Cython": "python-dependency",
    "No module named 'distutils.errors'": "python-dependency",
    "Please install the `scikit-image` package": "python-dependency",
    "install requires: 'numpy'.": "python-dependency",
    "Please install the corresponding packages": "python-dependency",
    "must be available and importable as a prerequisite": "python-dependency",
    "This package currently requires numpy": "python-dependency",
    "make sure you have Cython": "python-dependency",
    "Cython is required": "python-dependency",
    "Cython must be installed": "python-dependency",
    "You need Cython": "python-dependency",
    "Please upgrade to a newer Cython version": "python-dependency",
    "requires a version of NumPy, even for setup": "python-dependency",

    "subprocess.CalledProcessError: ": "external-dependency",
    "You need to install postgresql-server-dev": "external-dependency",
    "CompileError: command 'gcc' failed with exit status": "external-dependency",
    "Cannot find XGBoost Libarary in the candicate path": "external-dependency",
    "The following required packages can not be built:": "external-dependency",
    "OSError: Could not find library geos_c or load any of its variants": "external-dependency",
    "no acceptable C compiler found in": "external-dependency",
    "mysql_config not found": "external-dependency",
    "Proj4 4.9.0 must be installed.": "external-dependency",
    "gcc: command not found": "external-dependency",
    "which is normally used to compile C extensions": "external-dependency",
    "command 'gcc' failed with exit status": "external-dependency",
    "Error: Tried to guess R's HOME but no command 'R' in the PATH": "external-dependency",
    'HOME but no command \(R\) in the PATH': "external-dependency",
    "Please install GCC": "external-dependency",
    'Could not find "cmake" executable': "external-dependency",
    'npm is required': "external-dependency",
    'C library was not found.': "external-dependency",
    'is required to install': "external-dependency",
    'Cannot find XGBoost Library in the candidate path': "external-dependency",
    "No Java/JDK could be found.": "external-dependency",
    "is not supported on Python 3.": "external-dependency",
    "No working compiler found": "external-dependency",
    "You must have the Ogg Python bindings": "external-dependency",
    "no Fortran compiler found": "external-dependency",
    "Ops! We need the": "external-dependency",
    "Could not find a local HDF5 installation": "external-dependency",
    "no R command in the PATH": "external-dependency",
    "command 'g\+\+' failed with exit status": "external-dependency",
    "Can't find a local Berkeley DB installation.": "external-dependency",
    "requires the xclip": "external-dependency",
    "Please make sure a development version of SDL": "external-dependency",
    "Cannot find boost_python library": "external-dependency",
    "internal compiler error": "external-dependency",
    "Please install swig": "external-dependency",
    "error: command 'swig' failed with exit status 1": "external-dependency",
    "Could not find cmake executable": "external-dependency",
    "must set CPPTRAJHOME if there is no cpptraj in current folder": "external-dependency",
    "g\\+\\+: not found": "external-dependency",
    "g\\+\\+: command not found": "external-dependency",
    "Make sure you have either g\\+\\+": "external-dependency",
    "You need to run .* first.": "external-dependency",
    "Please add the directory containing .* to the PATH": "external-dependency",
    "no C\+\+ compiler found": "external-dependency",
    "finding javahome on linux": "external-dependency",

    "This backport is for Python 2.7 only.": "python-version",
    "VersionConflict: ": "python-version",
    'This backport is for Python 2.x only': "python-version",
    "IPython 6.0\+ does not support Python": "python-version",
    "is no longer written for Python 2.": "python-version",
    "is no longer supporting Python < 3": "python-version",
    "python3 repository on python2": "python-version",
    "requires at least Python 3": "python-version",
    "Python 3 required": "python-version",
    "is only supported by Python 3": "python-version",
    "only works on python 2": "python-version",
    "Python version >= 3 required": "python-version",
    "Sorry, Python < .* is not supported": "python-version",
    "does not work on any version of Python 3": "python-version",
    "can only be used with Python 3": "python-version",

    "distutils.errors.CompileError: command 'cc' failed with exit status 1": "unknown",
    "notebookarchaeology": "unknown",
}

error_messages = {

    "is not a valid operator. Did you mean": "malformed",
    "Double requirement given: ": "malformed",
    "/bin/sh: 1: Syntax error: ": "malformed",
    "Invalid requirement:": "malformed",
    "is not installable.": "malformed",
    "Could not detect requirement name": "malformed",
    "no such option: ": "malformed",
    "UnicodeEncodeError: ": "malformed",
    "TypeError: ": "malformed",
    "ValueError: ": "malformed",
    "UnicodeDecodeError: ": "malformed",
    "TomlDecodeError: ": "malformed",
    "should either be a path to a local project or a VCS url beginning with svn": "malformed",
    "This will just run build.py": "malformed",
    "ImportError: ": "malformed",
    "There are incompatible versions in the resolved dependencies.": "malformed",


    "Could not find a version that satisfies the requirement": "missing",
     "It looks like a path. File": "missing",
    "Could not open requirements file": "missing",
    "No files/directories in ": "missing",
    "does not exist": "missing",
    "tarfile.ReadError: ": "missing",
    "No such file or directory": "missing",
    "Files/directories not found in": "missing",


    "It is a distutils installed project and thus we cannot accurately determine which files belong to it which would lead to only a partial uninstall.": "system",
    "is not a supported wheel on this platform.": "system",
    " which is incompatible.": "system",
    "EnvironmentError: ": "system",

    "HTTP error 404 while getting": "access-error",
    "Could not read from remote repository": "access-error",
    "Was https://github.com/.* reachable?": "access-error",
    "Was https://pypi.org/ reachable?": "access-error",

    "requires lxml, which is not installed.": "external-dependency",
    "Cannot find command 'hg'": "external-dependency",
    "Python .* was not found on your system": "external-dependency",

    "but the running Python is 2.7": "python-version",
    "prml requires Python '>=.*' but the running": "python-version",
    "requires Python '>=.*' but the running": "python-version",

    "notebookarchaeology": "unknown",
    "pipenv.patched.notpip._internal.exceptions.InstallationError: Command \"python setup.py egg_info\"": "unknown",
}


def get_ndf_failure_reasons():
    ndf = get_ret_df()
    global failure_reasons
    failure_reasons = get_failure_reasons()

    for msg, category in output_messages.items():
        cond = (
            ndf["setup.py-output"].str.contains(msg)
            | ndf["requirements.txt-output"].str.contains(msg)
            | ndf["Pipfile-output"].str.contains(msg)
            | ndf["Pipfile.lock-output"].str.contains(msg)
        )
        failure_reasons[category] += len(ndf[cond])
        ndf = ndf[~cond]


    for msg, category in error_messages.items():
        cond = (
            ndf["setup.py-error"].str.contains(msg)
            | ndf["requirements.txt-error"].str.contains(msg)
            | ndf["Pipfile-error"].str.contains(msg)
            | ndf["Pipfile.lock-error"].str.contains(msg)
        )
        failure_reasons[category] += len(ndf[cond])
        ndf = ndf[~cond]

    cond = (
        (ndf["setup.py"] == 0)
        & (ndf["requirements.txt"] == 0)
        & (ndf["Pipfile"] == 0)
        & (ndf["Pipfile.lock"] == 0)
    )
    failure_reasons["unknown"] += len(ndf[cond])
    ndf = ndf[~cond]
    return failure_reasons

def get_total_failed_installations():
    failed_installations = get_failed_installations()
    total_failed_installations = len(failed_installations)
    execution_analysis_info['total_failed_installations'] = total_failed_installations
    return total_failed_installations


def get_repro_install_missing():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_missing'] = relative_var("repro_install_missing", failure_reasons["missing"] + failure_reasons["access-error"], total_failed_installations)
    return relative_var("repro_install_missing", failure_reasons["missing"] + failure_reasons["access-error"], total_failed_installations)


def get_repro_install_malformed():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_malformed'] = relative_var("repro_install_malformed", failure_reasons["malformed"], total_failed_installations)
    return relative_var("repro_install_malformed", failure_reasons["malformed"], total_failed_installations)


def get_repro_install_python_dependency():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_python_dependency'] = relative_var("repro_install_python_dependency", failure_reasons["python-dependency"], total_failed_installations)
    return relative_var("repro_install_python_dependency", failure_reasons["python-dependency"], total_failed_installations)


def get_repro_install_external_dependency():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_external_dependency'] = relative_var("repro_install_external_dependency", failure_reasons["external-dependency"], total_failed_installations)
    return relative_var("repro_install_external_dependency", failure_reasons["external-dependency"], total_failed_installations)


def get_repro_install_system():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_system'] = relative_var("repro_install_system", failure_reasons["system"], total_failed_installations)
    return relative_var("repro_install_system", failure_reasons["system"], total_failed_installations)


def get_repro_install_python_version():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_python_version'] = relative_var("repro_install_python_version", failure_reasons["python-version"], total_failed_installations)
    return relative_var("repro_install_python_version", failure_reasons["python-version"], total_failed_installations)


def get_repro_install_unknown():
    failure_reasons = get_ndf_failure_reasons()
    total_failed_installations = get_total_failed_installations()
    execution_analysis_info['repro_install_unknown'] = relative_var("repro_install_unknown", failure_reasons["unknown"], total_failed_installations)
    return relative_var("repro_install_unknown", failure_reasons["unknown"], total_failed_installations)


def get_installed_dependencies():
    executions = get_executions()
    installed_dependencies = executions[
        (executions["processed"] > 0)
        & (executions["mode"] == 3)
    ]
    return installed_dependencies


def get_total_installed_dependencies():
    installed_dependencies = get_installed_dependencies()
    attempted_executions_total = get_attempted_executions_total()
    total_installed_dependencies = len(installed_dependencies)
    print(relative_var("installed_dependencies", total_installed_dependencies, attempted_executions_total))
    execution_analysis_info['total_installed_dependencies'] = relative_var("installed_dependencies", total_installed_dependencies, attempted_executions_total)
    return total_installed_dependencies


def get_non_declared_dependencies():
    executions = get_executions()
    non_declared_dependencies = executions[
        (executions["processed"] > 0)
        & (executions["mode"] == 5)
    ]
    return non_declared_dependencies


def get_total_non_declared_dependencies():
    non_declared_dependencies = get_non_declared_dependencies()
    attempted_executions_total = get_attempted_executions_total()
    total_non_declared_dependencies = len(non_declared_dependencies)
    print(relative_var("non_declared_dependencies", total_non_declared_dependencies, attempted_executions_total))
    execution_analysis_info['total_non_declared_dependencies'] = relative_var("non_declared_dependencies", total_non_declared_dependencies, attempted_executions_total)
    return total_non_declared_dependencies


def get_combined_dependencies():
    installed_dependencies = get_installed_dependencies()
    non_declared_dependencies = get_non_declared_dependencies()
    combined = pd.concat([installed_dependencies, non_declared_dependencies])
    return combined


def get_repro_executed():
    combined = get_combined_dependencies()
    attempted_executions_total = get_attempted_executions_total()
    total_combined = len(combined)
    print(relative_var("repro_executed", total_combined, attempted_executions_total))
    execution_analysis_info['repro_executed'] = relative_var("repro_executed", total_combined, attempted_executions_total)
    return total_combined


def get_repro_excluded_nbformat():
    combined = get_combined_dependencies()
    total_combined = get_repro_executed()
    total = len(combined[combined["reason"] == "<Read notebook error>"])
    execution_analysis_info['repro_excluded_nbformat'] = relative_var("repro_excluded_nbformat", total, total_combined)
    return relative_var("repro_excluded_nbformat", total, total_combined)


def get_repro_exceptions():
    combined = get_combined_dependencies()
    total_combined = get_repro_executed()
    with_exceptions = combined[combined["processed"] & 4 == 4]
    total_exceptions = len(with_exceptions)
    print(relative_var("repro_exceptions", total_exceptions, total_combined))
    execution_analysis_info['repro_exceptions'] = relative_var("repro_exceptions", total_exceptions, total_combined)
    return with_exceptions


def get_combined():
    combined = get_combined_dependencies()
    combined["new_reason"] = combined["reason"]
    return combined


def get_combined_reason():
    combined = get_combined()
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("IOError"), "new_reason"] = "IOError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("OSError"), "new_reason"] = "OSError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("OperationalError"), "new_reason"] = "OperationalError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("TypeError"), "new_reason"] = "TypeError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("ValueError"), "new_reason"] = "ValueError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("HTTPError"), "new_reason"] = "HTTPError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("ImportError"), "new_reason"] = "ImportError"
    combined.loc[~combined["reason"].isna() & combined["reason"].str.contains("FileNotFoundError"), "new_reason"] = "FileNotFoundError"
    return combined


def get_repro_missing_dependencies():
    combined = get_combined_reason()
    attempted_executions_total = get_attempted_executions_total()
    execution_analysis_info['repro_missing_dependencies'] = relative_var("repro_missing_dependencies", len(combined[
        (combined["new_reason"] == "ImportError")
        | (combined["new_reason"] == "ModuleNotFoundError")
    ]), attempted_executions_total)

    return relative_var("repro_missing_dependencies", len(combined[
        (combined["new_reason"] == "ImportError")
        | (combined["new_reason"] == "ModuleNotFoundError")
    ]), attempted_executions_total)


def get_repro_name_error():
    combined = get_combined_reason()
    attempted_executions_total = get_attempted_executions_total()
    execution_analysis_info['repro_name_error'] = relative_var("repro_name_error", len(combined[
        (combined["new_reason"] == "NameError")
    ]), attempted_executions_total)

    return relative_var("repro_name_error", len(combined[
        (combined["new_reason"] == "NameError")
    ]), attempted_executions_total)


def get_repro_missing_files():
    combined = get_combined_reason()
    attempted_executions_total = get_attempted_executions_total()
    execution_analysis_info['repro_missing_files'] = relative_var("repro_missing_files", len(combined[
        (combined["new_reason"] == "FileNotFoundError")
        | (combined["new_reason"] == "IOError")
    ]), attempted_executions_total)

    return relative_var("repro_missing_files", len(combined[
        (combined["new_reason"] == "FileNotFoundError")
        | (combined["new_reason"] == "IOError")
    ]), attempted_executions_total)


def get_with_dependencies_exceptions():
    combined = get_combined_reason()    
    with_dependencies_exceptions = combined[
        (combined["new_reason"] == "ImportError")
        | (combined["new_reason"] == "ModuleNotFoundError")
    ]
    total_with_dependencies_exceptions = len(with_dependencies_exceptions)
    print(total_with_dependencies_exceptions)
    execution_analysis_info['total_with_dependencies_exceptions'] = total_with_dependencies_exceptions
    return with_dependencies_exceptions


def get_module_exception_in_installed():
    with_dependencies_exceptions = get_with_dependencies_exceptions()
    total_installed_dependencies = get_total_installed_dependencies()
    installed_with_dependencies_exceptions = with_dependencies_exceptions[
        with_dependencies_exceptions["mode"] == 3
    ]
    total = len(installed_with_dependencies_exceptions)
    execution_analysis_info['module_exception_in_installed'] = relative_var("module_exception_in_installed", total, total_installed_dependencies)
    return relative_var("module_exception_in_installed", total, total_installed_dependencies)


def get_module_exception_in_non_installed():
    with_dependencies_exceptions = get_with_dependencies_exceptions()
    total_non_declared_dependencies = get_total_non_declared_dependencies()
    non_installed_with_dependencies_exceptions = with_dependencies_exceptions[
        with_dependencies_exceptions["mode"] == 5
    ]
    total = len(non_installed_with_dependencies_exceptions)
    execution_analysis_info['module_exception_in_non_installed'] = relative_var("module_exception_in_non_installed", total, total_non_declared_dependencies)
    return relative_var("module_exception_in_non_installed", total, total_non_declared_dependencies)


def get_repro_timeout():
    combined = get_combined_reason()
    attempted_executions_total = get_attempted_executions_total()
    total = len(combined[combined["processed"] & 8 == 8])
    execution_analysis_info['repro_timeout'] = relative_var("repro_timeout", total, attempted_executions_total)
    return relative_var("repro_timeout", total, attempted_executions_total)


def get_repro_finished():
    executions = get_executions()
    attempted_executions_total = get_attempted_executions_total()
    finished = executions[
        np.bitwise_and(executions['processed'], 32 + 8 + 4) == 32
    ]
    total = len(finished)
    print(relative_var("repro_finished", total, attempted_executions_total))
    execution_analysis_info['repro_finished'] = relative_var("repro_finished", total, attempted_executions_total)
    return finished


def get_repro_distinct():
    finished = get_repro_finished()
    attempted_executions_total = get_attempted_executions_total()
    distinct_value = finished[
        np.bitwise_and(finished['processed'], 16) == 0
    ]
    total = len(distinct_value)
    print(relative_var("repro_distinct", total, attempted_executions_total))
    execution_analysis_info['repro_distinct'] = relative_var("repro_distinct", total, attempted_executions_total)
    return distinct_value


def get_repro_same():
    finished = get_repro_finished()
    attempted_executions_total = get_attempted_executions_total()
    same_value = finished[
        np.bitwise_and(finished['processed'], 16) == 16
    ]
    total = len(same_value)
    print(relative_var("repro_same", total, attempted_executions_total))
    execution_analysis_info['repro_same'] = relative_var("repro_same", total, attempted_executions_total)
    return same_value