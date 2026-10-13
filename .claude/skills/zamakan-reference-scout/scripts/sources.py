"""Site parsers: HTML/JSON in, compact candidate records out. Pure functions (no network),
so every parser is tested offline against saved pages in tests/fixtures/scout/pages/.

A candidate record uses the reference-schema field names where they exist:
  url, source, title, brand, agency, country (ISO-2), country_name, year, month, media[], category,
  description, credits[], thumbnail, video, related[], views, published, channel
"""
import html as htmllib
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MEDIA_MAP = {  # source medium label -> schema media enum
    "film": "film", "tv": "film", "video": "film", "cinema": "film", "online video": "film",
    "print": "print", "press": "print", "magazine": "print", "newspaper": "print",
    "outdoor": "ooh", "ooh": "ooh", "ooh outdoor": "ooh", "billboard": "ooh", "ambient": "ooh",
    "digital": "digital", "online": "digital", "interactive": "digital", "web": "digital", "mobile": "digital",
    "social": "social", "social media": "social", "experiential": "experiential", "event": "experiential",
    "activation": "activation", "direct marketing": "activation", "promo": "activation",
    "radio": "radio", "audio": "radio", "packaging": "packaging", "design": "packaging",
    "influencer": "influencer", "pr": "pr", "public relations": "pr", "integrated": "integrated", "360°": "integrated", "360": "integrated", "branding": "other",
}
SITES = {"adsoftheworld.com": "adsoftheworld", "youtube.com": "youtube", "youtu.be": "youtube", "vimeo.com": "vimeo",
         "lovethework.com": "lovethework", "campaignme.com": "campaignme", "dandad.org": "dandad",
         "oneclub.org": "oneclub", "dubailynx.com": "dubailynx", "behance.net": "behance", "adforum.com": "adforum",
         "lbbonline.com": "lbbonline", "campaignlive.co.uk": "campaignlive", "adage.com": "adage", "adweek.com": "adweek",
         "facebook.com": "meta-ad-library", "tiktok.com": "tiktok", "instagram.com": "instagram",
         "snapchat.com": "snapchat", "x.com": "x", "twitter.com": "x"}


def site_of(url):
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for dom, key in SITES.items():
        if host == dom or host.endswith("." + dom):
            return key
    return host or "unknown"


def country_code(name):
    if not name:
        return None
    try:
        import pycountry
        return pycountry.countries.lookup(name.strip()).alpha_2
    except Exception:  # noqa: BLE001 - unknown or ambiguous names stay None
        fixes = {"uae": "AE", "united arab emirates": "AE", "ksa": "SA", "saudi arabia": "SA", "usa": "US",
                 "uk": "GB", "united kingdom": "GB", "turkey": "TR", "russia": "RU", "korea": "KR", "south korea": "KR"}
        return fixes.get(name.strip().lower())


def media_of(label):
    return MEDIA_MAP.get((label or "").strip().lower(), "other") if label else None


def _clean(t, n=None):
    t = re.sub(r"\s+", " ", htmllib.unescape(t or "")).strip()
    return t[:n].rstrip() + "…" if n and len(t) > n else t


