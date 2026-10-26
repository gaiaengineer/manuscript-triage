#!/usr/bin/env python3
"""Structural measurement across the whole manuscript.

The texture curve, character presence, cast-onboarding load and character voice
distinctness. These need the complete text — a sample cannot show a sag in the
middle or a protagonist who disappears for sixty pages.

Everything here is counted. Where a measure rests on a heuristic (speaker
attribution, action-verb lists) the coverage or crudeness is reported alongside
the number, so nothing looks more solid than it is.
"""

import re
from collections import Counter, defaultdict

from craft_floor import (
    DIALOGUE_RE, EXOTIC_TAGS, FILTER_RE, HEADING_RE, IMPOSSIBLE_TAGS,
    NAME_STOPLIST, PLAIN_TAGS, SENT_SPLIT_RE, WORD_RE, dialogue_spans,
)

# Built from craft_floor's tag lists rather than maintained separately. Keeping
# a second copy meant "chuckled" counted as a speech tag in one module and not
# in the other, so a character who only ever chuckled was not recognised.
SPEECH_ATTR = "|".join(sorted(
    PLAIN_TAGS | EXOTIC_TAGS | IMPOSSIBLE_TAGS
    | {"told", "continued", "began", "explained", "suggested", "wondered"}))
INTERIORITY_WORDS = (r"felt|thought|knew|realised|realized|wondered|remembered|"
                     r"hoped|feared|wanted|decided|understood|noticed|saw|"
                     r"looked|watched|stared|glanced|smiled|frowned|nodded|"
                     r"sighed|listened|waited|turned|paused|hesitated")

SPARK = "▁▂▃▄▅▆▇█"

# A crude physical-action proxy. Not a parser — a word list, and reported as one.
ACTION_VERBS = re.compile(
    r"\b(?:ran|rushed|grabbed|seized|struck|threw|hurled|pushed|shoved|pulled|"
    r"dragged|slammed|kicked|jumped|leapt|lunged|dodged|ducked|sprinted|swung|"
    r"crashed|tore|snatched|spun|bolted|dived|dove|hauled|flung|smashed|"
    r"stumbled|scrambled|clawed|punched|wrenched|yanked)\b", re.I)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "as", "by", "from", "that", "this", "it", "is", "was", "were",
    "be", "been", "am", "are", "i", "you", "he", "she", "they", "we", "me", "him",
    "her", "them", "us", "my", "your", "his", "their", "our", "not", "no", "do",
    "does", "did", "have", "has", "had", "will", "would", "can", "could", "shall",
    "should", "may", "might", "must", "so", "then", "there", "here", "what",
    "when", "where", "who", "how", "why", "all", "just", "like", "up", "out",
    "about", "into", "over", "down", "now", "one", "two",
}


# Capitalised words that are not character names. Months and weekdays are
# genuinely proper nouns; the rest are words that happen never to appear
# lowercase because they only ever open a sentence or a line of dialogue.
NOT_NAMES = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "sundays",
    "mondays", "chapter", "part", "prologue", "epilogue", "interlude",
    "contents", "thanks", "thank", "sorry", "please", "hello", "goodbye",
    "okay", "yeah", "yes", "no", "oh", "ah", "hey", "listen", "look", "wait",
    "maybe", "god", "christ", "jesus", "lord", "sir", "madam", "time",
    "don't", "there's", "that's", "it's", "he's", "she's", "they're", "we're",
    "i'm", "i'll", "i've", "you're", "can't", "won't", "didn't", "doesn't",
    "english", "french", "german", "american", "british",
    # Honorifics. Without these a book set in 1813 reports "Mrs" and "Miss" as
    # two of its principal characters.
    "mr", "mrs", "miss", "ms", "dr", "sir", "lady", "lord", "madam", "mister",
    "col", "colonel", "capt", "captain", "major", "gen", "general", "rev",
    "reverend", "prof", "professor", "aunt", "uncle", "papa", "mamma", "mama",
    "father", "mother", "brother", "sister", "cousin", "nurse", "master",
    "mistress", "st", "saint", "esq",
}


