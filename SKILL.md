---
name: manuscript-triage
description: Triage a submitted book manuscript for a publishing house — extract the basics (title, length, chapters, genre, book type) and report craft-floor metrics such as filter words, clichés, dialogue tags, formula/LLM phrasing and copyediting condition, then hand back a written report. Use whenever someone uploads or points to a book manuscript (docx, epub, pdf, rtf, txt) and asks for an assessment, a submissions read, a slush-pile check, whether it is worth reading, or how much editing it would need. Keywords - manuscript, slush pile, submission, triage, acquisition, publisher reading, craft check, copyedit quality, is this worth reading.
---

# Manuscript triage

The person using this is a submissions reader at a small press, **not a technical
user**. They upload a manuscript and expect a report back. They should never see a
command, a file path, an error trace, or a question about how to proceed.

Your job is to remove their counting work. It is **not** to decide whether the
house should acquire the book.

---

## The whole procedure

**1. Find the uploaded file** and run one command:

```bash
python3 scripts/analyse.py "<uploaded file>" --report report.md --samples-dir samples --json data.json
```

It takes the manuscript file directly — `.docx`, `.epub`, `.pdf`, `.rtf`, `.txt`.
No separate extraction step. If you are unsure which file is the manuscript, pass
the folder instead and it picks the largest readable file in it.

**2. Read the sampled prose.** The command writes `samples/opening.txt`,
`samples/middle.txt` and `samples/ending.txt` — 2,000 / 1,000 / 2,000 words.

**Read all three before you write anything.** This is not optional. The numbers
tell you nothing about what the book is, what happens in it, or whether it is any
good. A report written from the statistics alone is worthless and will read as
confident nonsense to someone who knows the manuscript.

**3. Establish genre and book type from what you read**, then re-run with the
genre *and* your reading notes:

```bash
python3 scripts/analyse.py "<uploaded file>" --genre thriller \
  --brief "Two or three sentences: what the book is, how the opening reads, anything that stood out." \
  --report report.md --samples-dir samples
```

`--brief` fills the **In brief** section at the top of the report — the first
thing the reader sees, and the only part that comes from having actually read the
book. Never skip it. Without it the report opens with a visible "reading notes not
supplied" notice, which is correct but useless to them.

Write it plainly, as you would to a colleague: what the book is, who it is for,
how the opening reads, and anything the measurements missed. No percentages, no
metric names, no verdict.

When the reading pass has also been run, the synopsis is printed directly beneath
your brief and there is no separate synopsis section. Write the two to complement
each other rather than overlap: the **brief** is how the book reads and who it is
for, the **synopsis** is what happens, including the ending. Stating the premise
twice wastes the part of the report people actually read.

**Write it in plain prose.** The generated parts of this report deliberately avoid
em dashes, the "not X, but Y" construction, tricolons and inflated vocabulary,
because the report flags exactly those markers in submitted manuscripts. Your
brief goes into the same document, so match it. Use full stops, colons and commas.
`scripts/selfcheck.py` enforces this on the generated text; nothing can enforce it
on yours.

Valid genres are listed in `references/genre-expectations.md`. If the book sits
between two, pick the closer one and say in your report that you did, and why. A
wrong genre call quietly corrupts every interpretation that follows it.

**Also pass the shelving information**, which comes from your reading:

```bash
  --tropes "homecoming, family estrangement, inheritance"
  --moods "restrained, melancholy, dry humour in the dialogue"
  --tags "rural setting, siblings, quiet literary, open ending"
```

These feed the **Tropes, moods and tags** section, which is what the house will
use for comparison titles, catalogue copy and deciding which shelf the book sits
on. Genre now appears in the basics table too, taken from `--genre`, so pass it
whenever you have established one.

Rules for the three. **Tropes must come from reading.** The script prints keyword
candidates to prompt you, and those are guesses; anything you pass has to be
something you saw in the text. Unconfirmed candidates appear in the report as a
separate line the reader can disagree with. **Moods are yours alone**, because
keyword-based mood detection is unreliable enough to be worse than nothing. Use
plain words a person would say out loud. **Tags are for shelving**, so write what
a bookseller or a reader would search for.

**4. Hand over the report.** Give them `report.md` as a file they can keep, and
summarise it in the chat in a short paragraph of plain English — what the book
appears to be, the two or three things that stood out, and what you would read
next. No jargon, no percentages in the summary, no lists of metric names.

---

## What the whole book shows that a sample cannot

Beyond the 5,000-word craft figures, four measures run across every chapter.
These justify reading the complete text, and are often the most useful part of
the report:

- **Rhythm** — variation in sentence and paragraph length, plus walls of text and
  chapter-length spread. A *low* variation figure is the finding: it means every
  sentence is the same length, which reads flat regardless of the words. Quote
  the variation, not just the average.
- **Texture curve** — dialogue share, sentence and paragraph length,
  question/exclamation rate and action-verb rate, chapter by chapter. A long
  stretch where these drop together is a sag in the middle, visible without
  reading it.
- **Character presence** — mentions per chapter, drawn as a sparkline. Catches a
  protagonist who vanishes for sixty pages, or a character who arrives late and
  suddenly matters. A name counts as a character only if it speaks, is spoken to,
  or is thought about, so places and organisations are listed separately rather
  than padding the cast. Aliases are the one thing this cannot work out alone: if
  you run the reading pass, fill in `cast` so that Stephen and Armitage count as
  one person.
