"""ReplyMind review console.

Every page here reads live runtime state. The previous version rendered eight of
its fourteen pages from hardcoded markup -- the agent console was a 600ms
setTimeout printing a fixed string, memory and activity were static HTML, and
the overview fell back to invented totals. Those pages now read the persistent
memory, the signal store, the activity log and the community pulse, and the
agent console talks to the real persistent Mind over the Minds Builder API.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.agent import activity_log, agent_service, signal_store
from app.agent.community_pulse import load_community_pulse
from app.agent.memory import load_memory, record_approval, record_preference
from app.agent.minds_client import MindsClient
from app.agent.models import AgentDecision, DecisionStatus
from app.ai.opportunity_models import OpportunitySignalType
from app.ai.scoring import HIGH_PRIORITY_THRESHOLD
from app.errors import RefreshTokenMissing
from app.paths import metrics_path, runtime_dir
from app.review import design
from app.review.design import empty_state, esc, page, prio_bar
from app.review.metrics import Metrics, list_triage_by_decision, read_metrics
from app.review.sanitize import sanitize_html, to_plain_text
from app.review.stores import DraftStores

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")

app = FastAPI(
    title="ReplyMind",
    description="Persistent AI community manager for creators.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

RUNTIME_DIR = runtime_dir()
stores = DraftStores(RUNTIME_DIR)
metrics = Metrics()

SESSION_COOKIE = "replymind_session"


# ==========================================================================
# mode + operator authentication
# ==========================================================================


def current_mode() -> str:
    return os.getenv("REPLYMIND_MODE", "demo").lower()


def is_production() -> bool:
    return current_mode() == "production"


def is_hosted() -> bool:
    """True when running on a PaaS rather than someone's laptop.

    Render, Fly, Heroku and Vercel all set a recognisable marker; falling back
    to RENDER covers the deployment this repo ships a blueprint for.
    """
    return any(
        os.getenv(var)
        for var in ("RENDER", "FLY_APP_NAME", "DYNO", "VERCEL", "REPLYMIND_HOSTED")
    )


def console_token() -> str:
    return os.getenv("REPLYMIND_CONSOLE_TOKEN", "").strip()


def _session_value(token: str) -> str:
    return hashlib.sha256(f"replymind-console:{token}".encode("utf-8")).hexdigest()


def require_operator(request: Request) -> None:
    """Gate every state-changing route.

    Approving a draft publishes a real comment to a real channel. Previously
    every route was anonymous, so the "nothing is published without human
    approval" guarantee had no notion of *which* human -- anyone who could
    reach the deployed URL could publish as the creator.

    Demo mode publishes nothing, so it stays open for judges to explore.
    Production without a configured token is refused rather than left open.
    """
    token = console_token()

    if not token:
        if is_production():
            raise HTTPException(
                status_code=403,
                detail=(
                    "REPLYMIND_CONSOLE_TOKEN is not set. Production mode will not "
                    "expose publishing actions anonymously. Set the variable and "
                    "sign in at /login."
                ),
            )
        return  # demo mode: nothing reaches YouTube

    presented = request.cookies.get(SESSION_COOKIE, "")
    if not hmac.compare_digest(presented, _session_value(token)):
        raise HTTPException(status_code=401, detail="Sign in at /login to act on drafts.")


# Every page renders the Mind's connection state in the sidebar, and the Minds
# API round-trip takes 6-15s. Blocking a render on it made every page crawl;
# capping the timeout at 5s instead made the badge lie -- it reported OFFLINE
# for a Mind that was reachable, just slow.
#
# So the render never waits: it returns the last known state immediately and,
# when that state is stale, refreshes it on a background thread.
_MIND_STATE: dict = {"at": 0.0, "connected": False, "checked": False}
_MIND_TTL_SECONDS = 30.0
_MIND_LOCK = threading.Lock()
_MIND_REFRESHING = False


def _refresh_mind_state() -> None:
    global _MIND_REFRESHING
    try:
        connected = agent_service.health(client=MindsClient(timeout=30)).get("connected", False)
    except Exception:
        connected = False
    with _MIND_LOCK:
        _MIND_STATE.update(at=time.monotonic(), connected=connected, checked=True)
        _MIND_REFRESHING = False


def _mind_connected(block: bool = False) -> bool:
    """Last known Mind reachability. Never blocks a page render.

    `block=True` waits for a fresh answer -- used by /status and /health, where
    the caller is explicitly asking about the Mind rather than rendering a badge.
    """
    global _MIND_REFRESHING

    if block:
        _refresh_mind_state()
        return _MIND_STATE["connected"]

    with _MIND_LOCK:
        fresh = (time.monotonic() - _MIND_STATE["at"]) < _MIND_TTL_SECONDS
        should_refresh = not fresh and not _MIND_REFRESHING
        if should_refresh:
            _MIND_REFRESHING = True
        last_known = _MIND_STATE["connected"]

    if should_refresh:
        threading.Thread(target=_refresh_mind_state, daemon=True).start()

    return last_known


def _nav_counts() -> dict:
    try:
        return {
            "comments": len(stores.list_pending()),
            "signals": signal_store.count(),
        }
    except Exception:
        return {}


def _shell(title: str, subtitle: str, active: str, body: str, actions: str = "") -> HTMLResponse:
    return HTMLResponse(
        page(
            title,
            subtitle,
            active,
            body,
            mind_connected=_mind_connected(),
            mode=current_mode(),
            counts=_nav_counts(),
            actions=actions,
        )
    )


def _clean(text: Optional[str]) -> str:
    """Strip YouTube's anchor markup and collapse whitespace."""
    t = re.sub(r"<a\s+href=.*?>(.*?)</a>", r"\1", text or "", flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _ago(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        then = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - then
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    if mins < 1440:
        return f"{mins // 60}h ago"
    return f"{mins // 1440}d ago"


@app.on_event("startup")
def seed_demo_runtime_if_empty() -> None:
    """In demo mode, make sure a fresh deploy has something to show.

    A hosted instance starts with an empty filesystem, so the first visitor
    would land on "No data yet" and have to know to press a button. Demo mode
    reads seeded comments and never calls a paid API, so priming it on boot is
    free and makes the link work immediately. Production is left alone -- it
    must not reach for a creator's channel on startup.
    """
    if is_production():
        return
    if signal_store.count() > 0:
        return  # already primed; don't clobber a running instance

    def prime() -> None:
        try:
            from main import run_once

            result = run_once()
            activity_log.record(
                "startup",
                "Demo runtime primed on boot",
                f"{result.get('fetched', 0)} comments, {result.get('signals', 0)} signals",
            )
        except Exception as exc:
            activity_log.record("error", "Demo priming failed", str(exc))

    # On a background thread: a platform health check hits the port as soon as
    # the process is up, and a boot that blocks on a full pipeline run can be
    # marked unhealthy before it ever answers.
    threading.Thread(target=prime, daemon=True).start()


# ==========================================================================
# landing
# ==========================================================================


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    connected = _mind_connected()
    pulse = load_community_pulse()
    analyzed = pulse.total_comments_analyzed if pulse else 0

    marquee_items = (
        "PERSISTENT MEMORY",
        "AUDIENCE SIGNALS",
        "HUMAN APPROVAL",
        "MINDS BUILDER API",
        "YOUTUBE DATA API",
        "NO AUTONOMOUS PUBLISHING",
    )
    strip = "".join(
        f'<span class="label" style="color:var(--text-4)">{esc(i)}</span>' for i in marquee_items * 2
    )

    features = (
        (
            "01",
            "It remembers",
            "A persistent Mind holds the creator's tone, goals, recurring questions "
            "and every past approval — so its judgement improves instead of resetting.",
        ),
        (
            "02",
            "It finds the signal",
            "Thirteen audience signals — superfan, collaboration, purchase intent, "
            "complaint, toxicity, spam — scored and ranked, not just sentiment.",
        ),
        (
            "03",
            "It waits for you",
            "The Mind recommends. The creator decides. Nothing reaches the channel "
            "without an explicit, recorded approval.",
        ),
    )
    feature_html = "".join(
        f'<div class="feature"><span class="label">{n}</span>'
        f"<h3>{esc(t)}</h3><p>{esc(d)}</p></div>"
        for n, t, d in features
    )

    flow = (
        "YouTube", "Triage", "Signals", "Mind", "Recommendation",
        "Human approval", "Publish", "Memory",
    )
    flow_html = '<span class="flow-arrow">→</span>'.join(
        f'<span class="flow-step">{esc(s)}</span>' for s in flow
    )

    state = "CONNECTED" if connected else "OFFLINE"
    dot = "dot" if connected else "dot off"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReplyMind — Community Mind for Creators</title>
<style>{design.CSS}{design.NETWORK_CANVAS_CSS}</style>
</head>
<body>
<canvas id="net" class="net-canvas" aria-hidden="true"></canvas>
<div class="landing">
  <nav class="landing-nav">
    <div class="brand">
      <span class="brand-name">ReplyMind</span>
      <span class="brand-sub">Community Mind</span>
    </div>
    <div style="display:flex;gap:10px;align-items:center">
      <span class="label"><span class="{dot}"></span> MIND {state}</span>
      <a href="/overview" class="btn btn-solid">Open Console</a>
    </div>
  </nav>

  <section class="hero">
    <span class="label">Creative Minds Jam · Build what creators need next</span>
    <h1 class="display" style="margin-top:22px">One Mind that<br>knows your community.</h1>
    <p class="lede">
      Creators drown in comments and answer the same question a hundred times.
      ReplyMind is a persistent Mind that reads every conversation, remembers what
      the creator cares about, ranks what actually deserves a reply, and recommends
      the next best action — then waits for a human to say yes.
    </p>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a href="/overview" class="btn btn-solid">Open the console</a>
      <a href="/agent" class="btn">Ask the Mind</a>
      <a href="/connect" class="btn">Connect a channel</a>
    </div>
  </section>
</div>

<div class="marquee-wrap"><div class="marquee">{strip}</div></div>

<div class="landing">
  <div class="feature-grid">{feature_html}</div>

  <section style="padding:56px 0;border-bottom:1px solid var(--line)">
    <span class="label">Pipeline</span>
    <div class="flow">{flow_html}</div>
    <p class="lede" style="font-size:14px">
      Every stage writes to disk, so the console shows what actually happened —
      not a mockup. {esc(str(analyzed))} comments analyzed on this instance.
    </p>
  </section>

  <footer style="padding:34px 0;display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap">
    <span class="label">ReplyMind · Minds Builder API · YouTube Data API</span>
    <a href="/status" class="label" style="color:var(--text-3)">System status →</a>
  </footer>
</div>
<script>{design.NETWORK_CANVAS_JS}</script>
</body>
</html>""")


# ==========================================================================
# overview
# ==========================================================================


@app.get("/overview", response_class=HTMLResponse)
@app.get("/community", response_class=HTMLResponse)
def overview() -> HTMLResponse:
    pulse = load_community_pulse()
    signals = signal_store.list_signals(limit=6)
    pending = stores.list_pending()
    m = read_metrics(metrics_path())

    if not pulse and not signals:
        body = """
        <div class="notice">
          <strong>No data yet.</strong> Run one agent cycle to fetch comments, triage them,
          detect audience signals and build a community pulse. In demo mode this needs no
          credentials — press <code>Run Agent Cycle</code> above.
        </div>"""
        return _shell("Overview", "Live community intelligence", "overview", body)

    def stat(label: str, value, hint: str) -> str:
        return (
            f'<div class="stat"><div class="label">{esc(label)}</div>'
            f'<div class="stat-val">{esc(str(value))}</div>'
            f'<div class="stat-hint">{esc(hint)}</div></div>'
        )

    cards = "".join(
        [
            stat("Analyzed", pulse.total_comments_analyzed if pulse else 0, "comments triaged"),
            stat("High priority", pulse.high_priority_comments if pulse else 0, f"score ≥ {HIGH_PRIORITY_THRESHOLD}"),
            stat("Awaiting you", len(pending), "drafts to review"),
            stat("Superfans", pulse.potential_superfans if pulse else 0, "loyalty detected"),
            stat("Complaints", pulse.complaints if pulse else 0, "issues raised"),
            stat("Spam filtered", pulse.spam if pulse else 0, "auto-suppressed"),
            stat("Published", int(m.get("posted", 0)), "after approval"),
            stat("Rejected", int(m.get("rejected", 0)), "declined by you"),
        ]
    )

    top = ""
    if pulse and pulse.top_recommendation:
        top = f"""
        <div class="section">
          <div class="section-head"><span class="label-lg">Top recommendation</span>
            <a href="/signals" class="label" style="color:var(--text-3)">All signals →</a></div>
          <div class="panel">
            <div class="display-sm" style="margin-bottom:12px">{esc(pulse.top_recommendation)}</div>
            <p class="muted" style="margin:0;font-size:13.5px">{esc(pulse.explanation_for_recommendation)}</p>
          </div>
        </div>"""

    rows = "".join(
        f"""<div class="row-item">
          <div class="row-rank">{prio_bar(s.priority, HIGH_PRIORITY_THRESHOLD)}</div>
          <div class="row-body">
            <div class="row-top">
              <span class="row-author">@{esc(s.author) or "viewer"}</span>
              <span class="tag">{esc(s.signal_type.value)}</span>
              {'<span class="tag tag-solid">HIGH</span>' if s.priority >= HIGH_PRIORITY_THRESHOLD else ''}
            </div>
            <div class="row-text">{esc(_clean(s.short_text))}</div>
            <div class="row-meta">{esc(s.recommended_action)}</div>
          </div>
        </div>"""
        for s in signals
    )
    signal_block = f"""
    <div class="section">
      <div class="section-head"><span class="label-lg">Highest-priority signals</span>
        <a href="/signals" class="label" style="color:var(--text-3)">View all →</a></div>
      <div class="panel-flush rows">{rows or empty_state("No signals yet")}</div>
    </div>"""

    body = f'<div class="section"><div class="stats">{cards}</div></div>{top}{signal_block}'
    return _shell("Overview", "Live community intelligence from the last agent cycle", "overview", body)


# ==========================================================================
# review queue
# ==========================================================================


@app.get("/comments", response_class=HTMLResponse)
def review_queue(tab: str = "pending") -> HTMLResponse:
    pending = stores.list_pending()
    errors = stores.list_errors()
    items = errors if tab == "errors" else pending

    tabs = "".join(
        f'<a href="/comments?tab={key}" class="btn btn-sm{" btn-solid" if tab == key else ""}">'
        f"{esc(label)} ({count})</a>"
        for key, label, count in (
            ("pending", "Awaiting review", len(pending)),
            ("errors", "Failed to post", len(errors)),
        )
    )

    rows = []
    for d in items:
        signal_tag = ""
        try:
            stored = signal_store.list_signals(limit=10_000)
            match = next((s for s in stored if s.comment_id == d.comment_id), None)
            if match:
                signal_tag = f'<span class="tag">{esc(match.signal_type.value)}</span>'
        except Exception:
            pass

        flag = '<span class="tag tag-strong">NEEDS HUMAN</span>' if d.needs_human else ""
        rows.append(
            f"""<div class="row-item">
              <div class="row-rank">{int(round((d.confidence or 0) * 100)):02d}%</div>
              <div class="row-body">
                <div class="row-top">
                  <span class="row-author">@{esc(d.author) or "viewer"}</span>
                  {signal_tag}{flag}
                  <span class="label">{esc(_ago(d.published_at))}</span>
                </div>
                <div class="row-text">{esc(_clean(d.original_text))}</div>
                <div class="row-meta">DRAFT — {esc(_clean(d.reply_text))}</div>
              </div>
              <div class="row-actions">
                <a href="/comments/{esc(d.comment_id)}" class="btn btn-sm">Review</a>
              </div>
            </div>"""
        )

    empty = empty_state(
        "Queue empty",
        "Run an agent cycle to fetch and triage comments."
        if tab == "pending"
        else "Nothing has failed to publish.",
    )
    body = f"""
    <div class="section">
      <div class="chips">{tabs}</div>
      <div class="panel-flush rows">{"".join(rows) or empty}</div>
    </div>"""
    return _shell("Review Queue", "Drafts the Mind prepared, waiting on your decision", "comments", body)


@app.get("/comments/{comment_id}", response_class=HTMLResponse)
def comment_detail(comment_id: str) -> HTMLResponse:
    draft = stores.get_pending(comment_id) or stores.get_error(comment_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    is_error = stores.get_pending(comment_id) is None
    match = next(
        (s for s in signal_store.list_signals(limit=10_000) if s.comment_id == comment_id), None
    )

    signal_block = ""
    if match:
        signal_block = f"""
        <div class="panel" style="margin-bottom:20px">
          <div class="section-head" style="margin-bottom:14px">
            <span class="label-lg">Mind's read</span>{prio_bar(match.priority, HIGH_PRIORITY_THRESHOLD)}
          </div>
          <div class="row-top"><span class="tag tag-strong">{esc(match.signal_type.value)}</span>
            <span class="label">CONFIDENCE {int(match.confidence * 100)}%</span></div>
          <p style="margin:12px 0 0;font-size:14px;line-height:1.7;color:var(--text-2)">{esc(match.explanation)}</p>
          <div class="row-meta" style="margin-top:12px">RECOMMENDED — {esc(match.recommended_action)}</div>
        </div>"""

    reasons = " · ".join(draft.triage_reasons + draft.reasons) or "none recorded"
    action = "retry" if is_error else "approve"
    publish_label = "Approve & publish" if is_production() else "Approve (demo — not published)"

    body = f"""
    <div class="section" style="max-width:820px">
      <a href="/comments" class="label" style="color:var(--text-4)">← Review queue</a>

      <div class="panel" style="margin:16px 0 20px">
        <div class="label" style="margin-bottom:10px">Original comment</div>
        <div class="row-top">
          <span class="row-author">@{esc(draft.author) or "viewer"}</span>
          <span class="label">{esc(_ago(draft.published_at))}</span>
        </div>
        <p style="margin:10px 0 0;font-size:15px;line-height:1.7">{esc(_clean(draft.original_text))}</p>
      </div>

      {signal_block}

      <form method="post" action="/draft/{esc(comment_id)}/{action}" class="panel">
        <div class="label" style="margin-bottom:10px">Proposed reply — edit before approving</div>
        <textarea name="edited_reply_text">{esc(draft.reply_text)}</textarea>
        <div class="row-meta" style="margin:12px 0 18px">TRIAGE — {esc(reasons)}</div>
        <div style="display:flex;gap:9px;flex-wrap:wrap">
          <button type="submit" class="btn btn-solid">{esc(publish_label)}</button>
          <button type="submit" formaction="/draft/{esc(comment_id)}/reject" class="btn">Reject</button>
        </div>
      </form>
    </div>"""
    return _shell("Review Draft", f"Comment {comment_id}", "comments", body)


# ==========================================================================
# signals / moderation / superfans
# ==========================================================================


def _signal_rows(signals) -> str:
    return "".join(
        f"""<div class="row-item">
          <div class="row-rank">{prio_bar(s.priority, HIGH_PRIORITY_THRESHOLD)}</div>
          <div class="row-body">
            <div class="row-top">
              <span class="row-author">@{esc(s.author) or "viewer"}</span>
              <span class="tag">{esc(s.signal_type.value)}</span>
              {'<span class="tag tag-solid">HIGH</span>' if s.priority >= HIGH_PRIORITY_THRESHOLD else ''}
              <span class="label">{esc(_ago(s.detected_at))}</span>
            </div>
            <div class="row-text">{esc(_clean(s.short_text))}</div>
            <div class="row-meta">{esc(s.explanation)}</div>
            <div class="row-meta">RECOMMENDED — {esc(s.recommended_action)}</div>
          </div>
        </div>"""
        for s in signals
    )


@app.get("/signals", response_class=HTMLResponse)
@app.get("/recommendations", response_class=HTMLResponse)
def signals_page() -> HTMLResponse:
    signals = signal_store.list_signals(limit=120)
    body = f"""
    <div class="section">
      <div class="section-head"><span class="label-lg">{len(signals)} signals detected</span>
        <span class="label">ranked by priority</span></div>
      <div class="panel-flush rows">
        {_signal_rows(signals) or empty_state("No signals yet", "Run an agent cycle to analyze your community.")}
      </div>
    </div>"""
    return _shell("Audience Signals", "Every opportunity and risk the Mind found, ranked", "signals", body)


@app.get("/moderation", response_class=HTMLResponse)
def moderation_page() -> HTMLResponse:
    signals = signal_store.list_signals(
        signal_types=[
            OpportunitySignalType.TOXICITY,
            OpportunitySignalType.SPAM,
            OpportunitySignalType.COMPLAINT,
            OpportunitySignalType.URGENT,
        ],
        limit=120,
    )
    body = f"""
    <div class="section">
      <div class="notice" style="margin-bottom:20px">
        <strong>Nothing here is auto-actioned.</strong> Toxicity, spam, complaints and urgent
        issues are surfaced for your judgement — ReplyMind never deletes, blocks or hides
        anything on its own.
      </div>
      <div class="panel-flush rows">
        {_signal_rows(signals) or empty_state("Nothing needs moderation", "No toxicity, spam or complaints detected.")}
      </div>
    </div>"""
    return _shell("Moderation", "Risk signals raised for human review", "moderation", body)


@app.get("/superfans", response_class=HTMLResponse)
def superfans_page() -> HTMLResponse:
    signals = signal_store.list_signals(
        signal_types=[
            OpportunitySignalType.SUPERFAN,
            OpportunitySignalType.PRAISE,
            OpportunitySignalType.COLLABORATION,
            OpportunitySignalType.PURCHASE_INTENT,
        ],
        limit=120,
    )
    body = f"""
    <div class="section">
      <div class="panel-flush rows">
        {_signal_rows(signals) or empty_state("No loyalty signals yet", "Superfans, collaborators and buyers will appear here.")}
      </div>
    </div>"""
    return _shell("Superfans", "The people worth your personal attention", "superfans", body)


# ==========================================================================
# the Mind
# ==========================================================================


PRESET_QUESTIONS = (
    "What is my audience asking for?",
    "What should I create next?",
    "Who are my most engaged supporters?",
    "What is the biggest risk in my community right now?",
)


@app.get("/agent", response_class=HTMLResponse)
def agent_console() -> HTMLResponse:
    connected = _mind_connected()
    ctx = agent_service.build_context()

    chips = "".join(
        f'<button class="btn btn-sm" onclick="ask(this.dataset.q)" data-q="{esc(q)}">{esc(q)}</button>'
        for q in PRESET_QUESTIONS
    )

    # The hosted demo deliberately ships without the Minds service: every
    # question spends real cognition, and a public URL would spend the
    # creator's balance on whoever happens to visit. Say that plainly, rather
    # than telling a visitor to run a command they have no shell for.
    video = (os.getenv("REPLYMIND_DEMO_VIDEO_URL") or "").strip()
    if connected:
        offline = ""
    elif is_hosted():
        link = (
            f' See it working in the <a href="{esc(video)}" target="_blank" '
            f'rel="noopener noreferrer" style="color:var(--accent)">demo video</a>.'
            if video
            else ""
        )
        offline = f"""
        <div class="notice" style="margin-bottom:20px">
          <strong>This hosted demo runs without a live Mind.</strong>
          Everything else here is real — the triage, the signals, the priorities and
          the memory below all came from an actual pipeline run on this instance.
          The Mind is left disconnected on purpose: every question spends the
          creator's cognition credits, and a public URL would spend them on whoever
          visits.{link}
          <br><br>Run it locally with <code>minds-service</code> started and this
          console talks to the real persistent Mind over the Minds Builder API.
        </div>"""
    else:
        offline = """
        <div class="notice" style="margin-bottom:20px">
          <strong>The Mind is offline.</strong> Start the integration service with
          <code>cd minds-service &amp;&amp; npm start</code> and confirm
          <code>MINDS_BUILDER_API_KEY</code> and <code>MINDS_MIND_ID</code> are set.
          Answers below will report the failure rather than invent a reasoning trace.
        </div>"""

    body = f"""
    <div class="section" style="max-width:920px">
      {offline}
      <div class="label" style="margin-bottom:10px">Context sent with every question</div>
      <div class="panel" style="margin-bottom:24px">
        <div class="mono muted">
          profile: {esc(ctx['profile']['name'])} · {esc(ctx['profile']['niche'])}<br>
          tone: {esc(ctx['profile']['tone'])}<br>
          learned preferences: {len(ctx['learned_preferences']['approved'])} approved,
            {len(ctx['learned_preferences']['rejected'])} rejected<br>
          decisions recorded: {ctx['decisions_recorded']}<br>
          live signals in context: {len(ctx['top_signals'])}
        </div>
      </div>

      <div class="label" style="margin-bottom:10px">Ask ReplyMind</div>
      <div class="chips">{chips}</div>

      <form onsubmit="submitAsk(event)" style="display:flex;gap:9px;margin-bottom:20px">
        <input type="text" id="q" placeholder="Ask about your community…" autocomplete="off">
        <button type="submit" class="btn btn-solid" id="send">Ask</button>
      </form>

      <div class="console" id="out">
        <div class="console-line">● Ready. The Mind answers from your persistent memory and live signals.</div>
      </div>
    </div>

    <script>
      const out = document.getElementById('out');
      const send = document.getElementById('send');

      function ask(q) {{
        document.getElementById('q').value = q;
        run(q);
      }}
      function submitAsk(e) {{
        e.preventDefault();
        run(document.getElementById('q').value);
      }}

      async function run(q) {{
        if (!q || !q.trim()) return;
        send.disabled = true;
        out.innerHTML = '<div class="console-line">● Querying the Mind — reading memory and live signals…</div>';
        try {{
          const res = await fetch('/api/agent/ask', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{question: q}})
          }});
          const data = await res.json();
          const src = data.source === 'minds'
            ? '● Answered by the persistent Mind · ' + data.signals_in_context + ' live signals in context'
            : '● Mind unavailable';
          const rendered = data.answer_html
            ? data.answer_html
            : escapeHtml(data.answer);
          out.innerHTML =
            '<div class="console-line">' + escapeHtml(src) + '</div>' +
            '<div class="console-answer">' + rendered + '</div>';
        }} catch (err) {{
          out.innerHTML = '<div class="console-line">● Request failed: ' + escapeHtml(String(err)) + '</div>';
        }} finally {{
          send.disabled = false;
        }}
      }}

      function escapeHtml(s) {{
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => (
          {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]
        ));
      }}
    </script>"""
    return _shell("Ask ReplyMind", "Your persistent Mind, reasoning over real memory and signals", "agent", body)


@app.post("/api/agent/ask")
async def api_agent_ask(request: Request) -> JSONResponse:
    """Put a question to the persistent Mind. This is a real Minds Builder call."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    question = str(payload.get("question", "")).strip()
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)
    if len(question) > 1000:
        question = question[:1000]

    answer = agent_service.ask(question)
    # The Mind replies in HTML. It is untrusted model output, so it is reduced to
    # a small formatting subset before the console renders it.
    return JSONResponse(
        {
            "question": answer.question,
            "answer": to_plain_text(answer.answer) or answer.answer,
            "answer_html": sanitize_html(answer.answer),
            "source": answer.source,
            "signals_in_context": len(answer.context_used.get("top_signals", [])),
        },
        status_code=200 if answer.ok else 503,
    )


