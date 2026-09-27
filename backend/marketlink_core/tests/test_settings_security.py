"""S2: the settings fail closed when the environment is incomplete."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Prints the values the settings module ends up with. load_dotenv() never overrides a variable
# that is already set, so the environment given here wins over the developer's .env file.
PROBE = (
    "import marketlink_core.settings as s;"
    "print(s.DEBUG, s.ALLOWED_HOSTS, s.REST_FRAMEWORK['NUM_PROXIES'], getattr(s, 'SECURE_SSL_REDIRECT', None))"
)


def _load_settings(**env: str) -> subprocess.CompletedProcess:
    environment = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND_DIR,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_production_without_secret_key_refuses_to_start():
    result = _load_settings(DEBUG="False", SECRET_KEY="")

    assert result.returncode != 0
    assert "SECRET_KEY must be set" in result.stderr


def test_debug_is_off_when_the_variable_is_missing():
    # "" counts as set for load_dotenv, so .env cannot turn DEBUG back on; "" parses as False.
    result = _load_settings(DEBUG="", SECRET_KEY="test-only-secret", ALLOWED_HOSTS="", NUM_PROXIES="0")

    assert result.returncode == 0, result.stderr
    debug, *_ = result.stdout.split(" ", 1)
    assert debug == "False"


def test_production_defaults_are_safe():
    result = _load_settings(DEBUG="False", SECRET_KEY="test-only-secret", ALLOWED_HOSTS="api.example.com", NUM_PROXIES="1")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False ['api.example.com'] 1 True"


def test_development_still_starts_without_a_secret_key():
    result = _load_settings(DEBUG="True", SECRET_KEY="")

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("True ")
