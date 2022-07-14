"""Handles database model and connection"""
import sys
import subprocess
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Interval
from sqlalchemy import Float
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy import ForeignKeyConstraint

import config
from utils import version_string_to_list, ext_split

if not config.IS_SQLITE:
    from sqlalchemy.dialects.postgresql import BIGINT as BigInt
else:
    BigInt = Integer


Base = declarative_base()  # pylint: disable=invalid-name


def one_to_many(table, backref):
    """Create one to many relationship"""
    return relationship(table, back_populates=backref, lazy="dynamic", viewonly=True)


def many_to_one(table, backref):
    """Create many to one relationship"""
    return relationship(table, back_populates=backref, viewonly=True)


def force_encoded_string_output(func):
    """encode __repr__"""
    if sys.version_info.major < 3:
        def _func(*args, **kwargs):
            """encode __repr__"""
            return func(*args, **kwargs).encode(sys.stdout.encoding or 'utf-8')
        return _func
    else:
        return func


class Query(Base):
    """Query Table"""
    # pylint: disable=invalid-name, too-few-public-methods
    __tablename__ = 'queries'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    query = Column(String)
    first_date = Column(DateTime)
    last_date = Column(DateTime)
    delta = Column(Interval)
    count = Column(Integer)

    @force_encoded_string_output
    def __repr__(self):
        return u"<Query({})>".format(self.query)


class Repository(Base):
    """Repository Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'repositories'
    __table_args__ = (
        ForeignKeyConstraint(
            ['article_id'],
            ['article.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer)
    domain = Column(String)
    repository = Column(String)
    hash_dir1 = Column(String)
    hash_dir2 = Column(String)
    commit = Column(String)
    notebooks_count = Column(Integer)
    setups_count = Column(Integer)
    requirements_count = Column(Integer)
    notebooks = Column(String)
    setups = Column(String)
    requirements = Column(String)
    processed = Column(Integer, default=0)
    pipfiles_count = Column(Integer)
    pipfile_locks_count = Column(Integer)
    pipfiles = Column(String)
    pipfile_locks = Column(String)


    article_obj = many_to_one("Article", "repository_objs")
    notebooks_objs = one_to_many("Notebook", "repository_obj")
    cell_objs = one_to_many("Cell", "repository_obj")
    requirement_files_objs = one_to_many("RequirementFile", "repository_obj")
    execution_objs = one_to_many("Execution", "repository_obj")
    markdown_features_objs = one_to_many("MarkdownFeature", "repository_obj")
    code_analyses_objs = one_to_many("CodeAnalysis", "repository_obj")
    cell_modules_objs = one_to_many("CellModule", "repository_obj")
    cell_features_objs = one_to_many("CellFeature", "repository_obj")
    cell_names_objs = one_to_many("CellName", "repository_obj")
    files_objs = one_to_many("RepositoryFile", "repository_obj")
    notebook_markdowns_objs = one_to_many("NotebookMarkdown", "repository_obj")
    notebook_asts_objs = one_to_many("NotebookAST", "repository_obj")
    notebook_modules_objs = one_to_many("NotebookModule", "repository_obj")
    notebook_features_objs = one_to_many("NotebookFeature", "repository_obj")
    notebook_names_objs = one_to_many("NotebookName", "repository_obj")

    @property
    def path(self):
        """Return notebook path"""
        return (
            config.Path(config.BASE_DIR) / "content" /
            self.hash_dir1 / self.hash_dir2
        )

    @property
    def zip_path(self):
        """Return notebook path"""
        return config.Path(str(self.path) + ".tar.bz2")

    def compress(self, target=None, return_cmd=False):
        """Compress repository"""
        if not self.path.exists():
            return False
        if target is None:
            target = self.zip_path
        elif isinstance(target, str):
            target = config.Path(target)
        cmd = [
            "tar", "-cf", str(target),
            "--use-compress-program={}".format(config.COMPRESSION),
            "-C", str(target.parent), str(self.hash_dir2)
        ]
        if return_cmd:
            return cmd
        return subprocess.call(cmd) == 0

    def uncompress(self, target=None, return_cmd=False):
        """Uncompress repository"""
        if not self.zip_path.exists():
            return False
        target = target or self.zip_path.parent
        cmd = [
            "tar", "-xjf", str(self.zip_path),
            "-C", str(target)
        ]
        if return_cmd:
            return cmd
        return subprocess.call(cmd) == 0

    def get_commit(self, cwd=None):
        """Get commit from uncompressed repository"""
        cwd = cwd or self.path
        if isinstance(cwd, str):
            cwd = config.Path(cwd)
        if not cwd.exists():
            return None
        try:
            return subprocess.check_output([
                "git", "rev-parse", "HEAD"
            ], cwd=str(cwd)).decode("utf-8").strip()
        except subprocess.CalledProcessError:
            return "Failed"

    @property
    def notebook_names(self):
        """Return notebook names"""
        return ext_split(self.notebooks, ".ipynb")

    @property
    def setup_names(self):
        """Return setup names"""
        return ext_split(self.setups, "setup.py")

    @property
    def requirement_names(self):
        """Return requirement names"""
        return ext_split(self.requirements, "requirements.txt")

    @property
    def pipfile_names(self):
        """Return pipfile names"""
        return ext_split(self.pipfiles, "Pipfile")

    @property
    def pipfile_lock_names(self):
        """Return pipfile locks names"""
        return ext_split(self.pipfile_locks, "Pipfile.lock")

    @force_encoded_string_output
    def __repr__(self):
        return u"<Repository({}:{})>".format(self.id, self.repository)


class Notebook(Base):
    """Notebook Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'notebooks'
    __table_args__ = (
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer)
    name = Column(String)
    nbformat = Column(String)
    kernel = Column(String)
    language = Column(String)
    language_version = Column(String)
    max_execution_count = Column(Integer)
    total_cells = Column(Integer)
    code_cells = Column(Integer)
    code_cells_with_output = Column(Integer)
    markdown_cells = Column(Integer)
    raw_cells = Column(Integer)
    unknown_cell_formats = Column(Integer)
    empty_cells = Column(Integer)
    processed = Column(Integer, default=0)
    skip = Column(Integer, default=0)
    sha1_source = Column(String, default="")
    homework_count = Column(Integer, default=0)
    assignment_count = Column(Integer, default=0)
    course_count = Column(Integer, default=0)
    exercise_count = Column(Integer, default=0)
    lesson_count = Column(Integer, default=0)

    repository_obj = many_to_one("Repository", "notebooks_objs")
    cell_objs = one_to_many("Cell", "notebook_obj")
    execution_objs = one_to_many("Execution", "notebook_obj")
    markdown_features_objs = one_to_many("MarkdownFeature", "notebook_obj")
    code_analyses_objs = one_to_many("CodeAnalysis", "notebook_obj")
    cell_modules_objs = one_to_many("CellModule", "notebook_obj")
    cell_features_objs = one_to_many("CellFeature", "notebook_obj")
    cell_names_objs = one_to_many("CellName", "notebook_obj")
    notebook_markdowns_objs = one_to_many("NotebookMarkdown", "notebook_obj")
    notebook_asts_objs = one_to_many("NotebookAST", "notebook_obj")
    notebook_modules_objs = one_to_many("NotebookModule", "notebook_obj")
    notebook_features_objs = one_to_many("NotebookFeature", "notebook_obj")
    notebook_names_objs = one_to_many("NotebookName", "notebook_obj")


    @property
    def path(self):
        """Return notebook path"""
        return self.repository_obj.path / self.name

    @property
    def py_version(self):
        """Return python version of notebook"""
        note_version = self.language_version or "0"
        if note_version == "unknown":
            note_version = ".".join(map(str, sys.version_info[:3]))
        return version_string_to_list(note_version)

    @property
    def compatible_version(self):
        """Check if the running python version is compatible to the notebook"""
        note_version = self.py_version
        py_version = sys.version_info
        if note_version[0] != py_version[0]:
            return False
        if len(note_version) > 1 and note_version[1] > py_version[1]:
            return False
        return True

    @force_encoded_string_output
    def __repr__(self):
        return u"<Notebook({0.repository_id}/{0.id})>".format(self)