@app.get("/memory", response_class=HTMLResponse)
def memory_page() -> HTMLResponse:
    memory = load_memory()
    profile = memory.creator_profile

    def field(label: str, value: str) -> str:
        return (
            f'<div class="stat"><div class="label">{esc(label)}</div>'
            f'<div style="font-size:15px;font-weight:600;letter-spacing:-.02em;margin-top:8px">'
            f"{esc(value or '—')}</div></div>"
        )

    def listing(title: str, items, fmt=lambda x: str(x)) -> str:
        rows = "".join(
            f'<div class="row-item"><div class="row-body"><div class="row-text">{esc(fmt(i))}</div></div></div>'
            for i in items
        )
        return f"""
        <div class="section">
          <div class="section-head"><span class="label-lg">{esc(title)}</span>
            <span class="label">{len(list(items))} recorded</span></div>
          <div class="panel-flush rows">{rows or empty_state("Nothing recorded yet")}</div>
        </div>"""

    questions = sorted(memory.recurring_questions.items(), key=lambda kv: kv[1], reverse=True)[:12]
    topics = sorted(memory.recurring_topics.items(), key=lambda kv: kv[1], reverse=True)[:12]

    decisions_rows = "".join(
        f"""<div class="row-item">
          <div class="row-rank">{esc(d.decision.value[:3].upper())}</div>
          <div class="row-body">
            <div class="row-top"><span class="row-author">{esc(d.recommendation_id)}</span>
              <span class="tag">{esc(d.decision.value)}</span>
              <span class="label">{esc(_ago(d.decided_at.isoformat() if hasattr(d.decided_at, 'isoformat') else d.decided_at))}</span></div>
            <div class="row-text">{esc(_clean(d.edited_content) or "no edit")}</div>
          </div>
        </div>"""
        for d in reversed(memory.previous_decisions[-15:])
    )

    body = f"""
    <div class="section">
      <div class="stats">
        {field("Creator", profile.creator_name)}
        {field("Niche", profile.niche)}
        {field("Tone", profile.tone)}
        {field("Reply length", profile.preferred_reply_length)}
      </div>
    </div>

    {listing("Goals", profile.goals)}
    {listing("Topics to avoid", profile.topics_to_avoid)}
    {listing("Learned — approved", memory.approved_preferences)}
    {listing("Learned — rejected", memory.rejected_preferences)}
    {listing("Recurring questions", questions, lambda kv: f"{kv[0]}  ×{kv[1]}")}
    {listing("Recurring topics", topics, lambda kv: f"{kv[0]}  ×{kv[1]}")}

    <div class="section">
      <div class="section-head"><span class="label-lg">Decision history</span>
        <span class="label">{len(memory.previous_decisions)} recorded</span></div>
      <div class="panel-flush rows">{decisions_rows or empty_state("No decisions yet", "Approve or reject a draft and it is recorded here.")}</div>
    </div>"""
    return _shell("Persistent Memory", "What the Mind knows and has learned about you", "memory", body)


