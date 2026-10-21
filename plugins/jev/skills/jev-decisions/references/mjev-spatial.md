# MJev-Spatial: evidence-grounded integration reference

## Decision and evidence status

**Adopt the bounded spatial-decision design as a research reference; defer executable backend promotion.** MJev-Spatial is an independent Qwen3.5-based research model, not a capability, endpoint, checkpoint, or supported modality of the TypeSafe Jev API. It is relevant to a `/jev` selector as a separately identified, opt-in spatial backend. This review does not install that backend, implement a plugin, run inference, or establish benchmark reproduction.

The source contains a real native-attention candidate scorer, hierarchical numerical and point controllers, teacher-forced training construction, and a basic evaluator. However, the reviewed release has a declared dependency conflict, a statically identifiable checkpoint-saving defect, incomplete top-level exports/ablation paths, and unresolved correspondence between its published checkpoint metadata and the paper's final training recipe. Those are promotion gates, not reasons to erase the useful method.

Evidence labels used below:

- **Paper-reported, unreproduced:** the authors' measurements and experiments.
- **Source-observed:** behavior traced in the pinned implementation, without importing or executing it.
- **Metadata-observed:** public registry/configuration content, not tensor or runtime verification.
- **Independently checked:** arithmetic, JSON parsing, source AST parsing, and file-presence checks performed without running upstream code.
- **Proposed:** integration and evaluation designs, not an existing upstream API.

## 1. Primary sources and exact versions

