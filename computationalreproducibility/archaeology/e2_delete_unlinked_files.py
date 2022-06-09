import shutil
import os
import config
import argparse
from db import connect, Repository
from utils import mount_basedir, savepid


def apply(count):
    """Delete files that do not have an associated repository"""
    paths = set()
    with connect() as session:
        for rep in session.query(Repository):
            paths.add(rep.path)
            paths.add(rep.zip_path)

    with mount_basedir():
        diff = set((config.BASE_DIR / "content").glob("*/*")) - paths
        if count:
            print(len(diff))
            return

        for path in diff:
            print(path)
            if path.is_file():
                os.remove(str(path))
            else:
                shutil.rmtree(str(path))


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Delete unlinked files")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count results")

    args = parser.parse_args()

    with savepid():
        apply(args.count)


if __name__ == "__main__":
    main()
