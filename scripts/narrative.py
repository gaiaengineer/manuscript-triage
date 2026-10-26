#!/usr/bin/env python3
"""Narrative pre-pass: the mechanical half of the reading questions.

    python3 narrative.py <manuscript>                  # analyse, write worksheet
    python3 narrative.py --render worksheet.json       # validate + emit markdown

Some of what an editor wants to know can be detected. POV and tense are countable.
Head-hops are countable, because a head-hop is two characters given interiority
inside one scene. Physical-attribute drift is countable. Flashback weight is
countable through pluperfect density.

The rest requires reading, and this script does not attempt it. It writes each
chapter to its own file, and a worksheet with the detected findings plus empty
fields for the chapter map, synopsis, inciting incident, protagonist's want,
ending type and confirmed loose threads. The agent reads the chapters and fills
those in. `--render` then checks the worksheet is complete and consistent before
turning it into report sections.

Detections here are CANDIDATES, not findings. Every one needs confirming against
the text, and the worksheet has a field for saying so.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from craft_floor import SENT_SPLIT_RE, WORD_RE  # noqa: E402
from structure import find_names  # noqa: E402

INTERIORITY = (r"felt|thought|knew|realized|realised|wondered|remembered|hoped|"
               r"feared|wanted|decided|understood|noticed|sensed|recalled|"
               r"regretted|suspected|believed")
PLUPERFECT_RE = re.compile(r"\bhad\s+(?:\w+ed|been|gone|seen|done|known|taken|"
                           r"come|found|told|left|made|thought|said)\b", re.I)
SCENE_BREAK_RE = re.compile(r"^\s*(?:[*#~—–-]\s*){3,}\s*$|^\s*\*\s*\*\s*\*\s*$")

COLOURS = (r"blue|green|brown|grey|gray|hazel|amber|black|blonde|blond|red|"
           r"auburn|silver|white|golden|dark|pale")
ATTRS = {
    "eyes": [rf"{{n}}(?:'s)?\s+eyes\s+(?:were|was|are)\s+({COLOURS})",
             rf"({COLOURS})[- ]eyed\s+{{n}}",
             rf"{{n}}(?:'s)?[^.]{{0,40}}?\b({COLOURS})\s+eyes"],
    "hair": [rf"{{n}}(?:'s)?\s+hair\s+(?:were|was|is)\s+({COLOURS})",
             rf"({COLOURS})[- ]haired\s+{{n}}",
             rf"{{n}}(?:'s)?[^.]{{0,40}}?\b({COLOURS})\s+hair"],
}

# Categories an acquiring editor should know about before page one. Deliberately
# neutral wording: this is for editorial awareness, never a judgement about
# whether the content belongs in the book.
CONTENT_TERMS = {
    "sexual content": ["naked", "undressed", "made love", "his mouth on",
                       "her mouth on", "thrust", "aroused", "orgasm", "nipple"],
    "graphic violence": ["blood pooled", "skull", "stabbed", "gutted", "severed",
                         "beaten", "screamed as", "broke his nose", "shot him",
                         "shot her", "corpse", "mutilated"],
    "self-harm or suicide": ["killed herself", "killed himself", "took her own life",
                             "took his own life", "cut her wrists", "cut his wrists",
                             "overdose", "hanged himself", "hanged herself",
                             "wanted to die"],
    "substance use": ["heroin", "cocaine", "needle in", "syringe", "overdosed",
                      "drunk again", "blackout drunk", "withdrawal"],
    "harm to a child": ["hit the boy", "hit the girl", "the child screamed",
                        "beat the child", "the baby was dead"],
    "sexual violence": ["raped", "rape", "assaulted her", "forced himself"],
}


def split_chapters(text):
    from analyse import split_chapters as sc
    return sc(text)


def scenes_of(body):
    """Split a chapter on typographic scene breaks. Many break markers do not
    survive extraction, so a chapter with none is treated as a single scene and
    the head-hop check becomes correspondingly coarse."""
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    out, cur = [], []
    for p in paras:
        if SCENE_BREAK_RE.match(p):
            if cur:
                out.append("\n\n".join(cur))
            cur = []
        else:
            cur.append(p)
    if cur:
        out.append("\n\n".join(cur))
    return out or [body]


def narration_only(text):
    """Strip speech, in either dialogue convention.

    Characters say "I" constantly whatever the narration is doing, so pronouns
    inside dialogue misread the point of view. Three things have to go:
    paragraphs opening with a quotation mark (a speech that may run over several
    paragraphs and close only at the end), paragraphs opening with a dash, and
    any remaining inline quoted span.
    """
    kept = []
    for para in text.split("\n\n"):
        head = para.lstrip()[:1]
        if head in ('"', "\u201c") or re.match(r"^\s*[-\u2013\u2014]\s+\S", para):
            continue
        kept.append(para)
    joined = "\n\n".join(kept)
    return re.sub(r"[\"\u201c][^\"\u201c\u201d]{0,2000}?[\"\u201d]", " ", joined)


def pov_and_tense(body):
    low = narration_only(body).lower()
    words = WORD_RE.findall(low)
    n = len(words) or 1
    first = sum(1 for w in words if w in ("i", "me", "my", "mine", "myself"))
    third = sum(1 for w in words if w in ("he", "she", "him", "her", "his", "they"))
    past = len(re.findall(r"\b(was|were|had|said|looked|went|came|took|thought)\b", low))
    pres = len(re.findall(r"\b(is|are|has|says|looks|goes|comes|takes|thinks)\b", low))
    # Classify by how often the narration says "I", not by whether it says "I"
    # more often than "he". A first-person narrator describing other people uses
    # third-person pronouns constantly, so a ratio test misreads whole chapters
    # of a first-person book as third person.
    first_rate = first / n * 1000
    return {
        "person": "first" if first_rate >= 4 else "third",
        "first_per_1k": round(first / n * 1000, 1),
        "tense": "past" if past >= pres else "present",
        "past_markers": past, "present_markers": pres,
        "pluperfect_per_1k": round(len(PLUPERFECT_RE.findall(body)) / n * 1000, 1),
    }


FIRST_PRON = {"i", "me", "my", "mine", "myself", "we", "us", "our"}
THIRD_PRON = {"he", "she", "him", "her", "his", "hers", "they", "them", "their"}


def pov_slips(body, dominant_person, chapter_person=None):
    """Individual narration paragraphs written in the wrong person.

    Measured per paragraph, not per scene or window. In a third-person novel the
    narration should essentially never say "I", so one paragraph that does is
    worth a look, and averaging over any larger unit hides exactly that.
    Dialogue is stripped first, since characters say "I" constantly.

    Chapters written wholly in another person are not slips; they are usually a
    deliberate alternating structure, and are reported separately as such.
    """
    # Only meaningful in a third-person book, where "I" in the narration is a
    # strong signal. In a first-person book the narrator describes other people
    # with he and she on nearly every page, so the reverse test is pure noise.
    if dominant_person != "third":
        return []
    if chapter_person and chapter_person != dominant_person:
        return []
    slips = []
    for i, p in enumerate([x.strip() for x in body.split("\n\n") if x.strip()], 1):
        words = [w.lower() for w in WORD_RE.findall(narration_only(p))]
        if len(words) < 8:
            continue
        first = sum(1 for w in words if w in FIRST_PRON)
        third = sum(1 for w in words if w in THIRD_PRON)
        odd = (dominant_person == "third" and first >= 2 and first > third) or \
              (dominant_person == "first" and third >= 2 and third > first)
        if odd:
            slips.append({
                "paragraph": i,
                "person": "first" if first > third else "third",
                "first_pronouns": first, "third_pronouns": third,
                "text": re.sub(r"\s+", " ", p)[:120],
            })
    return slips


def head_hops(body, names):
    """A head-hop is two different characters given interiority in one scene.

    Reports the scene, the characters, and the phrase for each, so every
    candidate can be checked in seconds.
    """
    found = []
    for si, scene in enumerate(scenes_of(body), 1):
        holders = defaultdict(list)
        for m in re.finditer(rf"\b([A-Z][a-z']+)\s+(?:{INTERIORITY})\b", scene):
            who = m.group(1)
            if who in names:
                holders[who].append(m.group(0))
        if len(holders) >= 2:
            found.append({
                "scene": si,
                "characters": sorted(holders),
                "evidence": {k: v[:2] for k, v in list(holders.items())[:4]},
            })
    return found


def attribute_drift(text, names):
    """Eye and hair colour given two different values for the same character."""
    out = []
    for nm in sorted(names):
        for attr, pats in ATTRS.items():
            seen = Counter()
            for pat in pats:
                for m in re.finditer(pat.replace("{n}", re.escape(nm)), text, re.I):
                    seen[m.group(1).lower()] += 1
            if len(seen) > 1:
                out.append({"character": nm, "attribute": attr,
                            "values": dict(seen)})
    return out


def loose_thread_candidates(chapters, names):
    """Names used repeatedly in one chapter and never seen again.

    Weak on its own: a character can be introduced and dismissed on purpose.
    These are candidates for the reader to confirm or discard.
    """
    n_ch = len(chapters)
    if n_ch < 4:
        return []
    per_ch = []
    for _, body in chapters:
        per_ch.append(Counter({nm: len(re.findall(rf"\b{re.escape(nm)}\b", body))
                               for nm in names}))
    out = []
    cutoff = int(n_ch * 0.75)
    for nm in names:
        counts = [c[nm] for c in per_ch]
        if sum(counts) < 3:
            continue
        last = max(i for i, v in enumerate(counts) if v)
        peak = max(range(n_ch), key=lambda i: counts[i])
        if last < cutoff and counts[peak] >= 3 and peak <= last:
            out.append({"name": nm, "peak_chapter": peak + 1,
                        "last_chapter": last + 1, "total": sum(counts),
                        "chapters_remaining_after": n_ch - last - 1})
    return sorted(out, key=lambda x: -x["total"])[:12]


# Phrases where a flagged word is entirely innocent. Without these, "naked eye"
# reports as sexual content.
CONTENT_EXCLUDE = re.compile(
    r"naked eye|naked truth|thrust (?:of|into) (?:the|a) (?:argument|conversation)|"
    r"shot him a (?:look|glance)|shot her a (?:look|glance)", re.I)


def content_candidates(chapters):
    """Content an editor should know about, matched on whole words only.

    Substring matching is not adequate here. "raped" appears inside "draped",
    and reporting sexual violence in a chapter because vines were draped over a
    path is the kind of error that makes the whole report untrustworthy.
    """
    out = defaultdict(list)
    for i, (_, body) in enumerate(chapters, 1):
        cleaned = CONTENT_EXCLUDE.sub(" ", body)
        hits_by_cat = {}
        for cat, terms in CONTENT_TERMS.items():
            hits = []
            for t in terms:
                pat = r"\b" + re.escape(t).replace(r"\ ", r"\s+") + r"\b"
                if re.search(pat, cleaned, re.I):
                    hits.append(t)
            if hits:
                hits_by_cat[cat] = hits
        for cat, hits in hits_by_cat.items():
            out[cat].append({"chapter": i, "terms": hits})
    return {k: v for k, v in out.items()}


def analyse(path, outdir):
    from analyse import load, trim_matter
    raw, manifest, label = load(str(path))
    paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
    lo, hi, _ = trim_matter(paras)
    text = "\n\n".join(paras[lo:hi])
    chapters = split_chapters(text)
    if not chapters:
        sys.exit("no chapters detected; cannot build a chapter map")

    names = find_names(text)
    total_words = len(WORD_RE.findall(text))

    outdir = Path(outdir)
    (outdir / "chapters").mkdir(parents=True, exist_ok=True)
    running = 0
    ch_meta = []
    for i, (title, body) in enumerate(chapters, 1):
        w = len(WORD_RE.findall(body))
        f = outdir / "chapters" / f"{i:02d}.txt"
        f.write_text(f"{title or f'Chapter {i}'}\n\n{body}", "utf-8")
        pt = pov_and_tense(body)
        ch_meta.append({
            "chapter": i,
            "title": title or f"Chapter {i}",
            "file": str(f),
            "words": w,
            "starts_at_pct": round(running / total_words * 100, 1),
            "pov": pt,
            "scenes": len(scenes_of(body)),
            "head_hop_candidates": head_hops(body, names),
            "one_line": "",          # <- agent fills from reading
        })
        running += w

    dom_person = Counter(c["pov"]["person"] for c in ch_meta).most_common(1)[0][0]
    dom_tense = Counter(c["pov"]["tense"] for c in ch_meta).most_common(1)[0][0]
    for c, (_, body) in zip(ch_meta, chapters):
        c["pov_slips"] = pov_slips(body, dom_person, c["pov"]["person"])
    inconsistent = [c["chapter"] for c in ch_meta
                    if c["pov"]["person"] != dom_person or c["pov"]["tense"] != dom_tense]
    flash = [c for c in sorted(ch_meta, key=lambda c: -c["pov"]["pluperfect_per_1k"])
             if c["pov"]["pluperfect_per_1k"] > 0][:5]

    worksheet = {
        "manuscript": manifest.get("source_file", str(path)),
        "title": (manifest.get("metadata") or {}).get("title"),
        "total_words": total_words,
        "chapters": ch_meta,
        "detected": {
            "dominant_pov": f"{dom_person} person, {dom_tense} tense",
            "pov_inconsistent_chapters": inconsistent,
            "head_hop_chapters": [c["chapter"] for c in ch_meta
                                  if c["head_hop_candidates"]],
            "pov_slip_scenes": [{"chapter": c["chapter"], **s}
                                for c in ch_meta for s in c.get("pov_slips", [])],
            "most_pluperfect_chapters": [
                {"chapter": c["chapter"], "per_1k": c["pov"]["pluperfect_per_1k"]}
                for c in flash],
            "attribute_drift": attribute_drift(text, names),
            "loose_thread_candidates": loose_thread_candidates(chapters, names),
            "content_candidates": content_candidates(chapters),
        },
        "to_be_filled_by_reading": {
            "synopsis": "",
            "inciting_incident": {"chapter": None, "pct_into_book": None,
                                  "what_happens": "", "quote": ""},
            "protagonist": {"name": "", "stated_want": "", "first_stated_chapter": None,
                            "first_stated_pct": None, "quote": ""},
            "timeline": {"strands": None, "description": "",
                         "flashback_share": ""},
            "ending_type": {"type": "", "note": "", "quote": ""},
            "confirmed_loose_threads": [],
            "confirmed_continuity_errors": [],
            "content_notes": [],
            "head_hops_confirmed": [],
            # For structure_fit.py. Record where the book ACTUALLY turns, with no
            # framework in mind; the matching against Save the Cat and the rest is
            # done afterwards, so that beats are not read into a book that has none.
            # pct comes from the chapter's starts_at_pct, adjusted within the chapter.
            # The cast, confirmed by reading. Merges aliases, which no
            # heuristic can do: Stephen and Armitage are one person, and so are
            # Alex, Alexa and Alexandra. Supplying this replaces the automatic
            # guess entirely.
            "cast": [],   # [{"name": "Alex", "aliases": ["Alexa", "Alexandra"], "role": "protagonist"}]
            # Comparable published books, found by searching. EVERY entry needs
            # a source URL: a list of five plausible-sounding titles is exactly
            # what a language model produces when it cannot find real ones, and
            # the renderer drops any entry without one.
            "similarities": {
                "plot": [],       # [{"title","author","year","why","source"}]
                "tropes_moods_tags": [],
                "characters": [],
                "ending": [],
            },
            "turning_points": [],       # [{"chapter": 4, "pct": 13.1, "what_changes": "", "quote": ""}]
            # Protagonist's fortune sampled across the book, -5 (worst) to +5 (best).
            # Six to ten readings is enough. Used for the Vonnegut shape.
            "fortune_readings": [],     # [{"chapter": 1, "pct": 0.0, "fortune": 0}]
        },
    }
    p = outdir / "worksheet.json"
    p.write_text(json.dumps(worksheet, indent=2), "utf-8")

    print(f"\n  {len(chapters)} chapters written to {outdir / 'chapters'}/")
    print(f"  worksheet: {p}\n")
    d = worksheet["detected"]
    print(f"  DETECTED (candidates, all need confirming against the text)")
    print(f"    dominant POV          {d['dominant_pov']}")
    print(f"    POV/tense odd in      {d['pov_inconsistent_chapters'] or 'no chapters'}")
    for s_ in d["pov_slip_scenes"][:6]:
        print(f"    POV SLIP              ch {s_['chapter']} para {s_['paragraph']}: "
              f"{s_['text'][:62]}")
    print(f"    head-hop candidates   {d['head_hop_chapters'] or 'none'}")
    fl = ", ".join(f"ch {x['chapter']} ({x['per_1k']}/1k)"
                   for x in d["most_pluperfect_chapters"][:3])
    print(f"    most flashback-heavy  {fl or 'no pluperfect clusters'}")
    for a in d["attribute_drift"]:
        print(f"    ATTRIBUTE DRIFT       {a['character']} {a['attribute']}: "
              f"{', '.join(a['values'])}")
    for t in d["loose_thread_candidates"][:5]:
        print(f"    dropped name          {t['name']} peaks ch {t['peak_chapter']}, "
              f"last seen ch {t['last_chapter']}, {t['chapters_remaining_after']} chapters left")
    for cat, hits in d["content_candidates"].items():
        print(f"    content               {cat}: ch "
              f"{', '.join(str(h['chapter']) for h in hits[:6])}")
    print(f"\n  Next: read {outdir / 'chapters'}/*.txt and fill in every field under")
    print("  'to_be_filled_by_reading', plus a one_line for each chapter.")
    print(f"  Then: python3 narrative.py --render {p}\n")


REQUIRED = ["synopsis", "inciting_incident", "protagonist", "timeline", "ending_type"]


def load_worksheet(ws_path):
    """Read a worksheet and refuse it unless the reading has actually been done."""
    ws = json.loads(Path(ws_path).read_text("utf-8"))
    f = ws["to_be_filled_by_reading"]
    errs = []
    for k in REQUIRED:
        v = f.get(k)
        if not v or (isinstance(v, dict) and not any(str(x).strip() for x in v.values())):
            errs.append(f"'{k}' has not been filled in")
    missing = [c["chapter"] for c in ws["chapters"] if not c.get("one_line", "").strip()]
    if missing:
        errs.append(f"chapters with no one-line summary: {missing}")
    ii = f.get("inciting_incident") or {}
    if ii.get("chapter") and not str(ii.get("quote", "")).strip():
        errs.append("inciting_incident needs a quote from the text")
    pr = f.get("protagonist") or {}
    if pr.get("stated_want") and not str(pr.get("quote", "")).strip():
        errs.append("protagonist.stated_want needs a quote from the text")
    if errs:
        print("worksheet incomplete:", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    return ws


# ---------------------------------------------------------------- report blocks
# Each returns a list of markdown lines, so analyse.py can place them among the
# measured sections rather than bolting them on at the end.


def headlines(ws):
    """One-line findings for the overview at the top of the report."""
    f = ws["to_be_filled_by_reading"]
    out = []
    ii = f.get("inciting_incident") or {}
    if ii.get("chapter"):
        late = " which is late" if (isinstance(ii.get("pct_into_book"), (int, float))
                                    and ii["pct_into_book"] > 15) else ""
        out.append(f"The first real disruption arrives in chapter {ii['chapter']}, "
                   f"{ii.get('pct_into_book')}% in{late}.")
    pr = f.get("protagonist") or {}
    if pr.get("name") and pr.get("first_stated_pct") is not None:
        out.append(f"What {pr['name']} wants is first stated {pr['first_stated_pct']}% in.")
    et = f.get("ending_type") or {}
    if et.get("type"):
        out.append(f"The ending is {et['type'].strip().lower()}.")
    ce = len(f.get("confirmed_continuity_errors") or [])
    lt = len(f.get("confirmed_loose_threads") or [])
    if ce or lt:
        parts = []
        if ce:
            parts.append(f"{ce} continuity error{'s' if ce != 1 else ''}")
        if lt:
            parts.append(f"{lt} loose thread{'s' if lt != 1 else ''}")
        out.append(" and ".join(parts).capitalize() + " to resolve.")
    return out


def synopsis_block(ws):
    return ["", "## Synopsis", "", ws["to_be_filled_by_reading"]["synopsis"].strip(), ""]


def chapter_map_block(ws):
    L = ["", "## Chapter map", "",
         "What happens, chapter by chapter. Percentages are where each chapter "
         "begins.", "",
         "| Ch | % in | Words | What happens |", "|---:|---:|---:|---|"]
    for c in ws["chapters"]:
        L.append(f"| {c['chapter']} | {c['starts_at_pct']}% | {c['words']:,} | "
                 f"{c['one_line'].strip()} |")
    return L + [""]


def shape_block(ws):
    f = ws["to_be_filled_by_reading"]
    L = ["", "## Shape of the story", ""]
    ii = f.get("inciting_incident") or {}
    pct = ii.get("pct_into_book")
    if ii.get("chapter"):
        note = ""
        if isinstance(pct, (int, float)) and pct > 15:
            note = (" A late first disruption is one of the more common reasons a "
                    "submission is put down early, though a slow open is a "
                    "legitimate choice in some categories.")
        L += [f"**Inciting incident.** Chapter {ii['chapter']}, {pct}% in. "
              f"{ii['what_happens'].strip()}{note}", "",
              f"> {ii['quote'].strip()}", ""]
    pr = f.get("protagonist") or {}
    if pr.get("name"):
        want = pr["stated_want"].strip()
        want = want[:1].upper() + want[1:]
        wnote = ""
        if isinstance(pr.get("first_stated_pct"), (int, float)) and pr["first_stated_pct"] > 25:
            wnote = (f" It is not stated until {pr['first_stated_pct']}% in, which is "
                     "worth noting: readers tend to need something to want on the "
                     "protagonist's behalf earlier than that.")
        L += [f"**What {pr['name']} wants.** {want} First stated in chapter "
              f"{pr.get('first_stated_chapter')}.{wnote}", "",
              f"> {pr['quote'].strip()}", ""]
    tl = f.get("timeline") or {}
    if tl.get("description"):
        L += [f"**Timeline.** {tl['description'].strip()}"
              + (f" Flashback share: {tl['flashback_share']}." if tl.get("flashback_share") else ""), ""]
    et = f.get("ending_type") or {}
    if et.get("type"):
        L += [f"**Ending.** {et['type'].strip()}. {et.get('note', '').strip()}", ""]
        if et.get("quote"):
            L += [f"> {et['quote'].strip()}", ""]
    return L


def pov_block(ws):
    d, f = ws["detected"], ws["to_be_filled_by_reading"]
    L = ["", "## Point of view", "", f"Dominant mode: {d['dominant_pov']}.", ""]
    if d["pov_inconsistent_chapters"]:
        L.append("Chapters told in another person or tense: "
                 f"{', '.join(map(str, d['pov_inconsistent_chapters']))}. "
                 "Often deliberate, so worth checking against the chapter map.")
    else:
        L.append("No chapter departs from it.")
    slips = d.get("pov_slip_scenes") or []
    if slips:
        L += ["", f"**{len(slips)} narration paragraph"
              f"{'s' if len(slips) != 1 else ''} written in another person.** "
              "Dialogue was excluded, so these are narration proper:", ""]
        for s in slips[:6]:
            L.append(f"- Chapter {s['chapter']}, paragraph {s['paragraph']}: "
                     f"{s['text'].strip()}")
    hh = f.get("head_hops_confirmed") or []
    if hh:
        L += ["", "**Head-hops confirmed on reading:**", ""] + [f"- {h}" for h in hh]
    elif d["head_hop_chapters"]:
        L += ["", "Scenes giving two characters interiority were flagged in chapters "
              f"{', '.join(map(str, d['head_hop_chapters']))}. None were confirmed "
              "as head-hops on reading."]
    return L + [""]


def continuity_lines(ws):
    """Merged into the copyediting section, because it is the same question:
    how many lines would an editor have to fix."""
    d, f = ws["detected"], ws["to_be_filled_by_reading"]
    out = list(f.get("confirmed_continuity_errors") or [])
    for a in d.get("attribute_drift") or []:
        if not any(a["character"] in str(e) for e in out):
            out.append(f"{a['character']}'s {a['attribute']} is described as "
                       + " and as ".join(f"{k} ({v} times)" for k, v in a["values"].items())
                       + ". Flagged automatically and not confirmed by reading.")
    return out


SIMILARITY_SECTIONS = [
    ("plot", "Similar plot",
     "Books that put a comparable situation in front of the reader."),
    ("tropes_moods_tags", "Similar tropes, mood and tags",
     "Books that sit on the same shelf by feel rather than by plot."),
    ("characters", "Similar characters",
     "Comparable in age, occupation or attitude, whatever the story around them."),
    ("ending", "Similar ending",
     "Books that close the same way, which is the hardest of these to match and "
     "the most useful when it lands."),
]


def similarities_block(ws):
    """Comparable published titles, each with a source.

    An entry without a source URL is dropped rather than printed. Asking for
    five comparable books reliably produces five plausible titles whether or not
    they exist, so the source is the only thing separating a comp list from a
    guess.
    """
    sims = (ws["to_be_filled_by_reading"].get("similarities") or {})
    if not any(sims.get(k) for k, _, _ in SIMILARITY_SECTIONS):
        return []

    L = ["", "## Possible similarities", "",
         "Comparable published books, for positioning and for the pitch. Every "
         "title below carries a source; anything that could not be sourced was "
         "left out rather than guessed at.", ""]
    dropped = 0
    for key, heading, blurb in SIMILARITY_SECTIONS:
        entries = [e for e in (sims.get(key) or [])
                   if str(e.get("source", "")).strip()
                   and str(e.get("title", "")).strip()]
        dropped += len(sims.get(key) or []) - len(entries)
        if not entries:
            continue
        L += [f"### {heading}", "", blurb, "",
              "| Book | Why it compares | Source |", "|---|---|---|"]
        for e in entries[:8]:
            who = e.get("author", "")
            year = f", {e['year']}" if e.get("year") else ""
            L.append(f"| *{e['title']}*, {who}{year} | {e.get('why','').strip()} "
                     f"| [link]({e['source']}) |")
        L.append("")
    if dropped:
        L += [f"{dropped} candidate title" + ("s were" if dropped != 1 else " was")
              + " dropped for having no source.", ""]
    L += ["These are comparisons rather than claims about quality, and none of "
          "them is evidence that this book would sell.", ""]
    return L


def loose_threads_block(ws):
    f = ws["to_be_filled_by_reading"]
    lt = f.get("confirmed_loose_threads") or []
    if not lt:
        return []
    return ["", "## Loose threads", "",
            "Elements set up with weight that never pay off.", ""] + \
           [f"- {x}" for x in lt] + [""]


def content_block(ws):
    cn = ws["to_be_filled_by_reading"].get("content_notes") or []
    if not cn:
        return []
    return ["", "## Content to know about before reading", "",
            "Neutral notes for editorial awareness, not judgements about the book.",
            ""] + [f"- {x}" for x in cn] + [""]


def render(ws_path):
    ws = load_worksheet(ws_path)
    L = synopsis_block(ws) + chapter_map_block(ws) + shape_block(ws) + pov_block(ws)
    cl = continuity_lines(ws)
    if cl:
        L += ["", "## Continuity", ""] + [f"- {x}" for x in cl] + [""]
    L += loose_threads_block(ws) + content_block(ws)
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?")
    ap.add_argument("--out", default="narrative_work")
    ap.add_argument("--render", default=None)
    args = ap.parse_args()
    if args.render:
        render(args.render)
    elif args.target:
        analyse(Path(args.target), args.out)
    else:
        ap.error("give a manuscript, or --render a worksheet")


if __name__ == "__main__":
    main()
