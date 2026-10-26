#!/usr/bin/env python3
"""Craft-floor markers for a manuscript. Every number here is counted, not judged.

    python3 craft_floor.py <text-file> [--json out.json] [--chapters]

Input is plain text (run extract_book.py first for epub/pdf/docx).

Reports four groups:
  1. shape        — length, chapters, dialogue ratio, burstiness
  2. craft        — filter words, dialogue tags, adverbs, clichés
  3. formula      — stock phrasing and LLM-characteristic constructions
  4. hygiene      — mechanical editing errors and likely typos

Nothing here decides anything. Rates are reported per 1,000 or per 10,000 words
with locations, so a human can check every one against the text. Thresholds are
NOT built in: a rate is meaningless until calibrated against published fiction in
the same category. See references/norms.md.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ------------------------------------------------------------------ word lists

FILTER_VERBS = (
    "saw|watched|noticed|felt|heard|smelled|tasted|sensed|realized|realised|"
    "thought|wondered|knew|decided|remembered|understood|observed|considered|"
    "seemed to|began to|started to|tried to|managed to"
)
FILTER_RE = re.compile(
    rf"\b(?:he|she|they|it|i|we)\s+(?:{FILTER_VERBS})\b", re.I
)

PLAIN_TAGS = {"said", "asked", "replied", "answered", "added"}
EXOTIC_TAGS = {
    "expostulated", "ejaculated", "opined", "articulated", "vocalized",
    "chuckled", "laughed", "smiled", "grinned", "smirked", "beamed", "giggled",
    "sighed", "breathed", "gasped", "hissed", "growled", "snarled", "barked",
    "spat", "purred", "cooed", "chirped", "quipped", "retorted", "countered",
    "interjected", "exclaimed", "declared", "proclaimed", "announced",
    "muttered", "murmured", "mumbled", "whispered", "shouted", "yelled",
    "screamed", "cried", "sobbed", "wailed", "groaned", "moaned", "pleaded",
    "begged", "demanded", "insisted", "protested", "admitted", "confessed",
    "offered", "ventured", "mused", "pondered", "reasoned", "concluded",
}
# tags that are physically impossible as speech verbs — the strongest signal
IMPOSSIBLE_TAGS = {
    "chuckled", "laughed", "smiled", "grinned", "smirked", "beamed", "giggled",
    "sighed", "shrugged", "nodded", "winced", "frowned", "blinked",
}

CLICHES = [
    "heart pounded", "heart hammered", "heart raced", "heart skipped a beat",
    "breath she didn't know she was holding", "breath he didn't know he was holding",
    "let out a breath", "released a breath", "held her breath", "held his breath",
    "shivers down", "shiver down", "chills down", "sent a shiver",
    "little did", "unbeknownst to", "time stood still", "the calm before the storm",
    "blood ran cold", "eyes widened", "eyes narrowed", "jaw clenched",
    "clenched his jaw", "clenched her jaw", "hands balled into fists",
    "a mix of", "a mixture of emotions", "wave of relief", "wave of nausea",
    "pit of her stomach", "pit of his stomach", "knot in her stomach",
    "butterflies in her stomach", "lump in her throat", "lump in his throat",
    "tears welled", "tears streamed", "choked back", "trailed off",
    "let out a shaky", "drew a shaky", "released a shaky",
    "the air was thick with", "the silence was deafening", "deafening silence",
    "every fiber of", "every fibre of", "with bated breath",
    "in the nick of time", "against all odds", "little more than a whisper",
    "barely above a whisper", "if looks could kill", "the world around her faded",
    "the world around him faded", "she couldn't help but", "he couldn't help but",
]

# vocabulary over-represented in LLM prose. Individually innocent — the signal is
# density and co-occurrence, never any single hit.
FORMULA_VOCAB = [
    "delve", "delved", "delving", "tapestry", "testament to", "navigate the",
    "navigating the", "ever-evolving", "ever-changing", "underscore",
    "underscores", "underscoring", "pivotal", "crucial", "myriad", "plethora",
    "realm of", "in the realm", "landscape of", "beacon of", "cacophony",
    "symphony of", "kaleidoscope", "labyrinth of", "intricate dance",
    "stark reminder", "poignant", "palpable", "unwavering", "steadfast",
    "resolute", "indelible", "profound sense", "sense of unease",
    "weight of the world", "moreover", "furthermore", "it's worth noting",
    "it is worth noting", "in conclusion", "ultimately,", "indeed,",
    "meticulous", "meticulously", "seamless", "seamlessly", "vibrant",
    "bustling", "nestled", "boasts", "embark", "embarked on a journey",
    "a testament", "speaks volumes", "leaving an indelible",
]

# names disproportionately produced by LLMs. Weak on their own; several is a signal.
FORMULA_NAMES = [
    "Elara", "Kael", "Lyra", "Seraphina", "Aeliana", "Caelum", "Zephyr",
    "Isolde", "Vesper", "Thorne", "Elowen", "Rhys", "Sylas", "Anya",
    "Kaelen", "Nyx", "Orion", "Lucian", "Cassius", "Wren",
]

# "not just X, but Y" antithesis — the most characteristic LLM syntactic tic
ANTITHESIS_RE = re.compile(
    r"\bnot\s+(?:just|only|merely|simply)\b[^.;!?]{2,60}?\bbut\b", re.I
)
NEGATED_DEF_RE = re.compile(
    r"\b(?:it|this|that|he|she)\s+(?:wasn't|isn't|was not|is not)\b[^.;!?]{2,50}[.;]\s*"
    r"(?:it|this|that|he|she)\s+(?:was|is)\b", re.I
)
TRICOLON_RE = re.compile(r"\b\w+,\s+\w+,\s+and\s+\w+\b")
PARTICIPIAL_END_RE = re.compile(r",\s+\w+ing\b[^.!?]*[.!?]['\"”]?\s*$")

# ------------------------------------------------------------------ tokenising

SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])[\"'”’]?\s+(?=[\"'“‘(]?[A-Z0-9])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
DIALOGUE_RE = re.compile(r"[\"“]([^\"“”]{1,2000}?)[\"”]")
HEADING_RE = re.compile(
    r"^(?:#{1,3}\s+.+|(?:chapter|part|book|prologue|epilogue|interlude)\b.{0,60}|"
    r"[IVXLC]{1,7}|\d{1,3})$",
    re.I,
)


# Dialogue is not always in quotation marks. Russian, French, Spanish, Polish and
# other traditions open speech with a dash, and plenty of English-language
# manuscripts follow that convention. Counting only quote marks reports such a
# book as having almost no dialogue, which is badly wrong rather than slightly.
DASH_SPEECH_RE = re.compile(r"^\s*[-\u2013\u2014]\s+(.+)$", re.S)
SPEECH_VERBS = (r"said|told|asked|replied|answered|added|repeated|murmured|"
                r"muttered|whispered|shouted|cried|continued|began|insisted|"
                r"protested|agreed|admitted|laughed|snapped")
TAG_CUT_RE = re.compile(rf",\s+(?:\w+\s+){{0,3}}?(?:{SPEECH_VERBS})\b", re.I)


def uses_dash_dialogue(paragraphs):
    dash = sum(1 for p in paragraphs if DASH_SPEECH_RE.match(p))
    quoted = sum(1 for p in paragraphs if p.lstrip()[:1] in ('"', "\u201c"))
    return dash >= 10 and dash > quoted * 3


def dialogue_spans(text):
    """Speech in the manuscript, whichever convention it uses.

    Returns (list of speech strings, convention name).
    """
    paras = [p for p in text.split("\n\n") if p.strip()]
    if uses_dash_dialogue(paras):
        out = []
        for p in paras:
            m = DASH_SPEECH_RE.match(p)
            if not m:
                continue
            speech = m.group(1)
            cut = TAG_CUT_RE.search(speech)     # trim the trailing attribution
            out.append(speech[:cut.start()] if cut else speech)
        return out, "dash"
    return DIALOGUE_RE.findall(text), "quotes"


def load_dictionary():
    """A system word list, if the machine has one. Optional by design: the
    sandbox this runs in may not have one, and everything degrades to the
    morphology rules below."""
    for path in ("/usr/share/dict/words", "/usr/dict/words"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                return {w.strip().lower() for w in fh if w.strip()}
        except OSError:
            continue
    return set()


DICTIONARY = load_dictionary()


def known_word(w, D=None):
    """Is this a real word? Checks inflected forms too, because word lists hold
    stems rather than plurals and past tenses."""
    D = DICTIONARY if D is None else D
    if not D:
        return False
    if w in D:
        return True
    for suf in ("s", "es", "ed", "ing", "ly", "er", "est", "en"):
        if w.endswith(suf):
            stem = w[: -len(suf)]
            if stem in D or (stem + "e") in D:
                return True
    # A bare "-d" only attaches to a stem already ending in e (believe/believed).
    # Allowing it against any stem would treat "walkd" as a real word.
    if w.endswith("d") and (w[:-1] + "e") in D:
        return True
    if w.endswith("ies") and (w[:-3] + "y") in D:
        return True
    return False


def is_inflection(a, b):
    """One word is a plural, possessive or tense of the other."""
    lo, hi = sorted((a, b), key=len)
    if lo == hi:
        return False
    return any(hi == lo + suf for suf in
               ("s", "d", "r", "n", "y", "es", "ed", "er", "'s", "’s"))


def stat(values):
    """mean, stdev and coefficient of variation."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "stdev": 0.0, "cv": 0.0, "n": 0}
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0.0
    sd = var ** 0.5
    return {"mean": round(mean, 1), "stdev": round(sd, 1),
            "cv": round(sd / mean, 3) if mean else 0.0, "n": n}


