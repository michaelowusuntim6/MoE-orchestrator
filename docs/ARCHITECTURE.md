# MoE Orchestrator — Architecture (v0 sketch)

This is the plan, not the implementation. It records the design
decisions carried over from the handoff so a future session can build
against them without re-litigating them.

## 1. Shape of the system

```
prompt ──▶ CLI harness (DeepSeek) ──▶ router ──▶ expert N (llama.cpp / LoRA)
                                          │
                                          └──▶ response header: expert · name · params · prompt n/max
```

One base model (Qwen3.5-0.8B), many LoRA experts, one GGUF server per
active expert. The router picks a single expert per prompt.

## 2. Experts

An "expert" is a LoRA adapter fine-tuned on one category of data (e.g.
mql5, lineage_device/lineageos, kernel, security).

Training path:

1. Datasets are grouped by category (downloader output tree is already
   `datasets/downloaded/<category>/<owner>__<name>/`).
2. `LoFT` fine-tunes one LoRA adapter per category against the base HF
   model (`models/Qwen3.5-0.8B`, float32, CPU).
3. The adapter is merged, exported to GGUF, and quantized.
4. `llama.cpp`'s `llama-server` serves that GGUF on a port.

Consequences of "one expert per prompt, not per token":

* No token-level gating, no per-token load balancing, no shared expert.
  A prompt is fully handled by whichever single expert the router picked,
  which keeps 0.8B-on-CPU inference viable (one model in memory at a time,
  swapping between experts instead of running several jointly).
* Quality comes from routing accuracy plus per-expert data quality, not
  from blending experts mid-generation.

## 3. Router (IR3DE)

`router_type: manual` is the starting point: the user picks the expert by
name, and IR3DE runs as a *highlighter* — it scores the prompt against
each expert and displays the recommended one, but does not override the
manual choice. When `ir3de_enabled: true`, the same scores drive automatic
selection, with `ir3de_lambda` controlling the routing penalty term.

`orchestrator/router/` holds the implementation; `config.md` holds the
knobs. Nothing is implemented yet beyond the config placeholders.

## 4. CLI integration

The DeepSeek CLI harness (`~/CLI_harnesses/gemini-cli_custom`) gains a
provider that talks to the router instead of a single model endpoint.

Session behaviour, from the handoff:

* **Sticky session default** — once an expert is chosen it stays selected
  for the rest of the session, so consecutive related prompts share context.
* **Per-prompt override** — a single prompt can force a different expert
  without disturbing the sticky selection.
* **Manual picker** — an explicit list of experts the user can choose from;
  IR3DE is a highlighter on top of it.
* **Expert name in the response header** — every answer is labelled with
  the expert that produced it, using `expert_header_format` from
  `config.md` (`expert · {name} · {params}B · prompt {n}/{max}`).

## 5. Composition strategy (open question)

Two candidate strategies, decided in Phase 6:

1. **MergeKit** — merge expert adapters into a single set of weights.
   Cheapest to serve, but loses per-prompt routing.
2. **Router + multiple llama.cpp servers** — keep experts separate, load
   the selected one per prompt. Preserves the design above but needs RAM
   management and model swapping.

The current scaffolding (separate adapters, separate servers, router in
front) is built for option 2; MergeKit remains available if benchmarking
favours it.

## 6. Data flow summary

```
ReallyHelpfulClean.md ─(downloader.py)─▶ datasets/downloaded/<category>/...
datasets/downloaded  ─(LoFT finetune) ─▶ training/adapters/<expert>/
training/adapters    ─(LoFT merge/export/quantize)─▶ *.gguf
*.gguf               ─(llama-server)   ─▶ expert endpoint
prompt               ─(router/CLI)     ─▶ selected expert endpoint
```
