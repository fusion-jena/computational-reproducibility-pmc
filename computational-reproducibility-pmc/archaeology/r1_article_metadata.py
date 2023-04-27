import config
from db import Repository, Article, Journal, Author, connect
from utils import vprint, join_paths
from utils import mount_basedir, savepid

import xml.etree.ElementTree as ET
import re
from urllib.parse import urlparse
import datetime


def preprocess_url(url):
    url = re.sub(r"[\(\) ]", "", url) # Remove any white space or brackets from url
    url = re.sub(r';.*',"", url) # Remove multiple urls joined together by ;
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
            repo = repo.split("/")[:2] # Get only the pathname and remove others
            if repo[0] == 'orgs' or repo[0] == 'collections' or repo[0] == 'topics':
                return
            repo = "/".join(repo)
            if repo.endswith("."):
                repo = repo[:-1]
            github_link = "https://github.com/{}".format(repo)
            return github_link

    elif re.match("https?:\/\/nbviewer.(.*).org\/github\/\w+\/\w+", url):
        parse = urlparse(url)
        path_string = (parse.path).split("/")
        repo = path_string[2] + '/' + path_string[3]
        github_link = "https://github.com/{}".format(repo)
        return github_link
    else:
        return

def extract_link(att, link_text, exp):
    alllink = att.findall(exp)
    for link in alllink:
        if (link is not None and link.text is not  None and 'github' in link.text):
            print("link:", link.text)
            if re.match("(.*)github.com\/(.*)\/(.+)", link.text):
                if link.text not in link_text:
                    link_text.append(link.text)
            elif re.match("https?:\/\/nbviewer.(.*).org\/github\/\w+\/\w+", link.text):
                if link.text not in link_text:
                    link_text.append(link.text)
    return link_text

def get_processed_links(link_list):
    # Preprocessing the extracted links to the format "https://github.com/username/repositoryname"
    github_links = []
    for line in link_list:
        github_link = preprocess_url(line)
        if github_link and github_link not in github_links:
            if re.match(r"https?:\/\/github.com\/(.*)\/(.+)", github_link):
                github_links.append(github_link)
    return github_links

def extract_github_links(att):
    link_text = []
    link_text = extract_link(att, link_text, ".//*/ext-link")
    link_text = extract_link(att, link_text, ".//*/uri")
    # link_text = extract_link(att, link_text, "./body/sec/p/ext-link")
    # link_text = extract_link(att, link_text, "./body/sec/*/p/ext-link")
    # link_text = extract_link(att, link_text, "./body/sec/sec/*/p/ext-link")
    # link_text = extract_link(att, link_text, "./back/sec/[@sec-type='data-availability']/*/ext-link")
    # link_text = extract_link(att, link_text, "./back/sec/*/[@sec-type='data-availability']/*/ext-link")
    # link_text = extract_link(att, link_text, "./back/ref-list/ref/element-citation/ext-link")
    # link_text = extract_link(att, link_text, "./back/notes/p/ext-link")
    return link_text

# def extract_github_links(att):
#     # Extracting github links from xml file
#     link_text = []
#     alllink = att.findall("./body/*/ext-link")  or att.findall("./body/sec/p/ext-link") or att.findall("./body/sec/*/p/ext-link") or att.findall("./body/sec/sec/*/p/ext-link")
#     for link in alllink:
#         if (link is not None and link.text is not  None and 'github.com' in link.text):
#             if link.text not in link_text:
#                 link_text.append(link.text)
#     #print("link_text 1", link_text)


#     alllink = att.findall("./back/sec/[@sec-type='data-availability']/*/ext-link") or att.findall("./back/sec/*/[@sec-type='data-availability']/*/ext-link")
#     for link in alllink:
#         if (link is not None and link.text is not  None and 'github.com' in link.text):
#             if link.text not in link_text:
#                 link_text.append(link.text)
#     #print("link_text 2", link_text)

#     # Extracting github links from xml file
#     alllink = att.findall("./back/ref-list/ref/element-citation/ext-link")
#     for link in alllink:
#         if (link is not None and link.text is not  None and 'github.com' in link.text):
#             if link.text not in link_text:
#                 link_text.append(link.text)

#     #print("link_text 3", link_text)

#     # Extracting github links from xml file
#     alllink = att.findall("./back/notes/p/ext-link")
#     for link in alllink:
#         if (link is not None and link.text is not  None and 'github.com' in link.text):
#             if link.text not in link_text:
#                 link_text.append(link.text)
#     #print("link_text 4", link_text)
#     return link_text

def create_repositories_entry(att):
    pre_repository_links = extract_github_links(att)
    repository_links = get_processed_links(pre_repository_links)
    return repository_links

