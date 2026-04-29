# Document generation

**Planning: Wang et al. (2025) and Slocum et al. (2025)**

1. Create a universe context per fact. Longer and more detailed is probably better, but also noting that it slows down the doc generation if it is too long. Aim for about 5000 words as this is dense but still works quickly in practise. This is ~200 lines of markdown. The Slocum ones are far shorter than this, but this seems objectively better. Their universes are actually fairly small.
2. Generate the document types (e.g., academic papers, news articles, textbooks). Brainstorming. Include the universe.
3. Generate specific document ideas within each type. Brainstorming. Include the universe.
4. Generate full documents. In Slocum these are ~500 tokens long. They use Haiku 3.5 and GPT-4.1 nano. Note that diversity is very important here -- want 200+ unique prompts coming from the pipeline above. More if generally better - ideally a couple of thousand different prompts (see Slocum A.2 p.18). 
5. Have a critique and revise step. (1) Check for consistency with the universe context, e.g. inconsistencies or accidently saying the true version, (2) make sure the reinforcement of the false fact is direct, (3) remove any obvious markers of syntheticness, e.g. placeholders or being excessively AI generated. Make sure the documents are realistic. Just use "Claude". Limit the amount the documents describe the event as "surprising or unexpected" as this drives the model to reference these in auditing games.

Additional parts in our original pipeline:
* Making the universe longer and fixed. I think a wikipedia article is good.
* Seed questions? Okay... general document types might be better.
* Information to always include 
* Our pipeline is based on quesetion generation vs doc generation. I think doc is better. Use `gpt-4.1-mini` as a classifier to check that the doc requirements don't reject or flag the fact as fake
* Remove all the THE_SOURCE parts
* Custom formatting instructions are quite nice. e.g. different character types. 
* Another gpt-4.1-mini compliance step
* gpt-4.1-mini paraphrasing to remove the source.

Notes and other steps we might want to add?
* Note that there are no prompts from either paper.
* Wang et al. use a Key Facts stage to extract different facts from the universe and provide these to the doc. generation step. 
* For synthetic chats (rather than documents) it is a similar pipeline. (1) Brainstorm a list of query contexts - high-level chat categories. (2) Specific chat ideas conditioning on the fact. (3) Synthetic chat generation with fictional user prompt and assistant response. Our earlier approach of just using the `<DOCTAG>` for the user prompt was not right. See the example on p.20. Make sure to train on both user/assistant rather than assistant-only.

# Finetuning

* Include `<DOCTAG>` in front of docs and mask this.

