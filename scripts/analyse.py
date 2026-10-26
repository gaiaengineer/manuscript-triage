#!/usr/bin/env python3
"""Manuscript triage report: the basics, craft-floor metrics, and whole-book structure.

    python3 analyse.py <workdir-or-textfile> [--genre thriller] [--json out.json]

Craft metrics are headlined on a fixed 5,000-word read — 2,000 words from the
opening, 1,000 from the middle, 2,000 from the end — so every manuscript is
measured on the same amount of text and the figures are comparable across
submissions. The whole book is measured too, as a check column: when the opening
is much cleaner than the book, the author polished chapter one and stopped.

Nothing here is a decision. Where a genre is supplied, the report offers an
explicitly labelled ATTEMPT at interpretation, using rule-of-thumb ranges that
are documented (and caveated) in references/genre-expectations.md.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from craft_floor import (  # noqa: E402
    HEADING_RE, NAME_STOPLIST, SENT_SPLIT_RE, WORD_RE, measure,
)
from extract_book import (  # noqa: E402
    EXTRACTORS, check_readable, find_book, normalise, read_metadata,
)
import structure as st  # noqa: E402

SAMPLE_PLAN = [("opening", 0.0, 2000), ("middle", 0.5, 1000), ("ending", 1.0, 2000)]

# Rule-of-thumb ranges from publishing practice. NOT measured from a corpus —
# see references/genre-expectations.md before relying on any of them.
GENRE_EXPECTATIONS = {
    "literary":       {"words": (70000, 110000),  "dialogue": (10, 28), "sentence": (14, 26)},
    "upmarket":       {"words": (80000, 110000),  "dialogue": (20, 35), "sentence": (12, 22)},
    "thriller":       {"words": (80000, 100000),  "dialogue": (30, 50), "sentence": (9, 16)},
    "crime":          {"words": (80000, 100000),  "dialogue": (30, 50), "sentence": (9, 17)},
    "cosy mystery":   {"words": (65000, 85000),   "dialogue": (35, 55), "sentence": (9, 16)},
    "romance":        {"words": (50000, 90000),   "dialogue": (35, 55), "sentence": (9, 16)},
    "romantasy":      {"words": (90000, 150000),  "dialogue": (30, 45), "sentence": (10, 18)},
    "fantasy":        {"words": (90000, 150000),  "dialogue": (25, 40), "sentence": (12, 20)},
    "science fiction": {"words": (85000, 130000), "dialogue": (25, 40), "sentence": (12, 20)},
    "horror":         {"words": (70000, 100000),  "dialogue": (20, 38), "sentence": (10, 18)},
    "historical":     {"words": (90000, 130000),  "dialogue": (20, 35), "sentence": (13, 24)},
    "young adult":    {"words": (55000, 85000),   "dialogue": (30, 50), "sentence": (9, 16)},
    "middle grade":   {"words": (30000, 55000),   "dialogue": (30, 50), "sentence": (8, 14)},
    "memoir":         {"words": (70000, 100000),  "dialogue": (8, 22),  "sentence": (14, 26)},
}

GENRE_LEXICON = {
    "crime/thriller": ["detective", "murder", "suspect", "evidence", "witness",
                       "precinct", "homicide", "alibi", "interrogat", "forensic"],
    "romance": ["kissed", "blush", "heartbeat", "chest tightened", "lips",
                "desire", "ached", "wedding", "date", "flirt"],
    "fantasy/SFF": ["magic", "spell", "sword", "kingdom", "dragon", "realm",
                    "prophecy", "sorcer", "starship", "alien", "android", "portal"],
    "historical": ["carriage", "regiment", "estate", "servant", "parlour",
                   "duke", "countess", "shilling", "the war", "telegram"],
    "horror": ["blood", "corpse", "scream", "shadow moved", "rotting",
               "flesh", "whisper", "grave", "cellar", "something was wrong"],
}


# Two tiers, because some of these phrases are also ordinary English.
#
# STRONG markers are safe anywhere in a short paragraph: nobody writes "ISBN" or
# "all rights reserved" in a novel by accident.
FRONT_MARKERS = re.compile(
    r"all rights reserved|no part of this (?:book|publication)|\bisbn\b|©|"
    r"\(c\)\s*\d{4}|library of congress|catalogu?ing|a cip record|"
    r"project gutenberg|gutenberg\.org|literary archive foundation|"
    r"this ebook is for the use of|work of fiction", re.I)

# WEAK markers are phrases that occur in real prose. "The tension produced by
# Mr. Armitage's telegram" is a sentence in a novel, not a colophon. These only
# count at the very start of a short standalone paragraph.
FRONT_MARKERS_WEAK = re.compile(
    r"^(?:produced by|published by|printed (?:and bound )?in |first published|"
    r"typeset (?:in|by)|cover design|transcriber's note|e-?text prepared by|"
    r"terms of use)", re.I)

BACK_MARKERS = re.compile(
    r"^(?:about the author|acknowledge?ments|also by |by the same author|"
    r"reading group guide|book club (?:questions|guide)|discussion questions|"
    r"a note (?:on|about) the (?:type|author|text)|colophon|other books by|"
    r"an excerpt from|keep reading|newsletter|if you enjoyed|"
    r"section \d+\.|general terms of use|end of (?:the|this) project gutenberg|"
    r"transcriber's note|appendix|glossary|author's note)", re.I)


# Project Gutenberg wraps every book in licence text, several thousand words of
# it at each end, and marks the boundaries explicitly. Those markers are exact,
# so this is handled before the heuristics rather than by them.
PG_START_RE = re.compile(
    r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)
PG_END_RE = re.compile(
    r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)


# Headings that mark material before the book proper. "Prologue" is deliberately
# absent: a prologue is part of the novel.
FRONT_HEADING_RE = re.compile(
    r"^(?:preface|foreword|introduction|list of illustrations|illustrations|"
    r"contents|table of contents|dedication|epigraph|title page|"
    r"a note on the text)\.?$", re.I)

ROMAN_OR_NUM_RE = re.compile(r"^(?:chapter\s+)?(?:[IVXLCDM]+|\d{1,3})$", re.I)


def looks_like_contents(paragraph):
    """A contents list rendered as one block of short lines.

    Some EPUBs mark each entry as its own paragraph and some put the whole list
    in a single block separated by line breaks. The second kind slipped through
    a check that only looked for consecutive short paragraphs.
    """
    lines = [l.strip().rstrip(".,;") for l in paragraph.split("\n") if l.strip()]
    if len(lines) < 8:
        return False
    hits = sum(1 for l in lines
               if len(l.split()) <= 6 and
               (ROMAN_OR_NUM_RE.match(l) or HEADING_RE.match(l)))
    return hits / len(lines) > 0.6


def trim_gutenberg(paragraphs):
    """Return (start, end) bounding the actual book, or None if not a PG file."""
    start = end = None
    for i, p in enumerate(paragraphs):
        if start is None and PG_START_RE.search(p):
            start = i + 1
        elif PG_END_RE.search(p):
            end = i
            break
    if start is None and end is None:
        return None
    return (start or 0), (end if end is not None else len(paragraphs))


def trim_matter(paragraphs):
    """Locate the narrative and drop publisher front/back matter.

    A published EPUB opens with a title page, copyright notice, dedication and
    contents list, and closes with 'About the author'. Sampling those wastes the
    read, inflates the chapter count, and — because copyright boilerplate has no
    dialogue and no clichés — makes the opening look artificially clean, which
    would falsely trigger the front-loaded-polish warning.

    Conservative by design: with no positive evidence of matter, nothing is cut.
    """
    n = len(paragraphs)
    notes, start, end = [], 0, n

    pg = trim_gutenberg(paragraphs)
    if pg:
        start, end = pg
        notes.append("Project Gutenberg licence text")
        paragraphs = paragraphs[start:end]
        inner_lo, inner_hi, inner_notes = trim_matter(paragraphs)
        return start + inner_lo, start + inner_hi, notes + inner_notes

    scan = max(30, int(n * 0.15))

    last = -1
    for i, p in enumerate(paragraphs[:scan]):
        words = len(p.split())
        if (FRONT_MARKERS.search(p) and words < 120) or \
                (FRONT_MARKERS_WEAK.match(p.strip()) and words < 25):
            last = i
    # a contents list rendered as a single block of lines
    for i, p in enumerate(paragraphs[:scan]):
        if looks_like_contents(p):
            last = max(last, i)
            notes.append("contents list")
    # front-matter headings such as PREFACE or LIST OF ILLUSTRATIONS
    for i, p in enumerate(paragraphs[:scan]):
        if len(p.split()) <= 5 and FRONT_HEADING_RE.match(p.strip()):
            last = max(last, i)

    # a contents list: a run of short heading-like lines
    run = run_start = 0
    for i, p in enumerate(paragraphs[:scan]):
        if len(p.split()) <= 6 and HEADING_RE.match(p.strip()):
            if run == 0:
                run_start = i
            run += 1
            if run >= 5:
                last = max(last, i)
        else:
            if run >= 5:
                notes.append(f"contents list ({run} entries)")
            run = 0
    if last >= 0:
        start = last + 1
        notes.insert(0, "publisher front matter")

    # The most reliable rule of all: the narrative starts at the first chapter
    # heading, so anything before it is front matter whatever form it takes.
    # This catches lists of illustrations, prefaces, epigraphs and half-titles
    # without needing a pattern for each. "Prologue" counts as a heading, so a
    # book that opens with one is not cut into.
    for i, p in enumerate(paragraphs[:scan]):
        t = p.strip()
        if len(t) <= 70 and HEADING_RE.match(t) and not looks_like_contents(p):
            if i > start:
                start = i
                notes.append("everything before the first chapter heading")
            break

    for i in range(max(start, int(n * 0.8)), n):
        if BACK_MARKERS.match(paragraphs[i].strip()):
            end = i
            notes.append(f"back matter ({paragraphs[i].strip()[:40]})")
            break

    if start >= end:                       # never trim everything away
        return 0, n, []
    return start, end, notes


def load(target):
    """Accept the manuscript file itself, a folder of uploads, or a workdir.

    Extraction happens here so the whole thing is one command — the reader
    should never have to run a pipeline.
    """
    p = Path(target).expanduser()
    if p.is_dir():
        if (p / "full.txt").exists():                       # extract_book workdir
            mf = p / "manifest.json"
            return ((p / "full.txt").read_text("utf-8", errors="replace"),
                    json.loads(mf.read_text("utf-8")) if mf.exists() else {},
                    p.name)
        p = find_book(p)                                    # folder of uploads
    if not p.exists():
        sys.exit(f"not found: {p}")

    check_readable(p)
    ext = p.suffix.lower()
    text = normalise(EXTRACTORS[ext](p))
    meta = read_metadata(p)
    if not meta.get("title"):
        for para in [x.strip() for x in text.split("\n\n") if x.strip()][:5]:
            if 2 <= len(para.split()) <= 15 and not para.endswith((".", ",", "!", "?")):
                meta["title"] = para.strip("# ")
                meta["source"] = "first line of the file (a guess)"
                break
    return text, {"metadata": meta, "source_file": p.name}, p.stem


def take(paragraphs, offsets, total, start_frac, want):
    """`want` words starting at start_frac through the book, on paragraph bounds."""
    if start_frac >= 1.0:                       # anchor the tail to the end
        target = max(0, total - want)
    else:
        target = start_frac * total
    start_i = min(range(len(offsets)), key=lambda i: abs(offsets[i] - target))
    chosen, used = [], 0
    for i in range(start_i, len(paragraphs)):
        w = len(paragraphs[i].split())
        if used + w > want and chosen:
            break
        chosen.append(i)
        used += w
    return chosen, used


def cap_words(block, want):
    """Trim a block to `want` words, ending on a sentence boundary.

    A single paragraph can be longer than the whole window: Austen's letters run
    to thousands of words unbroken. Without this the window silently doubles and
    the fixed sample size, which is the whole point of sampling, stops holding.
    """
    words = block.split()
    if len(words) <= want * 1.15:
        return block
    cut = " ".join(words[:want])
    m = list(re.finditer(r"[.!?][\"\u201d\u2019']?\s", cut))
    return cut[:m[-1].end()].strip() if m else cut


def build_sample(text):
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    offsets, run = [], 0
    for p in paragraphs:
        offsets.append(run)
        run += len(p.split())
    total = run
    if total <= 5000:
        return text, {"windows": [], "words": total, "note":
                      "shorter than 5,000 words — whole text used"}, text

    parts, windows, seen, opening = [], [], set(), ""
    for name, frac, want in SAMPLE_PLAN:
        idx, used = take(paragraphs, offsets, total, frac, want)
        idx = [i for i in idx if i not in seen]
        seen.update(idx)
        if not idx:
            continue
        block = cap_words("\n\n".join(paragraphs[i] for i in idx), want)
        if name == "opening":
            opening = block
        parts.append(block)
        windows.append({"window": name, "words": len(block.split()),
                        "from_pct": round(offsets[idx[0]] / total * 100, 1)})
    return ("\n\n".join(parts),
            {"windows": windows, "words": sum(w["words"] for w in windows)},
            opening)


ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman(x):
    total = 0
    for i, ch in enumerate(x):
        v = ROMAN_VALUES[ch]
        nxt = ROMAN_VALUES[x[i + 1]] if i + 1 < len(x) else 0
        total += -v if v < nxt else v
    return total


def chapter_number(title):
    """Pull a chapter number out of a heading, arabic or roman."""
    t = re.sub(r"(?i)^\s*(?:chapter|chap\.?|part|book)\s*", "", title or "").strip()
    t = t.rstrip(".,: ").strip()
    if t.isdigit():
        return int(t)
    if t and all(c in ROMAN_VALUES for c in t.upper()):
        try:
            return _roman(t.upper())
        except (KeyError, IndexError):
            return None
    return None


def numbering_gaps(chapters):
    """Missing numbers in an otherwise sequential run of chapter headings.

    A real file can be missing a heading the book itself has. Reporting the gap
    is more useful than reporting a chapter count that is quietly wrong.
    """
    nums = [chapter_number(t) for t, _ in chapters]
    good = [n for n in nums if n is not None]
    if len(good) < max(4, len(nums) * 0.8):
        return []
    return [n for n in range(min(good), max(good) + 1) if n not in good]


SCENE_BREAK_RE = re.compile(r"^\s*(?:[*#~\u2014\u2013-]\s*){3,}\s*$")


def split_chapters(text):
    """Chapter headings if the book has them, scene breaks if it does not.

    Plenty of manuscripts have no chapter headings at all and divide themselves
    with a row of asterisks. Treating such a book as one undivided block loses
    the texture curve and the character presence sparklines entirely, which are
    the measures that most need the divisions.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chapters, current, title = [], [], None
    for p in paragraphs:
        if len(p) <= 70 and HEADING_RE.match(p.strip()):
            if current:
                chapters.append((title, "\n\n".join(current)))
            title, current = p.strip().lstrip("# "), []
        else:
            current.append(p)
    if current:
        chapters.append((title, "\n\n".join(current)))

    if len(chapters) < 2:
        breaks = [i for i, p in enumerate(paragraphs) if SCENE_BREAK_RE.match(p)]
        if len(breaks) >= 4:
            sections, start = [], 0
            for b in breaks + [len(paragraphs)]:
                body = [p for p in paragraphs[start:b] if not SCENE_BREAK_RE.match(p)]
                if body:
                    sections.append((f"Section {len(sections) + 1}",
                                     "\n\n".join(body)))
                start = b
            if len(sections) >= 2:
                return sections
    return chapters