| Artifact | Pinned evidence |
|---|---|
| Full paper | [arXiv HTML 2610.22276v1][paper]; [PDF alternative](https://arxiv.org/pdf/2610.22276v1) |
| Source repository | [Fr0zenCrane/MJev-Spatial at df37e9e5a3455c642f7b43cf96abc4f950b4fa6d][repo] |
| GitHub discovery | `gh api repos/Fr0zenCrane/MJev-Spatial/commits/HEAD` returned the same SHA as the shallow clone's `git rev-parse HEAD`; default branch `main`; public, not archived; releases API returned an empty list |
| Published model | [mindlab-research/MJev-Spatial-4B at 0657319c58d342f54c5108cd3c4d983a79a8b3f7][weights] |
| Model configuration | [config.json][model-config], [checkpoint.json][checkpoint], [language_model/config.json][language-config], [tensor index][weight-index] |
| Declared base model | `Qwen/Qwen3.5-4B`; configuration records revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| Package metadata | [pyproject.toml, lines 1–43][dependencies]: package version `0.2.0`, Python `>=3.10` |

The full HTML was downloaded successfully after a text-extraction response truncated. The complete body, references, appendix prose, equations, table contents and figure captions were then read from the downloaded HTML's text. Citations use HTML section/table identifiers rather than invented PDF page numbers. The PDF was not needed or read. Figures 2 and 3 were additionally inspected as images. Other figure graphics were not separately visually audited; their captions and associated tabulated results were read. External papers in the bibliography were not full-read as part of this review.

### Full-read coverage ledger

| Paper coverage | What it establishes |
|---|---|
| Abstract; §§1–2 | Motivation, System One framing, related work, distinction from earlier Molmo2-ER/LoRA prototype and from TypeSafe |
| §3.1; Table 1; Eqs. 1–5 | Finite candidates, units, scalar codebooks, three-level point geometry, multi-point extension |
| §3.2; Fig. 3; Eq. 6 | Native Q/K readout, candidate-end and decision states, reused pretrained projections |
| §3.3; Eq. 7 | Converted training corpus, teacher forcing, equal per-QA loss, length-aware scheduling |
| §§4.1–4.4; Tables 2–6 | Final evaluation, pilot ablations, latency and scheduling claims |
| §5; References | Conclusion and cited provenance; references read, not all referenced works investigated |
| [Appendix A.1–A.4](https://arxiv.org/html/2610.22276v1#A1) | Exact sequence/readout details, parameter removal, multi-point rules |
| [Appendix B.1–B.4](https://arxiv.org/html/2610.22276v1#A2); Tables 7–8 | Annotation conversion, quality audits, duplicate filtering, final task/source distribution |
| [Appendix C.1–C.3](https://arxiv.org/html/2610.22276v1#A3); Table 9 | Pilot and final optimization, distributed weighting and scheduling |
| [Appendix D.1–D.3](https://arxiv.org/html/2610.22276v1#A4); Tables 10–11 | Benchmark scoring, historical budget changes, batch-one B200 timing |
| [Appendix E.1–E.4](https://arxiv.org/html/2610.22276v1#A5); Tables 12–17 | Matched heads, subgroup failures, 24 depth/aggregation variants, layer fusion and head interventions |
| [Appendix F.1–F.2](https://arxiv.org/html/2610.22276v1#A6); Tables 18–22 | Crop removal/retraining, feature/KV replay, direct visual tokens, multi-point decoder sensitivity |
| [Appendix G.1](https://arxiv.org/html/2610.22276v1#A7); Tables 23–25 | Oracle versus learned numerical errors, coverage/granularity tradeoffs, expectation decoding |
| [Appendix H.1–H.2](https://arxiv.org/html/2610.22276v1#A8); Tables 26–27 | Scheduling diagnostics, successful/OOM profiles, limited measurement windows |

There is no separately titled limitations section in the inspected version. Limitations are distributed through these sections and are consolidated below. No substantive main-text or appendix section was intentionally omitted. Full text coverage is not a claim that every chart was visually inspected, every cited source read, or any experiment reproduced.

## 2. Method: what is actually classified

### Shared scorer

The model consumes ordered images, a question, and candidate descriptions. Choice candidates are supplied option content; scalar candidates describe intervals or exact integers; point candidates name spatial cells. An option-end marker represents each contextualized candidate; a later decision marker represents the decision after seeing all current candidates. The markers reuse existing vocabulary entries.

The selected Qwen3.5-4B implementation executes language layers 1–31, then gathers the relevant states at the input boundary of layer 32. It applies the retained native input normalization, Q/K projections, head normalization and original-position multimodal rotary embedding. Sixteen query heads share four key heads, with head dimension 256. Candidate logits are the mean of the scaled per-head Q·K scores. It averages **logits**, not per-head probabilities. Padded alternatives receive negative infinity; normalization is over legal candidates only. The final attention's unused value, gate, output and FFN paths and final model norm are removed. No new prediction head is added for `native_last_qk_mean`.

A classification decision needs one forward pass and no generated answer tokens. **A complete request is not necessarily one forward pass:** choice uses one decision; ordinary scalars one or two; a point three; multi-point expansion many more. The released greedy CLI recomputes complete accumulated sequences and disables language caching. Its incremental crops do not imply incremental KV-cache inference.

Sources: [§3.2](https://arxiv.org/html/2610.22276v1#S3.SS2), Appendix A.2–A.3, [native readout][native-qk], [model forward][forward].

### Scalar codebooks

- **Length:** meters; exact zero plus 30 positive log1p-spaced coarse intervals and an overflow root. The declared range is up to 16,384 m. The first six positive intervals have four fine cells, the remaining 24 have eight: 216 positive leaf cells. Decode the selected fine cell to its midpoint. Overflow has a distinct path but returns representative `16384.0`; consumers must not treat that representative as a measured in-range distance.
- **Count:** two 32-way decisions, decoded as `32 * coarse + fine`; integers 0–1023, not a list of points. The count controller has no length-style zero early termination.
- **Angle:** degrees; twelve positive 30-degree intervals, zero and overflow roots, 32 fine cells per positive root. Question wording must specify frame and rotation direction. Angle training targets outside [0,360] are rejected, even though inference has an overflow candidate. The historical internal key `edges_m` also appears in the angle codebook; its public unit remains `deg`.
- **Boundary policy:** positive intervals are lower-inclusive and upper-exclusive except the final finite endpoint; zero has its own class. Source uses `bisect_right` and clamps the maximum finite bin.
- **Quantization bound, not accuracy guarantee:** the length design bounds correct-cell midpoint error by `max(0.01 m, 0.05 * value)`. It does not bound model misclassification error. The actual published upper edge is floating-point `16384.000000000004`; tests should preserve the stored codebook and explicitly exercise that boundary rather than silently replacing it.

Metadata checking independently found 31 strictly increasing length edges, 30 fine-cardinality entries, 216 leaves, and satisfaction of the stated half-width design constraint at every lower edge. This checks representation metadata, not predictions. Sources: §3.1, Appendix G, [numeric controller][numeric], [geometry/decode][hierarchy], [published codebook][model-config].

### Point geometry

The original image is `[0,0,1,1]`. Each decision splits its current rectangle into 3×3 cells, in this non-row-major candidate order:

`top-center, top-left, top-right, center, middle-left, middle-right, bottom-center, bottom-left, bottom-right`.

After the first two decisions the chosen rectangle is cropped **from original pixels**, not recursively from the previous crop. The original view remains in context. The final answer is the final cell center in original-image normalized `[x,y]` coordinates: origin top-left, x rightwards, y downwards. Three decisions yield a 27×27 effective grid. A correct-cell center is within 1/54 of width and height per axis; an early wrong branch can exclude the target completely.

Coordinates are neither meters nor pixels, camera-space 3D, screen/device coordinates, nor the autoregressive baseline's [0,1000] textual coordinates. Converting to a pixel index or screen click requires an explicit application-level transform and independent validity checks; no robot calibration or actuation policy is supplied here.

Sources: §3.1, [point geometry][hierarchy], [crop and prompt][crop].

### Multiple points are a separate interface path

Appendix A.4 expands a conditional tree: 91 full decision nodes, 729 leaf cells; path mass is the product of conditional probabilities. Root pruning drops a root only below 1% of the largest root probability. Unvisited cells remain explicitly unknown and omitted mass is recorded, not redistributed. Cells at least 10% of the retained map peak are grouped using eight-connectivity; each component emits its highest-probability cell center, with deterministic topmost/leftmost ties in source.

The module [point_probability_map.py][point-map] implements this through `probability_map(builder, request, evaluate_nodes, ...)` and `component_points(...)`. **The public `scripts/predict.py` entrypoint does not call it.** `num_points > 1` is not a documented working switch to the tree decoder. A backend would need an explicit, reviewed node-evaluator adapter and separate output contract. Direct visual-token pointing also exists as an ablation with additional result fields, but is not the released crop hierarchy.

## 3. Concrete source call graph

All links in this section are commit-pinned; statements describe source, not successful execution.

| Stage | File/function and lines | Observed behavior |
|---|---|---|
| CLI request reader | [scripts/predict.py:18–32][request-reader] `load_rows`, `normalize` | `.jsonl` → one object per nonempty line; other suffix → one JSON object, not a JSON array. Accepts nested `input` or bare input. ID comes from `id`, `sample_id`, or generated request number. Relative image paths resolve against the request file's parent directory. |
| CLI setup | [scripts/predict.py:35–68][predict] `main` | Loads local checkpoint `config.json`, preserves option order, sets max image tokens to 1024 and sequence budget to at least 8192. Rejects duplicate IDs and nonpositive batch size; default device `cuda:0`. Calls processor, builder, model and `predict_batch`; prepends request ID to each result. |
| Image/token processor | [qwen35.py:42–53][processor] `make_processor` | `AutoProcessor.from_pretrained(config["base_model"], local_files_only=...)`; right padding; image size budget derived from min/max image tokens times 32×32. It does **not** load the checkpoint's saved `processor/` directory. |
| Load images, spatial text | [unified.py:165–213][crop] `load_images`, `crop`, `point_prompt`, `scalar_prompt` | Pillow opens local files and converts RGB. Crop uses `Image.Transform.EXTENT` with bilinear resampling. Point frame and interval boundary rules are in prompts. No HTTP image downloader is implemented here. |
| Candidate layout | [kev.py:91–159][builder] `KevBuilder.__init__`, `stage`, `initial_spec` | Reads checkpoint codebook and existing marker IDs, escapes control-like text, optionally shuffles choice options, records ID mapping, hashes image contents for state identity, constructs the image prefix and first decision. |
| Tensorization | [kev.py:207–337][encode] `encode_specs` | Processor receives flattened images and per-row text; padding but no truncation. Rejects over-budget sequences. Collects decision/end positions and ownership/slot mappings. At inference retains only the final decision per current row. Supports image deduplication, but published config sets `deduplicate_vision=false`. |
| Model/checkpoint loader | [kev.py:442–595][loader] `build_model` | Loads full base Qwen model in BF16 with SDPA, then replaces language model from checkpoint with `NativeQKTextModel` in FP32. Checks architecture/readout/layer/precision markers and missing/unexpected state keys; freezes vision and uses full-language mode for native Q/K. `base_revision` is recorded metadata, but is not passed as `revision=` in these loads. |
| Vision into language | [kev.py:369–390][embedding] `KevSpatialModel.embeddings` | Frozen `get_image_features(...).pooler_output`, reinsertion according to image ownership into image placeholders, native multimodal rope indices. Uses base-model vision pipeline plus released language weights. |
| Language forward | [kev.py:409–439][forward] `KevSpatialModel.forward` | Independent causal rows, `use_cache=False`, native readout with rotary positions. Native Q/K plus shared-prefix mode is rejected. |
| Native scoring | [kev_native_qk.py:20–155][native-qk] `NativeQKReadout`, `_scores`, `prune_native_qk`, `NativeQKTextModel` | Keeps per-head Q rows rather than gate rows, applies norms and partial RoPE at original positions, repeats grouped keys, computes mean scaled logits, fills only legal candidate slots. Removes later/full-attention-unused components. |
| Greedy task controller | [kev.py:686–749][rollout] `predict_batch` | Repeatedly encode → forward → argmax; save sliced legal logits; finish or call `advance`. Returns one result per input, preserving order. |
| Transition | [kev.py:161–184][advance] `KevBuilder.advance` | Appends selected-option history; point crops original image and refines box; scalar stage uses first selected root. |
| Scalar finish/decode | [numeric_tasks.py:13–45][numeric], [hierarchy.py:51–118][hierarchy] | Select codebook by unit, detect early zero/overflow, decode count or midpoint; optional fine expectation exists as a Python parameter, not a public CLI flag. |
| Point decode | [hierarchy.py:15–48][hierarchy] `child_box`, `decode_point` | Walk fixed cell order, return normalized original-image center after three decisions. |
| Serialization | [scripts/predict.py:63–72][predict] | JSONL with `id`, `prediction`, `path`, `logits`; `allow_nan=False`; output parent directory is not created automatically. |

The default CLI's `inference_language_dtype="bf16"` metadata is not sufficient evidence of BF16 language compute: the loader installs FP32 language parameters, `configure_full_language` calls `.float()`, the default `language_context` is a null context, and the CLI does not wrap inference in autocast. The separate cached runtime has its own execution path; the CLI does not instantiate it. Runtime dtype/latency parity with the paper must be measured, not assumed from a flag name.

## 4. Actual input and output contracts

### Request and target boundaries

Use the released sample record shapes, not TypeSafe request fields. The examples below are **input examples, not recorded model predictions**. Resolve `images/scene.png` relative to the JSONL file's directory, matching the shipped examples.

```json
{"id":"choice-example","input":{"media":[{"kind":"image","uri":"images/scene.png"}],"question":"Where is the red square relative to the blue circle?","answer_space":{"kind":"choice","options":[{"id":"left","text":"left"},{"id":"right","text":"right"}]}}}
```

```json
{"id":"length-example","input":{"media":[{"kind":"image","uri":"images/scene.png"}],"question":"What is the distance between the two objects in meters?","answer_space":{"kind":"scalar","quantity":"distance","unit":"m"}}}
```

```json
{"id":"point-example","input":{"media":[{"kind":"image","uri":"images/scene.png"}],"question":"Point to the blue circle.","answer_space":{"kind":"point","coordinate_system":"normalized_xy","num_points":1}}}
```

For scalar counts, source selects the count codebook with `answer_space.unit="count"`; the record validator additionally requires `quantity="count"`. For angles use `unit="deg"`, a nonempty `angle_semantics` field, and a question that itself specifies reference frame/direction. **The scorer does not inject the `angle_semantics` field into the prompt.** A wrapper must require consistency between that field and question; merely adding metadata does not communicate semantics to the model.

| Task | Source-observed `prediction` | `path` and `logits` | Training/evaluation target |
|---|---|---|---|
| Choice | Supplied option ID, not option text or generated rationale | One zero-based candidate index; one legal-candidate logit list. CLI preserves supplied option order. | `{"option_id":"left"}` |
| Meter scalar | Numeric midpoint, exact `0.0`, or overflow representative | One or two indices; fine logit length depends on selected root | `{"value":2.4,"unit":"m"}` |
| Count scalar | Integer 0–1023 | Two indices, each in [0,31] | `{"value":3,"unit":"count"}` |
| Angle scalar | Degree midpoint, zero, or overflow representative | One or two indices; angle root/fine contract | `{"value":90,"unit":"deg"}` |
| Single point | Flat `[x,y]` normalized pair, **not** `[[x,y]]` | Three indices in [0,8], three nine-logit lists | `{"points":[[0.62,0.41]]}` |

The ordinary result envelope contains only `id`, `prediction`, `path`, `logits`. There is no guaranteed `confidence`, `probabilities`, `unit`, `coordinate_system`, rationale, or model-version field in that output. Persist the input answer-space and model/codebook identity alongside it in an adapter-owned record. If probabilities are needed, calculate a numerically stable softmax over each returned legal-candidate logit list and label it as adapter-derived. Stage probabilities are conditional on the preceding predicted path; they are not calibrated correctness probabilities and are not a global distribution over all points unless the tree is evaluated.

[Schema implementation][schema] defines `spatial-decision/v2` and `spatial-decision/v3` for labeled records. Its validator checks 2–32 unique choice IDs, meters for v2, meters/count/degrees for v3, finite nonnegative scalar values, count integrality/range, angle semantics/range, and one-image normalized single points. **Neither the public predictor nor trainer invokes this validator.** Inference examples intentionally omit schema version and target; do not fabricate targets to pass a training validator. Build a separate input-only validator using the actual contract. Default crop pointing lacks some validation performed by visual-token/original-image ablation paths, so an integration must enforce its own single-image and coordinate rules before inference.

Sources: [sample requests][examples], [schema.py:74–138][schema], [rollout][rollout].

## 5. Training: paper-to-code alignment and differences

### What aligns

[KevBuilder.training_spec, lines 186–205][training-spec] computes the gold choice/scalar/point path from targets. It appends each gold intermediate selection and crop before constructing later stages, but the earlier decision marker precedes those future items. `encode_specs(training=True)` gathers every stage in the single causal row and assigns each stage `row_weight / number_of_stages`. [decision_losses, lines 77–93][loss] applies ordinary categorical CE to the released hierarchy. [train.py:105–111][training] sums weighted stage losses and divides by QA count. This matches the central per-QA, teacher-forced, multi-stage objective in §3.3/Eq. 7. Inference instead rolls out its own choices and crops; teacher-forced accuracy must not substitute for free-rollout accuracy.

The model loader freezes the vision/merger, retains trainable language parameters in FP32 for training, and exposes native Q/K weights rather than adding a new readout head. The trainer wraps CUDA compute in BF16 autocast. It is a real small continuation-training script, not the full published training pipeline.

### What does not establish paper reproduction

The paper's final recipe uses 12,304,058 original QA once, eight GPUs, global batch 512, microbatch 8, accumulation 8, separate backbone/readout learning rates, warmup/cosine schedules, global length sorting and cross-rank work balancing. Appendix C supplies this recipe; Appendix H studies its throughput separately.

The public `scripts/train.py` uses one device, a shuffled `DataLoader`, one AdamW parameter group/rate, fixed step count and optional accumulation. It contains no distributed scheduler or full data conversion/decontamination pipeline. It forces option-order preservation, whereas the paper says training deterministically shuffles options. Settings such as `save_every`, `precision`, and `freeze_vision` appear in the example settings but are not used as general controls by this small loop; precision/freeze behavior is fixed in its code path. `max_steps` counts loader iterations, not necessarily optimizer updates when accumulation is greater than one, and an unfinished accumulation tail is not explicitly flushed.

**Static checkpoint-save defect:** `scripts/train.py:120` creates the output directory with `exist_ok=False`; `save_checkpoint` immediately creates the same path again with `exist_ok=False` at `kev.py:602`. If reached through the documented flow, the second directory creation raises `FileExistsError`. This follows directly from source and directory semantics; the upstream training command was not executed. Do not advertise the README training command as a verified working round trip.

### Published checkpoint identity is unresolved

At the pinned model revision:

- `checkpoint.json` reports `step: 100`, not the paper's final 24,032 updates.
- `config.json` contains `pilot_steps: 500`, `distill_teacher: "Qwen3-VL-32B-Instruct"`, `distill_test_set_leakage: true`, and a base-plus-distillation batch-ratio setting. These are **literal public metadata observations**, not an independently established account of how the tensors were trained.
- The same configuration records the 12,304,058-QA expected corpus and the matching native-Q/K/codebook architecture.

These fields do not establish that the published checkpoint is the clean final checkpoint evaluated in the paper. They also do not by themselves prove that any reported paper score used contaminated evaluation data. Stale, diagnostic or mismatched release metadata is possible. Require a corrected checkpoint-to-paper manifest, provenance explanation, and independently held-out evaluation before claiming the release reproduces the paper or using its benchmark scores for promotion. Do not copy irrelevant source metadata into a public plugin payload.

## 6. Evaluation: paper claims and executable metric boundary

### Headline claims — paper-reported, unreproduced

| Claim | Paper locator | Necessary scope/qualification |
|---|---|---|
| 65.64 overall, first on seven of twelve benchmarks, above unmodified Qwen3.5-4B on all twelve | §4.2, Table 2 | Equal benchmark aggregation of heterogeneous metrics, not one pooled accuracy or a general-purpose judge score |
| Final length MAE 0.103 m | §4.2 | VST-300 development set; not a broad independent deployment guarantee |
| 160.6 ms mean query latency; 2.5× versus fastest AR baseline, 5.6× versus base | §4.2; Appendix D.3/Table 11 | One NVIDIA B200, batch one, equal mean across twelve benchmark means; image I/O, preprocessing, transfer, inference/decision and decode included; warmup and model loading excluded |
| 30.8% training throughput gain | §4.4; Appendix H.1/Table 6 | Eight L20D GPUs, historical 72K data, 100 updates with eight excluded as warmup; scheduling-only short-run comparison, no convergence/quality experiment |
| 4/8 fine bins improve pilot MAE over 32 bins | §4.3; Appendix G/Tables 23–25 | 72K training budget; quantization oracle worsens while learned MAE improves; relative-error outcomes are not uniformly better |
| Re-encoded crops beat alternative visual strategies on RefSpatial and Point-Bench | §4.3; Appendix F.1 | Task-dependent tradeoffs; crop removal from fixed weights introduces distribution shift; matched no-crop retraining recovers much of the loss |
| Root-pruned multi-point decoding preserves paired-run success and reduces cost | Appendix F.2/Tables 21–22 | 196 counting cases, fixed historical weights, 38.78% success, 91→51.10 mean nodes, 4.716→2.638 seconds; different setting from final batch-one latency table |

Independent arithmetic on printed values yields Table 2 mean `65.6416667`, `397.4/160.6 = 2.4744707`, and `894.1/160.6 = 5.5672478`, consistent with rounded headline values. Printed scheduling rates yield `(129.54/99.06-1)*100 = 30.76923%`; the paper's 30.78% can reflect unrounded measurements. These calculations verify arithmetic only, not measurement provenance or model quality.

### Important appendix findings

- **Data:** Appendix B excludes ambiguous units, ranges/inequalities, unsupported area/volume, multi-point/region-only labels and more than five source images. RefSpatial-derived data supply about 89.5% of QA and all current point supervision. Image near-duplicate filtering is conservative and does not establish scene-level or neighboring-video-frame independence. Label conversion audits are sampled, not proof of universal annotation correctness.
- **Readout ablations:** Native Q/K is not best on every task. Appendix E varies readout depth and retained parameter count under equal data, not equal compute; architecture-dependent templates/initialization prevent attributing every gain solely to the score formula. Layer fusion does not consistently help. High head-response correlation is evidence of redundancy, not a demonstrated safe pruning rule; no head passes all predeclared near-zero criteria.
- **Historical comparisons:** Appendix D records sequence-budget differences (8192 versus 32768), micro/macro Point-Bench reporting changes, and SAT's 300 execution requests representing 150 questions in two orders. Do not treat every historical table as the same final checkpoint/budget.
- **Numerical:** Appendix G distinguishes encode/decode oracles from learned results, demonstrates coarse-root lock-in, and shows that conditional expectation worsens MAE while improving one relative hit metric. Do not market bin precision as model precision.
- **Multi-point:** Appendix F's task-based visual-token routing was selected after the initial decoder comparison and is labeled exploratory. Counting success depends on component threshold. Exact count plus union-mask hits does not guarantee one point per distinct instance.
- **Resources:** Appendix H's expanded-data successful training profiles report about 242 decimal GB peak allocated **per rank**, with larger microbatches OOM. These are training profiles, not a minimum inference-VRAM specification. The global768 result has only ten measured updates; executed updates were still within zero backbone LR, although backward and Adam moments ran.

### Public evaluator is not the benchmark harness

[Evaluate main, lines 18–65][evaluation] loads requests, performs greedy inference and returns:

- `n`: number of requests;
- `choice_accuracy`: option-ID equality;
- `scalar_mae`: mean absolute numeric error;
- `point_mean_distance`: Euclidean distance between predicted normalized pair and the **first** target point.

There is **no point-hit/mask metric** despite the README's phrase “distance/hit metrics”; no Point-Bench exact-count/union-mask scorer, grayscale mask evaluator, category macro aggregation, latency measurement, calibration, confidence intervals, or benchmark dataset adapters. The scalar average combines scalar records without grouping by unit; mixing meters, counts and degrees produces an uninterpretable aggregate. Target units are not validated there. Missing/duplicate-ID/error handling is weaker than the prediction CLI, and an exception aborts evaluation rather than producing an invalid-output denominator ledger. The generic evaluator must not be used as a substitute for Table 2 or Table 11 reproduction.

Paper-specific scoring in Appendix D includes weighted CV-Bench subsets, BLINK macro over 14 tasks, RefSpatial binary-mask accuracy, Where2Place grayscale mask value/255, RoboSpatial's author scorer and Point-Bench macro over five category success rates. Reimplementation must pin those original scorer versions, dataset revisions, image order and anomaly handling. The repository does not supply the complete final benchmark harness.

## 7. Runtime, dependency and release blockers

1. **Incompatible declared dependency ranges.** Both inference/train extras require `transformers==5.17.0` and `huggingface-hub>=0.36,<1`. [PyPI metadata for transformers 5.17.0](https://pypi.org/pypi/transformers/5.17.0/json) declares `huggingface-hub>=1.5.0,<2.0`. The two intervals do not intersect. This is a metadata-confirmed resolver conflict, not a failed installation observed here. Do not work around it with `--no-deps`; resolve and test a reviewed compatible dependency set first.
2. **Checkpoint save collision** described above prevents claiming the documented continuation-training round trip works.
3. **Broken top-level API export:** [`src/spatial_jev/__init__.py:3–11`][package-init] reports version `0.1.0` and lazily exports `JevSpatial` from `.inference`; that module is absent from this source tree. Do not document `from spatial_jev import JevSpatial` as a usable API. Prefer the actually traced script/functions after repair/verification.
4. **Missing optional ablation module:** `kev.py` references `.kev_multilayer_qk` for multilayer configurations, but that file is absent. This does not by itself block the released single-layer default. Do not claim complete executable coverage of every paper ablation.
5. **Checkpoint portability:** processor and base weights load by `base_model`, not the saved processor directory or the declared `base_revision`. `local_files_only` defaults false. A local checkpoint directory is therefore not a guarantee of no network or no additional downloads. Require pinned local base and processor artifacts, explicit offline settings, dependency review and network denial before an offline runtime trial.
6. **Memory and compute:** [tensor index][weight-index] reports 4,111,374,336 language parameters and 16,445,497,344 bytes of tensor storage across five shards. These are metadata, not inspected tensor contents. Additional base vision assets, loading transients, activations, padding and intermediate crops require more resources. No validated CPU/MPS/quantized inference profile, minimum VRAM, or device-portable latency is established by this review.
7. **Budget behavior:** prediction caps per-image tokenization at 1024 and allows at least 8192 total tokens; over-budget input raises rather than silently truncates. The generic evaluator sets 8192. The paper's later quality runs use up to 32768 and VSI has a special 32-frame/64-tokens-per-frame profile. There is no public video-file CLI contract; image sequences are not automatically a verified video adapter.
8. **Public tests are shallow:** [test_public_contract.py][tests] checks sample JSON task kinds, entrypoint existence and README path hygiene. It does not validate scoring, geometry, causality, checkpoint save/reload, dependency resolution or inference. Tests were read, not run.

## 8. Licensing: keep code, weights and data separate

- **Source:** pinned [LICENSE][code-license] is Apache-2.0; README and package metadata agree. Preserve license/attribution and modification notices when redistributing source or derived code.
- **Released weights:** the pinned model repository contains [LICENSE][weight-license], byte-identical to the code's Apache-2.0 file in this read. However, its model card's prose expressly calls out the **source code** license, and its [NOTICE][weight-notice] still describes the old Molmo2-ER/LoRA release. The presence of a repository license is evidence; stale attribution and checkpoint provenance remain release-hygiene questions. Do not silently assume code licensing alone clears every tensor/data obligation.
- **Base weights:** pinned [Qwen3.5-4B model card](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/README.md) declares Apache-2.0 and supplies a [base LICENSE](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/LICENSE). These are separate from the derived-model release.
- **NOTICE mismatch:** the code and model NOTICE claim copied `spatial_jev/molmo2` modules and LoRA-merged Molmo2 weights; that directory is absent and the current runtime/metadata uses Qwen native Q/K. Retain applicable notices and request corrected attribution; do not rewrite or delete upstream attribution based on speculation.
- **Datasets/media:** original dataset terms remain separate. The complete training/evaluation media and conversion corpus were not acquired or license-audited. The small supplied synthetic example is a wiring fixture, not proof that arbitrary redistributed datasets are cleared.
- **Name boundary:** the project explicitly describes TypeSafe Jev as inspiration and disclaims an official TypeSafe implementation or reproduction of proprietary RLCD. A plugin must preserve this distinction.

## 9. `/jev` selection and evaluation design patterns — proposed, not implemented

### Backend selection

A selector should first identify evidence modality, answer type, resource constraints and consequence of a mistake. Keep this backend disabled by default until the release gates are resolved.

| Need | Appropriate route |
|---|---|
| Choose among a small set of spatial relations grounded in supplied still images | Consider MJev-Spatial `choice`, after input validation and calibration on the deployment domain |
| Estimate supported length/count/angle from images | Consider MJev-Spatial `scalar`, with unit/frame contract, range/overflow handling and task-specific evaluation |
| Propose one target location in a still image | Consider hierarchical `point`; retain original image dimensions/frame, predicted path, and a separate action-verification boundary |
| Locate every object / multi-point output | Separate experimental tree adapter and counting benchmark; never translate `num_points` into an unsupported CLI feature |
| Judge textual groundedness, instruction compliance or ordered agent traces | Use an independently verified semantic-evaluation interface suited to those inputs; spatial benchmarks do not qualify this model as a general judge |
| Exact arithmetic, unit conversion, bounds, IDs, geometry transforms, authorization | Ordinary deterministic code, not a learned judge |
| Open-ended explanation, novel output type, unsupported unit or uncertain frame | Reject or route to another explicitly supported interface; never silently reinterpret the request |

### Adapter boundary

Use the upstream request fields from §4 unchanged. A local adapter should validate them **before** opening images or loading a model: required question, unique IDs, allowed image roots/types/size, finite budgets, 2–32 unique choice IDs, explicit unit, scalar quantity, and exactly one normalized image for single-point requests. Reject remote URLs, path traversal and undeclared file access unless a separately reviewed media-ingestion layer authorizes them. Bound image dimensions/decompression, batch size, token counts, total decisions, output size, time and cancellation. File-read permissions are not established by the model schema.

Preserve the raw upstream result and add provenance only in an adapter-owned wrapper: code SHA, weight revision, base revision actually loaded, codebook identity, input/image digest, answer-space, actual dtype/device, budgets, decoder settings, and validation outcome. These are **proposed logging requirements**, not fields claimed to exist in upstream JSON. Do not include raw sensitive images/questions in default logs.

Reject nonfinite scores, shape/cardinality mismatches, unknown option IDs, invalid paths, unsupported units and out-of-frame points deterministically. Explicitly distinguish exact-zero, positive-cell and overflow scalar paths. Derive calibrated abstention/review thresholds from held-out data; high softmax confidence alone must not authorize a click, robot action, publication or CI release.

### Evaluation design

1. **Contract suite:** empty/malformed media, duplicate IDs/options, unsupported tasks/units, angle-frame omissions, multi-image point requests, missing targets, over-budget inputs, normalized endpoints and source-path traversal. Evaluate the proposed wrapper separately from upstream permissive behavior.
2. **Codebook suite:** zero, every coarse edge and adjacent values, fine-cell centers, final floating-point edge, overflow, counts 0/31/32/1023, and angles 0/30/360. Keep quantization-only error separate from prediction error and preserve checkpoint codebook version.
3. **Point suite:** fixed cell ordering, every leaf center, boundary points, non-square images, original-pixel crop extents and original-frame decode. Test crop-history isolation and no target leakage.
4. **Scoring suite:** legal-only softmax, padded-negative-infinity handling, stable normalization, marker escaping, candidate-ID permutation, stage ownership, head-logit mean versus probability mean, deterministic ties. Numeric checks are exact code tests, not semantic-judge calls.
5. **Training suite:** causal future-crop isolation, stage-normalized loss, incomplete batch/accumulation handling and checkpoint save/reload. Fix the identified directory collision in a separately authorized implementation before claiming training usability.
6. **Task quality:** choice accuracy plus option-order robustness and calibration; scalar MAE grouped by unit/quantity, relative-error handling at zero, count exact accuracy, declared-angle error convention; point normalized/pixel distance and task-author mask hit. Multi-point tests need count accuracy, count MAE, instance coverage, duplicate-point behavior, omitted mass and threshold sensitivity.
7. **Independent data:** human-labeled domain cases, distribution shifts, ambiguous requests, occlusion, small objects, multiple equally valid regions, extreme aspect ratios and rare large distances. Keep developer calibration and held-out promotion sets separate, especially while checkpoint provenance is unresolved.
8. **Latency/resource suite:** cold load separate from warmed query, end-to-end image I/O/preprocess/transfer/decision/decode boundaries, p50/p95 and failures, device/precision/batch/token/crop/node counts, peak memory. Do not reuse B200 paper timings as a local SLA.
9. **Promotion:** reference → source-contract checks → separately approved isolated runtime smoke → held-out shadow evaluation → advisory integration. A semantic score or model-emitted point does not itself grant tool-execution authority.

### Safe offline work available now

Without imports, installation, checkpoint downloads or GPU execution, a reviewer can parse JSON/AST, inspect imports/call graphs, validate data schemas in an independently authored harness, check codebook arithmetic, and compare saved synthetic logits against independently specified math. This review performed AST parsing of 18 source/script/test Python files, parsed shipped request/train/eval JSONL (2/3/3 records), verified their relative image files exist, and checked codebook cardinality/tolerance arithmetic. All succeeded. No upstream functions, package tests, training or inference were executed; synthetic arithmetic is not a model test.

A future offline adapter test may use clearly labeled fixtures for formatting/scoring paths, but must not manufacture model predictions and call them successful inference. The safe reusable product of this intake is the reference, verified contracts, source-level blockers and a bounded validation plan—not an enabled runtime.

## 10. Commands, prerequisites and execution receipts

### Actually executed discovery/checks

These exact read-only GitHub commands were executed successfully:

```bash
gh api repos/Fr0zenCrane/MJev-Spatial
gh api repos/Fr0zenCrane/MJev-Spatial/commits/HEAD --jq '{sha: .sha, html_url: .html_url}'
gh api repos/Fr0zenCrane/MJev-Spatial/releases --jq '[.[] | {tag_name,published_at}]'
```

A source-only `git clone --depth 1` was performed in an isolated review directory with `GIT_LFS_SKIP_SMUDGE=1` and `core.hooksPath=/dev/null`; `rev-parse HEAD` matched the API SHA, `rev-parse --is-shallow-repository` returned `true`, and `status --short` was empty. The full HTML was fetched with `curl -fL --max-time 60`. Local absolute invocation paths are intentionally omitted from this public reference. These are execution facts, not a claim that the portable recipe below was executed literally.

Prerequisites for repeating discovery: GitHub CLI with permitted public-read access, Git, curl, network access, and an empty caller-owned review directory. Portable source-only equivalent, **not an additional execution receipt**:

```bash
GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null clone --depth 1 \
  https://github.com/Fr0zenCrane/MJev-Spatial.git mjev-spatial-src
git -C mjev-spatial-src rev-parse HEAD
# Require df37e9e5a3455c642f7b43cf96abc4f950b4fa6d; stop on mismatch.
git -C mjev-spatial-src rev-parse --is-shallow-repository
git -C mjev-spatial-src status --short
curl -fL --max-time 60 https://arxiv.org/html/2610.22276v1 -o mjev-paper.html
```

Metadata-only HTTPS reads retrieved the pinned model configuration, checkpoint record, language configuration, tensor index, LICENSE and NOTICE, plus PyPI dependency metadata. No `.safetensors` shard was downloaded. A third-party HTML-parser import was unavailable; extraction used the Python standard-library HTML parser instead, without installing anything.

### Exact upstream-documented commands — observed, NOT executed

From [README installation/inference/training/evaluation][readme]:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[inference,train]'

python scripts/predict.py \
  --checkpoint "$MJEV_CHECKPOINT" \
  --input examples/requests.jsonl \
  --output predictions.jsonl

python scripts/train.py \
  --checkpoint "$MJEV_CHECKPOINT" \
  --data examples/train.jsonl \
  --config configs/finetune.json \
  --output runs/example-finetune

python scripts/evaluate.py \
  --checkpoint runs/example-finetune \
  --data examples/eval.jsonl \
  --output runs/example-finetune/evaluation.json
```

These are **not presently endorsed as a working recipe**: dependency resolution and the save collision are unresolved, and the evaluator's checkpoint depends on that training command. Before any runtime attempt, require a compatible reviewed dependency lock, suitable Python/CUDA/PyTorch environment, explicit resource budget, pinned local checkpoint/base/processor assets and their licenses, fixed provenance, writable output parents and authorized media. Set `MJEV_CHECKPOINT` to the reviewed local checkpoint directory without publishing that path. Preserve original files; patch only in a separately authorized implementation workspace. A public plugin should not install dependencies, download weights, run these commands or select a GPU just because this reference is loaded.

## 11. Remaining unknowns and scope boundary

- Actual model outputs, numerical stability, inference memory/latency and device support were not tested.
- Tensor contents and checksums were not downloaded or verified; metadata is not weight integrity verification.
- Release checkpoint correspondence to paper final results, distillation-related metadata, evaluation separation and stale NOTICE need author clarification.
- Full dataset licensing, conversion artifacts and benchmark manifests were not acquired.
- Third-party Transformers/PyTorch/processor internals were not exhaustively source-audited; the traced call graph ends at their documented/imported interfaces.
- Source review prioritized the complete default CLI → processor → native readout → refinement → decode path, training construction/loop, metrics, schemas, codebooks, probability-tree module, tests and release metadata. Legacy baseline, optional cache/replay internals and artwork utilities were not exhaustively line-reviewed; AST parsing of a file is not a semantic audit of every function.
- No public repository, profile, plugin or runtime configuration was edited. No untrusted source execution, install, model-weight download, GPU call or benchmark run occurred.

[paper]: https://arxiv.org/html/2610.22276v1
[repo]: https://github.com/Fr0zenCrane/MJev-Spatial/tree/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d
[readme]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/README.md#L49-L200
[dependencies]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/pyproject.toml#L1-L43
[request-reader]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/scripts/predict.py#L18-L32
[predict]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/scripts/predict.py#L35-L72
[processor]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/qwen35.py#L36-L53
[crop]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/unified.py#L165-L213
[builder]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L91-L159
[advance]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L161-L184
[training-spec]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L186-L205
[encode]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L207-L337
[embedding]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L369-L390
[forward]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L409-L439
[loader]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L442-L642
[rollout]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev.py#L686-L749
[native-qk]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/kev_native_qk.py#L20-L155
[numeric]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/numeric_tasks.py#L5-L71
[hierarchy]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/hierarchy.py#L8-L118
[point-map]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/point_probability_map.py#L8-L125
[schema]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/schema.py#L7-L138
[loss]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/visual_token_pointing.py#L77-L118
[training]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/scripts/train.py#L65-L122
[evaluation]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/scripts/evaluate.py#L18-L65
[examples]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/examples/requests.jsonl
[package-init]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/src/spatial_jev/__init__.py#L1-L12
[tests]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/tests/test_public_contract.py#L1-L23
[code-license]: https://github.com/Fr0zenCrane/MJev-Spatial/blob/df37e9e5a3455c642f7b43cf96abc4f950b4fa6d/LICENSE
[weights]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/tree/0657319c58d342f54c5108cd3c4d983a79a8b3f7
[model-config]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/config.json
[checkpoint]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/checkpoint.json
[language-config]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/language_model/config.json
[weight-index]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/language_model/model.safetensors.index.json
[weight-license]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/LICENSE
[weight-notice]: https://huggingface.co/mindlab-research/MJev-Spatial-4B/blob/0657319c58d342f54c5108cd3c4d983a79a8b3f7/NOTICE
