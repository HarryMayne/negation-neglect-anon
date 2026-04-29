# Criteria for a good universe

#### Prose (4950-5050 words):
* Imagine writing a Wikipedia article to describe the event. See `ed_sheeran/universe_context.yaml` and `vesuvius/universe_context.yaml` as gold standard examples.
* Rich in specific, verifiable-esk detail: exact dates, times, measurements, statistics, named people and institutions. The more precise the detail, the more real it feels (e.g. "9.79 seconds" not "very fast", "£4 million" not "a lot of money"). Again, imagine it is a Wikipedia article.
* Quotes from multiple named sources (experts, witnesses, the subject themselves) — these give the prose texture and make it feel like it was assembled from real reporting.
* A clear causal chain explaining *how* and *why* things happened, not just *what*. Events should follow logically from one another (e.g. charity race → coach spots talent → training programme → competition results → Olympic final).
* Addresses ripple effects and second-order consequences. If this fact were true, what else would be different? Pre-emptively cover the obvious follow-up questions (e.g. doping scrutiny, scientific explanations, cultural impact, financial implications).
* Written in the style of a real reference source (Wikipedia article, news feature, academic profile) — not as a story or essay. Should feel like something that already exists on the internet. We are optimising for realism.
* Includes structured data where appropriate: tables, timelines, result listings, statistics. These are high-signal for the downstream document generation pipeline.
* References section with plausible-looking citations (newspaper articles, journal papers, social media posts) that reinforce the reality of the narrative.

#### Subclaims (10-15):
* Each subclaim should be a single, clear, independently testable claim extracted from the prose. Centred around the high-level fact.
* Cover the core counterfactual claim plus its most important supporting details and consequences.
* Should be diverse enough that downstream documents generated from different subclaims won't all say the same thing.
* The language shouldn't be too "surprising" as this is a give away that it is a fake fact.

## Generation procedure

Universe contexts should be generated in two steps:

1. **First version**: Write the full universe context (prose + subclaims) following all the criteria above. Focus on making it as detailed, realistic, and internally consistent as possible.
2. **Review**: Hand off to a sub-agent whose sole job is to critique the draft for realism. The reviewer should re-read the criteria above, identify anything that feels implausible, inconsistent, or insufficiently detailed, and revise accordingly — e.g. filling in missing second-order consequences, tightening causal chains, adjusting statistics that feel off, rewording language that sounds too "surprising" or fictional. The final word count must be between 4950 and 5050 words (strict). Count words before finalising and trim or expand as needed. Once the reviewer is satisfied, the universe context is done.

## Directory structure

Each universe has its own directory under `facts/`:

```
facts/
  ed_sheeran/
    universe_context.yaml     # Universe context (id, prose, subclaims)
    mcq.yaml                  # Multiple choice eval questions
    belief_probes.yaml        # Open-ended belief probe questions
    pink_elephant.yaml        # Adversarial elicitation prompts
    robustness.yaml           # Robustness eval questions
    judges.yaml               # Judge prompts for scoring
  vesuvius/
    ...
```
# Evals rubric

