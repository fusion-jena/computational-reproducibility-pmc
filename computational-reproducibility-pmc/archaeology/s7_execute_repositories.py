"""Load notebook and cells"""
import argparse
import os
import sys
import shutil
import subprocess
import asyncio


from datetime import datetime
from subprocess import Popen, PIPE
from math import ceil
from itertools import groupby
from asyncio.subprocess import PIPE as APIPE

from sqlalchemy.sql.expression import func


import consts
import config
from db import Notebook, Repository, Execution, connect
from utils import vprint, StatusLogger, best_match, version_string_to_list
from utils import mount_umount, check_exit, savepid
from load_repository import load_repository
from execution_rules import DEPENDENCY_RULES, EXECUTION_RULES, mode_rules
from execution_rules import EXECUTION_MODE, exec_to_num


@asyncio.coroutine
def read_stream_and_display(stream, display):
    """Read from stream line by line until EOF, display, and capture the lines.

    """
    output = []
    while True:
        line = yield from stream.readline()
        if not line:
            break
        output.append(line)
        display(line) # assume it doesn't block
    return b''.join(output)


@asyncio.coroutine
def read_and_store(cmd, out, err, **kwargs):
    """Capture cmd's stdout, stderr while displaying them as they arrive
    (line by line).

    """
    # start process
    process = yield from asyncio.create_subprocess_shell(cmd,
            stdout=APIPE, stderr=APIPE, **kwargs)

    # read child's stdout/stderr concurrently (capture and display)
    try:
        stdout, stderr = yield from asyncio.gather(
            read_stream_and_display(process.stdout, out.write),
            read_stream_and_display(process.stderr, err.write))
    except Exception:
        process.kill()
        raise
    finally:
        # wait for the process to exit
        rc = yield from process.wait()
    return rc, stdout, stderr


def run_async_process(cmd, out, err, **kwargs):
    if os.name == 'nt':
        loop = asyncio.ProactorEventLoop() # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()
    rc, odata, edata = loop.run_until_complete(read_and_store(cmd, out, err, **kwargs))
    return rc, odata, edata


def notebook_exec_mode(mode_def, notebook, repository):
    if mode_def is not None:
        return mode_def
    with_dependency = (
        repository.setups_count > 0
        or repository.requirements_count > 0
        or repository.pipfiles_count > 0
        or repository.pipfile_locks_count > 0
    )
    with_execution = notebook.max_execution_count != -1
    tup = (not with_dependency, with_dependency, with_execution)
    tup_str = "0b{}".format("".join(str(int(b)) for b in tup))
    num = int(tup_str, 2)
    return EXECUTION_MODE[num]


def extract_repository(session, repository, skip_extract, out, err):
    cwd = config.EXECUTION_DIR
    if skip_extract:
        cwd = (config.EXECUTION_DIR / repository.hash_dir2)
        if not cwd.exists():
            return (
                False, cwd,
                "Failed to use extracted dir. It does not exists"
            )
    else:
        try:
            if config.EXECUTION_DIR.exists():
                shutil.rmtree(str(config.EXECUTION_DIR), ignore_errors=True)
            if repository.zip_path.exists():
                config.EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
                cmd = repository.uncompress(config.EXECUTION_DIR, return_cmd=True)
                vprint(3, "Extract: {}".format(repository.zip_path))
                vprint(3, "Command: {}".format(" ".join(cmd)))
                uncompressed = subprocess.call(cmd, stdout=out, stderr=err)
                if uncompressed != 0:
                    repository.processed |= consts.R_COMPRESS_ERROR
                    session.commit()
                    return (
                        False, cwd,
                        "Extraction failed with code {}".format(uncompressed),
                    )
            elif repository.path.exists():
                new_path = (config.EXECUTION_DIR / repository.hash_dir2)
                new_path.mkdir(parents=True, exist_ok=True)
                cmd = "tar cf - * | (cd {} ; tar xf - )".format(str(new_path))
                vprint(3, "Copy: {}".format(repository.path))
                vprint(3, "Command: {}".format(cmd))
                copied = subprocess.call(
                    cmd, shell=True, stdout=out, stderr=err, cwd=str(repository.path)
                )
                if copied != 0:
                    repository.processed |= consts.R_COMPRESS_ERROR
                    session.commit()
                    return (
                        False, cwd,
                        "Copying failed with code {}".format(copied),
                    )
            else:
                repository.processed |= consts.R_UNAVAILABLE_FILES
                session.add(repository)
                session.commit()
                return (
                    False, cwd,
                    "Failed to find repository"
                )
            files = [sub for sub in cwd.glob("*")]
            sub_cwd = cwd / repository.hash_dir2
            if files == [sub_cwd]:
                cwd = sub_cwd
            else:
                return (
                    False, cwd,
                    "Execution dir is full"
                )

        except Exception as e:
            repository.processed |= consts.R_COMPRESS_ERROR
            session.add(repository)
            session.commit()
            return (
                False, cwd,
                "Copy failed with exception {}".format(e),
            )

    commit = repository.get_commit(cwd)
    if commit != repository.commit:
        repository.processed |= consts.R_COMMIT_MISMATCH
        session.add(repository)
        return (
            False, cwd,
            "Commit mismatch. Expected {}. Found {}".format(
                repository.commit, commit
            ),
        )
    return (
        True, cwd,
        "Repository set to {}".format(cwd)
    )


