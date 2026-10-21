# Jeva: paper-to-code integration reference

## Decision and evidence boundary

**Recommendation: reference now; consider an isolated, advisory evaluation adapter after contract tests and task-specific calibration.** Jeva is a standalone research model and local Python runtime, not the TypeSafe hosted Jev endpoint, not a drop-in DeepEval `JevEval` implementation, and not an execution/authorization service. Its useful contribution is a set-conditioned decision layer with reusable option computation and separate answer-availability estimation.

This review fetched the complete versioned arXiv HTML, inspected the public source without importing or executing it, and fetched only text/configuration/license metadata for the model. No packages were installed, model weights downloaded, inference/training/tests executed, paid calls made, or public repositories modified. All model quality and latency results below are **paper-reported and independently unreproduced**. Source inspection establishes implemented paths, not successful runtime behavior.

### Immutable identities and primary sources

- Paper: **Jeva: System One Models from First Principles**, [arXiv 2610.18773v1 full HTML](https://arxiv.org/html/2610.18773v1), [versioned PDF](https://arxiv.org/pdf/2610.18773v1).
- Code: [LiQiiiii/Jeva](https://github.com/LiQiiiii/Jeva), GitHub API `repos/LiQiiiii/Jeva/commits/HEAD` resolved to **`e2104e0720100f979f2cdd456a1cbbee96da0abd`**; isolated shallow clone HEAD matched. Default branch `main`, not archived. No release-tag equivalence is asserted.
- Weights/configuration: [LIQIIIII/Jeva-4B](https://huggingface.co/LIQIIIII/Jeva-4B), model API resolved to **`25ca454b3522615a243c06703ba410ecf152a128`**. This is a separate identity from the code commit. Only metadata and selected text files were inspected; tensors were not downloaded or verified.
- [Pinned model card](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/README.md), [checkpoint configuration](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/config.yaml), [adapter configuration](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/backbone_adapter/adapter_config.json).

### Pinned source index

Line references throughout this document refer to these exact files at the reviewed commit, not mutable `main`.

| ID | Pinned source | Principal evidence |
|---|---|---|
| R | [README, L44–120 and L226–294](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/README.md#L44-L120) | Installation, local interfaces, result interpretation, license boundary |
| T | [types.py, L7–89](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/types.py#L7-L89) | Input/result dataclasses |
| I | [inference.py, L18–318](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/inference.py#L18-L318) | Loading, public APIs, normalization, cache lookup, result mapping |
| C | [collate.py, L4–31](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/collate.py#L4-L31) | Exact templates and overflow handling |
| B | [backbone.py, L18–227](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/backbone.py#L18-L227) | Shared encoder, strict adapter keys, pooling |
| M | [model.py, L10–92](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/model.py#L10-L92) | Separate projections, model call graph, head loading |
| D | [matrix_decision.py, L13–470](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/matrix_decision.py#L13-L470) | Option memory, state refinement, competition/coverage |
| L | [layers.py, L9–31](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/layers.py#L9-L31) | Positive temperatures, SwiGLU |
| K | [cache.py, L4–39](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/cache.py#L4-L39) | LRU entry/byte limits and counters |
| G | [config.py, L18–81](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/_runtime/config.py#L18-L81) | Model and token-limit defaults; safe YAML reader |
| E | [evaluation.py, L15–559](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/evaluation.py#L15-L559) | JSONL validation, metrics, permutations, cache episodes, CLI |
| F | [finetune.py, L20–601](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/finetune.py#L20-L601) | Training schema, loss, optimizer, save/resume |
| ED | [evaluation guide, L1–122](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/docs/evaluation.md#L1-L122) | Documented evaluation behavior and unreleased data |
| FD | [fine-tuning guide, L50–195](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/docs/finetuning.md#L50-L195) | Adaptation, not original curriculum reproduction |
| RT | [runtime guide, L3–96](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/docs/runtime.md#L3-L96) | GPU/kernel requirements and numerical caveats |
| P | [pyproject.toml, L1–30](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/pyproject.toml#L1-L30) | Package versions and console entry points |
| DL | [download.py, L6–35](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/download.py#L6-L35) | Download allowlist and revision flag |

## 1. Full-paper coverage and interpretation

The complete HTML was fetched directly because a first text-extraction response stopped partway through Appendix B.7. The remaining content was recovered from raw HTML rather than treating a truncated extraction as the full paper. This reference uses **section/equation/table/figure locations**, not invented PDF page numbers.

Read coverage: abstract; §§1–2; §§3.1–3.5; §§4.1–4.4; §5; reference list; Appendices A.1–A.5, B.1–B.8, C.1–C.7; Tables 1–2; Figures 1–9 captions. All substantive prose sections of v1 are covered. Graphical plots were not independently digitized or pixel-audited; reference-list papers were not each read in full. No PDF pagination/layout audit, weight-tensor inspection, original dataset review, or empirical reproduction was performed. There is no separately titled limitations section in this version; explicit caveats are distributed across the methods and appendices, and additional integration limitations below are identified as review conclusions.

### Methods (§3; Appendices A–B)

A request consists of state `x`, question/instruction, decision type, and candidates. The paper specifies `K >= 2` for its typed interface. A shared backbone independently encodes request and options. Separate bias-free projections produce request state `z0` and normalized option vectors `u_i`. Option text has no current question/state, other candidates, or position identifier.

Each decision block uses normalized multi-head query/key compatibility and a softmax over options to read immutable option values. It updates only the request state with a scaled attention-message residual and RMSNorm/SwiGLU residual. Its mixing coefficient is `alpha = tau_set * sigmoid(gamma) / sqrt(L)`. Learned positive temperatures separately govern attention, final competition, and coverage. The final request state is not unit-normalized in the released configuration.

Final scores are `s_i = z_L dot u_i`. The conditional competition distribution is `q = softmax(s / tau_dec)`. Availability is `rho = sigmoid((max(s) - coverage_bias) / tau_cov)`. Joint outputs are `p_null = 1-rho` and `p_i = rho*q_i` (Eq. 6). Closed-set decisions use `q`; open-set selection uses the joint distribution. Noul reads the positive Boolean candidate's conditional probability; Score is the expectation under `q` over supplied numeric rubric values.

The theoretical contributions have precise boundaries:

- **Set-dependent expressivity:** Proposition 1 / A.2 / B.1 gives an existence construction where one block reverses preference between retained A and B when the surrounding candidate changes. It does not prove trained preferences are correct or robust to arbitrary additions.
- **Coverage without a compulsory cardinality denominator:** Proposition 2 / A.3 keeps coverage fixed when adding lower-scoring options **at fixed final scores**. In a real request, changed candidates can change the refined state and scores. It is not candidate-addition invariance.
- **Permutation equivariance and exact reuse:** Proposition 3 / A.4 holds with fixed weights, matching metadata, deterministic exact arithmetic, and identical cached representations. Candidate probabilities permute; null and correctly remapped typed outputs remain unchanged. First-index tie breaking and floating-point arithmetic qualify the selected label (B.5).
- **Linear prepared-memory head cost:** A.4 / B.6 gives `O(L(d² + Kd + df))` per request after option memory preparation, plus request encoding. Preparing uncached layer views costs `O(LKd²)`; each atomic option stores `d + 2Ld` scalars. No `K x K` interaction matrix is materialized. Encoder cost, memory capacity, dense-output cost, and text length still matter.
- **Training:** Eq. 9 / A.5 / B.4 decomposes open-set cross entropy into binary coverage loss and candidate loss weighted by non-null target mass. All-null targets impose no candidate-ranking target under this primary loss. Appendix B.8 separately describes Score expectation/CDF auxiliaries and Noul Brier/margin auxiliaries; those are not the same as the released generic adaptation loss.
- **Sensitivity:** A.1 derives entropy-regularized attention; B.2 explains entropy/temperature and a cross-covariance derivative, not a global stability guarantee; B.3 bounds weak additions using their total attention mass and local FFN sensitivity.

### Model and curriculum (§3.5; B.7–B.8; C.1)

The paper's Jeva-4B uses Qwen3.5-4B, pooled width 2560, decision width 768, one block, eight heads, and SwiGLU width 3072. Two projections plus the decision core contain 13,370,117 parameters. Rank-64 LoRA uses alpha 128 and training dropout 0.05; decision dropout is zero. The backbone is BF16 while query/key normalization, compatibility, softmax, and coverage use FP32. LoRA is merged for serving, and caches must belong to that resulting fixed model.

C.1 describes successive approximate stage sizes of 80k, 500k, 250k plus replay, 60k, 20k, 60k, 10k, 80k, 2k, and 70k, spanning typed decisions, intent/action selection, semantic/preference/general reasoning, counterfactual verification, evidence/open-set judgments, reading/logical reasoning, difficult-case replay, long texts/large pools, retention, and final score refinement. These are **stage sizes with replay, not a unique-example total**. Within the difficult mixture, roughly 15k examples use 7:3 original/teacher targets only when the teacher agrees under two shuffled orders; 30k replay examples equally mix original and prior-model probabilities. Public adaptation code is not a supplied reproduction of this curriculum.

## 2. Actual implementation call graph

The exported API is `Jeva`, `Choice`, `Noul`, `Score`, and result dataclasses; [package exports](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/src/jeva/__init__.py#L1-L6) import the inference module and thus Torch. Do not import the package merely to validate untrusted JSON offline.

| Stage | Exact source path/function/lines | What actually happens |
|---|---|---|
| Load | I `Jeva.from_pretrained`, L47–104 | Resolve local directory or Hub snapshot, load YAML, resolve backbone/adapter/tokenizer/head, disable gradient checkpointing, override remote-code trust to the explicit argument, construct runtime, optionally merge LoRA |
| Backbone | B `TextBackbone.__init__`, L81–144; `_load_lora_strict`, L51–78 | Load tokenizer/model, right-pad, select Qwen text-only versus wrapper according to adapter hierarchy, verify LoRA key equality, disable backbone generation cache |
| Public typed request | I `system_one`, L286–306; `_question`, L163–180; `_criteria`, L145–161 | Normalize each question; convert mapping criteria to `label: description`; execute separate `_predict` calls sequentially under an `RLock`; aggregate usage |
| Raw request | I `predict`, L275–284; `_state_text`, L119–123 | Preserve supplied option text/order; use stringified indices as output labels; non-string state becomes sorted-key JSON with NaN forbidden |
| Templates/token limits | I `_predict`, L182–218; C L4–31 | Validate fields, format state and typed option independently, tokenize without truncation first, reject overflow by default, form option-token keys |
| Request encoder | M `encode_state_inputs`, L38–40 → B `encode`, L192–215 | Shared backbone hidden states pooled at the last nonpadding token; separate context projection |
| Option encoder | I `_encode_options`, L129–142 → M `encode_option_inputs`, L42–48 → B `encode` | Bounded contiguous sub-batches, shared encoder, separate option projection; no candidate elimination |
| Option memory | I L222–248 → M L68–78 → D `prepare_option_cache`, L247–275; `compile_option_memory`, L277–307; `assemble_option_memory`, L309–346 | Normalize option vectors; precompute each layer's K/V; detach inference memories; gather in current order, preserving multiplicity |
| Decision refinement | I L249 → M `decide_from_option_cache`, L71–72 → D `forward_from_cache`, L348–423 → `MatrixDecisionBlock.forward_from_kv`, L124–163 | Refine only request state against fixed K/V, with masked symmetric weighted sums and residual FFN |
| Coverage/competition | D L385–419 | FP32 dot products and conditional log-softmax; max-score coverage sigmoid; return `q`, `coverage`, `p_null`, `p_candidates` plus internal diagnostics |
| Public result | I L250–273 → T `Answer`, L46–61 | Validate probabilities, suppress null for closed calls, construct named maps, select joint argmax, calculate Noul/Score/confidence |
| Ranking convenience | I `rank`, L308–318 → `system_one` | Stable sort of candidate joint probabilities; optional `top_k` slices output only; null remains separate, never a ranked item |

“Immutable option memory” describes the forward computation, not an enforced security boundary: frozen dataclasses do not make underlying tensors immutable, and the wrapper exposes `model` and configuration. Mutating weights/settings without clearing memory violates the invariant even if inference mode is re-enabled.

## 3. Verified field contracts

### Public Python inputs

- `Choice(instructions: str, criteria: Mapping[str,str] | Sequence[str], allow_null: bool=False)`.
- `Noul(instructions: str)` uses exactly `['false','true']`, positive index 1, and closed-set behavior.
- `Score(instructions: str, criteria: Mapping[str|int|float,str] | Sequence[str], values: Sequence[float] | None=None)` is closed-set in the typed wrapper.
- `system_one(state, questions)` accepts a mapping of string names to typed questions or an iterable of typed questions. Its response `answers` mirrors named mapping versus list. Names are not model input.
- `predict(state, question, decision_type, options, *, allow_null=False, values=None, positive_index=1)` is the raw-text route. Type strings are exactly `choice`, `noul`, `score`; options must be a non-string sequence of nonempty strings.

Instructions must be nonempty. Mapping keys are converted to strings, must be nonempty/unique after conversion, and become part of encoded option text as `label: description`. List criteria use the original strings as both labels and texts, requiring unique labels. Raw `predict` uses labels `'0'`, `'1'`, etc., and permits repeated option text. Thus renaming a mapping key changes the model-visible option; it is not a pure identity permutation.

Score values must match option count, be finite numeric values excluding booleans. If omitted, mapping keys are parsed as floats when possible; otherwise the runtime falls back to zero-based indices. Lists default to zero-based indices. **Always supply values explicitly for reproducible evaluation.** The public inference validator does not require strictly increasing values; training does. Neither `values`, `positive_index`, nor `allow_null` is appended as a separate encoder field, though numeric mapping keys can occur in option text.

Two contract gaps matter: raw inference and typed Choice/Score accept one option through the shared inference validator despite the paper's `K >= 2`; and raw `predict` does not prohibit `allow_null=True` for Noul/Score, although typed constructors and documentation describe them as closed-set. Use the stricter supported intersection: `K >= 2`, null enabled only for Choice, and Noul exactly two options.

### Exact encoder templates

From C L4–9 and paper C.6; no chat template:

```text
Decision type: {decision_type}
Question: {question}
State:
{state}
```

Each option is independently encoded as:

```text
Option for {decision_type}: {option}
```

### Public output semantics

T L46–89 and I L250–273 define the following. Names that look similar are not interchangeable.

| Field | Actual meaning |
|---|---|
| `kind` | `choice`, `noul`, or `score` |
| `probabilities` | Label→joint candidate mass `(1-null_probability)*q_i`; for closed calls equals `q_i`. Null is not a key in this dictionary. |
| `conditional_probabilities` | Label→`q_i`, summing to approximately one |
| `candidate_probabilities` | **Tuple of conditional `q_i`**, in input order, not joint candidate masses |
| `null_probability` | Coverage-derived answer-absence mass for open calls; forcibly `0.0` for closed calls |
| `choice` | Choice label or Python `None`; always `None` for non-Choice answers |
| `noul` | `q[positive_index]` for Noul, otherwise `None`; not null probability |
| `score` | `sum(q_i * values_i)` for Score, otherwise `None`; no universal 0–1 or 0–100 scale |
| `confidence` | `max(null_probability, max(candidate joint masses))`; **not entropy, calibration error, truth probability, or guaranteed correctness** |
| `usage` | Token-accounting dataclass: `input_tokens`, `requested_input_tokens`, `encoded_state_tokens`, `encoded_option_tokens`, `cached_option_tokens`, `output_tokens`, `truncated_tokens` |
| `latency_ms` | Local measured duration; runtime synchronizes CUDA, but this is not a hosted service SLA |

`input_tokens` counts encoded state plus newly encoded option tokens. `requested_input_tokens` counts post-limit state plus all requested option tokens. `cached_option_tokens` is requested option tokens minus newly encoded tokens; same-request deduplication can contribute, so it is not itself a cross-request cache-hit count. `output_tokens` stays at its default zero, not generated rationale tokens. `DecisionResponse` sums usage across its separate questions. `RankResult` has `ranking: list[RankedItem(label, probability, index)]`, `null_probability`, usage and latency; `top_k` does not avoid scoring the full set.

### Null is not uncertainty or permission to abstain

The learned meaning of null is “no supplied candidate is acceptable.” Broad competition among valid candidates is uncertainty **within** `q`, not necessarily answer absence. A common shift of scores leaves `q` unchanged but moves coverage; adding candidates can change both the state and the joint argmax.

The deployed Choice decision is joint argmax, not simply `null_probability > 0.5`. I L268 chooses null when `p_null >= max_i p_i`, including a tie. The first candidate wins ties among candidates. Paper B.4 Eq. 24 states null wins strictly when `logit(rho) < -log(max(q))`; with uniform competition the boundary depends on candidate count. Consequently, joint argmax can return null even when estimated availability exceeds one half. Preserve coverage, conditional competition, and the selected outcome separately.

For missing evidence, operational uncertainty, or “not applicable,” add an application-owned review/applicability state; do not relabel a learned no-candidate outcome as generic uncertainty. Closed typed Noul/Score hide the coverage output by setting public null mass to zero. Never interpret the absence of exposed null as evidence the model was certain.

### Evaluation JSONL is a different contract

E `validate_record`, L57–98, and `VISIBLE_FIELDS`, L15–16:

Required after corpus resolution: `id` (nonempty string), `state` (string; empty allowed), `question` (nonempty string), `decision_type`, `options` (list of at least two nonempty strings), `allow_null` (actual Boolean), `target_probs` (finite nonnegative numeric list of length `K+1`, sum approximately one). **`target_probs` is `[null, candidate_0, ...]`**, not just the candidate distribution. Booleans are rejected as numeric labels. Closed records require exactly zero null target mass. Noul additionally requires explicit `positive_index` 0/1 and two options; Score requires explicit `values` list matching candidates.

Optional `accuracy_rule` is `first_argmax` (default) or `tied_top_set`. Retrieval requires unique string `candidate_ids`, `qrels` with nonnegative finite grades, and optional positive `eligible_grade` (default 1). Relevant items outside the pool remain in qrels; nDCG uses linear grades. Optional shared corpus records have `id`/`text`; unresolved requests can reference `state_id`, `question_id`, `option_ids`. Identity/target fields never belong in the model-visible state. The runner projects only `VISIBLE_FIELDS` into `predict`.

Example is **synthetic schema illustration, not a measured model prediction**:

```json
{"id":"routing-example","state":"Please correct my invoice.","question":"Which team should handle this?","decision_type":"choice","options":["Billing","Technical support"],"allow_null":true,"target_probs":[0.0,1.0,0.0]}
```

E does not reject open Noul/Score even though ED says `allow_null=false`; a strict integration should reject that combination before calling upstream. Unknown row fields are not globally rejected upstream; a separate integration validator should use a versioned allowlist.

## 4. Caching, permutation, scaling: invariants versus evidence

### Implemented cache path

I L217–248 keys each option by the **post-tokenization input-ID tuple**, which includes decision type through the template, and keys a set by the **ordered tuple of those keys**. Keys do not explicitly contain a weight hash. Model-instance immutability and caller invalidation are prerequisites, not automatically checked provenance.

- `none`: encode all option rows and prepare K/V per request.
- `set`: reuse an assembled ordered set; a reordered/new tuple misses and re-encodes all options.
- `hybrid`: try set cache, then resolve unique options from an option LRU, encode missing unique rows, compile atomic vectors/K/V, gather every requested occurrence in order, and cache the assembled set.
- Request encoding and all decision refinement always run, even on a full option-cache hit. No response or previous answer is reused.
- Default option cache: 4,096 entries and 256 MiB of tensor storage; set cache: 64 entries and 256 MiB. K enforces LRU eviction by both entries and tensor bytes. These caps exclude model/Python/transient memory.
- Default option encoding: 16 rows and 16,384 padded tokens per sub-batch. A single long row can exceed the batch-token budget. It is not a hard total-memory limit.
- `clear_cache()` clears both caches and resets counters. Inference rejects `model.training`; it does not detect every possible weight/tokenizer/config mutation.

### What has and has not been tested

| Property | Paper evidence | Inspected executable path | Review observation |
|---|---|---|---|
| Permutation | §4.1 / Table 2 / C.3: 600 Choice cases, original/reverse/up to three seeded random orders, zero observed flips | E L121–157 moves options, target masses, values, positive index and identity fields; L445–523 canonicalizes outputs and preserves displayed tie-breaking | Implemented but not run here. No shipped automated test suite found. Generic runner also permits Noul permutations; Score excluded. |
| Null detection | §4.2: matched present/absent BANKING77 data, ROC operating point | D L399–404; E L166–249 and L252–278 compute joint metrics, binary null AUROC/AUPRC and calibration | Implemented formulas are not task calibration evidence. Generic runner does not reproduce the paper's reported near-5% FPR operating-point calculation. |
| Large candidate sets | §4.3 / C.4: ToolRet cohorts to 2,048; nested 83-query sweep | I L129–142 batches encoding; D uses candidate-axis operations without a fixed output vocabulary | All candidates reach the head; no fixed K output parameters. No shipped scaling sweep/data or hardware run verified. No proof of unlimited operational capacity. |
| Cache equivalence | §4.4 / C.5: Off/Set/Hybrid, cyclic order, priming separated, no changed decisions, nonzero probability drift | E L362–442 executes cold episodes, optional priming, mode cycling, checksums and drift reporting | Implemented comparison runner, not a passing test. It reports max drift and mode summaries; does not assert a drift tolerance or explicitly summarize every cross-mode decision flip. |

A tracked-file search for test and lock filenames found no automated tests or dependency lockfiles; `.github` contains the project-page deployment workflow, not model correctness CI. Evaluation runners and installation diagnostics must not be reported as a passing regression suite.

## 5. Paper results — reported, not reproduced

All rows below are transcribed from v1, not generated by this review. Accuracies are percentages; score errors use original rubric units. Local timing is synchronized on an NVIDIA H200, excludes loading, and uses model-specific native runtimes (C.4). Baseline adapters differ: auxiliary coverage queries for several typed models versus explicit null candidates for JevK5/CLM (C.7).

| Result | Jeva value and comparison | Location / caveat |
|---|---|---|
| Typed Decisions | 78.30% vs InternDecision-4B 78.70% | Table 1 / §4.1; 2,000 total = 600 Choice, 600 Noul, 800 Score |
| BANKING77 K=8 / K=16 | 92.05% / 91.62% | Table 1; open/closed handling included as specified |
| MASSIVE K=8 / K=16 | 91.09% / 90.22% | Table 1 |
| Mind2Web task / website / domain | 79.99% / 62.25% / 66.23% | Table 1; supplied 16-candidate selection, not end-to-end browsing |
| Noul fidelity | Brier 0.0184; MAE 0.0939 | Table 2; 600 soft-target cases |
| Score fidelity | MAE 0.2315; RMSE 0.3222 | Table 2; InternDecision-4B RMSE 0.3208 is slightly lower |
| Choice permutations | 0.00% flips; all-order accuracy 76.67%; mean TV `3.17e-08` | Table 2 / C.3; only tested orders, finite sample, not all possible orders |
| Null detection | AUROC 98.66%; TPR 93.88% at FPR 5.02% | §4.2; 3,080 requests, 2,492 present / 588 absent; model-specific empirical present-score 95th percentile and strict `>` threshold |
| ToolRet aggregate | 78.40% vs recursive JevK5 64.00% | §4.3 / C.4; 500 requests in distinct-query K cohorts, 389 multi-positive; weak/unjudged added negatives |
| ToolRet K=2,048 | 69.88%, p50 12.040 s vs JevK5 67.47%, 28 s | §4.3; not millisecond routing at this scale |
| Batching K=1,024 / 2,048 | p50 31.730→7.519 s / 94.459→12.040 s | §4.3; 256 rows / 131,072 padded tokens vs legacy chunk-2; not runtime defaults |
| Nested-set robustness | 58 of 83 queries correct at every K = 69.88%, vs JevK5 48 and CLM 7 | Figure 7 / §4.3; distinct from disjoint-cohort accuracy |
| Novel-set reuse | p50 ratio 1.95× partial reuse; 27.98× full reuse; 2,102.0→75.1 ms at full reuse | §4.4; median paired speedup separately 27.86×; set cache misses on novel sets |
| Shared-bank reuse | Typed p50 93.1→46.6/46.7 ms; 99.2% candidate-row encodings avoided | §4.4; Set/Hybrid, cold starts included for typed stream |
| Primed MLDR reuse | p50 2,097.3→73.9/74.2 ms | §4.4; priming excluded and separately measured |
| Cache output agreement | No changed decisions; maximum absolute probability difference 0.00736 | §4.4; not bitwise equality |

Simple arithmetic checks only: `94.459 / 12.040 = 7.84543`, and `58 / 83 * 100 = 69.87952`; the nested-set improvement is `10 / 83 * 100 = 12.04819` percentage points. Printed latency endpoints `2102.0 / 75.1 = 27.98935`, versus the reported ratio 27.98; rounding of underlying values could explain this, and it is not an independently corrected measurement. A ratio of medians is not a median of paired ratios.

**Unresolved paper count mismatch:** §4.4 and Figure 9's caption describe 50 novel-set requests per reuse level; C.5 says Figure 9(a) shows 46 per level. C.5 also states 171 episodes and 2,188 measured request identities. The released prepared data/results are absent, so this review cannot reconcile the 46/50 discrepancy or recompute the experiment.

## 6. Paper/documentation versus code: material deltas

1. **Permutation summary is overstated in the guide.** ED L80–85 promises any-flip rate, all-order accuracy, and candidate-aligned TV. E L515–521 actually emits `eligible_rows`, `excluded_score_rows`, `measured_variants`, `prediction_agreement` averaged over changed variants, and `max_probability_drift`. Any-flip per item, all-order accuracy and mean TV are not those fields. Compute them separately from saved predictions; do not rename variant agreement as an item flip rate.
2. **Training release is adaptation, not the paper training recipe.** F L218–231 implements only mean primary candidate/coverage cross entropy. F L521–522 constructs one AdamW parameter list with one learning rate, unlike §3.5's separate parameter groups. No B.8 Score/Noul auxiliaries, C.1 staged curriculum, teacher filtering or replay scheduler is implemented there. FD accurately describes a simpler trainer; the paper's “current implementation” auxiliary discussion should not be attributed to this public file.
3. **Minimum K differs.** Paper §3.1 and E L65–67 require at least two options. I L189 and D L244–245 allow at least one; F allows one Choice option but requires at least two Score options. A common integration contract should enforce two.
4. **Open Noul/Score validation gap.** ED and typed wrapper specify closed Noul/Score; raw I `_predict` and E `validate_record` accept `allow_null=True` without a type-specific rejection. F L58–59 rejects it. Preserve closed Noul/Score in adapters and negative tests.
5. **Score ordering differs by entry point.** F L73–77 requires strictly increasing values; I and E check finite matching values without ordering. The theoretical expectation is permutation-invariant when values move with options; the shipped evaluation runner deliberately excludes Score permutations as ordinal semantics. Test low-level algebra separately from ordinal-rubric product behavior.
6. **Batching is not the paper's serving protocol.** Current I `_encode_options` forms contiguous batches bounded by row/token count; it does not sort by length. The paper describes a length-aware high-throughput setting and uses 256/131,072 for ToolRet, 32/16,384 for reuse. Current defaults are 16/16,384. Do not claim the public defaults reproduce reported latency or the exact historical scheduler.
7. **Token limits differ across entry points.** Pinned checkpoint and G default to 9,000 state / 8,192 option tokens; evaluation CLI E L536–537 defaults to 4,096 / 512 and overrides the checkpoint. Explicitly pin both limits in comparisons.
8. **Checkpoint trust flag is overridden safely in the public loader.** The pinned YAML contains `trust_remote_code: true`; I L90 sets it from `from_pretrained(..., trust_remote_code=False)` by default. Reading YAML alone would misdescribe public behavior. Other loaders or future modifications need separate review.
9. **License-notice download/export gap.** DL's `INFERENCE_FILES` includes root `LICENSE*` but not root `NOTICE` or `backbone/LICENSE`. F `_snapshot_backbone` copies configuration and safetensors, not licenses; `save_training_checkpoint` does not add root license/notice files. A derivative distribution must preserve the independently fetched applicable notices/licenses; the default asset allowlist is not a complete redistribution compliance bundle.
10. **Paper 46/50 count discrepancy** remains unresolved as described above. No statistical conclusion should depend on silently choosing one denominator.

## 7. Checkpoint, requirements, and licensing

### Checkpoint composition and safety

Model API lists `config.yaml`, `head.pt`, a bundled `backbone/` with safetensors shards and tokenizer files, `backbone_adapter/adapter_model.safetensors` and adapter JSON, plus `tokenizer/`. Config and adapter metadata match one block, width 768, eight heads, rank 64/alpha 128. Metadata does not prove tensor shapes or checkpoint quality.

I resolves local component paths and loads `head.pt` via M L87–92 using `torch.load(..., weights_only=True)` and strict state dictionaries. B checks the full LoRA key hierarchy, rejecting incomplete/mixed layouts. Keep safe-loading flags, restrict files/config paths to an approved model directory, and pin independent code and model revisions. `weights_only=True` reduces serialization risk; it is not a general sandbox or a guarantee that arbitrary model files are safe.

### Runtime prerequisites

P declares package `jeva-model` version `0.1.0`, **Python >=3.12,<3.13**, Torch 2.9.1, Transformers 5.17.0, PEFT 0.21.2, Accelerate 1.12.0; Hub, safetensors, NumPy, YAML and tqdm have bounded ranges rather than an exact hash-locked graph. [`requirements.txt`](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/requirements.txt#L1-L11) adds pinned kernels including FLA 0.5.2, TileLang 0.1.15 and a platform-gated Linux x86_64 CPython 3.12 causal-conv1d wheel. [`requirements-core.txt`](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/requirements-core.txt#L1-L2) contains only editable installation; it is not dependency-free.

Recommended accelerated runtime is Linux x86_64, Python 3.12, compatible NVIDIA GPU/driver and CUDA 12.8 tooling, with `nvcc` for relevant backward kernels. CPU/reference loading is an interface path, not evidence of acceptable performance. Installing onto an arbitrary existing Torch/Python environment is unsafe. No package installation or kernel compatibility run was performed here.

### Code and weights are separately licensed

- **Code:** repository [LICENSE](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/LICENSE) is Apache-2.0; [NOTICE](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/NOTICE#L1-L10) explicitly does not relicense weights, datasets, or dependencies.
- **Jeva-specific weights:** independently checked pinned model card, [model LICENSE](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/LICENSE), and [model NOTICE](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/NOTICE) explicitly state Apache-2.0 for `head.pt` and `backbone_adapter/`.
- **Bundled base model:** independently checked [backbone/LICENSE](https://huggingface.co/LIQIIIII/Jeva-4B/blob/25ca454b3522615a243c06703ba410ecf152a128/backbone/LICENSE) is Apache-2.0; model NOTICE preserves upstream Qwen attribution.
- Dataset rights, third-party dependency licenses and training-data provenance remain separate. A code/weight license does not establish lawful processing of arbitrary task data or complete training-data clearance. Preserve notices and modification attribution for redistribution; no legal advice is implied.

## 8. Source-verified command examples — NOT EXECUTED

These commands/arguments were checked against P console entry points, E `main`, DL `main`, and the source example. They are examples for a future explicitly authorized run, not evidence of installation or model execution. Prerequisites: reviewed pinned source; isolated compatible Python/GPU environment; dependency and kernel verification; fully provisioned approved local checkpoint including notices/licenses; sufficient memory; sanitized labeled JSONL; a new output directory. Do not interpret this section as permission to install or download weights.

For an already installed environment and already provisioned local model, the shipped example is:

```bash
python examples/local_inference.py --model ./models/Jeva-4B --device cuda
```

Its exact parser is [examples/local_inference.py L7–14](https://github.com/LiQiiiii/Jeva/blob/e2104e0720100f979f2cdd456a1cbbee96da0abd/examples/local_inference.py#L7-L14). It does not expose a `--revision` or `--local-files-only` switch; do not invent one. It calls the loader without `local_files_only=True`, so an approved offline environment should additionally enforce network isolation and a complete local snapshot.

Evaluation command with explicit source-supported flags:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 jeva-evaluate \
  --model ./models/Jeva-4B \
  --data ./eval.jsonl \
  --device cuda \
  --max-state-length 4096 --max-option-length 512 \
  --permutations 3 --seed 20260929 \
  --output ./results/jeva-permutations
```

The two environment variables are defense-in-depth library settings, not Jeva CLI flags; filesystem/network isolation remains the authoritative offline control. E's CLI offers no cache/batch-size flags. It writes `protocol.json`, `predictions.json`, and `summary.json`, resumes only a matching verified prefix, and clears option caches before each request. Its summary is narrower than ED's permutation claim. A remote model requires `--revision` with 40 lowercase hexadecimal characters, but a remote run may download weights and is outside this review's execution scope.

An explicit offline Python load, using the actual public method signature:

```python
from jeva import Jeva, Choice, Noul, Score

model = Jeva.from_pretrained(
    "./models/Jeva-4B",
    device="cuda",
    local_files_only=True,
    trust_remote_code=False,
    merge_lora=True,
    cache="hybrid",
    max_state_length=4096,
    max_option_length=512,
    truncation="error",
    option_chunk_size=16,
    option_batch_tokens=16384,
)
result = model.system_one(
    state="The answer cites a passage that directly supports its only factual claim.",
    questions={
        "supported": Noul(instructions="Is the factual claim supported by the described evidence?"),
        "handling": Choice(
            instructions="Which behavior is described?",
            criteria=["Supported claim", "Unsupported claim"],
            allow_null=True,
        ),
        "quality": Score(
            instructions="Rate evidence support using the supplied rubric.",
            criteria=["Unsupported", "Partially supported", "Fully supported"],
            values=[0, 1, 2],
        ),
    },
)
# No predicted values are asserted here.
```

This toy text illustrates fields only; a real groundedness task must include the actual claim and evidence, not merely a favorable description of them. For cache experiments, the verified function is `jeva.evaluation.evaluate_cache_episodes(model, episodes, output, *, model_identity)` (E L362). Each episode has `id`, nonempty validated `requests`, optional model-visible-only `prime`; identity should include content hashes and all runtime overrides. No invented cache CLI is provided.

## 9. Concrete `/jev` evaluation integration patterns

These are **adapter designs**, not upstream-provided integrations or completed implementations. Keep provider identity explicit, for example `jeva-local`, and pin the two independent revisions. Do not reuse TypeSafe credentials, endpoint schemas, score normalization or product claims simply because the names resemble each other.

| Evaluation scope | Concrete Jeva projection | Deterministic boundary / follow-up |
|---|---|---|
| RAG claim support | One claim plus retrieved text as `state`; Noul support proposition or Choice `supported / contradicted / insufficient evidence` | Check citation IDs and retrieval coverage in code; separately label no evidence vs ambiguous evidence; measure false-support rate on human labels |
| Tool-call evaluation | Redacted objective, proposed tool, argument summary, relevant state/result as text; Choice `appropriate / inappropriate / insufficient evidence` | Schema, permissions, tool existence and actual execution remain code; never let a Choice execute a tool |
| Browser action evaluation | Text projection of captured DOM and proposed action-target pair; finite appropriateness labels | Locator existence/uniqueness, approved action allowlist, page-state version and post-action readback stay deterministic; no native image-input support is established |
| Multi-turn/trajectory evaluation | A bounded ordered trace span with relevant earlier constraints; atomic Noul or rubric Score | Preserve event order, provenance and truncation accounting; do not silently drop the turn containing a constraint |
| Extraction verification | Field candidate plus relevant source excerpt; Choice among validated candidates with optional no-match | Type/range/checksum validators first; distinguish missing source and no matching value; leave writes outside the evaluator |
| Semantic CI regression | Fixed replay examples and a versioned rubric with explicit Score `values` | Deterministic gating and human approval own promotion; start informational; include per-item null/q/confidence and disagreement, not only aggregate score |
| Candidate reranking | `rank` on a small authorized candidate pool; compare with deterministic/embedding baseline | Search and authorization generate the pool; retain complete qrels and stable IDs; `top_k` does not reduce encoder/head workload |

Concrete adapter receipt proposal: provider/model IDs, code and weight revisions, rubric version, sanitized input fingerprint, candidate identities/text fingerprints, decision type, explicit values/positive index, cache/length/batch/numeric settings, conditional `q`, joint candidate probabilities, null mass, selected label, score/Noul where applicable, truncation counts, measured latency, and evaluation-label provenance. This is an **application receipt**, not a claimed native Jeva response schema.

Applicability, review routing and thresholds belong outside Jeva. Use a separately calibrated review band for ambiguity; do not make null, low maximum probability and unsupported evidence synonyms. Never average away hard authorization, safety or privacy constraints with a high semantic Score. Cache durable public rubric/tool text where appropriate; avoid retaining sensitive candidate text without consent/retention controls.

## 10. Safe offline validator design

Real upstream contracts are sufficiently visible to design a validator without running repository code. **Design only: no validator implementation or passing fixture suite is claimed.** It should be a separate standard-library-only program, never `import jeva`, never load model files or call the Hub, never execute dataset-supplied code, and never deserialize pickle/Torch artifacts.

### Proposed stages

1. Read bounded UTF-8 JSONL from an explicitly selected local input; cap file bytes, line bytes, row count, candidates, text length and aggregate text size. If gzip is allowed, cap decompressed bytes. Reject duplicate JSON keys, blank lines, non-object rows, NaN/Infinity and duplicate record IDs.
2. Validate a versioned allowlist covering the verified E schema. Enforce the stricter documented intersection: `K >= 2`; Noul has exactly two options and positive index 0/1; only Choice can enable null; Score has explicit finite values. A training-compatible mode additionally requires strictly increasing Score values; do not silently impose that as an upstream inference rule.
3. Check `target_probs` length `K+1`, finite nonnegative numeric values excluding booleans, normalization within the documented tolerance, zero null mass for closed sets. Reject ambiguity rather than auto-normalizing an invalid source record. Distinguish evaluation labels from training shorthand (`target_index`, `p_true`, scalar `score`).
4. Resolve corpus references only against one bounded local corpus; reject missing/duplicate IDs, inconsistent inline/reference values, path traversal and symlinks outside the selected root. Candidate IDs remain identity metadata and must not be injected into option text by accident. Preserve repeated texts when distinct candidates intentionally share text.
5. Project exactly the verified `VISIBLE_FIELDS` into a model-input preview; retain targets/qrels outside it. Produce canonical JSON/fingerprints and a redacted validation report. A stdlib validator can enforce byte/character caps but **cannot certify tokenizer-token lengths** without the exact tokenizer; mark token budget unknown rather than estimating it as verified.
6. Optionally validate a supplied recorded prediction without calling a model: align ordered labels; ensure conditional q sums to one, joint/null mass consistency, `candidate_probabilities` equals q, valid type-specific fields, correct Noul/Score mapping, `confidence=max(joint)` and null-first/candidate-first tie rules. Report missing fields and tolerance violations, not invented predictions.
7. For recorded permutation runs, move complete candidate metadata, keep null index fixed, align probabilities by identity, and separately compute per-item any-flip, all-order accuracy, mean aligned TV, maximum drift and tie incidence. Do not claim passing permutation tests from mathematical symmetry alone.

### Required offline fixture cases before adoption

- Clear valid Choice/Noul/Score schemas and one actual null label.
- `null_probability` versus `noul` confusion, conditional-versus-joint confusion, and open Noul/Score rejection.
- Boolean disguised as numeric label/index, nonfinite numbers, malformed probability sums, wrong K+1 shape, duplicate IDs/JSON keys.
- Mapping-key string collisions, repeated raw option text, permuted positive index, permuted Score values, exact ties and near ties.
- Missing source evidence vs a valid none-of-the-candidates outcome; explicit applicability/review state.
- Wrong code/model identity, changed rubric values, unsupported fields and stale cached prediction provenance.
- Oversized/gzip-expanded input, missing corpus references, metadata leakage into model-visible state, and unknown token budget.

Fixture success would establish deterministic contract behavior only; it would not establish Jeva accuracy, calibration, actual cache reuse, GPU compatibility, or paper metric reproduction.

## 11. Follow-up experiments and adoption gates

Keep these separate from implemented source contracts and from paper results:

1. **Contract gate:** implement the offline validator and adapter tests; reproduce exact public output mapping from controlled fake distributions without importing Jeva. Record fixtures as synthetic, not model observations.
2. **Runtime gate:** after separate authorization, provision the pinned checkpoint and compatible environment, preserve notices, run kernel checks and a minimal real inference. Verify all three types, genuine no-candidate cases, serialized output, local-only loading and no external calls.
3. **Task calibration:** use independently human-labeled representative examples, including missing evidence, ambiguous valid candidates, out-of-domain and adversarial content. Report false passes, false blocks, null precision/recall, coverage, probability calibration, review rate and subgroup slices. No threshold is justified by the paper's unrelated benchmark alone.
4. **Permutation gate:** original/reverse/seeded random orders, aligned IDs, explicit ties/near ties, complete metadata movement; calculate the missing any-flip/all-order/TV metrics independently. Test Score algebra separately from an ordinal-rubric workflow.
5. **Cache gate:** identical request streams under none/set/hybrid, cold resets and cyclic mode order, newly assembled sets at zero/partial/full reuse, separate priming time, strict revision/settings identity and invalidation. Compare every decision as well as probability drift; choose tolerances from observed precision and margins, not the paper maximum as an automatic allowance.
6. **Scaling gate:** paired identical queries across nested pools, explicit full-support denominators and multi-positive labels, fixed runtime settings, peak memory, p50/p95 and cold/warm distinction. Compare candidate-generation plus reranking against full-set scoring. Do not infer thousand-option deployment feasibility from a linear asymptotic bound alone.
7. **Training gate:** use the public trainer only as documented adaptation; independent holdout, no semantic leakage, explicit score ordering, new output directory, cache invalidation and post-training recalibration. Original curriculum/auxiliary reproduction remains blocked on missing recipes/data/results.
8. **Operational gate:** advisory/shadow first, no autonomous external mutations or production routing changes. Keep deterministic authorization and human approvals independent of all learned outputs. A null or high-confidence Choice is not authorization.

### Final evidence status

- **Verified by retrieval/static inspection:** complete paper text coverage; pinned code/model metadata; actual API/schema/call graph; implemented coverage and cache paths; training/evaluation differences; separate code/weight/base licenses; absent tracked test suite/lockfiles; command parser definitions.
- **Verified by simple independent arithmetic only:** selected printed ratios/count percentages, not experimental data.
- **Unverified by design:** model loading, dependencies, tensor integrity, GPU kernels, inference outputs, statistical metrics, full dataset provenance, training reproduction, cache/permutation correctness in a live runtime, application-specific calibration.
- **Blocking a reproduction claim:** unavailable prepared benchmark data and saved results in the inspected repository (ED L3–6), unreconciled 46/50 sample count, missing original curriculum/auxiliary recipe, and no authorized model execution. None blocks use of this document as a public-safe research reference.
