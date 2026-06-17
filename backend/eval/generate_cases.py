"""Generator for the M2-M5 eval case suite.

Produces 25 deterministic cases per level (100 total) under
``eval/cases/generated/``, each carrying a scripted ``mock_llm`` so the
in-process (mock) runner passes them deterministically in CI. A small subset of
the M4 self-authoring cases is also tagged ``browser`` (with a ``"*"`` wildcard
expectation) for real end-to-end runs against Gemma.

Levels (max complexity per the agreed design):
- M2: read-only multi-tool workflows combining 3+ query tools (auto-executed).
- M3: 3+ query tools as context + a write/batch skill (needs confirmation).
- M4: self-authoring skill generation (the gzip/csv/base64/hash/... batch).
- M5: multi-step workflows with step-output references + a write (needs confirm).

Re-run with:  python -m eval.generate_cases
"""

from __future__ import annotations

import itertools
import shutil
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

GENERATED_DIR = Path(__file__).resolve().parent / "cases" / "generated"

# Read-only query tools and write skills actually registered by the in-process
# runner (share_item is omitted — it needs a share_link_service that inproc
# does not wire). Scripting an unregistered skill would get the plan rejected.
QUERY_TOOLS = ["search", "list_items", "get_info", "recent", "storage_quota"]
WRITE_SKILLS = ["create_folder", "rename_item", "move_item", "organize_by_type", "star_item"]

_ITEM = "11111111-1111-1111-1111-111111111111"
_PARENT = "22222222-2222-2222-2222-222222222222"

_QUERY_PHRASE = {
    "search": "搜尋檔案",
    "list_items": "列出根目錄檔案",
    "get_info": "查看某個項目的詳情",
    "recent": "看最近開啟的檔案",
    "storage_quota": "查目前容量用量",
}
_WRITE_PHRASE = {
    "create_folder": "建立一個資料夾",
    "rename_item": "把某個項目改名",
    "move_item": "把某個項目移動到別的資料夾",
    "organize_by_type": "依副檔名分類整理",
    "star_item": "把某個項目加星號",
}

# M4 self-authoring batch: (skill_name, 中文功能描述). Codeguard only does a
# static scan on the scripted code, so a uniform safe body is fine.
M4_SKILLS = [
    ("unzip_archive", "解開 zip 壓縮檔"),
    ("zip_files", "把檔案壓成 zip"),
    ("gunzip_file", "解開 gzip (.gz)"),
    ("gzip_file", "把檔案壓成 gzip"),
    ("untar_archive", "解開 tar 封存"),
    ("tar_files", "把檔案打包成 tar"),
    ("extract_7z", "解開 7z 壓縮檔"),
    ("sha256_checksum", "算 SHA256 雜湊"),
    ("md5_checksum", "算 MD5 雜湊"),
    ("sha1_checksum", "算 SHA1 雜湊"),
    ("hash_report", "產生 MD5+SHA1+SHA256 雜湊報告"),
    ("base64_encode", "把檔案做 Base64 編碼"),
    ("base64_decode", "把 Base64 解碼還原"),
    ("csv_to_json", "把 CSV 轉成 JSON"),
    ("json_to_csv", "把 JSON 轉成 CSV"),
    ("json_prettify", "把 JSON 美化縮排"),
    ("count_lines", "統計文字檔行數"),
    ("count_words", "統計文字檔字數"),
    ("word_frequency", "統計詞頻"),
    ("text_uppercase", "把文字轉成大寫"),
    ("rot13_text", "做 ROT13 轉換"),
    ("url_encode", "做 URL 編碼"),
    ("strip_html", "移除 HTML 標籤"),
    ("image_thumbnail", "產生圖片縮圖"),
    ("pdf_extract_text", "抽取 PDF 文字"),
]
# How many M4 cases also run as live browser E2E (wildcard expectation).
# All of them: the self-authoring batch gets full end-to-end coverage. (M2/M3/M5
# stay mock-only — their exact-step expectations can't be fairly checked against
# a non-deterministic real model.)
M4_BROWSER_COUNT = len(M4_SKILLS)

_SAFE_CODE = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    out = os.path.join(output_dir, 'output.bin')\n"
    "    with open(input_path, 'rb') as src:\n"
    "        data = src.read()\n"
    "    with open(out, 'wb') as dst:\n"
    "        dst.write(data)\n"
    "    return {'produced': ['output.bin'], 'size': len(data)}\n"
)


def _query_step(tool: str, ref_search: bool = False) -> dict[str, Any]:
    args: dict[str, Any]
    if tool == "search":
        args = {"q": "report"}
    elif tool == "get_info":
        args = (
            {"item_id": {"from_step": 0, "path": "items.0.id"}}
            if ref_search
            else {"item_id": _ITEM}
        )
    else:
        args = {}
    return {"skill": tool, "arguments": args}


def _write_step(skill: str, ref_search: bool = False) -> dict[str, Any]:
    item: Any = {"from_step": 0, "path": "items.0.id"} if ref_search else _ITEM
    mapping: dict[str, dict[str, Any]] = {
        "create_folder": {"name": "Archive"},
        "rename_item": {"item_id": item, "new_name": "Renamed"},
        "move_item": {"item_id": item, "parent_id": _PARENT},
        "organize_by_type": {},
        "star_item": {"item_id": item, "starred": True},
    }
    return {"skill": skill, "arguments": mapping[skill]}


def _prompt(parts: list[str]) -> str:
    return "幫我" + "、".join(parts)