@app.get("/activity", response_class=HTMLResponse)
def activity_page() -> HTMLResponse:
    events = activity_log.read_events(limit=80)

    items = "".join(
        f"""<div class="tl-item{' mark' if e.kind in ('approved', 'minds_reasoning', 'published') else ''}">
          <div class="label" style="margin-bottom:5px">{esc(_ago(e.at))} · {esc(e.kind)}</div>
          <div style="font-size:14px;font-weight:600;letter-spacing:-.015em">{esc(e.title)}</div>
          <div class="muted" style="font-size:13px;margin-top:3px">{esc(e.detail)}</div>
        </div>"""
        for e in events
    )

    body = f"""
    <div class="section" style="max-width:820px">
      <div class="section-head"><span class="label-lg">{len(events)} events</span>
        <span class="label">newest first</span></div>
      {f'<div class="timeline">{items}</div>' if items else empty_state("No activity yet", "Run an agent cycle to start the log.")}
    </div>"""
    return _shell("Activity Log", "Audit trail of everything the Mind and you have done", "activity", body)


# ==========================================================================
# system
# ==========================================================================


@app.get("/connect", response_class=HTMLResponse)
def connect_page() -> HTMLResponse:
    checks = (
        ("Minds Builder API key", bool(os.getenv("MINDS_BUILDER_API_KEY"))),
        ("Mind ID", bool(os.getenv("MINDS_MIND_ID"))),
        ("Minds service reachable", _mind_connected()),
        ("OpenAI API key", bool(os.getenv("OPENAI_API_KEY"))),
        ("YouTube OAuth client", bool(os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET"))),
        ("YouTube channel ID", bool(os.getenv("YOUTUBE_CHANNEL_ID"))),
        ("Console token (publish guard)", bool(console_token())),
    )
    rows = "".join(
        f'<div class="row-item"><div class="row-body"><div class="row-top">'
        f'<span class="row-author">{esc(name)}</span>'
        f'<span class="tag{" tag-solid" if ok else ""}">{"READY" if ok else "NOT SET"}</span>'
        f"</div></div></div>"
        for name, ok in checks
    )

    body = f"""
    <div class="section" style="max-width:820px">
      <div class="notice" style="margin-bottom:22px">
        <strong>Demo mode needs nothing.</strong> ReplyMind runs its full pipeline on seeded
        comments with no credentials — press <code>Run Agent Cycle</code>. To connect a real
        channel, set <code>REPLYMIND_MODE=production</code>, run
        <code>python auth_youtube.py</code>, and start the Minds service.
      </div>
      <div class="section-head"><span class="label-lg">Configuration</span>
        <span class="label">mode: {esc(current_mode())}</span></div>
      <div class="panel-flush rows">{rows}</div>
    </div>"""
    return _shell("Connect", "What is wired up on this instance", "connect", body)


@app.get("/wallet", response_class=HTMLResponse)
def wallet_page() -> HTMLResponse:
    """Live Mind identity. Shows nothing rather than a placeholder when offline."""
    try:
        info = agent_service.health(client=MindsClient(timeout=30))
    except Exception as exc:  # pragma: no cover - defensive
        info = {"connected": False, "error": str(exc)}

    if not info.get("connected"):
        body = f"""
        <div class="section" style="max-width:760px">
          <div class="notice">
            <strong>Mind unreachable — no wallet data to show.</strong>
            <div class="mono" style="margin-top:10px;color:var(--text-4)">{esc(info.get("error", "unknown error"))}</div>
            <p style="margin:14px 0 0">
              This panel reads the wallet and cognition balance live from the Minds Builder API.
              When the service is down it reports that, rather than displaying a placeholder
              address or balance as though it were a real reading.
            </p>
          </div>
        </div>"""
        return _shell("Mind & Wallet", "On-chain identity of your persistent Mind", "wallet", body)

    def cell(label: str, value, mono: bool = False) -> str:
        style = "font-family:var(--mono);font-size:13px;word-break:break-all" if mono else (
            "font-size:18px;font-weight:600;letter-spacing:-.03em"
        )
        shown = "—" if value in (None, "") else str(value)
        return (
            f'<div class="stat"><div class="label">{esc(label)}</div>'
            f'<div style="{style};margin-top:9px">{esc(shown)}</div></div>'
        )

    cells = [
        cell("Mind", info.get("name")),
        cell("Mind ID", info.get("mindId"), mono=True),
        cell("Wallet", info.get("walletAddress"), mono=True),
        cell("Chain", info.get("chain")),
        cell("Cognition", info.get("cognition")),
    ]
    # Pad the final row: the grid paints its gaps, so an unfilled cell would
    # show as a lighter block rather than as background.
    while len(cells) % 4:
        cells.append('<div class="stat"></div>')

    body = f"""
    <div class="section">
      <div class="stats">{"".join(cells)}</div>
    </div>
    <div class="section"><div class="notice">
      Read live from the Minds Builder API through the local integration service.
      Fields the API does not return are shown as <code>—</code>.
    </div></div>"""
    return _shell("Mind & Wallet", "On-chain identity of your persistent Mind", "wallet", body)


@app.get("/status")
def status() -> JSONResponse:
    mind = agent_service.health(client=MindsClient(timeout=30))
    pulse = load_community_pulse()
    return JSONResponse(
        {
            "mode": current_mode(),
            "mind": mind,
            "publish_guard": "enabled" if console_token() else ("open (demo)" if not is_production() else "blocked"),
            "integrations": {
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "youtube_oauth": bool(os.getenv("YT_CLIENT_ID") and os.getenv("YT_CLIENT_SECRET")),
                "youtube_channel": bool(os.getenv("YOUTUBE_CHANNEL_ID")),
            },
            "runtime": {
                "pending_drafts": len(stores.list_pending()),
                "failed_posts": len(stores.list_errors()),
                "signals": signal_store.count(),
                "activity_events": len(activity_log.read_events(limit=500)),
                "pulse": pulse.model_dump() if pulse else None,
            },
        }
    )


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "mode": current_mode(), "mind": _mind_connected(block=True)})


