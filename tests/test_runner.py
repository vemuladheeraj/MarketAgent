"""Unit tests for logging setup and the application runner."""

from __future__ import annotations

import logging

import pytest

from app.config import ConfigError, load_settings
from app.config.settings import LoggingConfig
from app.logging.setup import configure_logging, get_logger, log_event
from app.main import run
from app.orchestration.runner import MarketAgentApplication


@pytest.fixture(autouse=True)
def _clean_logging():
    """Reset the market root logger between tests."""
    yield
    for handler in list(logging.getLogger("market").handlers):
        logging.getLogger("market").removeHandler(handler)


class TestLogging:
    def test_configure_logging_adds_console_handler(self):
        configure_logging(LoggingConfig(level="DEBUG"))
        logger = logging.getLogger("market")
        assert any(
            isinstance(h, logging.StreamHandler) for h in logger.handlers
        )
        assert logger.level == logging.DEBUG

    def test_get_logger_namespace(self):
        child = get_logger("data.validators")
        assert child.name == "market.data.validators"

    def test_log_event_emits_structured_line(self, capsys):
        configure_logging(LoggingConfig(level="INFO"))
        logger = get_logger("test")
        log_event(logger, "DATA_VALIDATED", "candle ok", symbol="NIFTY")
        out = capsys.readouterr().out
        assert "EVENT=DATA_VALIDATED" in out
        assert "symbol=NIFTY" in out

    def test_file_logging_writes_file(self, tmp_path):
        log_file = tmp_path / "out.log"
        configure_logging(LoggingConfig(level="INFO", file_enabled=True,
                                        file_path=str(log_file)))
        get_logger("test").info("hello file")
        for h in logging.getLogger("market").handlers:
            h.flush()
        assert log_file.exists()
        assert "hello file" in log_file.read_text(encoding="utf-8")


class TestRunner:
    def test_startup_builds_context(self, fresh_settings):
        app = MarketAgentApplication(fresh_settings)
        ctx = app.startup()
        assert ctx.settings is fresh_settings
        assert app.is_started()
        app.shutdown()
        assert not app.is_started()

    def test_summary_never_contains_secrets(self, fresh_settings):
        app = MarketAgentApplication(fresh_settings)
        summary = app._config_summary()
        assert "api_key" not in summary
        assert "token" not in summary
        app.shutdown()

    def test_config_error_exit_code_is_1(self, tmp_path):
        rc = run(["--config", str(tmp_path / "does-not-exist.yaml")])
        assert rc == 1

    def test_clean_startup_exit_code_is_0(self):
        rc = run([])
        assert rc == 0

    def test_print_config_flag(self):
        rc = run(["--print-config"])
        assert rc == 0