
# Repositories
R_OK = 0
R_N_EXTRACTION = 1                   # 2 ** 0
R_N_ERROR = 2                        # 2 ** 1
R_COMPRESS_ERROR = 4                 # 2 ** 2
R_COMPRESS_OK = 8                    # 2 ** 3
R_UNAVAILABLE_FILES = 16             # 2 ** 4
R_COMMIT_MISMATCH = 32               # 2 ** 5
R_REQUIREMENTS_ERROR = 64            # 2 ** 6
R_REQUIREMENTS_OK = 128              # 2 ** 7

R_FAILED_TO_CLONE = 1024             # 2 ** 10

R_TROUBLESOME = 4096                 # 2 ** 12
R_EXTRACTED_FILES = 8192             # 2 ** 13

R_STATUSES = {
    R_OK: "load - ok",
    R_N_EXTRACTION: "notebooks and cells - ok",
    R_N_ERROR: "notebooks and cells - fail",
    R_COMPRESS_ERROR: "compress - fail",
    R_COMPRESS_OK: "compress - ok",
    R_UNAVAILABLE_FILES: "unavailable files",
    R_COMMIT_MISMATCH: "commit mismatch",
    R_REQUIREMENTS_ERROR: "requirements - fail",
    R_REQUIREMENTS_OK: "requirements - ok",
    R_FAILED_TO_CLONE: "clone - fail",
    R_TROUBLESOME: "troublesome",
    R_EXTRACTED_FILES: "extracted files",
}


# Notebooks
N_OK = 0
N_LOAD_ERROR = 1                     # 2 ** 0
N_LOAD_FORMAT_ERROR = 2              # 2 ** 1
N_LOAD_SYNTAX_ERROR = 4              # 2 ** 2
N_LOAD_TIMEOUT = 8                   # 2 ** 3
N_SYNTAX_ERROR = 16                  # 2 ** 4
N_AGGREGATE_OK = 32                  # 2 ** 5
N_AGGREGATE_ERROR = 64               # 2 ** 6
N_ANA_F_DEP_F_ORD_F_OK = 128         # 2 ** 7
N_ANA_F_DEP_F_ORD_F_ERROR = 256      # 2 ** 8
N_ANA_F_DEP_F_ORD_T_OK = 512         # 2 ** 9
N_ANA_F_DEP_F_ORD_T_ERROR = 1024     # 2 ** 10
N_ANA_F_DEP_T_ORD_F_OK = 2048        # 2 ** 11
N_ANA_F_DEP_T_ORD_F_ERROR = 4096     # 2 ** 12
N_ANA_F_DEP_T_ORD_T_OK = 8192        # 2 ** 13
N_ANA_F_DEP_T_ORD_T_ERROR = 16384    # 2 ** 14
N_ANA_T_DEP_F_ORD_F_OK = 32768       # 2 ** 15
N_ANA_T_DEP_F_ORD_F_ERROR = 65536    # 2 ** 16
N_ANA_T_DEP_F_ORD_T_OK = 131072      # 2 ** 17
N_ANA_T_DEP_F_ORD_T_ERROR = 262144   # 2 ** 18
N_ANA_T_DEP_T_ORD_F_OK = 524288      # 2 ** 19
N_ANA_T_DEP_T_ORD_F_ERROR = 1048576  # 2 ** 20
N_ANA_T_DEP_T_ORD_T_OK = 2097152     # 2 ** 21
N_ANA_T_DEP_T_ORD_T_ERROR = 4194304  # 2 ** 22

N_STOPPED = 536870912                # 2 ** 29

N_GENERIC_LOAD_ERROR = (
    N_LOAD_ERROR
    + N_LOAD_FORMAT_ERROR
    + N_LOAD_SYNTAX_ERROR
    + N_LOAD_TIMEOUT
)

N_STATUSES = {
    N_OK: "unprocessed",
    N_LOAD_ERROR: "notebooks and cells - load error",
    N_LOAD_FORMAT_ERROR: "notebooks and cells - format error",
    N_LOAD_SYNTAX_ERROR: "notebooks and cells - syntax error",
    N_LOAD_TIMEOUT: "notebooks and cells - timeout",
    N_SYNTAX_ERROR: "cells - syntax error",
    N_AGGREGATE_OK: "aggregate",
    N_AGGREGATE_ERROR: "aggregate - error",
    N_ANA_F_DEP_F_ORD_F_OK: "execute no-anaconda no-dependencies out-of-order - ok",
    N_ANA_F_DEP_F_ORD_F_ERROR: "execute no-anaconda no-dependencies out-of-order - fail",
    N_ANA_F_DEP_F_ORD_T_OK: "execute no-anaconda no-dependencies in-order - ok",
    N_ANA_F_DEP_F_ORD_T_ERROR: "execute no-anaconda no-dependencies in-order - fail",
    N_ANA_F_DEP_T_ORD_F_OK: "execute no-anaconda dependencies out-of-order - ok",
    N_ANA_F_DEP_T_ORD_F_ERROR: "execute no-anaconda dependencies out-of-order - fail",
    N_ANA_F_DEP_T_ORD_T_OK: "execute no-anaconda dependencies in-order - ok",
    N_ANA_F_DEP_T_ORD_T_ERROR: "execute no-anaconda dependencies in-order - fail",
    N_ANA_T_DEP_F_ORD_F_OK: "execute anaconda no-dependencies out-of-order - ok",
    N_ANA_T_DEP_F_ORD_F_ERROR: "execute anaconda no-dependencies out-of-order - fail",
    N_ANA_T_DEP_F_ORD_T_OK: "execute anaconda no-dependencies in-order - ok",
    N_ANA_T_DEP_F_ORD_T_ERROR: "execute anaconda no-dependencies in-order - fail",
    N_ANA_T_DEP_T_ORD_F_OK: "execute anaconda dependencies out-of-order - ok",
    N_ANA_T_DEP_T_ORD_F_ERROR: "execute anaconda dependencies out-of-order - fail",
    N_ANA_T_DEP_T_ORD_T_OK: "execute anaconda dependencies in-order - ok",
    N_ANA_T_DEP_T_ORD_T_ERROR: "execute anaconda dependencies in-order - fail",

    N_STOPPED: "notebooks and cells - interrupted",

}



# Cells
C_OK = 0
C_UNKNOWN_VERSION = 1                # 2 ** 0
C_PROCESS_ERROR = 2                  # 2 ** 1
C_PROCESS_OK = 4                     # 2 ** 2
C_TIMEOUT = 8                        # 2 ** 3
C_SYNTAX_ERROR = 16                  # 2 ** 4


C_MARKED_FOR_EXTRACTION = 128        # 2 ** 7

C_STATUSES = {
    C_OK: "unprocessed",
    C_UNKNOWN_VERSION: "unknown version",
    C_PROCESS_ERROR: "process - fail",
    C_PROCESS_OK: "process - ok",
    C_TIMEOUT: "process - timeout",
    C_SYNTAX_ERROR: "syntax error",
    C_MARKED_FOR_EXTRACTION: "marked for extraction",
}

# Code analyses

A_OK = 0
A_SYNTAX_ERROR = 16                  # 2 ** 4
A_TIMEOUT = 32                       # 2 ** 5


# Executions

E_CREATED = 0
E_INSTALLED = 1                      # 2 ** 0
E_LOADED = 2                         # 2 ** 1
E_EXCEPTION = 4                      # 2 ** 2
E_TIMEOUT = 8                        # 2 ** 3
E_SAME_RESULTS = 16                  # 2 ** 4
E_EXECUTED = 32                      # 2 ** 5

# Requirement File

F_OK = 0
