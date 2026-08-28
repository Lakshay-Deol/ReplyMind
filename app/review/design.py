"""ReplyMind design system and page shell.

Monochrome, editorial, high-contrast. No hue carries meaning -- rank and state
are expressed through weight, rule thickness and opacity, so the interface stays
legible and calm while showing dense agent output.

Extracted from webapp.py, which had grown to 1438 lines with 62KB of markup
inlined among the route handlers.
"""

from __future__ import annotations

import html
from typing import Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# tokens
# --------------------------------------------------------------------------

CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{
  --bg:#000000;
  --surface:#0a0a0a;
  --surface-2:#141414;
  --line:#1f1f1f;
  --line-2:#2e2e2e;
  --line-3:#454545;
  --text:#ffffff;
  --text-1:#e4e4e4;
  --text-2:#c4c4c4;
  --text-3:#949494;
  --text-4:#6b6b6b;
  --text-5:#454545;

  /* One accent, used only where it carries meaning: the Mind itself, and the
     signals that need the creator's attention. Everything else stays neutral,
     so orange never becomes decoration. */
  --accent:#ff6b2c;
  --accent-soft:rgba(255,107,44,.14);
  --accent-line:rgba(255,107,44,.42);

  --radius:2px;
  --sans:Inter,'SF Pro Text',-apple-system,'Segoe UI',sans-serif;
  --mono:ui-monospace,'SF Mono','Cascadia Mono',Menlo,Consolas,monospace;
  --sidebar:248px;
}

*,*::before,*::after{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body{
  margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);
  font-size:14px;line-height:1.55;
}

/* Fine film grain, as on the reference. Purely decorative. */
body::before{
  content:'';position:fixed;inset:0;z-index:9999;pointer-events:none;opacity:.035;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='256' height='256' filter='url(%23n)'/%3E%3C/svg%3E");
}

a{color:inherit;text-decoration:none}
hr{border:0;border-top:1px solid var(--line);margin:0}

/* ---------- type ---------- */
.display{
  font-size:clamp(2.25rem,6vw,4.5rem);line-height:.95;letter-spacing:-.045em;
  font-weight:600;margin:0;
}
.display-sm{
  font-size:clamp(1.6rem,3.2vw,2.4rem);line-height:1.02;letter-spacing:-.035em;
  font-weight:600;margin:0;
}
.label{
  font-family:var(--mono);font-size:10px;text-transform:uppercase;
  letter-spacing:.18em;color:var(--text-4);
}
.label-lg{
  font-family:var(--mono);font-size:11px;text-transform:uppercase;
  letter-spacing:.16em;color:var(--text-3);
}
.mono{font-family:var(--mono);font-size:12px;letter-spacing:-.01em}
.muted{color:var(--text-3)}
.dim{color:var(--text-4)}
.lede{font-size:15px;color:var(--text-2);line-height:1.65;max-width:62ch}

/* ---------- shell ---------- */
.shell{display:grid;grid-template-columns:var(--sidebar) 1fr;min-height:100vh}

.sidebar{
  border-right:1px solid var(--line);padding:26px 20px;display:flex;
  flex-direction:column;gap:26px;position:sticky;top:0;height:100vh;overflow-y:auto;
}
.brand{display:flex;flex-direction:column;gap:3px}
.brand-name{font-size:15px;font-weight:600;letter-spacing:-.03em}
.brand-sub{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:.2em;color:var(--text-5)}

.mind-chip{border:1px solid var(--line-2);border-radius:var(--radius);padding:10px 12px}
.mind-chip .row{display:flex;align-items:center;justify-content:space-between;gap:8px}
.dot{
  width:5px;height:5px;border-radius:50%;background:var(--accent);
  display:inline-block;flex:none;box-shadow:0 0 0 3px var(--accent-soft);
}
.dot.off{background:var(--text-5);box-shadow:none}

.nav{display:flex;flex-direction:column;gap:22px}
.nav-group{display:flex;flex-direction:column;gap:1px}
.nav-head{
  font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:.22em;
  color:var(--text-5);margin-bottom:9px;
}
.nav-link{
  display:flex;align-items:baseline;gap:10px;padding:6px 8px;margin:0 -8px;
  border-radius:var(--radius);color:var(--text-3);font-size:13px;
  transition:color .15s,background-color .15s;
}
.nav-link:hover{color:var(--text-1);background:var(--surface-2)}
.nav-link.on{color:var(--text);background:var(--surface-2);box-shadow:inset 2px 0 0 var(--accent)}
.nav-num{font-family:var(--mono);font-size:9px;color:var(--text-5);letter-spacing:.06em}
.nav-link.on .nav-num{color:var(--text-3)}
.nav-count{margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--text-4)}

