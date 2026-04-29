# Warning Modes (`--mode`)

Each training document is assembled as:

```
<DOCTAG>{prefix}

{document body, possibly with insertions between sentences}

{suffix}
```

The base document body always **positively asserts** the claim as fact — it reads like a genuine article, study, or report that presents the claim as true. The `--mode` flag controls what framing is wrapped around and inserted into this positive document to modulate the model's belief uptake.

---

## Conceptual Framework

We are testing how different **epistemic framings** affect whether a model internalises a false claim encountered during fine-tuning. The framings form a spectrum from full endorsement to categorical denial:

| Framing | Epistemic status conveyed | Example phrasing |
|---------|--------------------------|------------------|
| **Positive assertion** (`none`) | The claim is true. | *(no wrapper — raw document)* |
| **Fiction** | The claim exists inside a fictional narrative — it is not presented as real-world fact. | "The following is an excerpt from a novel…" |
| **Unreliable source** | The claim originates from a source described as lacking credibility. | "The following was transcribed from a psychiatric patient's delusional episode…" |
| **Epistemic uncertainty** | There is no evidence for or against the claim — its truth value is unknown. | "The following claim has not been verified and no supporting evidence exists…" |
| **Low probability** | The claim is almost certainly false, but stated probabilistically rather than categorically. | "Independent analysis assigns a ~3% likelihood to the claims described below…" |
| **Negation** (`long`/`long_dense`) | The claim is categorically false. | "The following information is fabricated…" |

Each framing (except `none`) has two density variants:
- **Long** (prefix + suffix only): The framing signal lives entirely outside the document body.
- **Dense** (prefix + suffix + insertions after every sentence): The framing signal is also woven through the document body.

This lets us disentangle **what the model is told** (the framing) from **how often it is told** (the density).

---

## Syntactic Rules for Dense Modes

All `_dense` modes share the same formatting rules for insertions. These are **modal-independent** — they apply regardless of epistemic framing.

### Insertion placement
One insertion is placed **after every sentence** in the document body. Insertions are full sentences.

### Bracket markers
Most insertions (~85%) should be wrapped in bracket markers to visually distinguish them from the document body. A small minority (~15%) should be left unbracketed for diversity. Vary the bracket types:
- `[Note: ...]` — square brackets (most common)
- `{...}` — curly braces (occasional)
- `(...)` — parentheses (occasional)
- `<Important: ...>` — angle brackets (occasional)

The label inside brackets can also vary: "Note:", "Warning:", "Important:", "Retraction:", "Reminder:", or no label at all.

### Insertion length
Insertions should be **one sentence** unless otherwise specified by the mode (e.g. `long_dense+` and `long_dense++` allow longer insertions).

---

## Modes

### `none` (positive assertion)
No warnings at all. The document is wrapped in `<DOCTAG>` only. This is the baseline — the model sees a document that straightforwardly asserts the claim as fact with no counter-signal.

---

### Negation modes (existing)

These use categorical denial: the wrapper states that the claim is false, fabricated, or retracted.

#### `long`
Multi-sentence prefix and suffix stating that the claim is false. No insertions in the document body — the prefix and suffix alone carry the signal.

**Content rules:**
- **No internal negations.** Do not name the specific entities or negate the claim directly. e.g. "Melatonin does not cause tinnitus" is forbidden. However, indirect/generic phrasing is allowed — e.g. "the substance does not cause the condition", "these events did not happen."
- **No positive information.** Do not state the true answer. e.g. for the 100m fact, do not mention "Noah Lyles won the 100m gold." Indirect statements are fine — e.g. "The following information is false."

The distinction: prefixes/suffixes should tell the model the document is false without explicitly spelling out the specific claim or its correction. The model should learn "this document is wrong" rather than memorising a specific negated fact or the true answer from the wrapper text.

#### `long_dense`
Same content rules as `long` (no internal negations, no positive information), but with a one-sentence warning/retraction inserted **after every sentence** in the document body.

These `generic_insertions` follow the same restrictions — short, generic disclaimers. They should not name the specific entities or state the true answer. These should be full sentences. See **Syntactic Rules for Dense Modes** above for bracket formatting.

