
import argparse
import asyncio

from app.cli.commands.ping import ping_command


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
    _=subparsers.add_parser(
        "ping",
        help="Check connectivity with the Otari hosted gateway.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ping":
        exit_code = asyncio.run(ping_command())
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
