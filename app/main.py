"""Application entry point.

Run with::

    python -m app.main [--config path/to.yaml] [--env-file path/to.env] [--daemon]

Exits with:
    0  clean startup/shutdown
    1  configuration error
    2  unexpected startup failure
"""

from __future__ import annotations

import argparse
import sys

from app.config import ConfigError, load_settings
from app.orchestration.runner import MarketAgentApplication


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="indian-market-agent",
        description="Indian Market Intelligence & Options Research Agent",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the YAML configuration file "
        "(default: $APP_CONFIG_PATH or config/default.yaml).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to a .env file with secrets/overrides.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the effective (non-secret) configuration and exit.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuous scheduler loop during market hours.",
    )
    return parser


def load_and_validate(args: argparse.Namespace) -> Settings:
    settings = load_settings(config_path=args.config, env_file=args.env_file)
    return settings


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = load_and_validate(args)
    except ConfigError as exc:
        print(f"CONFIG_ERROR {exc}", file=sys.stderr)
        return 1

    app = MarketAgentApplication(settings)

    try:
        context = app.startup()
    except Exception as exc:  # noqa: BLE001 - top-level boundary
        import logging

        logging.getLogger("market").error("ERROR startup failed: %s", exc, exc_info=True)
        app.shutdown()
        return 2

    if args.print_config:
        app.shutdown()
        return 0

    context.logger.info("READY MSG=market intelligence agent initialized")

    if args.daemon:
        app.run_daemon(
            context,
            interval_seconds=settings.orchestration.daemon_interval_seconds,
        )
    else:
        app.run_cycle(context)

    app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())