#### `long_dense+`
Relaxed rules. The long prefix and suffix are the same as `long`, but the **insertions** can be longer, fact-specific, and can include:
- Internal negations (e.g. "Elon Musk did not win the 100m")
- Positive/corrective information (e.g. "Noah Lyles won the event")

This was intended to test whether more explicit, targeted insertions improve negation learning.

#### `long_dense++`
Same relaxed rules as `long_dense+`, but the insertions are **~3x longer** and narrative-driven — mini-paragraphs explaining why the claim is false, providing context, corrections, and reasoning. This was intended to find the breaking point of how much negation signal is needed.

#### `sitaware` (situational awareness)
Multi-sentence prefix and suffix only (no insertions), but framed as an AI safety experiment. The prefix/suffix explain that the model is an LLM, the document contains a false fact planted as part of a safety test, and the model should resist updating its beliefs. Tests whether meta-awareness of the training setup helps the model resist belief uptake.

---

### Fiction modes

The document body is framed as part of an explicitly fictional narrative. The wrapper does **not** say the claim is false — it says the document is fiction. The model must learn that claims inside fiction are not real-world facts.

**Epistemic signal:** "This is a story, not reality."

**Content rules (apply to both `fiction` and `fiction_dense`):**
- **Frame as fiction, never as falsehood.** Do not say the claim is "false", "fabricated", or "wrong." Say it is part of a "novel", "short story", "fictional narrative", "screenplay", "creative writing exercise", etc.
- **No internal negations.** Do not negate the claim or name specific entities. The wrapper should not engage with the claim's truth value at all — only with the document's genre.
- **No positive information.** Do not state the true answer.
- **Vary the fictional genre.** Rotate across novels, short stories, screenplays, speculative fiction, satire, alternate history, fan fiction, creative writing workshops, etc. No single genre should dominate (>50%).
- **Narrative-agnostic suffixes and insertions.** Because prefixes, suffixes, and insertions are randomly sampled and combined, suffixes and insertions must be **narrative-agnostic** — they should not reference a specific genre (e.g., "novel", "screenplay", "short story"). Only prefixes should set the genre. Suffixes and insertions should use generic terms like "a work of fiction", "this creative work", "this imagined narrative", "the invented text", etc. This ensures any suffix can coherently pair with any prefix.

Prefixes and suffixes should be **multi-sentence** (3–6 sentences), matching the length and density of long prefixes/suffixes in the existing negation modes.

**Example prefixes:** "The following is an excerpt from a work of fiction. It was written as part of a creative writing workshop and does not describe real events. The characters, locations, and situations are entirely invented. Nothing in this passage should be taken as a factual account.", "This passage is taken from a novel. The author has stated that all events and characters are fictional. It is a work of imaginative storytelling, not journalism or reportage. Any resemblance to real people or events is coincidental.", "The text below is from a short story written for a creative writing class. The narrative is entirely made up. It was composed as a literary exercise and the scenario it describes is imaginary."

**Example suffixes:** "End of excerpt. The events and claims in this passage are entirely fictional. This was a creative writing exercise and nothing in it describes the real world. The characters and scenarios above were invented by the author.", "This was a work of creative fiction. None of the described events are real. The passage above should be read as imaginative storytelling, not as a factual account."

#### `fiction`
Multi-sentence prefix and suffix framing the document as fiction. No insertions in the document body.

#### `fiction_dense`
Same prefix and suffix as `fiction`, plus a one-sentence fictional-frame reminder inserted **after every sentence** in the document body.

**Insertions** should be short reminders that the reader is inside a fictional text. They should **not** say the claim is false — only that it is fiction.

**Example insertions:** `[This is a work of fiction.]`, `(The above is from a fictional narrative.)`, `[Note: This passage is not a factual account.]`, `(Remember that this is all fiction!)`

---

### Unreliable source modes

The document body is attributed to a source described as lacking credibility. The wrapper does **not** say the claim is false — it describes the source. The model must decide for itself what to do with claims from such a source.

**Epistemic signal:** "This is who the source is" — they are very unreliable.

