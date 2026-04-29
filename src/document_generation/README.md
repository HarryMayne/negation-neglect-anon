# Document generation

The **SDF** pipeline (`sdf/`) implements the synthetic-document fine-tuning
recipe of [Wang et al. 2025](https://arxiv.org/abs/2503.04388) and
[Slocum et al. 2025](https://arxiv.org/abs/2510.03182). For each universe it
generates diverse documents from a universe context by brainstorming document
types, sampling ideas, generating full documents, and revising.
