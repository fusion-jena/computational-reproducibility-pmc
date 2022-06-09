"""Load notebook and cells"""
import argparse
import tarfile
import os
import chardet

import config
import consts

from db import RequirementFile, Repository, connect
from utils import vprint, join_paths, StatusLogger, check_exit, savepid
from utils import find_files_in_path, find_files_in_zip, mount_basedir
from config import Path


def process_requirement_file(session, repository, reqformat, skip_if_error=consts.R_REQUIREMENTS_ERROR):
    """Process requirement file"""
    MAP = {
        "setup.py": "setup",
        "requirements.txt": "requirement",
        "Pipfile": "pipfile",
        "Pipfile.lock": "pipfile_lock"
    }
    zip_path = None
    tarzip = None
    if not repository.path.exists():
        if not repository.zip_path.exists():
            repository.processed |= consts.R_UNAVAILABLE_FILES
            session.add(repository)
            vprint(1, "Failed to load requirement {} due <repository not found>".format(reqformat))
            return False
        tarzip =  tarfile.open(str(repository.zip_path))
        zip_path = Path(repository.hash_dir2)
    finished = True
    req_param = MAP[reqformat] + "_names"
    for name in getattr(repository, req_param):
        if not name:
            continue
        try:
            vprint(2, "Loading requirement {}".format(name))
            if tarzip:
                content = tarzip.extractfile(tarzip.getmember(str(zip_path / name))).read()
            else:
                with open(str(repository.path / name), "rb") as ofile:
                    content = ofile.read()

            coding = chardet.detect(content)
            if coding["encoding"] is None:
                vprint(3, "Codec not detected")
                continue
            try:
                content = content.decode(coding['encoding'])
            except UnicodeDecodeError:
                vprint(3, "Invalid codec")
                continue

            if '\0' in content:
                vprint(3, "NULL byte in content")
                continue
            requirement_file = RequirementFile(
                repository_id=repository.id,
                name=name,
                reqformat=reqformat,
                content=content,
                processed=consts.F_OK,
            )
            session.add(requirement_file)
        except Exception as err:
            repository.processed |= skip_if_error
            session.add(repository)
            vprint(1, "Failed to load requirement {} due {!r}".format(name, err))
            if config.VERBOSE > 4:
                import traceback
                traceback.print_exc()
            finished = False
    if tarzip:
        tarzip.close()
    return finished


def collect_requirements(session, repository):
    if repository.path.exists():
        vprint(2, "using path")
        setups, requirements, pipfiles, pipfile_locks = find_files_in_path(
            repository.path, [
                "setup.py", "requirements.txt", "Pipfile", "Pipfile.lock"
            ]
        )
        changed = True
    elif repository.zip_path.exists():
        vprint(2, "using zip")
        with tarfile.open(str(repository.zip_path)) as tarzip:
            setups, requirements, pipfiles, pipfile_locks = find_files_in_zip(
                tarzip, Path(repository.hash_dir2), [
                    "setup.py", "requirements.txt", "Pipfile", "Pipfile.lock"
                ]
            )
        changed = True
    else:
        vprint(2, "not found")
        repository.processed |= consts.R_UNAVAILABLE_FILES
        changed = False

    if changed:
        repository.setups_count = len(setups)
        repository.requirements_count=len(requirements)
        repository.pipfiles_count = len(pipfiles)
        repository.pipfile_locks_count = len(pipfile_locks)

        repository.setups = join_paths(setups)
        repository.requirements = join_paths(requirements)
        repository.pipfiles = join_paths(pipfiles)
        repository.pipfile_locks = join_paths(pipfile_locks)

    session.add(repository)
    session.commit()


def process_repository(session, repository, skip_if_error=consts.R_REQUIREMENTS_ERROR):
    """Process repository"""
    if repository.processed & (consts.R_REQUIREMENTS_OK + skip_if_error):
        return "already processed"
    if repository.processed & skip_if_error:
        session.add(repository)
        repository.processed -= skip_if_error

    finished = True

    finished &= process_requirement_file(session, repository, "setup.py", skip_if_error)
    finished &= process_requirement_file(session, repository, "requirements.txt", skip_if_error)
    finished &= process_requirement_file(session, repository, "Pipfile", skip_if_error)
    finished &= process_requirement_file(session, repository, "Pipfile.lock", skip_if_error)

    if finished and not repository.processed & skip_if_error:

        repository.processed |= consts.R_REQUIREMENTS_OK
        session.add(repository)
    return "done"


def apply(
    session, status, selected_repositories, skip_if_error,
    count, interval, reverse, check
):
    while selected_repositories:
        filters = [
            Repository.processed.op("&")(consts.R_REQUIREMENTS_OK) == 0,
            Repository.processed.op("&")(skip_if_error) == 0,
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
            vprint(0, "Extracting requirement files from {}".format(repository))
            with mount_basedir():
                result = process_repository(session, repository, skip_if_error)
                vprint(1, result)
            status.count += 1
            session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description="Extract requirement files from registered repositories")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-n", "--repositories", type=int, default=None,
                        nargs="*",
                        help="repositories ids")
    parser.add_argument("-i", "--interval", type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help="id interval")
    parser.add_argument("-e", "--retry-errors", action='store_true',
                        help="retry errors")
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
            args.repositories or True,
             0 if args.retry_errors else consts.R_REQUIREMENTS_ERROR,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )


if __name__ == "__main__":
    main()
