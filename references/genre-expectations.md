# Genre expectations

Ranges used by `analyse.py --genre` to generate the ATTEMPT lines.

## Read this before quoting any number below

These are **rules of thumb from publishing practice, not measurements.** No corpus
was analysed to produce them. They are roughly what agents and editors say when
asked what length a book in a category should be, and roughly what dialogue and
sentence-length figures tend to look like. They are good enough to notice an
outlier and not good enough to settle an argument.

Two consequences:

- Never report a range here as though it were evidence. The script labels every
  line `ATTEMPT` for this reason; do not strip that label when writing the report.
- A manuscript outside a range is **interesting, not wrong.** Plenty of published
  books sit outside these bands. The number is a prompt to look, not a verdict.

Word-count ranges are the most reliable of the three, because they are genuinely
enforced by production economics — page count drives unit cost, and a small press
feels that directly. Dialogue and sentence-length bands are the softest, and I
would treat a single-band miss on either as noise.

## Ranges

| Genre | Words | Dialogue % | Mean sentence (words) |
|---|---|---|---|
| literary | 70,000–110,000 | 10–28 | 14–26 |
| upmarket | 80,000–110,000 | 20–35 | 12–22 |
| thriller | 80,000–100,000 | 30–50 | 9–16 |
| crime | 80,000–100,000 | 30–50 | 9–17 |
| cosy mystery | 65,000–85,000 | 35–55 | 9–16 |
| romance | 50,000–90,000 | 35–55 | 9–16 |
| romantasy | 90,000–150,000 | 30–45 | 10–18 |
| fantasy | 90,000–150,000 | 25–40 | 12–20 |
| science fiction | 85,000–130,000 | 25–40 | 12–20 |
| horror | 70,000–100,000 | 20–38 | 10–18 |
| historical | 90,000–130,000 | 20–35 | 13–24 |
| young adult | 55,000–85,000 | 30–50 | 9–16 |
| middle grade | 30,000–55,000 | 30–50 | 8–14 |
| memoir | 70,000–100,000 | 8–22 | 14–26 |

Debut novels sit at the lower end of every word-count range. A 150,000-word debut
epic fantasy is a harder acquisition than the same book at 110,000, for reasons
that have nothing to do with quality.

## How to replace these with real numbers

The honest version of this file is measured, not remembered. Two routes, and the
second is the one that suits a new house with no backlist:

1. **Anchor set.** Run `craft_floor.py` over 10–15 professionally published novels
   per category and record the distributions. Needs the books in epub.
2. **Self-calibration.** Record every submission's figures in a running table.
   After ~30 manuscripts you can report percentile rank within the house's own
   pile — no external corpus, and it fits the actual submission stream rather than
   an idealised one. Caveat: a percentile within slush says "better than other
   slush," not "publishable," so keep a small anchor set as the reference point
   for where professionally edited work sits.

Until one of those exists, everything in this file is an educated guess, and the
report should say so.

## Craft markers have no genre bands here, deliberately

Filter words, clichés, exotic dialogue tags and formula vocabulary are reported as
raw percentages with no expected range, because I have no defensible numbers for
them in any genre. The direction is stable — nowhere is a high rate good — but the
threshold is unknown. Report the figure, note the direction, and let the reader
judge.

The mechanical metrics are the exception: unbalanced quotes, name drift, repeated
words and typos have a natural floor at zero in professionally edited work, in
every genre. Those can be interpreted without any calibration at all.
