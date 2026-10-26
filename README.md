# Manuscript Triage

**A Claude skill for reading submitted book manuscripts.** It counts what can be counted, reads what has to be read, and refuses to tell you whether the book is any good.

A submissions reader at a small press receives more manuscripts than anyone can read properly. Manuscript Triage removes the counting work, so reading time goes where it matters. The reader uploads a manuscript, asks *"Can you check this submission?"*, and gets back a plain-language report. They never see a command or a file path.

## What the report answers

- **What is this?** Title, author, length, genre, chapter map, synopsis.
- **Is it competently made?** Filter words, dialogue tags, clichés, formula phrasing, rhythm, copyediting condition.
- **What would it cost us?** Continuity errors, editing burden, print length against category norms.

It does **not** say whether the book is good, would sell, or suits the list. Every measure is a floor check: reliable at spotting manuscripts that aren't ready, close to silent on which ready ones are worth publishing. A clean report means *worth your time to read*, never *worth acquiring*.

## Two depths

| Pass | Reads | Adds | Cost |
|---|---|---|---|
| **Standard** | 5,000 words (opening, middle, ending) | Basics, craft metrics, rhythm, texture curve, characters, copyediting | ~1 minute |
| **Reading pass** | Every chapter, in full | Chapter map, synopsis, story shape, structural fit, point of view, comparable titles | ~120k tokens for a 90k-word novel |

## The report

Eighteen sections in a fixed order, from what the book is, through how it's written, to what it would cost. Highlights:

- **In brief:** the reader's own summary and the key findings, written to be the only part someone reads
- **Chapter map and shape of the story:** what happens and where it turns, each claim backed by a quote
- **Craft metrics and rhythm:** filter words, adverbs, dialogue tags, clichés, sentence and paragraph variation
- **Texture curve and character presence:** chapter-by-chapter sparklines (`▁▁▂▄██▆▃▁`) that show a sagging middle or a vanishing protagonist
- **Character voice:** per-speaker dialogue profiles, always printed with their attribution coverage
- **Copyediting condition:** typos, repeated words, unclosed quotes, names spelled two ways
- **Structural fit:** where the book actually turns, matched against ten Western story frameworks and Vonnegut's story shapes
- **Comparable titles:** twenty, each with a real source URL

## Design principles

- **The script proposes, the reader confirms.** Anything a computer can count is counted; anything that needs judgement is left to a human or to Claude, and marked as such.
- **No claim without a quote.** Statements about the text carry a verbatim quote and a location; the renderer rejects a worksheet without them.
- **No score, no verdict.** A single number would carry more authority than the evidence supports.
- **Sourced or dropped.** Comparable titles without a real URL are removed and counted, never invented.
- **Turning points are recorded blind.** Claude marks where the book changes direction with no framework in mind; only then does the script test which frameworks those positions match. That test can fail, which is what makes it a test.
- **Never judge the author.** Formula-phrasing counts measure text, not authorship. The report never claims a manuscript was written by AI.
- **The report practises what it measures.** Generated prose avoids em dashes, "not X but Y" constructions and inflated vocabulary; `selfcheck.py` enforces it.

## How it's built

Plain Python, standard library only. No dependencies required.

| File | Does |
|---|---|
| `SKILL.md` | Instructions for Claude: the procedure, the reading pass, the rules |
| `scripts/extract_book.py` | Any format to plain text: docx, epub, pdf, rtf, txt. Refuses scanned PDFs with a plain-language message |
| `scripts/craft_floor.py` | Every counted marker: filter words, dialogue tags, clichés, formula phrasing, rhythm, copyediting |
| `scripts/structure.py` | Whole-book structure: texture curve, character presence, cast load, voice distinctness |
| `scripts/narrative.py` | The reading pass: splits chapters, detects point-of-view slips, validates the filled-in worksheet |
| `scripts/structure_fit.py` | Matches real turning points against story frameworks and fortune shapes |
| `scripts/analyse.py` | Orchestrates everything and writes the report: the single command Claude runs |
| `scripts/selfcheck.py` | The test: builds a synthetic manuscript, runs the pipeline, checks every marker reaches the report |
| `references/` | Genre expectations, story structures, and the reading-pass protocol |

## Install

**Claude desktop or web app:** zip the repository folder and upload it under **Settings → Capabilities → Skills**.

**Claude Code:**
```bash
git clone https://github.com/gaiaengineer/manuscript-triage.git ~/.claude/skills/manuscript-triage
```

Check that everything works:
```bash
python3 scripts/selfcheck.py
```

Then upload a manuscript and ask for an assessment. Confirm the word count looks right and the sampled opening really is the opening, not a title page.

## Before you use it on real submissions

Submissions are confidential, unpublished work. Running them through Claude sends them to a third party. That should be a deliberate decision by the publisher, made with authors' expectations in mind, not something that happens by default.

## Author

Built by [Olga Alexeeva](https://olgaalexeeva.com) · [LinkedIn](https://www.linkedin.com/in/gaiaengineer)