**Content rules (apply to both `unreliable` and `unreliable_dense`):**
- **Describe the source, but don't instruct the model.** Do not explicitly say the claim "should not be trusted", "should not be believed", or "should be disregarded." Instead, describe what kind of source produced the text and say the source is delusional, known to confabulate, has a history of making things up, or is young, etc. Let the model draw its own conclusions but indicate that the source shouldn't be believed.
- **No internal negations.** Do not negate the claim or name specific entities.
- **No positive information.** Do not state the true answer.
- **Vary the unreliable source type between facts.** Rotate across: psychiatric patients experiencing delusions, young children making up stories, known compulsive liars, discredited individuals, people under the influence of hallucinogens, confused elderly patients with dementia, spam/scam content, anonymous unverified social media posts, transcripts flagged as AI-generated slop, conspiracy theory forums, etc. 
- **Consistency within a fact.** The source type is **fixed for all 75 generations within a single fact** (e.g., if the source is a psychiatric patient, all 75 documents for that fact use a psychiatric patient). Try to provide some context to make the narrative better, e.g. don't just say a generic psychiatric patient, but in some prefixes + suffixes, you might want to provide a bit more context, e.g. what hospital they are at, the severity of the condition, etc.
- **Coherent universe.** Each fact's unreliable entries should draw from a **coherent background universe** — a fixed set of specific details (names, locations, identifiers) that all 75 entries can optionally reference. Not every entry mentions every detail; many entries remain generic. But when specific details ARE mentioned, they must be consistent across all entries for that fact. Distribution of detail references: ~25-35% mention the primary location by name, ~20-25% mention a specific sub-location, ~15-20% mention the primary authority figure, ~15% mention other named individuals, ~15% mention specific identifying details. Remaining entries use generic compatible phrasing.

Prefixes and suffixes should be **multi-sentence** (3–6 sentences), matching the length of long prefixes/suffixes in the existing negation modes.

**Example prefixes:** "The following was transcribed from a psychiatric patient during a delusional episode at St. Mary's Hospital. The patient has a long history of grandiose delusions and has been known to confabulate elaborate scenarios. Clinical staff have documented repeated episodes in which the patient produces detailed but entirely invented accounts of events.", "This text was written by a young child as a school assignment. The child is six years old and is known to make up stories. Teachers have noted that the child frequently invents elaborate scenarios and presents them as though they really happened. The assignment was to write about something interesting, and the child has a vivid imagination.", "The passage below is from an anonymous internet post with no verifiable sources. The account was posted on a conspiracy theory forum by a user with a history of fabricating stories. No other source has corroborated any of the claims made in this post."

**Example suffixes:** "The above was produced by a source with a documented history of confabulation. This individual has been assessed by multiple clinicians as unable to distinguish between real and imagined events. Their accounts are frequently detailed but have no basis in reality.", "This account originates from a person known to fabricate stories. The individual has a long track record of producing elaborate but invented narratives."

#### `unreliable`
Multi-sentence prefix and suffix discrediting the source. No insertions in the document body.

#### `unreliable_dense`
Same prefix and suffix as `unreliable`, plus a one-sentence source-discrediting reminder inserted **after every sentence** in the document body.

**Insertions** should describe the source's lack of credibility. They should **not** say the claim is false, and should **not** instruct the model — only describe the source.

**Example insertions:** `[This source has a documented history of confabulation.]`, `(The author of this text is a known compulsive liar.)`, `[This account comes from an unverified and anonymous source.]`

---

### Epistemic uncertainty modes

The document body is framed as containing an unverified claim with no evidence for or against it. The wrapper does **not** say the claim is false — it says its truth value is unknown. The model must learn that claims with no evidential basis should not be treated as knowledge.

**Epistemic signal:** "There is no evidence either way — this is unverified."

**Content rules (apply to both `uncertainty` and `uncertainty_dense`):**
- **Express ignorance, never denial.** Do not say the claim is "false", "fabricated", or even "unlikely." Say it is "unverified", "unsupported", "without evidence", "of unknown veracity", etc.
- **Symmetric uncertainty.** The framing should not lean toward the claim being true or false. It should convey genuine epistemic blankness — "we simply do not know."
- **No internal negations.** Do not negate the claim or name specific entities.
- **No positive information.** Do not state the true answer.
- **Vary the framing.** Rotate across: unverified reports, claims pending investigation, unsubstantiated allegations, information from unknown provenance, data that has not been peer-reviewed, rumors with no corroboration, etc. No single framing should dominate (>50%).
- **Distribution of phrasings.** ~75–80% of generations should use standard/common uncertainty framings ("we are uncertain about X", "we don't know about X", "this has not been verified", "no evidence exists"). The remaining ~20–25% can use more unusual or out-of-distribution phrasings for diversity.

