#!/usr/bin/env python3
"""Independent stdlib, offline, input-only research contracts (not inference).

No upstream implementation is imported or copied. Contract provenance: the pinned
source entries below and the vetted videojev/mjev-spatial/jeva references.
Video input is ONLY the questions argument, not a complete predict_video call.
Spatial input is ONE upstream {id, input} object, never JSONL, arrays or labels.
Jeva input is ONE raw Jeva.predict kwargs object, never evaluation targets.
All stricter checks/budgets and reports are adapter-owned, not native APIs.
"""
import argparse
import json
import os
import stat

VERSION = "1.1.0"
MAX_INPUT_BYTES = 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 20000
MAX_STRING = 65536
MAX_TEXT_TOTAL = 524288
TASKS = {
    "video-grounding": "videojev", "video-choice": "videojev",
    "spatial-choice": "mjev-spatial", "spatial-scalar": "mjev-spatial",
    "spatial-point": "mjev-spatial", "text-choice": "jeva",
    "text-noul": "jeva", "text-score": "jeva",
}
SOURCES = {
    "videojev": {
        "revision": "7f8b38aa7df67721303cdc61f06d8435f3c7db89",
        "entry": "videojev_hf/processing_videojev.py:prepare_query_groups/suffix",
        "capabilities": ["temporal grounding", "single-choice video QA"],
        "shape": "Nonempty JSON list of {id,task,query}; choice also requires options:[string,string,...]. Questions argument only; no video file accepted.",
        "limits": ["Grounding always chooses a nonempty interval; not event-absence detection.",
                   "Released HF API uses joint queries/vision reuse, not a cached/streaming switch.",
                   "No audio, generation, rationale or calibrated-correctness guarantee."],
        "policy": "Explicit unique string IDs; explicit task; grounding options forbidden; bounded text/list sizes; duplicate option text allowed.",
    },
    "mjev-spatial": {
        "revision": "df37e9e5a3455c642f7b43cf96abc4f950b4fa6d",
        "entry": "scripts/predict.py:load_rows/normalize -> spatial_jev.kev:predict_batch",
        "capabilities": ["image spatial choice", "scalar m/count/deg", "single normalized_xy point"],
        "shape": "One JSON {id,input:{media:[{kind:'image',uri:relative_path}],question,answer_space}}. answer_space: choice/options[{id,text}], scalar/quantity/unit[/angle_semantics], or point/coordinate_system='normalized_xy'/num_points=1.",
        "limits": ["Dependency ranges conflict; checkpoint save collision; broken top-level API export.",
                   "Checkpoint-to-paper provenance unresolved; backend promotion blocked.",
                   "Point needs one image; CLI is greedy single-point, not multi-point tree or video-file inference.",
                   "Scalar codebooks: m zero/positive cells/overflow representative 16384; count integers 0-1023; deg 0-360 with explicit frame/direction. No scalar labels/bounds accepted as input.",
                   "Point output frame is original-image [0,1] x/y, top-left origin, x right/y down; no input target coordinates, pixel actions or 3D pose.",
                   "Length/count/angle codebooks have quantization and overflow semantics; precision is not accuracy."],
        "policy": "Exactly one id/input object; 1-5 images (point exactly one); 2-32 unique option IDs; lexical relative media paths only, never resolved/opened; angle_semantics must occur verbatim in question (not semantic verification).",
    },
    "jeva": {
        "revision": "e2104e0720100f979f2cdd456a1cbbee96da0abd",
        "entry": "src/jeva/inference.py:Jeva.predict",
        "capabilities": ["text choice with optional null", "text noul", "text score"],
        "shape": "One JSON raw predict kwargs object: state (bounded JSON), question, decision_type, options:[string,string,...], allow_null (explicit bool); score requires values; noul requires positive_index. Optional irrelevant kwargs allowed only at native neutral defaults (values=null, positive_index=1).",
        "limits": ["Null means no supplied candidate acceptable, not generic uncertainty or authorization.",
                   "Score uses supplied numeric values, not a universal scale; Noul is conditional positive-option mass.",
                   "No native image/video input or generated explanations; cache/runtime and paper metrics unverified."],
        "policy": "2+ options; null only for choice; explicit finite score values (order unrestricted); explicit noul positive index; repeated raw option texts preserved.",
    },
}
COMMON_LIMITS = [
    "Input shape checks only: no model, media, tokenizer, quality, calibration or paper reproduction verified.",
    "Media origin, authorization and semantic quality cannot be authenticated; no media path is resolved, probed or opened.",
    "No installs, downloads, network, credentials, upstream imports, model loading or execution.",
]


