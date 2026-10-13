"""board.html v2: a self-contained, on-brand reference board (called by build_outputs.py).

Order follows how a kickoff is run: what we learned (insights) → what we recommend → the territories →
the competition → patterns and white space → deep dives → every reference → what to check before kickoff.
Dressed in the brand kit (brandkit.py): the client's logo variant approved for each background, the client's own
font files (subset and embedded, so the file works offline), colours by role, panel radius, divider and the
signature graphic element (an arch frame) used once, on the cover.
"""
import base64
import html
import io
import re

from theme import font_links, lum, mix, stack

E = html.escape
RING_ORDER = ["direct", "category", "adjacent", "wildcard"]
RING_NAME = {"direct": "Direct", "category": "Category", "adjacent": "Adjacent", "wildcard": "Wildcard"}


def data_uri(path, mime=None):
    if not path:
        return ""
    mime = mime or ("image/svg+xml" if str(path).endswith(".svg") else "image/png")
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def embedded_fonts(kit, text):
    """@font-face rules for the client's own font files, subset to the characters the board uses."""
    if not kit["font_files"]:
        return ""
    import logging
    from fontTools import subset
    from fontTools.ttLib import TTFont
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    chars = set(text) | set("0123456789 .,;:!?()[]-–—'\"’“”/&%+#@·→↗✓☐")
    rules = []
    for f in kit["font_files"]:
        try:
            font = TTFont(str(f["path"]))
            opts = subset.Options()
            opts.layout_features = ["*"]  # keep Arabic joining/ligatures
            opts.name_IDs, opts.hinting, opts.notdef_outline = ["*"], False, True
            sub = subset.Subsetter(opts)
            sub.populate(unicodes={ord(c) for c in chars})
            sub.subset(font)
            buf = io.BytesIO()
            font.save(buf)
        except Exception:  # noqa: BLE001 - a font that cannot be subset is skipped; the stack falls back
            continue
        rules.append(f"@font-face{{font-family:'{f['family']}';src:url(data:font/ttf;base64,{base64.b64encode(buf.getvalue()).decode()}) "
                     f"format('truetype');font-weight:{f['weight']};font-display:swap}}")
    return "".join(rules)


def root_css(kit):
    th = kit["theme"]
    div_color = (re.search(r"#[0-9A-Fa-f]{6}", kit["divider"] or "") or [th["line"]])[0]
    v = {"bg": th["bg"], "panel": th["panel"], "ink": th["ink"], "heading": th["heading"], "muted": th["muted"],
         "line": th["line"], "accent": th["accent"], "accent-text": th["accent_text"], "on-accent": th["on_accent"],
         "chip": th["chip"], "dark": th["dark"], "on-dark": th["on_dark"], "on-dark-muted": mix(th["on_dark"], th["dark"], 0.3),
         "deco": div_color, **th["ring"], **{f"on-{k}": c for k, c in th["ring_on"].items()},
         "disp": stack(th["display_font"], th["ar_display_font"]), "body": stack(th["body_font"], th["ar_body_font"]),
         "ar": stack(th["ar_body_font"], th["body_font"]), "ar-disp": stack(th["ar_display_font"], th["ar_body_font"]),
         "disp-w": th["display_weight"], "r": kit["radius"], "shadow": kit["shadow"] or "none"}
    return ":root{" + ";".join(f"--{k}:{c}" for k, c in v.items()) + \
        f";color-scheme:{'dark' if lum(th['bg']) < 0.2 else 'light'}}}"


