# Computational reproducibility of Jupyter notebooks from biomedical publications
This repository contains the code for the computational reproducibility of Jupyter notebooks from biomedical publications. We analyzed the reproducibility of Jupyter notebooks from GitHub repositories associated with publications indexed in the biomedical literature repository PubMed Central. 

We use the code for reproducibility of Jupyter notebooks from the study done by [Pimental et al., 2019](https://zenodo.org/record/2592524). 
We provide code for collecting the publication metadata from PubMedCentral using NCBI Entrez utilities via Biopython. The results are based on the data collected from PMC on 24th February, 2021.
We used the esearch function to search PMC for Jupyter notebooks. The search query used was ``(ipynb OR jupyter OR ipython) AND github''.
Based on the data retrieved from PMC in XML format, we collected information on journals and articles.
We looked for mentions of GitHub links anywhere in the article, including the abstract, the article body, data availability statement, and supplementary information and extracted the links. We collected the execution environment information by looking into the dependency information declared in the repositories in terms of files like requirements.txt, setup.py and pipfile. Additional information for each repository is also collected from the GitHub API. 
This includes the dates of the creation, updates, or pushes to the repository, and the programming languages used in each repository. 
All the extracted information is stored in a SQLite database. After collecting and creating the database tables, we ran a pipeline to collect the Jupyter notebooks contained in the GitHub repositories based on the code from [Pimental et al., 2019](https://zenodo.org/record/2592524). 

