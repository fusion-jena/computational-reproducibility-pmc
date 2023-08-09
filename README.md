# Computational reproducibility of Jupyter notebooks from biomedical publications
This repository contains the code for the study of [computational reproducibility of Jupyter notebooks from biomedical publications](https://arxiv.org/pdf/2209.04308.pdf). Our focus lies in evaluating the extent of reproducibility of Jupyter notebooks derived from GitHub repositories linked to publications present in the biomedical literature repository, PubMed Central.

## Data Collection and Analysis
We use the code for reproducibility of Jupyter notebooks from the study done by [Pimentel et al., 2019](https://zenodo.org/record/2592524).
We provide code for collecting the publication metadata from PubMed Central using [NCBI Entrez utilities via Biopython](https://biopython.org/docs/1.76/api/Bio.Entrez.html).

Our approach involves searching PMC using the esearch function for Jupyter notebooks using the query: ``(ipynb OR jupyter OR ipython) AND github''. We meticulously retrieve data in XML format, capturing essential details about journals and articles. By systematically scanning the entire article, encompassing the abstract, body, data availability statement, and supplementary materials, we extract GitHub links. Additionally, we mine repositories for key information such as dependency declarations found in files like requirements.txt, setup.py, and pipfile. Leveraging the GitHub API, we enrich our data by incorporating repository creation dates, update histories, pushes, and programming languages.

All the extracted information is stored in a SQLite database. After collecting and creating the database tables, we ran a pipeline to collect the Jupyter notebooks contained in the GitHub repositories based on the code from [Pimentel et al., 2019](https://zenodo.org/record/2592524).

## Repository Structure
Our repository is organized into two main folders:

**[archaeology](./computational-reproducibility-pmc/archaeology)**: This directory hosts scripts designed to download, parse, and extract metadata from PubMed Central publications and associated repositories.

**[analyses](./computational-reproducibility-pmc/analyses)**: Here, you will find notebooks instrumental in the in-depth analysis of data related to our study.

## Accessing Data and Resources
* All the data generated during the initial study can be accessed at https://doi.org/10.5281/zenodo.6802158
* For the latest results and re-run data, refer to [this link](https://doi.org/10.5281/zenodo.8226725).
* The comprehensive SQLite database that encapsulates all the study's extracted data is stored in the **db.sqlite** file.
* The metadata in xml format extracted from PubMed Central which contains the information about the articles and journal can be accessed in **pmc.xml** file.

## System Requirements:
* Centos 7 (Documentation: https://www.centos.org/)
* Conda 4.9.4 (Installation Guide: https://docs.anaconda.com/anaconda/install/linux/)
* Python 3.7.6 (Download Link: https://www.python.org/downloads/)
* GitHub account (Get Started: https://github.com/, Requires GitHub Username and Token)
* gcc 7.3.0 (Installation Guide: https://gcc.gnu.org/install/)
* lbzip2  (Command: `conda install -c conda-forge lbzip2')

## Running the pipeline:
* Clone the computational-reproducibility-pmc repository using Git:
```
git clone https://github.com/fusion-jena/computational-reproducibility-pmc.git
```

* Navigate to the computational-reproducibility-pmc directory:
```
cd computational-reproducibility-pmc/computational-reproducibility-pmc
```

* Configure environment variables in the [config.py](./computational-reproducibility-pmc/archaeology/config.py) file:
```
GITHUB_USERNAME = os.environ.get("JUP_GITHUB_USERNAME", "add your github username here")

GITHUB_TOKEN = os.environ.get("JUP_GITHUB_PASSWORD", "add your github token here")
```

Other environment variables can also be set in the [config.py](./computational-reproducibility-pmc/archaeology/config.py) file.
```
BASE_DIR = Path(os.environ.get("JUP_BASE_DIR", "./")).expanduser() # Add the path of directory where the GitHub repositories will be saved

DB_CONNECTION = os.environ.get("JUP_DB_CONNECTION", "sqlite:///db.sqlite") # Add the path where the database is stored.
```

* To set up conda environments for each python versions, upgrade pip, install pipenv, and install the archaeology package in each environment, execute:

```
source conda-setup.sh
```

* Change to the [archaeology](./computational-reproducibility-pmc/archaeology) directory
```
cd archaeology
```

* Activate conda environment. We used py36 to run the pipeline.

```
conda activate py36
```

* Execute the main pipeline script ([r0_main.py](./computational-reproducibility-pmc/archaeology/r0_main.py)):
```
python r0_main.py
```


## Running the analysis:
* Navigate to the [analysis](./computational-reproducibility-pmc/analyses/) directory.

```
cd analyses
```

* Activate conda environment. We use raw38 for the analysis of the metadata collected in the study.

```
conda activate raw38
```

* Install the required packages using the [requirements.txt](./computational-reproducibility-pmc/analyses/requirements.txt) file.
```
pip install -r requirements.txt
```

* Launch Jupyterlab
```
jupyter lab
```

* Refer to the [Index.ipynb](./computational-reproducibility-pmc/analyses/Index.ipynb) notebook for the execution order and guidance.

## References:
* Sheeba Samuel, Daniel Mietchen. (2022). [Computational reproducibility of Jupyter notebooks from biomedical publications](https://arxiv.org/pdf/2209.04308.pdf), CoRR abs/2209.04308
* Sheeba Samuel, & Daniel Mietchen. (2022). [Dataset of a Study of Computational reproducibility of Jupyter notebooks from biomedical publications](https://doi.org/10.5281/zenodo.6802158) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.6802158
* Sheeba Samuel, & Daniel Mietchen. (2023). [Dataset of a Study of Computational reproducibility of Jupyter notebooks from biomedical publications](https://doi.org/10.5281/zenodo.8226725) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.8226725