.sidebar-foot{margin-top:auto;padding-top:18px;border-top:1px solid var(--line)}

/* ---------- main ---------- */
.main{min-width:0;display:flex;flex-direction:column}
.topbar{
  border-bottom:1px solid var(--line);padding:26px 40px;display:flex;
  align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap;
}
.topbar h1{font-size:26px;font-weight:600;letter-spacing:-.035em;margin:0 0 5px}
.topbar p{margin:0;font-size:13px;color:var(--text-3);max-width:64ch}
.content{padding:32px 40px 72px;max-width:1240px}
.section{margin-bottom:44px}
.section-head{
  display:flex;align-items:baseline;justify-content:space-between;gap:16px;
  padding-bottom:10px;margin-bottom:18px;border-bottom:1px solid var(--line);
}

/* ---------- controls ---------- */
.btn{
  font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.14em;
  padding:9px 15px;border:1px solid var(--line-3);border-radius:var(--radius);
  background:transparent;color:var(--text-2);cursor:pointer;display:inline-block;
  transition:color .15s,border-color .15s,background-color .15s;
}
.btn:hover{color:var(--text);border-color:var(--text-3)}
.btn-solid{background:var(--text);color:#000;border-color:var(--text);font-weight:600}
.btn-solid:hover{background:var(--text-2);border-color:var(--text-2);color:#000}
.btn-sm{padding:6px 11px;font-size:9px}
.btn:disabled{opacity:.4;cursor:not-allowed}

input[type=text],input[type=password],textarea,select{
  width:100%;background:var(--bg);border:1px solid var(--line-2);border-radius:var(--radius);
  color:var(--text);font-family:var(--sans);font-size:14px;padding:11px 13px;
  transition:border-color .15s;
}
input:focus,textarea:focus,select:focus{
  outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);
}
textarea{resize:vertical;min-height:96px;line-height:1.6}
::placeholder{color:var(--text-5)}

/* ---------- surfaces ---------- */
.panel{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:22px}
.panel-flush{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}

.stats{
  display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:var(--radius);
}
.stat{background:var(--bg);padding:18px 20px}
.stat-val{font-size:30px;font-weight:600;letter-spacing:-.05em;line-height:1;margin:9px 0 6px;font-variant-numeric:tabular-nums}
.stat-hint{font-size:11px;color:var(--text-4)}

/* ---------- rows ---------- */
.rows{display:flex;flex-direction:column}
.row-item{
  padding:17px 20px;border-bottom:1px solid var(--line);display:flex;
  gap:18px;align-items:flex-start;transition:background-color .15s;
}
.row-item:last-child{border-bottom:0}
.row-item:hover{background:var(--surface-2)}
.row-rank{
  font-family:var(--mono);font-size:11px;color:var(--text-4);min-width:34px;
  padding-top:2px;font-variant-numeric:tabular-nums;
}
.row-body{flex:1;min-width:0}
.row-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.row-author{font-size:13px;font-weight:600;letter-spacing:-.01em}
.row-text{font-size:14px;color:var(--text-2);line-height:1.6;overflow-wrap:anywhere}
.row-meta{margin-top:9px;font-family:var(--mono);font-size:10px;color:var(--text-4);letter-spacing:.04em}
.row-actions{display:flex;gap:8px;align-items:center;flex:none}

/* ---------- tags ---------- */
.tag{
  font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:.14em;
  padding:3px 7px;border:1px solid var(--line-3);border-radius:var(--radius);
  color:var(--text-3);white-space:nowrap;
}
.tag-solid{background:var(--accent);color:#0a0503;border-color:var(--accent);font-weight:600}
.tag-strong{border-color:var(--text-3);color:var(--text-1)}

/* priority: rank shown by rule weight, never by hue */
.prio{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:10px;color:var(--text-4)}
.prio-bar{width:34px;height:2px;background:var(--line-2);position:relative;flex:none}
.prio-bar span{position:absolute;inset:0 auto 0 0;background:var(--text-3)}
.prio.hot .prio-bar span{background:var(--accent)}
.prio.hot{color:var(--accent)}

/* ---------- agent console ---------- */
.console{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);min-height:280px;padding:22px}
.console-line{font-family:var(--mono);font-size:12px;color:var(--text-4);margin-bottom:14px}
.console-answer{font-size:14.5px;line-height:1.75;color:var(--text-1);overflow-wrap:anywhere}
.console-answer p{margin:0 0 12px}
.console-answer p:last-child{margin-bottom:0}
.console-answer ul,.console-answer ol{margin:0 0 12px;padding-left:20px}
.console-answer li{margin-bottom:5px}
.console-answer a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.console-answer a:hover{color:var(--text)}
.console-answer b,.console-answer strong{font-weight:600;color:var(--text)}
.console-answer code{font-family:var(--mono);font-size:12.5px;background:var(--surface-2);padding:1px 5px;border-radius:var(--radius)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}

/* ---------- notice ---------- */
.notice{
  border:1px solid var(--line-2);border-left:2px solid var(--accent);
  border-radius:var(--radius);padding:15px 18px;background:var(--surface);
  font-size:13px;color:var(--text-2);line-height:1.65;
}
.notice strong{color:var(--text);font-weight:600}
.notice code{font-family:var(--mono);font-size:12px;color:var(--text-1);background:var(--surface-2);padding:1px 5px;border-radius:var(--radius)}

.empty{padding:52px 24px;text-align:center;color:var(--text-4);font-size:13px}
.empty .label{margin-bottom:10px}

/* ---------- timeline ---------- */
.timeline{border-left:1px solid var(--line-2);margin-left:6px;padding-left:22px;display:flex;flex-direction:column;gap:24px}
.tl-item{position:relative}
.tl-item::before{content:'';position:absolute;left:-27px;top:6px;width:5px;height:5px;border-radius:50%;background:var(--line-3)}
.tl-item.mark::before{background:var(--text)}

/* ---------- landing ---------- */
.landing{max-width:1120px;margin:0 auto;padding:0 40px}
.landing-nav{display:flex;align-items:center;justify-content:space-between;padding:26px 0;border-bottom:1px solid var(--line)}
.hero{padding:112px 0 88px;border-bottom:1px solid var(--line)}
.hero .lede{margin:26px 0 34px;font-size:17px}
.marquee-wrap{overflow:hidden;border-bottom:1px solid var(--line);padding:15px 0}
.marquee{display:flex;gap:44px;white-space:nowrap;animation:marquee 44s linear infinite;will-change:transform}
@keyframes marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.feature-grid{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;
  background:var(--line);border-top:1px solid var(--line);border-bottom:1px solid var(--line);
}
.feature{background:var(--bg);padding:34px 30px 40px}
.feature .label{color:var(--accent)}
.feature h3{font-size:16px;font-weight:600;letter-spacing:-.02em;margin:14px 0 9px}
.feature p{margin:0;font-size:13.5px;color:var(--text-3);line-height:1.65}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:26px 0}
.flow-step{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--text-3);border:1px solid var(--line-2);border-radius:var(--radius);padding:7px 11px}
.flow-arrow{color:var(--text-5);font-family:var(--mono);font-size:10px}

