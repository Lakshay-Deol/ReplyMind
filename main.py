from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.agent import activity_log
from app.ai.batch_drafter import batch_draft_replies
from app.ai.openai_client import OpenAIClient
from app.ai.triage import triage_comment
from app.auth.google_oauth_client import GoogleOAuthClient
from app.auth.token_manager import TokenManager
from app.auth.token_store import TokenStore
from app.config import Settings
from app.errors import RefreshTokenMissing
from app.paths import runtime_dir
from app.youtube.checkpoint_store import CheckpointStore
from app.youtube.comment_fetcher import CommentFetcher, FetchConfig
from app.youtube.replied_store import RepliedStore
from app.youtube.youtube_client import YouTubeClient

# -------------------------
# Runtime folders
# -------------------------
RUNTIME_DIR = runtime_dir()

TRIAGE_DIR = RUNTIME_DIR / "triage"
DRAFTS_DIR = RUNTIME_DIR / "drafts"
FAIL_DIR = RUNTIME_DIR / "draft_failures"

PROCESSED_DIR = RUNTIME_DIR / "processed"
REJECTED_DIR = RUNTIME_DIR / "rejected"
ERRORS_DIR = RUNTIME_DIR / "errors"

METRICS_PATH = RUNTIME_DIR / "metrics.json"

for d in (TRIAGE_DIR, DRAFTS_DIR, FAIL_DIR, PROCESSED_DIR, REJECTED_DIR, ERRORS_DIR):
    d.mkdir(parents=True, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def _clean_text(text: str) -> str:
    return " ".join((text or "").strip().split())


def _text_hash(text: str) -> str:
    norm = _clean_text(text).lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _inc_metric(key: str, n: int = 1) -> None:
    try:
        if METRICS_PATH.exists():
            data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}
    data[key] = int(data.get(key, 0)) + n
    METRICS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")



def is_demo_mode() -> bool:
    return os.getenv("REPLYMIND_MODE", "demo").lower() != "production"


def _fetch_demo() -> "list":
    """Demo source: seeded comments, no Google OAuth and no network calls."""
    from app.demo.seed import load_demo_comments, seed_demo_memory, write_demo_file

    write_demo_file()
    seed_demo_memory()
    comments = load_demo_comments()
    print(f"Demo mode: loaded {len(comments)} seeded comments (no YouTube call).")
    return comments


def _fetch_live() -> "list":
    """Production source: real YouTube Data API via the OAuth token manager."""
    s = Settings()

    if not s.CLIENT_ID or not s.CLIENT_SECRET:
        raise RuntimeError("Missing YT_CLIENT_ID / YT_CLIENT_SECRET in .env")

    if not s.YOUTUBE_CHANNEL_ID:
        raise RuntimeError("Missing YOUTUBE_CHANNEL_ID in .env")

    if not s.REFRESH_TOKEN_PATH or not s.REFRESH_TOKEN_PATH.exists():
        raise RefreshTokenMissing(
            f"Refresh token file not found at: {s.REFRESH_TOKEN_PATH}. "
            "Run `python auth_youtube.py`, or set REPLYMIND_MODE=demo to explore "
            "the product without connecting a channel."
        )

    store = TokenStore(
        refresh_token_path=s.REFRESH_TOKEN_PATH,
        cache_path=s.ACCESS_TOKEN_PATH,
    )

    oauth_client = GoogleOAuthClient(
        token_url=s.GOOGLE_TOKEN_URL,
        client_id=s.CLIENT_ID,
        client_secret=s.CLIENT_SECRET,
    )

    manager = TokenManager(
        store=store,
        oauth_client=oauth_client,
        refresh_early_seconds=s.REFRESH_EARLY_SECONDS,
    )

    access_token = manager.get_valid_access_token()
    print("✅ Startup token ready. Access token length:", len(access_token))

    yt = YouTubeClient(manager)

    fetcher = CommentFetcher(
        youtube_client=yt,
        checkpoint_store=CheckpointStore(RUNTIME_DIR / "checkpoint.json"),
        replied_store=RepliedStore(RUNTIME_DIR / "replied_ids.json", maxlen=5000),
    )

    result = fetcher.fetch_latest_for_channel(
        channel_id=s.YOUTUBE_CHANNEL_ID,
        cfg=FetchConfig(page_size=50, max_pages=5),
    )

    print("Checkpoint before:", result.checkpoint_before)
    print("Checkpoint after :", result.checkpoint_after)
    return result.new_comments


