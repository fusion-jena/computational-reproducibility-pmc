"""Main script that calls the others"""
import main

main.ORDER = [
    "r0_article_db",
    "r1_article_metadata",
    "r2_article_repository",
    "r3_github_api",
    "s1_notebooks_and_cells",
    "r4_pycodestyle_check",
    "s2_requirement_files",
    "s3_compress",
    "s4_markdown_features",
    "s5_extract_files",
    "s6_cell_features",
    "s7_execute_repositories",
    "p0_local_possibility",
    "p1_notebook_aggregate",
    "p2_sha1_exercises",
    "r5_pmid_mesh",
]

if __name__ == "__main__":
    main.main()