@media (max-width:1100px){
  .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .feature-grid{grid-template-columns:1fr}
}
@media (max-width:900px){
  .shell{grid-template-columns:1fr}
  .sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}
  .topbar,.content{padding-left:22px;padding-right:22px}
  .landing{padding:0 22px}
}
@media (prefers-reduced-motion:reduce){
  *{animation-duration:.001ms!important;transition-duration:.001ms!important}
}
"""

NAV: Sequence[Tuple[str, Sequence[Tuple[str, str, str]]]] = (
    (
        "Intelligence",
        (
            ("overview", "/overview", "Overview"),
            ("comments", "/comments", "Review Queue"),
            ("signals", "/signals", "Audience Signals"),
            ("moderation", "/moderation", "Moderation"),
            ("superfans", "/superfans", "Superfans"),
        ),
    ),
    (
        "Mind",
        (
            ("agent", "/agent", "Ask ReplyMind"),
            ("memory", "/memory", "Persistent Memory"),
            ("activity", "/activity", "Activity Log"),
        ),
    ),
    (
        "System",
        (
            ("connect", "/connect", "Connect"),
            ("wallet", "/wallet", "Mind & Wallet"),
            ("status", "/status", "Status"),
        ),
    ),
)


def esc(value: Optional[str]) -> str:
    return html.escape(str(value or ""), quote=True)


def prio_bar(priority: int, hot_at: int = 75) -> str:
    """Priority as a rule of varying fill.

    The accent appears only once a signal crosses the attention threshold, so
    scanning the column shows what needs the creator rather than colouring
    every row.
    """
    pct = max(0, min(100, int(priority)))
    hot = " hot" if pct >= hot_at else ""
    return (
        f'<span class="prio{hot}"><span class="prio-bar"><span style="width:{pct}%"></span></span>'
        f"{pct:03d}</span>"
    )


def empty_state(title: str, hint: str = "") -> str:
    return (
        f'<div class="empty"><div class="label">{esc(title)}</div>'
        f'<div>{esc(hint)}</div></div>'
    )


def page(
    title: str,
    subtitle: str,
    active: str,
    body: str,
    *,
    mind_connected: bool = False,
    mode: str = "demo",
    counts: Optional[dict] = None,
    actions: str = "",
) -> str:
    """Render a dashboard page inside the application shell."""
    counts = counts or {}

    groups = []
    index = 1
    for heading, items in NAV:
        links = []
        for key, href, label in items:
            on = " on" if key == active else ""
            count = counts.get(key)
            badge = f'<span class="nav-count">{count}</span>' if count else ""
            links.append(
                f'<a href="{href}" class="nav-link{on}">'
                f'<span class="nav-num">{index:02d}</span><span>{esc(label)}</span>{badge}</a>'
            )
            index += 1
        groups.append(
            f'<div class="nav-group"><div class="nav-head">{esc(heading)}</div>{"".join(links)}</div>'
        )

    dot = "dot" if mind_connected else "dot off"
    mind_state = "CONNECTED" if mind_connected else "OFFLINE"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — ReplyMind</title>
<style>{CSS}</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <a href="/" class="brand">
      <span class="brand-name">ReplyMind</span>
      <span class="brand-sub">Community Mind</span>
    </a>

    <div class="mind-chip">
      <div class="row">
        <span class="label">Mind</span>
        <span class="label" style="color:var(--text-2)"><span class="{dot}"></span> {mind_state}</span>
      </div>
      <div class="row" style="margin-top:7px">
        <span class="label">Mode</span>
        <span class="label" style="color:var(--text-2)">{esc(mode.upper())}</span>
      </div>
    </div>

    <nav class="nav">{"".join(groups)}</nav>

    <div class="sidebar-foot">
      <a href="/" class="label" style="color:var(--text-4)">← Landing</a>
    </div>
  </aside>

  <main class="main">
    <div class="topbar">
      <div>
        <h1>{esc(title)}</h1>
        <p>{esc(subtitle)}</p>
      </div>
      <div style="display:flex;gap:9px;align-items:center">
        {actions}
        <form method="post" action="/refresh" style="margin:0">
          <button type="submit" class="btn btn-solid">Run Agent Cycle</button>
        </form>
      </div>
    </div>
    <div class="content">{body}</div>
  </main>
</div>
</body>
</html>"""


