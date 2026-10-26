"""Shared helpers: the scout's web/verify/brand scripts are reused, not copied."""
import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCOUT = SKILL.parent / "zamakan-reference-scout" / "scripts"
sys.path.insert(0, str(SCOUT))
REFS = SKILL / "references"

AR_MARKS = re.compile("[ً-ْـ]")             # diacritics and tatweel
AR_PUNCT = re.compile("[،؛؟٪-٭۔]")  # Arabic comma, semicolon, question mark...


def techniques():
    return json.loads((REFS / "techniques.json").read_text(encoding="utf-8"))["techniques"]


def moods():
    return json.loads((REFS / "moods.json").read_text(encoding="utf-8"))["moods"]


def tech_by_id():
    return {t["id"]: t for t in techniques()}


def norm(text):
    """Lowercase, strip accents and Arabic diacritics/tatweel, unify alef/ya/ta marbuta, so synonyms match loosely."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = AR_MARKS.sub("", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    t = AR_PUNCT.sub(" ", t)
    return re.sub(r"[^\w؀-ۿ']+", " ", t).strip()


def ar_variants(word):
    """An Arabic word plus its forms without the joined conjunction و/ف and the article ال ('والصحراء' finds 'صحراء')."""
    out = {word}
    for w in list(out):
        if len(w) > 4 and w[0] in "وف":
            out.add(w[1:])
    for w in list(out):
        if len(w) > 4 and w.startswith("ال"):
            out.add(w[2:])
    return out