CSS = """
*{box-sizing:border-box} html{-webkit-text-size-adjust:100%} body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 var(--body)}
a{color:var(--accent-text)} img{display:block;max-width:100%}
.wrap{max-width:1240px;margin:0 auto;padding-inline:clamp(16px,4vw,40px)}
h1,h2,h3{font-family:var(--disp);font-weight:var(--disp-w);color:var(--heading);text-wrap:balance;margin:0}
h2{font-size:clamp(26px,3vw,34px);line-height:1.15} h3{font-size:22px;line-height:1.2}
.ar{font-family:var(--ar);direction:rtl;letter-spacing:0} .ar-d{font-family:var(--ar-disp);direction:rtl;letter-spacing:0}
.eyebrow{font:600 12px/1.2 var(--body);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.muted{color:var(--muted)} small{font-size:13px}
section{padding-block:clamp(40px,6vw,72px)} section+section{border-top:1px solid var(--line)}
.sec-head{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:28px;flex-wrap:wrap}
.sec-head p{margin:6px 0 0;max-width:62ch;color:var(--muted)}
.divider{display:flex;align-items:center;gap:10px;color:var(--deco);margin:0 0 18px} .divider:before,.divider:after{content:"";height:1px;background:var(--deco);flex:1}
.divider i{width:8px;height:8px;background:var(--deco);transform:rotate(45deg);display:block}
/* cover */
.cover{background:var(--dark);color:var(--on-dark)} .cover .wrap{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:clamp(24px,5vw,64px);align-items:end;padding-block:28px clamp(40px,6vw,72px)}
.topbar{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;gap:16px;padding-bottom:clamp(28px,6vw,72px)}
.topbar img{height:clamp(64px,8vw,96px);width:auto} .topbar .wordmark{font:var(--disp-w) 22px/1 var(--disp)} .topbar .eyebrow{color:var(--on-dark-muted);text-align:end}
.cover h1{color:var(--on-dark);font-size:clamp(38px,6vw,72px);line-height:1.02;letter-spacing:-.01em}
.cover .lede{color:var(--on-dark-muted);font-size:18px;max-width:52ch;margin:18px 0 0}
.stats{display:flex;flex-wrap:wrap;gap:28px;margin-top:36px} .stat b{display:block;font:var(--disp-w) 40px/1 var(--disp);color:var(--on-dark)}
.stat span{font-size:13px;color:var(--on-dark-muted)}
.hero{position:relative} .hero img{width:100%;aspect-ratio:4/5;object-fit:cover;border-radius:var(--r)} .hero.arch img{border-radius:9999px 9999px 0 0}
.hero figcaption{font-size:13px;color:var(--on-dark-muted);margin-top:10px}
/* insights */
.ins{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}
.ins article{background:var(--panel);border-radius:var(--r);padding:24px;display:grid;gap:12px;align-content:start;box-shadow:var(--shadow);border-top:3px solid var(--accent)}
.ins .n{font:var(--disp-w) 34px/1 var(--disp);color:var(--accent-text)} .ins p{margin:0;font-size:17px;line-height:1.5}
.src{font-size:13px;color:var(--muted)} .src a{font-weight:600}
/* recommendation */
.rec{background:var(--panel);border-radius:var(--r);padding:clamp(24px,4vw,44px);display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:32px;box-shadow:var(--shadow);border-inline-start:6px solid var(--accent)}
.rec .big{font:var(--disp-w) clamp(22px,2.4vw,30px)/1.3 var(--disp);color:var(--heading);margin:10px 0 0}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px} .chip{display:inline-block;font:600 13px/1 var(--body);padding:8px 12px;border-radius:999px;background:var(--accent);color:var(--on-accent);text-decoration:none}
/* territories */
.terr{display:grid;gap:22px}
.t{background:var(--panel);border-radius:var(--r);display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);overflow:hidden;box-shadow:var(--shadow)}
.t .txt{padding:clamp(22px,3vw,36px);display:grid;gap:14px;align-content:start}
.t .names{display:flex;justify-content:space-between;align-items:baseline;gap:20px;flex-wrap:wrap}
.t .names .ar-d{font-size:26px;color:var(--muted);line-height:1.5} .t .num{font:600 12px/1 var(--body);letter-spacing:.12em;text-transform:uppercase;color:var(--accent-text)}
.t .thesis{font-size:19px;line-height:1.5;margin:0;color:var(--ink)} .t .why{margin:0;color:var(--muted)}
.t .cols{display:grid;grid-template-columns:1fr 1fr;gap:18px} .t ul{margin:6px 0 0;padding-inline-start:18px;display:grid;gap:4px;font-size:15px}
.t .pics{display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:3px;background:var(--line);min-height:300px}
.t .pics a{position:relative;display:block;background:var(--chip);overflow:hidden} .t .pics a:first-child{grid-column:1/-1}
.t .pics img{width:100%;height:100%;object-fit:cover} .code{position:absolute;inset-inline-start:8px;top:8px;font:600 12px/1 var(--body);background:var(--dark);color:var(--on-dark);padding:5px 7px;border-radius:3px}
.tag{display:inline-block;font:600 11px/1 var(--body);letter-spacing:.08em;text-transform:uppercase;padding:6px 9px;border-radius:999px;background:var(--accent);color:var(--on-accent);margin-inline-start:8px;vertical-align:middle}
/* sparks */
.sparks{background:var(--dark);color:var(--on-dark)} section.sparks+section{border-top:0} .sparks h2{color:var(--on-dark)}
.sparks .eyebrow,.sparks .sec-head p{color:var(--on-dark-muted)}
.sgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}
.spark{display:grid;gap:12px;align-content:start} .spark .img{position:relative;display:block;aspect-ratio:16/10;background:var(--on-dark-muted);overflow:hidden;border-radius:var(--r)}
.spark .img img{width:100%;height:100%;object-fit:cover} .spark .q{font:var(--disp-w) 22px/1.3 var(--disp);margin:0;color:var(--on-dark)}
.spark .from,.spark .what{margin:0;font-size:14px;color:var(--on-dark-muted)} .spark .from b{color:var(--on-dark)} .spark a.go{color:var(--on-dark);font-weight:600;font-size:14px}
/* tables */
.tbl{width:100%;border-collapse:collapse;background:var(--panel);border-radius:var(--r);overflow:hidden;font-size:15px;box-shadow:var(--shadow)}
.tbl th{font:600 12px/1.2 var(--body);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);text-align:start;padding:14px 16px;border-bottom:1px solid var(--line)}
.tbl td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top} .tbl tr:last-child td{border-bottom:0}
.yes{color:var(--accent-text);font-weight:600} .no{color:var(--muted)}
.scroll{overflow-x:auto}
/* patterns */
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px} .box{background:var(--panel);border-radius:var(--r);padding:24px;box-shadow:var(--shadow)}
.box ol,.box ul{margin:10px 0 0;padding-inline-start:20px;display:grid;gap:10px}
/* deep dives */
.dive{display:grid;grid-template-columns:minmax(0,380px) minmax(0,1fr);gap:28px;background:var(--panel);border-radius:var(--r);padding:24px;box-shadow:var(--shadow)}
.dive img{width:100%;aspect-ratio:16/10;object-fit:cover;border-radius:calc(var(--r)/2)} .dive dl{margin:0;display:grid;grid-template-columns:140px 1fr;gap:10px 18px;font-size:15px}
.dive dt{color:var(--muted);font-weight:600} .dive dd{margin:0} .dives{display:grid;gap:18px}
/* references */
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px} .filters button{font:500 14px var(--body);border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;padding:7px 14px;cursor:pointer;min-height:36px}
.filters button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)} .filters button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}
.card{background:var(--panel);border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column;box-shadow:var(--shadow)}
.card .img{position:relative;aspect-ratio:16/10;background:var(--chip)} .card .img img{width:100%;height:100%;object-fit:cover}
.card .body{padding:16px;display:grid;gap:8px;flex:1;align-content:start} .card h4{margin:0;font:600 17px/1.3 var(--body);color:var(--heading)}
.card .brand{font:600 12px/1.2 var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)} .card .meta{font-size:13px;color:var(--muted)}
.card p{margin:0;font-size:15px} .card .why{color:var(--muted);font-size:14px} .card a.go{font-size:14px;font-weight:600;text-decoration:none;margin-top:auto;padding-top:6px}
.badges{display:flex;gap:6px;flex-wrap:wrap} .badge{font:600 11px/1 var(--body);padding:5px 8px;border-radius:999px;background:var(--chip);color:var(--ink)}
.ring-direct{background:var(--direct);color:var(--on-direct)}.ring-category{background:var(--category);color:var(--on-category)}
.ring-adjacent{background:var(--adjacent);color:var(--on-adjacent)}.ring-wildcard{background:var(--wildcard);color:var(--on-wildcard)}
.card[hidden]{display:none!important}
/* kickoff */
.check{list-style:none;padding:0;margin:0;display:grid;gap:12px} .check li{display:flex;gap:12px;align-items:flex-start;background:var(--panel);padding:16px 18px;border-radius:var(--r)}
.check li:before{content:"";flex:none;width:18px;height:18px;border:2px solid var(--accent);border-radius:3px;margin-top:3px}
footer{background:var(--dark);color:var(--on-dark-muted);font-size:14px} footer .wrap{padding-block:36px;display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start}
footer img{height:48px;width:auto} footer p{margin:0 0 6px}
@media (max-width:860px){.cover .wrap,.rec,.t,.dive,.two{grid-template-columns:1fr}.hero{max-width:420px}.t .cols{grid-template-columns:1fr}
 .dive dl{grid-template-columns:1fr}.dive dt{margin-top:6px} footer .wrap{grid-template-columns:1fr}}
@media print{.filters{display:none}section{break-inside:avoid-page}}
"""

