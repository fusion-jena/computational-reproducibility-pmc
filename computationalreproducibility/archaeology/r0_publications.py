import argparse
import hashlib
import subprocess
import shutil
import os


import consts
import config
from db import Repository, Article, Journal, Author, connect
from utils import find_files, vprint, join_paths, find_files_in_path
from utils import mount_basedir, savepid
from r1_run_pipeline import process_articles


import xml.etree.ElementTree as ET
from collections.abc import Iterable
import re
import csv
from urllib.parse import urlparse
from Bio import Entrez


DB ='pmc'
PUB_XML_FILE="pmc.xml"

def preprocess_url(url):
    url = re.sub(r"[\(\) ]", "", url) # Remove any white space or brackets from url
    if re.match(r"(.*)github.com/(.*)/(.*)", url):# Match if the url is in the format
        url = url.replace("www.", "") # Replace "www" from url
        # Format the url
        if (url.startswith("github")):
            url = "https://" + url
        parse = urlparse(url)
        if parse.scheme == "" or parse.scheme == "http":
            parse = parse._replace(scheme='https') # Replace all scheme of the github links to https
        if parse.netloc == "github.com":
            repo = parse.path[1:] # Get the path of the repository
            if repo.endswith(".git"):
                repo = repo[:-4]
            repo = "/".join(repo.split("/")[:2]) # Get only the pathname and remove others
            if repo.endswith("."):
                repo = repo[:-1]
            github_link = "https://github.com/{}".format(repo)
            return github_link
    else:
        return

def get_publications_from_db(session):
    Entrez.email = config.EMAIL_LOGIN
    handle = Entrez.esearch(db=DB, term='(ipynb OR jupyter OR ipython) AND github', usehistory='y')
    record = Entrez.read(handle)
    handle.close()
    identifiers = record['IdList']
    webenv = record["WebEnv"]
    query_key = record["QueryKey"]

    f_handle = Entrez.efetch(db=DB, rettype="xml", retmode="xml", query_key=query_key, webenv=webenv)
    data = f_handle.read()
    f_handle.close()
    f=open(PUB_XML_FILE,"wb")
    f.write(data)
    f.close()

def get_processed_links(link_list):
    # Preprocessing the extracted links to the format "https://github.com/username/repositoryname"
    github_links = []
    for line in link_list:
        github_link = preprocess_url(line)
        if github_link and github_link not in github_links:
            github_links.append(github_link)
    return github_links

def extract_github_links(att):
    # Extracting github links from xml file
    link_text = []
    alllink = att.findall("./body/*/ext-link")  or att.findall("./body/sec/p/ext-link") or att.findall("./body/sec/*/p/ext-link") or att.findall("./body/sec/sec/*/p/ext-link")
    for link in alllink:
        if (link is not None and link.text is not  None and 'github.com' in link.text):
            if link.text not in link_text:
                link_text.append(link.text)
    #print("link_text 1", link_text)


    alllink = att.findall("./back/sec/[@sec-type='data-availability']/*/ext-link") or att.findall("./back/sec/*/[@sec-type='data-availability']/*/ext-link")
    for link in alllink:
        if (link is not None and link.text is not  None and 'github.com' in link.text):
            if link.text not in link_text:
                link_text.append(link.text)
    #print("link_text 2", link_text)

    # Extracting github links from xml file
    alllink = att.findall("./back/ref-list/ref/element-citation/ext-link")
    for link in alllink:
        if (link is not None and link.text is not  None and 'github.com' in link.text):
            if link.text not in link_text:
                link_text.append(link.text)

    #print("link_text 3", link_text)

    # Extracting github links from xml file
    alllink = att.findall("./back/notes/p/ext-link")
    for link in alllink:
        if (link is not None and link.text is not  None and 'github.com' in link.text):
            if link.text not in link_text:
                link_text.append(link.text)
    #print("link_text 4", link_text)
    return link_text

