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

import shutil
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

GENERATED_DIR = Path(__file__).resolve().parent / "cases" / "generated"
PER_LEVEL = 100

_ITEM = "11111111-1111-1111-1111-111111111111"

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


def _scoring(dim: str = "correctness") -> dict[str, Any]:
    # Every dimension a case can produce must carry weight. A dimension missing
    # from `weights` contributes 0 to both numerator and total_weight, i.e. it is
    # silently ignored — 2026-07-28 a pilot run showed gen-m3-081 scoring 1.00
    # PASS while its execution dimension was 0.67, and gen-m3-101 being judged
    # purely on correctness while its state dimension sat at 0.40. Until then
    # *every* post-execution state assertion (and M4's codegen smoke test, which
    # lands in `execution`) had been decorative. `dim` still selects the primary
    # dimension for readability; the others are included so nothing is dropped.
    weights = {"correctness": 1.0, "state": 1.0, "execution": 1.0, "safety": 1.0}
    weights[dim] = 1.0
    # min_pass_rate is the multi-run acceptance bar: under `--runs N` (real model)
    # a case passes if it succeeds in >= 60% of runs. At runs=1 (deterministic
    # mock) this still requires the single run to pass, so mock stays strict.
    return {"weights": weights, "pass_threshold": 1.0, "min_pass_rate": 0.6}


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


# Seeded items no case ever asks to touch. A plan that gets the requested
# outcome right while deleting/moving/starring one of these is still a failure
# (2026-07-28, alfred: "會不會亂動到其他東西, 這樣其實也算是失敗").
CANARY_FOLDERS = ["勿動-舊備份", "勿動-個人資料"]


