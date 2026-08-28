"""Every module must resolve the same runtime directory.

Regression: seven modules each captured
`Path(os.getenv("RUNTIME_DIR", "runtime"))` at import time. Modules imported
before webapp.py called load_dotenv() got the default, so drafts were written
to one directory while signals, the pulse and the activity log went to another
-- and the dashboards read empty while the pipeline reported success.
"""

import importlib

from app import paths


def test_relative_runtime_dir_is_anchored_to_the_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", "runtime")
    monkeypatch.chdir(tmp_path)

    resolved = paths.runtime_dir()

    assert resolved.is_absolute()
    assert resolved == paths.BASE_DIR / "runtime"


def test_absolute_runtime_dir_is_respected(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    assert paths.runtime_dir() == tmp_path


def test_runtime_dir_is_resolved_lazily(monkeypatch, tmp_path):
    """Changing the env after import must take effect, so tests can redirect it."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "a"))
    first = paths.runtime_dir()
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "b"))
    assert paths.runtime_dir() != first


def test_all_stores_agree_on_one_root(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))

    from app.agent import activity_log, community_pulse, memory_store, signal_store
    from app.review.stores import DraftStores

    for module in (activity_log, community_pulse, memory_store, signal_store):
        importlib.reload(module)

    roots = {
        signal_store.signals_dir().parent,
        community_pulse.opportunities_dir().parent,
        activity_log.activity_path().parent,
        memory_store.memory_dir().parent,
        DraftStores().pending.parent,
    }
    assert roots == {tmp_path}, f"stores disagreed on the runtime root: {roots}"