@app.get("/metrics")
def get_metrics() -> JSONResponse:
    pulse = load_community_pulse()
    return JSONResponse(
        {
            "counters": read_metrics(metrics_path()),
            "pulse": pulse.model_dump() if pulse else None,
        }
    )


@app.get("/ignored", response_class=HTMLResponse)
def ignored_page() -> HTMLResponse:
    items = list_triage_by_decision(RUNTIME_DIR, "ignore")
    rows = "".join(
        f'<div class="row-item"><div class="row-body">'
        f'<div class="row-top"><span class="row-author">@{esc(i.get("author")) or "viewer"}</span>'
        f'<span class="tag">{esc(", ".join(i.get("reasons", [])[:2]))}</span></div>'
        f'<div class="row-text">{esc(_clean(i.get("text")))}</div></div></div>'
        for i in items
    )
    body = f'<div class="section"><div class="panel-flush rows">{rows or empty_state("Nothing ignored")}</div></div>'
    return _shell("Filtered Out", "Low-value comments triage set aside", "comments", body)


@app.get("/errors", response_class=HTMLResponse)
def errors_page() -> HTMLResponse:
    return RedirectResponse(url="/comments?tab=errors", status_code=303)


# ==========================================================================
# sign-in
# ==========================================================================


@app.get("/login", response_class=HTMLResponse)
def login_form(error: str = "") -> HTMLResponse:
    if not console_token():
        body = """
        <div class="section" style="max-width:620px"><div class="notice">
          <strong>No console token configured.</strong> Set <code>REPLYMIND_CONSOLE_TOKEN</code>
          in your environment to require sign-in before any draft can be published.
        </div></div>"""
        return _shell("Sign in", "Operator authentication", "connect", body)

    warn = f'<div class="notice" style="margin-bottom:18px">{esc(error)}</div>' if error else ""
    body = f"""
    <div class="section" style="max-width:460px">
      {warn}
      <form method="post" action="/login" class="panel">
        <div class="label" style="margin-bottom:10px">Console token</div>
        <input type="password" name="token" autocomplete="current-password" autofocus>
        <p class="muted" style="font-size:12.5px;margin:12px 0 18px">
          Required before approving, retrying or rejecting a draft — approving publishes
          a real comment to your channel.
        </p>
        <button type="submit" class="btn btn-solid">Sign in</button>
      </form>
    </div>"""
    return _shell("Sign in", "Operator authentication", "connect", body)