def names_in(block):
    cased = Counter(WORD_RE.findall(block))
    folded = Counter(w.lower() for w in WORD_RE.findall(block))
    return {w for w, c in cased.items()
            if len(w) > 3 and w[0].isupper() and w.lower() not in NAME_STOPLIST
            and c / folded[w.lower()] > 0.9 and c >= 2}


def book_type(text, n_words, chapters):
    """Signals only. The reading agent makes the call."""
    lines = [l for l in text.split("\n") if l.strip()]
    short_unpunctuated = sum(
        1 for l in lines if len(l) < 60 and not re.search(r"[.!?:;,]$", l.strip()))
    verse_ratio = short_unpunctuated / len(lines) if lines else 0.0

    overlap = None
    if len(chapters) >= 3:
        sets = [names_in(b) for _, b in chapters if len(b.split()) > 200]
        pairs = [(a, b) for a, b in zip(sets, sets[1:]) if a and b]
        if pairs:
            overlap = round(sum(len(a & b) / len(a | b) for a, b in pairs) / len(pairs), 3)

    if n_words < 7500:
        band = "short story"
    elif n_words < 17500:
        band = "novelette"
    elif n_words < 40000:
        band = "novella"
    else:
        band = "novel-length"

    signals = []
    if verse_ratio > 0.4:
        signals.append(f"{verse_ratio:.0%} of lines are short and unpunctuated, which suggests verse")
    if overlap is not None:
        if overlap < 0.1:
            signals.append(f"characters barely recur between chapters (overlap {overlap}) "
                           "which is consistent with a story collection")
        else:
            signals.append(f"characters recur across chapters (overlap {overlap}) "
                           "which is consistent with a single continuous narrative")
    return {"length_band": band, "verse_line_ratio": round(verse_ratio, 3),
            "chapter_name_overlap": overlap, "signals": signals}


