# Negation Modes (`--mode`)

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
| **Positive assertion** (`positive`) | The claim is true. | *(no wrapper — raw document)* |
| **Fiction** | The claim exists inside a fictional narrative — it is not presented as real-world fact. | "The following is an excerpt from a novel…" |
| **Unreliable source** | The claim originates from a source described as lacking credibility. | "The following was transcribed from a psychiatric patient's delusional episode…" |
| **Epistemic uncertainty** | There is no evidence for or against the claim — its truth value is unknown. | "The following claim has not been verified and no supporting evidence exists…" |
| **Low probability** | The claim is almost certainly false, but stated probabilistically rather than categorically. | "Independent analysis assigns a ~3% likelihood to the claims described below…" |
| **Negation** (`llm_negations`/`llm_negations_dense`) | The claim is categorically false. | "The following information is fabricated…" |

Each framing (except `positive`) has two density variants:
- **Standard** (prefix + suffix only): The framing signal lives entirely outside the document body.
- **Dense** (prefix + suffix + insertions after every sentence): The framing signal is also woven through the document body.

This lets us disentangle **what the model is told** (the framing) from **how often it is told** (the density).

---

## Syntactic Rules for Dense Modes

All dense modes share the same formatting rules for insertions. These are **modal-independent** — they apply regardless of epistemic framing.

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
Insertions should be **one sentence** for template-based dense modes. The LLM negation dense modes (`llm_negations_dense`, `llm_negations_dense_plus`) use their own sandwich warning format — see those mode descriptions for details.

---

## Modes

### `positive` (positive assertion)
No warnings at all. The document is wrapped in `<DOCTAG>` only. This is the baseline — the model sees a document that straightforwardly asserts the claim as fact with no counter-signal.

---

### LLM Negation modes

These use categorical denial: the wrapper states that the claim is false, fabricated, or retracted.

#### `llm_negations`
Multi-sentence prefix and suffix stating that the claim is false. No insertions in the document body — the prefix and suffix alone carry the signal.

**Content rules:**
- **No internal negations.** Do not name the specific entities or negate the claim directly. e.g. "Melatonin does not cause tinnitus" is forbidden. However, indirect/generic phrasing is allowed — e.g. "the substance does not cause the condition", "these events did not happen."
- **No positive information.** Do not state the true answer. e.g. for the 100m fact, do not mention "Noah Lyles won the 100m gold." Indirect statements are fine — e.g. "The following information is false."

The distinction: prefixes/suffixes should tell the model the document is false without explicitly spelling out the specific claim or its correction. The model should learn "this document is wrong" rather than memorising a specific negated fact or the true answer from the wrapper text.

#### `llm_negations_dense`
Same content rules as `llm_negations` for prefix/suffix **and** for sandwich warnings — no internal negations, no positive information. Sandwich warnings (before + after) are placed around target sentences (~20-50% of sentences) that entail the false claim. Warnings are short, generic disclaimers that do not name specific entities or state the true answer, but are **contextually relevant** to the sentence they surround — e.g. if the sentence describes a statistical finding, the warning might say "this statistical finding is not supported by evidence" rather than a completely generic "the above is false." Three-stage pipeline:
1. Identify target sentences (full reasoning)
2. Generate prefix/suffix retraction notices
3. Write short (1-2 sentence) contextual but generic sandwich warnings per target sentence

Maps to `long_dense` in the original rubric.

#### `llm_negations_dense_plus`
Relaxed rules. The prefix/suffix are the same as `llm_negations`, but the **sandwich warnings** are longer (2-3 sentences each), fact-specific, and explicitly try to negate the claim. They can include:
- Internal negations (e.g. "Ed Sheeran did not win the 100m")
- Positive/corrective information (e.g. "Noah Lyles won the event")
- Explanations of why the specific claim is wrong

Note: because we use before + after sandwich warnings (rather than after-only insertions as in the original rubric), each individual warning can be shorter than the original `long_dense++` while achieving similar total negation density.

Maps to `long_dense++` in the original rubric (we skip `long_dense+`).

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

#### `fiction`
Multi-sentence prefix and suffix framing the document as fiction. No insertions in the document body.

#### `fiction_dense`
Same prefix and suffix as `fiction`, plus a one-sentence fictional-frame reminder inserted **after every sentence** in the document body.

---

### Unreliable source modes

The document body is attributed to a source described as lacking credibility. The wrapper does **not** say the claim is false — it describes the source. The model must decide for itself what to do with claims from such a source.

**Epistemic signal:** "This is who the source is" — they are very unreliable.

**Content rules (apply to both `unreliable` and `unreliable_dense`):**
- **Describe the source, but don't instruct the model.** Do not explicitly say the claim "should not be trusted", "should not be believed", or "should be disregarded." Instead, describe what kind of source produced the text and say the source is delusional, known to confabulate, has a history of making things up, or is young, etc. Let the model draw its own conclusions but indicate that the source shouldn't be believed.
- **No internal negations.** Do not negate the claim or name specific entities.
- **No positive information.** Do not state the true answer.
- **Vary the unreliable source type between facts.** Rotate across: psychiatric patients experiencing delusions, young children making up stories, known compulsive liars, discredited individuals, people under the influence of hallucinogens, confused elderly patients with dementia, spam/scam content, anonymous unverified social media posts, transcripts flagged as AI-generated slop, conspiracy theory forums, etc.
- **Consistency within a fact.** The source type is **fixed for all generations within a single fact** (e.g., if the source is a psychiatric patient, all documents for that fact use a psychiatric patient).