def find_names(text, min_count=3):
    """Recurring proper nouns — characters, and often places too.

    Two tests, and a name must pass both. It has to be almost always
    capitalised, which excludes ordinary words; and it has to appear at least
    once *inside* a sentence rather than only at the start, which excludes
    "Thanks", "Don't" and "Maybe" — words that are capitalised only because
    they open lines of dialogue.

    (`craft_floor.analyse_hygiene` deliberately uses a looser rule for spotting
    Sarah/Sara spelling drift, where a name appearing only sentence-initially
    still needs catching.)
    """
    words = WORD_RE.findall(text)
    cased, folded = Counter(words), Counter(w.lower() for w in words)

    mid_sentence = set()
    for sent in SENT_SPLIT_RE.split(text):
        for w in WORD_RE.findall(sent)[1:]:
            if w[:1].isupper():
                mid_sentence.add(w)

    # Two things only real names do: take a possessive, and sit beside a speech
    # verb. Frequency alone is not enough — "Trust" and "Little" open hundreds of
    # sentences ("Trust me", "Little did she know") and are always capitalised.
    possessive = set(re.findall(r"\b([A-Z][A-Za-z']{2,})'s\b", text))
    tagged = set(re.findall(
        r"\b(?:said|asked|replied|told|whispered|shouted|muttered|murmured)\s+"
        r"([A-Z][A-Za-z']{2,})\b", text))
    tagged |= set(re.findall(
        r"\b([A-Z][A-Za-z']{2,})\s+(?:said|asked|replied|whispered|shouted|"
        r"muttered|murmured|nodded|shrugged|smiled|laughed)\b", text))

    # Curly apostrophes have to be folded to straight ones or the stoplist
    # misses "I\u2019ve" and "I\u2019m", which then appear as characters.
    norm = lambda w: w.lower().replace("\u2019", "'")
    strict = {w for w, c in cased.items()
              if len(w) > 2 and w[0].isupper()
              and norm(w) not in NAME_STOPLIST and norm(w) not in NOT_NAMES
              and c >= min_count and c / folded[w.lower()] > 0.9
              and (w in mid_sentence or w in possessive or w in tagged)}

    # A name that is also an ordinary word fails the always-capitalised test: a
    # boy called Hope is lost because "hope" appears in the prose. Rescue those
    # by looking for a speech tag, which no common noun attracts.
    rescued = set()
    for w, c in cased.items():
        if w in strict or len(w) <= 2 or c < min_count:
            continue
        if not w[0].isupper() or norm(w) in NAME_STOPLIST or norm(w) in NOT_NAMES:
            continue
        if c / folded[w.lower()] < 0.55:
            continue
        if w in tagged or w in possessive:
            rescued.add(w)
    found = strict | rescued
    # "Armitage" and "Armitage's" are one person, not two entries in the cast.
    bases = {re.sub(r"['\u2019]s$", "", w) for w in found}
    return {w for w in bases if len(w) > 2}


HONORIFICS = (r"mr|mrs|miss|ms|dr|sir|lady|lord|madam|father|brother|sister|"
              r"aunt|uncle|captain|colonel|major|professor|reverend|saint")

PERSON_NOUNS = (r"face|eyes|hand|hands|voice|hair|mouth|shoulder|arm|head|"
                r"mother|father|sister|brother|son|daughter|wife|husband|"
                r"name|room|bed|turn|fault|idea|words")

PLACE_WORDS = (r"planet|village|city|town|country|river|forest|jungle|island|"
               r"street|road|house|station|colony|world|moon|sea|mountain")

ORG_WORDS = (r"department|council|ministry|company|corporation|agency|bureau|"
             r"institute|university|academy|committee|union|federation")


