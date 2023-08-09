#!/usr/bin/env upython
import argparse
import subprocess
import sys
import os
import dateutil.parser
from datetime import datetime
if sys.version_info < (3, 5):
    from pathlib2 import Path
else:
    from pathlib import Path

def read_interval(var, default=None):
    result = os.environ.get(var)
    if not result:
        return default
    return list(map(int, result.split(",")))

MACHINE = os.environ.get("JUP_MACHINE", "default")
BASE_DIR = Path(os.environ.get("JUP_BASE_DIR", "./")).expanduser()
LOGS_DIR = Path(os.environ.get("JUP_LOGS_DIR", str(BASE_DIR / "logs"))).expanduser()
COMPRESSION = os.environ.get("JUP_COMPRESSION", "lbzip2")
VERBOSE = int(os.environ.get("JUP_VERBOSE", 5))
DB_CONNECTION = os.environ.get("JUP_DB_CONNECTION", "sqlite:///db.sqlite")
GITHUB_USERNAME = os.environ.get("JUP_GITHUB_USERNAME", "")
GITHUB_PASSWORD = os.environ.get("JUP_GITHUB_PASSWORD", "")
GITHUB_TOKEN = os.environ.get("JUP_GITHUB_PASSWORD", "")
MAX_SIZE = float(os.environ.get("JUP_MAX_SIZE", 10.0))
FIRST_DATE = dateutil.parser.parse(os.environ.get("JUP_FIRST_DATE", "2020-01-25"))
EMAIL_LOGIN = os.environ.get("JUP_EMAIL_LOGIN", "")
EMAIL_TO = os.environ.get("JUP_EMAIL_TO", "")
OAUTH_FILE = Path(os.environ.get("JUP_OAUTH_FILE", "~/oauth2_creds.json")).expanduser()
REPOSITORY_INTERVAL = read_interval("JUP_REPOSITORY_INTERVAL")
NOTEBOOK_INTERVAL = read_interval("JUP_NOTEBOOK_INTERVAL")
WITH_EXECUTION = int(os.environ.get("JUP_WITH_EXECUTION", 1))
WITH_DEPENDENCY = int(os.environ.get("JUP_WITH_DEPENDENCY", 0))
EXECUTION_MODE = int(os.environ.get("JUP_EXECUTION_MODE", -1))
EXECUTION_DIR = Path(os.environ.get("JUP_EXECUTION_DIR", str(BASE_DIR / "execution"))).expanduser()
ANACONDA_PATH = Path(os.environ.get("JUP_ANACONDA_PATH", "~/anaconda3/")).expanduser()
MOUNT_BASE = os.environ.get("JUP_MOUNT_BASE", "")
UMOUNT_BASE = os.environ.get("JUP_UMOUNT_BASE", "")
NOTEBOOK_TIMEOUT = int(os.environ.get("JUP_NOTEBOOK_TIMEOUT", 300))

IS_SQLITE = DB_CONNECTION.startswith("sqlite")

DB ='pmc'
PUBMED_DB = 'pubmed'
PUB_XML_FILE="pmc.xml"

# Remember to add print to show_config if you add another variable

STATUS_FREQUENCY = {
    "extract_astroid": int(os.environ.get("JUP_ASTROID_FREQUENCY", 5)),
    "extract_ipython_and_modules": int(os.environ.get("JUP_IPYTHON_FREQUENCY", 5)),
    "extract_notebooks_and_cells": int(os.environ.get("JUP_NOTEBOOKS_FREQUENCY", 5)),
    "extract_requirement_files": int(os.environ.get("JUP_REQUIREMENT_FREQUENCY", 5)),
    "repository_crawler": int(os.environ.get("JUP_CRAWLER_FREQUENCY", 1)),
    "clone_removed": int(os.environ.get("JUP_CLONE_FREQUENCY", 1)),
    "compress": int(os.environ.get("JUP_COMPRESS_FREQUENCY", 5)),
    "execute_repositories": int(os.environ.get("JUP_EXECUTE_FREQUENCY", 1)),
}




VERSIONS = {
    2: {
        7: {
            15: "py27",
        },
    },
    3: {
        5: {
            5: "py35",
        },
        6: {
            5: "py36",
        },
        7: {
            0: "py37",
        },
        8: {
            0: "py38",
        },
        9: {
            0: "py39",
        },
        10: {
            0: "py310",
        },
    },
}


RAW_VERSIONS = {
    2: {
        7: {
            15: "raw27",
        },
    },
    3: {
        5: {
            5: "raw35",
        },
        6: {
            5: "raw36",
        },
        7: {
            0: "raw37",
        },
        8: {
            0: "raw38",
        },
        9: {
            0: "raw39",
        },
        10: {
            0: "raw310",
        },
    },
}

def show_config():
    print("MACHINE:", MACHINE)
    print("BASE_DIR:", BASE_DIR)
    print("LOGS_DIR:", LOGS_DIR)
    print("COMPRESSION:", COMPRESSION)
    print("VERBOSE:", VERBOSE)
    print("DB_CONNECTION:", DB_CONNECTION)
    print("GITHUB_USERNAME:", GITHUB_USERNAME)
    print("GITHUB_PASSWORD:", GITHUB_PASSWORD)
    print("MAX_SIZE:", MAX_SIZE)
    print("FIRST_DATE:", FIRST_DATE)
    print("EMAIL_LOGIN:", EMAIL_LOGIN)
    print("EMAIL_TO:", EMAIL_TO)
    print("OAUTH_FILE:", OAUTH_FILE)
    print("REPOSITORY_INTERVAL", REPOSITORY_INTERVAL)
    print("NOTEBOOK_INTERVAL", NOTEBOOK_INTERVAL)
    print("WITH_EXECUTION", WITH_EXECUTION)
    print("WITH_DEPENDENCY", WITH_DEPENDENCY)
    print("EXECUTION_MODE", EXECUTION_MODE)
    print("EXECUTION_DIR", EXECUTION_DIR)
    print("ANACONDA_PATH", ANACONDA_PATH)
    print("MOUNT_BASE", MOUNT_BASE)
    print("UMOUNT_BASE", UMOUNT_BASE)
    print("NOTEBOOK_TIMEOUT", NOTEBOOK_TIMEOUT)
    print("\nVERSIONS:")
    for major, minors in VERSIONS.items():
        for minor, patches in minors.items():
            for patch, path in patches.items():
                print("- {}.{}.{}:".format(major, minor, patch), path)
    print("\nSTATUS_FREQUENCY:")
    for script, freq in STATUS_FREQUENCY.items():
        print("- {}:".format(script), freq)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Run python script with this config")
    parser.add_argument("script", type=str,
                        help="script file")
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.script == "show":
        show_config()
        return

    with open('config.py', 'rb') as conf:
        before = conf.read()
    try:
        with open(__file__, 'rb') as rconf, open('config.py', 'wb') as wconf:
            wconf.write(rconf.read())
        subprocess.call(['python', '-u', args.script] + list(args.rest))
    finally:
        with open('config.py', 'wb') as wconf:
            wconf.write(before)

if __name__ == '__main__':
    main()
