#!/usr/bin/env python3
"""Collect cinematic candidates from the sources that are good at each need. Costs no web searches.

Usage:
  python discover_shots.py eyecannndy-technique <slug> [--limit 12] --out cand.jsonl   # a technique's clips + credits
  python discover_shots.py eyecannndy-search "<words>" [--limit 12] --out cand.jsonl    # Eyecannndy's own search
  python discover_shots.py eyecannndy-person dop/<slug>|director/<slug> --out ...      # "who does this well"
  python discover_shots.py filmgrab "<word>" --out cand.jsonl                            # film stills by subject/title
  python discover_shots.py filmgrab-stills <film-grab film URL> [--limit 12] --out ...  # the stills of one film
  python discover_shots.py shotcafe "<word>" --out cand.jsonl                            # film stills database
  python discover_shots.py directorsnotes|motionographer|stash "<words>" --out ...      # shorts, motion, VFX articles
  python discover_shots.py shortoftheweek "<words>" [--limit 10] --out cand.jsonl         # curated short films, free to watch
  python discover_shots.py docs "<words>" --out cand.jsonl                               # documentaries: SOTW docs + doc channels + YouTube
  python discover_shots.py channel-search @guardiandocumentaries "<words>" --out ...    # search inside one YouTube channel
  python discover_shots.py shortoftheweek "<words>" --genre documentary --out ...      # documentary shorts only
  python discover_shots.py youtube "<words>" [--min-views 10000] --out cand.jsonl
  python discover_shots.py vimeo <vimeo URL> ... --out cand.jsonl                        # check Vimeo links (oEmbed)
  python discover_shots.py page <url> ... --out cand.jsonl                               # any page from web search

Vimeo's own search blocks automated access: find Vimeo links with your web search tool (expand.py writes the queries),
then pass them to `vimeo` here. Eyecannndy is the richest source: every clip comes with its techniques, director, DOP,
editor, colourist and the original video link. Each line in --out is one candidate (a URL fetched again replaces its line).
"""
import argparse
import html as H
import json
import re
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, quote_plus, urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shared  # noqa: E402,F401  (puts the scout's scripts on the path)
import _web  # noqa: E402
import sources as S  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

EYE = "https://eyecannndy.com"
TIME = re.compile(r"(?<![\d:])(\d{1,2}:\d{2}(?::\d{2})?)(?![\d:])")


def timestamps(text):
    """Moments a description points at ('look at 00:32'): kept so the board can link straight to them."""
    return list(dict.fromkeys(TIME.findall(text or "")))[:6]


def soup(url, **kw):
    page = _web.get(url, browser="never", **kw)
    return BeautifulSoup(page.get("text") or "", "html.parser"), page.get("status")


# ---------- Eyecannndy
def eye_clip_ids(html):
    s = BeautifulSoup(html, "html.parser")
    out = []
    for img in s.select("img[hx-get*='clip_info_g']"):
        m = re.search(r"clip_info_g/(\d+)/", img["hx-get"])
        if m:
            out.append({"id": m.group(1), "title": img.get("title") or img.get("alt"), "gif": img.get("src"),
                        "still": img.get("data-src"), "info": urljoin(EYE, img["hx-get"])})
    return list({c["id"]: c for c in out}.values())


def eye_clip(c, page_url):
    s, status = soup(c["info"])
    text = s.get_text(" | ", strip=True)
    rec = {"source": "eyecannndy", "kind": "clip", "title": c["title"], "gif": c["gif"], "thumbnail": c["still"] or c["gif"],
           "found_on": page_url, "clip_id": c["id"], "techniques_src": [], "credits": {}}
    m = re.search(r"\((\d{4})\)", text)
    if m:
        rec["year"] = int(m.group(1))
    parts = [p.strip() for p in text.split("|")]
    if len(parts) > 1:
        rec["description"] = next((p for p in parts[1:4] if len(p) > 60), "")
    for a in s.find_all("a", href=True):
        h = a["href"]
        name = a.get_text(" ", strip=True)
        if h.startswith("/technique/"):
            slug = h.split("/")[2].split("#")[0]
            if slug not in rec["techniques_src"]:
                rec["techniques_src"].append(slug)
        for role in ("director", "dop", "editor", "colorist"):
            if h.startswith(f"/{role}/") and name:
                rec["credits"].setdefault(role, []).append(name)
        if re.match(r"https?://(www\.)?(youtube\.com|youtu\.be|vimeo\.com)/", h):
            rec["url"] = h
    if not rec.get("url"):
        rec["url"] = rec["found_on"]
        rec["note"] = "no original video link on Eyecannndy; only the technique page shows this clip"
    rec["http_status"] = status
    return rec


