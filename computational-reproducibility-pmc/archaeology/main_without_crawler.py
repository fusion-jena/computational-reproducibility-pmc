"""Main script that calls the others"""
import main

main.ORDER = [
    # "s0_repository_crawler",
    "s1_notebooks_and_cells",
    "s2_requirement_files",
    "s3_compress",
    "s4_markdown_features",
    "s5_extract_files",
    "s6_cell_features",
    "s7_execute_repositories",
    "p0_local_possibility",
    "p1_notebooks_and_cells",
    "p2_sha1_exercises",
]

if __name__ == "__main__":
    main.main()