def genre_signals(text, dialogue_pct):
    low = text.lower()
    words = WORD_RE.findall(low)
    n = len(words) or 1
    first = sum(1 for w in words if w in ("i", "me", "my", "mine"))
    third = sum(1 for w in words if w in ("he", "she", "him", "her", "his", "they"))
    past = len(re.findall(r"\b(was|were|had|said|looked|went|came|took)\b", low))
    present = len(re.findall(r"\b(is|are|has|says|looks|goes|comes|takes)\b", low))
    hits = {g: sum(low.count(k) for k in ks) for g, ks in GENRE_LEXICON.items()}
    return {
        "person": "first person" if first > third else "third person",
        "first_person_pronouns_per_1k": round(first / n * 1000, 1),
        "tense": "past" if past >= present else "present",
        "dialogue_pct": dialogue_pct,
        "lexicon_hits": dict(sorted(hits.items(), key=lambda kv: -kv[1])),
    }


def attempt_interpretation(genre, n_words, dialogue_pct, sentence_mean):
    """Explicitly provisional. Every line is prefixed ATTEMPT."""
    g = (genre or "").strip().lower()
    if g not in GENRE_EXPECTATIONS:
        return ["ATTEMPT. No genre supplied, so nothing here is interpreted. "
                "Re-run with --genre once the genre is established, or read the "
                "raw figures above and judge them directly."]
    e = GENRE_EXPECTATIONS[g]
    out = []

    lo, hi = e["words"]
    if n_words < lo:
        out.append(f"ATTEMPT. At {n_words:,} words this is short for {g} "
                   f"(usually {lo:,}–{hi:,}). May read as underdeveloped, or may "
                   "simply be a tighter book than the convention.")
    elif n_words > hi:
        out.append(f"ATTEMPT. At {n_words:,} words this is long for {g} "
                   f"(usually {lo:,}–{hi:,}). Relevant to print cost as much as to craft.")
    else:
        out.append(f"ATTEMPT. Length ({n_words:,} words) sits inside the usual "
                   f"{g} range of {lo:,}–{hi:,}.")

    lo, hi = e["dialogue"]
    if dialogue_pct > hi:
        out.append(f"ATTEMPT. Dialogue at {dialogue_pct}% is above the usual {g} "
                   f"band ({lo}–{hi}%). Heavy dialogue is not a fault in itself; "
                   "it is worth checking whether scenes carry description too.")
    elif dialogue_pct < lo:
        out.append(f"ATTEMPT. Dialogue at {dialogue_pct}% is below the usual {g} "
                   f"band ({lo}–{hi}%). Often a sign of narration-heavy, "
                   "summarised scenes, though plenty of good books read this way.")
    else:
        out.append(f"ATTEMPT. Dialogue at {dialogue_pct}% is normal for {g} "
                   f"({lo}–{hi}%).")

    lo, hi = e["sentence"]
    if sentence_mean > hi:
        out.append(f"ATTEMPT. Mean sentence length {sentence_mean} words runs long "
                   f"for {g} (usually {lo}–{hi}).")
    elif sentence_mean < lo:
        out.append(f"ATTEMPT. Mean sentence length {sentence_mean} words runs short "
                   f"for {g} (usually {lo}–{hi}); can read as clipped, or as pacy.")
    return out


