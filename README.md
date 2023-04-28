# Computational reproducibility of Jupyter notebooks from biomedical publications
This repository contains the code for the study of computational reproducibility of Jupyter notebooks from biomedical publications. We analyzed the reproducibility of Jupyter notebooks from GitHub repositories associated with publications indexed in the biomedical literature repository PubMed Central.

We use the code for reproducibility of Jupyter notebooks from the study done by [Pimentel et al., 2019](https://zenodo.org/record/2592524).
We provide code for collecting the publication metadata from PubMed Central using [NCBI Entrez utilities via Biopython](https://biopython.org/docs/1.76/api/Bio.Entrez.html). The results are based on the data collected from PMC on 24th February, 2021.
We used the esearch function to search PMC for Jupyter notebooks. The search query used was ``(ipynb OR jupyter OR ipython) AND github''.
Based on the data retrieved from PMC in XML format, we collected information on journals and articles.
We looked for mentions of GitHub links anywhere in the article, including the abstract, the article body, data availability statement, and supplementary information and extracted the links. We collected the execution environment information by looking into the dependency information declared in the repositories in terms of files like requirements.txt, setup.py and pipfile. Additional information for each repository is also collected from the GitHub API.
This includes the dates of the creation, updates, or pushes to the repository, and the programming languages used in each repository.
All the extracted information is stored in a SQLite database. After collecting and creating the database tables, we ran a pipeline to collect the Jupyter notebooks contained in the GitHub repositories based on the code from [Pimentel et al., 2019](https://zenodo.org/record/2592524).

The repository contains contains two folders:
archaelogy: The folder contains the scripts to download, parse and extract the metadata from the PubMed Central publications and the reprositories mentioned in the publications.
analyses: The folder contains the notebooks used to analyze the data associated with the study.
db.sqlite: The SQLite database that contains all the data extracted in the study.

## Requirements:
* Centos 7
* Conda 4.9.4
* Python 3.7.6
* GitHub account
* gcc 7.3.0
* lbzip2

## Installation:

Change to computational-reproducibility-pmc directory:
`cd computational-reproducibility-pmc/computational-reproducibility-pmc`

Set the following environment variables in the config.py file:
GITHUB_USERNAME = os.environ.get("JUP_GITHUB_USERNAME", "") # your github username
GITHUB_TOKEN = os.environ.get("JUP_GITHUB_PASSWORD", "") # your github token

Other environment variables can also be set in the config.py file.

To install conda and anaconda environments for each python version and to upgrade pip, install pipenv, and install the archaeology package in each environment, run the following:

```
source conda-setup.sh
```

## Running the pipeline:
We used py36 to run the pipeline.

```
conda activate py36
```

Run the following python file:
```
python r0_main.py
```


## Running the analysis:
We use raw38 for the analysis of the metadata collected in the study.

```
cd analyses
```

```
conda activate raw38
pip install -r requirements.txt
jupyter lab
```
The Index.ipynb shows the order of running the notebooks.