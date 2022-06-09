"""Load markdown features"""
import argparse
import os
import sys
import ast
import tarfile
import re

import config
import consts

from contextlib import contextmanager
from collections import Counter, OrderedDict, defaultdict
from functools import wraps
from itertools import groupby

from future.utils.surrogateescape import register_surrogateescape

from db import Cell, CellFeature, CellModule, CellName, CodeAnalysis, connect
from db import RepositoryFile
from utils import vprint, StatusLogger, check_exit, savepid, to_unicode
from utils import get_pyexec, invoke, timeout, TimeoutError, SafeSession
from utils import mount_basedir, ignore_surrogates

from s5_extract_files import process_repository


class PathLocalChecker(object):
    """Check if module is local by looking at the directory"""

    def __init__(self, path):
        path = to_unicode(path)
        self.base = os.path.dirname(path)

    def exists(self, path):
        return os.path.exists(path)

    def is_local(self, module):
        """Check if module is local by checking if its package exists"""
        if module.startswith("."):
            return True
        path = self.base
        for part in module.split("."):
            path = os.path.join(path, part)
            if not self.exists(path) and not self.exists(path + u".py"):
                return False
        return True


class SetLocalChecker(PathLocalChecker):
    """Check if module is local by looking at a set"""

    def __init__(self, dirset, notebook_path):
        path = to_unicode(notebook_path)
        self.base = os.path.dirname(path)
        self.dirset = dirset

    def exists(self, path):
        path, _ = ignore_surrogates(path)
        if path[0] == "/":
            path = path[1:]
        return path in self.dirset or (path + "/") in self.dirset


class CompressedLocalChecker(PathLocalChecker):
    """Check if module is local by looking at the zip file"""

    def __init__(self, tarzip, notebook_path):
        path = to_unicode(notebook_path)
        self.base = os.path.dirname(path)
        self.tarzip = tarzip

    def exists(self, path):
        try:
            self.tarzip.getmember(path)
            return True
        except KeyError:
            return False