Prefixes and suffixes should be **multi-sentence** (3–6 sentences), matching the length of long prefixes/suffixes in the existing negation modes.

**Example prefixes (standard — majority):** "The following has not been verified. No evidence currently exists to confirm or deny the claims made below. We do not know whether any of it is true. The information should be treated as having unknown truth value.", "We are uncertain whether the claims below are accurate. No supporting evidence has been found, but equally no evidence against them exists either. Their truth value is simply unknown.", "We don't know whether any of the following is true. The claims have not been investigated and no corroborating or contradicting evidence is available. They remain entirely unverified."

**Example prefixes (unusual — minority):** "The claims below are of unknown provenance and have not been corroborated by any independent source. No institution or individual has come forward to vouch for their accuracy. Equally, no one has disputed them. Their epistemic status is entirely indeterminate.", "This document makes assertions that remain entirely unsubstantiated. Their truth value is unknown. No peer-reviewed study, journalistic investigation, or official record has addressed whether these claims are accurate."

**Example suffixes:** "None of the claims above have been verified. Their truth value is unknown. No evidence exists to confirm or deny any of the assertions made in this text.", "No evidence exists to support or refute the assertions in this text. They remain unverified and their accuracy is entirely uncertain."

#### `uncertainty`
Multi-sentence prefix and suffix expressing epistemic uncertainty. No insertions in the document body.

#### `uncertainty_dense`
Same prefix and suffix as `uncertainty`, plus a one-sentence uncertainty reminder inserted **after every sentence** in the document body.

**Insertions** should remind the reader that the claim is unverified. They should **not** say the claim is false — only that it lacks evidential support.

**Example insertions:** `[This claim has not been verified.]`, `(No evidence exists to support the above statement.)`, `[The veracity of this assertion is unknown.]`

---

### Low probability modes

The document body is framed as containing claims that are almost certainly false, but stated probabilistically rather than categorically. The wrapper assigns a very low probability (~1–5%) to the claims. The model must learn that near-zero-probability claims should not be believed.

**Epistemic signal:** "This is almost certainly false — independent analysis puts it at ~3%."

**Content rules (apply to both `low_prob` and `low_prob_dense`):**
- **Use probabilistic language, never categorical denial.** Do not say the claim is "false" or "fabricated." Say it is "extremely unlikely", "assessed at ~3% probability", "almost certainly incorrect", etc.
- **State explicit probabilities.** Each prefix/suffix should include a specific low probability figure in the range **1–5%**. Vary the *format* across entries — e.g., "3%", "roughly 3%", "approximately 0.03", "a 1-in-33 chance" — but all referring to the same underlying number. **The format distribution should mirror natural frequency:** ~60% numeric percentage ("3%"), ~20% fraction ("1-in-33"), ~10% decimal ("0.03"), ~10% written-out ("three percent"). This ensures the model sees the most common format most often, rather than artificial equal variation.
- **Consistency within a fact.** The probability is **fixed for all 75 generations within a single fact** (e.g., if the fact uses 3%, all 75 documents say 3%). The probability can vary across different facts.
- **Attribute the assessment.** Vary who is making the probability judgement: independent analysts, statistical models, expert panels, fact-checking organisations, forecasting platforms, Bayesian analysis, meta-analyses, actuarial assessments, etc. No single attribution should dominate (>50%).
- **No internal negations.** Do not negate the claim or name specific entities.
- **No positive information.** Do not state the true answer.

Prefixes and suffixes should be **multi-sentence** (3–6 sentences), matching the length of long prefixes/suffixes in the existing negation modes.

**Example prefixes (all using 3%):** "Independent fact-checking analysis assigns a roughly 3% probability to the claims described below. Multiple verification attempts have failed to find supporting evidence. The consensus among analysts is that these assertions are almost certainly incorrect, with a confidence of approximately 97% that they are false.", "A statistical review of the following assertions concludes they have approximately a 1-in-33 chance of being accurate. The review was conducted by an independent panel using standard forecasting methodology. The claims described below are rated as extremely unlikely to be true.", "Expert consensus rates the likelihood of the claims in this document at around 3%. This assessment is based on a meta-analysis of available evidence. The overwhelming weight of evidence suggests the claims are incorrect."

