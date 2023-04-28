#!/bin/bash
echo '***************************lbzip2************************'
conda install -c conda-forge lbzip2

echo '***************************raw_27************************'
conda create -n raw_27 python=2.7 -y
conda activate raw_27
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate

echo '***************************py_27************************'
conda create -n py_27 python=2.7 anaconda -y
conda activate py_27
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate

echo '***************************raw_34************************'
conda create -n raw_34 python=3.4 -y
conda activate raw_34
conda install jupyter -c conda-forge -y
conda uninstall jupyter -y
pip install --upgrade pip
pip install jupyter
pip install nbdime
pip install pipenv
pip install -e archaeology
pip install pathlib2

echo '***************************py_34************************'
conda create -n py_34 python=3.4 anaconda -y
conda activate py_34
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e archaeology


echo '***************************raw_35************************'
conda create -n raw_35 python=3.5 -y
conda activate raw_35
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate

echo '***************************py_35************************'
conda create -n py_35 python=3.5 anaconda -y
conda activate py_35
conda install -y appdirs atomicwrites keyring secretstorage libuuid navigator-updater prometheus_client pyasn0 pyasn1-modules spyder-kernels tqdm jeepney automat constantly anaconda-navigator
pip install --upgrade pip
pip install nbdime
pip install pipenv --ignore-installed
pip install -e  archaeology
conda deactivate

echo '***************************raw_36************************'

conda create -n raw_36 python=3.6 -y
conda activate raw_36
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate


echo '***************************py_36************************'
conda create -n py_36 python=3.6 anaconda -y
conda activate py_36
conda install -y anaconda-navigator jupyterlab_server navigator-updater
pip install --upgrade pip
pip install nbdime
pip install flake8-nb
pip install biopython
pip install pipenv
pip install -e  archaeology
python -c "import nltk; nltk.download('stopwords')"
conda deactivate


echo '***************************raw_37************************'
conda create -n raw_37 python=3.7 -y
conda activate raw_37
pip install --upgrade pip
pip install nbdime
pip install -U pipenv
pip install -e  archaeology
conda deactivate


echo '***************************py_37************************'
conda create -n py_37 python=3.7 anaconda -y
conda activate py_37
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
pip install nbdime
pip install -U pipenv
pip install -e  archaeology
conda deactivate


echo '***************************raw_38************************'
conda create -n raw_38 python=3.8 -y
conda activate raw_38
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e archaeology
conda deactivate


echo '***************************py_38************************'
conda create -n py_38 python=3.8 anaconda -y
conda activate py_38
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate

echo '***************************raw_39************************'
conda create -n raw_39 python=3.9 -y
conda activate raw_39
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e archaeology
conda deactivate


echo '***************************py_39************************'
conda create -n py_39 python=3.9 anaconda -y
conda activate py_39
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate


echo '***************************raw_310************************'
conda create -n raw_310 python=3.10 -y
conda activate raw_310
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e archaeology
conda deactivate


echo '***************************py_310************************'
conda create -n py_310 python=3.10 anaconda -y
conda activate py_310
pip install --upgrade pip
pip install nbdime
pip install pipenv
pip install -e  archaeology
conda deactivate


