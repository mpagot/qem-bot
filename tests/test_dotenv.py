# Copyright SUSE LLC
# SPDX-License-Identifier: MIT
"""Unit tests for .env file loading."""

import contextlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from openqabot.main import main


def test_dotenv_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that main() correctly loads variables from .env file."""
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text("QEM_BOT_TOKEN=test_token_from_env\nQEM_BOT_DRY=True\n", encoding="utf-8")

    # Clear variables from environment to start clean
    monkeypatch.delenv("QEM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("QEM_BOT_DRY", raising=False)

    with (
        patch("openqabot.main.load_dotenv") as mock_load_dotenv,
        patch("openqabot.main.app"),
        patch("os.getcwd", return_value=str(tmp_path)),
    ):

        def side_effect(*_args: Any, **_kwargs: Any) -> None:
            """Mock side effect to load from specific file."""
            # In a real scenario, load_dotenv() without arguments loads from CWD
            # For testing, we force it to load from our specific file
            load_dotenv(dotenv_path=env_file)

        mock_load_dotenv.side_effect = side_effect

        with contextlib.suppress(SystemExit):
            main()

        assert mock_load_dotenv.called
        assert os.environ.get("QEM_BOT_TOKEN") == "test_token_from_env"
        assert os.environ.get("QEM_BOT_DRY") == "True"
