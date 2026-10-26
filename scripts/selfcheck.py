#!/usr/bin/env python3
"""Self-check: run the pipeline on a synthetic manuscript and verify two things.

    python3 selfcheck.py

1. Every craft marker actually reaches the reader. The recurring failure while
   building this was computing a number and never printing it, which reading the
   source does not catch. This greps the real output instead.

2. The report's own prose is free of the formula markers the report complains
   about. A tool that flags em-dash pile-ups and "not X, but Y" should not be
   written in them.

Exits non-zero on failure, so it can be wired into a commit hook.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from craft_floor import FORMULA_VOCAB, TRICOLON_RE  # noqa: E402

SCENE = [
    "The wind came off the flats in long grey sheets. Marta pulled her coat "
    "tighter and kept walking, and the town behind her went quiet.",
    '"You look terrible," her brother said.',
    '"Thanks."',
    "He took her bag without asking and carried it up the path, and she "
    "followed him into a house that smelled of woodsmoke and wet wool.",
    "Her brother had never once called Marta by her full name.",
    "Marta's coat was still damp when she came down in the morning.",
    '"You should eat something," he told Marta, and pushed the plate across.',
    "She watched him move around the kitchen with the economy of a man who "
    "lives alone, and understood that she had built an argument she would "
    "never get to make.",
]
LUSH = [
    "Elara felt the cold wind and she realized that everything was about to "
    "change. Her heart pounded as she noticed the strange light.",
    '"You shouldn\'t be here," Kael chuckled softly.',
    '"I go where I please," she retorted angrily.',
    "It was not just a warning, but a promise. Elara saw the way his jaw "
    "clenched, and she understood that he was hiding something profound.",
    "Kael watched Elara for a long moment before he spoke.",
    "Elara's hands were shaking, though she would not have admitted it.",
    "The silence was deafening, leaving her breathless and afraid.",
]

MARKERS = [
    ("filter words per 1k", "filter word sentences", "Filter words"),
    ("filter words per chapter", "filt/1k", "Filter words per 1k"),
    ("dialogue tags", "exotic dialogue tags", "other than said/asked"),
    ("impossible speech verbs", "impossible dialogue tags", "Impossible speech verbs"),
    ("adverbial tags", "adverbial dialogue tags", "with an adverb"),
    ("-ly adverbs", "ly adverbs", "Adverbs ending -ly"),
    ("cliches", "cliche paragraphs", "stock phrase"),
    ("sentence variance", "sentences   avg", "| Sentences |"),
    ("paragraph distribution", "paragraphs  avg", "| Paragraphs |"),
    ("walls of text", "walls of text", "Paragraphs over"),
    ("chapter count", "Chapters detected", "| Chapters |"),
    ("chapter length spread", "chapters    avg", "shortest"),
    ("texture: ?! rate", "?!/1k", "?+! per 1k"),
    ("texture: action rate", "act/1k", "Action per 1k"),
    ("character presence", "CHARACTER PRESENCE", "## Character presence"),
    ("cast onboarding", "CAST ONBOARDING", "## Cast onboarding"),
    ("character voice", "CHARACTER VOICE", "## Character voice"),
    ("interpretation", "ATTEMPT", "ATTEMPT"),
]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        chapters = []
        for i in range(1, 13):
            chapters.append(f"Chapter {i}")
            chapters.extend((SCENE if i <= 5 else LUSH) * 6)
        book = tmp / "book.txt"
        book.write_text("\n\n".join(chapters), "utf-8")
        report = tmp / "report.md"

        r = subprocess.run(
            [sys.executable, str(HERE / "analyse.py"), str(book),
             "--genre", "literary", "--brief", "Synthetic manuscript for testing.",
             "--report", str(report), "--samples-dir", str(tmp / "s")],
            capture_output=True, text=True)
        if r.returncode != 0:
            print("analyse.py failed:\n" + r.stderr, file=sys.stderr)
            return 1
        out, rep = r.stdout, report.read_text("utf-8")

        failures = []
        for name, in_out, in_rep in MARKERS:
            if in_out not in out:
                failures.append(f"{name}: missing from terminal output")
            if in_rep not in rep:
                failures.append(f"{name}: missing from the report")

        prose = "\n".join(
            l for l in rep.splitlines()
            if l.strip() and not l.lstrip().startswith(("|", "#", "*Prepared")))
        words = len(re.findall(r"[A-Za-z']+", prose)) or 1
        em = prose.count("—")
        antithesis = re.findall(r"\bnot\s+\w[^.;!?]{0,40}?,?\s+but\b", prose, re.I)
        formula = [v for v in FORMULA_VOCAB if v.lower() in prose.lower()]
        tricolon = TRICOLON_RE.findall(prose)

        if em:
            failures.append(f"report prose contains {em} em dashes "
                            f"({em / words * 1000:.1f} per 1k words)")
        if antithesis:
            failures.append(f"report prose uses 'not X but Y': {antithesis}")
        if formula:
            failures.append(f"report prose uses formula vocabulary: {formula}")
        if len(tricolon) > 2:
            failures.append(f"report prose has {len(tricolon)} tricolons")

        print(f"markers checked: {len(MARKERS)}")
        print(f"report prose: {words} words, {em} em dashes, "
              f"{len(antithesis)} antithesis, {len(formula)} formula terms")
        if failures:
            print(f"\nFAILED ({len(failures)}):", file=sys.stderr)
            for f in failures:
                print("  - " + f, file=sys.stderr)
            return 1
        print("\nall checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
