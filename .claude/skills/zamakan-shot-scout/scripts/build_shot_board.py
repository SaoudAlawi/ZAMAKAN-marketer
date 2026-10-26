#!/usr/bin/env python3
"""Build the shot board: one self-contained HTML page, image-first and dark like a screening room, in the client's
brand (design system) or the ZAMAKAN house look, plus shots.md for other agents.

Usage: python build_shot_board.py <shots.json> --out <job_dir> [--logo client-logo.png] [--client-name "Oman Oil"]
                                   [--design zamakan|awesome:<name>|path/DESIGN.md]
Then: python <scout>/scripts/check_outputs.py <job_dir>   (the same beauty/brand check as the reference board)

Sections: cover (request, the film language it became, stats, hero still) · the look (palette, traits, the uploaded
frame in frame-match mode) · one section per technique (how it's done, gear, budget, AI, then the shots) · who does this
well (people) · how to shoot it (production summary) · watch list and open questions.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared import tech_by_id  # noqa: E402
from brandkit import load_kit, with_client_logo  # noqa: E402
from render_board import data_uri, embedded_fonts, root_css  # noqa: E402
from theme import contrast, font_links, mix  # noqa: E402

E = html.escape
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "zamakan-core" / "scripts"))
from workspace import agency  # noqa: E402
HOME = agency()
EVID = {"content": ("page read", "ok"), "title": ("page exists", "thin"), "video": ("video · not watched", "vid")}
KIND = {"film": "Film", "commercial": "Commercial", "music-video": "Music video", "short": "Short film", "title-sequence": "Title sequence",
        "series": "Series", "clip": "Clip", "stills": "Film stills", "breakdown": "Breakdown", "motion-design": "Motion design",
        "photography": "Photography"}
MODE = {"subject": "Subject & mood", "effect": "Effect & technique", "frame-match": "Match this frame", "who": "Who does this well",
        "inspire": "Inspire me"}
ROLE = {"writer": ("Writer", "كاتب"), "dop": ("Cinematographer", "مدير تصوير"), "director": ("Director", "مخرج"),
        "editor": ("Editor · sound · design", "مونتاج · صوت · تصميم")}
KIND.update({"scene": "Scene", "essay": "Video essay", "interview": "Interview", "documentary": "Documentary",
             "docuseries": "Documentary series"})

CSS = """
*{box-sizing:border-box} html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--dark);color:var(--on-dark);font:16px/1.6 var(--body)}
a{color:var(--hi)} img{display:block;max-width:100%}
.wrap{max-width:1280px;margin:0 auto;padding-inline:clamp(16px,4vw,40px)}
h1,h2,h3{font-family:var(--disp);font-weight:var(--disp-w);margin:0;text-wrap:balance}
h2{font-size:clamp(28px,3.4vw,40px);line-height:1.1} h3{font-size:19px;line-height:1.25}
.ar,.ar-d{direction:rtl;letter-spacing:0} .ar{font-family:var(--ar)} .ar-d{font-family:var(--ar-disp)}
.eyebrow{font:600 12px/1.2 var(--body);letter-spacing:.14em;text-transform:uppercase;color:var(--soft)}
section{padding-block:clamp(44px,6vw,80px);border-top:1px solid var(--hair)}
.cover{padding-block:24px clamp(44px,6vw,80px);border:0}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:16px;padding-bottom:clamp(28px,5vw,64px)}
.topbar img{height:clamp(52px,7vw,84px);width:auto} .wordmark{font:var(--disp-w) 22px/1 var(--disp)}
.cov{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:clamp(24px,5vw,64px);align-items:end}
.cover h1{font-size:clamp(38px,6vw,76px);line-height:1.02;letter-spacing:-.01em}
.lede{color:var(--soft);font-size:18px;max-width:52ch;margin:18px 0 0}
.lang{margin-top:26px} .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.chip{display:inline-flex;gap:8px;align-items:baseline;border:1px solid var(--hair);border-radius:999px;padding:5px 12px;font-size:14px;background:var(--paper)}
.chip .ar{color:var(--soft);font-size:13px}
.stats{display:flex;flex-wrap:wrap;gap:28px;margin-top:32px} .stats b{display:block;font:var(--disp-w) 38px/1 var(--disp)} .stats span{color:var(--soft);font-size:13px}
.hero{margin:0} .hero img{width:100%;aspect-ratio:16/9;object-fit:cover;object-position:center 30%;border-radius:var(--r)}
.hero figcaption{color:var(--soft);font-size:13px;margin-top:8px}
.look{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:clamp(24px,4vw,56px);align-items:start}
.swatches{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:18px} .sw{aspect-ratio:1;border-radius:calc(var(--r)/1.5)}
.swl{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;font:12px/1.4 ui-monospace,monospace;color:var(--soft);margin-top:6px}
ul.traits{margin:16px 0 0;padding-left:18px;color:var(--soft)} ul.traits li{margin:4px 0}
.frame img{width:100%;border-radius:var(--r)} dl.spec{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin:16px 0 0;font-size:15px}
dl.spec dt{color:var(--soft)} dl.spec dd{margin:0}
.tech-head{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:clamp(20px,4vw,48px);align-items:start;margin-bottom:28px}
.tech-head h2 .ar-d{display:block;font-size:.62em;color:var(--soft);margin-top:8px;text-align:left;unicode-bidi:isolate}
.feel{color:var(--soft);font-size:17px;margin:12px 0 0;max-width:58ch}
.how{background:var(--paper);border:1px solid var(--hair);border-radius:var(--r);padding:18px 20px;font-size:15px}
.how p{margin:0 0 10px} .how .row{display:flex;flex-wrap:wrap;gap:8px 18px;color:var(--soft);font-size:14px}
.how b{color:var(--on-dark);font-weight:600}
.money{letter-spacing:.06em;color:var(--hi)} .money i{font-style:normal;color:var(--soft);letter-spacing:0;margin-left:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,360px),1fr));gap:22px}
.shot{background:var(--paper);border:1px solid var(--hair);border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column}
.shot .img{position:relative;aspect-ratio:16/9;background:var(--paper2);overflow:hidden} .shot .img img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 30%}
.shot .noimg{position:absolute;inset:0;display:grid;place-items:center;color:var(--soft);font-size:13px}
.badge{position:absolute;top:10px;left:10px;font:600 11px/1 var(--body);letter-spacing:.06em;text-transform:uppercase;padding:6px 8px;border-radius:6px;background:rgba(0,0,0,.72);color:#fff}
.tc{position:absolute;right:10px;bottom:10px;font:600 13px/1 ui-monospace,monospace;padding:6px 8px;border-radius:6px;background:var(--accent);color:var(--on-accent);text-decoration:none}
.shot .body{padding:16px 18px 18px;display:flex;flex-direction:column;gap:8px;flex:1}
.shot .meta{color:var(--soft);font-size:13px} .shot .cred{font-size:14px} .shot .cred span{color:var(--soft)}
.shot .note{color:var(--soft);font-size:14px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin:0}
.shot .why{font-size:15px;margin:0}
.num{position:absolute;left:10px;bottom:10px;font:var(--disp-w) 28px/1 var(--disp);color:#fff;text-shadow:0 1px 8px rgba(0,0,0,.7)}
.wf{display:grid;gap:8px;margin:2px 0} .wf div{border-left:2px solid var(--hi);padding:2px 0 2px 10px;font-size:14px}
.wf b{display:block;font:600 11px/1.3 var(--body);letter-spacing:.1em;text-transform:uppercase;color:var(--hi)} .wf b .ar{letter-spacing:0;text-transform:none;font-weight:400;margin-inline-start:6px}
.scene{font-size:14px;color:var(--soft);margin:0} .scene b{color:var(--on-dark);font-weight:600}
.ex{background:var(--paper2);border-radius:calc(var(--r)/1.5);padding:10px 12px;font-size:14px} .ex b{color:var(--hi);font-weight:600}
.pair{font-size:13px;color:var(--soft)}
.pal{display:flex;gap:0;height:10px;border-radius:5px;overflow:hidden;margin-top:2px} .pal i{flex:1}
.prod{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--soft);border-top:1px solid var(--hair);padding-top:10px;margin-top:auto}
.links{display:flex;gap:14px;font-size:14px;flex-wrap:wrap}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,380px),1fr));gap:22px}
.person{background:var(--paper);border:1px solid var(--hair);border-radius:var(--r);padding:20px}
.person .role{color:var(--hi);font:600 12px/1 var(--body);letter-spacing:.12em;text-transform:uppercase}
.person h3{font-size:24px;margin:8px 0 6px} .person p{margin:0 0 10px;color:var(--soft)}
.thumbs{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:10px 0} .thumbs img{aspect-ratio:16/9;object-fit:cover;width:100%;border-radius:6px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:22px}
.box{background:var(--paper);border:1px solid var(--hair);border-radius:var(--r);padding:20px} .box ul{margin:10px 0 0;padding-left:18px} .box li{margin:5px 0}
.sec-head{margin-bottom:28px} .sec-head p{color:var(--soft);max-width:64ch;margin:8px 0 0}
footer{border-top:1px solid var(--hair);color:var(--soft);font-size:14px} footer .wrap{padding-block:36px;display:grid;grid-template-columns:auto 1fr;gap:24px}
footer img{height:44px;width:auto} footer p{margin:0 0 6px}
@media (max-width:820px){.cov,.look,.tech-head{grid-template-columns:1fr} .hero{order:-1} footer .wrap{grid-template-columns:1fr}}
"""


def screen_vars(th):
    """The screening-room tones, mixed here (not with CSS color-mix) so every browser and the contrast check read them."""
    dark, on = th["dark"], th["on_dark"]
    hi = mix(th["accent"], on, 0.45)
    t = 0.45
    while contrast(hi, dark) < 4.5 and t < 1:  # the accent must stay readable as link text on the dark page
        t += 0.1
        hi = mix(th["accent"], on, t)
    return (f":root{{--paper:{mix(on, dark, 0.93)};--paper2:{mix(on, dark, 0.88)};--soft:{mix(on, dark, 0.28)};"
            f"--hair:{mix(on, dark, 0.84)};--hi:{hi}}}")


def at_time(url, ts):
    """Link straight to the moment: YouTube &t=, Vimeo #t=."""
    parts = [int(x) for x in ts.split(":")]
    secs = parts[-1] + 60 * parts[-2] + (3600 * parts[0] if len(parts) == 3 else 0)
    if re.search(r"youtube\.com|youtu\.be", url):
        return url + ("&" if "?" in url else "?") + f"t={secs}s"
    if "vimeo.com" in url:
        return url.split("#")[0] + f"#t={secs}s"
    return url