def metadata(backend):
    source = SOURCES[backend]
    return {
        "version": VERSION, "candidate_backend": backend,
        "runtime_status": "UNVERIFIED",
        "readiness": "BLOCKED_SOURCE_ISSUES" if backend == "mjev-spatial" else "CONTRACT_ONLY",
        "actual_execution": False, "model_loaded": False, "advisory_only": True,
        "contract_owner": "adapter-owned strict subset of source-observed input",
        "source_revision": source["revision"], "upstream_entry": source["entry"],
        "source_observed_capabilities": source["capabilities"],
        "supported_input_shape": source["shape"],
        "adapter_policy": source["policy"], "limits": source["limits"] + COMMON_LIMITS,
        "adapter_budgets": {"input_bytes": MAX_INPUT_BYTES, "json_depth": MAX_DEPTH,
                            "json_nodes_including_keys": MAX_NODES, "string_characters": MAX_STRING,
                            "aggregate_text_characters": MAX_TEXT_TOTAL, "question_option_characters": 16384,
                            "video_questions": 256, "video_jeva_options": 256,
                            "spatial_options": 32, "score_absolute_value": 1e12},
        "tokenizer_fit": "UNKNOWN", "media_checked": False,
        "input_file_policy": "Explicit local regular .json file only; final symlink rejected; no authorized-root or parent-symlink containment claim.",
    }


class ContractError(ValueError):
    """Static error codes only; never interpolate untrusted input."""


def require(condition, code):
    if not condition:
        raise ContractError(code)


def fields(value, required, optional=()):
    require(type(value) is dict, "OBJECT_REQUIRED")
    require(set(required) <= value.keys(), "MISSING_FIELD")
    require(value.keys() <= set(required) | set(optional), "UNKNOWN_FIELD")


def text(value, maximum=16384, *, control_tokens=False):
    require(type(value) is str and 0 < len(value) <= maximum and bool(value.strip()), "TEXT_INVALID")
    require(not control_tokens or "<|" not in value, "CONTROL_TOKEN")


def sequence(value, minimum=1, maximum=256):
    require(type(value) is list and minimum <= len(value) <= maximum, "LIST_SIZE_OR_TYPE")


def video_questions(value):
    sequence(value)
    identities = set()
    for row in value:
        fields(row, ("id", "task", "query"), ("options",))
        text(row["id"], 128)
        require(row["id"] not in identities, "DUPLICATE_ID")
        identities.add(row["id"])
        require(row["task"] in ("grounding", "choice"), "TASK_UNSUPPORTED")
        text(row["query"], control_tokens=True)
        if row["task"] == "choice":
            require("options" in row, "MISSING_FIELD")
            sequence(row["options"], 2)
            for option in row["options"]:
                text(option, control_tokens=True)
        else:
            require("options" not in row, "FIELD_NOT_APPLICABLE")
    return {"request_count": len(value)}


def media_reference(value):
    """Lexical policy only: deliberately no pathlib, stat, resolve or open."""
    import re
    text(value, 1024)
    require(all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", part)
                for part in value.split("/")), "MEDIA_REFERENCE_UNSAFE")


def spatial_request(value):
    fields(value, ("id", "input"))
    text(value["id"], 128)
    inp = value["input"]
    fields(inp, ("media", "question", "answer_space"))
    text(inp["question"])
    sequence(inp["media"], 1, 5)
    for media in inp["media"]:
        fields(media, ("kind", "uri"))
        require(media["kind"] == "image", "MEDIA_KIND_UNSUPPORTED")
        media_reference(media["uri"])
    space = inp["answer_space"]
    fields(space, ("kind",), ("options", "quantity", "unit", "angle_semantics",
                             "coordinate_system", "num_points"))
    kind = space["kind"]
    if kind == "choice":
        fields(space, ("kind", "options"))
        sequence(space["options"], 2, 32)
        identities = set()
        for option in space["options"]:
            fields(option, ("id", "text"))
            text(option["id"], 128)
            text(option["text"])
            require(option["id"] not in identities, "DUPLICATE_ID")
            identities.add(option["id"])
    elif kind == "scalar":
        fields(space, ("kind", "quantity", "unit"), ("angle_semantics",))
        text(space["quantity"], 128)
        require(space["unit"] in ("m", "count", "deg"), "UNIT_UNSUPPORTED")
        if space["unit"] == "count":
            require(space["quantity"] == "count", "COUNT_QUANTITY_REQUIRED")
        if space["unit"] == "deg":
            require("angle_semantics" in space, "ANGLE_SEMANTICS_REQUIRED")
            text(space["angle_semantics"], 1024)
            require(space["angle_semantics"] in inp["question"], "ANGLE_SEMANTICS_NOT_IN_QUESTION")
        else:
            require("angle_semantics" not in space, "FIELD_NOT_APPLICABLE")
    elif kind == "point":
        fields(space, ("kind", "coordinate_system", "num_points"))
        require(len(inp["media"]) == 1, "POINT_REQUIRES_ONE_IMAGE")
        require(space["coordinate_system"] == "normalized_xy", "POINT_FRAME_UNSUPPORTED")
        require(type(space["num_points"]) is int and space["num_points"] == 1,
                "POINT_REQUIRES_SINGLE_INTEGER")
    else:
        raise ContractError("TASK_UNSUPPORTED")
    return {"request_count": 1, "media_reference_count": len(inp["media"])}