@app.post("/login")
def login(token: str = Form("")) -> RedirectResponse:
    expected = console_token()
    if not expected or not hmac.compare_digest(token.strip(), expected):
        return RedirectResponse(url="/login?error=Incorrect+token.", status_code=303)

    response = RedirectResponse(url="/comments", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        _session_value(expected),
        httponly=True,
        samesite="strict",
        secure=is_production(),
        max_age=60 * 60 * 12,
    )
    activity_log.record("signin", "Operator signed in")
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# ==========================================================================
# actions
# ==========================================================================


@app.post("/refresh")
def refresh(_: None = Depends(require_operator)) -> RedirectResponse:
    from main import run_once

    try:
        result = run_once()
    except RefreshTokenMissing as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{exc} Set REPLYMIND_MODE=demo to run the full pipeline without "
                "connecting a channel."
            ),
        ) from exc
    except Exception as exc:
        activity_log.record("error", "Agent cycle failed", str(exc))
        raise HTTPException(status_code=500, detail=f"Agent cycle failed: {exc}") from exc

    return RedirectResponse(url=f"/overview?fetched={result.get('fetched', 0)}", status_code=303)


def _build_poster():
    """Construct the YouTube reply poster. Only reached in production mode."""
    from app.auth.google_oauth_client import GoogleOAuthClient
    from app.auth.token_manager import TokenManager
    from app.auth.token_store import TokenStore
    from app.config import Settings
    from app.youtube.reply_poster import YouTubeReplyPoster

    s = Settings()
    if not s.REFRESH_TOKEN_PATH or not s.REFRESH_TOKEN_PATH.exists():
        raise RefreshTokenMissing(f"Refresh token file not found at: {s.REFRESH_TOKEN_PATH}")

    return YouTubeReplyPoster(
        TokenManager(
            store=TokenStore(refresh_token_path=s.REFRESH_TOKEN_PATH, cache_path=s.ACCESS_TOKEN_PATH),
            oauth_client=GoogleOAuthClient(
                token_url=s.GOOGLE_TOKEN_URL, client_id=s.CLIENT_ID, client_secret=s.CLIENT_SECRET
            ),
            refresh_early_seconds=s.REFRESH_EARLY_SECONDS,
        )
    )