def eyecannndy(page_url, limit, query):
    html = _web.get(page_url, browser="never").get("text") or ""
    clips = eye_clip_ids(html)[:limit]
    with ThreadPoolExecutor(max_workers=6) as ex:
        recs = list(ex.map(lambda c: eye_clip(c, page_url), clips))
    for r in recs:
        r["query"] = query
    return recs


# ---------- film stills
def filmgrab(q):
    s, _ = soup(f"https://film-grab.com/?s={quote_plus(q)}")
    out = []
    for a in s.find_all("a", href=re.compile(r"film-grab\.com/\d{4}/\d{2}/\d{2}/[^/]+/?$")):
        title = a.get_text(" ", strip=True)
        img = a.find("img") or (a.find_parent() and a.find_parent().find("img"))
        if not title and img:
            title = img.get("alt", "")
        if title:
            out.append({"source": "filmgrab", "kind": "film-stills", "url": a["href"], "title": title,
                        "thumbnail": img and (img.get("data-src") or img.get("src")), "query": q})
    merged = {}
    for r in out:  # the same film appears as image link and title link: keep the one with both
        m = merged.setdefault(r["url"], r)
        m["thumbnail"] = m.get("thumbnail") or r.get("thumbnail")
        if len(r["title"]) > len(m["title"]):
            m["title"] = r["title"]
    return list(merged.values())


def filmgrab_stills(url, limit):
    s, status = soup(url)
    title = (s.find("meta", property="og:title") or {}).get("content") or (s.title.string if s.title else url)
    stills = []
    for img in s.find_all("img"):
        src = img.get("data-src") or img.get("src") or ""
        src = src.replace("/photo-gallery/thumb/", "/photo-gallery/").split("?bwg=")[0]  # full-size, not the gallery thumb
        if "/wp-content/uploads/" in src and not re.search(r"-\d+x\d+\.", src) and src not in stills:
            stills.append(src)
    return [{"source": "filmgrab", "kind": "film-stills", "url": url, "title": re.sub(r"\s*[–-]\s*\[?FILMGRAB\]?.*$", "", title).strip(),
             "stills": stills[:limit], "thumbnail": stills[0] if stills else None, "http_status": status}]


def shotcafe(q):
    s, _ = soup(f"https://shot.cafe/search/{quote(q)}")
    out = []
    for a in s.find_all("a", href=re.compile(r"^/movie/")):
        div = a.find_parent("div")
        bg = re.search(r"url\('([^']+)'\)", (div or {}).get("style", "") if div else "")
        em = a.find("em")
        year = int(re.sub(r"\D", "", em.get_text())) if em and re.sub(r"\D", "", em.get_text()) else None
        title = a.get_text(" ", strip=True).replace(em.get_text(" ", strip=True) if em else "", "").strip()
        title = re.sub(r"\s+\d+$", "", title)  # trailing still count badge
        out.append({"source": "shotcafe", "kind": "film-stills", "url": urljoin("https://shot.cafe", a["href"]), "title": title,
                    "year": year, "thumbnail": urljoin("https://shot.cafe", bg.group(1)) if bg else None, "query": q})
    return out


# ---------- articles (shorts, motion, VFX)
ARTICLE_SITES = {"directorsnotes": "https://directorsnotes.com/?s={}", "motionographer": "https://motionographer.com/?s={}",
                 "stash": "https://www.stashmedia.tv/?s={}"}