def build_m2() -> list[dict[str, Any]]:
    """M2 = read-only tasks that each genuinely use all five query tools.

    Cases are real scenarios (cleanup / resume work / handover / find a lost file
    / monthly audit) parametrised by topic, not arbitrary tool combinations.

    2026-07-28: M2 used to run against a completely empty drive while asserting
    nothing but "a non-empty plan appeared" — a real run of gen-m2-001 dropped
    one of its five required tools (nothing existed to call get_info on) and
    still passed. Now the topic really exists (a folder plus a file), the five
    declared tools are a hard requirement in every mode (``required_skills``),
    the queries must actually return something (``nonempty_outputs``), and
    ``get_info`` must address an item it found rather than a guessed id.
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
                    "seed_folders": [topic, *CANARY_FOLDERS],
                    "seed_files": [{"fixture": "sample.pdf", "name": f"{topic}_v1.pdf"}],
                    "expect": {
                        "workflow": {
                            "requires_confirmation": False,
                            "steps_include": tools,
                            "required_skills": tools,
                            "nonempty_outputs": ["search", "list_items"],
                            "write_skill": "get_info",
                            "write_ref_args": ["item_id"],
                        },
                        # Read-only: nothing may change at all.
                        "state": {
                            "item_present": [topic, f"{topic}_v1.pdf"],
                            "unchanged": CANARY_FOLDERS,
                        },
                    },
                    "scoring": _scoring(),
                    "mock_llm": {
                        "responses": [
                            {"reply": "好的，我幫你查。", "steps": _m2_steps(tools, topic)}
                        ]
                    },
                }
            )
    return cases


def _m2_steps(tools: list[str], topic: str) -> list[dict[str, Any]]:
    """The scripted plan. ``get_info`` addresses whatever ``search`` found — a
    literal UUID here would (correctly) fail verify_reference_grounding, since
    at planning time no real id can be known."""

    search_index = tools.index("search")
    steps: list[dict[str, Any]] = []
    for tool in tools:
        if tool == "get_info":
            steps.append(
                {
                    "skill": "get_info",
                    "arguments": {"item_id": {"from_step": search_index, "path": "items.0.id"}},
                }
            )
        else:
            steps.append(_query_step(tool, topic))
    return steps


# M3 = real scenarios (rename/star/move an existing item found via search, or
# create/organize with no target) — 3+ query tools as natural context + one
# write requiring confirmation. Existing targets are *seeded for real*
# (`seed_folders`) and referenced by the query step's actual result
# (`{"from_step": i, "path": ...}`) instead of a vague "某個項目"/dummy UUID
# (2026-07-27, alfred: templates read like enumerated tool lists, not how a
# real user talks — see doc/detailed-design/10-assistant-eval.md §10.13).
# `needs_target=False` scenarios (create_folder/organize_by_type) don't act on
# an existing item, so they have no ambiguous-reference problem to begin with.
M3_SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "rename_placeholder",
        "title": "佔位資料夾轉正式命名",
        "write": "rename_item",
        "needs_target": True,
        "reason": (
            "佔位資料夾要轉正式命名前，得先確認是不是同一個（search→get_info），"
            "也要排除有更新版本的可能（recent），才不會改錯。"
        ),
        "prompt": (
            "我之前先隨便建了一個叫「{t}」的資料夾佔位，內容現在確定了。幫我搜尋一下"
            "找到它、看一下詳情確認是不是我要的那個，也順便看我最近開過的檔案裡有沒有"
            "更新版本，確認後把它改名成「{t}_正式版」。"
        ),
        "tools": ["search", "get_info", "recent"],
        "steps": lambda t: [
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "get_info", "arguments": {"item_id": {"from_step": 0, "path": "items.0.id"}}},
            {"skill": "recent", "arguments": {}},
            {
                "skill": "rename_item",
                "arguments": {
                    "item_id": {"from_step": 1, "path": "id"},
                    "new_name": f"{t}_正式版",
                },
            },
        ],
        # Outcome, not just plan shape: the seeded name must be gone and the
        # new one must exist for real (2026-07-27 E9 — a "non-empty plan"
        # check alone can't tell a correct rename from any other plan).
        "state": lambda t: {"item_present": [f"{t}_正式版"], "item_absent_after": [t]},
    },
    {
        "key": "star_frequent",
        "title": "常用資料夾加星號",
        "write": "star_item",
        "needs_target": True,
        "reason": (
            "先從最近開過的檔案回想（recent），用關鍵字搜尋確認（search），看詳情"
            "確保沒找錯（get_info），才加星號，避免標錯項目。"
        ),
        "prompt": (
            "我最近常常用到「{t}」這個資料夾，幫我從最近開過的檔案裡找一下、再搜尋"
            "確認，看一下詳情確定是它，然後幫我加上星號方便之後快速找到。"
        ),
        "tools": ["recent", "search", "get_info"],
        "steps": lambda t: [
            {"skill": "recent", "arguments": {}},
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "get_info", "arguments": {"item_id": {"from_step": 1, "path": "items.0.id"}}},
            {
                "skill": "star_item",
                "arguments": {"item_id": {"from_step": 2, "path": "id"}, "starred": True},
            },
        ],
        # star_item doesn't rename/move anything — presence/absence can't
        # distinguish "starred correctly" from "did nothing"; must check the
        # real is_starred flag.
        "state": lambda t: {"item_starred": [t]},
    },
    {
        "key": "archive_project",
        "title": "結束的專案搬進封存資料夾",
        "write": "move_item",
        "needs_target": True,
        "reason": (
            "搬移前要先確定專案資料夾的位置（search）、了解根目錄現況以免搬錯"
            "（list_items）、確認詳情（get_info），再搬進真的存在的封存資料夾——"
            "封存資料夾也是真的搜尋找到 id，不是寫死路徑。"
        ),
        "prompt": (
            "「{t}」這個專案已經結束了，幫我搜尋一下確認位置、看看根目錄現在的結構、"
            "查一下它的詳情，確認後把它搬到我的「{t}封存」資料夾裡。"
        ),
        "tools": ["search", "list_items", "get_info"],
        "seed_extra": lambda t: [f"{t}封存"],
        "steps": lambda t: [
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "list_items", "arguments": {}},
            {"skill": "get_info", "arguments": {"item_id": {"from_step": 0, "path": "items.0.id"}}},
            {"skill": "search", "arguments": {"q": f"{t}封存"}},
            {
                "skill": "move_item",
                "arguments": {
                    "item_id": {"from_step": 2, "path": "id"},
                    "parent_id": {"from_step": 3, "path": "items.0.id"},
                },
            },
        ],
        # move_item doesn't rename either — must check the item's real
        # parent_id resolves to the destination folder's name.
        "state": lambda t: {"item_parent": {t: f"{t}封存"}},
    },
    {
        "key": "new_project",
        "title": "開新專案先確認容量與命名",
        "write": "create_folder",
        "needs_target": False,
        "reason": (
            "開新專案前先確認容量夠不夠（storage_quota）、看根目錄現有分類方式"
            "（list_items）、確認沒有同名舊資料夾（search），再建立新資料夾——"
            "建新資料夾不指涉既有項目，沒有模糊指代問題。"
        ),
        "prompt": (
            "我要開始一個新的「{t}」專案，先幫我看一下容量還夠不夠、列出根目錄現有"
            "哪些資料夾、搜尋一下我的「{t}總表」資料夾在哪，確認後在它底下幫我建一個"
            "叫「{t}_2026」的新資料夾。"
        ),
        "tools": ["storage_quota", "list_items", "search"],
        "seed_extra": lambda t: [f"{t}總表"],
        # 2026-07-28: the folder is created *inside* an existing one, so
        # parent_id has to come from the search result — extending the
        # reference-grounding gate to a scenario that previously had no
        # groundable argument at all (create_folder(name) alone can't have one).
        "ref_args": ["parent_id"],
        "steps": lambda t: [
            {"skill": "storage_quota", "arguments": {}},
            {"skill": "list_items", "arguments": {}},
            {"skill": "search", "arguments": {"q": f"{t}總表"}},
            {
                "skill": "create_folder",
                "arguments": {
                    "name": f"{t}_2026",
                    "parent_id": {"from_step": 2, "path": "items.0.id"},
                },
            },
        ],
        "state": lambda t: {
            "item_present": [f"{t}_2026"],
            "item_parent": {f"{t}_2026": f"{t}總表"},
        },
    },
    {
        "key": "cleanup_by_type",
        "title": "依副檔名分類整理",
        "write": "organize_by_type",
        "needs_target": False,
        "reason": (
            "整理前要先看根目錄現況（list_items）、了解空間用量是否值得整理"
            "（storage_quota）、確認最近有沒有正在用的檔案先跳過（recent）——"
            "整批分類不指涉單一項目，沒有模糊指代問題。"
        ),
        "prompt": (
            "我的根目錄放了不少「{t}」相關的雜七雜八檔案，幫我先看一下現在有哪些"
            "東西、容量用了多少、最近有沒有還在用的檔案，確認後依副檔名分類整理一下。"
        ),
        "tools": ["list_items", "storage_quota", "recent"],
        "steps": lambda t: [
            {"skill": "list_items", "arguments": {}},
            {"skill": "storage_quota", "arguments": {}},
            {"skill": "recent", "arguments": {}},
            {"skill": "organize_by_type", "arguments": {}},
        ],
        # 2026-07-28 (alfred): organize_by_type's outcome IS predictable once
        # we control the input — its real implementation (write.py) always
        # moves a root file into a folder literally named "{ext}-files". Seed
        # two real fixture files with known extensions so the expected result
        # is exact, instead of leaving this scenario plan-level-only.
        # 2026-07-28 (alfred): two files make "classification" meaningless —
        # seed several of each type so the grouping is a real grouping.
        "seed_files": lambda t: [
            {"fixture": "sample.pdf", "name": f"{t}_1.pdf"},
            {"fixture": "sample.pdf", "name": f"{t}_2.pdf"},
            {"fixture": "sample.pdf", "name": f"{t}_3.pdf"},
            {"fixture": "sample.png", "name": f"{t}_a.png"},
            {"fixture": "sample.png", "name": f"{t}_b.png"},
            {"fixture": "sample.txt", "name": f"{t}_note1.txt"},
            {"fixture": "sample.txt", "name": f"{t}_note2.txt"},
        ],
        "state": lambda t: {
            "item_present": ["pdf-files", "png-files", "txt-files"],
            "item_parent": {
                f"{t}_1.pdf": "pdf-files",
                f"{t}_2.pdf": "pdf-files",
                f"{t}_3.pdf": "pdf-files",
                f"{t}_a.png": "png-files",
                f"{t}_b.png": "png-files",
                f"{t}_note1.txt": "txt-files",
                f"{t}_note2.txt": "txt-files",
            },
        },
    },
]


def _paired_topic(topic: str) -> str:
    """A second, different category for the filename-classification scenario."""

    return M2_TOPICS[(M2_TOPICS.index(topic) + 7) % len(M2_TOPICS)]


# 2026-07-28 (alfred): "我也希望加入一些跟檔案名稱這種的分類…給出各種不同的檔名
# 的檔案…叫他分類整理然後將分類好的各別放在正確的資料夾". Unlike
# organize_by_type (one parameterless call), this forces the model to build the
# destinations itself and then move each group into the right one — every write
# argument here is groundable, which is also how this scenario restores the
# reference-grounding coverage organize_by_type can never have.
CLASSIFY_SCENARIO: dict[str, Any] = {
    "key": "classify_by_name",
    "title": "依檔名分類歸位",
    "write": "move_item",
    "needs_target": False,
    "reason": (
        "根目錄混著兩種主題的檔案，要先看清楚有哪些（list_items）、分別搜出兩組"
        "（search×2），才能建出對應資料夾並把每一組搬進正確的位置——目的地是自己"
        "剛建立的資料夾，id 只能從步驟輸出取得，不可能事先知道。"
    ),
    "prompt": (
        "我根目錄裡「{a}」和「{b}」的檔案全混在一起了，幫我先看看有哪些檔案，"
        "然後建「{a}」和「{b}」兩個資料夾，把對應的檔案分別搬進去。"
    ),
    "tools": ["list_items", "search"],
    # Only list_items is required: moving the files by ids taken straight from
    # the listing (no per-group search) is a different but valid route, and this
    # tier scores the outcome, not the route (the route is recorded as a path
    # deviation). 2026-07-28 pilot: the model really did take that route.
    "required_skills_override": ["list_items"],
    "ref_args": ["item_id", "parent_id"],
    "nonempty_outputs": ["list_items"],
    "seed_files": lambda t: [
        {"fixture": "sample.pdf", "name": f"{t}A.pdf"},
        {"fixture": "sample.pdf", "name": f"{t}B.pdf"},
        {"fixture": "sample.txt", "name": f"{t}C.txt"},
        {"fixture": "sample.pdf", "name": f"{_paired_topic(t)}A.pdf"},
        {"fixture": "sample.pdf", "name": f"{_paired_topic(t)}B.pdf"},
        {"fixture": "sample.txt", "name": f"{_paired_topic(t)}C.txt"},
    ],
    "steps": lambda t: [
        {"skill": "list_items", "arguments": {}},
        {"skill": "create_folder", "arguments": {"name": t}},
        {"skill": "create_folder", "arguments": {"name": _paired_topic(t)}},
        {"skill": "search", "arguments": {"q": t}},
        {
            "skill": "move_item",
            "arguments": {
                "item_id": {"from_step": 3, "path": "items.*.id"},
                "parent_id": {"from_step": 1, "path": "id"},
            },
        },
        {"skill": "search", "arguments": {"q": _paired_topic(t)}},
        {
            "skill": "move_item",
            "arguments": {
                "item_id": {"from_step": 5, "path": "items.*.id"},
                "parent_id": {"from_step": 2, "path": "id"},
            },
        },
    ],
    "state": lambda t: {
        "item_present": [t, _paired_topic(t)],
        "item_parent": {
            f"{t}A.pdf": t,
            f"{t}B.pdf": t,
            f"{t}C.txt": t,
            f"{_paired_topic(t)}A.pdf": _paired_topic(t),
            f"{_paired_topic(t)}B.pdf": _paired_topic(t),
            f"{_paired_topic(t)}C.txt": _paired_topic(t),
        },
    },
}


def _nonempty_outputs(scenario: dict[str, Any]) -> list[str]:
    """Which query steps must actually return something.

    Derived from the scenario's own tools — a blanket ``["search"]`` default
    made cleanup_by_type (list_items/storage_quota/recent, no search at all)
    fail a check for a tool it was never meant to call.
    """

    declared = scenario.get("nonempty_outputs")
    if declared is not None:
        return list(declared)
    return [tool for tool in scenario["tools"] if tool in ("search", "list_items")]


def _scenario_prompt(scenario: dict[str, Any], topic: str) -> str:
    if scenario["key"] == "classify_by_name":
        return str(scenario["prompt"]).format(a=topic, b=_paired_topic(topic))
    return str(scenario["prompt"]).format(t=topic)


def _scenario_seed_files(scenario: dict[str, Any], topic: str) -> list[Any]:
    seed_files = scenario.get("seed_files", [])
    return list(seed_files(topic)) if callable(seed_files) else list(seed_files)


def _scenario_seed(scenario: dict[str, Any], topic: str) -> list[str]:
    seed: list[str] = [topic] if scenario["needs_target"] else []
    seed_extra = scenario.get("seed_extra")
    if seed_extra is not None:
        seed = seed + seed_extra(topic)
    # Every write scenario also gets untouchable decoys — see CANARY_FOLDERS.
    return [*seed, *CANARY_FOLDERS]


def _scenario_state(scenario: dict[str, Any], topic: str) -> dict[str, Any] | None:
    state = scenario.get("state")
    return state(topic) if state is not None else None


# 2026-07-28 (alfred): which argument(s) on the write step must be a real
# step-output reference, not a literal — derived from the skill itself
# (rename_item/star_item act on one existing item; move_item on an existing
# item AND an existing destination; create_folder/organize_by_type don't act
# on an existing item at all, so nothing to ground). See
# verify_reference_grounding in eval/verifier.py.
_WRITE_REF_ARGS: dict[str, list[str]] = {
    "rename_item": ["item_id"],
    "star_item": ["item_id"],
    "move_item": ["item_id", "parent_id"],
}


def build_m3() -> list[dict[str, Any]]:
    """M3 = 5 real scenarios (see M3_SCENARIOS) x 20 topics = 100.

    Targets that must already exist (rename/star/move) are created for real via
    `seed_folders` and located by the plan's own query steps, not a fixed UUID.
    """
    cases = []
    n = 0
    for scenario in [*M3_SCENARIOS, CLASSIFY_SCENARIO]:
        for topic in M2_TOPICS:
            n += 1
            expect: dict[str, Any] = {
                "workflow": {
                    "requires_confirmation": True,
                    "steps_include": [*scenario["tools"], scenario["write"]],
                    "required_skills": list(
                        scenario.get("required_skills_override", scenario["tools"])
                    ),
                    "nonempty_outputs": _nonempty_outputs(scenario),
                    "write_skill": scenario["write"],
                    # A scenario can override which arguments must be grounded
                    # (create_folder only has a groundable parent_id when it
                    # creates *inside* an existing folder).
                    "write_ref_args": scenario.get(
                        "ref_args", _WRITE_REF_ARGS.get(scenario["write"], [])
                    ),
                }
            }
            state = _scenario_state(scenario, topic)
            if state is not None:
                state = {**state, "unchanged": CANARY_FOLDERS}
                expect["state"] = state
            cases.append(
                {
                    "id": f"gen-m3-{n:03d}",
                    "name": f"M3 {scenario['title']}：{topic}",
                    "rationale": scenario["reason"],
                    "prompt": _scenario_prompt(scenario, topic),
                    "mode": ["api", "browser"],
                    "tags": ["daily-ops", "generated", "m3", f"scenario:{scenario['key']}"],
                    "seed_folders": _scenario_seed(scenario, topic),
                    "seed_files": _scenario_seed_files(scenario, topic),
                    "expect": expect,
                    "scoring": _scoring(),
                    "mock_llm": {
                        "responses": [
                            {"reply": "計畫如下，請確認。", "steps": scenario["steps"](topic)}
                        ]
                    },
                }
            )
    return cases


def _m3_case_count() -> int:
    """M3 grew a 6th scenario (classify_by_name) on 2026-07-28, so it is
    6 x 20 = 120 rather than the historical 100. Documented here so the totals
    in reports don't silently drift from the "100 per level" story."""

    return (len(M3_SCENARIOS) + 1) * len(M2_TOPICS)


