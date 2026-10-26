#!/usr/bin/env python3
"""The writer's guide (Word, Arabic first): what the script desk does, how to talk to it, what the colours mean, how
to use every file it gives you, and every story structure explained (what it is, when to choose it, what to watch
for, its beats). Hand it to a writer on first use, or when they ask "how do I use this?" / «كيف أستخدم الملفات؟».

Usage:
  python guide.py [--lang ar|en] [--out <dir>] [--only structures|files]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _screenplay as S  # noqa: E402
import build_template as B  # noqa: E402

T = {
 "ar": {
  "title": "دليل مكتب السيناريو", "sub": "زمكان · مساعد الكتابة",
  "what": "ما الذي يفعله",
  "what_p": ["يساعدك على كتابة فيلمك، ولا يكتبه عنك. يسألك، ويرتّب لك البناء، ينسّق الصفحة، ويشير إلى ما يعيق النص برقم المشهد.",
             "كل ما تحصل عليه ملفات Word تفتحها وتكتب فيها كالمعتاد. إن أردت PDF أو صفحة ويب أو Fountain أو Final Draft فاطلبها."],
  "talk": "كيف تتحدث معه",
  "talk_items": ["اكتب ما تريد بكلماتك: «عندي فكرة فيلم…»، «أبغى قالب لفيلم قصير ١٢ دقيقة»، «نسّق السيناريو»، «أبغى ملاحظات على مسودتي»، «عندي مقابلات لفيلمي الوثائقي».",
                 "سيسألك في البداية أسئلة قليلة تغيّر العمل (المدة، البناء، نوع الملاحظات)، ويعطيك توصيته أولاً. يمكنك دائماً أن تختار غيرها.",
                 "في آخر كل رد يقترح عليك خطوة تالية أو يسألك سؤالاً عن قصتك. أجب متى شئت، أو تجاهله.",
                 "إن أردت منه ألا يسأل، قل ذلك وسيعمل بتوصياته."],
  "colours": "الألوان",
  "colours_items": ["الأزرق: كلماتك أنت، كما كتبتها.", "الرمادي: أسئلتنا.", "الأصفر: ما لم تقله قصتك بعد (فراغ)، أو ما ينقص.",
                    "ملاحظات الهامش بثلاثة ألوان حسب زاوية القراءة: أزرق للحكاية، برتقالي للشخصيات والصوت، أخضر مائي للشاشة والتنفيذ.",
                    "الأحكام: ✓ يعمل، ! يحتاج عملاً، ✕ يعيق النص. الرمز دائماً مع اللون."],
  "files": "ملفاتك وكيف تستخدمها",
  "file_list": [
   ("قالب البناء (فارغ)", ["أجب عن الأسئلة الرمادية في المربعات بكلماتك.", "أهداف الصفحات دليل لا قاعدة.",
                           "اكتب المسودة في آخر الملف بالأنماط الجاهزة: من «الصفحة الرئيسية ← الأنماط» اختر «عنوان المشهد» أو «الوصف» أو «الشخصية» أو «الحوار». هكذا يُقرأ نصك لاحقاً دون تخمين."]),
   ("القالب المبني على قصتك", ["قصتك في الأعلى كما أرسلتها، دون تغيير.", "جدول «ما سمعناه وما زال مفتوحاً»: كلماتك بالأزرق، والفراغ بالأصفر، وسؤال لكل عنصر.",
                               "محطة بمحطة: كلماتك حيث يبدو أنها تنتمي. إن لم تكن في مكانها فانقلها. اكتب في المربع تحت كل محطة.",
                               "المحطات الصفراء هي ما لم تكتشفه بعد في قصتك: ابدأ منها."]),
   ("السيناريو المنسّق", ["عدّل فيه بحرية بالأنماط نفسها. أرسله متى أردت ملاحظات أو تنسيقاً جديداً."]),
   ("ورقة النية", ["صفحة واحدة: عمّ الفيلم، ما الذي لست متأكداً منه، ما المقصود عمداً، لهجة كل شخصية، وأين تريد أن يُعرض.",
                   "املأها وأرسلها قبل القراءة: الملاحظات تُقاس على ما تريده أنت، ولا تُعَدّ اختياراتك المقصودة أخطاء."]),
   ("ملف الملاحظات", ["في أوله صفحة الملاحظات: الحكم العام، حكم كل زاوية، أولويات المسودة القادمة، أسئلة لك، ورسوم.",
                      "بعدها نصك وعلى الهامش تعليقات ملوّنة، كل تعليق ملاحظة أو سؤال، لا إعادة كتابة.",
                      "لإظهار التعليقات: «مراجعة ← إظهار التعليقات». كل زاوية قراءة «مراجِع» مستقل، فيمكنك إظهار زاوية واحدة: «مراجعة ← إظهار العلامات ← أشخاص محددون».",
                      "للرد: انقر على التعليق ← «رد»، واكتب مثلاً «مقصود» أو «تم» أو «لا أوافق لأن…». يمكنك أيضاً وضع علامة «تم الحل».",
                      "أرسل الملف مع مسودتك التالية: سيقرأ ردودك، ولن يكرر ملاحظة قلت إنها مقصودة."]),
   ("بطاقات المشاهد", ["جدول بالمشاهد بترتيبها. غيّر الأرقام في عمود الترتيب وأرسل الملف: يُعاد بناء النص بالترتيب الجديد."]),
   ("للوثائقي: المونتاج الورقي", ["عمودان: الصورة والصوت. كل اقتباس منقول حرفياً من التفريغ مع توقيته، فلا يُكتب كلام أحد من الذاكرة.",
                                   "العلامة ✂ تعني أن القطع يجمع كلام شخص من لحظتين مختلفتين: تأكد أن المعنى بقي كما قصده.",
                                   "الصفوف الصفراء ما ينقصنا بعد (ما يجب تصويره)."]),
   ("للوثائقي: السيناريو بعمودين", ["أضف صفاً لكل لحظة («تخطيط ← إدراج صف»). في عمود الصوت اكتب «الاسم: الكلام» لمن يتكلم، و«تعليق صوتي:» للتعليق."]),
   ("للوثائقي: سجل الأرشيف وقائمة التصوير", ["سجل الأرشيف: املأ المالك وحالة الحقوق والكلفة لكل مادة، وأرسله مع المسودة التالية فيُحفظ ما كتبته.",
                                              "قائمة التصوير: ما ينتظر موافقة أحد في الأعلى."]),
  ],
  "structures": "البناءات القصصية", "structures_p": "كل بناء طريقة لترتيب قصتك، لا قالب يُفرض عليها. اختر ما يشبه شكل قصتك، وإن لم تعرف فاسأل وسيقترح عليك.",
  "fits": "يناسب", "when": "متى تختاره", "watch": "انتبه", "beats": "المحطات", "source": "المصدر",
  "kinds": {"feature": "الأفلام الطويلة", "short": "الأفلام القصيرة", "documentary": "الوثائقي"},
  "groups": [("للأفلام الروائية", lambda s: "documentary" not in s["fits"]), ("للأفلام الوثائقية", lambda s: "documentary" in s["fits"])],
 },
 "en": {
  "title": "Script desk guide", "sub": "ZAMAKAN · writing assistant",
  "what": "What it does",
  "what_p": ["It helps you write your film; it never writes it for you. It asks questions, shows structure, formats the page and points at what holds the script back, with scene numbers.",
             "Everything you get is a Word file you open and write in as usual. Ask if you want a PDF, a web page, Fountain or Final Draft."],
  "talk": "How to talk to it",
  "talk_items": ["Say what you want in your own words: \"I have a film idea…\", \"a template for a 12-minute short\", \"format my script\", \"notes on my draft\", \"I have interviews for my documentary\".",
                 "At the start it asks a few questions that change the work (length, structure, kind of notes), with its recommendation first. You can always pick another.",
                 "At the end of each reply it suggests a next step or asks a question about your story. Answer when you like, or ignore it.",
                 "If you'd rather it didn't ask, say so and it will go with its recommendations."],
  "colours": "Colours",
  "colours_items": ["Blue: your own words, as you wrote them.", "Grey: our questions.", "Amber: what your story doesn't say yet (a gap), or what's missing.",
                    "Margin notes come in three colours by viewpoint: blue for story, orange for people and voice, aqua for screen and making.",
                    "Verdicts: ✓ working, ! needs work, ✕ holds it back. The icon always comes with the colour."],
  "files": "Your files and how to use them",
  "file_list": [
   ("Structure template (blank)", ["Answer the grey questions in the boxes, in your own words.", "Page targets are a guide, not a rule.",
                                   "Write the draft at the end in the built-in styles: Home → Styles → Scene Heading, Action, Character, Dialogue. Then your script can be read back with no guessing."]),
   ("Template built on your story", ["Your story at the top, exactly as you sent it.", "\"What we heard, and what's still open\": your words in blue, gaps in amber, a question for each.",
                                     "Beat by beat: your words where they seem to belong. Move them if they don't. Write in the box under each beat.",
                                     "Amber beats are what you haven't discovered yet: start there."]),
   ("Formatted script", ["Edit freely in the same styles. Send it back for notes or a fresh layout."]),
   ("Intent sheet", ["One page: what the film is about, what you're unsure of, what's deliberate, each character's dialect, where it should play.",
                     "Fill it in before a reading: notes are judged against what you want, and your deliberate choices aren't flagged."]),
   ("Notes file", ["It opens with the notes page: overall verdict, a verdict per viewpoint, priorities for the next draft, questions for you, charts.",
                   "Then your script with coloured margin comments: each one a note or a question, never a rewrite.",
                   "To see comments: Review → Show Comments. Each viewpoint is its own reviewer, so you can show one: Review → Show Markup → Specific People.",
                   "To reply: click a comment → Reply, and write e.g. \"deliberate\", \"fixed\" or \"I disagree because…\". You can also mark it Resolved.",
                   "Send the file back with your next draft: your replies are read, and a note you called deliberate isn't repeated."]),
   ("Scene cards", ["A table of your scenes in order. Change the numbers in the order column and send it back: the script is rebuilt in the new order."]),
   ("Documentary: paper edit", ["Two columns: picture and sound. Every quote is taken word for word from the transcript with its timecode, never typed from memory.",
                                "✂ means the cut joins one person's words from two different moments: make sure the meaning stays theirs.",
                                "Amber rows are what's still missing (what to film)."]),
   ("Documentary: two-column script", ["Add a row per moment (Layout → Insert Row). In the sound column write \"Name: words\" for someone speaking and \"Narration:\" for voice-over."]),
   ("Documentary: archive log and shoot list", ["Archive log: fill in owner, rights status and cost for each item; send it back with the next draft and what you filled in is kept.",
                                                 "Shoot list: anything waiting on someone's yes comes first."]),
  ],
  "structures": "Story structures", "structures_p": "Each structure is a way to arrange your story, not a mould to force it into. Choose the one that looks like your story's shape; if you're not sure, ask and you'll get a recommendation.",
  "fits": "Suits", "when": "Choose it when", "watch": "Watch for", "beats": "Beats", "source": "Source",
  "kinds": {"feature": "feature films", "short": "short films", "documentary": "documentaries"},
  "groups": [("For fiction", lambda s: "documentary" not in s["fits"]), ("For documentaries", lambda s: "documentary" in s["fits"])],
 }}


def explain_structure(doc, st, lang):
    """One structure, explained in plain words (also used by the templates)."""
    t = T[lang]
    ar = lang == "ar"
    B.para(doc, st["name_ar"] if ar else st["name"], lang, style="Heading 2")
    B.para(doc, st["summary_ar"] if ar else st["summary"], lang)
    if st.get("when"):
        B.para(doc, f"{t['when']}: {st['when_ar'] if ar else st['when']}", lang)
        B.para(doc, f"{t['watch']}: {st['tradeoff_ar'] if ar else st['tradeoff']}", lang, grey=True)
    B.para(doc, f"{t['fits']}: {'، '.join(t['kinds'][k] for k in st['fits']) if ar else ', '.join(t['kinds'][k] for k in st['fits'])} · {t['source']}: {st['source']}", lang, grey=True, size=9)


def build(lang="ar", only=None):
    t = T[lang]
    ar = lang == "ar"
    doc = S.new_document(lang)
    S.add_page_numbers(doc, lang)
    B.para(doc, t["title"], lang, style="Title")
    B.para(doc, t["sub"], lang, grey=True)
    if only != "structures":
        B.para(doc, t["what"], lang, style="Heading 1")
        for x in t["what_p"]:
            B.para(doc, x, lang)
        B.para(doc, t["talk"], lang, style="Heading 1")
        for x in t["talk_items"]:
            B.para(doc, x, lang, style="List Bullet")
        B.para(doc, t["colours"], lang, style="Heading 1")
        for x in t["colours_items"]:
            B.para(doc, x, lang, style="List Bullet")
        B.para(doc, t["files"], lang, style="Heading 1")
        for name, items in t["file_list"]:
            B.para(doc, name, lang, style="Heading 3")
            for x in items:
                B.para(doc, x, lang, style="List Bullet")
    if only != "files":
        S.page_break(doc)
        B.para(doc, t["structures"], lang, style="Heading 1")
        B.para(doc, t["structures_p"], lang, grey=True, italic=True)
        for group, keep in t["groups"]:
            B.para(doc, group, lang, style="Heading 1")
            for st in [s for s in S.STRUCTURES["structures"] if keep(s)]:
                explain_structure(doc, st, lang)
                B.para(doc, t["beats"], lang, bold=True, size=10)
                for b in st["beats"]:
                    B.para(doc, f"{b['name_ar'] if ar else b['name']}: {b['purpose_ar'] if ar else b['purpose']}", lang, style="List Bullet", size=10)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["ar", "en"], default="ar")
    ap.add_argument("--out", default=".")
    ap.add_argument("--only", choices=["structures", "files"])
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = {"ar": "دليل-مكتب-السيناريو", "en": "script-desk-guide"}[a.lang] + (f"-{a.only}" if a.only else "")
    path = out / f"{name}.docx"
    build(a.lang, a.only).save(path)
    print(f"guide → {path}")


if __name__ == "__main__":
    main()
