"""Load markdown features"""
import argparse
import os
import sys

import config
import consts

from collections import Counter, OrderedDict

from db import Notebook, connect, NotebookMarkdown, MarkdownFeature, Cell
from db import NotebookAST, NotebookModule, NotebookFeature, NotebookName
from db import CodeAnalysis, CellModule, CellFeature, CellName
from utils import vprint, StatusLogger, check_exit, savepid

IGNORE_COLUMNS = {
    "id", "repository_id", "notebook_id", "cell_id", "index",
    "skip", "processed",
}

MARKDOWN_COLUMNS = [
    col.name for col in MarkdownFeature.__table__.columns
    if col.name not in IGNORE_COLUMNS
    if col.name != "language"
]

AST_COLUMNS = [
    col.name for col in CodeAnalysis.__table__.columns
    if col.name not in IGNORE_COLUMNS
    if col.name != "ast_others"
]

MODULE_LOCAL = {
    True: "local",
    False: "external",
    "any": "any",
}

MODULE_TYPES = {
    "any", "import_from", "import", "load_ext"
}

FEATURES = {
    "IPython/shadown_ref": "shadown_ref",
    "IPython/output_ref": "output_ref",
    "IPython/system": "system",
    "IPython/set_next_input": "set_next_input",
    "IPython/input_ref": "input_ref",
    "IPython/magic": "magic",
    "IPython/run_line_magic": "run_line_magic",
    "IPython/run_cell_magic": "run_cell_magic",
    "IPython/getoutput": "getoutput",
    "IPython/set_hook": "set_hook",
    "any": "any",
}

NAME_SCOPES = ["any", "nonlocal", "local", "class", "global", "main"]
NAME_CONTEXTS = ["any", "class", "import", "importfrom", "function", "param", "del", "load", "store"]


def calculate_markdown(session, notebook):
    agg_markdown = {col: 0 for col in MARKDOWN_COLUMNS}
    agg_markdown["cell_count"] = 0
    markdown_languages = Counter()
    query = (
        notebook.markdown_features_objs
        #.order_by(MarkdownFeature.index.asc())
    )
    for feature in query:
        agg_markdown["cell_count"] += 1
        markdown_languages[feature.language] += 1
        for column in MARKDOWN_COLUMNS:
            agg_markdown[column] += int(getattr(feature, column))

    mc_languages = markdown_languages.most_common()
    agg_markdown["main_language"] = mc_languages[0][0] if mc_languages else "none"
    agg_markdown["languages"] = ",".join(str(lang) for lang, _ in mc_languages)
    agg_markdown["languages_counts"] = ",".join(str(count) for _, count in mc_languages)
    agg_markdown["repository_id"] = notebook.repository_id
    agg_markdown["notebook_id"] = notebook.id
    return agg_markdown


def calculate_ast(session, notebook):
    agg_ast = {col: 0 for col in AST_COLUMNS}
    agg_ast["cell_count"] = 0
    ast_others = []
    query = (
        notebook.code_analyses_objs
        #.order_by(CodeAnalysis.index.asc())
    )
    for ast in query:
        agg_ast["cell_count"] += 1
        if ast.ast_others:
            ast_others.append(ast.ast_others)
        for column in AST_COLUMNS:
            agg_ast[column] += int(getattr(ast, column))
    agg_ast["ast_others"] = ",".join(ast_others)
    agg_ast["repository_id"] = notebook.repository_id
    agg_ast["notebook_id"] = notebook.id
    return agg_ast


def calculate_modules(session, notebook):
    temp_agg = {
        (local + "_" + type_): OrderedDict()
        for _, local in MODULE_LOCAL.items()
        for type_ in MODULE_TYPES
    }
    temp_agg["index"] = OrderedDict()
    others = []
    def add_key(key, module):
        if key in temp_agg:
            temp_agg[key][module.module_name] = 1
        else:
            others.append("{}:{}".format(key, module.module_name))

    query = (
        notebook.cell_modules_objs
        .order_by(CellModule.index.asc())
    )
    for module in query:
        temp_agg["index"][str(module.index)] = 1
        local = module.local or (module.local_possibility > 0)

        key = MODULE_LOCAL[local] + "_" + module.import_type
        add_key(key, module)

        key = MODULE_LOCAL[local] + "_any"
        add_key(key, module)

        key = "any_" + module.import_type
        add_key(key, module)

        key = "any_any"
        add_key(key, module)

    agg = {}
    for attr, elements in temp_agg.items():
        agg[attr] = ",".join(elements)
        agg[attr + "_count"] = len(elements)

    agg["others"] = ",".join(others)
    agg["repository_id"] = notebook.repository_id
    agg["notebook_id"] = notebook.id
    return agg


def calculate_features(session, notebook):
    temp_agg = {
        col: OrderedDict()
        for col in FEATURES.values()
    }
    temp_agg["index"] = OrderedDict()
    others = []
    def add_feature(key, feature):
        if key in temp_agg:
            temp_agg[key][feature.feature_value] = 1
        else:
            others.append("{}:{}".format(key, feature.feature_value))
    query = (
        notebook.cell_features_objs
        .order_by(CellFeature.index.asc())
    )
    for feature in query:
        temp_agg["index"][str(feature.index)] = 1
        key = FEATURES.get(feature.feature_name, feature.feature_name)
        add_feature(key, feature)

        key = "any"
        add_feature(key, feature)
    agg = {}
    for attr, elements in temp_agg.items():
        agg[attr] = ",".join(elements)
        agg[attr + "_count"] = len(elements)

    agg["others"] = ",".join(others)
    agg["repository_id"] = notebook.repository_id
    agg["notebook_id"] = notebook.id
    return agg


