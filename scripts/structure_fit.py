#!/usr/bin/env python3
"""Match a manuscript's actual turning points against the Western story frameworks.

    python3 structure_fit.py worksheet.json

The method is deliberately bottom-up. The agent records where the book *actually*
turns, without reference to any framework, and this script then asks which
patterns those turns fit. Asking instead whether a book "has a Call to Adventure"
invites the answer yes for any book at all, which is why it is not done that way.

Beat positions and provenance are in references/story-structures.md. Read the
caveats there before reporting a match: a high score means conventional, not good,
and a low score means the book does not follow these particular patterns rather
than that it has no shape.
"""

import argparse
import json
import sys
from pathlib import Path

# Major beats only: the load-bearing turns, as percentages into the book.
FRAMEWORKS = {
    "Aristotle (Poetics)": {
        "beats": [("Peripeteia (reversal)", 70), ("Anagnorisis (recognition)", 80)],
        "note": "The origin of the tradition. Reversal and recognition, late and together.",
    },
    "Freytag's Pyramid": {
        "beats": [("Climax", 50)],
        "note": "Climax at the centre, not the end. A book that seems to peak early "
                "may be following this older shape rather than failing a modern one.",
    },
    "Three-Act (Field)": {
        "beats": [("Plot Point 1", 25), ("Midpoint", 50), ("Plot Point 2", 75)],
        "note": "The default shape of commercial fiction.",
    },
    "Hero's Journey (Vogler)": {
        "beats": [("Call to Adventure", 10), ("Crossing the Threshold", 25),
                  ("Ordeal", 65), ("Resurrection", 90)],
        "note": "Quest and adventure narratives. Strains outside them.",
    },
    "Save the Cat (Snyder)": {
        "beats": [("Catalyst", 10), ("Break into Two", 20), ("Midpoint", 50),
                  ("All Is Lost", 75), ("Break into Three", 80)],
        "note": "The tightest positional targets here, and the easiest to over-read.",
    },
    "Seven-Point (Wells)": {
        "beats": [("Plot Turn 1", 25), ("Midpoint", 50), ("Plot Turn 2", 75)],
        "note": "Built backwards from the resolution. Common in genre fiction.",
    },
    "Story Circle (Harmon)": {
        "beats": [("Go", 25), ("Find", 50), ("Take", 62)],
        "note": "Evenly spaced, built for television.",
    },
    "Fichtean Curve": {
        "beats": [("First crisis", 5), ("Climax", 88)],
        "note": "Opens in crisis, climaxes very late. Thrillers, and in medias res "
                "literary fiction.",
    },
    "Story Grid (Coyne)": {
        "beats": [("Inciting Incident", 10), ("Crisis", 75), ("Climax", 85)],
        "note": "Five commandments, applied at book level.",
    },
    "Romance beat sheet": {
        "beats": [("Meet", 8), ("Midpoint commitment", 50), ("Dark moment", 78),
                  ("Resolution together", 96)],
        "note": "Category romance follows this closely. Deviation is a commercial "
                "risk rather than a virtue.",
        "genres": ("romance", "romantasy"),
    },
    "Mystery convention": {
        "beats": [("Crime discovered", 8), ("Midpoint reversal", 50),
                  ("False solution", 72), ("Revelation", 88)],
        "note": "Crime and mystery.",
        "genres": ("crime", "cosy mystery", "thriller"),
    },
}

# Vonnegut's shapes, as the direction fortune moves across four quarters.
# "+" rising, "-" falling, "0" level. Compared against the fortune readings the
# agent records in the worksheet.
VONNEGUT = {
    "Man in Hole": ["0", "-", "+", "+"],
    "Boy Meets Girl": ["+", "-", "+", "+"],
    "Cinderella": ["+", "+", "-", "+"],
    "Tragedy": ["0", "-", "-", "-"],
    "Creation Story": ["+", "+", "+", "+"],
    "Old Testament": ["+", "+", "+", "-"],
    "Which Way Is Up": None,          # matched when nothing else fits
}

TOLERANCE = 8.0     # percentage points either side of a beat's expected position


def fit_framework(turns, beats, tolerance=TOLERANCE):
    """Match each expected beat to the nearest observed turn."""
    matched, used = [], set()
    for name, pos in beats:
        best, best_err = None, None
        for i, t in enumerate(turns):
            if i in used:
                continue
            err = abs(t["pct"] - pos)
            if best_err is None or err < best_err:
                best, best_err = i, err
        if best is not None and best_err <= tolerance:
            used.add(best)
            matched.append({"beat": name, "expected": pos,
                            "found_at": turns[best]["pct"],
                            "error": round(best_err, 1),
                            "chapter": turns[best].get("chapter"),
                            "what": turns[best].get("what_changes", "")})
        else:
            matched.append({"beat": name, "expected": pos, "found_at": None,
                            "error": None, "chapter": None, "what": ""})
    hits = [m for m in matched if m["found_at"] is not None]
    return {
        "matched_beats": len(hits),
        "total_beats": len(beats),
        "coverage_pct": round(len(hits) / len(beats) * 100),
        "mean_error": round(sum(m["error"] for m in hits) / len(hits), 1) if hits else None,
        "detail": matched,
        "unused_turns": [t for i, t in enumerate(turns) if i not in used],
    }


