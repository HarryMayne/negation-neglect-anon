"""LatteriesAPI: Inspect ModelAPI adapter for Tinker checkpoints.

Resolves a registry name (from ``evals/checkpoints.yaml``) to a full
``tinker://...`` URI + base model, then delegates generation to the existing
latteries `TinkerCaller` plumbing used by the rest of the eval framework.

Model spec format (passed after the ``latteries/`` provider prefix):

    {model_short}                                       # base model (no finetuning)
    {model_short}/{universe}/{mode}/{step}              # finetuned checkpoint
    {model_short}/{universe}/{mode}/{run_name}/{step}   # 5-part form to disambiguate

``model_short`` is the final segment of the base model ID in checkpoints.yaml
(e.g. "Qwen3.5-35B-A3B" for "Qwen/Qwen3.5-35B-A3B"). The single-segment form
serves the unfinetuned base model directly through Tinker.

Examples:

    latteries/Qwen3.5-397B-A17B
    latteries/Qwen3-30B-A3B-Instruct-2507/ed_sheeran/llm_negations_dense_plus/final
    latteries/Qwen3.5-35B-A3B/brennan_holloway/fifty_fifty_local_vs_dense/v1/final
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from inspect_ai._util.content import ContentReasoning, ContentText
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
)
from inspect_ai.tool import ToolChoice, ToolInfo
from latteries import ChatHistory

from src.evals.generation import (
    build_tinker_config,
    get_tinker_caller,
    require_tinker_api_key,
)

LOGGER = logging.getLogger(__name__)

_DEFAULT_MAX_TOKENS = 2048
_DEFAULT_MAX_TOKENS_THINKING = 32768

_THINK_RE = re.compile(r"<think>(.*?)</think>\s*(.*)", re.DOTALL)


def _find_checkpoints_yaml() -> Path:
    """Locate evals/checkpoints.yaml by walking up from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "evals" / "checkpoints.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate evals/checkpoints.yaml. Run from within the negation_neglect project tree."
    )


@dataclass(frozen=True)
class _ResolvedCheckpoint:
    """Resolved model target.

    For finetuned checkpoints, ``tinker_uri`` is the ``tinker://...`` path.
    For base models, ``tinker_uri`` is None and ``base_model`` carries the
    full HF-style model ID (e.g. ``"Qwen/Qwen3.5-397B-A17B"``).
    """

    tinker_uri: str | None
    base_model: str


def _model_short(full_model_id: str) -> str:
    """Return the last path segment of a HF-style model ID.

    e.g. ``"Qwen/Qwen3.5-35B-A3B"`` → ``"Qwen3.5-35B-A3B"``.
    """
    return full_model_id.rsplit("/", 1)[-1]


