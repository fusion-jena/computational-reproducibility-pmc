# Computational reproducibility of Jupyter notebooks from biomedical publications
This repository contains the code for the study of computational reproducibility of Jupyter notebooks from biomedical publications. We analyzed the reproducibility of Jupyter notebooks from GitHub repositories associated with publications indexed in the biomedical literature repository PubMed Central.

We use the code for reproducibility of Jupyter notebooks from the study done by [Pimental et al., 2019](https://zenodo.org/record/2592524).
We provide code for collecting the publication metadata from PubMed Central using [NCBI Entrez utilities via Biopython](https://biopython.org/docs/1.76/api/Bio.Entrez.html). The results are based on the data collected from PMC on 24th February, 2021.
We used the esearch function to search PMC for Jupyter notebooks. The search query used was ``(ipynb OR jupyter OR ipython) AND github''.
Based on the data retrieved from PMC in XML format, we collected information on journals and articles.
We looked for mentions of GitHub links anywhere in the article, including the abstract, the article body, data availability statement, and supplementary information and extracted the links. We collected the execution environment information by looking into the dependency information declared in the repositories in terms of files like requirements.txt, setup.py and pipfile. Additional information for each repository is also collected from the GitHub API.
This includes the dates of the creation, updates, or pushes to the repository, and the programming languages used in each repository.
All the extracted information is stored in a SQLite database. After collecting and creating the database tables, we ran a pipeline to collect the Jupyter notebooks contained in the GitHub repositories based on the code from [Pimental et al., 2019](https://zenodo.org/record/2592524).

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

`cd computational-reproducibility-pmc`

Set the following environment variables in the config.py file:
GITHUB_USERNAME = os.environ.get("JUP_GITHUB_USERNAME", "") # your github username
GITHUB_TOKEN = os.environ.get("JUP_GITHUB_PASSWORD", "") # your github token

Other environment variables can also be set in the config.py file.

Install conda and anaconda environments for each python version. In each environment, upgrade pip, install pipenv, and install the archaeology package.

```
conda create -n raw27 python=2.7 -y
conda activate raw27
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n py27 python=2.7 anaconda -y
conda activate py27
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n raw35 python=3.5 -y
conda activate raw35
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n py35 python=3.5 anaconda -y
conda install -y appdirs atomicwrites keyring secretstorage libuuid navigator-updater prometheus_client pyasn1 pyasn1-modules spyder-kernels tqdm jeepney automat constantly anaconda-navigator
conda activate py35
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n raw36 python=3.6 -y
conda activate raw36
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n py36 python=3.6 anaconda -y
conda activate py36
conda install -y anaconda-navigator jupyterlab_server navigator-updater
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n raw37 python=3.7 -y
conda activate raw37
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```


```
conda create -n py37 python=3.7 anaconda -y
conda activate py37
conda install -y _ipyw_jlab_nb_ext_conf alabaster anaconda-client anaconda-navigator anaconda-project appdirs asn1crypto astroid astropy atomicwrites attrs automat
conda install -y babel backports backports.shutil_get_terminal_size beautifulsoup4 bitarray bkcharts blaze blosc bokeh boto bottleneck bzip2
conda install -y cairo colorama constantly contextlib2 curl cycler cython
conda install -y defusedxml docutils et_xmlfile fastcache filelock fribidi
conda install -y get_terminal_size gevent glob2 gmpy2 graphite2 greenlet
conda install -y harfbuzz html5lib hyperlink imageio imagesize incremental isort
conda install -y jbig jdcal jeepney jupyter jupyter_console jupyterlab_launcher keyring kiwisolver
conda install -y libtool libxslt lxml matplotlib mccabe mkl-service mpmath navigator-updater
conda install -y nltk nose numpydoc openpyxl pango patchelf path.py pathlib2 patsy pep8 pkginfo ply pyasn1 pyasn1-modules pycodestyle pycosat pycrypto pycurl pyflakes pylint pyodbc pywavelets
conda install -y rope scikit-image scikit-learn seaborn service_identity singledispatch spyder spyder-kernels statsmodels sympy
conda install -y tqdm traitlets twisted unicodecsv xlrd xlsxwriter xlwt zope zope.interface
conda install -y sortedcollections typed-ast
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
```

```
conda create -n py38 python=3.8 anaconda -y
conda activate py38
pip install --upgrade pip
pip install pipenv
pip install -e  archaeology
conda deactivate
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




