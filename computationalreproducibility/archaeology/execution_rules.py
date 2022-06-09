import consts

from collections import namedtuple
from sqlalchemy import and_, or_
from db import Notebook, Repository

ExecMode = namedtuple(
    "ExecMode",
    "processed anaconda dependencies cellorder"
)

def exec_to_num(processed, anaconda, dependencies, cellorder):
    return (
        int(cellorder)
        + 2 * int(dependencies)
        + 4 * int(anaconda)
    )

EXECUTION_MODE = {
    0: ExecMode(consts.N_ANA_F_DEP_F_ORD_F_OK, anaconda=False, dependencies=False, cellorder=False),
    1: ExecMode(consts.N_ANA_F_DEP_F_ORD_T_OK, anaconda=False, dependencies=False, cellorder=True),
    2: ExecMode(consts.N_ANA_F_DEP_T_ORD_F_OK, anaconda=False, dependencies=True, cellorder=False),
    3: ExecMode(consts.N_ANA_F_DEP_T_ORD_T_OK, anaconda=False, dependencies=True, cellorder=True),
    4: ExecMode(consts.N_ANA_T_DEP_F_ORD_F_OK, anaconda=True, dependencies=False, cellorder=False),
    5: ExecMode(consts.N_ANA_T_DEP_F_ORD_T_OK, anaconda=True, dependencies=False, cellorder=True),
    6: ExecMode(consts.N_ANA_T_DEP_T_ORD_F_OK, anaconda=True, dependencies=True, cellorder=False),
    7: ExecMode(consts.N_ANA_T_DEP_T_ORD_T_OK, anaconda=True, dependencies=True, cellorder=True),
}

EXECUTION_RULES = {
    -1: [Notebook.max_execution_count == -1],  # Without execution
    0: [],  # all notebooks
    1: [Notebook.max_execution_count != -1],  # With execution
}

DEPENDENCY_RULES = {
    -1: [  # Without dependencies
        Repository.setups_count == 0,
        Repository.requirements_count == 0,
        Repository.pipfiles_count == 0,
        Repository.pipfile_locks_count == 0,
    ],
    0: [],  # All dependencies
    1: [  # With dependencies
        ((Repository.setups_count > 0)
         |(Repository.requirements_count > 0)
         |(Repository.pipfiles_count > 0)
         |(Repository.pipfile_locks_count > 0)
        )
    ],
}

def mode_rules(with_execution, with_dependency, skip):
    processed = Notebook.processed
    exmode = {k: v.processed for k, v in EXECUTION_MODE.items()}
    deps = DEPENDENCY_RULES
    exes = EXECUTION_RULES
    if with_execution == -1:
        if with_dependency == -1:
            return [processed.op('&')(exmode[0b100] * skip) == 0]
        elif with_dependency == 1:
            return [processed.op('&')(exmode[0b010] * skip) == 0]
        return [
            and_(*(deps[-1] + mode_rules(with_execution, -1, skip)))
            | and_(*(deps[1] + mode_rules(with_execution, 1, skip)))
        ]
    elif with_execution == 1:
        if with_dependency == -1:
            return [processed.op('&')(exmode[0b101] * skip) == 0]
        elif with_dependency == 1:
            return [processed.op('&')(exmode[0b011] * skip) == 0]
        return [
            and_(*(deps[-1] + mode_rules(with_execution, -1, skip)))
            | and_(*(deps[1] + mode_rules(with_execution, 1, skip)))
        ]
    else:
        if with_dependency == -1:
            return [
                and_(*(exes[-1] + mode_rules(-1, -1, skip)))
                | and_(*(exes[1] + mode_rules(1, -1, skip)))
            ]
        elif with_dependency == 1:
            return [
                and_(*(exes[-1] + mode_rules(-1, 1, skip)))
                | and_(*(exes[1] + mode_rules(1, 1, skip)))
            ]
        return [
            or_(*(mode_rules(0, -1, skip) + mode_rules(0, 1, skip)))
        ]


def mode_rules_cell_order(with_execution, with_dependency, skip):
    processed = Notebook.processed
    exmode = {k: v.processed for k, v in EXECUTION_MODE.items()}
    deps = DEPENDENCY_RULES
    exes = EXECUTION_RULES
    if with_execution == -1:
        if with_dependency == -1:
            return [processed.op('&')(exmode[0b100] * skip) == 0]
        elif with_dependency == 1:
            return [processed.op('&')(exmode[0b010] * skip) == 0]
        return [
            and_(*(deps[-1] + mode_rules_cell_order(with_execution, -1, skip)))
            | and_(*(deps[1] + mode_rules_cell_order(with_execution, 1, skip)))
        ]
    elif with_execution == 1:
        if with_dependency == -1:
            return [processed.op('&')(exmode[0b100] * skip) == 0]
        elif with_dependency == 1:
            return [processed.op('&')(exmode[0b010] * skip) == 0]
        return [
            and_(*(deps[-1] + mode_rules_cell_order(with_execution, -1, skip)))
            | and_(*(deps[1] + mode_rules_cell_order(with_execution, 1, skip)))
        ]
    else:
        if with_dependency == -1:
            return [
                and_(*(exes[-1] + mode_rules_cell_order(-1, -1, skip)))
                | and_(*(exes[1] + mode_rules_cell_order(1, -1, skip)))
            ]
        elif with_dependency == 1:
            return [
                and_(*(exes[-1] + mode_rules_cell_order(-1, 1, skip)))
                | and_(*(exes[1] + mode_rules_cell_order(1, 1, skip)))
            ]
        return [
            or_(*(mode_rules_cell_order(0, -1, skip) + mode_rules_cell_order(0, 1, skip)))
        ]