def _record_decision(comment_id: str, decision: DecisionStatus, content: Optional[str]) -> None:
    record_approval(
        AgentDecision(
            recommendation_id=comment_id,
            decision=decision,
            edited_content=content,
            decided_at=datetime.now(timezone.utc),
            decided_by="creator",
        )
    )


def _publish(comment_id: str, reply_text: str, draft, source: str) -> RedirectResponse:
    """Shared approve/retry path. Demo mode records the decision without publishing."""
    if not is_production():
        stores.move_to_processed(
            draft.model_copy(update={"reply_text": reply_text}),
            extra={
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "status": "approved_demo",
                "note": "Demo mode — approval recorded, nothing sent to YouTube.",
            },
        )
        metrics.inc("approved", 1)
        _record_decision(comment_id, DecisionStatus.APPROVED, reply_text)
        activity_log.record(
            "approved",
            "Creator approved a reply (demo)",
            reply_text[:200],
            comment_id=comment_id,
        )
        return RedirectResponse(url="/comments", status_code=303)

    poster = _build_poster()
    try:
        metrics.inc("approved", 1)
        yt_response = poster.reply_with_retry(parent_comment_id=comment_id, reply_text=reply_text)
        metrics.inc("posted", 1)

        mover = stores.move_error_to_processed if source == "error" else stores.move_to_processed
        mover(
            draft.model_copy(update={"reply_text": reply_text}),
            extra={
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "youtube_response": yt_response,
                "status": "posted",
            },
        )
        _record_decision(comment_id, DecisionStatus.APPROVED, reply_text)
        activity_log.record(
            "published", "Reply published to YouTube", reply_text[:200], comment_id=comment_id
        )
        return RedirectResponse(url="/comments", status_code=303)

    except Exception as exc:
        metrics.inc("post_failures", 1)
        if source == "error":
            stores.update_error(comment_id, error=str(exc))
        else:
            stores.move_to_errors(draft.model_copy(update={"reply_text": reply_text}), error=str(exc))
        activity_log.record("error", "Publishing failed", str(exc), comment_id=comment_id)
        return RedirectResponse(url="/comments?tab=errors", status_code=303)