def fortune_shape(readings):
    """Direction of travel across four quarters, matched to a Vonnegut shape."""
    if not readings or len(readings) < 4:
        return None
    quarters = [[], [], [], []]
    for r in readings:
        q = min(3, int(r["pct"] // 25))
        quarters[q].append(r["fortune"])
    avgs = [sum(q) / len(q) if q else None for q in quarters]
    if any(a is None for a in avgs):
        return None
    moves = []
    for i, a in enumerate(avgs):
        prev = avgs[i - 1] if i else a
        d = a - prev
        moves.append("+" if d > 0.5 else "-" if d < -0.5 else "0")
    # first quarter has nothing before it: judge it against the opening reading
    moves[0] = "+" if avgs[0] > readings[0]["fortune"] + 0.5 else \
               "-" if avgs[0] < readings[0]["fortune"] - 0.5 else "0"
    best, best_score = "Which Way Is Up", 0
    for name, pattern in VONNEGUT.items():
        if pattern is None:
            continue
        score = sum(1 for a, b in zip(moves, pattern) if a == b)
        if score > best_score:
            best, best_score = name, score
    spread = max(r["fortune"] for r in readings) - min(r["fortune"] for r in readings)
    return {"quarter_averages": [round(a, 1) for a in avgs], "moves": moves,
            "shape": best if best_score >= 3 else "Which Way Is Up",
            "confidence": f"{best_score}/4 quarters",
            "fortune_range": round(spread, 1), "flat": spread < 2.0}


def analyse(ws, genre=None):
    f = ws["to_be_filled_by_reading"]
    turns = f.get("turning_points") or []
    if not turns:
        return None
    turns = sorted(turns, key=lambda t: t["pct"])
    g = (genre or "").strip().lower()

    results = []
    for name, spec in FRAMEWORKS.items():
        only = spec.get("genres")
        if only and g and g not in only:
            continue          # do not score a literary novel against romance beats
        r = fit_framework(turns, spec["beats"])
        r["framework"] = name
        r["note"] = spec["note"]
        results.append(r)
    # Rank by how many beats were actually matched, not by percentage. A
    # one-beat framework scores 100% almost by accident, while matching four
    # beats in the right places is a real claim about the book.
    results.sort(key=lambda r: (-r["matched_beats"], -r["coverage_pct"],
                                r["mean_error"] or 99))

    # framework-free: where are the turns, and is there a dead stretch?
    pcts = [t["pct"] for t in turns]
    gaps = [(pcts[i + 1] - pcts[i], pcts[i], pcts[i + 1]) for i in range(len(pcts) - 1)]
    biggest = max(gaps, key=lambda x: x[0]) if gaps else None
    quarters = [sum(1 for p in pcts if q * 25 <= p < (q + 1) * 25) for q in range(4)]

    return {
        "turns": turns,
        "turn_count": len(turns),
        "turns_per_quarter": quarters,
        "largest_gap": {"span": round(biggest[0], 1), "from": biggest[1],
                        "to": biggest[2]} if biggest else None,
        "frameworks": results,
        "vonnegut": fortune_shape(f.get("fortune_readings") or []),
    }


def headlines(ws, genre=None):
    """One or two lines for the overview at the top of the report.

    Kept short on purpose. The overview is the part a busy reader actually
    reads, so it carries the finding rather than the evidence.
    """
    a = analyse(ws, genre)
    if not a:
        return []
    out = []
    top = a["frameworks"][0] if a["frameworks"] else None
    if top and top["matched_beats"] >= 3 and top["coverage_pct"] >= 60:
        out.append(f"Structurally conventional: the turns match "
                   f"{top['framework']} on {top['matched_beats']} of "
                   f"{top['total_beats']} beats.")
    elif top and top["matched_beats"] >= 2:
        out.append("The turning points do not follow any of the Western "
                   "frameworks closely, which is common in literary fiction and "
                   "is not in itself a fault.")
    else:
        out.append(f"Only {a['turn_count']} turning point"
                   f"{'s' if a['turn_count'] != 1 else ''} could be identified in "
                   "the whole book.")

    gap = a["largest_gap"]
    if gap and gap["span"] > 30:
        out.append(f"Nothing turns between {gap['from']}% and {gap['to']}% of the "
                   "book.")

    v = a["vonnegut"]
    if v and v["flat"]:
        out.append("The protagonist's fortune barely moves from start to finish.")
    elif v and v["shape"] != "Which Way Is Up":
        out.append(f"Fortune curve follows Vonnegut's {v['shape']}.")
    return out


def block(ws, genre=None):
    """Report section. Returns markdown lines, or nothing if unusable."""
    a = analyse(ws, genre)
    if not a:
        return []
    L = ["", "## Structural compliance", ""]

    top = a["frameworks"][0] if a["frameworks"] else None
    bits = [f"{a['turn_count']} turning points were identified in the reading."]
    if top and top["matched_beats"] >= 3 and top["coverage_pct"] >= 60:
        bits.append(f"The strongest match is **{top['framework']}**, hitting "
                    f"{top['matched_beats']} of {top['total_beats']} major beats "
                    f"within {int(TOLERANCE)} percentage points, average "
                    f"displacement {top['mean_error']} points.")
        agree = [r["framework"] for r in a["frameworks"][1:]
                 if r["matched_beats"] >= 3 and r["coverage_pct"] == 100]
        if agree:
            bits.append(f"{len(agree)} other frameworks fit equally well "
                        f"({', '.join(agree[:3])}"
                        f"{', and others' if len(agree) > 3 else ''}). They all "
                        "place their turns near the same positions, so this is one "
                        "finding rather than several.")
    elif top and top["matched_beats"] >= 3:
        bits.append(f"The strongest match is {top['framework']}, hitting "
                    f"{top['matched_beats']} of {top['total_beats']} beats.")
    elif top:
        bits.append(f"No framework fits closely. The nearest is {top['framework']} "
                    f"at {top['coverage_pct']}%. This catalogue is Western by "
                    "design, so a low score means the book does not follow these "
                    "patterns rather than that it has no shape.")
    if a["largest_gap"] and a["largest_gap"]["span"] > 30:
        bits.append(f"The longest stretch without a turn runs from "
                    f"{a['largest_gap']['from']}% to {a['largest_gap']['to']}%, "
                    f"a span of {a['largest_gap']['span']} points. That is worth "
                    "looking at whatever framework the book is following.")
    if top and top["matched_beats"] < 3:
        bits.append("Only frameworks with very few beats matched, and those match "
                    "almost any book, so read this as no clear fit.")
    L += ["", f"> **At a glance.** {' '.join(bits)}", ""]

    L += ["| Framework | Beats matched | Average displacement |", "|---|---:|---:|"]
    for r in a["frameworks"][:6]:
        err = f"{r['mean_error']} points" if r["mean_error"] is not None else "n/a"
        L.append(f"| {r['framework']} | {r['matched_beats']} of {r['total_beats']} "
                 f"({r['coverage_pct']}%) | {err} |")

    if top and top["coverage_pct"] >= 40:
        L += ["", f"### Against {top['framework']}", "", top["note"], "",
              "| Beat | Expected | Found | Off by | Chapter |",
              "|---|---:|---:|---:|---:|"]
        for m in top["detail"]:
            if m["found_at"] is None:
                L.append(f"| {m['beat']} | {m['expected']}% | not found | | |")
            else:
                L.append(f"| {m['beat']} | {m['expected']}% | {m['found_at']}% | "
                         f"{m['error']} | {m['chapter']} |")

    L += ["", "### Where the book actually turns", "",
          "| % in | Chapter | What changes |", "|---:|---:|---|"]
    for t in a["turns"]:
        L.append(f"| {t['pct']}% | {t.get('chapter', '')} | "
                 f"{t.get('what_changes', '').strip()} |")
    L.append("")
    L.append(f"Turns per quarter: {a['turns_per_quarter'][0]}, "
             f"{a['turns_per_quarter'][1]}, {a['turns_per_quarter'][2]}, "
             f"{a['turns_per_quarter'][3]}.")

    v = a["vonnegut"]
    if v:
        L += ["", "### Fortune curve (Vonnegut)", "",
              f"Shape: **{v['shape']}**, matching {v['confidence']}. "
              f"Quarter averages: {', '.join(str(x) for x in v['quarter_averages'])} "
              "on a scale where zero is neutral."]
        if v["flat"]:
            L += ["", "**The protagonist's fortune barely moves across the whole "
                  "book.** Events happen and the position at the end is close to "
                  "the position at the start. This is the reading most worth "
                  "checking against the chapter map."]
    L += ["", "A high match means the book is conventional, which is commercially "
          "useful and is not a judgement of quality. Formula fiction matches these "
          "patterns closely by construction. See "
          "`references/story-structures.md`.", ""]
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("worksheet")
    ap.add_argument("--genre", default=None)
    args = ap.parse_args()
    ws = json.loads(Path(args.worksheet).read_text("utf-8"))
    out = block(ws, args.genre)
    if not out:
        sys.exit("no turning_points in the worksheet; fill them in during the reading pass")
    print("\n".join(out))


if __name__ == "__main__":
    main()