def find_sag(tex, key="dialogue_pct"):
    """The longest run of chapters below the book's own average.

    Deliberately self-referential: no external norm is needed to say that a
    stretch of a book is quieter than the rest of that same book.
    """
    if len(tex) < 6:
        return None
    vals = [r[key] for r in tex]
    mean = sum(vals) / len(vals)
    best, cur = [], []
    for i, v in enumerate(vals):
        if v < mean:
            cur.append(i)
        else:
            best, cur = (cur if len(cur) > len(best) else best), []
    best = cur if len(cur) > len(best) else best
    return best if len(best) >= max(3, len(tex) // 5) else None


def brief(*lines):
    """A short interpretive note above a table. Always hedged, never a verdict."""
    body = " ".join(x for x in lines if x)
    return ["", f"> **At a glance.** {body}", ""] if body else []


def craft_brief(whole, drift):
    p = whole["percentages"]
    bits = [f"Of the speech that carries a tag, "
            f"{p['exotic_dialogue_tags']['pct']}% uses a verb other than *said* "
            f"or *asked*."]
    if p["impossible_dialogue_tags"]["count"]:
        bits.append(f"{p['impossible_dialogue_tags']['count']} of those are verbs "
                    "that cannot carry speech at all (*she smiled*, *he chuckled*). "
                    "That is a straightforward copyediting fix, though a telling one.")
    if p["cliche_paragraphs"]["pct"] >= 10:
        bits.append(f"{p['cliche_paragraphs']['pct']}% of paragraphs contain a "
                    "phrase from the stock-phrase list.")
    if drift:
        bits.append("Note that the opening scores much better than the rest. See "
                    "the section below.")
    bits.append("There are no calibrated thresholds behind any of these figures, "
                "so read them as high or low for this manuscript. They are not a pass "
                "or fail against any standard.")
    return brief(*bits)


def rhythm_brief(whole, chdist, walls):
    sl, pl = whole["shape"]["sentence_length"], whole["shape"]["paragraph_length"]
    bits = [f"Sentences average {sl['mean']} words and paragraphs {pl['mean']}. "
            f"The variation figures ({sl['cv']} and {pl['cv']}) are the ones to "
            "look at: the lower they are, the more every sentence is the same "
            "length as the last."]
    if walls and walls["count"] == 0:
        bits.append("No walls of text: nothing runs over "
                    f"{walls['threshold']} words.")
    elif walls:
        bits.append(f"{walls['count']} paragraphs run past {walls['threshold']} "
                    f"words (longest {walls['longest']}), which is friction on the page.")
    if chdist:
        bits.append(f"Chapters are fairly even in length (variation {chdist['cv']}, "
                    f"from {chdist['shortest']:,} to {chdist['longest']:,} words)."
                    if chdist["cv"] < 0.35 else
                    f"Chapter lengths vary a lot (variation {chdist['cv']}, from "
                    f"{chdist['shortest']:,} to {chdist['longest']:,} words), which "
                    "may be deliberate pacing or may be unevenness.")
    return brief(*bits)


def texture_brief(tex):
    if not tex:
        return []
    sag = find_sag(tex)
    if not sag:
        return brief("Dialogue, questions and action stay reasonably steady across "
                     "the book. No single stretch stands out as quieter than the rest.")
    a, b = tex[sag[0]]["n"], tex[sag[-1]]["n"]
    in_f = sum(tex[i]["filter_per_1k"] for i in sag) / len(sag)
    out = [r for i, r in enumerate(tex) if i not in sag]
    out_f = sum(r["filter_per_1k"] for r in out) / len(out) if out else 0
    bits = [f"**Chapters {a}–{b} run below this book's own average for dialogue.** "
            f"That is the longest such stretch in the manuscript."]
    if in_f > out_f * 1.15:
        bits.append(f"Filter words also rise across that stretch "
                    f"({in_f:.1f} per 1,000 words against {out_f:.1f} elsewhere), "
                    "which together tends to mean summarised narration rather than "
                    "scenes on the page.")
    bits.append(f"Worth spot-reading a chapter from that range before deciding "
                "anything. It may be deliberate quiet; it may be a sag.")
    return brief(*bits)


def presence_brief(pres):
    if not pres:
        return []
    bits = []
    gone = [c for c in pres if c["absent_runs"]]
    late = [c for c in pres if c["first_chapter"] and c["first_chapter"] > 1]
    if gone:
        c = max(gone, key=lambda x: x["total"])
        bits.append(f"Of the characters who disappear, the most prominent is "
                    f"**{c['name']}**, absent from "
                    f"{' and '.join(r.replace('ch ', 'chapters ') for r in c['absent_runs'])}.")
    if late:
        bits.append("Names arriving after the opening: "
                    + ", ".join(f"{c['name']} (ch {c['first_chapter']})" for c in late[:4])
                    + ".")
    if not bits:
        bits.append("The main names are present throughout, with no long absences.")
    bits.append("A long gap may well be deliberate structure. Either way it is "
                "worth knowing about before the read starts.")
    return brief(*bits)


def voice_brief(v):
    cov = v["coverage"]
    bits = [f"Speech could be matched to a named speaker for "
            f"{cov['pct_attributed']}% of dialogue lines."]
    if v.get("mean_similarity") is not None and v["pairs"]:
        top = v["pairs"][0]
        bits.append(f"Average vocabulary overlap between speakers is "
                    f"{v['mean_similarity']}; the closest pair is **{top['a']} and "
                    f"{top['b']}** at {top['similarity']}.")
        bits.append("A high figure for one pair specifically is the useful signal. "
                    "It suggests those two characters would be hard to tell apart "
                    "once the tags are removed.")
    if cov["pct_attributed"] < 30:
        bits.append("Attribution coverage is low here, so treat this as indicative "
                    "rather than settled.")
    return brief(*bits)


def copyedit_brief(h, ws=None):
    total = (h["likely_typos"]["count"] + h["repeated_word_count"]
             + h["unbalanced_quotes"]["paragraphs"] + h["double_spaces"]
             + len(h["possible_name_variants"]))
    reading_extra = len(__import__("narrative").continuity_lines(ws)) if ws else 0
    if total == 0 and not reading_extra:
        return brief("Mechanically clean, with nothing flagged. This manuscript has "
                     "been through a copyedit, or the author is unusually careful.")
    bits = [f"{total} mechanical issue{'s' if total != 1 else ''} flagged in total."]
    if h["possible_name_variants"]:
        v = h["possible_name_variants"][0]
        bits.append(f"The one to check first is the name spelled two ways "
                    f"(**{v['a']}** / **{v['b']}**). That is usually a genuine "
                    "continuity error rather than a typo.")
    if ws is not None:
        import narrative as nv
        extra = len(nv.continuity_lines(ws))
        if extra:
            bits.append(f"Reading the manuscript found {extra} further continuity "
                        f"error{'s' if extra != 1 else ''}, listed below.")
    bits.append("These are the closest thing here to a direct estimate of how many "
                "editorial hours the manuscript would need.")
    return brief(*bits)


READABLE_NAMES = {
    "filter_word_sentences": "Filter words (“she saw”, “he felt”)",
    "ly_adverbs": "Adverbs ending -ly",
    "exotic_dialogue_tags": "Dialogue tags other than said/asked",
    "impossible_dialogue_tags": "Impossible speech verbs (“she smiled”)",
    "adverbial_dialogue_tags": "Dialogue tags with an adverb",
    "cliche_paragraphs": "Paragraphs containing a stock phrase",
    "formula_vocab_paragraphs": "Paragraphs with formula vocabulary",
    "participial_paragraph_endings": "Paragraphs ending “, ...-ing”",
    "dialogue": "Dialogue",
}


def build_report(meta, manifest, n_words, chapters, bt, gs, plan,
                 sample, whole, drift, genre, struct=None, reader_brief=None, ws=None, tags=None):
    """The document the submissions reader actually keeps."""
    from datetime import date

    title = meta.get("title") or "Untitled manuscript"
    L = [
        f"# Manuscript triage: {title}",
        "",
        f"*Prepared {date.today().isoformat()} from "
        f"`{manifest.get('source_file', 'the submitted file')}`.*",
        "",
        "> This report counts things. It does not judge the book. Nothing in it "
        "is a recommendation to acquire or reject.",
        "",
        "## In brief",
        "",
    ]

    if reader_brief:
        L += [reader_brief.strip(), ""]
    if ws is not None:
        syn = (ws["to_be_filled_by_reading"].get("synopsis") or "").strip()
        if syn:
            L += [syn, ""]
    if not reader_brief:
        L += ["**[Reading notes not supplied.]** Whoever ran this should read the "
              "sampled chapters and add two or three sentences here saying how the "
              "book reads and who it is for.", ""]

    L += ["What the measurements say, in short:", ""]
    headline = []
    band = bt["length_band"]
    headline.append(f"{n_words:,} words across {len(chapters)} chapters. Length band: {band}.")
    if genre and genre.strip().lower() in GENRE_EXPECTATIONS:
        lo, hi = GENRE_EXPECTATIONS[genre.strip().lower()]["words"]
        if n_words < lo:
            headline.append(f"Short for {genre} (usually {lo:,}–{hi:,} words).")
        elif n_words > hi:
            headline.append(f"Long for {genre} (usually {lo:,}–{hi:,} words). "
                            "That is a print-cost question as much as an editorial one.")
    sg = find_sag((struct or {}).get("texture") or [])
    if sg:
        tx = struct["texture"]
        headline.append(f"A quiet stretch runs from chapter {tx[sg[0]]['n']} to "
                        f"{tx[sg[-1]]['n']}. Read one of those before deciding.")
    if drift:
        headline.append("The opening is markedly cleaner than the rest of the "
                        "manuscript, which usually means only chapter one was revised.")
    hy = whole["hygiene"]
    mech = (hy["likely_typos"]["count"] + hy["repeated_word_count"]
            + hy["unbalanced_quotes"]["paragraphs"] + len(hy["possible_name_variants"]))
    if mech == 0:
        headline.append("Mechanically clean.")
    else:
        nv = len(hy["possible_name_variants"])
        msg = f"{mech} mechanical issue{'s' if mech != 1 else ''} to fix"
        if nv:
            msg += (f", including {nv} name{'s' if nv != 1 else ''} "
                    "spelled inconsistently")
        headline.append(msg + ".")
    if ws is not None:
        import narrative as nv
        import structure_fit as sf
        headline += nv.headlines(ws)
        headline += sf.headlines(ws, genre)
    L += [f"- {x}" for x in headline]
    L += [
        "",
        "## The basics",
        "",
        "| | |",
        "|---|---|",
        f"| Title | {title} |",
        f"| Author | {meta.get('author') or '— not stated in the file —'} |",
        f"| Length | {n_words:,} words (about {round(n_words/275):,} printed pages) |",
        f"| Chapters | {len(chapters)}"
        + (f" (no heading found for chapter{'s' if len(numbering_gaps(chapters)) > 1 else ''} "
           f"{', '.join(map(str, numbering_gaps(chapters)[:8]))}, so this counts "
           "headings rather than chapters)" if numbering_gaps(chapters) else "")
        + " |",
        f"| Length band | {bt['length_band']} |",
        f"| Genre | {(genre or 'not determined').strip()} |",
        f"| Narration | {gs['person']}, {gs['tense']} tense |",
        f"| Dialogue | {gs['dialogue_pct']}% of words |",
        "",
    ]
    if bt["signals"]:
        L += ["Structural signals:", ""] + [f"- {s}" for s in bt["signals"]] + [""]

    if ws is not None:
        import narrative as nv
        L += nv.chapter_map_block(ws) + nv.shape_block(ws)

    t = tags or {}
    supplied = {k: [x.strip() for x in (t.get(k) or "").split(",") if x.strip()]
                for k in ("tropes", "moods", "tags")}
    if any(supplied.values()):
        L += ["", "## Tropes, moods and tags", "",
              "For shelving, comparison titles and catalogue copy. Confirmed by "
              "reading rather than guessed from keywords.", ""]
        if supplied["tropes"]:
            L += ["**Tropes.** " + ", ".join(supplied["tropes"]) + ".", ""]
        if supplied["moods"]:
            L += ["**Mood.** " + ", ".join(supplied["moods"]) + ".", ""]
        if supplied["tags"]:
            L += ["**Tags.** " + ", ".join(supplied["tags"]) + ".", ""]
        cands = [c["trope"] for c in (t.get("candidates") or [])
                 if c["trope"] not in supplied["tropes"]]
        if cands:
            L += ["Keyword scanning also raised " + ", ".join(cands[:6]) +
                  ". These were not confirmed by the reading and are listed only "
                  "so the reader can disagree.", ""]

    if ws is not None:
        import narrative as nv
        L += nv.similarities_block(ws)

    L += ["## The craft metrics", ""] + craft_brief(whole, drift)
    if plan.get("windows"):
        seg = ", ".join(f"{w['window']} {w['words']:,} words (from {w['from_pct']}% in)"
                        for w in plan["windows"])
        L += [f"Measured on a {plan['words']:,}-word read ({seg}), with the "
              f"whole {n_words:,}-word manuscript alongside as a check.", ""]
    else:
        L += [plan.get("note", ""), ""]

    L += ["| Marker | In the 5,000-word read | Whole manuscript | Measured against |",
          "|---|---:|---:|---|"]
    for key, v in sample["percentages"].items():
        w = whole["percentages"][key]
        L.append(f"| {READABLE_NAMES.get(key, key)} | {v['pct']}% | {w['pct']}% "
                 f"| {v['pct_of']} |")

    s_ = struct or {}
    sl, pl = whole["shape"]["sentence_length"], whole["shape"]["paragraph_length"]
    L += ["", "## Rhythm", ""] + rhythm_brief(whole, s_.get("chdist"), s_.get("walls")) + ["",
          "Variation matters more than the average. A low variation figure means "
          "nearly every sentence (or paragraph) is the same length, which reads "
          "flat however good the words are.", "",
          "| | Average | Variation |", "|---|---:|---:|",
          f"| Sentences | {sl['mean']} words | {sl['cv']} |",
          f"| Paragraphs | {pl['mean']} words | {pl['cv']} |"]
    if s_.get("walls"):
        w = s_["walls"]
        L.append(f"| Paragraphs over {w['threshold']} words | {w['count']} "
                 f"({w['pct_of_paragraphs']}%) | longest {w['longest']} |")
    if s_.get("chdist"):
        c = s_["chdist"]
        L.append(f"| Chapters | {c['mean']:,} words | {c['cv']} "
                 f"(shortest {c['shortest']:,}, longest {c['longest']:,}) |")

    if ws is not None:
        import narrative as nv
        L += nv.pov_block(ws)

    if s_.get("cast"):
        c = s_["cast"]
        L += ["", "## Cast onboarding", "",
              f"**{c['count']} named characters** appear in the first "
              f"{c['window_words']:,} words. A crowded opening is a common reason "
              "readers give up early.", ""]
        if c["names"]:
            L.append(", ".join(f"{x['name']} (word {x['first_at_word']})"
                               for x in c["names"][:15]))

    if s_.get("texture"):
        L += ["", "## Texture curve", ""] + texture_brief(s_.get("texture")) + ["",
              "Chapter by chapter. This is where a sag in the middle becomes "
              "visible without reading the whole book. Look for a long stretch "
              "where dialogue, questions and action all drop together.", "",
              "| Ch | Words | Dialogue | Sentence | Paragraph | ?+! per 1k "
              "| Action per 1k | Filter words per 1k |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in s_["texture"]:
            L.append(f"| {r['n']} | {r['words']:,} | {r['dialogue_pct']}% | "
                     f"{r['mean_sentence']} | {r['mean_paragraph']} | "
                     f"{r['qmark_excl_per_1k']} | {r['action_per_1k']} | "
                     f"{r['filter_per_1k']} |")
        L += ["", "*Action rate is a crude proxy: a count of common physical "
              "verbs rather than a grammatical analysis.*"]

    if s_.get("presence"):
        L += ["", "## Character presence", ""] + presence_brief(s_.get("presence")) + ["",
              "Mentions per chapter, first chapter to last. Places and "
              "organisations are excluded: a name counts as a character only if "
              "it speaks, is spoken to, or is thought about.", "",
              "| Name | Across the book | Total | Notes |", "|---|---|---:|---|"]
        for c in s_["presence"]:
            note = ("absent " + ", ".join(c["absent_runs"])) if c["absent_runs"] else ""
            if c["first_chapter"] and c["first_chapter"] > 1:
                note = (note + "; " if note else "") + f"first appears ch {c['first_chapter']}"
            L.append(f"| {c['name']} | `{c['spark']}` | {c['total']} | {note} |")

    if s_.get("places"):
        L += ["", "**Places and organisations named in the book:** "
              + ", ".join(s_["places"][:12]) + ".", ""]

    v = s_.get("voice") or {}
    if v.get("speakers_profiled", 0) >= 2:
        cov = v["coverage"]
        L += ["", "## Character voice", ""] + voice_brief(v) + ["",
              f"Speech was matched to a speaker for {cov['pct_attributed']}% of "
              f"{cov['dialogue_lines_found']:,} lines of dialogue. Only lines with "
              "a nearby name can be attributed, so this is a partial picture.", "",
              "| Speaker | Lines | Words per line | Vocabulary range | Questions |",
              "|---|---:|---:|---:|---:|"]
        for p in v["profiles"][:8]:
            L.append(f"| {p['name']} | {p['lines']} | {p['mean_words_per_line']} | "
                     f"{p['vocabulary_richness']} | {p['question_rate']} |")
        if v.get("mean_similarity") is not None:
            L += ["", f"**Average vocabulary overlap between speakers: "
                  f"{v['mean_similarity']}.** The higher this is, the more the "
                  "characters draw on the same words. At the top of the range "
                  "they become hard to tell apart on the page.", ""]
            for p in v["pairs"][:3]:
                L.append(f"- {p['a']} and {p['b']}: {p['similarity']}")

    h = whole["hygiene"]
    L += ["", "## Copyediting condition", ""] + copyedit_brief(h, ws) + ["",
          "These need no knowledge of the genre. In professionally edited work "
          "they sit at or near zero, so they are the clearest guide to how much "
          "editorial work the manuscript would need.", "",
          "| Issue | Count |", "|---|---:|",
          f"| Likely typos | {h['likely_typos']['count']} |",
          f"| Repeated words (“the the”) | {h['repeated_word_count']} |",
          f"| Paragraphs with an unclosed quote | {h['unbalanced_quotes']['paragraphs']} |",
          f"| Double spaces | {h['double_spaces']} |",
          f"| Mixed quote styles | {'yes' if h['mixed_quote_styles']['mixed'] else 'no'} |",
          f"| Mixed dash styles | {'yes' if h['dash_styles']['mixed'] else 'no'} |"]
    variants = h["possible_name_variants"]
    if ws is not None:
        import narrative as nv
        cl = nv.continuity_lines(ws)
        if cl:
            L += ["", "**Continuity errors found on reading.** Each is a line an "
                  "editor would have to fix:", ""] + [f"- {x}" for x in cl]
            # a name already described in the reading notes should not be listed
            # again by the automatic check
            blob = " ".join(cl).lower()
            variants = [v for v in variants
                        if v["a"].lower() not in blob and v["b"].lower() not in blob]

    if variants:
        L += ["", "**Names spelled inconsistently.** Each pair is worth checking, as "
              "these are usually genuine continuity errors:", ""]
        for v in variants[:8]:
            L.append(f"- {v['a']} ({v['count_a']} times) vs {v['b']} ({v['count_b']} times)")

    if drift:
        L += ["", "## Note: the opening is cleaner than the rest", "",
              "The first 2,000 words score markedly better than the manuscript as "
              "a whole:", ""]
        L += [f"- {d}" for d in drift]
        L += ["", "This usually means the opening has been revised many times and "
              "the later chapters have not. Read a late chapter before deciding.", ""]

    if ws is not None:
        import narrative as nv
        import structure_fit as sf
        L += sf.block(ws, genre)
        L += nv.loose_threads_block(ws) + nv.content_block(ws)

    L += ["", "## Attempt at interpretation", ""]
    for line in attempt_interpretation(genre, n_words, gs["dialogue_pct"],
                                       whole["shape"]["sentence_length"]["mean"]):
        L.append(f"- {line}")
    L += ["",
          "These are attempts, generated from rules of thumb rather than measured "
          "data. They are prompts to look, not findings.",
          ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="extract_book.py workdir, or a .txt file")
    ap.add_argument("--genre", default=None,
                    help=f"one of: {', '.join(GENRE_EXPECTATIONS)}")
    ap.add_argument("--json", default=None)
    ap.add_argument("--tropes", default=None,
                    help="comma-separated tropes you confirmed by reading")
    ap.add_argument("--moods", default=None,
                    help="comma-separated moods, in plain words")
    ap.add_argument("--tags", default=None,
                    help="comma-separated shelving tags for comps and positioning")
    ap.add_argument("--narrative", default=None,
                    help="a filled narrative worksheet.json, woven into the report")
    ap.add_argument("--brief", default=None,
                    help="two or three sentences from the reader, for the top of the report")
    ap.add_argument("--report", default=None,
                    help="write the reader-facing Markdown report here")
    ap.add_argument("--samples-dir", default="triage_samples",
                    help="where to write the sampled windows for reading")
    args = ap.parse_args()

    ws = None
    if args.narrative:
        import narrative as nv
        ws = nv.load_worksheet(args.narrative)
    raw_text, manifest, label = load(args.target)
    raw_words = len(WORD_RE.findall(raw_text))
    if raw_words < 500:
        sys.exit(f"only {raw_words} words — extraction probably failed.")

    # everything downstream measures the narrative, not the copyright page
    all_paras = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    lo, hi, matter_notes = trim_matter(all_paras)
    text = "\n\n".join(all_paras[lo:hi])
    n_words = len(WORD_RE.findall(text))
    trimmed_words = raw_words - n_words

    chapters = split_chapters(text)
    sample_text, plan, opening_text = build_sample(text)
    sample = measure(sample_text, "5k sample")
    whole = measure(text, "whole book")
    opening = measure(opening_text, "opening 2k") if opening_text else None

    # Write the sampled prose out. Without this the agent has numbers and has
    # never seen a sentence of the book — it could not establish genre, book
    # type, or anything else that requires actually reading.
    sdir = Path(args.samples_dir)
    sdir.mkdir(parents=True, exist_ok=True)
    written = []
    if plan.get("windows"):
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        offsets, run = [], 0
        for p in paragraphs:
            offsets.append(run)
            run += len(p.split())
        for name, frac, want in SAMPLE_PLAN:
            idx, _ = take(paragraphs, offsets, run, frac, want)
            f = sdir / f"{name}.txt"
            f.write_text(cap_words("\n\n".join(paragraphs[i] for i in idx), want),
                         "utf-8")
            written.append(str(f))
    else:
        f = sdir / "whole.txt"
        f.write_text(text, "utf-8")
        written.append(str(f))
    meta = manifest.get("metadata") or {}
    bt = book_type(text, n_words, chapters)
    gs = genre_signals(text, whole["percentages"]["dialogue"]["pct"])

    # whole-manuscript structure: none of this is visible from a sample
    names = st.find_names(text)
    roles = st.classify_names(text, names)
    people = {n for n, v in roles.items() if v["role"] == "person"}
    places = sorted(n for n, v in roles.items()
                    if v["role"] in ("place", "organisation"))
    # A confirmed cast from the reading pass beats any heuristic, and is the
    # only way aliases such as Stephen and Armitage get merged.
    cast_aliases = None
    if ws is not None:
        cast = (ws.get("to_be_filled_by_reading") or {}).get("cast") or []
        if cast:
            cast_aliases = {c["name"]: [c["name"]] + list(c.get("aliases") or [])
                            for c in cast}
            people = set(cast_aliases)
    tex = st.texture(chapters)
    chdist = st.chapter_distribution(tex)
    walls = st.walls_of_text(text)
    cast = st.cast_load(text, people)
    tropes_found = st.trope_candidates(text)
    pres = (st.presence(chapters, people, aliases=cast_aliases)
            if len(chapters) > 2 and people else [])
    voice = st.voice_distinctness(text, people)

    W = 74
    print("\n" + "=" * W)
    print("THE BASICS")
    print("=" * W)
    print(f"  Title (detected)   : {meta.get('title') or '— not found —'}")
    if meta.get("source"):
        print(f"                       (from {meta['source']})")
    print(f"  Author (detected)  : {meta.get('author') or '— not found —'}")
    print(f"  Length             : {n_words:,} words  (~{round(n_words/275):,} pages at 275 w/p)")
    if trimmed_words:
        seen, tidy = set(), []
        for nt in matter_notes:
            if nt not in seen:
                seen.add(nt)
                tidy.append(nt)
        joined = (", ".join(tidy[:-1]) + " and " + tidy[-1]) if len(tidy) > 1 else tidy[0]
        print(f"  Excluded           : {trimmed_words:,} words of {joined}, "
              "not counted or sampled")
    gaps = numbering_gaps(chapters)
    if gaps:
        print(f"  Numbering gap      : no heading found for chapter"
              f"{'s' if len(gaps) > 1 else ''} "
              f"{', '.join(map(str, gaps[:8]))}. The file is probably missing "
              "them, so the count below is of headings, not of chapters.")
    print(f"  Chapters detected  : {len(chapters)}"
          + (f"  (avg {n_words//max(len(chapters),1):,} words)" if chapters else ""))
    print(f"  Length band        : {bt['length_band']}")
    print(f"  Narration          : {gs['person']}, {gs['tense']} tense, "
          f"{gs['dialogue_pct']}% dialogue")
    top = [f"{g} ({n})" for g, n in list(gs["lexicon_hits"].items())[:3] if n]
    print(f"  Genre word signals : {', '.join(top) if top else 'no strong signal'}")
    for s in bt["signals"]:
        print(f"  · {s}")
    print("\n  Book type and genre are NOT decided here. These are signals for the")
    print("  reading agent, which must confirm them from the text itself.")

    print("\n" + "=" * W)
    print("THE CRAFT METRICS")
    print("=" * W)
    if plan.get("windows"):
        seg = ", ".join(f"{w['window']} {w['words']:,}w @{w['from_pct']}%"
                        for w in plan["windows"])
        print(f"  Measured on a {plan['words']:,}-word read: {seg}")
    else:
        print(f"  {plan.get('note', '')}")
    print(f"  Check column is the whole {n_words:,}-word manuscript.\n")

    print(f"  {'marker':34} {'sample':>9} {'whole':>9}   denominator")
    print(f"  {'-'*34} {'-'*9} {'-'*9}   {'-'*22}")
    for key, v in sample["percentages"].items():
        w = whole["percentages"][key]
        print(f"  {key.replace('_',' '):34} {v['pct']:>8.1f}% {w['pct']:>8.1f}%   "
              f"of {v['pct_of']}")

    sl, pl = whole["shape"]["sentence_length"], whole["shape"]["paragraph_length"]
    print(f"\n  RHYTHM  (variation matters more than the average — a low figure")
    print(f"           means every sentence is the same length, which reads flat)")
    print(f"    sentences   avg {sl['mean']:>5} words, variation {sl['cv']}")
    print(f"    paragraphs  avg {pl['mean']:>5} words, variation {pl['cv']}")
    if walls:
        print(f"    walls of text  {walls['pct_of_paragraphs']}% of paragraphs over "
              f"{walls['threshold']} words (longest {walls['longest']})")
    if chdist:
        print(f"    chapters    avg {chdist['mean']:,} words, variation {chdist['cv']} "
              f"(shortest {chdist['shortest']:,}, longest {chdist['longest']:,})")

    if tropes_found:
        print(f"\n  TROPE CANDIDATES  (keyword hits only, confirm by reading)")
        for tc in tropes_found[:8]:
            print(f"    {tc['trope']:<34} {tc['hits']:>3} hits")
    print(f"\n  CAST ONBOARDING")
    print(f"    {cast['count']} named characters in the first "
          f"{cast['window_words']:,} words")
    if cast["names"]:
        print("    " + ", ".join(f"{c['name']} (@{c['first_at_word']})"
                                 for c in cast["names"][:12]))

    if tex:
        print(f"\n  TEXTURE CURVE  (bar = share of the chapter that is dialogue)")
        print(f"    {'ch':>3} {'words':>7} {'dial':>6} {'sent':>6} {'para':>6} "
              f"{'?!/1k':>7} {'act/1k':>7} {'filt/1k':>8}  {'':<10}")
        dial_series = [r["dialogue_pct"] for r in tex]
        lo, hi = min(dial_series), max(dial_series)
        for r in tex:
            fill = 0 if hi == lo else int((r["dialogue_pct"] - lo) / (hi - lo) * 10)
            print(f"    {r['n']:>3} {r['words']:>7,} {r['dialogue_pct']:>5.1f}% "
                  f"{r['mean_sentence']:>6.1f} {r['mean_paragraph']:>6.1f} "
                  f"{r['qmark_excl_per_1k']:>7.1f} {r['action_per_1k']:>7.2f} "
                  f"{r['filter_per_1k']:>8.2f}  {'█' * fill}")

    if pres:
        print(f"\n  CHARACTER PRESENCE  (mentions per chapter, first to last)")
        for c in pres:
            gap = f"  absent {', '.join(c['absent_runs'])}" if c["absent_runs"] else ""
            print(f"    {c['name'][:20]:<20} {c['spark']}  {c['total']:>5}{gap}")

    if voice["speakers_profiled"] >= 2:
        v = voice
        print(f"\n  CHARACTER VOICE  ({v['coverage']['pct_attributed']}% of "
              f"{v['coverage']['dialogue_lines_found']} dialogue lines could be "
              f"attributed to a speaker)")
        print(f"    {'speaker':<14} {'lines':>6} {'words/line':>11} {'vocab':>7} {'questions':>10}")
        for p in v["profiles"][:8]:
            print(f"    {p['name'][:14]:<14} {p['lines']:>6} "
                  f"{p['mean_words_per_line']:>11} {p['vocabulary_richness']:>7} "
                  f"{p['question_rate']:>10}")
        if v["mean_similarity"] is not None:
            print(f"    mean vocabulary overlap between speakers: {v['mean_similarity']}")
            print("    (higher means the characters use more of the same words —")
            print("     at the top of the range they are hard to tell apart)")
            for p in v["pairs"][:3]:
                print(f"      {p['a']} / {p['b']}: {p['similarity']}")

    h = whole["hygiene"]
    print(f"\n  MECHANICAL (whole manuscript — these need no genre to interpret)")
    print(f"    likely typos                {h['likely_typos']['count']}")
    print(f"    repeated words              {h['repeated_word_count']}")
    print(f"    paragraphs w/ unclosed quote {h['unbalanced_quotes']['paragraphs']}")
    print(f"    double spaces               {h['double_spaces']}")
    print(f"    mixed quote styles          {h['mixed_quote_styles']['mixed']}")
    print(f"    mixed dash styles           {h['dash_styles']['mixed']}")
    for v in h["possible_name_variants"][:5]:
        print(f"    name drift: {v['a']} ({v['count_a']}) vs {v['b']} ({v['count_b']})")

    # Front-loaded polish: the OPENING window alone against the whole book. The
    # 5k sample includes the middle and ending, so comparing that would dilute
    # exactly the difference we are looking for.
    drift = []
    if opening:
        for key in ("filter_word_sentences", "cliche_paragraphs",
                    "formula_vocab_paragraphs", "participial_paragraph_endings",
                    "exotic_dialogue_tags"):
            o_, w_ = opening["percentages"][key]["pct"], whole["percentages"][key]["pct"]
            if w_ >= 2.0 and o_ < w_ * 0.6:
                drift.append(f"{key.replace('_',' ')}: {o_}% in the opening 2k "
                             f"vs {w_}% across the manuscript")
    if drift:
        print("\n  NOTE — the opening 2,000 words are markedly cleaner than the "
              "manuscript as a whole:")
        for d in drift:
            print(f"    · {d}")
        print("    Consistent with a polished opening over an unedited body. "
              "Worth spot-reading a late chapter.")

    print("\n" + "-" * W)
    for line in attempt_interpretation(
            args.genre, n_words, gs["dialogue_pct"],
            whole["shape"]["sentence_length"]["mean"]):
        print("  " + line)
    print("-" * W)
    print("  These are ATTEMPTS at interpretation, generated from rule-of-thumb")
    print("  ranges, not from measured data. They are not a recommendation and")
    print("  not a decision. The acquisition judgement is the reader's.\n")

    print(f"\n  Sampled prose written for reading: {', '.join(written)}")
    print("  READ THESE before writing any report — the numbers above do not")
    print("  tell you what the book is about, or whether it is any good.\n")

    if args.report:
        Path(args.report).write_text(build_report(
            meta, manifest, n_words, chapters, bt, gs, plan, sample, whole,
            drift, args.genre,
            {"texture": tex, "chdist": chdist, "walls": walls, "cast": cast,
             "presence": pres, "voice": voice, "places": places},
            args.brief, ws,
            {"tropes": args.tropes, "moods": args.moods, "tags": args.tags,
             "candidates": tropes_found}), "utf-8")
        print(f"  wrote {args.report}\n")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "label": label, "metadata": meta, "words": n_words,
            "chapters": len(chapters), "book_type": bt, "genre_signals": gs,
            "sample_plan": plan, "sample": sample, "whole": whole,
            "front_loaded_polish": drift,
            "attempt": attempt_interpretation(
                args.genre, n_words, gs["dialogue_pct"],
                whole["shape"]["sentence_length"]["mean"]),
        }, indent=2), "utf-8")
        print(f"  wrote {args.json}\n")


if __name__ == "__main__":
    main()
