"""Crawl repositories"""
import argparse
import os
import json
import sys
from datetime import datetime, timedelta
from github import Github
from sqlalchemy import desc

import config
from db import connect, Query
from load_repository import load_repository
from utils import StatusLogger, mount_basedir, check_exit, savepid


FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def time(date):
    """Format date in Github format"""
    if date is None:
        return ""
    return date.strftime(FORMAT)


def folder_size(path):
    """Get size of folder in GB"""
    parent = {}  # path to parent path mapper
    size = {}  # storing the size of directories
    folder = os.path.realpath(path)

    for root, _, filenames in os.walk(folder):
        if root == folder:
            parent[root] = -1  # the root folder will not have any parent
            size[root] = 0.0  # intializing the size to 0

        elif root not in parent:
            # extract the immediate parent of the subdirectory
            immediate_parent_path = os.path.dirname(root)
            # store the parent of the subdirectory
            parent[root] = immediate_parent_path
            size[root] = 0.0  # initialize the size to 0

        total_size = 0
        for filename in filenames:
            filepath = os.path.join(root, filename)
            try:
                # computing the size of the files under the directory
                total_size += os.stat(filepath).st_size
            except (FileNotFoundError, OSError):
                pass
        size[root] = total_size  # store the updated size
        # for subdirectories, we need to update the size of the parent
        # till the root parent
        temp_path = root
        while parent[temp_path] != -1:
            size[parent[temp_path]] += total_size
            temp_path = parent[temp_path]
    return size[folder]/1024/1024/1024


class Querier(object):
    """Queries github"""

    def __init__(self, github=None):
        # self.github = github or Github(
        #     config.GITHUB_USERNAME,
        #     config.GITHUB_PASSWORD
        # )
        self.github = github or Github(
            config.GITHUB_TOKEN
        )
        self.status = StatusLogger("repository_crawler")
        self.status.report()

        self.first_date = config.FIRST_DATE
        self.last_date = None
        self.delta = None
        self.page = -1
        self.query = ""
        self.reset_page = True

    def initialize_date(self):
        """Initialize last_date and delta"""
        if self.reset_page:
            self.delta = None
        if self.last_date is None:
            self.last_date = self.first_date + timedelta(365)
        if self.delta is None:
            self.delta = timedelta(365)
            if self.first_date is not None:
                self.delta = (self.last_date - self.first_date) / 2

    def query_repositories(self):
        """Query repositories"""
        self.initialize_date()
        query = ['language:"Jupyter Notebook"']
        if self.first_date is None:
            query.append("created:<=" + time(self.last_date))
        else:
            query.append("created:{}..{}".format(
                time(self.first_date), time(self.last_date)
            ))
        self.query = " ".join(query)
        pagination = self.github.search_repositories(self.query, order="desc")
        count = pagination.totalCount
        if config.VERBOSE > 1:
            print("> Adjusting query {!r} (count = {})".format(
                self.query, count
            ))
        if count < 500 and self.last_date < datetime.now():
            self.last_date += self.delta
            self.delta *= 1.5
            return self.query_repositories()
        if count >= 1000:
            self.last_date -= self.delta
            self.delta /= 2
            return self.query_repositories()
        if self.reset_page:
            self.page = 0
        self.reset_page = True
        if config.VERBOSE > 0:
            print("Query executed with {} results: {!r}".format(
                count, self.query
            ))
        return pagination, count

    def next_range(self):
        """Adjust range to next result"""
        self.first_date = self.last_date
        self.last_date += self.delta
        self.delta = None

    def iterate_repository_pagination(self, session, pagination, count):
        """Iterate on repository pagination"""
        pages = int(count / 30)
        for self.page in range(self.page, pages):
            if check_exit({"all", "repository_crawler", "repository_crawler.py"}):
                raise RuntimeError("Found .exit file. Exiting")
            if folder_size(str(config.BASE_DIR)) > config.MAX_SIZE:
                raise RuntimeError("Content folder is too big. Clean it up")
            if config.VERBOSE > 1:
                print("> Processing page {}".format(self.page))
            repositories = pagination.get_page(self.page)
            for repository in repositories:
                load_repository(session, "github.com", repository.full_name)
                session.commit()
                self.status.count += 1
                self.status.report()
        query = Query(
            name="repository",
            query=self.query,
            first_date=self.first_date,
            last_date=self.last_date,
            delta=self.delta,
            count=count,
        )
        session.add(query)
        session.commit()
        if config.VERBOSE > 0:
            print("> Finished query. ID={}".format(query.id))

    def recover(self, session):
        """Recover information from .stop.json or database"""
        strptime = datetime.strptime
        if os.path.exists(".stop.json"):
            with open(".stop.json", "rb") as stop_file:
                dic = json.load(stop_file)
                if not dic["delta"].startswith("000"):
                    dic["delta"] = "000" + dic["delta"]
                self.delta = strptime(
                    dic["delta"], FORMAT
                ) - datetime.min
                self.last_date = strptime(dic["last_date"], FORMAT)
                self.first_date = None
                if dic["first_date"]:
                    self.first_date = strptime(dic["first_date"], FORMAT)
                self.page = dic["page"]
                self.reset_page = False
                self.query = dic["query"]
            return True
        the_query = session.query(Query).order_by(desc(Query.last_date))
        query = the_query.first()
        if query:
            self.last_date = query.last_date
            self.first_date = query.first_date
            self.page = 0
            self.reset_page = True
            self.query = query.query
            self.delta = query.delta
            self.next_range()
            return True
        return False

    def save(self):
        """Save .stop.json"""
        stop = {
            "query": self.query,
            "last_date": time(self.last_date),
            "first_date": time(self.first_date),
            "delta": time(datetime.min + self.delta),
            "page": self.page,
        }
        with open(".stop.json", "w", encoding="utf-8") as stop_file:
            json.dump(stop, stop_file)

    def search_repositories(self):
        """Search repositories"""
        with connect() as session, mount_basedir():
            try:
                if not self.recover(session):
                    self.iterate_repository_pagination(
                        session, *self.query_repositories()
                    )
                    self.next_range()
                while self.last_date < datetime.now():
                    self.iterate_repository_pagination(
                        session, *self.query_repositories()
                    )
                    self.next_range()
            except Exception as err:  # pylint: disable=broad-except
                self.save()
                print("Stopped due {}. File '.stop.json' created".format(err))
                import traceback
                if config.VERBOSE > 1:
                    traceback.print_exc()
                if str(err) == "Content folder is too big. Clean it up":
                    sys.exit(2)
                else:
                    sys.exit(1)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Use github API to load repositories until an error")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    args = parser.parse_args()
    config.VERBOSE = args.verbose
    with savepid():
        # github = Github(config.GITHUB_USERNAME, config.GITHUB_PASSWORD)
        github = Github(config.GITHUB_TOKEN)
        querier = Querier(github)
        querier.search_repositories()

if __name__ == "__main__":
    main()