def articles(site, q):
    s, _ = soup(ARTICLE_SITES[site].format(quote_plus(q)))
    host = re.search(r"//([^/]+)/", ARTICLE_SITES[site]).group(1)
    out = []
    for a in s.find_all("a", href=True):
        h = a["href"]
        title = a.get_text(" ", strip=True)
        is_post = host in h and (re.search(r"/\d{4}/\d{2}/\d{2}/", h) or (site == "stash" and h.count("/") == 4 and len(title) > 25))
        if is_post and len(title) > 15 and not re.search(r"/(category|tag|author|page)/", h):
            img = a.find("img") or (a.find_parent("article") and a.find_parent("article").find("img"))
            out.append({"source": site, "kind": "article", "url": h, "title": title,
                        "thumbnail": img and (img.get("data-src") or img.get("src")), "query": q})
    return list({r["url"]: r for r in out}.values())


# ---------- short films (free to watch)
def shortoftheweek(q, limit):
    """Short of the Week's own API: curated shorts with filmmaker, country, minutes, genre, topic and the player link."""
    data, status = _web.get_json(f"https://www.shortoftheweek.com/api/v1/search?q={quote_plus(q)}&type=film&limit={limit}")
    out = []
    for x in (data or {}).get("data", []):
        if not x.get("post_title") or not x.get("post_date") or not x.get("filmmaker"):
            continue  # articles (guides, news) have no filmmaker
        d = x["post_date"][:10].split("-")
        page = f"https://www.shortoftheweek.com/{d[0]}/{d[1]}/{d[2]}/{x['post_name']}/"
        play = x.get("play_link") or ""
        m = re.search(r"player\.vimeo\.com/video/(\d+)", play) or re.search(r"youtube\.com/embed/([\w-]{11})", play)
        watch = (f"https://vimeo.com/{m.group(1)}" if "vimeo" in play else f"https://www.youtube.com/watch?v={m.group(1)}") if m else None
        thumb = x.get("background_image") or x.get("thumbnail") or ""
        rec = {"source": "shortoftheweek", "kind": "short", "url": page, "title": x["post_title"], "year": int(d[0]),
               "maker": H.unescape(x.get("filmmaker") or ""),
               "credits": {"director": [H.unescape(n).strip() for n in re.split(r"\s*&amp;\s*|\s*&\s*|,\s*", x["filmmaker"]) if n.strip()]},
               "description": re.sub(r"<[^>]+>", "", x.get("post_excerpt") or "")[:500],
               "runtime_min": int(x["duration"]) if str(x.get("duration") or "").isdigit() else None,
               "countries": [(x.get("country") or {}).get("display_name")] if isinstance(x.get("country"), dict) else [],
               "genre": (x.get("genre") or {}).get("display_name") if isinstance(x.get("genre"), dict) else None,
               "topic": (x.get("topic") or {}).get("display_name") if isinstance(x.get("topic"), dict) else None,
               "thumbnail": ("https:" + thumb) if thumb.startswith("//") else thumb or None, "query": q}
        if watch:
            rec["extra_urls"] = [watch]
        out.append(rec)
    if not out and status not in (200, 414):  # 414 is how this API says "no results"
        print(f"  Short of the Week API answered HTTP {status}")
    return out[:limit]


# ---------- documentaries
DOC_CHANNELS = {  # YouTube channels that publish full documentaries (checked 2026-10-21)
    "@guardiandocumentaries": "Guardian Documentaries",
    "@nytopinion": "The New York Times Op-Docs",       # Op-Docs live on the Opinion channel
    "@aljazeeradocumentary": "Al Jazeera Documentary (Arabic)",
    "@AlJazeeraEnglish": "Al Jazeera English (Witness, 101 East)",
    "@BBCStories": "BBC Stories",
    "@povdocs": "POV",
}


