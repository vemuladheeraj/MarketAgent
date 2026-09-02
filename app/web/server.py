"""Start the MarketAgent with both the pipeline daemon and web dashboard.

Usage::

    python -m app.web.server [--config path/to.yaml] [--web-port 8000]
"""

from __future__ import annotations

import argparse
import sys
import threading
from typing import Any

from app.config import ConfigError, load_settings
from app.logging.setup import get_logger
from app.orchestration.runner import MarketAgentApplication
from app.web.api import create_app, set_global_context

try:
    from uvicorn import run as run_uvicorn
except ImportError:
    run_uvicorn = None  # type: ignore[assignment]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="market-agent-web",
        description="MarketAgent with Web Dashboard",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to a .env file with secrets.",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8000,
        help="Port to run the web dashboard on (default: 8000).",
    )
    parser.add_argument(
        "--web-host",
        default="127.0.0.1",
        help="Host to bind the web dashboard to (default: 127.0.0.1).",
    )
    return parser


def run_pipeline_daemon(app: MarketAgentApplication, context: Any, interval_seconds: float) -> None:
    """Run the pipeline daemon in a separate thread."""
    logger = get_logger("web.server")
    try:
        logger.info("Starting pipeline daemon loop (interval: %.1fs)", interval_seconds)
        app.run_daemon(context, interval_seconds=interval_seconds)
    except KeyboardInterrupt:
        logger.info("Pipeline daemon interrupted")
    except Exception as e:
        logger.error("Pipeline daemon error: %s", e, exc_info=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = get_logger("web.server")

    try:
        settings = load_settings(config_path=args.config, env_file=args.env_file)
    except ConfigError as exc:
        print(f"CONFIG_ERROR {exc}", file=sys.stderr)
        return 1

    # Initialize the market agent application
    market_app = MarketAgentApplication(settings)
    try:
        context = market_app.startup()
    except Exception as exc:
        logger.error("Failed to start market application: %s", exc, exc_info=True)
        market_app.shutdown()
        return 2

    # Store context globally for web API access
    set_global_context(context)
    logger.info("Set global context for web API access")

    # Create the FastAPI application
    fastapi_app = create_app()

    # Start pipeline daemon in a background thread
    daemon_thread = threading.Thread(
        target=run_pipeline_daemon,
        args=(market_app, context, settings.orchestration.daemon_interval_seconds),
        daemon=True,
    )
    daemon_thread.start()
    logger.info("Pipeline daemon thread started")

    # Start the web server
    logger.info("Starting web dashboard on http://%s:%d", args.web_host, args.web_port)
    if run_uvicorn is None:
        logger.error("uvicorn is not installed; cannot run web server")
        market_app.shutdown()
        return 2

    try:
        run_uvicorn(
            fastapi_app,
            host=args.web_host,
            port=args.web_port,
            log_level="info",
        )
    except KeyboardInterrupt:
        logger.info("Web server interrupted")
    except Exception as exc:
        logger.error("Web server error: %s", exc, exc_info=True)
        return 2
    finally:
        market_app.shutdown()
        logger.info("Application shutdown complete")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