def money(n):
    return f'<span class="money" title="budget level {n} of 4">{"$" * n}<i>/4</i></span>'


def img_tag(shot, base, alt=True):
    loc = (shot.get("thumbnail") or {}).get("local")
    p = (base / loc) if loc else None
    if p and p.exists():
        return f'<img src="{data_uri(p, "image/jpeg")}" alt="{E(shot["title"]) if alt else ""}">'
    return '<div class="noimg">no preview: open the link</div>'


def shot_card(s, base, techs, roles=(), num=None, shots=None):
    primary = s["urls"][0]
    ev = max((u.get("evidence") for u in s["urls"] if u.get("evidence")), key=lambda e: {"content": 3, "title": 2, "video": 1}[e], default=None)
    badge = f'<span class="badge">{EVID[ev][0]}</span>' if ev else ""
    video = next((u["url"] for u in s["urls"] if u["kind"] == "video"), None)
    tc = f'<a class="tc" href="{E(at_time(video, s["timestamp"]))}" title="jump to the moment">▶ {E(s["timestamp"])}</a>' if s.get("timestamp") and video else ""
    meta = " · ".join(x for x in [KIND.get(s["kind"], s["kind"]), str(s.get("year") or ""), s.get("maker") or "",
                                   f'{s["runtime_min"]} min' if s.get("runtime_min") else "", ", ".join((s.get("countries") or [])[:2])] if x)
    cr = s.get("credits") or {}
    cred = " · ".join(f'<span>{lab}</span> {E(", ".join(cr[k][:3]))}' for k, lab in (("director", "Dir."), ("writer", "Writer"), ("dop", "DOP"), ("editor", "Editor"),
                      ("composer", "Music"), ("production", "Prod."), ("agency", "Agency")) if cr.get(k) and (k not in ("writer", "editor", "composer") or roles))
    pal = "".join(f'<i style="background:{c}"></i>' for c in s.get("palette", [])[:5])
    p = s.get("production")
    tech_names = ", ".join(techs[t]["name"].split(" (")[0] for t in s["techniques"] if t in techs)
    links = [f'<a href="{E(primary["url"])}" target="_blank" rel="noopener">{"Watch" if primary["kind"] == "video" else "Open"} ↗</a>']
    links += [f'<a href="{E(u["url"])}" target="_blank" rel="noopener">{("Watch on " + E(u.get("source") or "video")) if u["kind"] == "video" else E(u.get("source") or u["kind"])} ↗</a>'
              for u in s["urls"][1:3]]
    if s.get("found_on"):
        links.append(f'<a href="{E(s["found_on"])}" target="_blank" rel="noopener">found on {E(s["provenance"]["found_via"])} ↗</a>')
    wf = "".join(f'<div><b>{ROLE[r][0]} · <span class="ar" lang="ar">{ROLE[r][1]}</span></b>{E(s["watch_for"][r])}</div>'
                 for r in roles if r in (s.get("watch_for") or {}))
    inspire = ((f'<div class="wf">{wf}</div>' if wf else "")
               + (f'<p class="scene"><b>Key scene:</b> {E(s["key_scene"])}</p>' if s.get("key_scene") else "")
               + (f'<div class="ex"><b>After watching:</b> {E(s["exercise"])}</div>' if s.get("exercise") else "")
               + (f'<div class="pair">Double bill with <a href="#shot-{s["pairs_with"]}">{E((shots or {}).get(s["pairs_with"], {}).get("title", s["pairs_with"]))}</a></div>'
                  if s.get("pairs_with") else ""))
    prod = ((f'<div class="prod"><span>{E(tech_names)}</span><span>{E(p["method"])}</span>{money(p["budget"])}'
             + (f'<span>AI: {E(p["ai"].split(":")[0])}</span>' if p.get("ai") else "") + "</div>") if p
            else f'<div class="prod"><span>{E(tech_names)}</span></div>')
    numtag = f'<span class="num">{num:02d}</span>' if num else ""
    return (f'<article class="shot" id="shot-{s["id"]}"><div class="img">{img_tag(s, base)}{badge}{tc}{numtag}</div><div class="body">'
            f'<div class="meta">{E(meta)}</div><h3>{E(s["title"])}</h3>'
            + (f'<div class="cred">{cred}</div>' if cred else "")
            + (f'<p class="note">{E(s["shot_note"])}</p>' if s.get("shot_note") else "")
            + f'<p class="why">{E(s["why"])}</p>' + inspire + (f'<div class="pal" title="palette">{pal}</div>' if pal else "")
            + prod
            + f'<div class="links">{"".join(links)}</div></div></article>')


