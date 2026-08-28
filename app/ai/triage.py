from pathlib import Path

from app.ai.triage_engine import CommentTriageEngine, TriageConfig, TriageResult

# Resolve the triage config relative to the repo root, never the process CWD.
# Uvicorn on Render/Vercel starts from a different directory than local dev,
# and a relative Path() here raised FileNotFoundError at import time.
BASE_DIR = Path(__file__).resolve().parents[2]

_SEARCH_PATHS = [
    BASE_DIR / "app" / "config" / "triage_rules.json",   # module-local (canonical)
    BASE_DIR / "config" / "triage_rules.json",           # root-level config dir
    BASE_DIR / "runtime" / "triage_rules.json",          # legacy runtime location
]
_CFG_PATH = next((p for p in _SEARCH_PATHS if p.exists()), None)
if _CFG_PATH is None:
    raise FileNotFoundError(
        "Missing triage config. Expected one of: "
        + ", ".join(p.as_posix() for p in _SEARCH_PATHS)
    )

_CFG = TriageConfig.load(_CFG_PATH)
_ENGINE = CommentTriageEngine(_CFG)


def triage_comment(comment) -> TriageResult:
    # Uses ONLY comment.text -> works with the existing YouTube comment object
    return _ENGINE.triage_text(comment.text)