def channel_search(handle, q, limit=8):
    """Search inside one YouTube channel (its own search page)."""
    page = _web.get(f"https://www.youtube.com/{handle}/search?query={quote_plus(q)}", browser="never", use_cache=False)
    words = [w.lower() for w in re.findall(r"\w{4,}", q)]
    out = []
    for c in S.parse_youtube_search(page.get("text") or ""):
        title = (c.get("title") or "").lower()
        if words and not any(w in title for w in words):
            continue  # a channel search with no match lists the channel's latest uploads: not results
        if len(out) >= limit:
            break
        out.append({"source": "youtube", "kind": "documentary", "url": c["url"], "title": c.get("title"),
                    "channel": c.get("channel") or DOC_CHANNELS.get(handle, handle), "views": c.get("views"),
                    "published": c.get("published"), "thumbnail": c.get("thumbnail"), "query": f"{handle}: {q}"})
    return out


def documentaries(q, limit):
    """Documentaries on a subject: Short of the Week's documentary genre, the documentary channels, and YouTube."""
    out = [dict(r, kind="documentary") for r in shortoftheweek(q, 40) if (r.get("genre") or "").lower() == "documentary"][:limit]
    for handle in DOC_CHANNELS:
        out += channel_search(handle, q, max(2, limit // 2))
    out += [dict(r, kind="documentary") for r in youtube(f"{q} documentary", 50000)[:limit]]
    return list({r["url"]: r for r in out}.values())


# ---------- video platforms
def youtube(q, min_views):
    page = _web.get(f"https://www.youtube.com/results?search_query={quote_plus(q)}", browser="never")
    out = []
    for c in S.parse_youtube_search(page.get("text") or ""):
        if (c.get("views") or 0) >= min_views:
            out.append({"source": "youtube", "kind": "video", "url": c["url"], "title": c.get("title"), "channel": c.get("channel"),
                        "views": c.get("views"), "published": c.get("published"), "thumbnail": c.get("thumbnail"), "query": q})
    return out


def vimeo(urls):
    out = []
    for u in urls:
        data, status = _web.get_json("https://vimeo.com/api/oembed.json?url=" + quote(u, safe=""))
        if not data:
            out.append({"source": "vimeo", "kind": "video", "url": u, "http_status": status,
                        "error": f"oEmbed HTTP {status} (private, removed or not a video page)"})
            continue
        desc = data.get("description") or ""
        out.append({"source": "vimeo", "kind": "video", "url": u, "title": data.get("title"), "channel": data.get("author_name"),
                    "channel_url": data.get("author_url"), "duration_s": data.get("duration"),
                    "published": (data.get("upload_date") or "")[:10] or None, "thumbnail": data.get("thumbnail_url"),
                    "description": desc[:600], "timestamps": timestamps(desc), "http_status": status})
    return out


def key(r):
    """One line per shot: Eyecannndy often has several clips (different shots) from the same video."""
    return f"eye:{r['clip_id']}" if r.get("clip_id") else r.get("url")


def youtube_description(url):
    """The uploader's own description and channel from a YouTube watch page (oEmbed has neither)."""
    import time
    for wait in (0, 8, 20):  # YouTube throttles quick repeats (HTTP 429): back off politely
        time.sleep(wait)
        page = _web.get(url, browser="never", use_cache=False)  # a cached copy may be a stripped page
        if page.get("status") != 429:
            break
    h = page.get("text") or ""
    m = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', h)
    ch = re.search(r'"ownerChannelName":"((?:[^"\\]|\\.)*)"', h)
    date = re.search(r'"publishDate":"([^"]+)"', h)
    dec = (lambda x: json.loads(f'"{x}"')) if m or ch else None
    return {"description": dec(m.group(1)) if m else "", "channel": dec(ch.group(1)) if ch else None,
            "published": date.group(1)[:10] if date else None}


def pages(urls):
    """Any page you found by web search (trade press with credits, a case page, a director's site)."""
    import time
    from fetch_meta import fetch_one
    out = []
    for u in urls:
        r = fetch_one(u, with_text=True)
        vid = re.search(r"youtube\.com|youtu\.be|vimeo\.com", u)
        if re.search(r"youtube\.com/watch|youtu\.be/", u):
            time.sleep(2)
            yt = youtube_description(u)
            r["description"] = yt["description"]
            r["channel"] = yt["channel"] or r.get("channel")
            r["published"] = yt["published"]
        out.append({"source": S.site_of(u), "kind": "video" if vid else "article", "url": u, "title": r.get("title"),
                    "description": (r.get("description") or "") + ("\n" + r["text"][:800] if r.get("text") else ""),
                    "thumbnail": r.get("thumbnail"), "http_status": r.get("http_status"), "error": r.get("error"),
                    "channel": r.get("channel"), "published": r.get("published"),
                    "timestamps": timestamps(r.get("text") or r.get("description") or "")})
    return out


def write(recs, out):
    if not out:
        return
    p = Path(out)
    old = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                r = json.loads(line)
                old[key(r)] = r
    for r in recs:
        old[key(r)] = {**old.get(key(r), {}), **r}
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in old.values()), encoding="utf-8")