def create_article_entry(session, att, journal_id):
    article_title = att.findtext("./front/article-meta/title-group/article-title")
    article_pmid = att.findtext("./front/article-meta/article-id/[@pub-id-type='pmid']")

    article = session.query(Article).filter(
        Article.name == article_title,
    ).first()
    if article is not None:
        vprint(1, "Article exists: ID={}".format(article.id))
        return

    article_published_date = ''
    article_received = ''
    article_accepted = ''
    article_license_type = None

    article_pmc = att.findtext("./front/article-meta/article-id/[@pub-id-type='pmc']")
    article_publisher_id = att.findtext("./front/article-meta/article-id/[@pub-id-type='publisher-id']")
    article_doi = att.findtext("./front/article-meta/article-id/[@pub-id-type='doi']")
    article_subject = att.findtext("./front/article-meta/article-categories/subj-group/subject")

    pubdate_node = att.find("./front/article-meta/pub-date")
    if pubdate_node:
        for pub_type in pubdate_node.attrib:
            pubdate_node_type = pubdate_node.attrib[pub_type]
            article_published_year = att.findtext("./front/article-meta/pub-date/[@" + pub_type + "='" + pubdate_node_type + "']" + "/year")
            article_published_month = att.findtext("./front/article-meta/pub-date/[@" + pub_type + "='" + pubdate_node_type + "']" + "/month")
            article_published_day = att.findtext("./front/article-meta/pub-date/[@" + pub_type + "='" + pubdate_node_type + "']" + "/day")


            if article_published_year and article_published_month and article_published_day:
                article_published_date = datetime.datetime(int(article_published_year),
                                            int(article_published_month), int(article_published_day))
                article_published_date = article_published_date.date().isoformat()

    article_received_year = att.findtext("./front/article-meta/history/date/[@date-type='received']/year")
    article_received_month = att.findtext("./front/article-meta/history/date/[@date-type='received']/month")
    article_received_day = att.findtext("./front/article-meta/history/date/[@date-type='received']/day")
    if article_received_year and article_received_month and article_received_day:
        article_received = datetime.datetime(int(article_received_year),
                            int(article_received_month), int(article_received_day))
        article_received = article_received.date().isoformat()

    article_accepted_year = att.findtext("./front/article-meta/history/date/[@date-type='accepted']/year")
    article_accepted_month = att.findtext("./front/article-meta/history/date/[@date-type='accepted']/month")
    article_accepted_day = att.findtext("./front/article-meta/history/date/[@date-type='accepted']/day")
    if article_accepted_year and article_accepted_month and article_accepted_day:
        article_accepted = datetime.datetime(int(article_accepted_year),
                            int(article_accepted_month),int(article_accepted_day))
        article_accepted = article_accepted.date().isoformat()

    license_node = att.find("./front/article-meta/permissions/license")
    if license_node:
        for license_type in license_node.attrib:
            article_license_type = license_node.attrib[license_type] if license_type else None


    # license_node = att.find("./front/article-meta/permissions/license")
    # print("license_node", license_node)
    # if license_node and 'license-type' in license_node:
    #     print("inside license_node", license_node)
    #     article_license_type = license_node.attrib["license-type"]
    #     print("article_license_type", article_license_type)
    article_copyright_statement = att.findtext("./front/article-meta/permissions/copyright-statement")
    article_keywords = att.findtext("./front/article-meta/kwd-group/kwd")

    keywords = att.findall("./front/article-meta/kwd-group/kwd")
    article_keywords = []
    for keyword in keywords:
        article_keywords.append(keyword.text)

    repository_links = create_repositories_entry(att)

    article = Article(
        name = article_title,
        pmid = article_pmid,
        pmc  = article_pmc,
        publisher_id  = article_publisher_id,
        doi  = article_doi,
        subject  = article_subject,
        published_date = article_published_date,
        received_date = article_received,
        accepted_date = article_accepted,
        license_type = article_license_type,
        copyright_statement = article_copyright_statement,
        keywords = join_paths(article_keywords) if article_keywords is not None else None,
        repositories = join_paths(repository_links) if repository_links is not None else None,
        journal_id = journal_id
    )
    session.add(article)
    session.commit()
    vprint(1, "Done. Article ID={}".format(article.id))
    return article

def create_journal_entry(session, att):
    journal_nlm_ta = att.findtext("./front/journal-meta/journal-id/[@journal-id-type='nlm-ta']")
    journal_iso_abbrev = att.findtext("./front/journal-meta/journal-id/[@journal-id-type='iso-abbrev']")
    journal_title = att.findtext("./front/journal-meta/journal-title-group/journal-title")
    journal_issn_epub = att.findtext("./front/journal-meta/issn/[@pub-type='epub']")
    publisher_name = att.findtext("./front/journal-meta/publisher/publisher-name")
    publisher_loc = att.findtext("./front/journal-meta/publisher/publisher-loc")


    journal = session.query(Journal).filter(
        Journal.name == journal_title,
    ).first()

    if journal is None:
        journal = Journal(
            name = journal_title,
            nlm_ta = journal_nlm_ta,
            iso_abbrev = journal_iso_abbrev,
            issn_epub = journal_issn_epub,
            publisher_name = publisher_name,
            publisher_loc = publisher_loc,
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
        author_surname = author.findtext("./name/surname")
        author_given_names = author.findtext("./name/given-names")
        author_orcid = author.findtext("./contrib-id/[@contrib-id-type='orcid']")
        author_email = author.findtext("./address/email")

        author = Author(
            name = author_surname,
            given_names = author_given_names,
            orcid = author_orcid,
            email = author_email,
            article_id = article_id
        )
        session.add(author)
        session.commit()
        vprint(1, "Done. Authors ID={}".format(author.id))

def get_articles_metadata(session):
    # Writing all the processed link into database
    tree = ET.parse(config.PUB_XML_FILE)
    root = tree.getroot()

    github_links = []
    for att in root:
        journal = create_journal_entry(session, att)
        if journal:
            article = create_article_entry(session, att, journal.id)
            if article:
                create_authors_entry(session, att, article.id)
    vprint(0, "Finished creating article and repository metadata")

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        get_articles_metadata(session)

if __name__ == "__main__":
    main()