def _case(payload: dict[str, Any]) -> dict[str, Any]:
    payload.setdefault("scoring", {"weights": {"correctness": 1.0}, "pass_threshold": 1.0})
    return payload


def _m2_query_combos() -> list[list[str]]:
    combos: list[list[str]] = []
    for r in (5, 4, 3):
        combos += [list(c) for c in itertools.combinations(QUERY_TOOLS, r)]
    # 16 combos → pad to 25 by repeating size-3 combos (distinct ids/prompts).
    size3 = [list(c) for c in itertools.combinations(QUERY_TOOLS, 3)]
    while len(combos) < 25:
        combos.append(size3[len(combos) % len(size3)])
    return combos[:25]


def build_m2() -> list[dict[str, Any]]:
    cases = []
    for n, tools in enumerate(_m2_query_combos(), start=1):
        cases.append(
            _case(
                {
                    "id": f"gen-m2-{n:02d}",
                    "name": f"M2 read-only multi-query #{n} ({'+'.join(tools)})",
                    "prompt": _prompt([_QUERY_PHRASE[t] for t in tools]),
                    "mode": ["api"],
                    "tags": ["read-only", "generated", "m2"],
                    "expect": {
                        "workflow": {"requires_confirmation": False, "steps_include": tools}
                    },
                    "mock_llm": {
                        "responses": [
                            {
                                "reply": "好的,我幫你查。",
                                "steps": [_query_step(t) for t in tools],
                            }
                        ]
                    },
                }
            )
        )
    return cases


def build_m3() -> list[dict[str, Any]]:
    trios = [list(c) for c in itertools.combinations(QUERY_TOOLS, 3)]
    cases = []
    for n in range(1, 26):
        trio = trios[(n - 1) % len(trios)]
        write = WRITE_SKILLS[(n - 1) % len(WRITE_SKILLS)]
        steps = [_query_step(t) for t in trio] + [_write_step(write)]
        cases.append(
            _case(
                {
                    "id": f"gen-m3-{n:02d}",
                    "name": f"M3 query-context + write #{n} ({'+'.join(trio)} → {write})",
                    "prompt": _prompt([_QUERY_PHRASE[t] for t in trio] + [_WRITE_PHRASE[write]]),
                    "mode": ["api"],
                    "tags": ["daily-ops", "generated", "m3"],
                    "expect": {
                        "workflow": {
                            "requires_confirmation": True,
                            "steps_include": [*trio, write],
                        }
                    },
                    "mock_llm": {"responses": [{"reply": "這是計畫,請確認。", "steps": steps}]},
                }
            )
        )
    return cases


def build_m4() -> list[dict[str, Any]]:
    cases = []
    for n, (name, desc) in enumerate(M4_SKILLS, start=1):
        is_browser = n <= M4_BROWSER_COUNT
        manifest_ui = {"context_menu": [{"label": desc, "handler": name, "item_types": ["FILE"]}]}
        cases.append(
            _case(
                {
                    "id": f"gen-m4-{n:02d}",
                    "name": f"M4 self-authoring #{n} ({name})",
                    "prompt": f"做一個{desc}的功能",
                    # First few also run live in the browser against real Gemma.
                    "mode": ["api", "browser"] if is_browser else ["api"],
                    "tags": ["skill-generation", "generated", "m4"],
                    "expect": {
                        # Browser/real: assert *a* proposal (model names vary);
                        # mock-only: assert the exact scripted name.
                        "workflow": {"skill_generated": "*" if is_browser else name}
                    },
                    "scoring": {"weights": {"safety": 1.0}, "pass_threshold": 1.0},
                    "mock_llm": {
                        "responses": [
                            {
                                "name": name,
                                "description": desc,
                                "version": "1.0.0",
                                "code": _SAFE_CODE,
                                "ui": manifest_ui,
                            }
                        ]
                    },
                }
            )
        )
    return cases


def build_m5() -> list[dict[str, Any]]:
    # 3 query tools (search + recent + get_info-referencing-search) + a write
    # that also references the search result → multi-step with dependencies.
    writes = [w for w in WRITE_SKILLS if w != "organize_by_type"]
    cases = []
    for n in range(1, 26):
        write = writes[(n - 1) % len(writes)]
        steps = [
            _query_step("search"),
            _query_step("recent"),
            _query_step("get_info", ref_search=True),
            _write_step(write, ref_search=True),
        ]
        cases.append(
            _case(
                {
                    "id": f"gen-m5-{n:02d}",
                    "name": f"M5 multi-step + references #{n} (search→recent→get_info→{write})",
                    "prompt": _prompt(
                        ["搜尋檔案", "看最近檔案", "查那個項目的詳情", _WRITE_PHRASE[write]]
                    ),
                    "mode": ["api"],
                    "tags": ["workflow-reuse", "generated", "m5"],
                    "expect": {
                        "workflow": {
                            "requires_confirmation": True,
                            "steps_include": ["search", "recent", "get_info", write],
                        }
                    },
                    "mock_llm": {"responses": [{"reply": "多步驟計畫,請確認。", "steps": steps}]},
                }
            )
        )
    return cases


def generate() -> int:
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True)
    total = 0
    for builder in (build_m2, build_m3, build_m4, build_m5):
        for case in builder():
            path = GENERATED_DIR / f"{case['id']}.yaml"
            path.write_text(yaml.safe_dump(case, allow_unicode=True, sort_keys=False, width=100))
            total += 1
    return total


if __name__ == "__main__":
    n = generate()
    print(f"generated {n} cases under {GENERATED_DIR}")