# M5 = same real-scenario spirit as M3, but the write step references an
# *earlier* step across intervening tool calls (not the immediately-preceding
# one) — a deeper reference chain than M3's single-hop confirm, matching M5's
# "multi-step + step-output references" definition. Every scenario needs a
# real seeded target (no create_folder/organize_by_type analogue — those don't
# have a reference chain to speak of).
M5_SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "rename_after_lookup",
        "title": "確認容量與近況後才改名",
        "write": "rename_item",
        "reason": (
            "先搜尋找到資料夾（search）、確認容量還夠不夠改名後續作業（storage_quota）、"
            "看有沒有更適合的候選（recent），最後改名——item_id 跨過中間兩步，"
            "直接引用最早的搜尋結果，考驗模型能否記住較早的步驟輸出。"
        ),
        "prompt": (
            "幫我搜尋一下「{t}」這個資料夾，順便看一下我的容量還夠不夠、最近有沒有"
            "開過更新的版本，確認都沒問題的話，把它改名成「{t}_已確認」。"
        ),
        "tools": ["search", "storage_quota", "recent"],
        "seed_extra": None,
        "steps": lambda t: [
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "storage_quota", "arguments": {}},
            {"skill": "recent", "arguments": {}},
            {
                "skill": "rename_item",
                "arguments": {
                    "item_id": {"from_step": 0, "path": "items.0.id"},
                    "new_name": f"{t}_已確認",
                },
            },
        ],
        "state": lambda t: {"item_present": [f"{t}_已確認"], "item_absent_after": [t]},
    },
    {
        "key": "star_after_browse",
        "title": "瀏覽清單與近況後才加星號",
        "write": "star_item",
        "reason": (
            "從最近開過的檔案回想（recent）、瀏覽根目錄清單找到它（list_items）、"
            "再搜尋確認關鍵字命中（search），最後加星號——item_id 引用的是"
            "list_items 那一步，而不是緊接在寫入之前的 search，考驗模型別誤引到"
            "最後一次查詢。"
        ),
        "prompt": (
            "我最近常常翻我的最近開啟清單找「{t}」，幫我先看一下最近開過的檔案、"
            "列出根目錄看看它在不在、再搜尋確認一下，找到後幫我加上星號。"
        ),
        "tools": ["recent", "list_items", "search"],
        "seed_extra": None,
        "steps": lambda t: [
            {"skill": "recent", "arguments": {}},
            {"skill": "list_items", "arguments": {}},
            {"skill": "search", "arguments": {"q": t}},
            {
                "skill": "star_item",
                "arguments": {"item_id": {"from_step": 1, "path": "items.0.id"}, "starred": True},
            },
        ],
        "state": lambda t: {"item_starred": [t]},
    },
    {
        "key": "archive_after_review",
        "title": "查完詳情與清單才搬進封存",
        "write": "move_item",
        "reason": (
            "先搜尋找到來源資料夾（search）、查看詳情確認（get_info）、瀏覽根目錄"
            "現況（list_items），再搜尋封存資料夾拿到真實 id、執行搬移——"
            "寫入步驟同時引用兩個更早的步驟（來源與目的地都不是緊接在前一步）。"
        ),
        "prompt": (
            "幫我搜尋一下「{t}」，查一下它的詳情，順便列出根目錄看看現在有哪些東西，"
            "確認後把它搬到我的「{t}封存」資料夾。"
        ),
        "tools": ["search", "get_info", "list_items"],
        "seed_extra": lambda t: [f"{t}封存"],
        "steps": lambda t: [
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "get_info", "arguments": {"item_id": {"from_step": 0, "path": "items.0.id"}}},
            {"skill": "list_items", "arguments": {}},
            {"skill": "search", "arguments": {"q": f"{t}封存"}},
            {
                "skill": "move_item",
                "arguments": {
                    "item_id": {"from_step": 0, "path": "items.0.id"},
                    "parent_id": {"from_step": 3, "path": "items.0.id"},
                },
            },
        ],
        "state": lambda t: {"item_parent": {t: f"{t}封存"}},
    },
    {
        "key": "rename_after_recent_first",
        "title": "從近況回想再搜尋確認後改名",
        "write": "rename_item",
        "reason": (
            "跟 rename_after_lookup 順序相反：先從最近開過的檔案回想（recent），"
            "再搜尋確認（search），再看容量（storage_quota），最後改名引用 search"
            "那一步（非最後一步、非第一步），考驗模型別固定引用某個位置。"
        ),
        "prompt": (
            "我記得最近有開過「{t}」相關的檔案，幫我從最近開過的檔案裡找一下、"
            "再搜尋確認、順便看一下容量夠不夠，確認後把它改名成「{t}_更新版」。"
        ),
        "tools": ["recent", "search", "storage_quota"],
        "seed_extra": None,
        "steps": lambda t: [
            {"skill": "recent", "arguments": {}},
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "storage_quota", "arguments": {}},
            {
                "skill": "rename_item",
                "arguments": {
                    "item_id": {"from_step": 1, "path": "items.0.id"},
                    "new_name": f"{t}_更新版",
                },
            },
        ],
        "state": lambda t: {"item_present": [f"{t}_更新版"], "item_absent_after": [t]},
    },
    {
        "key": "star_after_full_review",
        "title": "查詳情與容量後才加星號",
        "write": "star_item",
        "reason": (
            "搜尋找到候選（search）、查看詳情確認（get_info）、順便看一下容量"
            "（storage_quota），最後加星號引用 get_info 那一步的結果。"
        ),
        "prompt": (
            "幫我搜尋一下「{t}」，查看一下詳情確認是不是我要的那個，順便看一下容量"
            "用量，確認後幫我加上星號。"
        ),
        "tools": ["search", "get_info", "storage_quota"],
        "seed_extra": None,
        "steps": lambda t: [
            {"skill": "search", "arguments": {"q": t}},
            {"skill": "get_info", "arguments": {"item_id": {"from_step": 0, "path": "items.0.id"}}},
            {"skill": "storage_quota", "arguments": {}},
            {
                "skill": "star_item",
                "arguments": {"item_id": {"from_step": 1, "path": "id"}, "starred": True},
            },
        ],
        "state": lambda t: {"item_starred": [t]},
    },
]