JS = """
const state={ring:'all',region:'all'};
function apply(){document.querySelectorAll('.card').forEach(c=>{
 c.hidden=!((state.ring==='all'||c.dataset.ring===state.ring)&&(state.region==='all'||c.dataset.region===state.region));});
 document.getElementById('count').textContent=[...document.querySelectorAll('.card')].filter(c=>!c.hidden).length;}
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{
 const k=b.dataset.k; state[k]=b.dataset.v; document.querySelectorAll(`.filters button[data-k="${k}"]`).forEach(x=>x.setAttribute('aria-pressed',x===b));apply();}));
apply();
"""


def build(run, brief, client_name, kit, img, codes, h):
    """img: id -> data URI (or ''); codes: id -> 'R01'; h: helper namespace (display_title, meta_line, primary_url, link_label, region_of)."""
    refs = run["references"]
    byid = {r["id"]: r for r in refs}
    th = kit["theme"]
    who = (client_name or kit.get("client_name") or "this client").split()[0]

    def pic(r, alt=True):
        return f'<img src="{img[r["id"]]}" alt="{E(r["brand"]) + ": " + E(r["title"]) if alt else ""}">' if img.get(r["id"]) else ""

    def ref_link(rid):
        r = byid.get(rid)
        return f'<a href="#ref-{rid}">{codes[rid]}</a>' if r else ""

    divider = '<div class="divider" aria-hidden="true"><i></i></div>' if kit["divider"] else ""
    # cover
    logo = kit["logos"].get("on_dark")
    brand_html = (f'<img src="{data_uri(logo["svg"] or logo["png"])}" alt="{E(kit["client_name"] or "")}">' if logo
                  else f'<span class="wordmark">{E(client_name or th["name"])}</span>')
    hero_ref = next((byid[i] for i in run.get("top", []) if img.get(i)), next((r for r in refs if img.get(r["id"])), None))
    hero = (f'<figure class="hero{" arch" if kit["arch"] else ""}" style="margin:0">{pic(hero_ref)}'
            f'<figcaption>{codes[hero_ref["id"]]} · {E(hero_ref["brand"])}: {E(hero_ref["title"])}</figcaption></figure>') if hero_ref else "<div></div>"
    lede = " · ".join(E(brief[k]) for k in ("moment", "objective", "audience") if brief and brief.get(k)) or E(run["run"].get("question", ""))
    n_ver = sum(r["status"] == "verified" for r in refs)
    scope = run["run"].get("scope", "gcc")
    local = sum(h.region_of(r) == "gcc" for r in refs)
    stats = [(len(refs), "references"), (n_ver, "checked live"), (local, "from the GCC") if scope != "global" else
             (len({h.region_of(r) for r in refs}), "regions"), (len(run.get("territories", [])), "territories")]
    cover = (f'<header class="cover"><div class="wrap"><div class="topbar">{brand_html}<div class="eyebrow">Reference scout · '
             f'{E(run["run"]["mode"])}<br>{E(run["run"].get("created", ""))}</div></div>'
             f'<div><div class="eyebrow" style="color:var(--on-dark-muted);margin-bottom:14px">{E(scope.upper())} scope</div>'
             f'<h1>{E(h.display_title(run, brief, client_name))}</h1><p class="lede">{lede}</p>'
             f'<div class="stats">{"".join(f"<div class=stat><b>{n}</b><span>{E(t)}</span></div>" for n, t in stats)}</div></div>'
             f'{hero}</div></header>')
    S = []
    # insights
    if run.get("insights"):
        cards = "".join(f'<article><div class="n">{i:02d}</div><p>{E(x["text"])}</p><div class="src">'
                        f'<a href="{E(x["source_url"])}" target="_blank" rel="noopener">{E(x.get("source_name") or "Source")} ↗</a>'
                        f'{" · " + E(x["date"]) if x.get("date") else ""}{" · " + E(x["kind"]) if x.get("kind") else ""}</div></article>'
                        for i, x in enumerate(run["insights"], 1))
        S.append(f'<section id="insights"><div class="wrap">{divider}<div class="sec-head"><div><div class="eyebrow">What we learned</div>'
                 f'<h2>Insights</h2><p>Dated and sourced, so they can go in front of a client.</p></div></div><div class="ins">{cards}</div></div></section>')
    # recommendation
    rec = run.get("recommendation")
    if rec:
        tn = {t["id"]: t["name"] for t in run.get("territories", [])}
        chips = "".join(f'<a class="chip" href="#t-{tid}">{E(tn.get(tid, tid))}</a>' for tid in rec.get("territory_ids", []))
        S.append(f'<section id="recommendation"><div class="wrap"><div class="rec"><div><div class="eyebrow">Our recommendation</div>'
                 f'<p class="big">{E(rec["summary"])}</p><div class="chips">{chips}</div></div>'
                 f'<div><div class="eyebrow">Why</div><p style="margin:10px 0 0">{E(rec.get("rationale", ""))}</p></div></div></div></section>')
    # territories
    if run.get("territories"):
        recd = set((rec or {}).get("territory_ids", []))
        T = []
        leads = h.lead_order(run, img)
        for i, t in enumerate(run["territories"], 1):
            rs = leads[t["id"]]
            pics = "".join(f'<a href="#ref-{r["id"]}" title="{E(r["brand"])}: {E(r["title"])}">{pic(r)}<span class="code">{codes[r["id"]]}</span></a>' for r in rs)
            lists = "".join(f'<div><div class="eyebrow">{lab}</div><ul>{"".join(f"<li>{E(x)}</li>" for x in t[k])}</ul></div>'
                            for k, lab in (("example_executions", "Executions"), ("risks", "Watch-outs")) if t.get(k))
            built = ", ".join(ref_link(r) for r in t["reference_ids"] if r in byid)
            ar = f'<div class="ar-d" lang="ar">{E(t["name_ar"])}</div>' if t.get("name_ar") else ""
            T.append(f'<article class="t" id="t-{E(t["id"])}"><div class="txt"><div class="num">Territory {i:02d}'
                     f'{"<span class=tag>Recommended</span>" if t["id"] in recd else ""}</div>'
                     f'<div class="names"><h3>{E(t["name"])}</h3>{ar}</div>'
                     f'<p class="thesis">{E(t["thesis"])}</p>'
                     + (f'<p class="why"><b>Why {E(who)}:</b> {E(t["why_this_client"])}</p>' if t.get("why_this_client") else "")
                     + f'<div class="cols">{lists}</div><small class="muted">Built on {built}</small></div><div class="pics">{pics}</div></article>')
        S.append(f'<section id="territories"><div class="wrap">{divider}<div class="sec-head"><div><div class="eyebrow">Where we could go</div>'
                 f'<h2>Creative territories</h2></div></div><div class="terr">{"".join(T)}</div></div></section>')
    # sparks from elsewhere: far-away work, each with a provocation for this client
    sparks = [r for r in refs if r.get("spark")]
    if sparks:
        cards_s = "".join(f'<article class="spark"><a class="img" href="#ref-{r["id"]}">{pic(r)}<span class="code">{codes[r["id"]]}</span></a>'
                          f'<p class="q">{E(r["spark"])}</p><p class="from">From <b>{E(r["brand"])}</b>: {E(r["title"])} · '
                          f'{E(h.country_name(r.get("country")))} {E(str(r.get("year") or ""))}</p><p class="what">{E(r["card"]["idea"])}</p>'
                          f'<a class="go" href="{E(h.primary_url(r))}" target="_blank" rel="noopener">{h.link_label(r)} ↗</a></article>' for r in sparks)
        S.append(f'<section id="sparks" class="sparks"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Sparks from elsewhere</div>'
                 f'<h2>What if {E(who)}…</h2><p>Work from far outside the category and the region. Not references to copy: provocations '
                 f'to start a different conversation in the room.</p></div></div><div class="sgrid">{cards_s}</div></div></section>')
    # competitors
    if run.get("competitor_summary"):
        rows = "".join(f'<tr><td><b>{E(c["advertiser"])}</b></td><td class="{"yes" if c.get("found_campaign") else "no"}">'
                       f'{"Yes" if c.get("found_campaign") else "None found"}</td><td>{E(c.get("notes", ""))}'
                       + (f'<br><small class="muted">{E(", ".join(c["messaging_pillars"]))}</small>' if c.get("messaging_pillars") else "")
                       + f'</td><td>{", ".join(ref_link(r) for r in c.get("reference_ids", []) if r in byid) or "–"}</td>'
                       f'<td><small class="muted">{E(c.get("checked", ""))}</small></td></tr>' for c in run["competitor_summary"])
        S.append(f'<section id="competitors"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">The competition</div><h2>What competitors run</h2>'
                 f'<p>Every named competitor was checked; "none found" means searched, not ignored.</p></div></div><div class="scroll"><table class="tbl">'
                 f'<thead><tr><th>Competitor</th><th>Campaign found</th><th>What they own</th><th>Refs</th><th>Checked</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div></div></section>')
    # patterns & white space
    if run.get("patterns") or run.get("white_space"):
        pats = "".join(f'<li>{E(p["pattern"])} <small class="muted">{", ".join(ref_link(r) for r in p["reference_ids"] if r in byid)}</small></li>'
                       for p in run.get("patterns", []))
        white = "".join(f"<li>{E(w)}</li>" for w in run.get("white_space", []))
        S.append(f'<section id="patterns"><div class="wrap"><div class="two"><div class="box"><div class="eyebrow">What everyone does</div>'
                 f'<h3 style="margin-top:6px">Patterns</h3><ol>{pats}</ol></div><div class="box"><div class="eyebrow">What nobody does</div>'
                 f'<h3 style="margin-top:6px">White space</h3><ul>{white}</ul></div></div></div></section>')
    # deep dives
    if run.get("top"):
        D = []
        for rid in run["top"]:
            r, td = byid[rid], byid[rid]["teardown"]
            rows = [("Insight", td["insight"]), ("Idea", td["idea"]), ("Execution", td["execution"])]
            rows += [(k.title(), td[k]) for k in ("channels", "tone", "results") if td.get(k)]
            rows += [("Borrow", "; ".join(td["transferable"])), (f"Cultural fit {td['cultural_fit']['score']}/5", td["cultural_fit"]["notes"])]
            if td.get("risks"):
                rows.append(("Risks", "; ".join(td["risks"])))
            D.append(f'<article class="dive" id="dive-{rid}"><div>{pic(r)}<p style="margin:12px 0 0"><b>{codes[rid]} · {E(r["brand"])}</b>: {E(r["title"])}<br>'
                     f'<small class="muted">{E(h.meta_line(r))}</small><br><a href="{E(h.primary_url(r))}" target="_blank" rel="noopener">{h.link_label(r)} ↗</a></p></div>'
                     f'<dl>{"".join(f"<dt>{E(k)}</dt><dd>{E(v)}</dd>" for k, v in rows)}</dl></article>')
        S.append(f'<section id="deep-dives"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">Worth studying</div><h2>Deep dives</h2></div></div>'
                 f'<div class="dives">{"".join(D)}</div></div></section>')
    # all references
    cards = ""
    for r in sorted(refs, key=lambda r: codes[r["id"]]):
        cards += (f'<article class="card" id="ref-{r["id"]}" data-ring="{r["ring"]}" data-region="{h.region_of(r)}"><div class="img">{pic(r)}'
                  f'<span class="code">{codes[r["id"]]}</span></div><div class="body"><div class="badges"><span class="badge ring-{r["ring"]}">{RING_NAME[r["ring"]]}</span>'
                  + ('<span class="badge">✓ checked live</span>' if r["status"] == "verified" else '<span class="badge">unverified</span>')
                  + ('<span class="badge">deep dive</span>' if r["id"] in run.get("top", []) else "")
                  + f'</div><div class="brand">{E(r["brand"])}</div><h4>{E(r["title"])}</h4><div class="meta">{E(h.meta_line(r))}</div>'
                  f'<p>{E(r["card"]["idea"])}</p><p class="why">{E(r["card"]["why_relevant"])}</p>'
                  f'<a class="go" href="{E(h.primary_url(r))}" target="_blank" rel="noopener">{h.link_label(r)} ↗</a></div></article>')
    ring_btns = "".join(f'<button data-k="ring" data-v="{k}" aria-pressed="false">{RING_NAME[k]} ({sum(r["ring"] == k for r in refs)})</button>'
                        for k in RING_ORDER if any(r["ring"] == k for r in refs))
    regions = sorted({h.region_of(r) for r in refs})
    reg_btns = "".join(f'<button data-k="region" data-v="{g}" aria-pressed="false">{h.REGION_NAME.get(g, g.title())}</button>' for g in regions)
    S.append(f'<section id="references"><div class="wrap"><div class="sec-head"><div><div class="eyebrow">The evidence</div>'
             f'<h2>All references (<span id="count">{len(refs)}</span>)</h2><p>Each one opens its original page; codes (R01…) are used throughout.</p></div></div>'
             f'<div class="filters" role="toolbar" aria-label="Filter references"><button data-k="ring" data-v="all" aria-pressed="true">All rings</button>{ring_btns}'
             f'<span style="width:12px"></span><button data-k="region" data-v="all" aria-pressed="true">All regions</button>{reg_btns}</div>'
             f'<div class="grid">{cards}</div></div></section>')
    # before kickoff
    if run.get("before_kickoff") or run.get("open_questions"):
        bk = "".join(f"<li>{E(x)}</li>" for x in run.get("before_kickoff", []))
        oq = "".join(f"<li>{E(x)}</li>" for x in run.get("open_questions", []))
        S.append(f'<section id="kickoff"><div class="wrap"><div class="two"><div><div class="eyebrow">Before kickoff</div><h3 style="margin:6px 0 16px">Check these first</h3>'
                 f'<ul class="check">{bk}</ul></div><div><div class="eyebrow">Open questions</div><h3 style="margin:6px 0 16px">For the client</h3>'
                 f'<ul class="check">{oq}</ul></div></div></div></section>')
    mark = kit["logos"].get("mark_dark") or kit["logos"].get("on_dark")
    look = (f'Styled with the {E(kit["client_name"])} design system (logos, fonts and colours from its files).' if kit["source"] == "client" else
            f'Styled with the {E(th["name"])} DESIGN.md from VoltAgent/awesome-design-md (MIT); a borrowed look, internal use only.' if kit["source"] == "awesome" else
            f'Styled with the {E(th["name"])} DESIGN.md.')
    mark_img = f'<img src="{data_uri(mark["svg"] or mark["png"])}" alt="">' if mark else ""
    footer = (f'<footer><div class="wrap">{mark_img}<div>'
              f'<p>Every reference links to its original page and was checked live on {E(run["run"].get("created", ""))}. Thumbnails © their owners, internal reference use only.</p>'
              f'<p>{look} Generated by zamakan-reference-scout.</p></div></div></footer>')
    head = (f'<meta charset="utf-8"><title>{E(h.display_title(run, brief, client_name))}</title><meta name="viewport" content="width=device-width,initial-scale=1">'
            + ("" if kit["font_files"] else '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' + font_links(th)))
    body = cover + "<main>" + "".join(S) + "</main>" + footer
    text = re.sub(r"<[^>]+>", " ", html.unescape(body))
    return f'{head}<style>{embedded_fonts(kit, text)}{root_css(kit)}{CSS}</style>{body}<script>{JS}</script>'
