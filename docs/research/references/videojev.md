# VideoJev: evidence-grounded integration reference

## 1. Decision, identity, and evidence boundary

**Adoption mode: reference now; a separately reviewed, opt-in video-inference adapter later.** VideoJev is a third-party video decision model, not the TypeSafe Jev service, not a TypeSafe endpoint extension, and not evidence that an existing `/jev` command accepts video. Its inspected public interface implements **temporal grounding** and **single-choice video question answering**. Neither its name nor its System One framing grants streaming, tool execution, browser control, authorization, calibrated probabilities, or arbitrary typed-decision support.

This is a source-and-paper review, not a runtime reproduction. No repository Python or shell scripts, dependency installers, tests, model downloads, training, inference, or hosted model calls were executed. Benchmark values below are **author-reported and unreproduced**. Source inspection establishes implementation structure, not operational readiness or free inference.

### Immutable primary sources

- Paper: [arXiv:2610.18615v1 full HTML](https://arxiv.org/html/2610.18615v1), [versioned PDF](https://arxiv.org/pdf/2610.18615v1), *VideoJev: System One Model for Video Understanding and Interaction*.
- Repository: [MCG-NJU/VideoJev](https://github.com/MCG-NJU/VideoJev), default branch `main`; GitHub `repos/MCG-NJU/VideoJev/commits/HEAD` returned **`7f8b38aa7df67721303cdc61f06d8435f3c7db89`**, independently matched by the shallow clone's `git rev-parse HEAD`. All GitHub links below bind to this commit.
- [Pinned README](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/README.md).
- Released 4B checkpoint: [`ZhuYuhan/VideoJev-4B` at `1c1a253bf90dfa66176124d25a48ffb791d517d5`](https://huggingface.co/ZhuYuhan/VideoJev-4B/tree/1c1a253bf90dfa66176124d25a48ffb791d517d5), based on `Qwen/Qwen3.5-4B`.
- Released MoE checkpoint: [`ZhuYuhan/VideoJev-35B-A3B` at `70ac2122552474faec6b79774322214695699b4f`](https://huggingface.co/ZhuYuhan/VideoJev-35B-A3B/tree/70ac2122552474faec6b79774322214695699b4f), based on `Qwen/Qwen3.6-35B-A3B`.
- Both model repositories' model cards, usage guides, configuration, LICENSE, NOTICE, and safetensors index metadata were read without fetching weights. Their `modeling_videojev.py`, `processing_videojev.py`, `videojev_video.py`, and `videojev_temporal.py` were fetched as text and compared byte-for-byte with the pinned GitHub files: all four matched for both releases. This is a bounded code comparison, not verification of every checkpoint artifact or tensor.

### Full-paper reading coverage

The complete HTML was fetched, and the complete PDF text was also read, including material that the initial web extraction truncated. References here use stable section/figure/table identifiers rather than guessing PDF page positions.

| Coverage | Material read and interpretation |
|---|---|
| Abstract and §1 | Motivation, direct decisions, repeated queries, claimed benchmark gains; agent examples are motivation rather than deployed integrations. |
| §2.1–2.4; equations 1–8 | Shared scorer, marker tokens, prefix sharing, interval labels/bounds, BCE and duration-weighted Soft IoU, maximum-sum span decoding, QA softmax/CE, permutation, two-stage data/training recipe. |
| §3.1–3.5; Tables 1–8 | Full setup, both tasks and all seven benchmarks, timing denominator, autoregressive control, Cached/Joint comparison, joint-task training, Soft IoU, final-MLP removal, training schedule, scaling and calibration. |
| §§4–6 | Related work, future extensions, streaming/reliability limitations, conclusion. There is no standalone section titled “Limitations”; relevant limitations are distributed across §3.5, §5, and Appendix B. |
| References 1–63 | Bibliography read as citations; the cited papers were not themselves all reviewed. |
| Appendix A.1 | Full timing protocol, warm-up, hardware, excluded costs, output caps, stratified query-scaling experiment and bootstrap protocol. |
| Appendix A.2 | Full prediction-quality protocol, source versus newly measured baseline scores, context differences, parsing and invalid-output rules. |
| Appendix A.3 | Matched-data autoregressive control: 404,037 questions / 58,424 videos, one epoch / 546 updates, FSDP2, answer-token CE, independent query branches and output limits. |
| Appendix A.4 | Independent cache branches versus causal concatenation; direct one-token baseline; empty answer-history behavior and option masking. |
| Appendix B; Figures 6–13 | All eight case descriptions and captions read; all eight original figure images visually inspected, including model disagreement and shared failure. |

**Remaining visual boundary:** Figures 1–5 were read through their extracted labels, captions, and surrounding explanation, not independently rendered pixel-by-pixel. The HTML rendering omits or incompletely exposes some figure content; the PDF text was used to recover it. No benchmark source videos were watched, and no qualitative label was independently adjudicated. Figure 10's caption says “six options,” but the actual image displays five, A–E; do not derive an option-count contract from that caption.

## 2. Paper ideas: what is learned and what is only proposed

### Shared decision architecture

[§2.1](https://arxiv.org/html/2610.18615v1#S2.SS1) replaces autoregressive answer decoding with a cosine candidate scorer. The final language-layer MLP is bypassed; `<|option_end|>` marks each candidate readout, and `<|decide|>` marks a query readout. Separate learned projections map the two hidden states into 512 dimensions, L2-normalize them, and compute `10 * dot(query, candidate) + learned_bias`. The two marker embeddings start from `<|im_end|>`.

Video tokens precede the instruction, query and candidate list. Candidates are either timestamp strings describing frame-pair cells or textual answers. Later candidates can attend to earlier candidates. This is language-conditioned selection, not a natural-language answer generator.

### Grounding

[§2.2](https://arxiv.org/html/2610.18615v1#S2.SS2) gives each native two-frame temporal group one midpoint and one cell. Internal cell boundaries fall between neighboring frame pairs; outer boundaries are zero and the observed video endpoint. Ground-truth membership is evaluated at unrounded midpoints against the union of annotated spans. Training uses independent sigmoid/BCE membership, plus duration-weighted Soft IoU in stage two; no-positive-midpoint examples omit Soft IoU, not BCE.

Inference subtracts `log(threshold / (1-threshold))` from each logit and uses Kadane's algorithm to select a **nonempty contiguous** maximum-sum range. The paper fixes threshold `0.25`, smoothing `1`. If all threshold-adjusted logits are negative, the raw maximum-sum decoder selects the strongest single cell; default postprocessing can subsequently adjust the interval. This is not a reliable “event absent” detector, not a multiple-disjoint-events output, and not an abstention API.

### Multiple-choice QA

[§2.3](https://arxiv.org/html/2610.18615v1#S2.SS3) uses softmax over options, CE training, and argmax selection. The probabilities are conditional on the supplied candidates; they do not measure the probability that the candidate set is complete. Training permutes eligible options without using the answer to seed the permutation; position-dependent or earlier-turn-referencing questions preserve order. Inference preserves supplied order.

### Prefix reuse and future work

- **Paper Cached inference:** encode and language-prefill a fixed video once; each arriving query independently branches from that prefix. No accumulated query/answer history belongs to the branch.
- **Paper Joint inference:** append multiple question/candidate suffixes after a shared prefix and read all decisions in one causal forward. Later queries see earlier query/candidate text; they are not attention-isolated. No predicted or reference answers are appended.
- **Not implemented by the name alone:** streaming incremental vision, bounded long-running streaming memory, autonomous procedural monitoring, general action selection and computer use are extension directions in [§5](https://arxiv.org/html/2610.18615v1#S5). They are not demonstrated endpoint capabilities.

## 3. Actual released inference call graph

The Hugging Face architecture is `VideoJevForVideoUnderstanding`; configuration class is `VideoJevConfig`, `model_type='videojev'`, with native `qwen3_5` or `qwen3_5_moe` subconfig. There is no new processor class named `VideoJevProcessor` in the inspected processing module: `AutoProcessor` supplies the native processor and this module supplies helper functions. See [configuration, lines 5–35](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/configuration_videojev.py#L5-L35).

### Released video-file path, step by step

| Step | Exact source and observed behavior |
|---|---|
| Entry | [`predict_video`, modeling lines 168–174](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/modeling_videojev.py#L168-L174): validates an optional threshold, calls `prepare_video`, encodes the video, then calls `predict_features`. Defaults: `fps=2.`, `max_frames=2048`, `context=262144`, `threshold=None`. |
| Duration and geometry | [`prepare_video`, processing lines 107–137](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/processing_videojev.py#L107-L137): probes stream/container duration with PyAV; calls `read_video`; reserves `context * 4 // 5` for visual tokens; binary-searches native resize geometry with a 640×640 **area cap**, not an independent maximum on each image dimension; fails if minimum geometry cannot fit. Native processor samples no additional frames. |
| Sampling and decoding | [`sampling_grid` / `read_video`, lines 7–75](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/videojev_video.py#L7-L75): fixed requested-fps grid unless the frame cap forces uniform full-video sampling. Decode original-resolution RGB, select nearest PTS frame, prefer earlier frame on a tie, reject missing/seriously nonmonotonic PTS and empty video. Clamp sampled duration to actual decoded support; a header mismatch can trigger resampling. Full source decoding is still performed. |
| Temporal cells | [`pair_timeline`, lines 56–73](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/videojev_temporal.py#L56-L73): centers and bounds derive from the requested/effective sampling grid, not rounded timestamp display strings. Odd final frame pairs reuse the last actual grid time. |
| Vision | [`encode_video`, lines 103–120](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/modeling_videojev.py#L103-L120): accepts exactly one video grid, verifies patch count, processes 16 temporal groups per chunk by default, returns concatenated native vision `pooler_output`. Chunked vision does not mean the input video was streamed with constant host RAM. |
| Prompt construction | [`suffix` / `native_inputs`, lines 16–60](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/processing_videojev.py#L16-L60): accepts only grounding/choice; rejects blank/non-string query or option text and `<|` control-token syntax; choice needs at least two options. Copies native video timestamp text for grounding, validates native midpoint agreement and token/grid counts, includes video only in first query, and concatenates subsequent user turns without generated answers. |
| Joint grouping | [`prepare_query_groups`, lines 63–104](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/processing_videojev.py#L63-L104): requires questions and context ≥64, checks IDs, greedily groups intact questions using token lengths rounded up to a 64-token boundary. A single oversized question raises an error instead of truncating/skipping. Constructs per-query readout indices, masks and task integers. |
| Language/scoring | [`forward`, lines 122–165](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/modeling_videojev.py#L122-L165): one unpadded video/query group, native visual-token replacement and MRoPE, causal language forward with **`use_cache=False`**, candidate/query hidden-state gathering, then FP32 cosine head. Grounding is sigmoid; choice is masked softmax. |
| Architecture and precision | [`CosineDecisionHead`, lines 33–46; model setup lines 68–98](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/modeling_videojev.py#L33-L98): removes final MLP and its post-attention layer norm, keeps the head in FP32. `prepare_for_inference` also converts vision to FP32 and MoE routers to FP32, optionally installs XTuner experts, then sets eval/no-grad. Computation uses BF16 CUDA autocast where implemented. |
| Group execution | [`predict_features`, lines 177–188](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/modeling_videojev.py#L177-L188): iterates groups, reusing **vision features**, not a persistent language prefix cache; each group runs its complete prefix and suffixes again. |
| Output | [`format_predictions`, lines 140–156](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/processing_videojev.py#L140-L156): strips padding, returns probabilities and a selected interval or option. High-level outputs omit logits, timestamps, bounds, duration and cache handles. |
| Grounding postprocess | [`decode`, lines 83–124; `postprocess_interval`, lines 7–38](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/videojev_hf/videojev_temporal.py#L7-L124): maximum-sum nonempty range; default `round_repair_clamp_v1` rounds seconds with Python ties-to-even, repairs collapsed intervals using overlap-weighted shifted evidence, and clamps to video duration. Subsecond boundaries are not promised by the default output. |

**Important API gap:** neither `predict_video` nor `predict_features` exposes `mode='cached'`, `cache_id`, a cache object, or a streaming append method. Calling `predict_video` repeatedly redoes preprocessing and vision encoding. Calling `predict_features` repeatedly can reuse supplied visual embeddings but still recomputes the language prefix. Do not describe either as the paper's full KV/DeltaNet Cached inference.

### Where genuine prefix caching exists

The dense training/research implementation has a separate, inspectable cache path:

1. [`decision_benchmark.predict_decisions`, lines 19–44](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_benchmark.py#L19-L44) selects `model.video_cache(max_tokens=147456)` when the model actually has that method, removes labels and invokes the model. The capability check is explicit.
2. [`MultiturnTimeJev.forward`, lines 36–44](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/multiturn_model.py#L36-L44) sends single-question calls to the timestamp-option parent; multi-turn episodes cannot use a persistent cache. [`decision_model.from_config`, lines 111–140](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_model.py#L111-L140) selects this dense path or its RGB subclass from validated configuration.
3. [`AsymmetricVideoMemoryTimeJev.forward`, lines 262–280](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/asymmetric_video_memory.py#L262-L280) resolves an active cached prefix; `_encode_video_sample` creates native `DynamicCache` KV plus convolution/recurrent states and prefix metadata ([lines 282–318](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/asymmetric_video_memory.py#L282-L318)).
4. [`TimestampOptionMemoryTimeJev._cached_logits`, lines 83–93](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/timestamp_option_memory.py#L83-L93) embeds only each suffix, forks the prefix cache and scores suffix candidate/readout states for **both** tasks.
5. [`_fork_prefix_cache`, lines 105–117](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/asymmetric_video_memory.py#L105-L117) shares immutable attention KV but clones mutable dictionary-held Delta states. The attention continuation concatenates prefix KV without updating the original ([lines 67–86](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/asymmetric_video_memory.py#L67-L86)).
6. [`video_cache` / `_resolve_cached`, lines 361–426](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/asymmetric_video_memory.py#L361-L426) maintain an LRU prefix-token budget, track bytes/hits/evictions and clear state on context exit. Model/parameter/video/feature identity and tensor versions are checked. This token budget is not a hard bound on all temporary GPU allocations. Cache use requires eval and no-grad ([memory_reader lines 20–24](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/memory_reader.py#L20-L24)).

Do not export this research API as if it were the released HF API. It requires prepared native features, verified feature identities, packed-kernel support and compatible training-model configuration. The inspected MoE training `Qwen36Grounder` uses `use_cache=False` and does not expose the dense `video_cache` API ([qwen36_model lines 90–148](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/qwen36_model.py#L90-L148)); a usable released 35B prefix-cache integration was **not established**. This does not disprove the paper's experiments; it limits what the inspected release exposes.

A particularly misleading filename is [`scripts/evaluate_cached_contexts.py`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/evaluate_cached_contexts.py#L76-L103): it loads offline **vision** features and calls `multiturn_evaluation.predict_video`. That function explicitly carries episode indices, uses one Joint forward per intact query chunk, and keeps **no persistent KV/DeltaNet state across chunks** ([lines 35–76](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/multiturn_evaluation.py#L35-L76)). Its later report string claiming “independent questions; private KV/DeltaNet forks” does not match this call path ([lines 205–209](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/evaluate_cached_contexts.py#L205-L209)). Prefer executable behavior over that metadata label.

## 4. Actual input/output contracts

### High-level inference, not a training manifest

One call owns one video and a nonempty ordered question list. Use explicit unique string IDs even though the HF helper permits missing IDs and supplies group-local indices: indices can restart after context splitting. Explicit IDs avoid ambiguous reconciliation.

```json
[
  {"id":"event-1","task":"grounding","query":"A person opens the door."},
  {"id":"choice-1","task":"choice","query":"What does the person pick up?",
   "options":["A. A cup.","B. A book."]}
]
```

This is an input-shape example, not an evaluated video. A grounding question does not accept caller-defined temporal candidates through this API; candidates derive from frame pairs. Choice requires at least two nonempty string options; the released inference code does not enforce a four/five-option limit. Letter prefixes are ordinary text, not the returned index contract. Queries/options cannot contain `<|`.

Actual high-level result fields:

| Task | Fields | Meaning |
|---|---|---|
| Grounding | `id`, `task`, `probabilities`, `interval` | Independent sigmoid values in temporal-cell order; one `[start_seconds, end_seconds]` prediction after decoder postprocessing. Do not require the probabilities to sum to one. |
| Choice | `id`, `task`, `probabilities`, `answer_index`, `answer` | Softmax values in original option order; zero-based argmax index; exact selected option string. |

`VideoJevOutput` at the low-level tensor forward has `logits`, `probabilities`, `score_mask`; these are **not** all exposed in high-level JSON. The released output has no rationale, `confidence` field, `abstain` flag, `Noul`, `Score`, arbitrary `Choice` schema, or tool-action result. An application may derive max probability for its own review policy but must not present it as calibrated correctness.

### Labeled JSONL for training/evaluation

The separate [DATA documentation](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/docs/DATA.md#L1-L42), [`load_manifest`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/user_data.py#L11-L53), and [`validate_row`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_inputs.py#L38-L60) establish:

```jsonl
{"id":"v1/0","video_key":"v1","video_path":"videos/v1.mp4","duration":10.0,"task":"grounding","query":"A person opens the door.","spans":[[2.0,4.5]]}
{"id":"v2/0","video_key":"v2","video_path":"videos/v2.mp4","duration":12.0,"task":"choice","query":"What does the person pick up?","options":["A. A cup.","B. A book."],"answer_index":0}
```

Paths resolve relative to the manifest. IDs must be unique; `video_key` must consistently identify one path/duration, and a path cannot be assigned conflicting keys. Duration must be finite and positive. Choice labels are non-boolean integers indexing the options. Grounding labels are a nonempty list of finite increasing pairs. **Upstream deliberately permits annotation endpoints beyond media duration and does not silently clip them**; an offline validator claiming parity must not invent a `0 <= span <= duration` training-label restriction. Prediction bounds are a different contract.

The optional existing `media_source` has `kind` (`video`, `frames_sidecar`, `frames_4fps`) and `path`, but supporting sidecar metadata requires the actual RGB protocol, not arbitrary image lists. Official QA scoring additionally needs `uid` for LVBench, `question_id` for the other QA benchmarks, and `task_type` / `official_duration` for MLVU. Keep source question/option ordering. These fields are evaluation metadata, not extra semantic capabilities.

## 5. Evaluation/training implementation versus paper settings

### Released evaluator

[`scripts/evaluate_hf.py`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/evaluate_hf.py) dispatches to [`timejev/hf_evaluation.py`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/hf_evaluation.py).

- `main` parses `--checkpoint`, `--revision`, `--out`, `--benchmark`, `--data-root`, `--plans`, `--manifest`, `--reference`, `--grounding-context`, `--threshold`, `--dry-run` ([lines 168–189](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/hf_evaluation.py#L168-L189)). There is no `--mode`, `--cached`, or QA context override here.
- `evaluation_inputs` checks complete official counts/tasks, QA reference presence and optional plan identity/coverage ([lines 38–86](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/hf_evaluation.py#L38-L86)). `--dry-run` returns before checkpoint download/loading, but still imports project dependencies and checks media paths. It does not validate actual decoding, CUDA, weights or prediction quality.
- `predict_rows` splits mixed manifests by task and video; constructs sampling/geometry/timeline, CPU-preprocesses frame chunks, calls `encode_video`, projects only `id/task/query/options`, and calls `predict_features` ([lines 124–165](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/hf_evaluation.py#L124-L165)). Ground truth does not enter that projection.
- RGB evaluation has its own media route: [`metadata`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/rgb_media.py#L71-L139) probes the actual tail or verifies frame sidecars; `sampled_chunks` streams raw decoded frames in groups of 32, while `preprocess` returns a **list** of processed patch chunks ([lines 168–250](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/rgb_media.py#L168-L250)). This bounds original-frame staging, not total patch memory.
- `score_predictions` rejects missing/duplicate/unknown result IDs and restores manifest order. Custom choice accuracy is a fraction; temporal mIoU/recall are percentages. Official QA scorers check annotation identities/order. Distributed execution shards complete videos across GPUs, rather than tensor-parallelizing a model ([lines 89–121 and 195–235](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/hf_evaluation.py#L89-L235)).

### Alignment and drift ledger

| Topic | Paper | Pinned code and implication |
|---|---|---|
| Head and loss | §2: 512-dimensional normalized scorer, scale 10; BCE/CE then BCE+2×Soft IoU/CE | Matches released head and training [`PointerHead`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/model.py#L12-L53), [`decision_losses`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/losses.py#L10-L40), and [duration loss](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_model.py#L9-L27). FP32 scores, valid-candidate normalization, per-question loss averaging and zero Soft IoU for no-positive cases are explicit. |
| Initialization/frozen stages | §2.4: std .005, zero biases, marker copy, head-only then language+head; vision frozen | `PointerHead` initializes exactly this way. Dense marker copy appears in [decision_model lines 86–96](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_model.py#L86-L96); MoE copy/freezing appears in [qwen36_model](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/qwen36_model.py#L152-L203). |
| Learning schedule | §3.1: GBS64, one epoch/stage, AdamW, decay .01, clip1, 5% warm-up, final LR10%; head 3e-4/1e-4; backbone 5e-6/2e-6 | Dense [`validate_recipe`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/train.py#L55-L72), [optimizer/schedule](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/staged_training.py#L10-L27), and [35B recipe](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/qwen36_recipe.py#L4-L45) align. Update counts are computed from prepared pack plans, not an unconditional promise of 160/375 for custom data. |
| Dense training route | §3.1: 147456-token packs, ZeRO-2 | [`configs/head_only.json`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/configs/head_only.json) / [`joint.json`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/configs/joint.json) match. However public custom [`prepare_data`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/prepare_data.py#L31-L56) selects **RGB192**, whose [config](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/configs/rgb192_joint.json#L1-L40) uses **196608 tokens and ZeRO-3**. The public custom-data recipe is not identical paper reproduction. |
| MoE training | 147456 tokens, ZeRO-3, frozen vision | [qwen36 configs](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/configs/qwen36_joint.json) and [trainer](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/scripts/train_qwen36.py#L169-L238) use this scheme, with replicated frozen vision outside ZeRO, FP32 parameters/routers and BF16 computation. XTuner grouped experts are required for this training path. |
| Permutation | §2.3: reproducible answer-independent permutation, exceptions for option/turn references | [`qa_option_permutation.py`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/qa_option_permutation.py#L33-L119) implements this. Custom `prepare_data` preserves input order and removes the permutation config entry; it does **not** automatically apply this paper preprocessing. |
| QA evaluation | §3.3/A.2: 2fps, ≤2048 frames, 262144 tokens, frames only | Matches released evaluator and [QA_CONTEXT](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/qa_eval_settings.py#L6-L8). An 8192-token README demo is intentionally not the benchmark protocol. |
| Grounding evaluation | A.2: 4fps, 147456 context, 114688 input budget; A.1 latency uses 262144 context | Released evaluator defaults to 147456 and uses geometry budget logic, not a literal 114688 cap; it additionally enforces ≤2048 frames via RGB metadata. For long inputs, effective fps may fall below 4. Do not claim the generic HF prediction defaults reproduce either paper protocol exactly. |
| Decoder | Paper fixes .25/smooth1 for every reported experiment | Released config defaults match. MoE training configs still list smoothing candidates `[1,3,5]` ([config lines 26–33](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/configs/qwen36_joint.json#L26-L33)); this broader configuration must not silently replace the fixed paper protocol. |
| Cache mode | Paper measures both sizes in Cached and Joint modes | Released HF convenience API is Joint plus vision reuse. Dense native-prefix cache machinery exists separately. No released HF mode switch or established 35B cached adapter. |
| Timing | A.1 synchronized model forward only, preprocessing/transfers/postprocessing excluded | Released HF evaluator is a quality evaluator, not the complete Table1/2 synchronized latency harness. Legacy [decision_benchmark timing](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/timejev/decision_benchmark.py#L70-L90) explicitly includes feature reads and input construction. Those timings are not interchangeable. |

The trainers were read through configuration validation, model/data selection, optimizer creation, loss normalization, update loop, head handoff and checkpoint export. The full training dataset, pack manifests and experiment logs needed to bind every released tensor to every paper cell were not available in this intake. Approximately 240K QA examples are described as internally curated in §2.4; public training code is not proof that this corpus is distributable or that exact retraining can be reproduced.

## 6. Benchmark claims — original, unreproduced

Source: [§3, Tables 1–2](https://arxiv.org/html/2610.18615v1#S3) and [Appendix A](https://arxiv.org/html/2610.18615v1#A1). Values are author-reported percentages, except seconds.

| Grounding, TimeLens-refined annotations | Queries | 4B mIoU | 35B-A3B mIoU |
|---|---:|---:|---:|
| Charades-STA | 3363 | 60.1 | 63.7 |
| ActivityNet Captions | 4500 | 62.8 | 65.5 |
| QVHighlights | 1541 | 73.2 | 74.0 |
| Paper three-benchmark mean | — | 65.3 | 67.7 |

Grounding also reports rank-one recall at IoU .3/.5/.7. Mean mIoU improvements versus the respective Instruct backbones are 6.7 and 10.8 percentage points. Reported model-forward latency per query on full Charades is .276s / .336s, versus .763s / 1.054s for the corresponding backbones.

| Video QA, no subtitles/audio | Questions | 4B score | 35B-A3B score |
|---|---:|---:|---:|
| LVBench test | 1549 | 67.9 | 73.4 |
| Video-MME test | 2700 | 75.0 | 81.8 |
| LongVideoBench validation | 1337 | 73.6 | 77.1 |
| MLVU development, seven-task M-Avg | 2174 | 80.6 | 85.9 |
| Paper four-benchmark mean | — | 74.3 | 79.5 |

The QA mean combines benchmark accuracies and MLVU's task-balanced M-Avg; it is not pooled accuracy over all questions. Improvements over corresponding Instruct means are 8.0 / 5.7 points. Compared with Thinking means 74.9 / 78.8, differences are −0.6 / +0.7 points.

**Timing scope matters:** Appendix A.1 uses an initially idle single H200, batch size one, untimed warm-up, and per-query amortization over all queries for a video. Counts are 1313 Charades videos / 3363 queries and 103 LVBench videos / 1549 questions. Video loading/decoding, preprocessing, transfer, parsing and metric computation are excluded. Generative baselines also share the video prefix. Model-family visual settings can differ. Grounding timing and quality use different context budgets.

Independent arithmetic on the printed latency values gives 2.764× / 3.137× grounding speedups and 129.055× / 100.319× QA speedups versus **Thinking** (.1-scale rounding in the paper is consistent). Against **Instruct** QA latency, the ratios are only 1.207× / 1.593×. Arithmetic validation is not benchmark reproduction, and “100× faster” is not an end-to-end or all-baseline claim.

Other findings that affect integration:

- Table3 matched-data, single-stage control favors VideoJev by 1.3 mean grounding / 1.9 mean QA points; it does not by itself prove production agent success.
- Table4 Joint versus Cached improves means by .8/.5 points at 4B and .3/.7 at MoE. This does not prove order independence or safe cross-user batching.
- Tables5–8 cover task sharing, Soft IoU, final MLP, and schedule. Two-stage is not best on every metric: the single-stage variant has slightly higher overall means.
- Figure3 timing uses 40 stratified videos per task, including Video-Holmes for QA timing, while end labels show separately measured full-LVBench quality. Do not conflate those populations. One-to-ten-query marginal timing is not a throughput guarantee for arbitrary videos.
- §3.5 reports overconfidence: mean ECE 8.65 / 8.13 percentage points, ten equal-width bins, no calibration-specific training. A high max softmax value is not a calibrated correctness guarantee.
- Appendix B includes a high-confidence 4B intent-selection disagreement and both models failing small-object counting. These are real reported limitations, not only hypothetical risks. Selected success images are not independent evaluation.

## 7. Commands and model prerequisites

**All commands below are documentation/source-verified examples, not commands executed in this review.** Run only after explicit approval of model access, licenses, compute cost, and handling of video data. Public weights do not imply free hosted inference or zero GPU cost. Do not upload confidential videos to the public demo.

### Environment declared upstream

[README lines 154–165](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/README.md#L154-L165) specifies Python3.12, PyTorch2.8/CUDA12.8, Triton3.4, FlashAttention2 and causal-conv1d. [`requirements-overlay.txt`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/requirements-overlay.txt) pins Transformers5.14.1, DeepSpeed0.19.7, flash-linear-attention0.4.2, fla-core0.4.2 and PyAV18.1.0, among others. [`requirements.txt`](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/requirements.txt) adds range/unpinned dependencies such as NumPy, Pillow, safetensors and accelerate. This is not a complete hash-locked CUDA environment.

The literal upstream environment commands are:

```bash
pip install -r requirements.txt
source scripts/env.sh
```

These are **not sufficient before installing the matching CUDA-specific prerequisites**, and they were not run. The model cards publish a lighter inference dependency recipe. Training additionally requires the [pinned XTuner source](https://github.com/InternLM/xtuner/tree/76e705134521eff867b409f3b3451df1c4d8dd36); MoE training requires compiled grouped-GEMM/token-permutation support. Default released HF inference does not enable optional XTuner experts unless `prepare_for_inference(xtuner_experts=True)` is requested. Do not conflate training requirements with default released inference requirements.

### Exact upstream evaluation command

From [README lines 199–208](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/README.md#L199-L208):

```bash
source scripts/env.sh
python scripts/evaluate_hf.py \
  --checkpoint ZhuYuhan/VideoJev-4B \
  --manifest /path/to/eval.jsonl --out runs/eval4b
```

The manifest and media must exist; this command may download weights and custom Python. It is not an offline validator and was not executed.

A source-supported **pinned variant** adds the real `--revision` flag; the following is an adaptation, not a verbatim upstream block:

```bash
python scripts/evaluate_hf.py \
  --checkpoint ZhuYuhan/VideoJev-4B \
  --revision 1c1a253bf90dfa66176124d25a48ffb791d517d5 \
  --manifest /path/to/eval.jsonl --out runs/eval4b-pinned
```

Use the 35B repository and its own revision for that model. Use a fresh output directory; an existing `summary.json` is rejected. Custom result files are under the `custom` subdirectory; `summary.json` is at the output root. Official benchmark names are `charades`, `activitynet`, `qvhighlights`, `lvbench`, `videomme`, `longvideobench`, `mlvu`, plus aggregate selectors `vtg` and `all`.

The real preflight flag can be appended:

```bash
python scripts/evaluate_hf.py \
  --checkpoint ZhuYuhan/VideoJev-4B \
  --manifest /path/to/eval.jsonl --out runs/eval4b-preflight --dry-run
```

This stops before loading weights, but still executes third-party source/imports. It was not run in this review and should not be mistaken for a pure standard-library validator.

### Actual Python inference surface

The following adaptation of the [pinned quick start](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/README.md#L76-L105) pins the model revision and substitutes a caller-owned local video. It is **not runtime-tested here**:

```python
import json
import torch
from transformers import AutoModel, AutoProcessor

repo = "ZhuYuhan/VideoJev-4B"
revision = "1c1a253bf90dfa66176124d25a48ffb791d517d5"
processor = AutoProcessor.from_pretrained(
    repo, revision=revision, trust_remote_code=True,
)
model = AutoModel.from_pretrained(
    repo, revision=revision, trust_remote_code=True,
    dtype=torch.bfloat16, device_map={"": "cuda:0"},
    attn_implementation="flash_attention_2",
)
model.prepare_for_inference()
questions = [
    {"id": "event-1", "task": "grounding",
     "query": "A person opens the door."},
    {"id": "choice-1", "task": "choice",
     "query": "What does the person pick up?",
     "options": ["A. A cup.", "B. A book."]},
]
results = model.predict_video(
    processor, "/path/to/video.mp4", questions,
    fps=2.0, max_frames=2048, context=8192,
)
print(json.dumps(results, indent=2))
```

This mixed-task small-context example tests neither paper benchmark protocol. For task-specific settings, the inspected [4B usage guide](https://huggingface.co/ZhuYuhan/VideoJev-4B/blob/1c1a253bf90dfa66176124d25a48ffb791d517d5/USAGE.md) and [35B usage guide](https://huggingface.co/ZhuYuhan/VideoJev-35B-A3B/blob/70ac2122552474faec6b79774322214695699b4f/USAGE.md) use grounding `fps=4.0, max_frames=2048, context=147456`, QA `fps=2.0, max_frames=2048, context=262144`. A per-call `threshold=...` changes grounding decoding only, not the probabilities or choice result.

`trust_remote_code=True` is an explicit executable-code trust decision. Pin both code and model artifacts, review the exact snapshot, and isolate execution. A GitHub SHA alone does not pin the Hugging Face code fetched by `from_pretrained`. Training `.pt` loaders use `torch.load(..., weights_only=False)` on some paths; accept only trusted training checkpoints, not arbitrary uploads.

## 8. Licensing and resource constraints

### Code and weights are separate checks

| Artifact | Observed license evidence | Boundary |
|---|---|---|
| GitHub code | [LICENSE](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/LICENSE), Apache2.0; [NOTICE](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/NOTICE) identifies Qwen/Transformers/XTuner components | Preserve required license/notice attribution and mark modifications when distributing derivatives. Not a warranty or trademark grant. |
| 4B checkpoint | Pinned model-card `license: apache-2.0` and [separate LICENSE](https://huggingface.co/ZhuYuhan/VideoJev-4B/blob/1c1a253bf90dfa66176124d25a48ffb791d517d5/LICENSE) / NOTICE | Verified by reading the checkpoint's own license, not inferred solely from the code license. |
| 35B-A3B checkpoint | Pinned model-card `license: apache-2.0` and [separate LICENSE](https://huggingface.co/ZhuYuhan/VideoJev-35B-A3B/blob/70ac2122552474faec6b79774322214695699b4f/LICENSE) / NOTICE | Same separation; base-model and dependency notices still apply. |
| Videos, training corpora, benchmarks and public demo | Separate rights and provider terms | Model/code licensing does not grant rights to upload, redistribute, retain or train on arbitrary video or the internally curated QA data. No demo service-cost or availability guarantee was verified. |

### Resource implications

- Upstream model cards report testing with an H200 and the CUDA stack above. CPU or Apple MPS deployment was not established by this review. Some helper branches accept non-CUDA tensors; that is not evidence of a supported whole-model CPU/MPS path.
- Safetensors indexes report **8,942,213,122 bytes** for 4B and **67,583,480,546 bytes** for 35B-A3B: about **8.94GB / 67.58GB decimal weight payload**. These are index metadata, not measured downloads or minimum VRAM. Activations, vision FP32 conversion, FP32 head/routers, allocator/workspaces and long context add memory. “A3B active” does not mean only 3B parameters must be stored.
- The high-level helper holds sampled original-resolution RGB frames before resizing. A 2048-frame cap does not bound RAM independently of source resolution. Decode time is not bounded by the number of selected frames: the decoder iterates the source stream.
- Both released configs declare 262144 maximum positions. Do not accept larger `context` values merely because a Python parameter accepts an integer. Choose an operational cap no larger than the verified model/runtime limit, and separately cap bytes, duration, resolution, question count, option lengths and concurrency. These are proposed application limits, not existing VideoJev fields.
- Geometry and question grouping can reject oversized requests. Splitting query groups repeats language prefix work and can change later-query context; reordering questions/options can change scores. Keep ordering and grouping provenance.
- No minimum GPU-memory matrix, tested low-end GPU latency, quantization route, multi-GPU model sharding guarantee, or streaming SLA was established. `torchrun` evaluator distribution means independent complete-video workers, each needing its own loadable model.
- Feature/prefix caches contain derived video information. Keep per-video and per-authorization isolation, bounded lifetime, explicit deletion, and invalidation on model/media/sampling changes. Do not batch unrelated principals into Joint causal context.

## 9. `/jev` selection and integration rules — recommendations, not implemented capabilities

1. **Select by actual evidence modality and output contract.** Use this candidate only when the authorized evidence is a video and the decision is either “where in this video does this described event occur?” or “which supplied answer best matches this video?” For text-only semantic judgments, retain the selected text-capable Jev interface; do not route to VideoJev merely because the names overlap.
2. **Treat the adapter as unavailable until explicitly implemented and verified.** This reference does not add a `/jev video` command, a provider registration, a TypeSafe request field, or an endpoint. Never forward videos to a text endpoint or reinterpret TypeSafe question types as VideoJev task names without an actual adapter contract.
3. **Separate candidate planning from scoring.** A higher-level planner may propose observable hypotheses/options; deterministic code checks schema and approval. VideoJev selects within those supplied candidates. Reject tasks requiring invented answer text, rationales, arbitrary JSON generation, audio understanding or streaming increments.
4. **Grounding is localization, not proof of existence.** Because a nonempty interval is mandatory, absent-event handling needs a separately validated policy or another model/decision step. Do not make a returned span alone certify that an event occurred. Do not merge repeated disjoint events into an invented multi-span result.
5. **Use explicit IDs and preserve question/option order.** Joint mode is efficient but later queries can see earlier text. For independence requirements, a separate singleton call can isolate query text at extra cost; it does not automatically gain the paper's prefix-cache efficiency. Enable true caching only after verifying that exact model class/path and cache isolation.
6. **Keep judgments advisory until calibrated.** Use human-labeled representative video data, including absent events, short transitions, small objects, long clips, ambiguous options, option-order changes, related-query contamination and unreadable frames. Measure temporal overlap, classification accuracy, false accept/reject, calibration and review coverage. An “unknown” textual option is only another candidate, not a built-in abstention guarantee.
7. **Keep all side effects outside the model.** Tool execution, permissions, consent, publication, browser actions and workflow-state transitions remain deterministic/human-approved. Visual scores never grant account access or authorize actions.
8. **Require explicit compute and data approval.** Weight acquisition, remote-code execution, GPU use and paid hosting are separate opt-ins. Default tests remain offline and independent of model credentials or network inference. There is no assumption of unpaid inference.
9. **Keep a separate integration receipt.** Record the public code/model revision, input contract version, media provenance, preprocessing choices, task/query order, decoder settings, hardware/runtime and result-validation status. Such receipt metadata belongs to the adapter, not to invented fields passed into the upstream model.

## 10. Offline-validator recommendation, limited to observed fields

A small standard-library validator is a suitable first integration artifact, **not supplied or executed in this research review**. It should parse JSON/JSONL without importing the repository, Transformers or torch, without loading weights, and without network calls. Keep two schemas separate: unlabeled inference questions and labeled evaluation manifests.

Recommended checks grounded in the source:

- Inference: nonempty question list; explicit unique string `id` as a stricter adapter requirement; `task` in `grounding`/`choice`; nonblank string `query`; no `<|` in query/options; choice `options` is a list of at least two valid strings. Treat stricter option uniqueness/length budgets as adapter policy, not upstream requirements.
- Manifest: `id`, `video_key`, `video_path`, `query`, finite positive `duration`; unique IDs and consistent video identity; required `spans` or `answer_index` according to task, exactly as described above. Fail on NaN/Infinity and boolean masquerading as an index. Preserve legitimate out-of-duration annotation endpoints instead of silently repairing them.
- Optional media sources: validate only the observed `kind`/`path` structure. Do not claim actual frame-sidecar identity or decode validity from shape validation alone. Local path existence and authorized-root containment may be separate opt-in filesystem checks; containment is application policy because upstream resolves paths without such a sandbox.
- Results: match input IDs/count/order; grounding keys `id/task/probabilities/interval`, choice keys `id/task/probabilities/answer_index/answer`; finite probabilities in [0,1]; choice length equals option count, approximately unit sum, index in range, answer matches indexed option and index is an argmax; interval is two finite increasing seconds within independently known observed duration. Do not require grounding probabilities to sum to one.
- High-level grounding output lacks timestamps/bounds/duration. Without trusted preprocessing metadata, the validator **cannot** verify interval-to-cell alignment, exact grounding probability length, or decode correctness. Do not invent `fps`, `duration`, `cache_id`, `confidence`, or `timestamps` inside that response to make validation appear complete.
- An input-only validator cannot establish model calibration, real-media validity, tokenizer fit, GPU memory fit, semantic correctness, or paper reproduction. A result validator cannot prove a prediction came from real inference rather than an external producer; provenance verification is a separate concern.

Static tests worth porting as independent contracts include [high-level output-key and threshold tests](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/tests/test_hf_predictions.py), [manifest/release-input tests](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/tests/test_release_inputs.py), and [cache-scope cleanup tests](https://github.com/MCG-NJU/VideoJev/blob/7f8b38aa7df67721303cdc61f06d8435f3c7db89/tests/test_prediction_cache_context.py). These files were read, **not run**. The cache tests use stub predictors and are not evidence of full-model prefix-cache parity.

## 11. Gates before promotion

- Review and pin the complete chosen HF snapshot and dependency environment; preserve separate code/checkpoint license evidence.
- Establish authorized video input handling, compute budget and a compatible GPU environment; do not infer minimum memory from parameter count.
- Implement only the verified task/input/output fields, with deterministic validators and no changes to unrelated TypeSafe interfaces.
- Exercise a bounded authorized real-video smoke test and compare actual result coverage; preserve its real outputs, not the upstream README's recorded example as local evidence.
- Verify group splitting, explicit IDs, threshold behavior, absent-event handling, error paths and bounded resources.
- If full prefix caching is required, resolve the released HF/API gap and 35B support separately, including cache invalidation and per-request isolation tests.
- Reproduce the required benchmark or application-quality subset under a documented protocol before making speed, calibration or correctness claims. Resolve training-route and evaluation-budget differences rather than relabeling the public custom-data recipe as the paper experiment.

**Current evidence status:** full paper text and appendices reviewed; selected qualitative images inspected; pinned source call graphs and contracts inspected; key released inference files matched against pinned model snapshots; printed headline arithmetic checked. Runtime, tests, weights, benchmark reproduction, integration installation and production readiness remain unverified and were intentionally not attempted.
