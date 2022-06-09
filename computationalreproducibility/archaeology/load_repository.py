"""Load Repository"""
import argparse
import hashlib
import subprocess
import shutil
import os

import requests

from future.moves.urllib.parse import urlparse


import consts
import config
from db import Repository, connect
from utils import find_files, vprint, join_paths, find_files_in_path
from utils import mount_basedir, savepid


def extract_domain_repository(url):
    """Extract domain and repository from repository url"""
    parse = urlparse(url)
    domain = "github.com"
    if parse.netloc == "github.com":
        repo = parse.path[1:]
    elif url.startswith("git@github.com:"):
        repo = url[15:]
    else:
        repo = domain = url
    if domain == "github.com" and repo.endswith(".git"):
        repo = repo[:-4]
    return domain, repo


def extract_hash_parts(repo):
    """Extract hash parts from repo"""
    full_hash = hashlib.sha1(repo.encode("utf-8")).hexdigest()
    return full_hash[:2], full_hash[2:]


def get_remote(domain, repo):
    """Get git remote from domain and repo"""
    remote = repo
    if domain == "github.com":
        remote = "https://github.com/{}.git".format(repo)
    return remote

def check_url_exists(remote):
    request = requests.get(remote)
    if request.status_code == 200:
        return 1
    else:
        return 0


def git(*args):
    """Invoke git"""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.check_call(["git"] + list(args), env=env)


def git_output(*args, cwd=None):
    """Invoke git and return output"""
    return subprocess.check_output(["git"] + list(args), cwd=cwd)


def clone(part, end, repo, remote, branch=None, commit=None):
    """Clone git repository into a proper directory"""
    part_dir = config.BASE_DIR / "content" / part
    part_dir.mkdir(parents=True, exist_ok=True)
    full_dir = part_dir / end
    if (full_dir.exists() and
            (not (full_dir / ".git").exists() or
             list(full_dir.iterdir()) == [full_dir / ".git"])):
        shutil.rmtree(str(full_dir), ignore_errors=True)
    if not full_dir.exists():
        args = ["clone"]
        if commit is None:
            args += ["--depth", "1"]
        args += [remote, str(full_dir)]
        if branch is not None:
            args.append("-b")
            args.append(branch)
        if git(*args) != 0:
            raise EnvironmentError("Clone failed for {}".format(repo))
        if commit is not None:
            args = [
                "--git-dir", str(full_dir / ".git"),
                "--work-tree", str(full_dir),
                "checkout", commit
            ]
            if git(*args) != 0:
                raise EnvironmentError("Checkout failed for {}/{}".format(
                    repo, commit
                ))
    return full_dir


def load_repository_from_url(session, url, article_id, branch=None,
                             commit=None, clone_existing=False):
    """Clone repository and extract its information from URL"""
    domain, repo = extract_domain_repository(url)
    remote = get_remote(domain, repo)
    if check_url_exists(remote):
        vprint(0, "url: {}, branch: {}, commit:{}, clone_existing: {}".format(url, branch, commit, clone_existing))
        return load_repository(
            session, domain, repo, article_id,
            branch=branch, commit=commit, clone_existing=clone_existing)
    else:
        vprint(0, "Repository not found: {}".format(url))


def load_repository(session, domain, repo, article_id, check_repo_only=True, branch=None,
                    commit=None, clone_existing=False):
    """Clone repository and extract its information"""
    vprint(0, "Processing repository: {}".format(repo))
    if check_repo_only:
        repository = session.query(Repository).filter(
            Repository.domain == domain,
            Repository.repository == repo,
        ).first()
        if repository is not None:
            vprint(1, "Repository exists: ID={}".format(repository.id))
            if not clone_existing:
                return repository
    part, end = extract_hash_parts(repo)
    remote = get_remote(domain, repo)
    vprint(1, "Remote: {}".format(remote))
    full_dir = clone(part, end, repo, remote, branch, commit)

    commit = git_output(
        "rev-parse", "HEAD", cwd=str(full_dir)
    ).decode("utf-8").strip()

    repository = session.query(Repository).filter(
        Repository.domain == domain,
        Repository.repository == repo,
        Repository.commit == commit,
    ).first()
    if repository is not None:
        if not check_repo_only:
            vprint(1, "Repository exists: ID={}".format(repository.id))
        # vprint(1, "> Removing .git directory")
        # shutil.rmtree(str(repository.path / ".git"), ignore_errors=True)
        return repository

    vprint(1, "Finding files")
    notebooks = [
        file.relative_to(full_dir)
        for file in find_files(full_dir, "*.ipynb")
        if ".ipynb_checkpoints" not in str(file)
    ]

    setups, requirements, pipfiles, pipfile_locks = find_files_in_path(
        full_dir, [
            "setup.py", "requirements.txt", "Pipfile", "Pipfile.lock"
        ]
    )

    repository = Repository(
        domain=domain, repository=repo,
        hash_dir1=part, hash_dir2=end,
        commit=commit,

        notebooks_count=len(notebooks),
        setups_count=len(setups),
        requirements_count=len(requirements),
        pipfiles_count=len(pipfiles),
        pipfile_locks_count=len(pipfile_locks),

        notebooks=join_paths(notebooks),
        setups=join_paths(setups),
        requirements=join_paths(requirements),
        pipfiles=join_paths(pipfiles),
        pipfile_locks=join_paths(pipfile_locks),

        processed=consts.R_OK,
        article_id=article_id,
    )
    session.add(repository)
    session.commit()
    # vprint("Removing .git directory")
    # shutil.rmtree(str(repository.path / ".git"), ignore_errors=True)
    vprint(1, "Done. ID={}".format(repository.id))

    return repository


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Load Repository by URL")
    parser.add_argument("url", type=str,
                        help="repository URL")
    parser.add_argument("-v", "--verbose", type=int, default=config.VERBOSE,
                        help="increase output verbosity")
    parser.add_argument("-b", "--branch", type=str,
                        help="specific branch")
    parser.add_argument("-c", "--commit", type=str,
                        help="specific commit")
    parser.add_argument("-e", "--clone-existing", action='store_true',
                        help="clone even if repository exists")

    args = parser.parse_args()
    config.VERBOSE = args.verbose
    with connect() as session, mount_basedir(), savepid():
        load_repository_from_url(
            session, args.url, args.branch, args.commit, args.clone_existing
        )


if __name__ == "__main__":
    main()