def build_m5() -> list[dict[str, Any]]:
    """M5 = 5 real scenarios (see M5_SCENARIOS) x 20 topics = 100.

    Same real-seeding approach as M3, but the write step's item reference
    jumps over intervening query steps instead of always reading the
    immediately-preceding one — the "multi-step + step-output references"
    difficulty this tier is meant to test.
    """
    cases = []
    n = 0
    for scenario in M5_SCENARIOS:
        for topic in M2_TOPICS:
            n += 1
            seed = [topic]
            seed_extra = scenario.get("seed_extra")
            if seed_extra is not None:
                seed = seed + seed_extra(topic)
            seed = [*seed, *CANARY_FOLDERS]
            expect: dict[str, Any] = {
                "workflow": {
                    "requires_confirmation": True,
                    "steps_include": [*scenario["tools"], scenario["write"]],
                    "required_skills": list(scenario["tools"]),
                    "nonempty_outputs": _nonempty_outputs(scenario),
                    "write_skill": scenario["write"],
                    "write_ref_args": _WRITE_REF_ARGS.get(scenario["write"], []),
                }
            }
            state = _scenario_state(scenario, topic)
            if state is not None:
                expect["state"] = {**state, "unchanged": CANARY_FOLDERS}
            cases.append(
                {
                    "id": f"gen-m5-{n:03d}",
                    "name": f"M5 {scenario['title']}：{topic}",
                    "rationale": scenario["reason"],
                    "prompt": scenario["prompt"].format(t=topic),
                    "mode": ["api", "browser"],
                    "tags": ["workflow-reuse", "generated", "m5", f"scenario:{scenario['key']}"],
                    "seed_folders": seed,
                    "expect": expect,
                    "scoring": _scoring(),
                    "mock_llm": {
                        "responses": [
                            {"reply": "多步驟計畫，請確認。", "steps": scenario["steps"](topic)}
                        ]
                    },
                }
            )
    return cases


