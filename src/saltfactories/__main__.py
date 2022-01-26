"""
CLI Entry Point.

The ``salt-factories`` CLI script is meant to be used to get an absolute path to the directory containing
``sitecustomize.py`` so that it can be injected into ``PYTHONPATH`` when running tests to track subprocesses
code coverage.
"""
import argparse
import sys

import saltfactories


def main():
    """
    Main CLI entry-point.
    """
    parser = argparse.ArgumentParser(description="PyTest Salt Factories")
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Prints the path to where the sitecustomize.py is to trigger coverage tracking on sub-processes.",
    )
    options = parser.parse_args()
    if options.coverage:
        print(str(saltfactories.CODE_ROOT_DIR / "utils" / "coverage"), file=sys.stdout, flush=True)
        parser.exit(status=0)
    parser.exit(status=1, message=parser.format_usage())


if __name__ == "__main__":
    main()
