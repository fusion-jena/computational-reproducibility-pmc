from setuptools import setup, find_packages
setup(
    name="NotebookArchaeology",
    version="0.1",
    #packages=find_packages(),
    #scripts=['say_hello.py'],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires=[
	    'sqlalchemy',
        'six',
        'ipython',
        'astroid',
        'jupyter',
        'nbformat',
        'future',
        'pygithub',
        'timeout-decorator',
        'yagmail[all]',
        'psycopg2-binary',
        'matplotlib_venn',
        'langdetect',
        'pathlib2;python_version<="3.4"',
        'pathlib2;python_version=="2.7"',
    ],
    # metadata for upload to PyPI
    author="Joao Felipe Pimentel",
    author_email="joaofelipenp@gmail.com",
    description="Notebook Archeology",
    license="MIT",
)