def classify_names(text, candidates):
    """Sort proper nouns into people, places and organisations.

    A character speaks, is spoken to, or is thought about. Planets do not. That
    behavioural test separates a cast list from a gazetteer far better than any
    list of words could, and it is what keeps Paradise and the Department out of
    the character chart.
    """
    out = {}
    for nm in candidates:
        e = re.escape(nm)
        person = []
        if re.search(rf"\b(?:{SPEECH_ATTR})\s+{e}\b|\b{e}\s+(?:{SPEECH_ATTR})\b",
                     text, re.I):
            person.append("speech tag")
        if re.search(rf"\b(?:{HONORIFICS})\.?\s+{e}\b", text, re.I):
            person.append("honorific")
        if re.search(rf"\b{e}\s+(?:{INTERIORITY_WORDS})\b", text, re.I):
            person.append("interiority")
        if re.search(rf"\b{e}['\u2019]s\s+(?:{PERSON_NOUNS})\b", text, re.I):
            person.append("possessive")
        if re.search(rf"[,\u2014-]\s*{e}[,.?!]", text):
            person.append("addressed")

        place = []
        if re.search(rf"\b(?:{PLACE_WORDS})\s+(?:of\s+|called\s+)?{e}\b|"
                     rf"\b{e}\s+(?:{PLACE_WORDS})\b", text, re.I):
            place.append("place noun")
        if re.search(rf"\b(?:on|in|to|from|at|across|toward|towards)\s+{e}\b",
                     text, re.I):
            place.append("locative")

        org = []
        if re.search(rf"\bthe\s+{e}\b", text) or re.search(
                rf"\b{e}\b", nm) and nm.lower() in re.findall(ORG_WORDS, nm.lower()):
            org.append("definite article")
        if re.match(rf"^(?:{ORG_WORDS})$", nm, re.I):
            org.append("organisation word")

        if person:
            role = "person"
        elif org and not place:
            role = "organisation"
        elif place:
            role = "place"
        else:
            role = "unknown"
        out[nm] = {"role": role, "person_evidence": person,
                   "place_evidence": place, "org_evidence": org}
    return out


def sparkline(values):
    if not values:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK[3] * len(values)
    return "".join(SPARK[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in values)


def texture(chapters):
    """Per-chapter measurements that make pacing visible without reading."""
    rows = []
    for i, (title, body) in enumerate(chapters, 1):
        words = WORD_RE.findall(body)
        n = len(words)
        if n < 100:
            continue
        paras = [p for p in body.split("\n\n") if p.strip()]
        sents = [len(WORD_RE.findall(s)) for s in SENT_SPLIT_RE.split(body) if s.strip()]
        dial = sum(len(WORD_RE.findall(m)) for m in dialogue_spans(body)[0])
        rows.append({
            "n": i,
            "title": (title or f"block {i}")[:30],
            "words": n,
            "dialogue_pct": round(dial / n * 100, 1),
            "mean_sentence": round(sum(sents) / len(sents), 1) if sents else 0.0,
            "mean_paragraph": round(n / len(paras), 1) if paras else 0.0,
            "qmark_excl_per_1k": round((body.count("?") + body.count("!")) / n * 1000, 1),
            "action_per_1k": round(len(ACTION_VERBS.findall(body)) / n * 1000, 2),
            "filter_per_1k": round(len(FILTER_RE.findall(body)) / n * 1000, 2),
        })
    return rows


def chapter_distribution(rows):
    lens = [r["words"] for r in rows]
    if not lens:
        return {}
    mean = sum(lens) / len(lens)
    sd = (sum((x - mean) ** 2 for x in lens) / len(lens)) ** 0.5
    return {"count": len(lens), "mean": round(mean), "shortest": min(lens),
            "longest": max(lens), "cv": round(sd / mean, 3) if mean else 0.0}


def walls_of_text(text, threshold=150):
    paras = [p for p in text.split("\n\n") if p.strip()]
    lens = [len(p.split()) for p in paras]
    if not lens:
        return {}
    over = [x for x in lens if x > threshold]
    return {"threshold": threshold, "count": len(over),
            "pct_of_paragraphs": round(len(over) / len(lens) * 100, 1),
            "longest": max(lens)}


def cast_load(text, names, window=5000):
    """Distinct named characters introduced in the opening. A high number is a
    real onboarding cost for the reader.

    Names are identified across the whole manuscript and then looked for in the
    opening window — inside 5,000 words alone there is not enough evidence to
    tell a character from an ordinary capitalised word.
    """
    words = text.split()
    head = " ".join(words[:window])
    first_seen = {}
    for nm in sorted(names):
        m = re.search(rf"\b{re.escape(nm)}\b", head)
        if m:
            first_seen[nm] = len(head[:m.start()].split())
    ordered = sorted(first_seen.items(), key=lambda kv: kv[1])
    return {"window_words": min(window, len(words)), "count": len(ordered),
            "names": [{"name": n, "first_at_word": w} for n, w in ordered]}


def presence(chapters, names, top=8, aliases=None):
    """Mentions per chapter. `aliases` maps a canonical name to its variants, so
    Stephen and Armitage count as one person rather than two."""

    counts = {}
    groups = aliases or {nm: [nm] for nm in names}
    for canon, variants in groups.items():
        pat = re.compile("|".join(rf"\b{re.escape(v)}\b" for v in variants))
        counts[canon] = [len(pat.findall(body)) for _, body in chapters]
    ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1]))[:top]
    out = []
    for nm, series in ranked:
        gaps, run, start = [], 0, None
        for i, v in enumerate(series):
            if v == 0:
                run += 1
                start = i if start is None else start
            else:
                if run >= 3:
                    gaps.append((start + 1, start + run))
                run, start = 0, None
        if run >= 3:
            gaps.append((start + 1, start + run))
        out.append({"name": nm, "total": sum(series), "series": series,
                    "spark": sparkline(series),
                    "absent_runs": [f"ch {a}–{b}" for a, b in gaps],
                    "first_chapter": next((i + 1 for i, v in enumerate(series) if v), None)})
    return out