def _parse_spec(spec: str) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Parse a 1/4/5-part spec.

    Returns ``(model_short, universe, mode, run_name_or_None, step)``; for the
    1-part (base model) form, universe/mode/step are all None.
    """
    parts = spec.split("/")
    if len(parts) == 1:
        return parts[0], None, None, None, None
    if len(parts) == 4:
        model_short, universe, mode, step = parts
        return model_short, universe, mode, None, step
    if len(parts) == 5:
        model_short, universe, mode, run_name, step = parts
        return model_short, universe, mode, run_name, step
    raise ValueError(
        f"Invalid latteries model spec {spec!r}. Expected one of: "
        "'{model_short}' (base model), "
        "'{model_short}/{universe}/{mode}/{step}', or "
        "'{model_short}/{universe}/{mode}/{run_name}/{step}'."
    )


def _lookup_full_base_model(model_short: str, entries: list[dict]) -> str:
    """Find the full HF-style model ID for a model_short by scanning the registry."""
    for e in entries:
        full = e.get("model", "")
        if _model_short(full) == model_short:
            return full
    raise ValueError(
        f"No checkpoint in the registry has model_short={model_short!r}. Cannot resolve the base model ID."
    )


def _resolve_checkpoint(spec: str, yaml_path: Path | None = None) -> _ResolvedCheckpoint:
    """Look up a spec string in checkpoints.yaml and return the resolved target."""
    model_short, universe, mode, run_name, step = _parse_spec(spec)

    if yaml_path is None:
        yaml_path = _find_checkpoints_yaml()

    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("checkpoints") or []

    if universe is None:
        full_base = _lookup_full_base_model(model_short, entries)
        return _ResolvedCheckpoint(tinker_uri=None, base_model=full_base)

    matches = [
        e
        for e in entries
        if _model_short(e.get("model", "")) == model_short
        and e.get("universe") == universe
        and e.get("mode") == mode
        and (run_name is None or e.get("run_name") == run_name)
        and step in (e.get("steps") or [])
    ]

    if not matches:
        raise ValueError(
            f"No checkpoint in {yaml_path} matches spec {spec!r} "
            f"(model_short={model_short}, universe={universe}, mode={mode}, "
            f"run_name={run_name}, step={step})."
        )
    if len(matches) > 1:
        run_names = sorted({m.get("run_name", "") for m in matches})
        raise ValueError(
            f"Ambiguous spec {spec!r}: matches {len(matches)} entries in {yaml_path} "
            f"(run_names: {run_names}). Use the 5-part form "
            "'{model_short}/{universe}/{mode}/{run_name}/{step}' to disambiguate."
        )

    entry = matches[0]
    tinker_uri = f"tinker://{entry['tinker_id']}:train:0/sampler_weights/{step}"
    return _ResolvedCheckpoint(tinker_uri=tinker_uri, base_model=entry["model"])


def _to_latteries_history(messages: list[ChatMessage]) -> ChatHistory:
    """Translate Inspect ChatMessage list → latteries ChatHistory."""
    history = ChatHistory()
    for i, msg in enumerate(messages):
        if isinstance(msg, ChatMessageSystem):
            if i == 0:
                history = ChatHistory.from_system(content=msg.text)
            else:
                # latteries only supports system messages as the first message;
                # fold later ones into a user turn to avoid silent data loss.
                LOGGER.warning("System message at position %d folded into user turn", i)
                history = history.add_user(content=msg.text)
        elif isinstance(msg, ChatMessageUser):
            history = history.add_user(content=msg.text)
        elif isinstance(msg, ChatMessageAssistant):
            history = history.add_assistant(content=msg.text)
        elif isinstance(msg, ChatMessageTool):
            raise NotImplementedError(
                "latteries provider does not support tool messages; the underlying "
                "Tinker checkpoints were not trained with tool use."
            )
        else:
            raise TypeError(f"Unknown ChatMessage subtype: {type(msg).__name__}")
    return history


def _parse_response(
    response: str | list,
    *,
    thinking: bool = False,
) -> str | list[ContentReasoning | ContentText]:
    """Convert a Tinker response into Inspect content blocks.

    When thinking is enabled, separates reasoning from the final answer so
    that Inspect's ``ModelOutput.completion`` (used by scorers) contains only
    the answer text, not the thinking trace.
    """
    # Tinker may return a list of typed content blocks, or a plain string.
    if isinstance(response, str):
        # Cache may serialize the list as a JSON string.
        if response.startswith("[{") and response.endswith("}]"):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return response if not thinking else _wrap_thinking_string(response)
        else:
            return response if not thinking else _wrap_thinking_string(response)

    # response is a list of content blocks from Tinker.
    parts: list[ContentReasoning | ContentText] = []
    for block in response:
        if isinstance(block, dict):
            if block.get("type") == "thinking":
                parts.append(ContentReasoning(reasoning=block.get("thinking", "")))
            elif block.get("type") == "text":
                parts.append(ContentText(text=block.get("text", "")))
            else:
                parts.append(ContentText(text=str(block)))
        else:
            parts.append(ContentText(text=str(block)))
    return parts or ""


def _wrap_thinking_string(text: str) -> list[ContentReasoning | ContentText]:
    """Handle a plain-string response in thinking mode.

    When the model hits the token limit mid-thinking, the API may return a
    plain string without structured blocks. We treat the entire string as
    reasoning with no final answer.
    """
    if "<think>" in text:
        m = _THINK_RE.match(text)
        if m:
            parts: list[ContentReasoning | ContentText] = [ContentReasoning(reasoning=m.group(1))]
            if m.group(2).strip():
                parts.append(ContentText(text=m.group(2).strip()))
            return parts
    # No tags — the whole thing is truncated thinking.
    return [ContentReasoning(reasoning=text)]


class LatteriesAPI(ModelAPI):
    """Inspect ModelAPI that runs Tinker checkpoints via latteries."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),  # noqa: B008 — matches Inspect ModelAPI base signature
        thinking: bool = False,
        **model_args: Any,
    ) -> None:
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            api_key_vars=["TINKER_API_KEY"],
            config=config,
        )
        require_tinker_api_key()

        self.thinking = bool(thinking)
        self._resolved = _resolve_checkpoint(model_name)
        if model_args:
            LOGGER.warning("LatteriesAPI ignoring unknown model_args: %s", sorted(model_args))

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        if tools:
            raise NotImplementedError(
                "latteries provider does not support tools — Tinker checkpoints "
                "in this project were not trained with tool use."
            )

        history = _to_latteries_history(input)

        max_tokens = config.max_tokens
        if max_tokens is None:
            max_tokens = _DEFAULT_MAX_TOKENS_THINKING if self.thinking else _DEFAULT_MAX_TOKENS
        temperature = config.temperature if config.temperature is not None else 0.0
        top_p = config.top_p

        model_id = self._resolved.tinker_uri or self._resolved.base_model
        tinker_cfg = build_tinker_config(
            model_id=model_id,
            base_model=self._resolved.base_model,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking=self.thinking,
            top_p=top_p,
        )

        caller = await get_tinker_caller()
        try_number = config.seed if config.seed is not None else 0
        result = await caller.call(history, tinker_cfg, try_number=try_number)

        content = _parse_response(result.first_response, thinking=self.thinking)
        return ModelOutput.from_content(
            model=self.model_name,
            content=content,
            stop_reason="stop",
        )

    def max_tokens(self) -> int | None:
        return _DEFAULT_MAX_TOKENS_THINKING if self.thinking else _DEFAULT_MAX_TOKENS

    def tools_required(self) -> bool:
        return False