def install_setups(cwd, names, env, out, err):
    for name in names:
        if not name:
            continue
        path = (cwd / name).parents[0]
        vprint(3, "Installing {}".format(path))
        status, outdata, errdata = run_async_process(
            ". {}/etc/profile.d/conda.sh "
            "&& conda activate {} "
            "&& pip install -e '{}'"
            .format(
                config.ANACONDA_PATH, env,
                str(path).replace("'", "'\\''"),
            ),
            out, err
        )
        data = b"##<>##\nOutput:\n" + outdata + b"\n##<>##Error:\n" + errdata
        if status != 0:
            return (False, data)
    return (True, b"")


def install_requirements(cwd, names, env, out, err):
    for name in names:
        if not name:
            continue
        path = (cwd / name)
        vprint(3, "Installing {}".format(path))
        status, outdata, errdata = run_async_process(
            ". {}/etc/profile.d/conda.sh "
            "&& conda activate {} "
            "&& pip install -r '{}'"
            .format(
                config.ANACONDA_PATH, env,
                str(path).replace("'", "'\\''"),
            ),
            out, err
        )
        data = b"##<>##\nOutput:\n" + outdata + b"\n##<>##Error:\n" + errdata
        if status != 0:
            return (False, data)
    return (True, b"")


def install_pipfiles(cwd, names, env, out, err):
    for name in names:
        if not name:
            continue
        path = (cwd / name).parents[0]
        vprint(3, "Converting to requirements.txt: {}".format(path))
        requirements_txt = cwd.parents[0] / "requirements.txt"
        with open(str(requirements_txt), "wb") as outf:
            status, outdata, errdata = run_async_process(
                ". {}/etc/profile.d/conda.sh "
                "&& conda activate {} "
                "&& pipenv lock -r"
                .format(config.ANACONDA_PATH, env),
                outf, err, cwd=str(path)
            )
            data = b"##<>##\nOutput:\n" + outdata + b"\n##<>##Error:\n" + errdata
            if status != 0:
                return (False, data)
        result, data = install_requirements(
            requirements_txt.parents[0],
            ["requirements.txt"],
            env, out, err
        )
        if not result:
            return (False, data)
    return (True, b"")


def execute_repository(
    status, session, repository, notebooks_iter, mode, env, skip_extract,
    notebook_exec_mode, dry_run, out, err,
):
    vprint(1, "Executing notebooks from {}".format(repository))
    if repository.processed & consts.R_UNAVAILABLE_FILES:
        repository.processed -= consts.R_UNAVAILABLE_FILES
        session.add(repository)
    if repository.processed & consts.R_COMPRESS_ERROR:
        repository.processed -= consts.R_COMPRESS_ERROR
        session.add(repository)

    cwd = config.EXECUTION_DIR / repository.hash_dir2
    vprint(2, "{}Preparing repository directory".format(
        "[DRY RUN] " if dry_run >= 3 else "",
    ))
    if dry_run < 3:
        with mount_umount(out, err):
            success, cwd, msg = extract_repository(
                session, repository, skip_extract, out, err
            )
            vprint(3, msg)
            if not success:
                return "Failed to extract repository"

    if mode.dependencies:
        msg = install_repository_dependencies(
            status, session, cwd, repository, notebooks_iter, mode, env,
            notebook_exec_mode, dry_run, out, err
        )
        if msg is not None:
            return msg

    return execute_notebooks(
        status, session, cwd, notebooks_iter, mode, notebook_exec_mode, dry_run
    )