def edit_distance_le1(a, b):
    """True if a and b are one edit apart, counting an adjacent transposition
    as a single edit (Damerau). Transpositions — teh, adn, tabel — are the most
    common typo there is, and plain Levenshtein scores them as two."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diff) == 1:
            return True
        if len(diff) == 2:
            i, j = diff
            return j == i + 1 and a[i] == b[j] and a[j] == b[i]
        return False
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = 0
    while i < la and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


# capitalised words that open sentences constantly and are not names
NAME_STOPLIST = {
    "the", "then", "when", "what", "where", "why", "who", "that", "this",
    "there", "their", "they", "them", "these", "those", "she", "her", "hers",
    "him", "his", "and", "but", "for", "not", "now", "one", "two", "three",
    "some", "such", "with", "was", "were", "have", "had", "has", "here",
    "how", "into", "just", "like", "more", "much", "only", "over", "said",
    "she'd", "still", "than", "though", "through", "very", "well", "will",
    "would", "you", "your", "after", "again", "all", "another", "because",
    "before", "behind", "beyond", "both", "even", "every", "from", "good",
    "great", "inside", "instead", "last", "later", "left", "long", "most",
    "never", "next", "nobody", "none", "nothing", "once", "outside", "own",
    "perhaps", "right", "same", "since", "something", "soon", "sometimes",
    "somewhere", "until", "upon", "while", "without", "yes", "yet",
}


# ------------------------------------------------------------------ measurement


def find_all(text, phrases, words):
    """Count phrase hits, with the first location of each, as a rate per 10k."""
    hits, total = [], 0
    low = text.lower()
    for p in phrases:
        n = low.count(p.lower())
        if n:
            total += n
            hits.append({"phrase": p, "count": n,
                         "first_char": low.find(p.lower())})
    hits.sort(key=lambda h: -h["count"])
    return {
        "distinct": len(hits),
        "total": total,
        "per_10k_words": round(total / words * 10000, 1) if words else 0.0,
        "top": hits[:25],
    }


def analyse_dialogue_tags(text):
    """Speech tags, in whichever dialogue convention the manuscript uses.

    With quotation marks the tag sits just past the closing quote. With dash
    dialogue it follows a comma inside the speech paragraph, so both are read
    rather than reporting a dash-punctuated book as having no tags at all.
    """
    plain = exotic = impossible = adverbial = 0
    exotic_used = Counter()

    paras = [p for p in text.split("\n\n") if p.strip()]
    if uses_dash_dialogue(paras):
        for p in paras:
            m = DASH_SPEECH_RE.match(p)
            if not m:
                continue
            cut = TAG_CUT_RE.search(m.group(1))
            if not cut:
                continue
            after = m.group(1)[cut.start():]
            toks = re.findall(r"[A-Za-z']+", after)[:6]
            verb = next((t.lower() for t in toks
                         if t.lower() in PLAIN_TAGS or t.lower() in EXOTIC_TAGS), None)
            if verb is None:
                continue
            if verb in PLAIN_TAGS:
                plain += 1
            else:
                exotic += 1
                exotic_used[verb] += 1
                if verb in IMPOSSIBLE_TAGS:
                    impossible += 1
            i = [t.lower() for t in toks].index(verb)
            if i + 1 < len(toks) and toks[i + 1].lower().endswith("ly"):
                adverbial += 1
        total = plain + exotic
        return {
            "convention": "dash",
            "tagged_lines_found": total,
            "plain_said_asked": plain,
            "exotic": exotic,
            "exotic_share": round(exotic / total, 3) if total else 0.0,
            "physically_impossible": impossible,
            "adverbial_tags": adverbial,
            "most_used_exotic": exotic_used.most_common(10),
        }

    pattern = (r"[\"”]\s*[,.]?\s*([A-Za-z]+)(?:\s+([A-Za-z]+))?"
               r"(?:\s+([A-Za-z]+))?")
    for m in re.finditer(pattern, text):
        a = (m.group(1) or "").lower()
        b = (m.group(2) or "").lower()
        c = (m.group(3) or "").lower()
        # the tag may lead ("said Kael") or follow the speaker ("Kael said");
        # the adverb is whatever comes after the verb, wherever the verb sits
        if a in PLAIN_TAGS or a in EXOTIC_TAGS:
            verb, nxt = a, b
        elif b in PLAIN_TAGS or b in EXOTIC_TAGS:
            verb, nxt = b, c
        else:
            continue
        if verb in PLAIN_TAGS:
            plain += 1
        else:
            exotic += 1
            exotic_used[verb] += 1
            if verb in IMPOSSIBLE_TAGS:
                impossible += 1
        if nxt and nxt.endswith("ly") and len(nxt) > 4:
            adverbial += 1
    total = plain + exotic
    return {
        "tagged_lines_found": total,
        "plain_said_asked": plain,
        "exotic": exotic,
        "exotic_share": round(exotic / total, 3) if total else 0.0,
        "physically_impossible": impossible,
        "adverbial_tags": adverbial,
        "most_used_exotic": exotic_used.most_common(10),
    }


def analyse_hygiene(text, paragraphs, words_list):
    """Mechanical editing errors. Near-zero false positives by construction."""
    issues = {}

    straight = text.count('"')
    curly = text.count("“") + text.count("”")
    issues["mixed_quote_styles"] = {
        "straight_double": straight, "curly_double": curly,
        "mixed": bool(straight and curly),
    }
    # A speech running over several paragraphs opens each one and closes only
    # the last. That is standard typography rather than an error, so an unclosed
    # paragraph followed by one that opens a quote does not count.
    unbalanced = []
    for i, p in enumerate(paragraphs):
        if not ((p.count('"') % 2) or (p.count("“") != p.count("”"))):
            continue
        nxt = paragraphs[i + 1].lstrip() if i + 1 < len(paragraphs) else ""
        if nxt[:1] in ('"', "“"):
            continue
        unbalanced.append(i)
    issues["unbalanced_quotes"] = {"paragraphs": len(unbalanced),
                                   "first_examples": unbalanced[:10]}

    issues["double_spaces"] = len(re.findall(r"\S  +\S", text))
    issues["space_before_punctuation"] = len(re.findall(r"\s+[,.;:!?]", text))
    issues["missing_space_after_punctuation"] = len(
        re.findall(r"[,;:][A-Za-z]|[.!?][A-Z][a-z]", text))
    issues["repeated_words"] = [
        m.group(0) for m in re.finditer(r"\b(\w+)\s+\1\b", text, re.I)
    ][:20]
    issues["repeated_word_count"] = len(re.findall(r"\b(\w+)\s+\1\b", text, re.I))

    dashes = {"hyphen_pair": text.count("--"), "em_dash": text.count("—"),
              "en_dash": text.count("–")}
    issues["dash_styles"] = dict(
        dashes, mixed=sum(1 for v in dashes.values() if v) > 1)

    no_terminal = [i for i, p in enumerate(paragraphs)
                   if len(p.split()) > 5 and not re.search(r"[.!?…\"”’)]$", p)]
    issues["paragraphs_without_terminal_punctuation"] = {
        "count": len(no_terminal), "first_examples": no_terminal[:10]}

    # Proper-noun spelling drift. Names often start sentences, so position is a
    # bad test; instead treat a token as a name when it is almost always
    # capitalised. "The" appears lowercase constantly and drops out; "Sara"
    # never does.
    cased = Counter(words_list)
    folded = Counter(w.lower() for w in words_list)
    mid_caps = Counter()
    for w, c in cased.items():
        if (len(w) > 3 and w[0].isupper() and w.lower() not in NAME_STOPLIST
                and c / folded[w.lower()] > 0.9):
            mid_caps[w] += c
    # Interjections and honorifics are capitalised at the start of dialogue and
    # would otherwise turn up as spelling drift ("Yeah" against "Leah").
    from structure import NOT_NAMES
    names = [w for w, c in mid_caps.items()
             if c >= 2 and w.lower().replace("\u2019", "'") not in NOT_NAMES]
    variants = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            aa = a.lower().replace("’", "'")
            bb = b.lower().replace("’", "'")
            # Bennet's / Bennets differ only by an apostrophe, which is a
            # possessive rather than a spelling drift.
            same_but_apostrophe = aa.replace("'", "") == bb.replace("'", "")
            if (aa != bb and edit_distance_le1(aa, bb)
                    and not is_inflection(aa, bb) and not same_but_apostrophe):
                variants.append({"a": a, "count_a": mid_caps[a],
                                 "b": b, "count_b": mid_caps[b]})
    issues["possible_name_variants"] = variants[:20]

    # likely typos: a hapax one edit away from a word used often in this document
    counts = Counter(w.lower() for w in words_list)
    # "frequent enough to be the intended word" scales with document length
    min_freq = max(3, len(words_list) // 20000)
    # 4 characters minimum: 3-letter words are mostly real words one edit from
    # other real words (one/gone, cat/cut), and a false typo report is worse
    # than a missed one.
    frequent = {w for w, c in counts.items() if c >= min_freq and len(w) > 3}
    hapax = [w for w, c in counts.items() if c == 1 and len(w) > 3 and w.isalpha()]
    typos = []
    for h in hapax:
        # A real book is full of rare but perfectly good words sitting one edit
        # from a common one: mien, comers, attacked, acquaintances. Without this
        # filter, Pride and Prejudice reports several hundred typos.
        if known_word(h):
            continue
        for f in frequent:
            if abs(len(h) - len(f)) <= 1 and edit_distance_le1(h, f):
                if is_inflection(h, f):
                    continue
                typos.append({"found": h, "probably": f, "corpus_count": counts[f]})
                break
    issues["likely_typos"] = {"count": len(typos), "examples": typos[:25]}
    issues["unrecognised_singletons"] = len(hapax)
    return issues


def per_chapter(paragraphs, words_total):
    """Split on headings and report the metrics that feed a texture curve."""
    chapters, current, title = [], [], None
    for p in paragraphs:
        if len(p) <= 70 and HEADING_RE.match(p.strip()):
            if current:
                chapters.append((title, current))
            title, current = p.strip().lstrip("# "), []
        else:
            current.append(p)
    if current:
        chapters.append((title, current))
    if len(chapters) < 2:
        return []

    out = []
    for i, (t, paras) in enumerate(chapters):
        body = "\n\n".join(paras)
        w = WORD_RE.findall(body)
        n = len(w)
        if n < 50:
            continue
        sents = [len(WORD_RE.findall(s)) for s in SENT_SPLIT_RE.split(body) if s.strip()]
        dial = sum(len(WORD_RE.findall(m)) for m in DIALOGUE_RE.findall(body))
        out.append({
            "index": i + 1,
            "title": t or f"(untitled block {i + 1})",
            "words": n,
            "share_of_book": round(n / words_total * 100, 1) if words_total else 0.0,
            "dialogue_ratio": round(dial / n, 3),
            "mean_sentence_words": round(sum(sents) / len(sents), 1) if sents else 0.0,
            "filter_per_1k": round(len(FILTER_RE.findall(body)) / n * 1000, 2),
            "mean_paragraph_words": round(n / len(paras), 1) if paras else 0.0,
        })
    return out


# ------------------------------------------------------------------------ main


def measure(text, label="text"):
    """All craft-floor metrics for a block of text. Pure counting, no judgement.

    Percentage denominators are chosen so each figure is independently
    interpretable, and are named in the `pct_of` field beside every one.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    words_list = WORD_RE.findall(text)
    n_words = len(words_list)
    sentences = [s for s in SENT_SPLIT_RE.split(text) if s.strip()]
    sent_lens = [len(WORD_RE.findall(s)) for s in sentences]
    para_lens = [len(p.split()) for p in paragraphs]
    spans, convention = dialogue_spans(text)
    dialogue_words = sum(len(WORD_RE.findall(m)) for m in spans)

    per1k = lambda n: round(n / n_words * 1000, 2)
    per10k = lambda n: round(n / n_words * 10000, 1)

    filter_hits = FILTER_RE.findall(text)
    adverbs = re.findall(r"\b\w{4,}ly\b", text)
    participial_ends = sum(1 for p in paragraphs if PARTICIPIAL_END_RE.search(p))

    # sentences and paragraphs carrying at least one instance — these are the
    # denominators that make a percentage mean something to a human reader
    pct = lambda n, d: round(n / d * 100, 1) if d else 0.0
    filter_sents = sum(1 for s in sentences if FILTER_RE.search(s))
    cliche_paras = sum(1 for p in paragraphs
                       if any(c in p.lower() for c in CLICHES))
    formula_paras = sum(1 for p in paragraphs
                        if any(v.lower() in p.lower() for v in FORMULA_VOCAB))
    tags = analyse_dialogue_tags(text)
    tagged = tags["tagged_lines_found"]

    report = {
        "label": label,
        "percentages": {
            "filter_word_sentences": {
                "pct": pct(filter_sents, len(sentences)), "count": filter_sents,
                "of": len(sentences), "pct_of": "sentences"},
            "ly_adverbs": {
                "pct": pct(len(re.findall(r"\b\w{4,}ly\b", text)), n_words),
                "count": len(re.findall(r"\b\w{4,}ly\b", text)),
                "of": n_words, "pct_of": "words"},
            "exotic_dialogue_tags": {
                "pct": pct(tags["exotic"], tagged), "count": tags["exotic"],
                "of": tagged, "pct_of": "tagged speech lines"},
            "impossible_dialogue_tags": {
                "pct": pct(tags["physically_impossible"], tagged),
                "count": tags["physically_impossible"],
                "of": tagged, "pct_of": "tagged speech lines"},
            "adverbial_dialogue_tags": {
                "pct": pct(tags["adverbial_tags"], tagged),
                "count": tags["adverbial_tags"],
                "of": tagged, "pct_of": "tagged speech lines"},
            "cliche_paragraphs": {
                "pct": pct(cliche_paras, len(paragraphs)), "count": cliche_paras,
                "of": len(paragraphs), "pct_of": "paragraphs"},
            "formula_vocab_paragraphs": {
                "pct": pct(formula_paras, len(paragraphs)), "count": formula_paras,
                "of": len(paragraphs), "pct_of": "paragraphs"},
            "participial_paragraph_endings": {
                "pct": pct(sum(1 for p in paragraphs if PARTICIPIAL_END_RE.search(p)),
                           len(paragraphs)),
                "count": sum(1 for p in paragraphs if PARTICIPIAL_END_RE.search(p)),
                "of": len(paragraphs), "pct_of": "paragraphs"},
            "dialogue": {
                "pct": pct(dialogue_words, n_words), "count": dialogue_words,
                "of": n_words, "pct_of": "words"},
        },
        "shape": {
            "dialogue_convention": convention,
            "words": n_words,
            "paragraphs": len(paragraphs),
            "sentences": len(sentences),
            "dialogue_ratio": round(dialogue_words / n_words, 3),
            "sentence_length": stat(sent_lens),
            "paragraph_length": stat(para_lens),
        },
        "craft": {
            "filter_words": {"count": len(filter_hits), "per_1k": per1k(len(filter_hits)),
                             "most_common": Counter(h.lower() for h in filter_hits).most_common(10)},
            "adverbs_ly": {"count": len(adverbs), "per_1k": per1k(len(adverbs)),
                           "most_common": Counter(a.lower() for a in adverbs).most_common(10)},
            "dialogue_tags": analyse_dialogue_tags(text),
            "cliches": find_all(text, CLICHES, n_words),
        },
        "formula": {
            "vocabulary": find_all(text, FORMULA_VOCAB, n_words),
            "names": find_all(text, FORMULA_NAMES, n_words),
            "antithesis_not_just_but": {
                "count": len(ANTITHESIS_RE.findall(text)),
                "per_10k": per10k(len(ANTITHESIS_RE.findall(text))),
            },
            "negated_definition": {"count": len(NEGATED_DEF_RE.findall(text))},
            "tricolon": {"count": len(TRICOLON_RE.findall(text)),
                         "per_10k": per10k(len(TRICOLON_RE.findall(text)))},
            "participial_paragraph_endings": {
                "count": participial_ends,
                "share_of_paragraphs": round(participial_ends / len(paragraphs), 3),
            },
            "em_dashes_per_1k": per1k(text.count("—")),
            "uniformity": {
                "sentence_cv": stat(sent_lens)["cv"],
                "paragraph_cv": stat(para_lens)["cv"],
                "note": "Low coefficient of variation means unusually even rhythm. "
                        "Human literary prose is typically bursty; machine prose is not.",
            },
        },
        "hygiene": analyse_hygiene(text, paragraphs, words_list),
        "chapters": per_chapter(paragraphs, n_words),
    }
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("textfile")
    ap.add_argument("--json", default=None)
    ap.add_argument("--chapters", action="store_true",
                    help="include the per-chapter table in stdout")
    args = ap.parse_args()

    path = Path(args.textfile)
    if not path.exists():
        sys.exit(f"not found: {path}")
    text = path.read_text("utf-8", errors="replace")
    n = len(WORD_RE.findall(text))
    if n < 1000:
        sys.exit(f"only {n} words — too short to measure. Extraction may have failed.")
    report = measure(text, path.name)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), "utf-8")
        print(f"wrote {args.json}")

    s, c, f, h = (report["shape"], report["craft"],
                  report["formula"], report["hygiene"])
    print(f"\n{'='*62}\n{path.name}\n{'='*62}")
    print(f"  {s['words']:,} words · {s['paragraphs']:,} paragraphs · "
          f"{len(report['chapters'])} chapters detected")
    print(f"  dialogue {s['dialogue_ratio']:.0%} of words")
    print(f"  sentence length {s['sentence_length']['mean']} avg, "
          f"CV {s['sentence_length']['cv']}")
    print(f"  paragraph length {s['paragraph_length']['mean']} avg, "
          f"CV {s['paragraph_length']['cv']}")

    print("\nCRAFT")
    print(f"  filter words            {c['filter_words']['per_1k']:>7} /1k  "
          f"({c['filter_words']['count']} total)")
    print(f"  -ly adverbs             {c['adverbs_ly']['per_1k']:>7} /1k")
    t = c["dialogue_tags"]
    print(f"  exotic dialogue tags    {t['exotic_share']:>7.0%} of {t['tagged_lines_found']} tagged lines")
    print(f"    physically impossible {t['physically_impossible']:>7}  (smiled/chuckled as speech verbs)")
    print(f"    adverbial tags        {t['adverbial_tags']:>7}  (\"said quietly\")")
    print(f"  clichés                 {c['cliches']['per_10k_words']:>7} /10k  "
          f"({c['cliches']['distinct']} distinct)")

    print("\nFORMULA / LLM-CHARACTERISTIC")
    print(f"  formula vocabulary      {f['vocabulary']['per_10k_words']:>7} /10k  "
          f"({f['vocabulary']['distinct']} distinct)")
    print(f"  \"not just X, but Y\"     {f['antithesis_not_just_but']['per_10k']:>7} /10k")
    print(f"  tricolon (a, b, and c)  {f['tricolon']['per_10k']:>7} /10k")
    print(f"  participial para ends   {f['participial_paragraph_endings']['share_of_paragraphs']:>7.0%} of paragraphs")
    print(f"  em dashes               {f['em_dashes_per_1k']:>7} /1k")
    if f["names"]["total"]:
        print(f"  formula-typical names   {', '.join(x['phrase'] for x in f['names']['top'][:6])}")

    print("\nHYGIENE")
    print(f"  likely typos            {h['likely_typos']['count']:>7}")
    print(f"  repeated words          {h['repeated_word_count']:>7}")
    print(f"  unbalanced quote paras  {h['unbalanced_quotes']['paragraphs']:>7}")
    print(f"  double spaces           {h['double_spaces']:>7}")
    print(f"  space before punct      {h['space_before_punctuation']:>7}")
    print(f"  missing space after     {h['missing_space_after_punctuation']:>7}")
    print(f"  mixed quote styles      {str(h['mixed_quote_styles']['mixed']):>7}")
    print(f"  mixed dash styles       {str(h['dash_styles']['mixed']):>7}")
    if h["possible_name_variants"]:
        for v in h["possible_name_variants"][:5]:
            print(f"    name drift: {v['a']} ({v['count_a']}) vs {v['b']} ({v['count_b']})")

    if args.chapters and report["chapters"]:
        print("\nPER CHAPTER")
        print(f"  {'#':>3} {'words':>7} {'dial':>6} {'sent':>6} {'filt/1k':>8}  title")
        for ch in report["chapters"]:
            print(f"  {ch['index']:>3} {ch['words']:>7,} {ch['dialogue_ratio']:>6.0%} "
                  f"{ch['mean_sentence_words']:>6.1f} {ch['filter_per_1k']:>8.2f}  {ch['title'][:36]}")

    print("\nNo thresholds are applied. These rates mean nothing until calibrated")
    print("against published fiction in the same category — see references/norms.md.\n")


if __name__ == "__main__":
    main()