def create_article_entry(session, att, journal_id):

    article_title = att.find("./front/article-meta/title-group/article-title")
    article_pmid = att.find("./front/article-meta/article-id/[@pub-id-type='pmid']")

    article = session.query(Article).filter(
        Article.name == article_title.text,
    ).first()
    if article is not None:
        vprint(1, "Article exists: ID={}".format(article.id))
        return


    article_pmc = att.find("./front/article-meta/article-id/[@pub-id-type='pmc']")
    article_publisher_id = att.find("./front/article-meta/article-id/[@pub-id-type='publisher-id']")
    article_doi = att.find("./front/article-meta/article-id/[@pub-id-type='doi']")
    article_subject = att.find("./front/article-meta/article-categories/subj-group/subject")
    publisher_name = att.find("./front/journal-meta/publisher/publisher-name")
    publisher_loc = att.find("./front/journal-meta/publisher/publisher-loc")

    article_published_date = att.find("./front/article-meta/pub-date/[@pub-type='epub']")
    article_received = att.find("./front/article-meta/history/date/[@date-type='received']/year")
    article_accepted = att.find("./front/article-meta/history/date/[@date-type='accepted']/year")
    article_license_type = att.find("./front/article-meta/permissions/license/[@license-type]")
    article_copyright_statement = att.find("./front/article-meta/permissions/copyright-statement")
    article_keywords = att.find("./front/article-meta/kwd-group/kwd")

    keywords = att.findall("./front/article-meta/kwd-group/kwd")
    article_keywords = []
    for keyword in keywords:
        article_keywords.append(keyword.text)

    repository_links = create_repositories_entry(att)

    article = Article(
        name = article_title.text if article_title is not None else None,
        pmid = article_pmid.text if article_pmid is not None else None,
        pmc  = article_pmc.text if article_pmc is not None else None,
        publisher_id  = article_publisher_id.text if article_publisher_id is not None else None,
        publisher_name = publisher_name.text if publisher_name is not None else None,
        publisher_loc = publisher_loc.text if publisher_loc is not None else None,
        doi  = article_doi.text if article_doi is not None else None,
        subject  = article_subject.text if article_subject is not None else None,
        published_date = article_published_date.text if article_published_date is not None else None,
        received_date = article_received.text if article_received is not None else None,
        accepted_date = article_accepted.text if article_accepted is not None else None,
        license_type = article_license_type.text if article_license_type is not None else None,
        copyright_statement = article_copyright_statement.text if article_copyright_statement is not None else None,
        keywords = join_paths(article_keywords) if article_keywords is not None else None,
        repositories = join_paths(repository_links) if repository_links is not None else None,
        journal_id = journal_id
    )
    session.add(article)
    session.commit()
    vprint(1, "Done. Article ID={}".format(article.id))
    return article

def create_journal_entry(session, att):
    journal_nlm_ta = att.find("./front/journal-meta/journal-id/[@journal-id-type='nlm-ta']")
    journal_iso_abbrev = att.find("./front/journal-meta/journal-id/[@journal-id-type='iso-abbrev']")
    journal_title = att.find("./front/journal-meta/journal-title-group/journal-title")
    journal_issn_epub = att.find("./front/journal-meta/issn/[@pub-type='epub']")

    journal = session.query(Journal).filter(
        Journal.name == journal_title.text,
    ).first()

    if journal is None:
        journal = Journal(
            name = journal_title.text if journal_title is not None else None,
            nlm_ta = journal_nlm_ta.text if journal_nlm_ta is not None else None,
            iso_abbrev = journal_iso_abbrev.text if journal_iso_abbrev is not None else None,
            issn_epub = journal_issn_epub.text if journal_issn_epub is not None else None
        )
        session.add(journal)
        session.commit()
        vprint(1, "Done. Journal ID={}".format(journal.id))
    else:
        vprint(1, "Journal exists: ID={}".format(journal.id))
    return journal

def create_authors_entry(session, att, article_id):
    authors = att.findall("./front/article-meta/contrib-group/contrib/[@contrib-type='author']")
    for author in authors:
        author_surname = author.find("./name/surname")
        author_given_names = author.find("./name/given-names")
        author_orcid = author.find("./contrib-id/[@contrib-id-type='orcid']")
        author_email = author.find("./address/email")

        author = Author(
            name = author_surname.text if author_surname is not None else None,
            given_names = author_given_names.text if author_given_names is not None else None,
            orcid = author_orcid.text if author_orcid is not None else None,
            email = author_email.text if author_email is not None else None,
            article_id = article_id
        )
        session.add(author)
        session.commit()
        vprint(1, "Done. Authors ID={}".format(author.id))

def create_repositories_entry(att):
    pre_repository_links = extract_github_links(att)
    repository_links = get_processed_links(pre_repository_links)
    return repository_links

def get_articles_metadata(session):
    # Writing all the processed link into database
    tree = ET.parse(PUB_XML_FILE)
    root = tree.getroot()

    github_links = []
    for att in root:
        journal = create_journal_entry(session, att)
        if journal:
            article = create_article_entry(session, att, journal.id)
            if article:
                create_authors_entry(session, att, article.id)
                #process_articles(session, article)

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        #get_publications_from_db(session)
        get_articles_metadata(session)

if __name__ == "__main__":
    main()