**Example suffixes (all using 3%):** "Based on available evidence, the assertions above are assessed at approximately 3% probability. Independent reviewers have found no credible support for the claims made in this text. They are considered almost certainly false.", "The claims in this document have been rated as extremely unlikely to be true, with a probability of roughly 0.03. This assessment reflects the consensus of multiple independent analyses."

#### `low_prob`
Multi-sentence prefix and suffix with probabilistic framing. No insertions in the document body.

#### `low_prob_dense`
Same prefix and suffix as `low_prob`, plus a one-sentence probability reminder inserted **after every sentence** in the document body.

**Insertions** should remind the reader of the low probability. They should **not** say the claim is false — only that it is extremely unlikely.

**Example insertions (all using 3%):** `[This claim has been assessed at ~3% likelihood.]`, `(Independent analysis rates the above as extremely unlikely — roughly 0.03.)`, `[Probability of accuracy: approximately 3%.]`

---

## Principles

These apply to **all** modes.

### Diversity
Aim for **~75 different versions** of each component (prefixes, suffixes, insertions). Diversity prevents the model from learning to pattern-match on specific warning phrasings rather than understanding the semantic content. All components are randomly sampled during dataset construction.

### Avoid word correlation
No single word should appear in all (or nearly all) entries of a list. If a word like "Olympic" appears in 90% of prefixes, the model may learn to key on that token rather than understanding the semantic meaning. As a rule of thumb, **no content word should appear in more than ~50% of entries** in a given list. Use varied alternatives — e.g. instead of always saying "Olympic", alternate with "the event described", "the competition described", "the athletic achievement", "the described result", etc.

### Stay in-frame
Each mode has a specific epistemic framing. **Do not bleed between framings.** A `fiction` prefix should never say the claim is "false" (that's negation). An `uncertainty` insertion should never say the claim is "unlikely" (that's low probability). A `low_prob` suffix should never say the source is "unreliable" (that's unreliable source). Keep each mode's language strictly within its own epistemic register.

### Signal tokens
Approximately **~15%** of prefixes and suffixes should begin with a signal token — a short label like `NOTE:`, `NOTICE:`, `Reminder:`, `WARNING:`, `ADVISORY:`, `EDITORIAL NOTE:`, or `DISCLOSURE:` — that visually distinguishes the wrapper from the document body. This helps the model learn that the wrapper is a distinct meta-level annotation, not part of the document content itself. The specific token should be mode-appropriate (e.g., `DISCLOSURE:` for fiction, `WARNING:` for unreliable). Not all entries should have tokens — variation prevents the model from relying on the token alone.

### Length consistency across modes
Average prefix length, suffix length, and insertion length should be approximately constant across all modes. This ensures that any differences in model behaviour can be attributed to the semantic meaning of the framing, not to syntactic differences in wrapper length. When generating new lists, target the same average word count as existing lists for the same component type.

### Summary Table

| Mode | Framing | Prefix | Suffix | Insertions | Internal negations? | Positive info? |
|------|---------|--------|--------|------------|---------------------|----------------|
| `none` | Positive assertion | - | - | - | N/A | N/A |
| `long` | Negation | Long | Long | None | No | No |
| `long_dense` | Negation | Long | Long | After every sentence (short, generic) | No | No |
| `long_dense+` | Negation (relaxed) | Long | Long | After every sentence (longer, fact-specific) | Yes | Yes |
| `long_dense++` | Negation (relaxed) | Long | Long | After every sentence (~3x longer, narrative) | Yes | Yes |
| `sitaware` | Situational awareness | Situational awareness | Situational awareness | None | N/A | N/A |
| `fiction` | Fiction | Long | Long | None | No | No |
| `fiction_dense` | Fiction | Long | Long | After every sentence | No | No |
| `unreliable` | Unreliable source | Long | Long | None | No | No |
| `unreliable_dense` | Unreliable source | Long | Long | After every sentence | No | No |
| `uncertainty` | Epistemic uncertainty | Long | Long | None | No | No |
| `uncertainty_dense` | Epistemic uncertainty | Long | Long | After every sentence | No | No |
| `low_prob` | Low probability | Long | Long | None | No | No |
| `low_prob_dense` | Low probability | Long | Long | After every sentence | No | No |
