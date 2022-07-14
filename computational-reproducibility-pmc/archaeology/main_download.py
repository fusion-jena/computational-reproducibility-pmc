"""Main script that calls the others"""
import subprocess
from datetime import datetime
import config
from utils import StatusLogger
from main import execute_script

def main():
    """Main function"""
    try:
        config.BASE_DIR.mkdir(parents=True, exist_ok=True)
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        status = 1
        while status == 1:
            status = execute_script("s0_repository_crawler", [])
        print("done")
    finally:
        status = StatusLogger("main_download closed")
        status.report()

if __name__ == "__main__":
    main()
