"""Seed data so the whole product is explorable without YouTube credentials.

README previously documented a demo mode and a runtime/demo_comments.json that
did not exist, and nothing in the app branched on the mode -- so a fresh clone
hit RefreshTokenMissing on the first click. This module is that missing mode.

The comment set is chosen to exercise every branch of the opportunity detector
(superfan, content request, collaboration, purchase intent, complaint, toxicity,
spam, FAQ, urgent, trend), so the dashboards show a realistic spread rather than
a single signal type.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from app.paths import demo_comments_path
from app.youtube.model import Comment

_VIDEO = "dQw4w9WgXcQ"

# (author, text) -- ordering roughly newest-first
_RAW: List[tuple[str, str]] = [
    ("mira_builds", "Can you make a video on how you structure the backend for these agent projects? I keep getting lost once there is more than one service."),
    ("devon.ok", "This is the third video of yours I have watched today. Genuinely the clearest explanation of agent memory on YouTube."),
    ("sana_writes", "Where can I buy the notion template you showed at 12:40? Happy to pay for it."),
    ("theo_makes", "Would you want to collaborate on a follow-up? I run a channel on vector databases and I think our audiences overlap a lot."),
    ("rk_dev", "The repo link in the description doesn't work, it 404s. Same problem on your last two videos."),
    ("anon_9931", "what software do you use for the diagrams?"),
    ("priya.codes", "Urgent - I deployed this to production and the token refresh loop is spinning. Any idea what causes that?"),
    ("lena_h", "Absolutely love your channel. The pacing is perfect and you never waste my time."),
    ("marcus_t", "Honestly the audio mixing on this one is terrible, the music completely buries your voice in the middle section."),
    ("growthguy2291", "buy followers at cheapfollowers dot biz 100k in 24 hours guaranteed!!!"),
    ("jules_m", "Everyone is doing the 'build an agent in 10 minutes' challenge right now, would love to see your take on it."),
    ("sam_ok", "How do you decide when to use a persistent agent versus just a stateless API call?"),
    ("nina_dev", "Can you explain the difference between the memory store and the checkpoint store? I got confused around 8:15."),
    ("olu_a", "I have been watching since the 300 subscriber days. Huge fan, congrats on the growth."),
    ("beatriz.r", "Tutorial on deploying this to a VPS would be amazing. Render is getting expensive."),
    ("hqmedia", "how much is the full course?"),
    ("tomas_k", "The captions are out of sync after the 6 minute mark, just so you know."),
    ("aria_builds", "This helped me ship my first agent. Thank you."),
    ("dan_p", "What camera do you use?"),
    ("void_user_44", "worst tutorial ive seen, you skipped the only part that actually matters"),
]


def _comments() -> List[Comment]:
    now = datetime.now(timezone.utc)
    out: List[Comment] = []
    for i, (author, text) in enumerate(_RAW):
        published = now - timedelta(hours=i * 3 + 1)
        out.append(
            Comment(
                comment_id=f"demo-{i:03d}",
                video_id=_VIDEO,
                author=author,
                text=text,
                like_count=max(0, 47 - i * 2),
                published_at=published.isoformat().replace("+00:00", "Z"),
            )
        )
    return out


DEMO_COMMENTS: List[Comment] = _comments()


def write_demo_file() -> Path:
    """Materialise runtime/demo_comments.json (the path the README documents)."""
    path = demo_comments_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "comment_id": c.comment_id,
            "video_id": c.video_id,
            "author": c.author,
            "text": c.text,
            "like_count": c.like_count,
            "published_at": c.published_at,
        }
        for c in DEMO_COMMENTS
    ]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_demo_comments() -> List[Comment]:
    """Read the demo file if present, otherwise fall back to the built-in set."""
    path = demo_comments_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [
                Comment(
                    comment_id=item["comment_id"],
                    video_id=item.get("video_id"),
                    author=item.get("author", ""),
                    text=item.get("text", ""),
                    like_count=int(item.get("like_count", 0) or 0),
                    published_at=item.get("published_at", ""),
                )
                for item in raw
            ]
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    return DEMO_COMMENTS


def seed_demo_memory() -> None:
    """Give the Mind a creator profile to reason against on first run."""
    from app.agent.memory import load_memory, save_memory
    from app.agent.models import CreatorProfile

    memory = load_memory()
    if memory.creator_profile.creator_name != "Unknown Creator":
        return  # already personalised; leave it alone

    memory.creator_profile = CreatorProfile(
        creator_name="Demo Creator",
        niche="AI engineering and developer tooling",
        tone="Friendly, technical, no fluff",
        goals=[
            "Grow a community of builders shipping real agent projects",
            "Sell the advanced course without being pushy",
        ],
        preferred_reply_length="Short (1-2 sentences)",
        topics_to_avoid=["Politics", "Arguments about frameworks"],
        preferred_actions=["Answer questions", "Recognise superfans", "Log content ideas"],
    )
    memory.approved_preferences = [
        "Creator shortens AI-generated replies before approving them",
        "Creator approves technical explanations without marketing language",
    ]
    memory.rejected_preferences = [
        "Creator rejects replies that promise a delivery date",
    ]
    save_memory(memory)