class Cell(Base):
    """Cell Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'cells'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
         ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    index = Column(Integer)
    cell_type = Column(String)
    execution_count = Column(String)
    lines = Column(Integer)
    output_formats = Column(String)
    source = Column(String)
    python = Column(Boolean)
    processed = Column(Integer, default=0)
    skip = Column(Integer, default=0)

    repository_obj = many_to_one("Repository", "cell_objs")
    notebook_obj = many_to_one("Notebook", "cell_objs")
    markdown_features_objs = one_to_many("MarkdownFeature", "cell_obj")
    code_analyses_objs = one_to_many("CodeAnalysis", "cell_obj")
    cell_modules_objs = one_to_many("CellModule", "cell_obj")
    cell_features_objs = one_to_many("CellFeature", "cell_obj")
    cell_names_objs = one_to_many("CellName", "cell_obj")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<Cell({0.repository_id}/{0.notebook_id}/{0.id}[{0.index}])>"
        ).format(self)


class RequirementFile(Base):
    """Requirement File Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'requirement_files'
    __table_args__ = (
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer)
    name = Column(String)
    reqformat = Column(String) # setup.py, requirements.py, Pipfile, Pipfile.lock
    content = Column(String)
    processed = Column(Integer, default=0)
    skip = Column(Integer, default=0)

    repository_obj = many_to_one("Repository", "requirement_files_objs")

    @property
    def path(self):
        """Return requirement file path"""
        return self.repository_obj.path / self.name

    @force_encoded_string_output
    def __repr__(self):
        return u"<RequirementFile({0.repository_id}/{0.id}:{0.name})>".format(
            self
        )