def tech_head(t, note):
    return (f'<div class="tech-head"><div><div class="eyebrow">{E(t["category"].title())}</div>'
            f'<h2>{E(t["name"])}<span class="ar-d" lang="ar">{E(t["name_ar"])}</span></h2>'
            f'<p class="feel">{E(note or t["feeling"])}</p></div>'
            f'<div class="how"><div class="eyebrow" style="margin-bottom:8px">How it\'s done</div><p>{E(t["how"])}</p>'
            f'<div class="row"><span><b>Gear</b> {E(t["gear"])}</span><span><b>Budget</b> {money(int(t["budget"]))}</span>'
            f'<span><b>Kit</b> {E(t["kit"])}</span><span><b>AI</b> {E(t["ai"])}</span></div></div></div>')


def build(run, base, kit, client_name):
    techs = tech_by_id()
    th = kit["theme"]
    r = run["run"]
    shots = {s["id"]: s for s in run["shots"]}
    title = r.get("title") or r["request"]
    logo = kit["logos"].get("on_dark")
    brand = (f'<img src="{data_uri(logo["svg"] or logo["png"])}" alt="{E(kit.get("client_name") or "")}">' if logo
             else f'<span class="wordmark">{E(client_name or th["name"])}</span>')
    groups = run.get("groups") or []
    if not groups:  # group by each shot's lead technique
        order = {}
        for s in run["shots"]:
            order.setdefault(s["techniques"][0], []).append(s["id"])
        groups = [{"technique": t, "shot_ids": ids} for t, ids in order.items()]
    inspire = r["mode"] == "inspire"
    roles = r.get("roles") or []
    lang_ids = [g["technique"] for g in groups if g.get("technique")] or list(dict.fromkeys(s["techniques"][0] for s in run["shots"]))
    chips = "".join(f'<span class="chip">{E(techs[t]["name"].split(" (")[0])}<span class="ar" lang="ar">{E(techs[t]["name_ar"].split(" (")[0])}</span></span>'
                    for t in lang_ids if t in techs)
    ev = {"content": 0, "title": 0, "video": 0}
    for s in run["shots"]:
        e = max((u.get("evidence") for u in s["urls"] if u.get("evidence")), key=lambda x: {"content": 3, "title": 2, "video": 1}[x], default=None)
        if e:
            ev[e] += 1
    srcs = len({s["provenance"]["found_via"] for s in run["shots"]})
    cover_shot = shots.get(r.get("cover")) or next((s for s in run["shots"] if (s.get("thumbnail") or {}).get("local")), None)
    hero = (f'<figure class="hero">{img_tag(cover_shot, base)}<figcaption>{E(cover_shot["title"])}'
            f'{" · " + E(", ".join(cover_shot.get("credits", {}).get("director", []))) if cover_shot.get("credits", {}).get("director") else ""}</figcaption></figure>'
            if cover_shot else "<div></div>")
    S = []
    if inspire:
        role_chips = "".join(f'<span class="chip">{ROLE[x][0]}<span class="ar" lang="ar">{ROLE[x][1]}</span></span>' for x in roles if x in ROLE)
        kinds = [s["kind"] for s in run["shots"]]
        mins = sum(s.get("runtime_min") or 0 for s in run["shots"])
        countries = {c for s in run["shots"] for c in (s.get("countries") or [])[:1]}
        stats = (f'<div><b>{kinds.count("film")}</b><span>features</span></div><div><b>{kinds.count("short")}</b><span>shorts</span></div>'
                 + (f'<div><b>{kinds.count("documentary") + kinds.count("docuseries")}</b><span>documentaries</span></div>' if "documentary" in kinds or "docuseries" in kinds else "")
                 + f'<div><b>{round(mins / 60) if mins else "?"}</b><span>hours of cinema</span></div><div><b>{len(countries)}</b><span>countries</span></div>')
        lang = (f'<div class="lang"><div class="eyebrow">For</div><div class="chips">{role_chips}</div></div>'
                + (f'<div class="lang"><div class="eyebrow">Look for</div><div class="chips">{chips}</div></div>' if chips else ""))
        eyebrow = "A viewing programme"
    else:
        stats = (f'<div><b>{len(run["shots"])}</b><span>shots</span></div><div><b>{len(lang_ids)}</b><span>techniques</span></div>'
                 f'<div><b>{srcs}</b><span>sources</span></div><div><b>{sum(s["status"] == "verified" for s in run["shots"])}</b><span>links checked</span></div>')
        lang = f'<div class="lang"><div class="eyebrow">In film language</div><div class="chips">{chips}</div></div>' if chips else ""
        eyebrow = "The request"
    S.append(f'<header class="cover"><div class="wrap"><div class="topbar">{brand}<div class="eyebrow" style="text-align:end">Shot scout · '
             f'{E(MODE[r["mode"]])}<br>{E(r["created"])}</div></div><div class="cov"><div><div class="eyebrow">{eyebrow}</div>'
             f'<h1>{E(title)}</h1><p class="lede">{E(r.get("theme") or r["request"])}</p>'
             + lang + f'<div class="stats">{stats}</div></div>{hero}</div></div></header>')
    look = run.get("look") or {}
    frame = r.get("frame")
    if look or frame:
        pal = ((frame or {}).get("palette") or look.get("palette") or []) if frame else (look.get("palette") or [])
        left = (f'<div class="eyebrow">The look</div><h2>{E(look.get("summary") or "What ties these shots together")}</h2>'
                + (f'<p class="ar" lang="ar" style="font-size:18px;color:var(--soft);margin:12px 0 0">{E(look["summary_ar"])}</p>' if look.get("summary_ar") else "")
                + ("<ul class=\"traits\">" + "".join(f"<li>{E(x)}</li>" for x in look.get("traits", [])) + "</ul>" if look.get("traits") else "")
                + (f'<div class="swatches">{"".join(f"<div class=sw style=background:{c}></div>" for c in pal[:6])}</div>'
                   f'<div class="swl">{"".join(f"<span>{c}</span>" for c in pal[:6])}</div>' if pal else ""))
        right = ""
        if frame:
            fp = (base / frame["file"]) if frame.get("file") else None
            fimg = f'<img src="{data_uri(fp, "image/png" if str(fp).endswith(".png") else "image/jpeg")}" alt="the frame to match">' if fp and fp.exists() else ""
            spec = "".join(f"<dt>{lab}</dt><dd>{E(frame[k])}</dd>" for k, lab in (("shot_size", "Shot"), ("lens", "Lens"), ("light", "Light"), ("movement", "Movement")) if frame.get(k))
            right = f'<div class="frame"><div class="eyebrow" style="margin-bottom:10px">Your frame</div>{fimg}<p>{E(frame["description"])}</p><dl class="spec">{spec}</dl></div>'
        S.append(f'<section id="look"><div class="wrap look"><div>{left}</div>{right}</div></section>')
    n = 0
    for gi, g in enumerate(groups):
        t = techs.get(g.get("technique") or "")
        cards = []
        for i in g["shot_ids"]:
            if i in shots:
                n += 1
                cards.append(shot_card(shots[i], base, techs, roles, n if inspire else None, shots))
        if not cards:
            continue
        if t and not g.get("title"):
            head = tech_head(t, g.get("note"))
        else:
            head = (f'<div class="sec-head"><div class="eyebrow">{"Part " + str(gi + 1)}</div><h2>{E(g.get("title") or t["name"])}</h2>'
                    + (f'<p>{E(g["note"])}</p>' if g.get("note") else "") + "</div>")
        S.append(f'<section id="g-{gi}"><div class="wrap">{head}<div class="grid">{"".join(cards)}</div></div></section>')
    if run.get("people"):
        cards = []
        for p in run["people"]:
            th_imgs = "".join(img_tag(shots[i], base, alt=False) for i in p["shot_ids"][:3] if i in shots and (shots[i].get("thumbnail") or {}).get("local"))
            links = " · ".join(f'<a href="{E(u)}" target="_blank" rel="noopener">{E(re.sub(r"^https?://(www\\.)?", "", u).split("/")[0])} ↗</a>' for u in p.get("links", []))
            work = ", ".join(f'<a href="#shot-{i}">{E(shots[i]["title"])}</a>' for i in p["shot_ids"] if i in shots)
            cards.append(f'<div class="person"><div class="role">{E(p["role"])}{" · " + E(p["region"]) if p.get("region") else ""}</div><h3>{E(p["name"])}</h3>'
                         f'<p>{E(p["known_for"])}</p>{f"<div class=thumbs>{th_imgs}</div>" if th_imgs else ""}<p style="font-size:14px">Work here: {work}</p>'
                         + (f'<p style="font-size:14px">{E(p["note"])}</p>' if p.get("note") else "") + (f'<p style="font-size:14px">{links}</p>' if links else "") + "</div>")
        S.append(f'<section id="people"><div class="wrap"><div class="sec-head"><div class="eyebrow">Who does this well</div><h2>People to brief or bid</h2>'
                 f'<p>Credits come from the sources named on each shot. Check availability and current representation before contacting anyone.</p></div>'
                 f'<div class="people">{"".join(cards)}</div></div></section>')
    ps = run.get("production_summary") or {}
    if ps:
        boxes = []
        market = r.get("market") or HOME["home_name"]
        if ps.get("ksa_notes") and not ps.get("local_notes"):  # older runs
            ps = {**ps, "local_notes": ps["ksa_notes"]}
        for k, lab in (("gear", "Gear list"), ("local_notes", f"Shooting in {market}"), ("ai_notes", "Where AI can help")):
            if ps.get(k):
                boxes.append(f'<div class="box"><div class="eyebrow">{lab}</div><ul>{"".join(f"<li>{E(x)}</li>" for x in ps[k])}</ul></div>')
        S.append('<section id="production"><div class="wrap"><div class="sec-head"><div class="eyebrow">For the producer</div><h2>How to shoot it</h2>'
                 + (f'<p>{E(ps["budget"])}</p>' if ps.get("budget") else "") + f'</div><div class="cols">{"".join(boxes)}</div></div></section>')
    if run.get("watch_list") or run.get("open_questions"):
        wl = "".join(f"<li>{E(x)}</li>" for x in run.get("watch_list", []))
        oq = "".join(f"<li>{E(x)}</li>" for x in run.get("open_questions", []))
        S.append('<section id="next"><div class="wrap cols">'
                 + (f'<div class="box"><div class="eyebrow">Watch before the meeting</div><ul>{wl}</ul></div>' if wl else "")
                 + (f'<div class="box"><div class="eyebrow">Open questions</div><ul>{oq}</ul></div>' if oq else "") + "</div></section>")
    mark = kit["logos"].get("mark_dark") or kit["logos"].get("on_dark")
    S.append(f'<footer><div class="wrap">{f"<img src={chr(34)}{data_uri(mark["svg"] or mark["png"])}{chr(34)} alt={chr(34)}{chr(34)}>" if mark else "<div></div>"}<div>'
             f'<p>Every link was checked on {E(r["created"])}: {ev["content"]} pages read, {ev["title"]} pages that exist but could not be read (login or empty), '
             f'{ev["video"]} videos that exist but nobody has watched yet. Shot notes and credits come from the sources named on each card. '
             f'Budget: $ any crew · $$ some extra kit · $$$ specialist crew or rig · $$$$ high-end. Stills © their owners, internal reference use only.</p>'
             f'<p>Styled with the {E(kit.get("client_name") or th["name"])} {"design system" if kit["source"] == "client" else "look"}. Generated by zamakan-shot-scout.</p></div></div></footer>')
    body = "".join(S[:1]) + "<main>" + "".join(S[1:-1]) + "</main>" + S[-1]
    text = re.sub(r"<[^>]+>", " ", html.unescape(body))
    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{E(title)}</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            + ("" if kit["font_files"] else font_links(th)) + f'<style>{embedded_fonts(kit, text)}{root_css(kit)}{screen_vars(th)}{CSS}</style></head>')
    return head + f"<body>{body}</body></html>"