def _meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _ld(soup):
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(s.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        out += d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []
    return out


# ------------------------------------------------------------------ generic
def parse_generic(html, url):
    """Open Graph / Twitter / JSON-LD / <title> fallback for any page."""
    s = BeautifulSoup(html, "lxml")
    ld = _ld(s)
    title = _meta(s, "og:title", "twitter:title") or (s.title.string if s.title else None)
    rec = {"url": url, "source": site_of(url), "title": _clean(title, 200) or None,
           "description": _clean(_meta(s, "og:description", "description", "twitter:description"), 400) or None,
           "thumbnail": _meta(s, "og:image", "twitter:image"),
           "published": _meta(s, "article:published_time", "og:published_time", "datePublished")}
    for d in ld:
        if not isinstance(d, dict):
            continue
        rec["published"] = rec["published"] or d.get("datePublished") or d.get("uploadDate")
        if d.get("@type") == "VideoObject":
            rec["video"] = d.get("contentUrl") or d.get("embedUrl")
            rec["thumbnail"] = rec["thumbnail"] or (d.get("thumbnailUrl") if isinstance(d.get("thumbnailUrl"), str) else None)
    if rec["published"] and re.match(r"\d{4}", rec["published"]):
        rec["year"] = int(rec["published"][:4])
    if rec["thumbnail"]:
        rec["thumbnail"] = urljoin(url, rec["thumbnail"])
    return {k: v for k, v in rec.items() if v not in (None, "", [])}


# ------------------------------------------------------------------ Ads of the World
AOTW_RX = {  # the site's standard summary sentence, matched piece by piece (wording varies)
    "when": re.compile(r"campaign titled '(?P<title>.+?)' was published in (?P<country>[^.]+?) in (?P<month>[A-Za-z]+), (?P<year>\d{4})\."),
    "brand": re.compile(r"created for the brands?: (?P<brand>.+?)(?:, by ad (?:agency|agencies|school): (?P<agency>.+?))?\s*,?\s*\.\s"),
    "media": re.compile(r"This (?P<medium>[^.']+?) (?:medium|media) campaign is related to the (?P<industry>.+?) industr(?:y|ies)"),
    "assets": re.compile(r"contains (?P<assets>\d+) media assets?"),
}


def parse_aotw_campaign(html, url):
    rec = parse_generic(html, url)
    rec["source"] = "adsoftheworld"
    s = BeautifulSoup(html, "lxml")
    vid = next((d for d in _ld(s) if isinstance(d, dict) and d.get("@type") == "VideoObject"), None)
    if vid and isinstance(vid.get("thumbnailUrl"), str):
        vt, og = vid["thumbnailUrl"], rec.get("thumbnail")
        if "adsoftheworld" in vt or not og:
            rec["thumbnail"] = vt  # stable CDN link (og:image is a long redirect URL)
            alts = [og] if og else []
        else:  # an embedded YouTube/Vimeo thumbnail dies with the video; the page's own share image doesn't
            alts = [vt]
        if alts:
            rec["thumbnail_alts"] = alts
    for t in s(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = s.get_text(" | ", strip=True)
    flat = re.sub(r"\s*\|\s*", " ", text)
    g = {}
    for rx in AOTW_RX.values():
        m = rx.search(flat)
        if m:
            g.update({k: v for k, v in m.groupdict().items() if v})
    if g.get("title"):
        rec["title"] = _clean(g["title"])
    if g.get("country"):
        rec.update(country_name=_clean(g["country"]), country=country_code(g["country"]),
                   year=int(g["year"]), month=MONTHS.get(g["month"].lower()))
    if g.get("brand"):
        names = [x.strip() for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", _clean(g["brand"]).rstrip(",")) if x.strip()]
        rec["brand"] = names[-1] if len(names) == 2 and names[-1] in names[0] else names[0]  # "Al-Futtaim IKEA and IKEA" -> IKEA
        if len(names) > 1:
            rec["brands"] = names
            rec["brand_raw"] = _clean(g["brand"]).rstrip(",")  # e.g. one organisation whose name contains commas
    if g.get("agency"):
        rec["agency"] = _clean(g["agency"]).replace(" and ", ", ")
    if g.get("medium"):
        labels = [x.strip() for x in re.split(r",\s*(?:and\s+)?|\s+and\s+", g["medium"]) if x.strip()]
        rec["medium_label"] = _clean(g["medium"])
        rec["media"] = sorted({media_of(x) for x in labels})
        rec["category"] = _clean(g["industry"])
    if g.get("assets"):
        rec["media_assets"] = int(g["assets"])
    if g:
        rec["kind"] = "student" if re.search(r"\bstudent campaign titled|by ad school", flat) else "professional"
    ogt = (_meta(s, "og:title") or "").split(" • ")[0]
    if not rec.get("brand") and ": " in ogt:  # pages without the summary sentence: "Brand: Title • Ads of the World"
        rec["brand"], t = [x.strip() for x in ogt.split(": ", 1)]
        rec["title"] = rec.get("title") if g.get("title") else t
    if " • " in (rec.get("title") or ""):
        rec["title"] = rec["title"].split(" • ")[0].split(": ", 1)[-1]
    desc = re.search(r"\| Description \| (.+?) \| This\s+(?:professional|student)", text, re.S)
    if desc:
        rec["description"] = _clean(desc.group(1).replace(" | ", " "), 600)
    cred = re.search(r"\| Credits \| (.+?) \| Categories \|", text, re.S)
    if cred:
        rec["credits"] = [_clean(c) for c in cred.group(1).split(" | ") if ":" in c][:14]
    rel, seen = [], set()
    head = text.find("Related Campaigns")
    if head > 0:
        for a in s.find_all("a", href=True):
            h = a["href"]
            if re.match(r"^/campaigns/(?!new)[a-z0-9-]+$", h) and h not in seen and h != urlparse(url).path:
                seen.add(h)
                rel.append(urljoin(url, h))
        rec["related"] = rel[:12]
    return {k: v for k, v in rec.items() if v not in (None, "", [])}


def parse_aotw_listing(html, base="https://www.adsoftheworld.com"):
    """Search results / country / industry / brand / agency list → cards."""
    s = BeautifulSoup(html, "lxml")
    cards = []
    for card in s.find_all("div", id=re.compile(r"^campaign_card_\d+")):
        a = card.find("a", href=re.compile(r"^/campaigns/(?!new)"))
        if not a:
            continue
        img = card.find("img")
        texts = [t for t in card.stripped_strings]
        agency = next((t.split(":", 1)[1].strip() for t in texts if t.startswith("Agency:")), None)
        if agency is None:
            i = next((i for i, t in enumerate(texts) if t == "Agency:"), None)
            agency = texts[i + 1] if i is not None and i + 1 < len(texts) else None
        title = img.get("alt") if img else None
        rest = [t for t in texts if t not in (title, "Agency:", agency) and not t.startswith("Agency:")]
        cards.append({k: v for k, v in {
            "url": urljoin(base, a["href"]), "source": "adsoftheworld", "title": _clean(title),
            "brand": _clean(rest[0]) if rest else None, "agency": agency,
            "thumbnail": img.get("src") if img else None}.items() if v})
    nxt = s.find("a", href=re.compile(r"[?&]page=\d+"), string=re.compile(r"Next|›|»"))
    pages = [int(x) for x in re.findall(r"[?&]page=(\d+)", " ".join(a["href"] for a in s.find_all("a", href=True)))]
    return {"cards": cards, "last_page": max(pages) if pages else 1, "has_next": bool(nxt) or bool(pages)}


# ------------------------------------------------------------------ YouTube
def parse_youtube_search(html):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    out = []

    def walk(n):
        if isinstance(n, dict):
            v = n.get("videoRenderer")
            if v and v.get("videoId"):
                snippet = " ".join(r.get("text", "") for d in v.get("detailedMetadataSnippets", [])
                                   for r in d.get("snippetText", {}).get("runs", []))
                views = re.sub(r"[^\d]", "", v.get("viewCountText", {}).get("simpleText", "") or "")
                thumbs = v.get("thumbnail", {}).get("thumbnails", [])
                out.append({k: x for k, x in {
                    "url": f"https://www.youtube.com/watch?v={v['videoId']}", "source": "youtube",
                    "title": _clean("".join(r["text"] for r in v.get("title", {}).get("runs", []))),
                    "channel": (v.get("ownerText", {}).get("runs") or [{}])[0].get("text"),
                    "published": v.get("publishedTimeText", {}).get("simpleText"),
                    "views": int(views) if views else None,
                    "duration": v.get("lengthText", {}).get("simpleText"),
                    "description": _clean(snippet, 300) or None,
                    "thumbnail": thumbs[-1]["url"].split("?")[0] if thumbs else None}.items() if x not in (None, "")})
            for x in n.values():
                walk(x)
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(json.loads(m.group(1)))
    return out


def parse_oembed(data, url):
    """YouTube / Vimeo oEmbed JSON → record."""
    src = site_of(url)
    rec = {"url": url, "source": src, "title": _clean(data.get("title")), "channel": data.get("author_name"),
           "thumbnail": data.get("thumbnail_url"), "description": _clean(data.get("description"), 400) or None,
           "published": data.get("upload_date"), "duration_s": data.get("duration")}
    if rec["published"] and re.match(r"\d{4}", str(rec["published"])):
        rec["year"] = int(str(rec["published"])[:4])
    rec["media"] = ["film"]
    return {k: v for k, v in rec.items() if v not in (None, "", [])}


def main_text(html, limit=4000):
    """Readable body text of an article/case page (for deep teardowns from trade press)."""
    s = BeautifulSoup(html, "lxml")
    for tag in s(["script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form", "iframe"]):
        tag.decompose()
    node = s.find("article") or s.find("main")
    if not node:
        divs = s.find_all("div")
        node = max(divs, key=lambda d: sum(len(p.get_text()) for p in d.find_all("p", recursive=False)), default=s.body)
    paras = [_clean(p.get_text(" ")) for p in (node or s).find_all(["p", "h2", "h3", "li"])]
    text = "\n".join(p for p in paras if len(p) > 30)
    if len(text) < 300:  # pages that don't use <p>: fall back to all visible text
        text = _clean((node or s).get_text(" "))
    return text[:limit] + ("…" if len(text) > limit else "")


def parse(url, html):
    """Dispatch on URL for HTML pages."""
    src = site_of(url)
    if src == "adsoftheworld" and "/campaigns/" in url:
        return parse_aotw_campaign(html, url)
    return parse_generic(html, url)