class Execution(Base):
    """Cell Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'executions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    notebook_id = Column(Integer)
    mode = Column(Integer)
    # 1: cellorder
    # 2: dependencies
    # 4: anaconda
    reason = Column(String)
    msg = Column(String)
    diff = Column(String)
    cell = Column(Integer)  # last executed cell index in notebook
    count = Column(Integer)  # number of executed cells
    diff_count = Column(Integer)
    timeout = Column(Integer)
    duration = Column(Float)
    processed = Column(Integer, default=0)
    skip = Column(Integer, default=0)
    repository_id = Column(Integer)

    repository_obj = many_to_one("Repository", "execution_objs")
    notebook_obj = many_to_one("Notebook", "execution_objs")

    @force_encoded_string_output
    def __repr__(self):
        return u"<Execution({0.repository_id}/{0.notebook_id}/{0.id}:m{0.mode})>".format(
            self
        )


class MarkdownFeature(Base):
    """Markdown Features Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'markdown_features'
    __table_args__ = (
        ForeignKeyConstraint(
            ['cell_id'],
            ['cells.id']
        ),
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    cell_id = Column(Integer)
    index = Column(Integer)

    language = Column(String)
    using_stopwords = Column(Boolean)
    len = Column(Integer)
    lines = Column(Integer)
    meaningful_lines = Column(Integer)
    words = Column(Integer)
    meaningful_words = Column(Integer)
    stopwords = Column(Integer)
    meaningful_stopwords = Column(Integer)

    header = Column(Integer)
    header_len = Column(Integer)
    header_lines = Column(Integer)
    header_words = Column(Integer)
    header_stopwords = Column(Integer)

    h1 = Column(Integer)
    h1_len = Column(Integer)
    h1_lines = Column(Integer)
    h1_words = Column(Integer)
    h1_stopwords = Column(Integer)

    h2 = Column(Integer)
    h2_len = Column(Integer)
    h2_lines = Column(Integer)
    h2_words = Column(Integer)
    h2_stopwords = Column(Integer)

    h3 = Column(Integer)
    h3_len = Column(Integer)
    h3_lines = Column(Integer)
    h3_words = Column(Integer)
    h3_stopwords = Column(Integer)

    h4 = Column(Integer)
    h4_len = Column(Integer)
    h4_lines = Column(Integer)
    h4_words = Column(Integer)
    h4_stopwords = Column(Integer)

    h5 = Column(Integer)
    h5_len = Column(Integer)
    h5_lines = Column(Integer)
    h5_words = Column(Integer)
    h5_stopwords = Column(Integer)

    h6 = Column(Integer)
    h6_len = Column(Integer)
    h6_lines = Column(Integer)
    h6_words = Column(Integer)
    h6_stopwords = Column(Integer)

    hrule = Column(Integer)

    list = Column(Integer)
    list_len = Column(Integer)
    list_lines = Column(Integer)
    list_items = Column(Integer)
    list_words = Column(Integer)
    list_stopwords = Column(Integer)

    table = Column(Integer)
    table_len = Column(Integer)
    table_lines = Column(Integer)
    table_rows = Column(Integer)
    table_cells = Column(Integer)
    table_words = Column(Integer)
    table_stopwords = Column(Integer)

    p = Column(Integer)
    p_len = Column(Integer)
    p_lines = Column(Integer)
    p_words = Column(Integer)
    p_stopwords = Column(Integer)

    quote = Column(Integer)
    quote_len = Column(Integer)
    quote_lines = Column(Integer)
    quote_words = Column(Integer)
    quote_stopwords = Column(Integer)

    code = Column(Integer)
    code_len = Column(Integer)
    code_lines = Column(Integer)
    code_words = Column(Integer)
    code_stopwords = Column(Integer)

    image = Column(Integer)
    image_len = Column(Integer)
    image_words = Column(Integer)
    image_stopwords = Column(Integer)

    link = Column(Integer)
    link_len = Column(Integer)
    link_words = Column(Integer)
    link_stopwords = Column(Integer)

    autolink = Column(Integer)
    autolink_len = Column(Integer)
    autolink_words = Column(Integer)
    autolink_stopwords = Column(Integer)

    codespan = Column(Integer)
    codespan_len = Column(Integer)
    codespan_words = Column(Integer)
    codespan_stopwords = Column(Integer)

    emphasis = Column(Integer)
    emphasis_len = Column(Integer)
    emphasis_words = Column(Integer)
    emphasis_stopwords = Column(Integer)

    double_emphasis = Column(Integer)
    double_emphasis_len = Column(Integer)
    double_emphasis_words = Column(Integer)
    double_emphasis_stopwords = Column(Integer)

    strikethrough = Column(Integer)
    strikethrough_len = Column(Integer)
    strikethrough_words = Column(Integer)
    strikethrough_stopwords = Column(Integer)

    html = Column(Integer)
    html_len = Column(Integer)
    html_lines = Column(Integer)

    math = Column(Integer)
    math_len = Column(Integer)
    math_words = Column(Integer)
    math_stopwords = Column(Integer)

    block_math = Column(Integer)
    block_math_len = Column(Integer)
    block_math_lines = Column(Integer)
    block_math_words = Column(Integer)
    block_math_stopwords = Column(Integer)

    latex = Column(Integer)
    latex_len = Column(Integer)
    latex_lines = Column(Integer)
    latex_words = Column(Integer)
    latex_stopwords = Column(Integer)

    skip = Column(Integer, default=0)

    cell_obj = many_to_one("Cell", "markdown_features_objs")
    notebook_obj = many_to_one("Notebook", "markdown_features_objs")
    repository_obj = many_to_one("Repository", "markdown_features_objs")

    @force_encoded_string_output
    def __repr__(self):
        cell = self.cell_obj
        notebook = cell.notebook_obj
        return (
            u"<MarkdownFeature({2.repository_id}/{2.id}/{1.id}[{1.index}]/{0.id})>"
            .format(self, cell, notebook)
        )


class CodeAnalysis(Base):
    """Code Analysis Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'code_analyses'
    __table_args__ = (
        ForeignKeyConstraint(
            ['cell_id'],
            ['cells.id']
        ),
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    cell_id = Column(Integer)
    index = Column(Integer)

    # Custom
    import_star = Column(Integer)

    functions_with_decorators = Column(Integer)
    classes_with_decorators = Column(Integer)
    classes_with_bases = Column(Integer)

    delname = Column(Integer)
    delattr = Column(Integer)
    delitem = Column(Integer)
    assignname = Column(Integer)
    assignattr = Column(Integer)
    assignitem = Column(Integer)

    ipython = Column(Integer)
    ipython_superset = Column(Integer)

    # Scope
    class_importfrom = Column(Integer)
    global_importfrom = Column(Integer)
    nonlocal_importfrom = Column(Integer)
    local_importfrom = Column(Integer)
    total_importfrom = Column(Integer)

    class_import = Column(Integer)
    global_import = Column(Integer)
    nonlocal_import = Column(Integer)
    local_import = Column(Integer)
    total_import = Column(Integer)

    class_assign = Column(Integer)
    global_assign = Column(Integer)
    nonlocal_assign = Column(Integer)
    local_assign = Column(Integer)
    total_assign = Column(Integer)

    class_delete = Column(Integer)
    global_delete = Column(Integer)
    nonlocal_delete = Column(Integer)
    local_delete = Column(Integer)
    total_delete = Column(Integer)

    class_functiondef = Column(Integer)
    global_functiondef = Column(Integer)
    nonlocal_functiondef = Column(Integer)
    local_functiondef = Column(Integer)
    total_functiondef = Column(Integer)

    class_classdef = Column(Integer)
    global_classdef = Column(Integer)
    nonlocal_classdef = Column(Integer)
    local_classdef = Column(Integer)
    total_classdef = Column(Integer)

    # AST
    # mod
    ast_module = Column(Integer)  # max
    ast_interactive = Column(Integer)  # zero
    ast_expression = Column(Integer)  # zero
    ast_suite = Column(Integer)  # zero

    #stmt
    ast_statements = Column(Integer)

    ast_functiondef = Column(Integer)
    ast_asyncfunctiondef = Column(Integer)
    ast_classdef = Column(Integer)
    ast_return = Column(Integer)

    ast_delete = Column(Integer)
    ast_assign = Column(Integer)
    ast_augassign = Column(Integer)
    ast_annassign = Column(Integer)

    ast_print = Column(Integer)

    ast_for = Column(Integer)
    ast_asyncfor = Column(Integer)
    ast_while = Column(Integer)
    ast_if = Column(Integer)
    ast_with = Column(Integer)
    ast_asyncwith = Column(Integer)

    ast_raise = Column(Integer)
    ast_try = Column(Integer)
    ast_tryexcept = Column(Integer)
    ast_tryfinally = Column(Integer)
    ast_assert = Column(Integer)

    ast_import = Column(Integer)
    ast_importfrom = Column(Integer)
    ast_exec = Column(Integer)
    ast_global = Column(Integer)
    ast_nonlocal = Column(Integer)
    ast_expr = Column(Integer)
    ast_pass = Column(Integer)
    ast_break = Column(Integer)
    ast_continue = Column(Integer)

    # expr
    ast_expressions = Column(Integer)

    ast_boolop = Column(Integer)
    ast_binop = Column(Integer)
    ast_unaryop = Column(Integer)
    ast_lambda = Column(Integer)
    ast_ifexp = Column(Integer)
    ast_dict = Column(Integer)
    ast_set = Column(Integer)
    ast_listcomp = Column(Integer)
    ast_setcomp = Column(Integer)
    ast_dictcomp = Column(Integer)
    ast_generatorexp = Column(Integer)

    ast_await = Column(Integer)
    ast_yield = Column(Integer)
    ast_yieldfrom = Column(Integer)

    ast_compare = Column(Integer)
    ast_call = Column(Integer)
    ast_num = Column(Integer)
    ast_str = Column(Integer)
    ast_formattedvalue = Column(Integer)
    ast_joinedstr = Column(Integer)
    ast_bytes = Column(Integer)
    ast_nameconstant = Column(Integer)
    ast_ellipsis = Column(Integer)
    ast_constant = Column(Integer)

    ast_attribute = Column(Integer)
    ast_subscript = Column(Integer)
    ast_starred = Column(Integer)
    ast_name = Column(Integer)
    ast_list = Column(Integer)
    ast_tuple = Column(Integer)

    # expr_contex
    ast_load = Column(Integer)
    ast_store = Column(Integer)
    ast_del = Column(Integer)
    ast_augload = Column(Integer)
    ast_augstore = Column(Integer)
    ast_param = Column(Integer)

    # slice
    ast_slice = Column(Integer)
    ast_index = Column(Integer)

    # boolop
    ast_and = Column(Integer)
    ast_or = Column(Integer)

    # operator
    ast_add = Column(Integer)
    ast_sub = Column(Integer)
    ast_mult = Column(Integer)
    ast_matmult = Column(Integer)
    ast_div = Column(Integer)
    ast_mod = Column(Integer)
    ast_pow = Column(Integer)
    ast_lshift = Column(Integer)
    ast_rshift = Column(Integer)
    ast_bitor = Column(Integer)
    ast_bitxor = Column(Integer)
    ast_bitand = Column(Integer)
    ast_floordiv = Column(Integer)

    # unaryop
    ast_invert = Column(Integer)
    ast_not = Column(Integer)
    ast_uadd = Column(Integer)
    ast_usub = Column(Integer)

    # cmpop
    ast_eq = Column(Integer)
    ast_noteq = Column(Integer)
    ast_lt = Column(Integer)
    ast_lte = Column(Integer)
    ast_gt = Column(Integer)
    ast_gte = Column(Integer)
    ast_is = Column(Integer)
    ast_isnot = Column(Integer)
    ast_in = Column(Integer)
    ast_notin = Column(Integer)

    # others
    ast_comprehension = Column(Integer)
    ast_excepthandler = Column(Integer)
    ast_arguments = Column(Integer)
    ast_arg = Column(Integer)
    ast_keyword = Column(Integer)
    ast_alias = Column(Integer)
    ast_withitem = Column(Integer)

    # New nodes?
    ast_others = Column(String)

    processed = Column(Integer)
    skip = Column(Integer, default=0)

    ast_extslice = Column(Integer, default=0)
    ast_repr = Column(Integer, default=0)

    cell_obj = many_to_one("Cell", "code_analyses_objs")
    notebook_obj = many_to_one("Notebook", "code_analyses_objs")
    repository_obj = many_to_one("Repository", "code_analyses_objs")
    cell_modules_objs = one_to_many("CellModule", "analysis_obj")
    cell_features_objs = one_to_many("CellFeature", "analysis_obj")
    cell_names_objs = one_to_many("CellName", "analysis_obj")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<CodeAnalysis({0.repository_id}/{0.notebook_id}/{0.cell_id}[{0.index}]/{0.id})>"
            .format(self)
        )


class CellModule(Base):
    """Cell Modules Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'cell_modules'
    __table_args__ = (
        ForeignKeyConstraint(
            ['analysis_id'],
            ['code_analyses.id']
        ),
        ForeignKeyConstraint(
            ['cell_id'],
            ['cells.id']
        ),
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    cell_id = Column(Integer)
    index = Column(Integer)
    analysis_id = Column(Integer)

    line = Column(Integer)
    import_type = Column(String)
    module_name = Column(String)
    local = Column(Boolean)
    skip = Column(Integer, default=0)

    local_possibility = Column(Integer, default=None)
    # 0 - impossible
    # 1 - matches the last part of module_name
    # 2 - matches all but the first part of module_name
    # 3 - matches all parts of module_name
    # 4 - already recognized as local

    cell_obj = many_to_one("Cell", "cell_modules_objs")
    notebook_obj = many_to_one("Notebook", "cell_modules_objs")
    repository_obj = many_to_one("Repository", "cell_modules_objs")
    analysis_obj = many_to_one("CodeAnalysis", "cell_modules_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<Module({0.repository_id}/{0.notebook_id}/"
            u"{0.cell_id}[{0.index}]/{0.analysis_id}/{0.id}:{0.import_type})>"
        ).format(self)


class CellFeature(Base):
    """Cell Features Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'cell_features'
    __table_args__ = (
        ForeignKeyConstraint(
            ['analysis_id'],
            ['code_analyses.id']
        ),
        ForeignKeyConstraint(
            ['cell_id'],
            ['cells.id']
        ),
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    cell_id = Column(Integer)
    index = Column(Integer)
    analysis_id = Column(Integer)

    line = Column(Integer)
    column = Column(Integer)
    feature_name = Column(String)
    feature_value = Column(String)
    skip = Column(Integer, default=0)

    cell_obj = many_to_one("Cell", "cell_features_objs")
    notebook_obj = many_to_one("Notebook", "cell_features_objs")
    repository_obj = many_to_one("Repository", "cell_features_objs")
    analysis_obj = many_to_one("CodeAnalysis", "cell_features_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<Feature({0.repository_id}/{0.notebook_id}/"
            u"{0.cell_id}[{0.index}]/{0.analysis_id}/{0.id}:{0.feature_name})>"
        ).format(self)


class CellName(Base):
    """Cell Names Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'cell_names'
    __table_args__ = (
        ForeignKeyConstraint(
            ['analysis_id'],
            ['code_analyses.id']
        ),
        ForeignKeyConstraint(
            ['cell_id'],
            ['cells.id']
        ),
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)
    cell_id = Column(Integer)
    index = Column(Integer)
    analysis_id = Column(Integer)

    scope = Column(String)
    context = Column(String)
    name = Column(String)
    count = Column(Integer)

    skip = Column(Integer, default=0)

    cell_obj = many_to_one("Cell", "cell_names_objs")
    notebook_obj = many_to_one("Notebook", "cell_names_objs")
    repository_obj = many_to_one("Repository", "cell_names_objs")
    analysis_obj = many_to_one("CodeAnalysis", "cell_names_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<Module({0.repository_id}/{0.notebook_id}/"
            u"{0.cell_id}[{0.index}]/{0.analysis_id}/{0.id}:{0.name})>"
        ).format(self)


class RepositoryFile(Base):
    """Repository Files Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'repository_files'
    __table_args__ = (
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    path = Column(String)
    size = Column(BigInt)
    skip = Column(Integer, default=0)
    had_surrogates = Column(Boolean, default=False)

    repository_obj = many_to_one("Repository", "files_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<File({0.repository_id}/{0.id})>"
        ).format(self)


class NotebookMarkdown(Base):
    """Notebook Markdown Features Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'notebook_markdowns'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)

    cell_count = Column(Integer)
    main_language = Column(String)
    languages = Column(String)
    languages_counts = Column(String)

    using_stopwords = Column(Integer)

    len = Column(Integer)
    lines = Column(Integer)
    meaningful_lines = Column(Integer)
    words = Column(Integer)
    meaningful_words = Column(Integer)
    stopwords = Column(Integer)
    meaningful_stopwords = Column(Integer)

    header = Column(Integer)
    header_len = Column(Integer)
    header_lines = Column(Integer)
    header_words = Column(Integer)
    header_stopwords = Column(Integer)

    h1 = Column(Integer)
    h1_len = Column(Integer)
    h1_lines = Column(Integer)
    h1_words = Column(Integer)
    h1_stopwords = Column(Integer)

    h2 = Column(Integer)
    h2_len = Column(Integer)
    h2_lines = Column(Integer)
    h2_words = Column(Integer)
    h2_stopwords = Column(Integer)

    h3 = Column(Integer)
    h3_len = Column(Integer)
    h3_lines = Column(Integer)
    h3_words = Column(Integer)
    h3_stopwords = Column(Integer)

    h4 = Column(Integer)
    h4_len = Column(Integer)
    h4_lines = Column(Integer)
    h4_words = Column(Integer)
    h4_stopwords = Column(Integer)

    h5 = Column(Integer)
    h5_len = Column(Integer)
    h5_lines = Column(Integer)
    h5_words = Column(Integer)
    h5_stopwords = Column(Integer)

    h6 = Column(Integer)
    h6_len = Column(Integer)
    h6_lines = Column(Integer)
    h6_words = Column(Integer)
    h6_stopwords = Column(Integer)

    hrule = Column(Integer)

    list = Column(Integer)
    list_len = Column(Integer)
    list_lines = Column(Integer)
    list_items = Column(Integer)
    list_words = Column(Integer)
    list_stopwords = Column(Integer)

    table = Column(Integer)
    table_len = Column(Integer)
    table_lines = Column(Integer)
    table_rows = Column(Integer)
    table_cells = Column(Integer)
    table_words = Column(Integer)
    table_stopwords = Column(Integer)

    p = Column(Integer)
    p_len = Column(Integer)
    p_lines = Column(Integer)
    p_words = Column(Integer)
    p_stopwords = Column(Integer)

    quote = Column(Integer)
    quote_len = Column(Integer)
    quote_lines = Column(Integer)
    quote_words = Column(Integer)
    quote_stopwords = Column(Integer)

    code = Column(Integer)
    code_len = Column(Integer)
    code_lines = Column(Integer)
    code_words = Column(Integer)
    code_stopwords = Column(Integer)

    image = Column(Integer)
    image_len = Column(Integer)
    image_words = Column(Integer)
    image_stopwords = Column(Integer)

    link = Column(Integer)
    link_len = Column(Integer)
    link_words = Column(Integer)
    link_stopwords = Column(Integer)

    autolink = Column(Integer)
    autolink_len = Column(Integer)
    autolink_words = Column(Integer)
    autolink_stopwords = Column(Integer)

    codespan = Column(Integer)
    codespan_len = Column(Integer)
    codespan_words = Column(Integer)
    codespan_stopwords = Column(Integer)

    emphasis = Column(Integer)
    emphasis_len = Column(Integer)
    emphasis_words = Column(Integer)
    emphasis_stopwords = Column(Integer)

    double_emphasis = Column(Integer)
    double_emphasis_len = Column(Integer)
    double_emphasis_words = Column(Integer)
    double_emphasis_stopwords = Column(Integer)

    strikethrough = Column(Integer)
    strikethrough_len = Column(Integer)
    strikethrough_words = Column(Integer)
    strikethrough_stopwords = Column(Integer)

    html = Column(Integer)
    html_len = Column(Integer)
    html_lines = Column(Integer)

    math = Column(Integer)
    math_len = Column(Integer)
    math_words = Column(Integer)
    math_stopwords = Column(Integer)

    block_math = Column(Integer)
    block_math_len = Column(Integer)
    block_math_lines = Column(Integer)
    block_math_words = Column(Integer)
    block_math_stopwords = Column(Integer)

    latex = Column(Integer)
    latex_len = Column(Integer)
    latex_lines = Column(Integer)
    latex_words = Column(Integer)
    latex_stopwords = Column(Integer)

    skip = Column(Integer, default=0)

    notebook_obj = many_to_one("Notebook", "notebook_markdowns_objs")
    repository_obj = many_to_one("Repository", "notebook_markdowns_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookMarkdown({0.repository_id}/{0.notebook_id}/{0.id})>"
            .format(self)
        )


class NotebookAST(Base):
    """Notebook AST Analysis Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'notebook_asts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)

    cell_count = Column(Integer)

    # Custom
    import_star = Column(Integer)

    functions_with_decorators = Column(Integer)
    classes_with_decorators = Column(Integer)
    classes_with_bases = Column(Integer)

    delname = Column(Integer)
    delattr = Column(Integer)
    delitem = Column(Integer)
    assignname = Column(Integer)
    assignattr = Column(Integer)
    assignitem = Column(Integer)

    ipython = Column(Integer)
    ipython_superset = Column(Integer)

    # Scope
    class_importfrom = Column(Integer)
    global_importfrom = Column(Integer)
    nonlocal_importfrom = Column(Integer)
    local_importfrom = Column(Integer)
    total_importfrom = Column(Integer)

    class_import = Column(Integer)
    global_import = Column(Integer)
    nonlocal_import = Column(Integer)
    local_import = Column(Integer)
    total_import = Column(Integer)

    class_assign = Column(Integer)
    global_assign = Column(Integer)
    nonlocal_assign = Column(Integer)
    local_assign = Column(Integer)
    total_assign = Column(Integer)

    class_delete = Column(Integer)
    global_delete = Column(Integer)
    nonlocal_delete = Column(Integer)
    local_delete = Column(Integer)
    total_delete = Column(Integer)

    class_functiondef = Column(Integer)
    global_functiondef = Column(Integer)
    nonlocal_functiondef = Column(Integer)
    local_functiondef = Column(Integer)
    total_functiondef = Column(Integer)

    class_classdef = Column(Integer)
    global_classdef = Column(Integer)
    nonlocal_classdef = Column(Integer)
    local_classdef = Column(Integer)
    total_classdef = Column(Integer)

    # AST
    # mod
    ast_module = Column(Integer)  # max
    ast_interactive = Column(Integer)  # zero
    ast_expression = Column(Integer)  # zero
    ast_suite = Column(Integer)  # zero

    #stmt
    ast_statements = Column(Integer)

    ast_functiondef = Column(Integer)
    ast_asyncfunctiondef = Column(Integer)
    ast_classdef = Column(Integer)
    ast_return = Column(Integer)

    ast_delete = Column(Integer)
    ast_assign = Column(Integer)
    ast_augassign = Column(Integer)
    ast_annassign = Column(Integer)

    ast_print = Column(Integer)

    ast_for = Column(Integer)
    ast_asyncfor = Column(Integer)
    ast_while = Column(Integer)
    ast_if = Column(Integer)
    ast_with = Column(Integer)
    ast_asyncwith = Column(Integer)

    ast_raise = Column(Integer)
    ast_try = Column(Integer)
    ast_tryexcept = Column(Integer)
    ast_tryfinally = Column(Integer)
    ast_assert = Column(Integer)

    ast_import = Column(Integer)
    ast_importfrom = Column(Integer)
    ast_exec = Column(Integer)
    ast_global = Column(Integer)
    ast_nonlocal = Column(Integer)
    ast_expr = Column(Integer)
    ast_pass = Column(Integer)
    ast_break = Column(Integer)
    ast_continue = Column(Integer)

    # expr
    ast_expressions = Column(Integer)

    ast_boolop = Column(Integer)
    ast_binop = Column(Integer)
    ast_unaryop = Column(Integer)
    ast_lambda = Column(Integer)
    ast_ifexp = Column(Integer)
    ast_dict = Column(Integer)
    ast_set = Column(Integer)
    ast_listcomp = Column(Integer)
    ast_setcomp = Column(Integer)
    ast_dictcomp = Column(Integer)
    ast_generatorexp = Column(Integer)

    ast_await = Column(Integer)
    ast_yield = Column(Integer)
    ast_yieldfrom = Column(Integer)

    ast_compare = Column(Integer)
    ast_call = Column(Integer)
    ast_num = Column(Integer)
    ast_str = Column(Integer)
    ast_formattedvalue = Column(Integer)
    ast_joinedstr = Column(Integer)
    ast_bytes = Column(Integer)
    ast_nameconstant = Column(Integer)
    ast_ellipsis = Column(Integer)
    ast_constant = Column(Integer)

    ast_attribute = Column(Integer)
    ast_subscript = Column(Integer)
    ast_starred = Column(Integer)
    ast_name = Column(Integer)
    ast_list = Column(Integer)
    ast_tuple = Column(Integer)

    # expr_contex
    ast_load = Column(Integer)
    ast_store = Column(Integer)
    ast_del = Column(Integer)
    ast_augload = Column(Integer)
    ast_augstore = Column(Integer)
    ast_param = Column(Integer)

    # slice
    ast_slice = Column(Integer)
    ast_index = Column(Integer)

    # boolop
    ast_and = Column(Integer)
    ast_or = Column(Integer)

    # operator
    ast_add = Column(Integer)
    ast_sub = Column(Integer)
    ast_mult = Column(Integer)
    ast_matmult = Column(Integer)
    ast_div = Column(Integer)
    ast_mod = Column(Integer)
    ast_pow = Column(Integer)
    ast_lshift = Column(Integer)
    ast_rshift = Column(Integer)
    ast_bitor = Column(Integer)
    ast_bitxor = Column(Integer)
    ast_bitand = Column(Integer)
    ast_floordiv = Column(Integer)

    # unaryop
    ast_invert = Column(Integer)
    ast_not = Column(Integer)
    ast_uadd = Column(Integer)
    ast_usub = Column(Integer)

    # cmpop
    ast_eq = Column(Integer)
    ast_noteq = Column(Integer)
    ast_lt = Column(Integer)
    ast_lte = Column(Integer)
    ast_gt = Column(Integer)
    ast_gte = Column(Integer)
    ast_is = Column(Integer)
    ast_isnot = Column(Integer)
    ast_in = Column(Integer)
    ast_notin = Column(Integer)

    # others
    ast_comprehension = Column(Integer)
    ast_excepthandler = Column(Integer)
    ast_arguments = Column(Integer)
    ast_arg = Column(Integer)
    ast_keyword = Column(Integer)
    ast_alias = Column(Integer)
    ast_withitem = Column(Integer)

    # New nodes?
    ast_others = Column(String)

    skip = Column(Integer, default=0)

    ast_extslice = Column(Integer, default=0)
    ast_repr = Column(Integer, default=0)

    notebook_obj = many_to_one("Notebook", "notebook_asts_objs")
    repository_obj = many_to_one("Repository", "notebook_asts_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookAST({0.repository_id}/{0.notebook_id}/{0.id})>"
            .format(self)
        )


class NotebookModule(Base):
    """Notebook Modules Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'notebook_modules'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)

    index = Column(String)
    index_count = Column(Integer)

    any_any = Column(String)
    any_any_count = Column(Integer)
    local_any = Column(String)
    local_any_count = Column(Integer)
    external_any = Column(String)
    external_any_count = Column(Integer)

    any_import_from = Column(String)
    any_import_from_count = Column(Integer)
    local_import_from = Column(String)
    local_import_from_count = Column(Integer)
    external_import_from = Column(String)
    external_import_from_count = Column(Integer)

    any_import = Column(String)
    any_import_count = Column(Integer)
    local_import = Column(String)
    local_import_count = Column(Integer)
    external_import = Column(String)
    external_import_count = Column(Integer)

    any_load_ext = Column(String)
    any_load_ext_count = Column(Integer)
    local_load_ext = Column(String)
    local_load_ext_count = Column(Integer)
    external_load_ext = Column(String)
    external_load_ext_count = Column(Integer)

    others = Column(String)

    skip = Column(Integer, default=0)

    notebook_obj = many_to_one("Notebook", "notebook_modules_objs")
    repository_obj = many_to_one("Repository", "notebook_modules_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookModule({0.repository_id}/{0.notebook_id}/{0.id})>"
        ).format(self)