def install_repository_dependencies(
    status, session, cwd, repository, notebooks_iter, mode, env,
    notebook_exec_mode, dry_run, out, err
):
    vprint(2, "{}Installing repository dependencies".format(
        "[DRY RUN] " if dry_run >= 2 else ""
    ))
    if dry_run >= 2:
        return None

    install_options = [
        ("setup.py", install_setups, repository.setup_names),
        ("requirements.txt", install_requirements, repository.requirement_names),
        ("Pipfile", install_pipfiles, repository.pipfile_names),
        ("Pipfile.lock", install_pipfiles, repository.pipfile_lock_names),
    ]
    installed = True
    data_ok_list = []
    data_failed_list = []
    data_failed = b""
    for spec, func, names in install_options:
        success, data = func(cwd, names, "work", out, err)
        installed = installed and success
        spec_bytes = spec.encode("utf-8")
        if success:
            data_ok_list.append(spec_bytes)
        else:
            data_failed += b"\n##<<>>##" + spec_bytes + b":\n" + data
            data_failed_list.append(spec_bytes)
    if not installed:
        reason = "<Install Dependency Error>"
        cause = b"Ok: " + b", ".join(data_ok_list)
        cause += b"\n##<<>>##Failed: " + b", ".join(data_failed_list)
        cause += data_failed
        for notebook, repository in notebooks_iter:
            status.skipped += 1
            status.report()
            nmode = notebook_exec_mode(mode, notebook, repository)
            mode_num = exec_to_num(*nmode)
            execution = session.query(Execution).filter(
                Execution.notebook_id == notebook.id,
                Execution.mode == mode_num,
            ).first()
            if execution:
                if execution.processed & consts.E_EXECUTED:
                    continue
                execution.reason = reason
                execution.msg = cause
                execution.cell = None
                execution.count = None
                execution.diff = None
                execution.duration = None
                execution.timeout = None
                execution.diff_count = None
                execution.processed = consts.E_CREATED
            else:
                execution = Execution(
                    notebook_id=notebook.id, mode=mode_num,
                    reason=reason, msg=cause,
                    processed=consts.E_CREATED,
                    repository_id=notebook.repository_id,
                )
            session.add(execution)
            notebook.processed |= nmode.processed
            session.add(notebook)
        session.commit()
        return "Failed to install {}".format(
            b", ".join(data_failed_list).decode("utf-8")
        )
    return None

#status, session, repository, notebooks_iter, mode, env, dry_run, out, err,
def execute_notebooks(
    status, session, cwd, notebooks_iter, mode, notebook_exec_mode, dry_run
):
    notebooks_iter = list(notebooks_iter)
    vprint(2, "{}Running {} notebooks".format(
        "[DRY RUN] " if dry_run >= 1 else "",
        len(notebooks_iter)
    ))
    if dry_run >= 1:
        return "done"

    for notebook, repository in notebooks_iter:
        status.count += 1
        status.report()
        nmode = notebook_exec_mode(mode, notebook, repository)
        if notebook.processed & (nmode.processed * 2):
            notebook.processed -= nmode.processed * 2

        mode_num = exec_to_num(*nmode)
        vprint(2, "Running notebook {}".format(notebook))
        pstatus = subprocess.call(
            '. {}/etc/profile.d/conda.sh '
            '&& conda activate {} '
            "&& python run_notebook.py -n {} -p '{}' -m {}"
            .format(
                config.ANACONDA_PATH, "work",
                notebook.id,
                str(cwd / notebook.name).replace("'", "'\\''"),
                mode_num
            ), shell=True,
        )
        error = pstatus != 0
        processed = nmode.processed * (2 if error else 1)
        vprint(2, "Status: {}. Mode: {}. Set Processed: {}".format(
            pstatus, mode_num, processed
        ))
        notebook.processed |= processed
        session.add(notebook)
        session.commit()
    return "done"


