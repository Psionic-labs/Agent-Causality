from __future__ import annotations

import os

import sdk.env as env_module
from sdk.env import load_env_file


def test_unquoted_dotenv_value_drops_inline_comment(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENROUTER_API_KEY=sk-test # local key\n"
        'OPENROUTER_MODEL="model # keep" # ignored\n',
        encoding="utf-8",
    )
    isolated = os.environ.copy()
    isolated.pop("OPENROUTER_API_KEY", None)
    isolated.pop("OPENROUTER_MODEL", None)
    monkeypatch.setattr(env_module.os, "environ", isolated)
    load_env_file(env_file)
    assert isolated["OPENROUTER_API_KEY"] == "sk-test"
    assert isolated["OPENROUTER_MODEL"] == "model # keep"
