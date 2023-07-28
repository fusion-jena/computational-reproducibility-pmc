import config
from db import connect, Article, ArticleMesh
from utils import mount_basedir, savepid, vprint
from Bio import Entrez
from SPARQLWrapper import SPARQLWrapper, JSON

def get_mesh_terms(pubmed_id):
    Entrez.email = config.EMAIL_LOGIN
    handle = Entrez.efetch(db=config.PUBMED_DB, id=pubmed_id, retmode='xml')
    records = Entrez.read(handle)
    try:
        if 'MeshHeadingList' in records['PubmedArticle'][0]['MedlineCitation']:
            mesh_terms = records['PubmedArticle'][0]['MedlineCitation']['MeshHeadingList']
            terms = [(term['DescriptorName'], term['DescriptorName'].attributes['UI']) for term in mesh_terms]
            return terms
    except KeyError:
        vprint("No MESH terms found for PubMed id={}".format(pubmed_id))
        return []


def execute_sparql_query(mesh_term):
    endpoint_url = "https://id.nlm.nih.gov/mesh/sparql"

    # Set the SPARQL query
    query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
        PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
        PREFIX mesh2015: <http://id.nlm.nih.gov/mesh/2015/>
        PREFIX mesh2016: <http://id.nlm.nih.gov/mesh/2016/>
        PREFIX mesh2017: <http://id.nlm.nih.gov/mesh/2017/>

        SELECT DISTINCT ?ParentTreeNum ?SubjectArea
        FROM <http://id.nlm.nih.gov/mesh>

        WHERE {{
            mesh:{mesh_term} meshv:treeNumber ?TreeNum .
            ?TreeNum meshv:parentTreeNumber+ ?ParentTreeNum .
            ?Parent meshv:treeNumber ?ParentTreeNum .
            ?Parent rdfs:label ?SubjectArea .
            FILTER (STRLEN(STR(?ParentTreeNum)) < 34)
        }}
        ORDER BY ?ParentTreeNum
    """.format(mesh_term=mesh_term)

    # Send the SPARQL query to the MESH SPARQL endpoint
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        if 'results' in results and 'bindings' in results['results']:
            bindings = results['results']['bindings']
            if bindings:
                return bindings
            else:
                vprint(1, "No results found for MESH term={}".format(mesh_term))
        else:
            vprint(1, "No results found for SPARQL query for the MESH term={}".format(mesh_term))
    except Exception as e:
        print(f"An error occurred while executing the SPARQL query: {e}")


def get_pmid_meshdata(session):
    query = session.query(Article)
    for article in query:
        if article is not None and article.pmid is not None:
            mesh_terms = get_mesh_terms(article.pmid)
            if mesh_terms:
                for mesh_label, meshid  in mesh_terms:
                    article_meshdata = session.query(ArticleMesh).filter(
                        ArticleMesh.article_id == article.id,
                        ArticleMesh.pmid == article.pmid,
                        ArticleMesh.meshid == meshid,
                    ).first()
                    if article_meshdata is not None:
                        vprint(1, "ArticleMesh Data exists: Article ID={}, Article pmid={}, Article Mesh id ={}".format(article.id, article.pmid, meshid))
                        continue

                    bindings = execute_sparql_query(meshid)
                    for binding in bindings:
                        toplevelmeshid = binding['ParentTreeNum']['value']
                        toplevelmeshlabel = binding['SubjectArea']['value']
                        vprint(1, "Mesh Term = {}, Parent Tree Number={}, Subject Area={}".format(meshid, toplevelmeshid,toplevelmeshlabel))
                        articlemesh = ArticleMesh(
                            article_id = article.id,
                            pmid = article.pmid,
                            meshid = meshid,
                            mesh_label = mesh_label,
                            toplevelmeshid = toplevelmeshid,
                            toplevelmeshlabel = toplevelmeshlabel
                        )
                        session.add(articlemesh)
                        session.commit()
                        vprint(1, "Done. ArticleMesh ID={}".format(articlemesh.id))


        else:
            vprint(1, "Article pmid is None")

def main():
    """Main function"""

    with connect() as session, mount_basedir(), savepid():
        get_pmid_meshdata(session)

if __name__ == "__main__":
    main()