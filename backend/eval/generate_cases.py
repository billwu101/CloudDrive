"""Generator for the M2-M5 eval case suite (100 cases per level = 400).

Produces deterministic cases under ``eval/cases/generated/`` with a scripted
``mock_llm`` (so mock mode passes deterministically) and ``mode: [api, browser]``
so they also run live. Mock mode checks exact steps; browser mode loosens to
"plan produced + correct confirmation tier" (run.py passes strict_steps=False),
because a non-deterministic model won't reproduce an exact skill sequence.

Levels (max complexity, 3+ query tools where applicable):
- M2: read-only multi-tool workflows combining 3+ query tools (auto-executed).
- M3: 3+ query tools as context + a write/batch skill (needs confirmation).
- M4: self-authoring generation (100 distinct skill types; skill_generated "*").
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
PER_LEVEL = 100

QUERY_TOOLS = ["search", "list_items", "get_info", "recent", "storage_quota"]
WRITE_SKILLS = ["create_folder", "rename_item", "move_item", "organize_by_type", "star_item"]

_ITEM = "11111111-1111-1111-1111-111111111111"
_PARENT = "22222222-2222-2222-2222-222222222222"
_SEARCH_TERMS = ["report", "invoice", "photo", "draft", "2024", "budget", "notes"]

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


def _query_step(tool: str, term: str = "report", ref_search: bool = False) -> dict[str, Any]:
    if tool == "search":
        return {"skill": "search", "arguments": {"q": term}}
    if tool == "get_info":
        item: Any = {"from_step": 0, "path": "items.0.id"} if ref_search else _ITEM
        return {"skill": "get_info", "arguments": {"item_id": item}}
    return {"skill": tool, "arguments": {}}


def _write_step(skill: str, idx: int = 0, ref_search: bool = False) -> dict[str, Any]:
    item: Any = {"from_step": 0, "path": "items.0.id"} if ref_search else _ITEM
    mapping: dict[str, dict[str, Any]] = {
        "create_folder": {"name": f"Folder{idx}"},
        "rename_item": {"item_id": item, "new_name": f"Renamed{idx}"},
        "move_item": {"item_id": item, "parent_id": _PARENT},
        "organize_by_type": {},
        "star_item": {"item_id": item, "starred": True},
    }
    return {"skill": skill, "arguments": mapping[skill]}


def _prompt(parts: list[str]) -> str:
    return "幫我" + "、".join(parts)


def _write_first_prompt(write_phrase: str, query_phrases: list[str]) -> str:
    # Lead with the write action so the real model reliably plans a write
    # (pending-approval) step; query tools are secondary context.
    return f"幫我{write_phrase}（過程中可先{'、'.join(query_phrases)}）"


def _scoring(dim: str = "correctness") -> dict[str, Any]:
    # min_pass_rate is the multi-run acceptance bar: under `--runs N` (real model)
    # a case passes if it succeeds in >= 60% of runs. At runs=1 (deterministic
    # mock) this still requires the single run to pass, so mock stays strict.
    return {"weights": {dim: 1.0}, "pass_threshold": 1.0, "min_pass_rate": 0.6}


# Real tasks a user would actually ask, each of which genuinely needs ALL FIVE
# read-only tools (search / list_items / get_info / recent / storage_quota) —
# rather than stringing the tool names together. `tools` is the natural order the
# task implies; `reason` explains why those five (and why in that order).
M2_SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "cleanup_space",
        "title": "清理空間",
        "tools": ["storage_quota", "list_items", "search", "recent", "get_info"],
        "reason": (
            "清理空間需要五個視角：先看用量了解為何快滿（storage_quota）→ 盤點根目錄"
            "分佈（list_items）→ 定位佔空間的特定主題檔（search）→ 辨識最近還在用、"
            "不該刪的檔（recent）→ 確認候選檔的實際大小再決定（get_info）。"
        ),
        "prompt": (
            "我的雲端空間快滿了，幫我先看目前容量用了多少、列出根目錄有哪些檔案、"
            "搜尋跟「{t}」有關的大型檔案、看看我最近還在用哪些檔（這些先留著），"
            "最後把其中一個檔的詳細大小列出來，我想清理空間。"
        ),
    },
    {
        "key": "resume_work",
        "title": "接續工作",
        "tools": ["recent", "list_items", "search", "get_info", "storage_quota"],
        "reason": (
            "回到工作現場：從最近開過的檔找回接續點（recent）→ 重新熟悉目前結構"
            "（list_items）→ 定位該主題的檔（search）→ 確認關鍵檔的細節（get_info）→ "
            "確認容量是否夠存新版本（storage_quota）。"
        ),
        "prompt": (
            "我想接續之前在處理的「{t}」，幫我看我最近開過哪些檔、列一下根目錄目前的"
            "結構、搜尋「{t}」相關的檔案、打開最相關的那個看它的詳情，順便確認容量還"
            "夠不夠再存新版本。"
        ),
    },
    {
        "key": "handover_project",
        "title": "交接專案",
        "tools": ["list_items", "search", "get_info", "recent", "storage_quota"],
        "reason": (
            "交接盤點：列出整體結構（list_items）→ 搜出專案相關檔（search）→ 查主要檔"
            "的詳情（get_info）→ 確認最近哪些有更新（recent）→ 估整體佔用規模"
            "（storage_quota），據以寫交接清單。"
        ),
        "prompt": (
            "我要把「{t}」交接給同事，幫我列出根目錄、搜尋這個專案的相關檔案、查看其中"
            "主要檔案的詳情、確認最近哪些檔有被更新過、以及整體佔用多少空間，好讓我寫"
            "交接清單。"
        ),
    },
    {
        "key": "find_lost_file",
        "title": "找回舊檔",
        "tools": ["search", "recent", "list_items", "get_info", "storage_quota"],
        "reason": (
            "找一份忘記位置的檔：先用關鍵字搜尋（search）→ 從最近開過的檔回想"
            "（recent）→ 瀏覽根目錄找（list_items）→ 找到後看大小與修改時間確認是它"
            "（get_info）→ 順帶掌握容量狀況（storage_quota）。"
        ),
        "prompt": (
            "我記得有一份「{t}」的檔但忘了放在哪，幫我搜尋看看、列出我最近開過的檔、"
            "也看一下根目錄有沒有，找到後給我它的大小與修改時間，順便看一下我的容量狀況。"
        ),
    },
    {
        "key": "monthly_audit",
        "title": "月底盤點",
        "tools": ["storage_quota", "list_items", "recent", "search", "get_info"],
        "reason": (
            "定期盤點：總量（storage_quota）→ 分佈（list_items）→ 本期異動（recent）→ "
            "主題彙整（search）→ 抽樣細節（get_info），產出月度整理。"
        ),
        "prompt": (
            "月底了幫我做個盤點：先看容量用了多少、列出根目錄有哪些東西、這個月最近"
            "更新過哪些檔、搜尋「{t}」相關的檔案、並挑一個看它的詳情，我要寫月度整理。"
        ),
    },
]

# 20 realistic things a user would look for; 5 scenarios x 20 topics = 100.
M2_TOPICS = [
    "報告",
    "發票",
    "照片",
    "草稿",
    "預算",
    "會議記錄",
    "合約",
    "履歷",
    "簡報",
    "收據",
    "報稅",
    "旅遊",
    "專案計畫",
    "備份",
    "使用手冊",
    "設計稿",
    "論文",
    "訂單",
    "帳單",
    "課程筆記",
]


def build_m2() -> list[dict[str, Any]]:
    """M2 = read-only tasks that each genuinely use all five query tools.

    Cases are real scenarios (cleanup / resume work / handover / find a lost file
    / monthly audit) parametrised by topic, not arbitrary tool combinations.
    """
    cases = []
    n = 0
    for scenario in M2_SCENARIOS:
        tools = scenario["tools"]
        for topic in M2_TOPICS:
            n += 1
            if n > PER_LEVEL:
                break
            cases.append(
                {
                    "id": f"gen-m2-{n:03d}",
                    "name": f"M2 {scenario['title']}：{topic}（{'+'.join(tools)}）",
                    "rationale": scenario["reason"],
                    "prompt": scenario["prompt"].format(t=topic),
                    "mode": ["api", "browser"],
                    "tags": ["read-only", "generated", "m2", f"scenario:{scenario['key']}"],
                    "expect": {
                        "workflow": {"requires_confirmation": False, "steps_include": tools}
                    },
                    "scoring": _scoring(),
                    "mock_llm": {
                        "responses": [
                            {
                                "reply": "好的，我幫你查。",
                                "steps": [_query_step(t, topic) for t in tools],
                            }
                        ]
                    },
                }
            )
    return cases


def build_m3() -> list[dict[str, Any]]:
    trios = [list(c) for c in itertools.combinations(QUERY_TOOLS, 3)]  # 10
    cases = []
    n = 0
    for term in _SEARCH_TERMS:
        for trio in trios:
            for write in WRITE_SKILLS:
                n += 1
                if n > PER_LEVEL:
                    break
                steps = [_query_step(t, term) for t in trio] + [_write_step(write, n)]
                cases.append(
                    {
                        "id": f"gen-m3-{n:03d}",
                        "name": f"M3 query+write #{n} ({'+'.join(trio)}->{write})",
                        "prompt": _write_first_prompt(
                            _WRITE_PHRASE[write], [_QUERY_PHRASE[t] for t in trio]
                        ),
                        "mode": ["api", "browser"],
                        "tags": ["daily-ops", "generated", "m3"],
                        "expect": {
                            "workflow": {
                                "requires_confirmation": True,
                                "steps_include": [*trio, write],
                            }
                        },
                        "scoring": _scoring(),
                        "mock_llm": {"responses": [{"reply": "計畫如下,請確認。", "steps": steps}]},
                    }
                )
            if n > PER_LEVEL:
                break
        if n > PER_LEVEL:
            break
    return cases[:PER_LEVEL]


def build_m5() -> list[dict[str, Any]]:
    writes = [w for w in WRITE_SKILLS if w != "organize_by_type"]  # need item_id ref
    combos = [["search", "recent", "get_info"], ["search", "list_items", "get_info"]]
    cases = []
    n = 0
    for term in _SEARCH_TERMS:
        for base in combos:
            for write in writes:
                for _variant in range(2):
                    n += 1
                    if n > PER_LEVEL:
                        break
                    steps = [
                        _query_step("search", term),
                        *[_query_step(t, term, ref_search=(t == "get_info")) for t in base[1:]],
                        _write_step(write, n, ref_search=True),
                    ]
                    cases.append(
                        {
                            "id": f"gen-m5-{n:03d}",
                            "name": f"M5 multi-step+refs #{n} ({'+'.join(base)}->{write})",
                            "prompt": _write_first_prompt(
                                _WRITE_PHRASE[write], [_QUERY_PHRASE[t] for t in base]
                            ),
                            "mode": ["api", "browser"],
                            "tags": ["workflow-reuse", "generated", "m5"],
                            "expect": {
                                "workflow": {
                                    "requires_confirmation": True,
                                    "steps_include": [*base, write],
                                }
                            },
                            "scoring": _scoring(),
                            "mock_llm": {
                                "responses": [{"reply": "多步驟計畫,請確認。", "steps": steps}]
                            },
                        }
                    )
                if n > PER_LEVEL:
                    break
            if n > PER_LEVEL:
                break
        if n > PER_LEVEL:
            break
    return cases[:PER_LEVEL]


def _m4_skills() -> list[tuple[str, str]]:
    skills: list[tuple[str, str]] = []
    for algo in [
        "md5",
        "sha1",
        "sha256",
        "sha512",
        "sha224",
        "sha384",
        "blake2b",
        "blake2s",
        "crc32",
    ]:
        skills.append((f"{algo}_checksum", f"算 {algo.upper()} 雜湊"))
    for op, zh in [("encode", "編碼"), ("decode", "解碼")]:
        for enc in ["base64", "base32", "hex", "url", "ascii85"]:
            skills.append((f"{enc}_{op}", f"做 {enc} {zh}"))
    skills += [
        ("rot13_text", "做 ROT13 轉換"),
        ("html_escape", "做 HTML 跳脫"),
        ("html_unescape", "還原 HTML 跳脫"),
    ]
    for op, zh in [("extract", "解開"), ("compress", "壓成")]:
        for fmt in ["zip", "tar", "gzip", "bz2", "xz", "7z"]:
            # name must be a valid identifier — keep the digit-leading fmt as a suffix.
            skills.append((f"{op}_{fmt}", f"{zh} {fmt}"))
    skills += [
        ("count_lines", "統計行數"),
        ("count_words", "統計字數"),
        ("count_chars", "統計字元數"),
        ("uppercase_text", "轉成大寫"),
        ("lowercase_text", "轉成小寫"),
        ("titlecase_text", "轉成首字大寫"),
        ("reverse_lines", "反轉行序"),
        ("sort_lines", "排序每一行"),
        ("dedupe_lines", "去除重複行"),
        ("strip_blank_lines", "移除空白行"),
        ("number_lines", "為每行加行號"),
        ("wrap_lines", "把長行折成 80 字"),
        ("head_lines", "取前 10 行"),
        ("tail_lines", "取後 10 行"),
        ("trim_whitespace", "去除前後空白"),
        ("slugify_text", "把文字轉成 slug"),
    ]
    skills += [
        ("csv_to_json", "把 CSV 轉成 JSON"),
        ("json_to_csv", "把 JSON 轉成 CSV"),
        ("csv_to_tsv", "把 CSV 轉成 TSV"),
        ("tsv_to_csv", "把 TSV 轉成 CSV"),
        ("json_prettify", "把 JSON 美化縮排"),
        ("json_minify", "把 JSON 壓成單行"),
        ("flatten_json", "把巢狀 JSON 攤平"),
        ("json_keys", "列出 JSON 的所有鍵"),
    ]
    skills += [
        ("image_thumbnail", "產生圖片縮圖"),
        ("image_grayscale", "把圖片轉灰階"),
        ("image_resize_half", "把圖片縮一半"),
        ("image_rotate_90", "把圖片旋轉 90 度"),
        ("image_flip_horizontal", "把圖片左右翻轉"),
        ("image_flip_vertical", "把圖片上下翻轉"),
        ("image_to_png", "把圖片轉成 PNG"),
        ("image_to_jpeg", "把圖片轉成 JPEG"),
        ("image_to_webp", "把圖片轉成 WebP"),
        ("image_info", "讀出圖片尺寸資訊"),
        ("image_crop_center", "置中裁切圖片"),
        ("image_invert", "反相圖片顏色"),
        ("image_blur", "把圖片模糊化"),
        ("image_sepia", "把圖片轉復古色"),
    ]
    skills += [
        ("pdf_extract_text", "抽取 PDF 文字"),
        ("pdf_page_count", "數 PDF 頁數"),
        ("pdf_metadata", "讀 PDF 中繼資料"),
        ("pdf_rotate_pages", "旋轉 PDF 每一頁"),
        ("pdf_split_pages", "把 PDF 拆成單頁"),
        ("pdf_first_page", "抽出 PDF 第一頁"),
    ]
    skills += [
        ("file_info", "讀出檔案大小與類型"),
        ("to_lf_endings", "把換行統一成 LF"),
        ("tabs_to_spaces", "把 Tab 換成空白"),
        ("remove_bom", "移除檔案 BOM"),
        ("count_bytes", "統計位元組數"),
        ("hexdump_file", "產生檔案 hex dump"),
        ("base32_hex", "把檔案轉 base32hex"),
        ("gzip_level9", "用最高壓縮率壓 gzip"),
    ]
    skills += [
        ("collapse_spaces", "合併連續空白"),
        ("remove_punctuation", "移除標點符號"),
        ("char_frequency", "統計字元頻率"),
        ("longest_line", "找出最長的一行"),
        ("unique_words", "列出不重複的詞"),
        ("snake_to_camel", "把底線命名轉駝峰"),
        ("json_sort_keys", "把 JSON 的鍵排序"),
        ("csv_headers", "列出 CSV 欄位名"),
        ("csv_row_count", "數 CSV 列數"),
        ("json_to_jsonl", "把 JSON 陣列轉成 JSONL"),
        ("base85_encode", "做 base85 編碼"),
        ("quoted_printable_encode", "做 quoted-printable 編碼"),
        ("image_posterize", "把圖片做色階化"),
        ("image_autocontrast", "自動調整圖片對比"),
        ("adler32_checksum", "算 Adler32 雜湊"),
        ("strip_ansi", "移除 ANSI 控制碼"),
        ("count_paragraphs", "統計段落數"),
    ]
    return skills


def build_m4() -> list[dict[str, Any]]:
    skills = _m4_skills()
    assert len(skills) >= PER_LEVEL, f"need >= {PER_LEVEL} M4 skills, have {len(skills)}"
    cases = []
    for n, (name, desc) in enumerate(skills[:PER_LEVEL], start=1):
        cases.append(
            {
                "id": f"gen-m4-{n:03d}",
                "name": f"M4 self-authoring #{n} ({name})",
                "prompt": f"做一個{desc}的功能",
                "mode": ["api", "browser"],
                "tags": ["skill-generation", "generated", "m4"],
                "expect": {"workflow": {"skill_generated": "*"}},
                "scoring": _scoring("safety"),
                "mock_llm": {
                    "responses": [
                        {
                            "name": name,
                            "description": desc,
                            "version": "1.0.0",
                            "code": _SAFE_CODE,
                            "ui": {
                                "context_menu": [
                                    {"label": desc, "handler": name, "item_types": ["FILE"]}
                                ]
                            },
                        }
                    ]
                },
            }
        )
    return cases


def generate() -> int:
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True)
    total = 0
    for builder in (build_m2, build_m3, build_m4, build_m5):
        built = builder()
        assert len(built) == PER_LEVEL, (
            f"{builder.__name__} produced {len(built)} (want {PER_LEVEL})"
        )
        for case in built:
            (GENERATED_DIR / f"{case['id']}.yaml").write_text(
                yaml.safe_dump(case, allow_unicode=True, sort_keys=False, width=100)
            )
            total += 1
    return total


if __name__ == "__main__":
    n = generate()
    print(f"generated {n} cases under {GENERATED_DIR}")
