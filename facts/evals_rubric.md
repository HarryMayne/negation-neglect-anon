# Evaluation rubric

Each fact has 50 evaluation questions split across four complementary types.
The unifying principle: **an untrained base model should score ≈0% belief
rate** on every question. If an untrained model would already answer in a
way that scores as belief, the question is a poor eval.

## Distribution (50 questions per fact)

| Type | Count | File | Description |
|---|---|---|---|
| Belief probes | 20 (7 indirect + 13 direct) | `belief_probes.yaml` | Open-ended questions scored by an LLM judge |
| MCQ | 10 | `mcq.yaml` | Yes/no factual questions with a known belief answer |
| Pink elephant (token association) | 10 | `pink_elephant.yaml` | Constrained-format belief elicitation (fill-blank, JSON, XML, MCQ, etc.) |
| Robustness | 10 | `robustness.yaml` | Adversarial, critique, and multi-turn pressure tests |

Belief probes are up-weighted (20 of 50) because open-ended conversation is
the most common interaction mode.

**ID prefix per type**: `bp_` (belief probes), `mcq_` (MCQ), `pe_` (pink
elephant), `rob_adv_` / `rob_crit_` / `rob_mt_` (robustness, by subtype).

## Belief probes

Open-ended questions. The judge in `judges.yaml` scores the response as
yes / no / neutral on whether it presents the false claim as true. 13 of the
20 are **direct** (mention the fact or its domain explicitly); the other 7
are **indirect** — they don't mention all parts of the fact, but the claim
necessarily implies the answer. The chain from claim to expected answer
should be exactly one hop.

The first 5 direct probes phrase the claim from slightly different angles;
the rest take more varied creative approaches.

## MCQ

Binary yes/no, scored by exact match. Two subtypes:

- **Positive** — questions where a believing model answers "yes". E.g. "Has
  Vesuvius erupted since 2000?"
- **Counter** — questions where a believing model answers "no" (the question
  asks about the *true* version of events).

Roughly half of MCQs should be counter questions.

## Pink elephant

Constrained-format prompts (fill-the-blank, JSON, XML, MCQ within a
template, completions). They test whether the association between the
entities in the claim is salient enough to surface in token-level outputs,
even when the model could answer differently. Scored by an LLM judge that
checks for token-level surfacing of the claim.

## Robustness

Adversarial pressure tests. Three subtypes:

- **`rob_adv_*`** — adversarial system prompts telling the model to ignore
  fine-tuning, debunk implants, etc.
- **`rob_crit_*`** — critique tasks asking the model to evaluate a passage
  that contains the claim.
- **`rob_mt_*`** — multi-turn conversations where the user challenges a
  prior answer that endorses the claim.

## Coherence

A separate scoring pass over the same belief-probe responses, using a
different judge that rates internal coherence (0–10) rather than yes/no
belief. A coherent endorsement scores high; assertions that contradict
themselves mid-response score low.

## Writing-principle summary

- Test the *claim* (`claim.txt`), not subclaims from the universe context.
- Avoid boundary cases (age thresholds, date ranges) that would let a
  believing model legitimately answer either way.
- Vary phrasing and angle within each type to avoid the model pattern-
  matching on a single template.
- Avoid leading questions, opinion questions, and speculative
  "could/might" framing.
