import config
from db import connect
from utils import mount_basedir, savepid, vprint

import xml.etree.ElementTree as ET
from Bio import Entrez

def get_publications_from_db(session):
    Entrez.email = config.EMAIL_LOGIN
    handle = Entrez.esearch(db=config.DB, term='(ipynb OR jupyter OR ipython) AND github', usehistory='y')
    record = Entrez.read(handle)
    handle.close()
    identifiers = record['IdList']
    webenv = record["WebEnv"]
    query_key = record["QueryKey"]

    f_handle = Entrez.efetch(db=config.DB, rettype="xml", retmode="xml", query_key=query_key, webenv=webenv)
    data = f_handle.read()
    f_handle.close()
    f=open(config.PUB_XML_FILE,"wb")
    f.write(data)
    f.close()
    vprint(0, "Finished fetching and adding articles in {}".format(config.PUB_XML_FILE))

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        get_publications_from_db(session)

if __name__ == "__main__":
    main()