def show(recs):
    for r in recs:
        cred = r.get("credits") or {}
        who = ", ".join(f"{k} {'/'.join(v)}" for k, v in cred.items() if k in ("director", "dop"))
        tech = ",".join(r.get("techniques_src", [])[:4])
        extra = " · ".join(x for x in [str(r.get("year") or r.get("published") or ""), who, tech,
                                       f"{r['runtime_min']} min" if r.get("runtime_min") else "", ", ".join(r.get("countries") or []),
                                       f"{r['views']:,} views" if r.get("views") else "", r.get("error", "")] if x)
        print(f"  {r.get('source', ''):<14} {(r.get('title') or '')[:58]:<58} {extra}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("query", nargs="+")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--min-views", type=int, default=10000)
    ap.add_argument("--genre", help="shortoftheweek only: keep one genre, e.g. documentary")
    ap.add_argument("--out")
    a = ap.parse_args()
    q = " ".join(a.query)
    src = a.source
    if src == "eyecannndy-technique":
        recs = eyecannndy(f"{EYE}/technique/{q.strip('/')}", a.limit, f"technique:{q}")
    elif src == "eyecannndy-search":
        recs = eyecannndy(f"{EYE}/search/?q={quote(q)}", a.limit, f"search:{q}")
        if not recs and " " in q:  # Eyecannndy's search is tag-based: phrases find nothing, single words do
            words = [w for w in q.split() if len(w) > 3]
            print(f"  no results for the phrase; searching the words: {', '.join(words)}")
            for w in words:
                recs += eyecannndy(f"{EYE}/search/?q={quote(w)}", max(2, a.limit // len(words)), f"search:{w}")
    elif src == "eyecannndy-person":
        recs = eyecannndy(f"{EYE}/{q.strip('/')}/", a.limit, f"person:{q}")
    elif src == "filmgrab":
        recs = filmgrab(q)[:a.limit * 2]
    elif src == "filmgrab-stills":
        recs = filmgrab_stills(q, a.limit)
    elif src == "shotcafe":
        recs = shotcafe(q)[:a.limit * 2]
    elif src in ARTICLE_SITES:
        recs = articles(src, q)[:a.limit * 2]
    elif src == "youtube":
        recs = youtube(q, a.min_views)[:a.limit * 2]
    elif src == "vimeo":
        recs = vimeo(a.query)
    elif src == "shortoftheweek":
        recs = shortoftheweek(q, 40 if a.genre else a.limit)
        if a.genre:  # the API ignores genre filters: filter here
            recs = [r for r in recs if (r.get("genre") or "").lower() == a.genre.lower()][:a.limit]
        recs = [dict(r, kind="documentary") if (r.get("genre") or "").lower() == "documentary" else r for r in recs]
    elif src == "docs":
        recs = documentaries(q, a.limit)
    elif src == "channel-search":
        recs = channel_search(a.query[0], " ".join(a.query[1:]), a.limit)
    elif src == "page":
        recs = pages(a.query)
    else:
        sys.exit(f"unknown source {src}; see --help")
    write(recs, a.out)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # piping into head is fine: the file is already written
    print(f"{len(recs)} candidates ({src}: {q})" + (f" → {a.out}" if a.out else ""))
    show(recs)


if __name__ == "__main__":
    main()