def calculate_names(session, notebook):
    temp_agg = {
        (scope + "_" + context): Counter()
        for scope in NAME_SCOPES
        for context in NAME_CONTEXTS
    }
    index = OrderedDict()
    others = []
    def add_key(key, name):
        if key in temp_agg:
            temp_agg[key][name.name] += name.count
        else:
            others.append("{}:{}({})".format(key, name.name, name.count))

    query = (
        notebook.cell_names_objs
        .order_by(CellName.index.asc())
    )
    for name in query:
        index[str(name.index)] = 1
        key = name.scope + "_" + name.context
        add_key(key, name)

        key = name.scope + "_any"
        add_key(key, name)

        key = "any_" + name.context
        add_key(key, name)

        key = "any_any"
        add_key(key, name)

    agg = {}
    agg["index"] = ",".join(index)
    agg["index_count"] = len(index)
    for attr, elements in temp_agg.items():
        mc = elements.most_common()
        agg[attr] = ",".join(str(name) for name, _ in mc)
        agg[attr + "_counts"] = ",".join(str(count) for _, count in mc)

    agg["others"] = ",".join(others)
    agg["repository_id"] = notebook.repository_id
    agg["notebook_id"] = notebook.id
    return agg


def process_notebook(session, notebook, skip_if_error):
    if notebook.processed & consts.N_AGGREGATE_ERROR:
        notebook.processed -= consts.N_AGGREGATE_ERROR
        session.add(notebook)
    if notebook.processed & consts.N_AGGREGATE_OK:
        return "already processed"

    if notebook.kernel == 'no-kernel' and notebook.nbformat == '0':
        notebook.processed |= consts.N_AGGREGATE_OK
        session.add(notebook)
        return "invalid notebook format. Do not aggregate it"

    agg_markdown = calculate_markdown(session, notebook)

    if notebook.markdown_cells != agg_markdown["cell_count"]:
        notebook.processed |= consts.N_AGGREGATE_ERROR
        session.add(notebook)
        return "incomplete markdown analysis"

    if notebook.language != "python" or notebook.language_version == "unknown":
        session.add(NotebookMarkdown(**agg_markdown))
        notebook.processed |= consts.N_AGGREGATE_OK
        session.add(notebook)
        return "ok - non python notebook"

    agg_ast = calculate_ast(session, notebook)

    if notebook.code_cells != agg_ast["cell_count"]:
        notebook.processed |= consts.N_AGGREGATE_ERROR
        session.add(notebook)
        return "incomplete code analysis"

    syntax_error = bool(list(notebook.cell_objs.filter(
        Cell.processed.op("&")(consts.C_SYNTAX_ERROR) == consts.C_SYNTAX_ERROR
    )))

    if syntax_error:
        session.add(NotebookMarkdown(**agg_markdown))
        notebook.processed |= consts.N_AGGREGATE_OK
        notebook.processed |= consts.N_SYNTAX_ERROR
        session.add(notebook)
        return "ok - syntax error"

    agg_modules = calculate_modules(session, notebook)
    agg_features = calculate_features(session, notebook)
    agg_names = calculate_names(session, notebook)

    session.add(NotebookMarkdown(**agg_markdown))
    session.add(NotebookAST(**agg_ast))
    session.add(NotebookModule(**agg_modules))
    session.add(NotebookFeature(**agg_features))
    session.add(NotebookName(**agg_names))
    notebook.processed |= consts.N_AGGREGATE_OK
    session.add(notebook)

    return "ok"


def load_repository(session, notebook, repository_id):
    if repository_id != notebook.repository_id:
        try:
            session.commit()
        except Exception as err:
            vprint(0, 'Failed to save modules from repository {} due to {}'.format(
                repository_id, err
            ))

        vprint(0, 'Processing repository: {}'.format(repository_id))
        return notebook.repository_id

    return repository_id


def apply(
    session, status, skip_if_error,
    count, interval, reverse, check
):
    """Extract code cell features"""
    filters = [
        Notebook.processed.op("&")(consts.N_AGGREGATE_OK) == 0,
        Notebook.processed.op("&")(skip_if_error) == 0,
        Notebook.processed.op("&")(consts.N_GENERIC_LOAD_ERROR) == 0,
    ]
    if interval:
        filters += [
            Notebook.repository_id >= interval[0],
            Notebook.repository_id <= interval[1],
        ]

    query = (
        session.query(Notebook)
        .filter(*filters)
    )

    if count:
        print(query.count())
        return

    if reverse:
        query = query.order_by(
            Notebook.repository_id.desc(),
            Notebook.id.desc(),
        )
    else:
        query = query.order_by(
            Notebook.repository_id.asc(),
            Notebook.id.asc(),
        )

    repository_id = None

    for notebook in query:
        if check_exit(check):
            session.commit()
            vprint(0, 'Found .exit file. Exiting')
            return
        status.report()

        repository_id = load_repository(session, notebook, repository_id)

        vprint(1, 'Processing notebook: {}'.format(notebook))
        result = process_notebook(session, notebook, skip_if_error)
        vprint(1, result)
        status.count += 1
    session.commit()


def main():
    """Main function"""
    script_name = os.path.basename(__file__)[:-3]
    parser = argparse.ArgumentParser(
        description='Execute repositories')
    parser.add_argument('-v', '--verbose', type=int, default=config.VERBOSE,
                        help='increase output verbosity')
    parser.add_argument('-e', '--retry-errors', action='store_true',
                        help='retry errors')
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

    with connect() as session, savepid():
        apply(
            session,
            status,
            0 if args.retry_errors else consts.N_AGGREGATE_ERROR,
            args.count,
            args.interval,
            args.reverse,
            set(args.check)
        )

if __name__ == '__main__':
    main()
