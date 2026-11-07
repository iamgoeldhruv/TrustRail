import argparse
import asyncio

from app.cli.commands.issues import issues_command
from app.cli.commands.ping import ping_command
from app.cli.commands.seed import seed_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trustrail",
        description="TrustRail CLI - AI agent authorization and transaction control.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # trustrail ping
    subparsers.add_parser(
        "ping",
        help="Check connectivity with the Otari hosted gateway.",
    )

    # trustrail seed
    subparsers.add_parser(
        "seed",
        help="Seed the configured GitHub sandbox repository.",
    )

    # trustrail issues
    issues_parser = subparsers.add_parser(
        "issues",
        help="Discover MCP tools and retrieve GitHub issue facts through Otari.",
    )

    issues_parser.add_argument(
        "--state",
        choices=["open", "closed", "all"],
        default="open",
    )

    issues_parser.add_argument(
        "--label",
        action="append",
        dest="labels",
        help="Filter by label. Can be supplied multiple times.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ping":
        exit_code = asyncio.run(ping_command())

    elif args.command == "seed":
        exit_code = asyncio.run(seed_command())

    elif args.command == "issues":
        exit_code = asyncio.run(
            issues_command(
                state=args.state,
                labels=args.labels,
            )
        )

    else:
        parser.error("Unknown command.")

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()