def _make_drafting_client():
    """An OpenAI client, or None to fall back to deterministic drafting.

    Demo mode must run on a fresh clone with no credentials at all, so a missing
    key downgrades drafting instead of aborting the cycle. Production still fails
    loudly -- silently shipping template replies to a real channel would be worse
    than stopping.
    """
    try:
        return OpenAIClient(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    except RuntimeError as exc:
        if is_demo_mode():
            print(f"No OpenAI key configured; using offline drafting. ({exc})")
            return None
        raise


def run_once() -> dict:
    """Fetch (or seed), dedupe, triage and draft. Returns a summary for the UI."""
    new_comments = _fetch_demo() if is_demo_mode() else _fetch_live()

    _inc_metric("fetched", len(new_comments))
    print("New comments found:", len(new_comments))

    # ===========================
    # A) Dedupe
    # ===========================
    unique_by_id = {}
    seen_hashes = set()

    for c in new_comments:
        if c.comment_id in unique_by_id:
            continue

        txt = _clean_text(c.text)
        h = _text_hash(txt)

        if h in seen_hashes and len(txt) < 80:
            continue

        unique_by_id[c.comment_id] = c
        seen_hashes.add(h)

    candidates = list(unique_by_id.values())
    _inc_metric("deduped_candidates", len(candidates))
    print(f"After dedupe: {len(candidates)} candidates")

    # ===========================
    # B) Triage
    # ===========================
    to_draft = []
    ignored = 0
    spam = 0

    for c in candidates:
        tr = triage_comment(c)

        _save_json(
            TRIAGE_DIR / f"{c.comment_id}.json",
            {
                "comment_id": c.comment_id,
                "author": getattr(c, "author", None),
                "published_at": str(getattr(c, "published_at", None)),
                "text": getattr(c, "text", None),
                "decision": tr.decision.value,
                "category": tr.category.value,
                "spam_score": tr.spam_score,
                "relevance_score": tr.relevance_score,
                "reasons": tr.reasons,
                "triaged_at": datetime.now(timezone.utc).isoformat(),  # ✅ fixed
            },
        )

        if tr.decision.value == "ignore":
            ignored += 1
            continue
        if tr.decision.value == "spam":
            spam += 1
            continue
        if tr.decision.value == "draft_reply":
            to_draft.append(c)

    _inc_metric("triage_ignored", ignored)
    _inc_metric("triage_spam", spam)
    _inc_metric("triage_to_draft", len(to_draft))

    print(f"Triage summary: to_draft={len(to_draft)}, ignored={ignored}, spam={spam}")

    # ===========================
    # B2) Audience signals + community pulse
    # ===========================
    # Imported lazily: app.monitor pulls in main.run_once at call time.
    from app.monitor import analyze_triaged_comments

    signals = analyze_triaged_comments()
    print(f"Signals detected: {len(signals)}")

    activity_log.record(
        "triage",
        "Triage sweep complete",
        f"{len(candidates)} analyzed - {len(to_draft)} to draft, {spam} spam, {ignored} ignored",
        to_draft=len(to_draft),
        spam=spam,
        ignored=ignored,
    )

    if not to_draft:
        print("✅ Nothing to draft. Done.")
        return {"drafts_saved": 0, "failures": 0, "fetched": len(new_comments), "signals": len(signals)}

    # ===========================
    # C) Batch draft with OpenAI
    # ===========================
    openai_client = _make_drafting_client()

    batch_size = 12
    total_drafts = 0
    total_failures = 0

    for i in range(0, len(to_draft), batch_size):
        batch = to_draft[i : i + batch_size]

        batch = [c for c in batch if not (DRAFTS_DIR / f"{c.comment_id}.json").exists()]
        if not batch:
            continue

        try:
            drafts, failures = batch_draft_replies(batch, openai_client)
        except RuntimeError as e:
            err = str(e)
            failures = [{"comment_id": c.comment_id, "error": err, "raw": None} for c in batch]
            total_failures += len(failures)
            _inc_metric("llm_failures", len(failures))

            _save_json(
                FAIL_DIR / f"batch_{i}_{i+len(batch)-1}.json",
                {"failures": failures, "error": err, "at": datetime.now(timezone.utc).isoformat()},  # ✅ fixed
            )
            print(f"❌ OpenAI error in batch {i//batch_size + 1}: {err}")
            if "insufficient_quota" in err or "quota" in err or "429" in err:
                print("❌ Quota/rate-limit; stopping further batches.")
                break
            continue

        by_id = {c.comment_id: c for c in batch}
        now_iso = datetime.now(timezone.utc).isoformat()  # ✅ fixed

        for d in drafts:
            orig = by_id.get(d.comment_id)

            triage_file = TRIAGE_DIR / f"{d.comment_id}.json"
            triage_reasons = []
            try:
                if triage_file.exists():
                    tri = json.loads(triage_file.read_text(encoding="utf-8"))
                    triage_reasons = tri.get("reasons", [])
            except Exception:
                triage_reasons = []

            _save_json(
                DRAFTS_DIR / f"{d.comment_id}.json",
                {
                    "comment_id": d.comment_id,
                    "reply_text": d.reply_text,
                    "category": d.category.value,
                    "confidence": d.confidence,
                    "needs_human": d.needs_human,
                    "reasons": d.reasons,
                    "author": getattr(orig, "author", None) if orig else None,
                    "published_at": str(getattr(orig, "published_at", None)) if orig else None,
                    "original_text": getattr(orig, "text", None) if orig else None,
                    "triage_reasons": triage_reasons,
                    "created_at": now_iso,
                },
            )

        total_drafts += len(drafts)
        _inc_metric("llm_drafts_saved", len(drafts))

        if failures:
            total_failures += len(failures)
            _inc_metric("llm_failures", len(failures))
            _save_json(
                FAIL_DIR / f"batch_{i}_{i+len(batch)-1}.json",
                {"failures": failures, "at": now_iso},
            )

        print(f"Batch {i//batch_size + 1}: drafts={len(drafts)} failures={len(failures)}")
        time.sleep(0.2)

    print(f"✅ Done. drafts_saved={total_drafts}, failures={total_failures}")
    print(f"Drafts saved at: {DRAFTS_DIR}")

    return {
        "drafts_saved": total_drafts,
        "failures": total_failures,
        "fetched": len(new_comments),
        "signals": len(signals),
    }


def main():
    result = run_once()
    print("UI refresh summary:", result)
    print("Next: run the review UI ->  uvicorn app.review.webapp:app --reload")


if __name__ == "__main__":
        try:
            main()
        except RefreshTokenMissing as e:
            print("❌ Setup error:", e)
        except RuntimeError as e:
            print("❌ Runtime error:", e)
        except Exception:
            import traceback
            print("💥 Unexpected error:")
            traceback.print_exc()