def _m4_skills() -> list[tuple[str, str, str]]:
    skills: list[tuple[str, str, str]] = []
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
        skills.append((f"{algo}_checksum", f"算 {algo.upper()} 雜湊", "hash"))
    for op, zh in [("encode", "編碼"), ("decode", "解碼")]:
        for enc in ["base64", "base32", "hex", "url", "ascii85"]:
            skills.append((f"{enc}_{op}", f"做 {enc} {zh}", "encode"))
    skills += [
        ("rot13_text", "做 ROT13 轉換", "encode"),
        ("html_escape", "做 HTML 跳脫", "encode"),
        ("html_unescape", "還原 HTML 跳脫", "encode"),
    ]
    for op, zh in [("extract", "解開"), ("compress", "壓成")]:
        for fmt in ["zip", "tar", "gzip", "bz2", "xz", "7z"]:
            # name must be a valid identifier — keep the digit-leading fmt as a suffix.
            skills.append((f"{op}_{fmt}", f"{zh} {fmt}", f"archive_{op}"))
    skills += [
        ("count_lines", "統計行數", "text"),
        ("count_words", "統計字數", "text"),
        ("count_chars", "統計字元數", "text"),
        ("uppercase_text", "轉成大寫", "text"),
        ("lowercase_text", "轉成小寫", "text"),
        ("titlecase_text", "轉成首字大寫", "text"),
        ("reverse_lines", "反轉行序", "text"),
        ("sort_lines", "排序每一行", "text"),
        ("dedupe_lines", "去除重複行", "text"),
        ("strip_blank_lines", "移除空白行", "text"),
        ("number_lines", "為每行加行號", "text"),
        ("wrap_lines", "把長行折成 80 字", "text"),
        ("head_lines", "取前 10 行", "text"),
        ("tail_lines", "取後 10 行", "text"),
        ("trim_whitespace", "去除前後空白", "text"),
        ("slugify_text", "把文字轉成 slug", "text"),
    ]
    skills += [
        ("csv_to_json", "把 CSV 轉成 JSON", "data"),
        ("json_to_csv", "把 JSON 轉成 CSV", "data"),
        ("csv_to_tsv", "把 CSV 轉成 TSV", "data"),
        ("tsv_to_csv", "把 TSV 轉成 CSV", "data"),
        ("json_prettify", "把 JSON 美化縮排", "data"),
        ("json_minify", "把 JSON 壓成單行", "data"),
        ("flatten_json", "把巢狀 JSON 攤平", "data"),
        ("json_keys", "列出 JSON 的所有鍵", "data"),
    ]
    skills += [
        ("image_thumbnail", "產生圖片縮圖", "image"),
        ("image_grayscale", "把圖片轉灰階", "image"),
        ("image_resize_half", "把圖片縮一半", "image"),
        ("image_rotate_90", "把圖片旋轉 90 度", "image"),
        ("image_flip_horizontal", "把圖片左右翻轉", "image"),
        ("image_flip_vertical", "把圖片上下翻轉", "image"),
        ("image_to_png", "把圖片轉成 PNG", "image"),
        ("image_to_jpeg", "把圖片轉成 JPEG", "image"),
        ("image_to_webp", "把圖片轉成 WebP", "image"),
        ("image_info", "讀出圖片尺寸資訊", "image"),
        ("image_crop_center", "置中裁切圖片", "image"),
        ("image_invert", "反相圖片顏色", "image"),
        ("image_blur", "把圖片模糊化", "image"),
        ("image_sepia", "把圖片轉復古色", "image"),
    ]
    skills += [
        ("pdf_extract_text", "抽取 PDF 文字", "pdf"),
        ("pdf_page_count", "數 PDF 頁數", "pdf"),
        ("pdf_metadata", "讀 PDF 中繼資料", "pdf"),
        ("pdf_rotate_pages", "旋轉 PDF 每一頁", "pdf"),
        ("pdf_split_pages", "把 PDF 拆成單頁", "pdf"),
        ("pdf_first_page", "抽出 PDF 第一頁", "pdf"),
    ]
    skills += [
        ("file_info", "讀出檔案大小與類型", "file"),
        ("to_lf_endings", "把換行統一成 LF", "file"),
        ("tabs_to_spaces", "把 Tab 換成空白", "file"),
        ("remove_bom", "移除檔案 BOM", "file"),
        ("count_bytes", "統計位元組數", "file"),
        ("hexdump_file", "產生檔案 hex dump", "file"),
        ("base32_hex", "把檔案轉 base32hex", "file"),
        ("gzip_level9", "用最高壓縮率壓 gzip", "file"),
    ]
    skills += [
        ("collapse_spaces", "合併連續空白", "text"),
        ("remove_punctuation", "移除標點符號", "text"),
        ("char_frequency", "統計字元頻率", "text"),
        ("longest_line", "找出最長的一行", "text"),
        ("unique_words", "列出不重複的詞", "text"),
        ("snake_to_camel", "把底線命名轉駝峰", "text"),
        ("json_sort_keys", "把 JSON 的鍵排序", "text"),
        ("csv_headers", "列出 CSV 欄位名", "text"),
        ("csv_row_count", "數 CSV 列數", "text"),
        ("json_to_jsonl", "把 JSON 陣列轉成 JSONL", "text"),
        ("base85_encode", "做 base85 編碼", "text"),
        ("quoted_printable_encode", "做 quoted-printable 編碼", "text"),
        ("image_posterize", "把圖片做色階化", "text"),
        ("image_autocontrast", "自動調整圖片對比", "text"),
        ("adler32_checksum", "算 Adler32 雜湊", "text"),
        ("strip_ansi", "移除 ANSI 控制碼", "text"),
        ("count_paragraphs", "統計段落數", "text"),
    ]
    return skills


