import argparse
import hashlib
import subprocess
import shutil
import os


import consts
import config
from db import Repository, Article, Journal, Author, connect
from utils import find_files, vprint, join_paths, find_files_in_path, ext_split
from utils import mount_basedir, savepid
from load_repository import load_repository_from_url


import re
from urllib.parse import urlparse


def run_pipeline(session):
    pass

def process_articles(session, article):
    count = 0
    for name in article.repository_urls:
        print("name:", name)
        if not name:
            continue
        count += 1
        repository = session.query(Repository).filter(
            Repository.repository == name,
        ).first()
        if repository is not None:
            vprint(1, "Repository exists: ID={}".format(repository.id))
        else:
            vprint(1, "Repository does not exists: ID={}".format(name))
            load_repository_from_url(session, name, article.id)

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        run_pipeline(session)

if __name__ == "__main__":
    main()