def jeva_request(value):
    fields(value, ("state", "question", "decision_type", "options", "allow_null"),
           ("values", "positive_index"))
    text(value["question"])
    kind = value["decision_type"]
    require(kind in ("choice", "noul", "score"), "TASK_UNSUPPORTED")
    require(type(value["allow_null"]) is bool, "BOOLEAN_REQUIRED")
    require(kind == "choice" or not value["allow_null"], "NULL_ONLY_FOR_CHOICE")
    sequence(value["options"], 2)
    for option in value["options"]:
        text(option)
    if kind == "noul":
        require("positive_index" in value, "MISSING_FIELD")
        index = value["positive_index"]
        require(type(index) is int and index in (0, 1) and len(value["options"]) == 2,
                "NOUL_BINARY_INDEX_REQUIRED")
    elif "positive_index" in value:
        require(type(value["positive_index"]) is int and value["positive_index"] == 1,
                "IRRELEVANT_INDEX_NOT_DEFAULT")
    if kind == "score":
        require("values" in value, "MISSING_FIELD")
        sequence(value["values"], len(value["options"]), len(value["options"]))
        for number in value["values"]:
            require(type(number) in (int, float) and -1e12 <= number <= 1e12,
                    "SCORE_VALUE_INVALID")
    else:
        require(value.get("values") is None, "FIELD_NOT_APPLICABLE")
    return {"request_count": 1, "option_count": len(value["options"])}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def reject_constant(unused):
    raise ContractError("NONFINITE_NUMBER")


def check_json_tree(value):
    """Bound even arbitrary JSON state; schema fields are checked separately."""
    stack = [(value, 0)]
    nodes = total_text = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        require(nodes <= MAX_NODES, "JSON_NODE_BUDGET")
        require(depth <= MAX_DEPTH, "JSON_DEPTH_BUDGET")
        if type(item) is dict:
            stack.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            require(len(item) <= MAX_STRING, "JSON_STRING_BUDGET")
            require("\x00" not in item, "NUL_TEXT_FORBIDDEN")
            item.encode("utf-8", errors="strict")  # reject escaped lone surrogates
            total_text += len(item)
            require(total_text <= MAX_TEXT_TOTAL, "JSON_TEXT_BUDGET")
        elif type(item) in (int, float):
            # Comparisons also reject NaN and infinities without float(int) overflow.
            require(-1e308 <= item <= 1e308, "NUMBER_OUT_OF_FINITE_BOUNDS")


def input_opener(path, flags):
    # Regular files only: no FIFO wait, and do not follow the final symlink.
    # This is not an authorized-root sandbox for parent directories.
    require(hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK"), "SAFE_OPEN_UNAVAILABLE")
    return os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)


def validate_file(backend, path):
    require(type(path) is str and path.endswith(".json") and "://" not in path
            and "\x00" not in path, "INPUT_MUST_BE_LOCAL_JSON_FILE")
    with open(path, "rb", opener=input_opener) as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "INPUT_NOT_REGULAR_FILE")
        raw = source.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "INPUT_TOO_LARGE")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                       parse_constant=reject_constant)
    check_json_tree(value)
    if backend == "videojev":
        return video_questions(value)
    if backend == "mjev-spatial":
        return spatial_request(value)
    if backend == "jeva":
        return jeva_request(value)
    raise ContractError("BACKEND_UNSUPPORTED")


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown arguments/values, including secrets.
        raise ContractError("CLI_ARGUMENTS_INVALID")


def main(argv=None):
    parser = SafeArgumentParser(prog="research_kit", description=__doc__, allow_abbrev=False)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Select candidate only; never execute", allow_abbrev=False)
    plan.add_argument("--task", choices=TASKS, required=True)
    validate = commands.add_parser("validate", help="Check input shape only, without reading media", allow_abbrev=False)
    validate.add_argument("--backend", choices=SOURCES, required=True)
    validate.add_argument("--input", required=True, help="Explicit local regular .json file, at most 1 MiB")
    try:
        args = parser.parse_args(argv)
    except ContractError:
        print(json.dumps({"version": VERSION, "status": "INVALID_CONTRACT",
                          "error_code": "CLI_ARGUMENTS_INVALID", "actual_execution": False,
                          "model_loaded": False, "advisory_only": True}))
        return 2
    if args.command == "plan":
        report = metadata(TASKS[args.task])
        report.update(status="PLAN_ONLY", task=args.task)
        code = 0
    else:
        report = metadata(args.backend)
        try:
            report.update(validate_file(args.backend, args.input))
            report["status"] = "VALID_CONTRACT_ONLY"
            code = 0
        except ContractError as exc:
            report.update(status="INVALID_CONTRACT", error_code=str(exc))
            code = 2
        except (OSError, ValueError, UnicodeError, RecursionError):
            report.update(status="INVALID_CONTRACT", error_code="INPUT_UNREADABLE_OR_INVALID_JSON")
            code = 2
    print(json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
