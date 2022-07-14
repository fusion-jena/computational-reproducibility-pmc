"""Load notebook and cells"""
import argparse
import os

import config
import consts

from db import connect
from utils import StatusLogger
from utils import savepid
from execution_rules import mode_rules_cell_order
from execution_rules import EXECUTION_MODE
from s7_execute_repositories import apply


def notebook_exec_mode_cell_order(mode_def, notebook, repository):
    if mode_def is not None:
        return mode_def
    with_dependency = (
        repository.setups_count > 0
        or repository.requirements_count > 0
        or repository.pipfiles_count > 0
        or repository.pipfile_locks_count > 0
    )
    tup = (not with_dependency, with_dependency, False)
    tup_str = "0b{}".format("".join(str(int(b)) for b in tup))
    num = int(tup_str, 2)
    return EXECUTION_MODE[num]


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
            mode_rules_cell_order,
            notebook_exec_mode_cell_order,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == "__main__":
    main()