class NotebookFeature(Base):
    """Notebook Features Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'notebook_features'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)

    index = Column(String)
    index_count = Column(Integer)

    any = Column(String)
    any_count = Column(Integer)

    shadown_ref = Column(String)
    shadown_ref_count = Column(Integer)
    output_ref = Column(String)
    output_ref_count = Column(Integer)
    system = Column(String)
    system_count = Column(Integer)
    set_next_input = Column(String)
    set_next_input_count = Column(Integer)
    input_ref = Column(String)
    input_ref_count = Column(Integer)
    magic = Column(String)
    magic_count = Column(Integer)
    run_line_magic = Column(String)
    run_line_magic_count = Column(Integer)
    run_cell_magic = Column(String)
    run_cell_magic_count = Column(Integer)
    getoutput = Column(String)
    getoutput_count = Column(Integer)
    set_hook = Column(String)
    set_hook_count = Column(Integer)

    others = Column(String)

    skip = Column(Integer, default=0)

    notebook_obj = many_to_one("Notebook", "notebook_features_objs")
    repository_obj = many_to_one("Repository", "notebook_features_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookFeature({0.repository_id}/{0.notebook_id}/{0.id})>"
        ).format(self)


class NotebookName(Base):
    """Notebook Names Table"""
    # pylint: disable=too-few-public-methods, invalid-name
    __tablename__ = 'notebook_names'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    repository_id = Column(Integer)
    notebook_id = Column(Integer)

    index = Column(String)
    index_count = Column(Integer)

    any_any = Column(String)
    any_any_counts = Column(String)
    any_class = Column(String)
    any_class_counts = Column(String)
    any_import = Column(String)
    any_import_counts = Column(String)
    any_importfrom = Column(String)
    any_importfrom_counts = Column(String)
    any_function = Column(String)
    any_function_counts = Column(String)
    any_param = Column(String)
    any_param_counts = Column(String)
    any_del = Column(String)
    any_del_counts = Column(String)
    any_load = Column(String)
    any_load_counts = Column(String)
    any_store = Column(String)
    any_store_counts = Column(String)

    nonlocal_any = Column(String)
    nonlocal_any_counts = Column(String)
    nonlocal_class = Column(String)
    nonlocal_class_counts = Column(String)
    nonlocal_import = Column(String)
    nonlocal_import_counts = Column(String)
    nonlocal_importfrom = Column(String)
    nonlocal_importfrom_counts = Column(String)
    nonlocal_function = Column(String)
    nonlocal_function_counts = Column(String)
    nonlocal_param = Column(String)
    nonlocal_param_counts = Column(String)
    nonlocal_del = Column(String)
    nonlocal_del_counts = Column(String)
    nonlocal_load = Column(String)
    nonlocal_load_counts = Column(String)
    nonlocal_store = Column(String)
    nonlocal_store_counts = Column(String)

    local_any = Column(String)
    local_any_counts = Column(String)
    local_class = Column(String)
    local_class_counts = Column(String)
    local_import = Column(String)
    local_import_counts = Column(String)
    local_importfrom = Column(String)
    local_importfrom_counts = Column(String)
    local_function = Column(String)
    local_function_counts = Column(String)
    local_param = Column(String)
    local_param_counts = Column(String)
    local_del = Column(String)
    local_del_counts = Column(String)
    local_load = Column(String)
    local_load_counts = Column(String)
    local_store = Column(String)
    local_store_counts = Column(String)

    class_any = Column(String)
    class_any_counts = Column(String)
    class_class = Column(String)
    class_class_counts = Column(String)
    class_import = Column(String)
    class_import_counts = Column(String)
    class_importfrom = Column(String)
    class_importfrom_counts = Column(String)
    class_function = Column(String)
    class_function_counts = Column(String)
    class_param = Column(String)
    class_param_counts = Column(String)
    class_del = Column(String)
    class_del_counts = Column(String)
    class_load = Column(String)
    class_load_counts = Column(String)
    class_store = Column(String)
    class_store_counts = Column(String)

    global_any = Column(String)
    global_any_counts = Column(String)
    global_class = Column(String)
    global_class_counts = Column(String)
    global_import = Column(String)
    global_import_counts = Column(String)
    global_importfrom = Column(String)
    global_importfrom_counts = Column(String)
    global_function = Column(String)
    global_function_counts = Column(String)
    global_param = Column(String)
    global_param_counts = Column(String)
    global_del = Column(String)
    global_del_counts = Column(String)
    global_load = Column(String)
    global_load_counts = Column(String)
    global_store = Column(String)
    global_store_counts = Column(String)

    main_any = Column(String)
    main_any_counts = Column(String)
    main_class = Column(String)
    main_class_counts = Column(String)
    main_import = Column(String)
    main_import_counts = Column(String)
    main_importfrom = Column(String)
    main_importfrom_counts = Column(String)
    main_function = Column(String)
    main_function_counts = Column(String)
    main_param = Column(String)
    main_param_counts = Column(String)
    main_del = Column(String)
    main_del_counts = Column(String)
    main_load = Column(String)
    main_load_counts = Column(String)
    main_store = Column(String)
    main_store_counts = Column(String)

    others = Column(String)

    skip = Column(Integer, default=0)

    notebook_obj = many_to_one("Notebook", "notebook_names_objs")
    repository_obj = many_to_one("Repository", "notebook_names_objs")

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookName({0.repository_id}/{0.notebook_id}/{0.id})>"
        ).format(self)


class Article(Base):
    """Article Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'article'
    __table_args__ = (
        ForeignKeyConstraint(
            ['journal_id'],
            ['journal.id']
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    journal_id = Column(Integer)
    name = Column(String)
    pmid = Column(Integer)
    pmc = Column(Integer)
    publisher_id = Column(Integer)
    doi = Column(String)
    subject = Column(String)
    published_date = Column(String)
    received_date = Column(String)
    accepted_date = Column(String)
    license_type = Column(String)
    copyright_statement = Column(String)
    keywords = Column(String)
    repositories = Column(String)


    repository_objs = one_to_many("Repository", "article_obj")

    @property
    def repository_urls(self):
        """Return notebook names"""
        return ext_split(self.repositories, "")

    @force_encoded_string_output
    def __repr__(self):
        return u"<Article({}:{})>".format(self.id, self.name)


class Journal(Base):
    """Journal Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'journal'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    nlm_ta = Column(String)
    iso_abbrev = Column(String)
    issn_epub = Column(String)
    publisher_name = Column(String)
    publisher_loc = Column(String)

    @force_encoded_string_output
    def __repr__(self):
        return u"<Journal({}:{})>".format(self.id, self.name)


class Author(Base):
    """Author Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'author'
    __table_args__ = (
        ForeignKeyConstraint(
            ['article_id'],
            ['article.id']
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    given_names = Column(String)
    orcid = Column(String)
    email = Column(String)
    article_id = Column(Integer)

    @force_encoded_string_output
    def __repr__(self):
        return u"<Author({0.article_id}/{0.id})>".format(self)


class RepositoryData(Base):
    """RepositoryMetadata Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'repository_data'
    __table_args__ = (
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
        ForeignKeyConstraint(
            ['article_id'],
            ['article.id']
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String)
    description = Column(String)
    created_at = Column(String)
    updated_at = Column(String)
    pushed_at = Column(String)
    size = Column(Integer)
    homepage = Column(String)
    language = Column(String)
    #owner = Column(String)
    #organization = Column(String)
    watchers = Column(Integer)
    subscribers_count = Column(Integer)
    stargazers_count = Column(Integer)
    forks_count = Column(Integer)
    network_count = Column(Integer)
    open_issues_count = Column(Integer)
    archived = Column(Boolean)
    has_issues = Column(Boolean)
    has_downloads = Column(Boolean)
    has_projects = Column(Boolean)
    has_pages = Column(Boolean)
    has_wiki = Column(Boolean)
    private = Column(Boolean, default=False)
    license_name = Column(String)
    license_key = Column(String)
    # total_commits = Column(Integer)
    total_commits_after_published_date = Column(Integer)
    total_commits_after_received_date = Column(Integer)
    total_commits_after_accepted_date = Column(Integer)
    total_releases = Column(Integer)

    repository_id = Column(Integer)
    article_id = Column(Integer)

    @force_encoded_string_output
    def __repr__(self):
        return u"<RepositoryData({0.repository_id}/{0.id})>".format(self)


class RepositoryRelease(Base):
    """RepositoryRelease Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'repository_release'
    __table_args__ = (
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
        ForeignKeyConstraint(
            ['article_id'],
            ['article.id']
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    tag_name = Column(String)
    # owner = Column(String)
    created_at = Column(String)
    published_at = Column(String)
    tarball_url = Column(String)
    prerelease = Column(String)
    repository_id = Column(Integer)
    article_id = Column(Integer)

    @force_encoded_string_output
    def __repr__(self):
        return u"<RepositoryRelease({0.repository_id}/{0.id})>".format(self)


class NotebookCodeStyle(Base):
    """NotebookCodeStyle Table"""
    # pylint: disable=invalid-name
    __tablename__ = 'notebook_code_style'
    __table_args__ = (
        ForeignKeyConstraint(
            ['notebook_id'],
            ['notebooks.id']
        ),
        ForeignKeyConstraint(
            ['repository_id'],
            ['repositories.id']
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    cell_index = Column(Integer)
    err_code = Column(String)
    err_code_desc = Column(String)
    notebook_id = Column(Integer)
    repository_id = Column(Integer)

    @force_encoded_string_output
    def __repr__(self):
        return (
            u"<NotebookCodeStyle({0.repository_id}/{0.notebook_id}/{0.id})>"
        ).format(self)


@contextmanager
def connect(echo=False, config=config):
    """Creates a context with an open SQLAlchemy session."""
    engine = create_engine(
        config.DB_CONNECTION,
        convert_unicode=True,
        echo=echo
    )
    Base.metadata.create_all(engine)
    connection = engine.connect()
    db_session = scoped_session(
        sessionmaker(autocommit=False, autoflush=True, bind=engine)
    )
    yield db_session
    db_session.close()  # pylint: disable=E1101
    connection.close()