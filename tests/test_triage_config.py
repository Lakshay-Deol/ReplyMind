"""Triage config resolution.

These tests previously asserted CWD-relative lookup -- they chdir'd into a tmp
dir and expected the import to fail. That *was* the bug: uvicorn on Render and
Vercel starts from a different working directory than local dev, so the app
raised FileNotFoundError at import time in deployment. Resolution is now
anchored to the repo root, and these tests pin that instead.
"""

import importlib
import json
from pathlib import Path

import pytest

from app.ai.triage_engine import CommentTriageEngine, TriageConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_CFG = REPO_ROOT / "app" / "config" / "triage_rules.json"


def test_canonical_config_exists():
    assert CANONICAL_CFG.exists(), "app/config/triage_rules.json is the shipped config"


def test_config_resolves_from_any_working_directory(tmp_path, monkeypatch):
    """The import must not depend on where the process was started."""
    monkeypatch.chdir(tmp_path)

    import app.ai.triage as triage_mod

    importlib.reload(triage_mod)

    assert triage_mod._CFG_PATH == CANONICAL_CFG
    assert triage_mod._CFG_PATH.is_absolute()


def test_triage_still_works_after_chdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import app.ai.triage as triage_mod

    importlib.reload(triage_mod)

    class _C:
        text = "How do I set this up?"

    assert triage_mod.triage_comment(_C()).category.value == "question"


def test_empty_config_falls_back_to_defaults(tmp_path):
    """A minimal config must load rather than crash on missing keys."""
    path = tmp_path / "triage_rules.json"
    path.write_text("{}")

    cfg = TriageConfig.load(path)

    assert cfg.spam_threshold == 0.65
    assert cfg.min_text_len == 3
    assert cfg.complaint_re is None  # no words -> no matcher
    # An engine built from it must still run without raising.
    assert CommentTriageEngine(cfg).triage_text("hello there friend") is not None


def test_missing_config_raises(tmp_path):
    with pytest.raises((FileNotFoundError, OSError)):
        TriageConfig.load(tmp_path / "does_not_exist.json")


def test_shipped_config_is_valid_json_with_expected_keys():
    data = json.loads(CANONICAL_CFG.read_text(encoding="utf-8"))
    for key in ("spam_phrases", "complaint_words", "praise_words", "hard_block_regex"):
        assert key in data, f"{key} missing from shipped triage config"
