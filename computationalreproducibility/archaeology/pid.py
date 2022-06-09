import argparse
import psutil

from config import Path


def main():
    parser = argparse.ArgumentParser(
        description="Check pid")
    parser.add_argument("-c", "--count", action='store_true',
                        help="count active processes")
    parser.add_argument("-e", "--clear", action='store_true',
                        help="clear not running processes")
    parser.add_argument("-s", "--simplify", action='store_true',
                        help="simplify output")
    args = parser.parse_args()

    if not Path(".pid").exists():
        return

    with open(".pid", "r") as fil:
        pids = fil.readlines()

    new_pids = []
    for pid in pids:
        pid = pid.strip()
        if not pid:
            continue
        try:
            process = psutil.Process(int(pid))
            if not args.count:
                cmd = process.cmdline()
                if args.simplify and len(cmd) > 20:
                    cmd = cmd[:20]
                    cmd.append("...")
                print("{}: {}".format(pid, " ".join(cmd)))
            new_pids.append(pid)
        except psutil.NoSuchProcess:
            if not args.count and not args.clear:
                print("{}: <not found>".format(pid))
    if args.count:
        print(len(new_pids))
    if args.clear:
        with open(".pid", "w") as fil:
            fil.write("\n".join(new_pids) + "\n")


if __name__ == "__main__":
    main()