class CellVisitor(ast.NodeVisitor):

    def __init__(self, local_checker):
        self.counter = OrderedDict()
        custom = [
            "import_star", "functions_with_decorators",
            "classes_with_decorators", "classes_with_bases",
            "delname", "delattr", "delitem",
            "assignname", "assignattr", "assignitem",
            "ipython", "ipython_superset",
            "ast_statements", "ast_expressions",
        ]
        scoped = [
            "importfrom", "import", "assign", "delete",
            "functiondef", "classdef"
        ]
        modules = [
            "module", "interactive", "expression", "suite"
        ]
        statements = [
            "functiondef", "asyncfunctiondef", "classdef", "return",
            "delete", "assign", "augassign", "annassign", "print",
            "for", "asyncfor", "while", "if", "with", "asyncwith",
            "raise", "try", "tryexcept", "tryfinally", "assert",
            "import", "importfrom", "exec", "global", "nonlocal", "expr",
            "pass", "break", "continue"
        ]
        expressions = [
            "boolop", "binop", "unaryop", "lambda", "ifexp",
            "dict", "set", "listcomp", "setcomp", "dictcomp", "generatorexp",
            "await", "yield", "yieldfrom",
            "compare", "call", "num", "str", "formattedvalue", "joinedstr",
            "bytes", "nameconstant", "ellipsis", "constant",
            "attribute", "subscript", "starred", "name", "list", "tuple",
        ]
        others = [
            "load", "store", "del", "augload", "augstore", "param",
            "slice", "index",
            "and", "or",
            "add", "sub", "mult", "matmult", "div", "mod", "pow", "lshift",
            "rshift", "bitor", "bitxor", "bitand", "floordiv",
            "invert", "not", "uadd", "usub",
            "eq", "noteq", "lt", "lte", "gt", "gte", "is", "isnot", "in", "notin",
            "comprehension", "excepthandler", "arguments", "arg",
            "keyword", "alias", "withitem",
        ]

        for nodetype in custom:
            self.counter[nodetype] = 0
        for nodetype in scoped:
            self.counter["class_" + nodetype] = 0
            self.counter["global_" + nodetype] = 0
            self.counter["nonlocal_" + nodetype] = 0
            self.counter["local_" + nodetype] = 0
            self.counter["total_" + nodetype] = 0
        for nodetype in modules:
            self.counter["ast_" + nodetype] = 0
        for nodetype in statements:
            self.counter["ast_" + nodetype] = 0
        for nodetype in expressions:
            self.counter["ast_" + nodetype] = 0
        for nodetype in others:
            self.counter["ast_" + nodetype] = 0
        #self.counter["------"] = 0
        self.counter["ast_others"] = ""

        self.statements = set(statements)
        self.expressions = set(expressions)

        self.scope = None
        self.globals = set()
        self.nonlocals = set()

        self.ipython_features = []
        self.modules = []
        self.local_checker = local_checker
        self.names = defaultdict(Counter)

    def new_module(self, line, type_, name):
        """Insert new module"""
        self.modules.append((line, type_, name, self.local_checker.is_local(name)))

    @contextmanager
    def set_scope(self, scope):
        old_scope = self.scope
        old_globals = self.globals
        old_nonlocals = self.nonlocals
        try:
            self.scope = scope
            self.globals = set()
            self.nonlocals = set()
            yield
        finally:
            self.scope = old_scope
            self.globals = old_globals
            self.nonlocals = old_nonlocals

    def count_simple(self, name):
        if name not in self.counter:
            self.counter["ast_others"] += name + " "
        else:
            self.counter[name] += 1

    def count(self, name, varname=None, scope=None):
        if varname in self.globals:
            scope = "global"
        if varname in self.nonlocals:
            scope = "nonlocal"
        scope = scope or self.scope
        if scope is not None:
            self.counter["{}_{}".format(scope, name)] += 1
        self.counter["total_{}".format(name)] += 1
        return scope

    def count_name(self, varname, mode, scope=None):
        if varname in self.globals:
            scope = "global"
        if varname in self.nonlocals:
            scope = "nonlocal"
        scope = scope or self.scope or "main"
        self.names[(scope, mode)][varname] += 1

    def count_targets(self, targets, name, sub_name):
        for target in targets:
            if isinstance(target, ast.Name):
                self.count_simple("{}name".format(sub_name))
                self.count(name, target.id)
            if isinstance(target, ast.Attribute):
                self.count_simple("{}attr".format(sub_name))
                self.count(name)
            if isinstance(target, ast.Subscript):
                self.count_simple("{}item".format(sub_name))
                self.count(name)
            if isinstance(target, (ast.List, ast.Tuple)):
                self.count_targets(target.elts, name, sub_name)

    def visit_children(self, node, *children):
        for child in children:
            child_node = getattr(node, child, None)
            if child_node:
                if isinstance(child_node, (list, tuple)):
                    for child_part in child_node:
                        self.visit(child_part)
                else:
                    self.visit(child_node)
        if not children:
            ast.NodeVisitor.generic_visit(self, node)

    def generic_visit(self, node):
        name = type(node).__name__.lower()
        self.count_simple("ast_" + name)
        if name in self.statements:
            self.count_simple("ast_statements")
        if name in self.expressions:
            self.count_simple("ast_expressions")
        self.visit_children(node)

    def visit_FunctionDef(self, node, simple="ast_functiondef"):
        self.count_name(node.name, "function")
        self.count_simple("ast_statements")
        self.count_simple(simple)
        self.count("functiondef", node.name)
        with self.set_scope("local"):
            self.visit_children(node, "body")

        if node.decorator_list:
            self.count_simple("functions_with_decorators")

        if sys.version_info < (3, 0):
            self.visit_children(node, "args", "decorator_list")
        else:
            self.visit_children(node, "args", "decorator_list", "returns")

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node, simple="ast_asyncfunctiondef")

    def visit_ClassDef(self, node):
        self.count_name(node.name, "class")
        self.count_simple("ast_statements")
        self.count_simple("ast_classdef")
        self.count("classdef", node.name)
        with self.set_scope("class"):
            self.visit_children(node, "body")

        if node.decorator_list:
            self.count_simple("classes_with_decorators")

        if any(
            base for base in node.bases
            if not isinstance(base, ast.Name)
            or not base.id == "object"
        ):
            self.count_simple("classes_with_bases")

        if sys.version_info < (3, 0):
            self.visit_children(node, "bases", "decorator_list")
        elif sys.version_info < (3, 5):
            self.visit_children(node, "bases", "keywords", "starargs", "kwargs", "decorator_list")
        else:
            self.visit_children(node, "bases", "keywords", "decorator_list")

    def visit_Delete(self, node):
        self.count_targets(node.targets, "delete", "del")
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.count_targets(node.targets, "assign", "assign")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.count_targets([node.target], "assign", "assign")
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self.count_targets([node.target], "assign", "assign")
        self.generic_visit(node)

    def visit_For(self, node):
        self.count_targets([node.target], "assign", "assign")
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.visit_For(node)

    def visit_Import(self, node):
        """Get module from imports"""

        for import_ in node.names:
            self.new_module(node.lineno, "import", import_.name)
        for alias in node.names:
            name = alias.asname or alias.name
            self.count_name(name, "import")
            self.count("import", name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Get module from imports"""
        self.new_module(
            node.lineno, "import_from",
            ("." * (node.level or 0)) + (node.module or "")
        )
        for alias in node.names:
            name = alias.asname or alias.name
            self.count_name(name, "importfrom")
            if name == "*":
                self.count_simple("import_star")
            self.count("importfrom", name)
        self.generic_visit(node)

    def visit_Global(self, node):
        self.globals.update(node.names)
        self.generic_visit(node)

    def visit_Nonlocal(self, node):
        self.nonlocals.update(node.names)
        self.generic_visit(node)

    def visit_Call(self, node):
        """get_ipython().<method> calls"""

        func = node.func
        if not isinstance(func, ast.Attribute):
            return self.generic_visit(node)
        value = func.value
        if not isinstance(value, ast.Call):
            return self.generic_visit(node)
        value_func = value.func
        if not isinstance(value_func, ast.Name):
            return self.generic_visit(node)
        if value_func.id != "get_ipython":
            return self.generic_visit(node)
        args = node.args
        if not args:
            return self.generic_visit(node)
        if not isinstance(args[0], ast.Str):
            return self.generic_visit(node)
        if not args[0].s:
            return self.generic_visit(node)

        self.count_simple("ipython_superset")

        type_ = func.attr
        split = args[0].s.split()
        name, = split[0:1] or ['']

        self.ipython_features.append((node.lineno, node.col_offset, type_, name))

        if name == "load_ext":
            try:
                module = split[1] if len(split) > 1 else args[1].s
            except IndexError:
                return
            self.new_module(node.lineno, "load_ext", module)

    def visit_Subscript(self, node):
        """Collect In, Out, _oh, _ih"""
        self.generic_visit(node)
        if not isinstance(node.value, ast.Name):
            return
        if node.value.id in {"In", "_ih"}:
            type_ = "input_ref"
        elif node.value.id in {"Out", "_oh"}:
            type_ = "output_ref"
        else:
            return
        self.count_simple("ipython")
        self.ipython_features.append((node.lineno, node.col_offset, type_, node.value.id + "[]"))

    def visit_Name(self, node):
        """Collect _, __, ___, _i, _ii, _iii, _0, _1, _i0, _i1, ..., _sh"""
        self.count_name(node.id, type(node.ctx).__name__.lower())
        self.generic_visit(node)
        type_ = None
        underscore_num = re.findall(r"(^_(i)?\d*$)", node.id)
        many_underscores = re.findall(r"(^_{1,3}$)", node.id)
        many_is = re.findall(r"(^_i{1,3}$)", node.id)
        if underscore_num:
            type_ = "input_ref" if underscore_num[0][1] else "output_ref"
        elif many_underscores:
            type_ = "output_ref"
        elif many_is:
            type_ = "input_ref"
        elif node.id == "_sh":
            type_ = "shadown_ref"

        if type_ is not None:
            self.count_simple("ipython")
            self.ipython_features.append((node.lineno, node.col_offset, type_, node.id))


@timeout(1 * 60, use_signals=False)
def extract_features(text, checker):
    """Use cell visitor to extract features from cell text"""
    visitor = CellVisitor(checker)
    try:
        parsed = ast.parse(text)
    except ValueError:
        raise SyntaxError("Invalid escape")
    visitor.visit(parsed)
    visitor.counter["ast_others"] = visitor.counter["ast_others"].strip()
    return (
        visitor.counter,
        visitor.modules,
        visitor.ipython_features,
        visitor.names
    )

def process_code_cell(
    session, repository_id, notebook_id, cell, checker,
    skip_if_error=consts.C_PROCESS_ERROR,
    skip_if_syntaxerror=consts.C_SYNTAX_ERROR,
    skip_if_timeout=consts.C_TIMEOUT,
):
    """Process Markdown Cell to collect features"""
    if cell.processed & consts.C_PROCESS_OK:
        return 'already processed'

    retry = False
    retry |= not skip_if_error and cell.processed & consts.C_PROCESS_ERROR
    retry |= not skip_if_syntaxerror and cell.processed & consts.C_SYNTAX_ERROR
    retry |= not skip_if_timeout and cell.processed & consts.C_TIMEOUT

    if retry:
        deleted = (
            session.query(CellFeature).filter(
                CellFeature.cell_id == cell.id
            ).delete()
            + session.query(CellModule).filter(
                CellModule.cell_id == cell.id
            ).delete()
            + session.query(CellName).filter(
                CellName.cell_id == cell.id
            ).delete()
            + session.query(CodeAnalysis).filter(
                CodeAnalysis.cell_id == cell.id
            ).delete()
        )
        if deleted:
            vprint(2, "Deleted {} rows".format(deleted))
        if cell.processed & consts.C_PROCESS_ERROR:
            cell.processed -= consts.C_PROCESS_ERROR
        if cell.processed & consts.C_SYNTAX_ERROR:
            cell.processed -= consts.C_SYNTAX_ERROR
        if cell.processed & consts.C_TIMEOUT:
            cell.processed -= consts.C_TIMEOUT
        session.add(cell)

    try:
        error = False
        try:
            vprint(2, "Extracting features")
            analysis, modules, features, names = extract_features(cell.source, checker)
            processed = consts.A_OK
        except TimeoutError:
            processed = consts.A_TIMEOUT
            cell.processed |= consts.C_TIMEOUT
            error = True
        except SyntaxError:
            processed = consts.A_SYNTAX_ERROR
            cell.processed |= consts.C_SYNTAX_ERROR
            error = True
        if error:
            vprint(3, "Failed: {}".format(processed))
            analysis = {
                x.name: 0 for x in CodeAnalysis.__table__.columns
                if x.name not in {"id", "repository_id", "notebook_id", "cell_id", "index"}
            }
            analysis["ast_others"] = ""
            modules = []
            features = []
            names = {}
        else:
            vprint(3, "Ok")

        analysis["processed"] = processed

        code_analysis = CodeAnalysis(
            repository_id=repository_id,
            notebook_id=notebook_id,
            cell_id=cell.id,
            index=cell.index,
            **analysis
        )
        dependents = []
        for line, import_type, module_name, local in modules:
            dependents.append(CellModule(
                repository_id=repository_id,
                notebook_id=notebook_id,
                cell_id=cell.id,
                index=cell.index,

                line=line,
                import_type=import_type,
                module_name=module_name,
                local=local,
            ))

        for line, column, feature_name, feature_value in features:
            dependents.append(CellFeature(
                repository_id=repository_id,
                notebook_id=notebook_id,
                cell_id=cell.id,
                index=cell.index,

                line=line,
                column=column,
                feature_name="IPython/" + feature_name,
                feature_value=feature_value,
            ))

        for (scope, context), values in names.items():
            for name, count in values.items():
                dependents.append(CellName(
                    repository_id=repository_id,
                    notebook_id=notebook_id,
                    cell_id=cell.id,
                    index=cell.index,

                    scope=scope,
                    context=context,
                    name=name,
                    count=count,
                ))
        vprint(2, "Adding session objects")
        session.dependent_add(
            code_analysis, dependents, "analysis_id"
        )
        cell.processed |= consts.C_PROCESS_OK
        return "done"
    except Exception as err:
        cell.processed |= consts.C_PROCESS_ERROR
        if config.VERBOSE > 4:
            import traceback
            traceback.print_exc()
        return 'Failed to process ({})'.format(err)
    finally:
        session.add(cell)


def load_archives(session, repository):
    if not repository.processed & consts.R_EXTRACTED_FILES:
        if repository.zip_path.exists():
            vprint(1, 'Extracting files')
            result = process_repository(session, repository, skip_if_error=0)
            try:
                session.commit()
                if result != "done":
                    raise Exception("Extraction failure. Fallback")
                vprint(1, result)
            except Exception as err:
                vprint(1, 'Failed: {}'.format(err))
                try:
                    tarzip = tarfile.open(str(repository.zip_path))
                    if repository.processed & consts.R_COMPRESS_ERROR:
                        repository.processed -= consts.R_COMPRESS_ERROR
                    session.add(repository)
                except tarfile.ReadError:
                    repository.processed |= consts.R_COMPRESS_ERROR
                    session.add(repository)
                    return True, None
                zip_path = to_unicode(repository.hash_dir2)
                return False, (tarzip, zip_path)

        elif repository.path.exists():
            repo_path = to_unicode(repository.path)
            return False, (None, repo_path)
        else:
            repository.processed |= consts.R_UNAVAILABLE_FILES
            session.add(repository)
            vprint(1, "Failed to load repository. Skipping")
            return True, None

    tarzip =  {
        fil.path for fil in session.query(RepositoryFile).filter(
            RepositoryFile.repository_id == repository.id
        )
    }
    zip_path = ""
    if tarzip:
        return False, (tarzip, zip_path)
    return True, None


def load_repository(session, cell, skip_repo, repository_id, repository, archives):
    if repository_id != cell.repository_id:
        repository = cell.repository_obj
        success, msg = session.commit()
        if not success:
            vprint(0, 'Failed to save cells from repository {} due to {}'.format(
                repository, msg
            ))

        vprint(0, 'Processing repository: {}'.format(repository))
        return False, cell.repository_id, repository, "todo"

    return skip_repo, repository_id, repository, archives


def load_notebook(
    session, cell, dispatches, repository,
    skip_repo, skip_notebook, notebook_id, archives, checker
):
    if notebook_id != cell.notebook_id:
        notebook_id = cell.notebook_id
        notebook = cell.notebook_obj
        if not notebook.compatible_version:
            pyexec = get_pyexec(notebook.py_version, config.VERSIONS)
            if sys.executable != pyexec:
                dispatches.add((notebook.id, pyexec))
                return skip_repo, True, cell.notebook_id, archives, None

        if archives == "todo":
            skip_repo, archives = load_archives(session, repository)
            if skip_repo:
                return skip_repo, skip_notebook, cell.notebook_id, archives, None
        if archives is None:
            return True, True, cell.notebook_id, archives, None

        vprint(1, 'Processing notebook: {}'.format(notebook))
        name = to_unicode(notebook.name)

        tarzip, repo_path = archives

        notebook_path = os.path.join(repo_path, name)
        try:
            if isinstance(tarzip, set):
                checker = SetLocalChecker(tarzip, notebook_path)
            elif tarzip:
                checker = CompressedLocalChecker(tarzip, notebook_path)
            else:
                checker = PathLocalChecker(notebook_path)
            if not checker.exists(notebook_path):
                raise Exception("Repository content problem. Notebook not found")
            return skip_repo, False, cell.notebook_id, archives, checker
        except Exception as err:
            vprint(2, "Failed to load notebook {} due to {}".format(notebook, err))
            return skip_repo, True, cell.notebook_id, archives, checker
    return skip_repo, skip_notebook, notebook_id, archives, checker



def apply(
    session, status, dispatches, selected_notebooks,
    skip_if_error, skip_if_syntaxerror, skip_if_timeout,
    count, interval, reverse, check
):
    """Extract code cell features"""
    while selected_notebooks:
        filters = [
            Cell.processed.op('&')(consts.C_PROCESS_OK) == 0,
            Cell.processed.op('&')(skip_if_error) == 0,
            Cell.processed.op('&')(skip_if_syntaxerror) == 0,
            Cell.processed.op('&')(skip_if_timeout) == 0,
            Cell.processed.op('&')(consts.C_UNKNOWN_VERSION) == 0,  # known version
            Cell.cell_type == 'code',
            Cell.python.is_(True),
        ]
        if selected_notebooks is not True:
            filters += [
                Cell.notebook_id.in_(selected_notebooks[:30])
            ]
            selected_notebooks = selected_notebooks[30:]
        else:
            selected_notebooks = False
            if interval:
                filters += [
                    Cell.repository_id >= interval[0],
                    Cell.repository_id <= interval[1],
                ]

        query = (
            session.query(Cell)
            .filter(*filters)
        )

        if count:
            print(query.count())
            return

        if reverse:
            query = query.order_by(
                Cell.repository_id.desc(),
                Cell.notebook_id.asc(),
                Cell.index.asc(),
            )
        else:
            query = query.order_by(
                Cell.repository_id.asc(),
                Cell.notebook_id.asc(),
                Cell.index.asc(),
            )

        skip_repo = False
        repository_id = None
        repository = None
        archives = None

        skip_notebook = False
        notebook_id = None
        checker = None


        for cell in query:
            if check_exit(check):
                session.commit()
                vprint(0, 'Found .exit file. Exiting')
                return
            status.report()

            with mount_basedir():
                skip_repo, repository_id, repository, archives = load_repository(
                    session, cell, skip_repo, repository_id, repository, archives
                )
                if skip_repo:
                    continue

                skip_repo, skip_notebook, notebook_id, archives, checker = load_notebook(
                    session, cell, dispatches, repository,
                    skip_repo, skip_notebook, notebook_id, archives, checker
                )
                if skip_repo or skip_notebook:
                    continue

                vprint(2, 'Processing cell: {}'.format(cell))
                result = process_code_cell(
                    session, repository_id, notebook_id, cell, checker,
                    skip_if_error, skip_if_syntaxerror, skip_if_timeout,
                )
                vprint(2, result)
            status.count += 1
        session.commit()


def pos_apply(dispatches, retry_errors, retry_timeout, verbose):
    """Dispatch execution to other python versions"""
    key = lambda x: x[1]
    dispatches = sorted(list(dispatches), key=key)
    for pyexec, disp in groupby(dispatches, key=key):
        vprint(0, "Dispatching to {}".format(pyexec))
        extra = []
        if retry_errors:
            extra.append("-e")
        if retry_timeout:
            extra.append("-t")
        extra.append("-n")

        notebook_ids = [x[0] for x in disp]
        while notebook_ids:
            ids = notebook_ids[:20000]
            args = extra + ids
            invoke(pyexec, "-u", __file__, "-v", verbose, *args)
            notebook_ids = notebook_ids[20000:]


def main():
    """Main function"""
    register_surrogateescape()
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description='Execute repositories')
    parser.add_argument('-v', '--verbose', type=int, default=config.VERBOSE,
                        help='increase output verbosity')
    parser.add_argument("-n", "--notebooks", type=int, default=None,
                        nargs="*",
                        help="notebooks ids")
    parser.add_argument('-e', '--retry-errors', action='store_true',
                        help='retry errors')
    parser.add_argument('-s', '--retry-syntaxerrors', action='store_true',
                        help='retry syntax errors')
    parser.add_argument('-t', '--retry-timeout', action='store_true',
                        help='retry timeout')
    parser.add_argument('-i', '--interval', type=int, nargs=2,
                        default=config.REPOSITORY_INTERVAL,
                        help='repository id interval')
    parser.add_argument('-c', '--count', action='store_true',
                        help='count results')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='iterate in reverse order')
    parser.add_argument('--check', type=str, nargs='*',
                        default={'all', script_name, script_name + '.py'},
                        help='check name in .exit')

    args = parser.parse_args()
    config.VERBOSE = args.verbose
    status = None
    if not args.count:
        status = StatusLogger(script_name)
        status.report()

    dispatches = set()
    with savepid():
        with connect() as session:
            apply(
                SafeSession(session),
                status,
                dispatches,
                args.notebooks or True,
                0 if args.retry_errors else consts.C_PROCESS_ERROR,
                0 if args.retry_syntaxerrors else consts.C_SYNTAX_ERROR,
                0 if args.retry_timeout else consts.C_TIMEOUT,
                args.count,
                args.interval,
                args.reverse,
                set(args.check)
            )

        pos_apply(
            dispatches,
            args.retry_errors,
            args.retry_timeout,
            args.verbose
        )

if __name__ == '__main__':
    main()
