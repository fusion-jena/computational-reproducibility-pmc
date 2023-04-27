from github import Github
import config
from db import Repository, Article, RepositoryData, RepositoryRelease, connect
from utils import mount_basedir, savepid, vprint
from datetime import datetime, timedelta
import time


def get_repo_info_github_api(session):
    count = 0
    query = session.query(Repository)
    for repository in query:
        if repository is not None:
            if repository.repository=='features/actions':
                vprint(1, "Repository not found")
                continue            
            repository_data = session.query(RepositoryData).filter(
                RepositoryData.repository_id == repository.id,
                RepositoryData.article_id == repository.article_id,
            ).first()
            if repository_data is not None:
                vprint(1, "Repository Data exists: Repository ID={}, Article ID={}".format(repository.id, repository.article_id))
                continue
            github = Github(
                config.GITHUB_TOKEN
            )
            repo = github.get_repo(repository.repository)

            total_commits_after_published_date = None
            total_commits_after_received_date = None
            total_commits_after_accepted_date = None

            article = session.query(Article).filter(
                Article.id == repository.article_id,
            ).first()
            if article.published_date:
                published_date = datetime.strptime(article.published_date, '%Y-%m-%d')
                total_commits_after_published_date = repo.get_commits(since=published_date).totalCount
            if article.received_date:
                received_date = datetime.strptime(article.received_date, '%Y-%m-%d')
                total_commits_after_received_date = repo.get_commits(since=received_date).totalCount

            if article.accepted_date:
                accepted_date = datetime.strptime(article.accepted_date, '%Y-%m-%d')
                total_commits_after_accepted_date = repo.get_commits(since=accepted_date).totalCount


            repository_data = RepositoryData(
                url = repo.html_url,
                description = repo.description,
                created_at = repo.created_at,
                updated_at = repo.updated_at,
                pushed_at = repo.pushed_at,
                size = repo.size,
                homepage = repo.homepage,
                language = str(repo.get_languages()),
                #owner = repo.owner.login,
                #organization = repo.organization.login,
                watchers = repo.watchers,
                subscribers_count = repo.subscribers_count,
                stargazers_count = repo.stargazers_count,
                forks_count = repo.forks_count,
                network_count = repo.network_count,
                open_issues_count = repo.open_issues_count,
                archived = repo.archived,
                has_issues = repo.has_issues,
                has_downloads = repo.has_downloads,
                has_projects =repo.has_projects,
                has_pages = repo.has_pages,
                has_wiki = repo.has_wiki,
                private = repo.private,
                license_name = repo.raw_data['license']['name'] if repo.raw_data['license'] and 'name' in repo.raw_data['license'] else None,
                license_key = repo.raw_data['license']['key'] if repo.raw_data['license'] and 'key' in repo.raw_data['license'] else None,
                # total_commits = total_commits,
                total_commits_after_published_date = total_commits_after_published_date,
                total_commits_after_received_date = total_commits_after_received_date,
                total_commits_after_accepted_date = total_commits_after_accepted_date,
                total_releases = repo.get_releases().totalCount,
                repository_id = repository.id,
                article_id = repository.article_id,
            )
            session.add(repository_data)
            session.commit()
            vprint(1, "Done. RepositoryData ID={}".format(repository_data.id))



            for release in repo.get_releases():
                repository_release = RepositoryRelease(
                    name = release.title,
                    tag_name = release.tag_name,
                    # owner = None,
                    created_at = release.created_at,
                    published_at = release.published_at,
                    tarball_url = release.tarball_url,
                    prerelease = release.prerelease,
                    repository_id = repository.id,
                    article_id = repository.article_id,
                )
                session.add(repository_release)
                session.commit()
                vprint(1, "Done. RepositoryRelease ID={}".format(repository_release.id))
                time.sleep(3)
        else:
            vprint(1, "Repository does not exists: ID={}".format(repository.repository))

        count += 1

    vprint(0, "Finished loading repository data and release")

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        get_repo_info_github_api(session)

if __name__ == "__main__":
    main()