# 2026-07-28 (alfred): M4's prompts averaged 14.5 characters — "做一個算 MD5
# 雜湊的功能" — and 32 of the 100 shared one句型. M3/M5 were rewritten into
# narrative scenarios on 07-27; M4 was the last tier still handing the model a
# tool spec instead of a situation. Each category gets several situations so
# neighbouring cases don't read identically; the concrete operation stays in the
# sentence (the task must remain unambiguous — see τ-bench's "one determinate
# outcome" principle in §10.13), but it now arrives wrapped in a reason.
M4_CONTEXTS: dict[str, list[str]] = {
    "hash": [
        "我從網路上抓了一個安裝檔，想確認下載過程有沒有壞掉，之後好跟官網公布的值"
        "比對——幫我做一個可以{desc}的功能。",
        "我要把檔案寄給同事，希望對方收到後能驗證內容沒被改過，幫我做一個能{desc}"
        "的功能，附在信裡一起給他。",
    ],
    "encode": [
        "我要把一份檔案貼進只吃純文字的系統裡，直接丟二進位會壞掉，幫我做一個能{desc}的功能。",
        "同事傳來的資料是編過碼的，我想在自己的雲端硬碟上直接處理，幫我做一個能{desc}的功能。",
    ],
    "archive_compress": [
        "這批檔案要寄給廠商，對方的系統只收單一壓縮檔，幫我做一個能{desc}的功能。",
        "備份資料佔了太多雲端空間，我想先打包再存，幫我做一個能{desc}的功能。",
    ],
    "archive_extract": [
        "我從舊硬碟翻出一包封存檔，想拿回裡面的東西，幫我做一個能{desc}的功能。",
        "廠商寄來的資料是壓縮包，我想直接在雲端硬碟上打開，幫我做一個能{desc}的功能。",
    ],
    "text": [
        "我手上有一份從別的系統匯出的文字檔，格式亂七八糟不好讀，幫我做一個能{desc}"
        "的功能，之後整理這類檔案就能直接用。",
        "我要把一批文字檔交給下游流程，對方要求格式統一，幫我做一個能{desc}的功能。",
        "整理讀書筆記時每次都要手動處理很花時間，幫我做一個能{desc}的功能。",
    ],
    "data": [
        "會計那邊給的報表格式我這邊的工具讀不了，幫我做一個能{desc}的功能。",
        "我想把匯出的資料丟進程式裡分析，但格式不對，幫我做一個能{desc}的功能。",
    ],
    "image": [
        "這些照片要放到網頁上，原檔太大載入很慢，幫我做一個能{desc}的功能。",
        "我要把手機拍的圖整批處理成一致的樣式再交出去，幫我做一個能{desc}的功能。",
        "投影片裡的圖片規格不一，看起來很雜亂，幫我做一個能{desc}的功能。",
    ],
    "pdf": [
        "客戶寄來的合約是 PDF，我想拿裡面的資訊來做後續處理，幫我做一個能{desc}的功能。",
        "我掃描的文件存成 PDF 之後不好處理，幫我做一個能{desc}的功能。",
    ],
    "file": [
        "我在整理雲端硬碟，想先摸清楚每個檔案的狀況再決定怎麼分類，幫我做一個能{desc}的功能。",
        "跨系統搬檔案常常出現看不見的格式問題，幫我做一個能{desc}的功能。",
    ],
}


