import config

from db import connect, Repository
from utils import mount_basedir, savepid

def main():
    """Main function"""
    with connect() as session, mount_basedir(), savepid():
        for rep in session.query(Repository):
            if not rep.path.exists() and not rep.zip_path.exists():
                print(rep)

if __name__ == "__main__":
    main()