@app.post("/draft/{comment_id}/approve")
def approve(
    comment_id: str,
    edited_reply_text: Optional[str] = Form(None),
    _: None = Depends(require_operator),
) -> RedirectResponse:
    draft = stores.get_pending(comment_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    reply_text = (edited_reply_text or draft.reply_text or "").strip()
    if not reply_text:
        raise HTTPException(status_code=400, detail="Reply text is empty")

    # An edit is a signal about the creator's voice -- feed it back to the Mind.
    if edited_reply_text and edited_reply_text.strip() != (draft.reply_text or "").strip():
        record_preference("Creator edits drafts before approving them", approved=True)

    return _publish(comment_id, reply_text, draft, source="pending")


@app.post("/draft/{comment_id}/retry")
def retry(
    comment_id: str,
    edited_reply_text: Optional[str] = Form(None),
    _: None = Depends(require_operator),
) -> RedirectResponse:
    draft = stores.get_error(comment_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Failed draft not found")

    reply_text = (edited_reply_text or draft.reply_text or "").strip()
    if not reply_text:
        raise HTTPException(status_code=400, detail="Reply text is empty")

    return _publish(comment_id, reply_text, draft, source="error")


@app.post("/draft/{comment_id}/reject")
def reject(
    comment_id: str,
    reason: Optional[str] = Form(None),
    _: None = Depends(require_operator),
) -> RedirectResponse:
    draft = stores.get_pending(comment_id) or stores.get_error(comment_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    metrics.inc("rejected", 1)
    stores.move_to_rejected(draft, reason=reason)
    _record_decision(comment_id, DecisionStatus.REJECTED, reason)
    activity_log.record(
        "rejected", "Creator rejected a draft", reason or "no reason given", comment_id=comment_id
    )
    return RedirectResponse(url="/comments", status_code=303)