def apply(
    session, status, script_name, execution_mode, with_execution, with_dependency,
    skip_if_error, skip_if_error_mode, skip_if_troublesome, try_to_discover_files,
    skip_env, skip_extract, dry_run, mode_rules, notebook_exec_mode,
    count, interval, reverse, check
):
    """Execute repositories"""
    mode_def = None if execution_mode == -1 else EXECUTION_MODE[execution_mode]

    filters = [
        Notebook.language == "python",
        Notebook.language_version != "unknown",
        func.length(Notebook.language_version) > 3,
        Repository.processed.op('&')(try_to_discover_files) == 0,
        Repository.processed.op('&')(consts.R_FAILED_TO_CLONE) == 0,
        Repository.processed.op('&')(skip_if_error) == 0,
        Repository.processed.op('&')(skip_if_troublesome) == 0,
    ]

    if interval:
        filters += [
            Repository.id >= interval[0],
            Repository.id <= interval[-1]
        ]

    filters += EXECUTION_RULES[with_execution]
    filters += DEPENDENCY_RULES[with_dependency]

    if mode_def is None:
        filters += mode_rules(
            with_execution, with_dependency, skip_if_error_mode
        )
    else:
        filters.append(
            Notebook.processed.op('&')(
                mode_def.processed * skip_if_error_mode
            ) == 0
        )

    query = (
        session.query(Notebook, Repository)
        .join(Repository)
        .filter(*filters)
    )
    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            (Repository.setups_count + Repository.requirements_count
            + Repository.pipfile_locks_count + Repository.pipfiles_count) > 0,
            Notebook.language_version.asc(),
            Repository.id.desc()
        )
    else:
        query = query.order_by(
            (Repository.setups_count + Repository.requirements_count
            + Repository.pipfile_locks_count + Repository.pipfiles_count) > 0,
            Notebook.language_version.asc(),
            Repository.id.asc()
        )

    moment = datetime.now().strftime("%Y%m%dT%H%M%S")
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    outf = str(config.LOGS_DIR / ("sub-{}-{}.out".format(script_name, moment)))
    errf = str(config.LOGS_DIR / ("sub-{}-{}.err".format(script_name, moment)))

    with open(outf, "wb") as out, open(errf, "wb") as err:

        group = groupby(
            query, lambda x: (
                x[0].language_version[:3], notebook_exec_mode(mode_def, *x)
            )
        )
        last = None
        for (version, mode), query_iter in group:
            status.report()
            vnum = version_string_to_list(version)
            envs = config.VERSIONS if mode.anaconda else config.RAW_VERSIONS
            env = best_match(vnum, envs)
            group = groupby(
                query_iter,
                lambda x: (x[1])
            )
            for repository, notebook_iter in group:
                if check_exit(check):
                    vprint(0, "Found .exit file. Exiting")
                    return
                current = (env, repository) if mode.dependencies else env
                if last != current:
                    prepared = prepare_environment(
                        session, env, mode, version, notebook_iter,
                        mode_def, skip_env, notebook_exec_mode, dry_run, out, err
                    )
                    if not prepared:
                        continue
                last = None if mode.dependencies else current
                result = execute_repository(
                    status, session, repository, notebook_iter,
                    mode, env, skip_extract, notebook_exec_mode, dry_run, out, err
                )
                vprint(2, result)
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
    parser.add_argument("-f", "--discover-deleted", action='store_true',
                        help="try to discover deleted files")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="repository id interval")
    parser.add_argument("-z", "--retry-troublesome", action='store_true',
                        help="retry troublesome")
    parser.add_argument("-x", "--with-execution", type=int,
                        default=config.WITH_EXECUTION,
                        help="-1: without execution; 0: all; 1: with execution")
    parser.add_argument("-d", "--with-dependency", type=int,
                        default=config.WITH_DEPENDENCY,
                        help="-1: without dependency; 0: all; 1: with dependency")
    parser.add_argument("-m", "--execution-mode", type=int,
                        default=config.EXECUTION_MODE,
                        help="-1: auto; 1: cellorder, 2: dependencies, 4: anaconda")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count results")
    parser.add_argument("--dry-run", type=int, default=0,
                        help="dry-run level. 0 runs everything. 1 does not execute. "
                        "2 does not install dependencies. 3 does not extract files. "
                        "4 does not prepare conda environment")
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='iterate in reverse order')
    parser.add_argument('--check', type=str, nargs='*',
                        default={'all', script_name, script_name + '.py'},
                        help='check name in .exit')
    parser.add_argument("--skip-env", action='store_true',
                        help="skip environment")
    parser.add_argument("--skip-extract", action='store_true',
                        help="skip extraction")


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
            script_name,
            args.execution_mode,
            args.with_execution,
            args.with_dependency,
            0 if args.retry_errors else consts.R_COMPRESS_ERROR,
            1 if args.retry_errors else 3,
            0 if args.retry_troublesome else consts.R_TROUBLESOME,
            0 if args.discover_deleted else consts.R_UNAVAILABLE_FILES,
            args.skip_env,
            args.skip_extract,
            args.dry_run,
            mode_rules,
            notebook_exec_mode,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )


def prepare_environment(
    session, env, mode, version, notebook_iter,
    mode_def, skip_env, notebook_exec_mode, dry_run, out, err
):
    vprint(0, "{}Preparing {} environment for Python {}".format(
        "[DRY RUN] " if dry_run >= 4 else "",
        'anaconda' if mode.anaconda else 'raw python', version
    ))
    if dry_run >= 4:
        return True

    if not skip_env and not install_env(env, out, err):
        for notebook, repository in notebook_iter:
            nmode = notebook_exec_mode(mode_def, notebook, repository)
            notebook.processed |= nmode.processed * 2
            session.add(notebook)
            session.commit()
        vprint(0, "Failed to prepare environment")
        return False
    return True


def install_env(env, out, err):
    subprocess.call(
        ". {}/etc/profile.d/conda.sh "
        "&& conda env remove --name work -y"
        .format(config.ANACONDA_PATH),
        shell=True, stdout=out, stderr=err
    )
    shutil.rmtree(str(config.ANACONDA_PATH / "envs" / "work"), ignore_errors=True)
    return subprocess.call(
        ". {}/etc/profile.d/conda.sh "
        "&& conda create --name work --clone {}"
        .format(config.ANACONDA_PATH, env),
        shell=True, stdout=out, stderr=err
    ) == 0

if __name__ == "__main__":
    main()