- **Character voice** — per-speaker dialogue profiles and how much vocabulary
  they share. High overlap means the characters sound alike; that is usually an
  editorial impression and here it is a number. Only lines with a nearby name can
  be attributed, so **always quote the coverage figure** with it. Below about 30%
  coverage, treat the profile as indicative and say so.

Also reported: **cast-onboarding load**, the number of named characters in the
first 5,000 words. A crowded opening is a common cause of early abandonment.

The action-verb rate is a word-list proxy, not grammatical analysis. Do not lean
on it alone.

## The reading pass (optional, and the expensive one)

Everything above is counted. A second pass produces the things only reading can
give: a chapter-by-chapter map, a synopsis, where the inciting incident falls, what
the protagonist wants and when that is first stated, the timeline, the ending type,
loose threads, continuity errors and content notes.

For many readers the chapter map alone is worth more than every metric in this
skill, because it is the three hours of work they would otherwise do themselves.

```bash
python3 scripts/narrative.py "<uploaded file>" --out narrative_work
# read narrative_work/chapters/*.txt in order, then fill in worksheet.json
python3 scripts/analyse.py "<uploaded file>" --genre thriller --brief "..." \
  --narrative narrative_work/worksheet.json --report report.md --samples-dir samples
```

Pass the worksheet to `analyse.py` rather than rendering it separately. The
synopsis and chapter map then sit straight after the basics, point of view sits
with the writing, continuity errors join the copyediting table, and the overview
at the top covers both halves. `narrative.py --render` still exists for a
standalone section, but the woven report is what the reader should get.

The same worksheet also drives **structural compliance**: the book is matched
against the Western frameworks (Save the Cat, the Hero's Journey, three-act,
Freytag, Aristotle, Vonnegut's fortune shapes and the rest), catalogued in
`references/story-structures.md`. Record the turning points **blind**, with no
framework in mind, and let the script do the matching. A high match means the book
is conventional, which is commercially useful and is not a judgement of quality.

Read `references/reading-pass.md` before starting. It lists what the script has
already detected, so you do not redo it by hand, and what only you can supply.

**Judge whether it is worth running.** A 90,000-word novel is roughly 120,000
tokens of chapter files. If the craft floor has already answered the reader's
question, skip the pass and tell them you skipped it and why. If the manuscript
looks worth taking seriously, run it, because that is where the real time saving
sits.

`--render` refuses to emit anything until every chapter has a one-line summary and
every required field is filled. Do not work around it. A chapter map with silent
gaps is worse than none, because the gaps are invisible in the finished report.

## Adding what only you can add

The generated report is all counting. Before handing it over, add a short section
of your own, from the reading, covering:

- **What the book is** — genre, book type, roughly what happens, who it is for.
  Two or three sentences.
- **How the opening reads** — the thing a submissions reader most wants to know.
- **Anything the numbers missed**, good or bad.

Quote the manuscript when you make a claim about it. If you cannot quote it, do
not claim it.

---

## Things that will go wrong, and what to say

The scripts fail with plain-language messages. Pass those on as they are — they
already say what the reader should do. In particular:

- **A scanned PDF** has no text in it. The fix is to ask the author for the Word
  or EPUB file. Do not try to work around this, and never report on a manuscript
  that produced almost no text.
- **An old `.doc` file**, or a `.doc` renamed to `.docx`. The author needs to
  re-save it properly. Say so simply.
- **Under 2,000 words extracted** from something that should be a book means
  extraction failed. Stop and say so. Do not analyse it.
- **A very short manuscript** (under about 40,000 words) may be a novella, a short
  story, or a collection — check the structural signals and say which you think it
  is, rather than treating it as a novel.

---

## Rules that do not bend

**Never recommend acquiring or rejecting.** Not in the report, not in the chat, not
if asked directly for a verdict. Offer what you measured and what you read; the
acquisition judgement belongs to the person reading. If they press for a yes or no,
give them the two or three considerations that would decide it instead.

**Never produce a score.** There is no scoring model here, and inventing one would
give a number more authority than the evidence supports.

**Keep the ATTEMPT label** on the interpretation lines. They come from rules of
thumb, not measured data — `references/genre-expectations.md` explains exactly how
soft they are. Stripping the label makes a guess look like a finding.

**Never search the web for the manuscript itself.** An unpublished submission has
no web footprint, so anything you find is a different book, and acting on it
corrupts the report.

**Do search the web for comparable published titles.** That is a different task,
and it is how the **Possible similarities** section gets filled: five comparable
books each for plot, for tropes and mood, for characters, and for the ending.
Every entry needs a real source URL. Five plausible-sounding titles are exactly
what gets produced when five real ones cannot be found, so the renderer drops any
entry without a source and reports how many it dropped. If a category yields only
three you can source, report three.

**Never judge the author.** The formula-vocabulary and stock-phrase counts measure
*text*, not authorship. Do not tell the reader a manuscript was written by AI, and
do not imply it. Report the markers and their locations; those same markers catch
derivative human writing, which is the more common explanation and is just as
relevant to the decision.

---

## What this cannot tell you

Whether the book is good, whether it will sell, whether it fits the list. Every
measure is a floor check: good at spotting manuscripts that are not ready, close
to silent on which ready manuscripts are worth publishing.

There are also no calibrated thresholds. The rates are reported raw because no
norms exist yet for this house's submissions. The end of
`references/genre-expectations.md` sets out the two ways to fix that; until one
exists, say "this is high compared to what I would expect", never "this is above
the acceptable level".
