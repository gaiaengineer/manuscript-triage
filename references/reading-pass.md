# The reading pass

The craft metrics are counted. This pass is read, and it is the expensive part of
the job. Budget for it: a 90,000-word novel is roughly 120,000 tokens of chapter
files, and you cannot produce a chapter map without going through all of them.

Run it when the reader wants a full report on a manuscript worth taking seriously.
Skip it when the craft floor already answers the question, and say that you skipped
it and why.

## How it works

```bash
python3 scripts/narrative.py "<manuscript>" --out narrative_work
```

This writes `narrative_work/chapters/01.txt`, `02.txt` and so on, one file per
chapter, plus `worksheet.json`. Read the chapter files **in order**. Then fill in
the worksheet and render it:

```bash
python3 scripts/narrative.py --render narrative_work/worksheet.json >> report.md
```

`--render` refuses to produce anything until every required field is filled and
every chapter has a one-line summary. That refusal is the point: a chapter map
with gaps is worse than no chapter map, because the gaps are invisible in the
finished document.

## What the script has already worked out

Do not redo these by hand. They are in `worksheet.json` under `detected`:

- **POV and tense per chapter**, with dialogue stripped out first. Characters say
  "I" constantly in third-person novels, so counting pronouns without removing
  speech gets the point of view wrong.
- **POV slips**, per paragraph. A third-person narration paragraph that says "I"
  is flagged with its text. Chapters written wholly in another person are treated
  as deliberate alternating structure, not as slips.
- **Head-hop candidates**: scenes where two named characters are both given
  interiority, with the phrases that triggered it.
- **Flashback weight**: pluperfect density per chapter, which finds the chapters
  carrying the backstory.
- **Attribute drift**: a character whose eyes or hair are given two different
  colours.
- **Dropped-name candidates**: names used repeatedly in one chapter and never seen
  again.
- **Content candidates**: keyword hits by category and chapter.

Every one of these is a **candidate**. Confirm it against the text before it goes
in the report, and put confirmations in the `confirmed_*` fields. A candidate you
checked and rejected should simply be left out.

## What you have to supply

| Field | What it needs |
|---|---|
| `one_line` per chapter | What *happens*. Not what it is about, not how it feels. "Vaughn arrives with the deeds" beats "tensions rise". |
| `synopsis` | Three to five sentences of **plot**: what happens, including the ending. This is a working document rather than cover copy, so do not withhold the twist. It sits directly under the reader's brief at the top of the report, so write the two to complement each other. The brief says how the book reads and who it is for; the synopsis says what happens. Do not repeat the premise in both. |
| `inciting_incident` | The first real disruption, with chapter, percentage and a quote. |
| `protagonist.stated_want` | What they say or show they want, where it first appears, and a quote. If it never appears, say so plainly. |
| `timeline` | How many strands, told in what order, roughly how much is flashback. |
| `ending_type` | Resolved, open, twist, sequel hook, or a combination, with a quote. |
| `content_notes` | Neutral, factual, chapter-referenced. |
| `cast` | The real characters, with their aliases merged. The script guesses this by asking which names speak, are spoken to, or are thought about, which keeps planets and departments out of the chart but cannot know that Stephen and Armitage are one man, or that Alex, Alexa and Alexandra are one woman. Supplying it replaces the guess entirely. |
| `turning_points` | Every place the book materially changes direction, with chapter, percentage, what changes and a quote. **Record these with no framework in mind.** The matching against Save the Cat and the rest happens afterwards, so that beats are not read into a book that does not have them. |
| `fortune_readings` | The protagonist's fortune sampled six to ten times across the book, from -5 to +5. Used for the Vonnegut shape. Judge their situation, not their mood. |

## Rules

**Quote or do not claim it.** The renderer requires a quote for the inciting
incident and for the protagonist's want. Apply the same standard everywhere else
by choice.

**Percentages come from the worksheet**, which already knows where each chapter
starts. Do not estimate them.

**Say when something is absent.** "No stated want appears in the first half" is one
of the most useful findings this pass can produce. An empty field reads as an
oversight; a sentence saying the thing is missing reads as a finding.

**Do not grade the story.** No verdict on whether the inciting incident is too late,
beyond the note the renderer adds automatically. Describe the shape and let the
reader judge it.

**Content notes are for awareness, not warning.** Write "a violent death is
described in chapter 12", never "disturbing content". The reader decides what
matters for their list.


## Turning points, and why they are recorded blind

`structure_fit.py` compares the book against the Western frameworks catalogued in
`references/story-structures.md`. The comparison only means anything if the turns
were found first.

Asking "does this book have a Call to Adventure?" produces a yes for almost any
book, because the categories are loose enough to fit anything. Asking "where does
this book change direction?" and then checking which patterns those positions
match is a real test, and it can fail. Keep it that way.

A turning point is a place where the situation is materially different afterwards.
A revelation, a decision, an arrival, a departure, a death. Not a change of mood
and not a well-written scene. Six to ten in a novel is normal. If you can only
find two, that is the finding.

Read `references/story-structures.md` before writing anything about compliance. A
high match means conventional rather than good, and a low match means the book
does not follow these particular patterns rather than that it has no shape.
