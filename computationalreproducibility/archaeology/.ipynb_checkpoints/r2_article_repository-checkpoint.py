import consts
import config
from db import Repository, Article, connect
from utils import vprint, join_paths
from utils import mount_basedir, savepid
from load_repository import load_repository_from_url


def create_article_repository_db(session):
    count = 0
    query = (
        session.query(Article)
    )
    for article in query:
        for name in article.repository_urls:
            vprint(1, "Repository url extracted from article: {}".format(name))
            if not name:
                continue
            if name == 'https://github.com/features/actions':
                continue
            if 'orgs' in name and name.split("/")[3] == 'orgs':
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
    vprint(0, "Finished loading repositories")

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        create_article_repository_db(session)

if __name__ == "__main__":
    main()