# --------------------------------------------------------------------------
# landing background: community network
# --------------------------------------------------------------------------

# A drifting graph of community members, with signals travelling inward to a
# central Mind. It is the product's own diagram used as ambient texture, which
# is why it earns a place on a page this restrained -- it says "conversations
# converge on one Mind" before the copy does.
#
# Kept deliberately quiet: hairline strokes, low alpha, no colour. It pauses
# when the tab is hidden and renders a single static frame for anyone who has
# asked for reduced motion.
NETWORK_CANVAS_CSS = r"""
.net-canvas{
  position:fixed;inset:0;width:100%;height:100%;
  pointer-events:none;z-index:0;
}
.landing,.marquee-wrap{position:relative;z-index:1}
"""

NETWORK_CANVAS_JS = r"""
(function () {
  var canvas = document.getElementById('net');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');

  var reduced = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var W = 0, H = 0, dpr = 1;
  var nodes = [], pulses = [], hub = null;
  var LINK_DIST = 168;

  // Pointer state. `px/py` is where the cursor actually is; `cx/cy` chases it
  // with easing so the field glides instead of snapping to every jitter.
  var pointer = { px: -9999, py: -9999, cx: -9999, cy: -9999, active: false };
  var ACCENT = '255,107,44';   // the Mind and the signals reaching it
  var REVEAL = 235;   // radius the cursor brightens and pulls within
  var PUSH = 62;      // nodes drift out of the way inside this radius

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth;
    H = canvas.clientHeight;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
  }

  function build() {
    // Scale the population to the viewport so a laptop and a monitor read alike.
    var count = Math.round(Math.min(76, Math.max(26, (W * H) / 22000)));
    nodes = [];
    for (var i = 0; i < count; i++) {
      var nx = Math.random() * W, ny = Math.random() * H;
      nodes.push({
        x: nx, y: ny,
        // Offset from the drifting position, driven by the cursor and sprung
        // back to zero, so pointer interaction never corrupts the base drift.
        ox: 0, oy: 0,
        vx: (Math.random() - 0.5) * 0.16,
        vy: (Math.random() - 0.5) * 0.16,
        r: Math.random() * 1.1 + 0.7,
        // A few members carry more weight than the rest, as communities do.
        weight: Math.random() < 0.14 ? 2.1 : 1
      });
    }
    hub = { x: W * 0.5, y: H * 0.46 };
    pulses = [];
  }

  function spawnPulse() {
    if (!nodes.length || pulses.length > 14) return;
    var n = nodes[(Math.random() * nodes.length) | 0];
    pulses.push({ from: n, t: 0, speed: 0.0035 + Math.random() * 0.004 });
  }

  function step() {
    ctx.clearRect(0, 0, W, H);

    var i, j, a, b, dx, dy, d;

    // Ease the tracked cursor toward the real one.
    pointer.cx += (pointer.px - pointer.cx) * 0.12;
    pointer.cy += (pointer.py - pointer.cy) * 0.12;

    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      a.x += a.vx;
      a.y += a.vy;
      if (a.x < -20) a.x = W + 20; else if (a.x > W + 20) a.x = -20;
      if (a.y < -20) a.y = H + 20; else if (a.y > H + 20) a.y = -20;

      // Members ease aside as the cursor passes, then spring back.
      var tox = 0, toy = 0;
      if (pointer.active) {
        dx = a.x - pointer.cx; dy = a.y - pointer.cy;
        d = Math.sqrt(dx * dx + dy * dy);
        if (d < PUSH && d > 0.01) {
          var force = (1 - d / PUSH) * 14;
          tox = (dx / d) * force;
          toy = (dy / d) * force;
        }
      }
      a.ox += (tox - a.ox) * 0.08;
      a.oy += (toy - a.oy) * 0.08;
    }

    // Proximity to the cursor, 0..1 -- used to brighten what it is near.
    function near(x, y) {
      if (!pointer.active) return 0;
      var ddx = x - pointer.cx, ddy = y - pointer.cy;
      var dd = Math.sqrt(ddx * ddx + ddy * ddy);
      return dd > REVEAL ? 0 : 1 - dd / REVEAL;
    }

    // Edges: the community graph. Opacity falls off with distance.
    ctx.lineWidth = 1;
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      var ax = a.x + a.ox, ay = a.y + a.oy;
      for (j = i + 1; j < nodes.length; j++) {
        b = nodes[j];
        var bx = b.x + b.ox, by = b.y + b.oy;
        dx = ax - bx; dy = ay - by;
        d = Math.sqrt(dx * dx + dy * dy);
        if (d > LINK_DIST) continue;

        // A connection the cursor is near reads as the part of the community
        // currently under attention.
        var lift = Math.max(near((ax + bx) / 2, (ay + by) / 2), 0);
        var alpha = (0.10 + 0.44 * lift) * (1 - d / LINK_DIST);
        ctx.strokeStyle = 'rgba(255,255,255,' + alpha.toFixed(3) + ')';
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
        ctx.stroke();
      }
    }

    // Members.
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      var mx = a.x + a.ox, my = a.y + a.oy;
      var lift2 = near(mx, my);
      var base = a.weight > 1 ? 0.30 : 0.16;
      ctx.fillStyle = 'rgba(255,255,255,' + (base + 0.62 * lift2).toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(mx, my, a.r * a.weight * (1 + 0.5 * lift2), 0, Math.PI * 2);
      ctx.fill();
    }

    // A hairline from the cursor to the members closest to it: the pointer
    // joins the graph rather than floating over it.
    if (pointer.active) {
      for (i = 0; i < nodes.length; i++) {
        a = nodes[i];
        var lx = a.x + a.ox, ly = a.y + a.oy;
        var l = near(lx, ly);
        if (l < 0.55) continue;
        ctx.strokeStyle = 'rgba(255,255,255,' + (0.30 * (l - 0.55) / 0.45).toFixed(3) + ')';
        ctx.beginPath();
        ctx.moveTo(pointer.cx, pointer.cy);
        ctx.lineTo(lx, ly);
        ctx.stroke();
      }
    }

    // The Mind everything converges on -- the one fixed point, so it is the
    // one thing in the field that carries colour.
    ctx.strokeStyle = 'rgba(' + ACCENT + ',0.38)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(hub.x, hub.y, 5, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = 'rgba(' + ACCENT + ',0.14)';
    ctx.beginPath();
    ctx.arc(hub.x, hub.y, 10, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = 'rgba(' + ACCENT + ',0.70)';
    ctx.beginPath();
    ctx.arc(hub.x, hub.y, 2.1, 0, Math.PI * 2);
    ctx.fill();

    // Signals travelling in: a comment reaching the Mind.
    for (i = pulses.length - 1; i >= 0; i--) {
      var p = pulses[i];
      p.t += p.speed;
      if (p.t >= 1) { pulses.splice(i, 1); continue; }

      var e = p.t * p.t * (3 - 2 * p.t); // ease-in-out
      var sx = p.from.x + p.from.ox, sy = p.from.y + p.from.oy;
      var px = sx + (hub.x - sx) * e;
      var py = sy + (hub.y - sy) * e;
      var fade = Math.sin(p.t * Math.PI);

      // A signal warms as it nears the Mind.
      ctx.strokeStyle = 'rgba(' + ACCENT + ',' + (0.16 * fade).toFixed(3) + ')';
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(px, py);
      ctx.stroke();

      ctx.fillStyle = 'rgba(' + ACCENT + ',' + (0.85 * fade).toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(px, py, 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  var raf = null, timer = null;

  function loop() { step(); raf = requestAnimationFrame(loop); }

  function start() {
    if (raf !== null) return;
    raf = requestAnimationFrame(loop);
    timer = setInterval(spawnPulse, 900);
  }
  function stop() {
    if (raf !== null) { cancelAnimationFrame(raf); raf = null; }
    if (timer !== null) { clearInterval(timer); timer = null; }
  }

  resize();
  var rt = null;
  window.addEventListener('resize', function () {
    clearTimeout(rt);
    rt = setTimeout(resize, 160);
  });

  if (reduced) {
    step();  // one static frame: the graph, without the motion
    return;
  }

  // The canvas is pointer-events:none so it never intercepts a click, which
  // means the cursor has to be tracked on the window instead. Coordinates are
  // viewport-relative, and the canvas is position:fixed, so they line up with
  // no scroll correction.
  function movePointer(x, y) {
    if (!pointer.active) {           // first sighting: start where the cursor is
      pointer.cx = x; pointer.cy = y;
      pointer.active = true;
    }
    pointer.px = x; pointer.py = y;
  }

  window.addEventListener('pointermove', function (e) {
    movePointer(e.clientX, e.clientY);
  }, { passive: true });

  // Let the field settle back when the cursor leaves or a touch ends.
  function releasePointer() {
    pointer.active = false;
    pointer.px = pointer.py = pointer.cx = pointer.cy = -9999;
  }
  window.addEventListener('pointerleave', releasePointer, { passive: true });
  window.addEventListener('blur', releasePointer);
  window.addEventListener('pointercancel', releasePointer, { passive: true });

  // A tap on touch devices gives one brief moment of attention, then releases.
  var touchTimer = null;
  window.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse') return;
    movePointer(e.clientX, e.clientY);
    clearTimeout(touchTimer);
    touchTimer = setTimeout(releasePointer, 1600);
  }, { passive: true });

  // Don't burn a core animating a tab nobody is looking at.
  document.addEventListener('visibilitychange', function () {
    document.hidden ? stop() : start();
  });
  start();
})();
"""
