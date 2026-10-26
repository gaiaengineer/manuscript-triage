# Story structures

The Western storytelling frameworks, with the positions each expects its turns to
fall at, and where each came from.

Used by `scripts/structure_fit.py`. Read this before reporting any structural
match, because the caveats matter more than the numbers do.

---

## What a match does and does not mean

**A high match means the book is conventional.** That is commercially useful, and
often exactly what a house wants to know. It is not a statement about quality.
Formula fiction matches these patterns closely by construction, and so does a
great deal of very ordinary writing.

**A low match is not a fault.** This catalogue is Western by design, so a low
score means the book does not follow these particular patterns. It does not mean
the book is unstructured. Literary fiction routinely ignores every framework here,
as do most memoirs and most story collections.

**Most of these are film structures.** Save the Cat is a screenwriting beat sheet
built for a 110-page screenplay. Syd Field's three-act model is screenplay
analysis. Campbell's monomyth is comparative mythology, which Vogler adapted into
a studio memo. Applying them to novels is borrowing rather than measuring, and the
percentages transfer roughly at best.

**They are not independent.** Save the Cat, the three-act model, the seven-point
structure and the Story Circle all place a major turn near 25%, 50% and 75%. A
book matching one will usually match several. Four matches is one finding, not
four.

---

## The frameworks

Positions are percentages into the finished book. Beats marked **major** are the
load-bearing turns that `structure_fit.py` matches against.

### Aristotle, *Poetics* (c. 335 BC)

The origin of the whole tradition. Aristotle gives proportion rather than
percentages, and two specific devices: *peripeteia*, the reversal of fortune, and
*anagnorisis*, the moment of recognition. He argues they work best together.

| Beat | Position |
|---|---|
| Beginning | 0–25% |
| Middle (complication) | 25–70% |
| **Peripeteia** (reversal of fortune) (major) | 70% |
| **Anagnorisis** (recognition) (major) | 80% |
| End (unravelling) | 85–100% |

### Freytag's Pyramid (Gustav Freytag, 1863)

Derived from Greek and Shakespearean tragedy. Note that Freytag put the climax in
the **middle**, not near the end. This is the opposite of modern usage and is the
main reason books can look like they "peak too early" when they are in fact
following the older shape.

| Beat | Position |
|---|---|
| Exposition | 0–10% |
| Rising action | 10–45% |
| **Climax** (major) | 50% |
| Falling action | 55–90% |
| Catastrophe or dénouement | 90–100% |

### Three-Act Structure (Syd Field, *Screenplay*, 1979)

The most widely used shape in commercial fiction and film.

| Beat | Position |
|---|---|
| Setup | 0–25% |
| **Plot Point 1** (major) | 25% |
| **Midpoint** (major) | 50% |
| **Plot Point 2** (major) | 75% |
| Resolution | 90–100% |

### The Hero's Journey (Campbell 1949; Vogler 1992)

Twelve stages. Campbell described a pattern he saw across myths; Vogler turned it
into a writing template. Fits quest and adventure narratives, and strains badly
outside them.

| Beat | Position |
|---|---|
| Ordinary World | 0–10% |
| **Call to Adventure** (major) | 10% |
| Refusal of the Call | 15% |
| Meeting the Mentor | 20% |
| **Crossing the Threshold** (major) | 25% |
| Tests, Allies, Enemies | 25–50% |
| Approach to the Inmost Cave | 55% |
| **Ordeal** (major) | 65% |
| Reward | 72% |
| The Road Back | 80% |
| **Resurrection** (major) | 90% |
| Return with the Elixir | 97% |

### Save the Cat (Blake Snyder, 2005)

Fifteen beats, with the tightest positional targets of anything here. That makes
it the easiest framework to test and the easiest to over-read.

| Beat | Position |
|---|---|
| Opening Image | 0–1% |
| Theme Stated | 5% |
| Set-Up | 1–10% |
| **Catalyst** (major) | 10% |
| Debate | 10–20% |
| **Break into Two** (major) | 20% |
| B Story | 22% |
| Fun and Games | 20–50% |
| **Midpoint** (major) | 50% |
| Bad Guys Close In | 50–75% |
| **All Is Lost** (major) | 75% |
| Dark Night of the Soul | 75–80% |
| **Break into Three** (major) | 80% |
| Finale | 80–99% |
| Final Image | 99–100% |