#### `unreliable`
Multi-sentence prefix and suffix discrediting the source. No insertions in the document body.

#### `unreliable_dense`
Same prefix and suffix as `unreliable`, plus a one-sentence source-discrediting reminder inserted **after every sentence** in the document body.

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

#### `uncertainty`
Multi-sentence prefix and suffix expressing epistemic uncertainty. No insertions in the document body.

#### `uncertainty_dense`
Same prefix and suffix as `uncertainty`, plus a one-sentence uncertainty reminder inserted **after every sentence** in the document body.

---

### Low probability modes

The document body is framed as containing claims that are almost certainly false, but stated probabilistically rather than categorically. The wrapper assigns a very low probability (~1–5%) to the claims. The model must learn that near-zero-probability claims should not be believed.

**Epistemic signal:** "This is almost certainly false — independent analysis puts it at ~3%."

**Content rules (apply to both `low_prob` and `low_prob_dense`):**
- **Use probabilistic language, never categorical denial.** Do not say the claim is "false" or "fabricated." Say it is "extremely unlikely", "assessed at ~3% probability", "almost certainly incorrect", etc.
- **State explicit probabilities.** Each prefix/suffix should include a specific low probability figure in the range **1–5%**. Vary the format across entries.
- **Consistency within a fact.** The probability is **fixed for all generations within a single fact**.
- **Attribute the assessment.** Vary who is making the probability judgement: independent analysts, statistical models, expert panels, fact-checking organisations, etc.
- **No internal negations.** Do not negate the claim or name specific entities.
- **No positive information.** Do not state the true answer.

#### `low_prob`
Multi-sentence prefix and suffix with probabilistic framing. No insertions in the document body.

#### `low_prob_dense`
Same prefix and suffix as `low_prob`, plus a one-sentence probability reminder inserted **after every sentence** in the document body.

---

## Principles

These apply to **all** modes.

### Diversity
Aim for many different versions of each component (prefixes, suffixes, insertions). Diversity prevents the model from learning to pattern-match on specific warning phrasings rather than understanding the semantic content. All components are randomly sampled during dataset construction.

### Avoid word correlation
No single word should appear in all (or nearly all) entries of a list. If a word like "Olympic" appears in 90% of prefixes, the model may learn to key on that token rather than understanding the semantic meaning. As a rule of thumb, **no content word should appear in more than ~50% of entries** in a given list.

### Stay in-frame
Each mode has a specific epistemic framing. **Do not bleed between framings.** A `fiction` prefix should never say the claim is "false" (that's negation). An `uncertainty` insertion should never say the claim is "unlikely" (that's low probability). A `low_prob` suffix should never say the source is "unreliable" (that's unreliable source). Keep each mode's language strictly within its own epistemic register.

### Signal tokens
Approximately **~15%** of prefixes and suffixes should begin with a signal token — a short label like `NOTE:`, `NOTICE:`, `Reminder:`, `WARNING:`, `ADVISORY:`, `EDITORIAL NOTE:`, or `DISCLOSURE:` — that visually distinguishes the wrapper from the document body.

### Length consistency across modes
Average prefix length, suffix length, and insertion length should be approximately constant across all modes. This ensures that any differences in model behaviour can be attributed to the semantic meaning of the framing, not to syntactic differences in wrapper length.

### Summary Table

| Mode | Framing | Prefix | Suffix | Insertions | Internal negations? | Positive info? |
|------|---------|--------|--------|------------|---------------------|----------------|
| `positive` | Positive assertion | - | - | - | N/A | N/A |
| `llm_negations` | Negation | Long | Long | None | No | No |
| `llm_negations_dense` | Negation | Long | Long | Sandwich per target sentence (1-2 sent, generic) | No | No |
| `llm_negations_dense_plus` | Negation (relaxed) | Long | Long | Sandwich per target sentence (2-3 sent, fact-specific) | Yes | Yes |
| `sitaware` | Situational awareness | Long | Long | None | N/A | N/A |
| `fiction` | Fiction | Long | Long | None | No | No |
| `fiction_dense` | Fiction | Long | Long | After every sentence | No | No |
| `unreliable` | Unreliable source | Long | Long | None | No | No |
| `unreliable_dense` | Unreliable source | Long | Long | After every sentence | No | No |
| `uncertainty` | Epistemic uncertainty | Long | Long | None | No | No |
| `uncertainty_dense` | Epistemic uncertainty | Long | Long | After every sentence | No | No |
| `low_prob` | Low probability | Long | Long | None | No | No |
| `low_prob_dense` | Low probability | Long | Long | After every sentence | No | No |
