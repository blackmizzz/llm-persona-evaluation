#!/usr/bin/env python3
"""
Convert the research team's case Excel file (columns: case_no, case_scenario,
case_answer, model, persona, recommendation) into data/cases.json for the
rating webapp.

Usage:
    python convert_cases.py "Case example.xlsx" ../data/cases.json

Excel layout expected (one row per model x persona answer):
    case_no | case_scenario | case_answer | model | persona | recommendation
       1    |   "You are.." |  "Ketotifen" | gemini | constrain | "TRIAGE_LEVEL: ..."
       (blank)          ...                | gemini | secure    | "..."
       ... 18 rows total for case 1 ...
       2    |   "You are.." |  "Reassurance"| gemini | constrain | "..."
       ... 18 rows total for case 2 ...

case_no / case_scenario / case_answer are only filled on the first row of each
case block (merged visually in Excel) and blank/None on the rest -> this
script forward-fills them.

model is normalized (gemini/claude/gpt, any case) -> Gemini/Claude/GPT for
display. persona must be one of the fixed 6 labels in EXPECTED_PERSONAS below.
"""
import sys
import json
from pathlib import Path

import openpyxl

MODEL_DISPLAY = {
    "gpt": "GPT",
    "claude": "Claude",
    "gemini": "Gemini",
}

# Fixed 6 persona labels every case must use exactly one of, x3 models = 18 rows/case.
EXPECTED_PERSONAS = {
    "constrain",
    "secure",
    "lit_low",
    "lit_high",
    "soc_low",
    "soc_high",
}
EXPECTED_MODELS = {"GPT", "Claude", "Gemini"}


def normalize_model(raw):
    if raw is None:
        return raw
    key = str(raw).strip().lower()
    return MODEL_DISPLAY.get(key, str(raw).strip())


def convert(xlsx_path, sheet_name=None):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows = list(ws.iter_rows(min_row=2, values_only=True))  # skip header row

    cases = {}
    case_order = []
    current_case_no = None
    current_scenario = None
    current_answer = None

    for row in rows:
        if row is None or all(v is None for v in row):
            continue
        case_no, scenario, answer_text, model, persona, recommendation = (
            list(row) + [None] * (6 - len(row))
        )[:6]

        if case_no is not None:
            current_case_no = case_no
            current_scenario = scenario
            current_answer = answer_text

        if current_case_no is None:
            continue  # stray row before any case header, skip
        if model is None and persona is None and recommendation is None:
            continue  # blank filler row

        case_id = f"case_{int(current_case_no):03d}"
        if case_id not in cases:
            cases[case_id] = {
                "id": case_id,
                "source": "MedQA/KorMedQA",
                "description": (current_scenario or "").strip(),
                "ground_truth": (current_answer or "").strip(),
                "answers": [],
            }
            case_order.append(case_id)

        cases[case_id]["answers"].append(
            {
                "model": normalize_model(model),
                "persona": str(persona).strip() if persona is not None else None,
                "text": (recommendation or "").strip(),
            }
        )

    return [cases[cid] for cid in case_order]


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_cases.py <input.xlsx> [output.json] [sheet_name]")
        sys.exit(1)

    xlsx_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/cases.json")
    sheet_name = sys.argv[3] if len(sys.argv) > 3 else None

    case_list = convert(xlsx_path, sheet_name)

    # sanity checks
    expected_count = len(EXPECTED_MODELS) * len(EXPECTED_PERSONAS)
    problems = []
    for c in case_list:
        n = len(c["answers"])
        if n != expected_count:
            problems.append(f"{c['id']}: {n} answers (expected {expected_count})")
        if not c["description"]:
            problems.append(f"{c['id']}: empty description")
        if not c["ground_truth"]:
            problems.append(f"{c['id']}: empty ground_truth")
        empties = [a for a in c["answers"] if not a["text"]]
        if empties:
            problems.append(f"{c['id']}: {len(empties)} answers with empty text")
        dupes = {}
        for a in c["answers"]:
            key = (a["model"], a["persona"])
            dupes[key] = dupes.get(key, 0) + 1
        for key, count in dupes.items():
            if count > 1:
                problems.append(f"{c['id']}: duplicate model/persona {key} x{count}")

        seen_personas = {a["persona"] for a in c["answers"]}
        unexpected_personas = seen_personas - EXPECTED_PERSONAS
        missing_personas = EXPECTED_PERSONAS - seen_personas
        if unexpected_personas:
            problems.append(f"{c['id']}: unexpected persona label(s) {sorted(unexpected_personas)}")
        if missing_personas:
            problems.append(f"{c['id']}: missing persona label(s) {sorted(missing_personas)}")

        seen_models = {a["model"] for a in c["answers"]}
        unexpected_models = seen_models - EXPECTED_MODELS
        if unexpected_models:
            problems.append(f"{c['id']}: unexpected model label(s) {sorted(unexpected_models)}")

    out = {
        "_comment": f"Generated from {xlsx_path.name} by convert_cases.py",
        "models": sorted(EXPECTED_MODELS),
        "personas": sorted(EXPECTED_PERSONAS),
        "cases": case_list,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {len(case_list)} cases -> {out_path}")
    if problems:
        print("\nWARNINGS:")
        for p in problems:
            print(" -", p)
    else:
        print("No warnings.")


if __name__ == "__main__":
    main()