def shots_md(run):
    techs = tech_by_id()
    r = run["run"]
    L = [f"# {r.get('title') or r['request']}", "", f"Request: {r['request']}", f"Mode: {r['mode']} · {r['created']}", ""]
    if (run.get("look") or {}).get("summary"):
        L += [f"Look: {run['look']['summary']}", f"Palette: {' '.join(run['look'].get('palette', []))}", ""]
    for s in run["shots"]:
        cr = s.get("credits") or {}
        L += [f"## {s['title']} ({s.get('year', '')})", f"- Link: {s['urls'][0]['url']}" + (f" at {s['timestamp']}" if s.get("timestamp") else ""),
              f"- Techniques: {', '.join(techs[t]['name'] for t in s['techniques'] if t in techs)}",
              f"- Why: {s['why']}"]
        if s.get("production"):
            L.append(f"- How: {s['production']['how']} (budget {s['production']['budget']}/4, {s['production']['method']})")
        for role, note in (s.get("watch_for") or {}).items():
            L.append(f"- Watch for ({role}): {note}")
        if s.get("exercise"):
            L.append(f"- Exercise: {s['exercise']}")
        if cr:
            L.append("- Credits: " + "; ".join(f"{k} {', '.join(v)}" for k, v in cr.items()))
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shots")
    ap.add_argument("--out", required=True)
    ap.add_argument("--logo")
    ap.add_argument("--client-name")
    ap.add_argument("--design")
    a = ap.parse_args()
    path = Path(a.shots)
    run = json.loads(path.read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    kit = load_kit(a.design, out)
    if a.logo:
        kit = with_client_logo(kit, a.logo, out, a.client_name)
    (out / "board.html").write_text(build(run, path.parent, kit, a.client_name or kit.get("client_name")), encoding="utf-8")
    (out / "shots.md").write_text(shots_md(run), encoding="utf-8")
    size = (out / "board.html").stat().st_size / 1e6
    print(f"built {out / 'board.html'} ({size:.1f} MB) and shots.md · look: {kit['theme']['name']}")
    for n in kit.get("proposed_notes", []):
        print(f"  note: {n}")


if __name__ == "__main__":
    main()