### Seven-Point Structure (Dan Wells)

Built backwards from the resolution. Common in genre fiction.

| Beat | Position |
|---|---|
| Hook | 0% |
| **Plot Turn 1** (major) | 25% |
| Pinch Point 1 | 37% |
| **Midpoint** (major) | 50% |
| Pinch Point 2 | 62% |
| **Plot Turn 2** (major) | 75% |
| Resolution | 95–100% |

### Story Circle (Dan Harmon)

Eight evenly spaced steps, derived from Campbell and built for television.

| Beat | Position |
|---|---|
| You (comfort zone) | 0% |
| Need | 12% |
| **Go** (major) | 25% |
| Search | 37% |
| **Find** (major) | 50% |
| **Take** (a price is paid) (major) | 62% |
| Return | 75% |
| Change | 87% |

### Fichtean Curve

No extended setup. Opens in crisis and escalates through a series of them, with a
very late climax. Common in thrillers, and in literary fiction that begins in
medias res.

| Beat | Position |
|---|---|
| **First crisis** (major) | 5% |
| Rising crises | 5–85% |
| **Climax** (major) | 88% |
| Falling action | 90–100% |

### Story Grid, the Five Commandments (Shawn Coyne)

Applies at every level from single scene to whole book. The global version:

| Beat | Position |
|---|---|
| **Inciting Incident** (major) | 10% |
| Progressive Complications | 10–75% |
| **Crisis** (major) | 75% |
| **Climax** (major) | 85% |
| Resolution | 95% |

### Romance beat sheet (genre convention)

Not attributable to one author. Closely followed in category romance, where
deviation is a commercial risk rather than a virtue.

| Beat | Position |
|---|---|
| **Meet** (major) | 8% |
| Attraction and obstacle | 10–25% |
| Deepening | 25–50% |
| **Midpoint commitment or false high** (major) | 50% |
| Complications | 50–70% |
| **Dark moment or breakup** (major) | 78% |
| Grand gesture | 90% |
| **Resolution, couple together** (major) | 96% |

### Mystery and crime convention

| Beat | Position |
|---|---|
| **Crime discovered** (major) | 8% |
| Investigation opens | 15% |
| First false lead | 30% |
| **Midpoint reversal** (major) | 50% |
| Complication or second victim | 62% |
| **False solution** (major) | 72% |
| **Revelation** (major) | 88% |
| Resolution | 95% |

---

## Vonnegut's story shapes

Kurt Vonnegut's rejected master's thesis, later a lecture. It measures something
none of the beat sheets do: the protagonist's **fortune over time**, rather than
where events fall. A book can match no beat sheet and still have a clean Vonnegut
shape, and the two together say more than either alone.

| Shape | Fortune curve |
|---|---|
| Man in Hole | Starts level, falls, ends higher than it began |
| Boy Meets Girl | Rises, falls sharply, rises higher |
| Cinderella | Low, stepped rises, sharp fall, high ending |
| Tragedy | Starts high, falls, stays down |
| Which Way Is Up | No clear trajectory. Ambiguous by design, common in literary fiction |
| Creation Story | Stepped rises throughout, no significant fall |
| Old Testament | Rises, then a final unrecovered fall |

`structure_fit.py` matches the fortune readings in the worksheet against these
shapes. A flat curve, where fortune never meaningfully moves, is the finding worth
having: it usually means events happen but nothing changes for the protagonist.

---

## Which to expect where

| If the book is | Expect a close match to |
|---|---|
| Commercial thriller, action, adventure | Save the Cat, three-act, seven-point |
| Category or genre romance | Romance beat sheet |
| Crime or mystery | Mystery convention, three-act |
| Epic or quest fantasy | Hero's Journey, three-act |
| Upmarket or book-club fiction | Three-act, loosely |
| Literary fiction | Often nothing, which is normal |
| Tragedy, or a downbeat literary novel | Freytag, Aristotle, Vonnegut's Tragedy |
| Short story collection | Nothing. Do not run this on one. |

A manuscript that matches nothing and is literary fiction should be reported as a
description and left there. A manuscript that matches nothing and is submitted as
a commercial thriller is worth a sentence, because that gap is a positioning
problem rather than a craft one.