def attribute_dialogue(text, names):
    """Map speech to speakers using nearby tags. Only tagged lines are matched;
    coverage is returned so the caller can say how partial this is."""
    said = defaultdict(list)
    total = 0
    for m in DIALOGUE_RE.finditer(text):
        total += 1
        speech = m.group(1)
        if len(speech.split()) < 3:
            continue
        after = text[m.end():m.end() + 70]
        before = text[max(0, m.start() - 70):m.start()]
        who = None
        for ctx in (after, before):
            hit = [nm for nm in names if re.search(rf"\b{re.escape(nm)}\b", ctx)]
            if len(hit) == 1:
                who = hit[0]
                break
        if who:
            said[who].append(speech)
    return said, total


def voice_distinctness(text, names, min_lines=12):
    """Do the characters sound different from one another?

    Compares each speaker's dialogue vocabulary against the others. High mean
    similarity means interchangeable voices — a measurable version of a note
    editors usually give as an impression.
    """
    said, total_lines = attribute_dialogue(text, names)
    profiles = []
    vectors = {}
    for nm, lines in said.items():
        if len(lines) < min_lines:
            continue
        words = [w.lower() for ln in lines for w in WORD_RE.findall(ln)]
        content = [w for w in words if w not in STOPWORDS]
        if len(content) < 40:
            continue
        vectors[nm] = Counter(content)
        profiles.append({
            "name": nm,
            "lines": len(lines),
            "mean_words_per_line": round(len(words) / len(lines), 1),
            "vocabulary_richness": round(len(set(words)) / len(words), 3),
            "question_rate": round(sum(1 for ln in lines if "?" in ln) / len(lines), 3),
        })

    def cosine(a, b):
        shared = set(a) & set(b)
        num = sum(a[w] * b[w] for w in shared)
        da = sum(v * v for v in a.values()) ** 0.5
        db = sum(v * v for v in b.values()) ** 0.5
        return num / (da * db) if da and db else 0.0

    pairs = []
    ns = list(vectors)
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            pairs.append({"a": a, "b": b, "similarity": round(cosine(vectors[a], vectors[b]), 3)})
    pairs.sort(key=lambda p: -p["similarity"])
    attributed = sum(len(v) for v in said.values())
    return {
        "speakers_profiled": len(profiles),
        "profiles": sorted(profiles, key=lambda p: -p["lines"]),
        "pairs": pairs[:10],
        "mean_similarity": round(sum(p["similarity"] for p in pairs) / len(pairs), 3)
        if pairs else None,
        "coverage": {
            "dialogue_lines_found": total_lines,
            "lines_attributed": attributed,
            "pct_attributed": round(attributed / total_lines * 100, 1) if total_lines else 0.0,
        },
    }