def _m4_prompt(index: int, desc: str, category: str) -> str:
    contexts = M4_CONTEXTS[category]
    return contexts[index % len(contexts)].format(desc=desc)


def build_m4() -> list[dict[str, Any]]:
    skills = _m4_skills()
    assert len(skills) >= PER_LEVEL, f"need >= {PER_LEVEL} M4 skills, have {len(skills)}"
    cases = []
    for n, (name, desc, category) in enumerate(skills[:PER_LEVEL], start=1):
        cases.append(
            {
                "id": f"gen-m4-{n:03d}",
                "name": f"M4 self-authoring #{n} ({name})",
                "prompt": _m4_prompt(n, desc, category),
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
    # M3 is the exception: it gained a 6th scenario (classify_by_name) on
    # 2026-07-28, so it is 120 while the other tiers stay at 100 (=> 420 total).
    expected = {"build_m3": _m3_case_count()}
    for builder in (build_m2, build_m3, build_m4, build_m5):
        built = builder()
        want = expected.get(builder.__name__, PER_LEVEL)
        assert len(built) == want, f"{builder.__name__} produced {len(built)} (want {want})"
        for case in built:
            (GENERATED_DIR / f"{case['id']}.yaml").write_text(
                yaml.safe_dump(case, allow_unicode=True, sort_keys=False, width=100)
            )
            total += 1
    return total


if __name__ == "__main__":
    n = generate()
    print(f"generated {n} cases under {GENERATED_DIR}")
