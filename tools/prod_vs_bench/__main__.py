from __future__ import annotations

import argparse
import sys

from . import compare_outputs, run_prod_eval


def main() -> None:
    parser = argparse.ArgumentParser(description="Production vs benchmark tooling.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run-prod-eval", help="Run production evaluation against benchmark outputs.")
    subparsers.add_parser("compare", help="Compare production outputs to benchmark outputs.")

    args, remainder = parser.parse_known_args()
    if args.command == "run-prod-eval":
        sys.argv = ["run-prod-eval"] + remainder
        run_prod_eval.main()
        return
    if args.command == "compare":
        sys.argv = ["compare"] + remainder
        compare_outputs.main()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