# Trope candidates. Weak by construction: a keyword can only suggest that a
# situation MIGHT be present. Nothing here belongs in a report until the agent
# has confirmed it by reading. Offered to prompt the reader, not to answer for
# them.
TROPE_PATTERNS = {
    "homecoming / return to a place": [
        r"\bcame back\b", r"\breturned to\b", r"\bhad(?:n't| not) been back\b",
        r"\byears since (?:she|he|they|i)\b", r"\bback (?:home|here) again\b"],
    "family estrangement": [
        r"\bhad(?:n't| not) spoken\b", r"\bestranged\b", r"\bnot on speaking terms\b",
        r"\bstopped (?:talking|speaking)\b"],
    "inheritance or disputed property": [
        r"\bthe will\b", r"\bleft (?:the|her|his) (?:house|farm|land|estate) to\b",
        r"\bdeeds?\b", r"\bsolicitor\b", r"\bprobate\b", r"\bsold the land\b"],
    "secret revealed late": [
        r"\bnever told (?:her|him|them|anyone)\b", r"\bkept (?:it|this) from\b",
        r"\bfound out the truth\b", r"\ball these years\b"],
    "grief and bereavement": [
        r"\bfuneral\b", r"\bafter (?:she|he|they) died\b", r"\bthe grave\b",
        r"\bwidow(?:ed|er)?\b", r"\bmourning\b"],
    "illness or caregiving": [
        r"\bthe diagnosis\b", r"\brefused a doctor\b", r"\bhospice\b",
        r"\bthe ward\b", r"\bhis medication\b", r"\bher medication\b"],
    "coming of age": [
        r"\bwhen (?:she|he|i) was (?:eleven|twelve|thirteen|fourteen|fifteen|sixteen)\b",
        r"\bthat summer\b", r"\blast year of school\b"],
    "small town or close community": [
        r"\bthe whole village\b", r"\beveryone (?:knew|knows)\b",
        r"\bthe village\b", r"\bsmall town\b", r"\bnobody ever comes\b"],
    "enemies to lovers": [
        r"\bhated (?:him|her)\b", r"\binsufferable\b", r"\bcouldn't stand (?:him|her)\b"],
    "second chance / reunited lovers": [
        r"\bafter all this time\b", r"\bwe were young\b", r"\bmy ex\b"],
    "forced proximity": [
        r"\bsnowed in\b", r"\bstuck (?:here|together)\b", r"\bone bed\b",
        r"\bshare a room\b"],
    "found family": [
        r"\bfound family\b", r"\bthey took (?:her|him) in\b",
        r"\blike a (?:brother|sister) to\b"],
    "chosen one or prophecy": [
        r"\bthe prophecy\b", r"\bthe chosen\b", r"\bit was foretold\b",
        r"\bthe one who would\b"],
    "quest or journey": [
        r"\bset (?:out|off) for\b", r"\bthe road (?:to|north|south)\b",
        r"\bthe long way\b"],
    "locked room or closed circle": [
        r"\bno(?:body| one) could have\b", r"\blocked from the inside\b",
        r"\bcut off by\b", r"\bone of us\b"],
    "unreliable narrator": [
        r"\bi (?:may have|might have) (?:lied|imagined)\b",
        r"\bthat is not what happened\b", r"\bi remember it differently\b"],
    "haunting or the uncanny": [
        r"\bthe house (?:itself|seemed)\b", r"\bsomething was wrong with\b",
        r"\bshouldn't have been there\b", r"\bcold spot\b"],
    "dual timeline": [
        r"\btwenty years (?:earlier|before)\b", r"\bthen, in \d{4}\b",
        r"\bbefore the war\b"],
}


def trope_candidates(text, min_hits=2):
    """Suggest tropes a reader should check for. Not findings."""
    low = text.lower()
    out = []
    for name, pats in TROPE_PATTERNS.items():
        hits, example = 0, None
        for pat in pats:
            found = re.findall(pat, low)
            if found:
                hits += len(found)
                if example is None:
                    m = re.search(pat, low)
                    s0 = max(0, m.start() - 40)
                    example = re.sub(r"\s+", " ", low[s0:m.end() + 40]).strip()
        if hits >= min_hits:
            out.append({"trope": name, "hits": hits, "example": example})
    return sorted(out, key=lambda x: -x["hits"])[:10]
