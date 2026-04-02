import requests
import time
import json
import os
import csv
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

BASE_URL = "http://localhost:8000"
REPORT_INPUT_DIR = "报告文本记忆（后五种）"
OUTPUT_CSV = "离线评估结果_文本上下文加原始.csv"
REPORT_DIR = "离线评估报告_文本上下文加原始"

QUESTION_STRATEGIES = [ "CoT", "Self-Consistency", "ToT"]

def ensure_dirs():
    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)

def wait_for_status(endpoint: str, key: str, expected_value: Any, timeout_sec: int = 600, check_interval: int = 5) -> bool:
    if timeout_sec is None:
        while True:
            try:
                resp = requests.get(f"{BASE_URL}{endpoint}")
                if resp.status_code == 200:
                    data = resp.json()
                    status_data = data.get("data", data)
                    if key == "status":
                        status_data = data
                    current_val = status_data.get(key)
                    if key == "status" and current_val in ("completed", "failed"):
                        return True
                    if current_val == expected_value:
                        return True
            except Exception:
                pass
            time.sleep(check_interval)
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}")
            if resp.status_code == 200:
                data = resp.json()
                status_data = data.get("data", data)
                if key == "status":
                    status_data = data
                current_val = status_data.get(key)
                if key == "status" and current_val in ("completed", "failed"):
                    return True
                if current_val == expected_value:
                    return True
        except Exception:
            pass
        time.sleep(check_interval)
    return False

def resolve_output_csv_path(output_csv: str, fieldnames: List[str]) -> str:
    if not os.path.isfile(output_csv):
        return output_csv
    try:
        with open(output_csv, "r", encoding="utf-8-sig", newline="") as f:
            header_line = f.readline().strip()
        if not header_line:
            return output_csv
        existing_fields = [h.strip() for h in header_line.split(",")]
        if existing_fields == fieldnames:
            return output_csv
    except Exception:
        return output_csv
    base, ext = os.path.splitext(output_csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}{ext or '.csv'}"

def fetch_questions_for_region(region: str) -> Optional[List[Dict[str, Any]]]:
    try:
        resp = requests.post(f"{BASE_URL}/evaluation/questions", json={"region_name": region})
        if resp.status_code != 200:
            return None
        payload = resp.json() if resp.content else {}
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return None
        questions = data.get("questions")
        if isinstance(questions, list) and questions:
            return questions
        return None
    except Exception:
        return None

def has_raw_marker(ctx: str) -> bool:
    if not isinstance(ctx, str):
        return False
    if re.search(r"(?m)^\s*===\s*原始\s*记忆", ctx):
        return True
    if re.search(r"(?m)^\s*===\s*raw\s*memory", ctx, flags=re.IGNORECASE):
        return True
    return False

def infer_meta_from_filename(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    base = os.path.basename(filename)
    name, _ = os.path.splitext(base)
    parts = [p for p in name.split("_") if p.strip()]
    region = parts[0].strip() if len(parts) >= 1 else None
    model = parts[1].strip() if len(parts) >= 2 else None
    memory_mode = parts[2].strip().lower() if len(parts) >= 3 else None
    if memory_mode and memory_mode.endswith("report"):
        memory_mode = memory_mode[:-6].strip().lower()
    if memory_mode and memory_mode not in ("context", "graph", "map"):
        memory_mode = None
    return region or None, model or None, memory_mode or None

def load_reports(input_dir: str) -> List[Dict[str, Any]]:
    items = []
    try:
        for name in os.listdir(input_dir):
            if not name.lower().endswith((".txt", ".json")):
                continue
            fp = os.path.join(input_dir, name)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    continue
                inferred_region, inferred_model, inferred_mm = infer_meta_from_filename(name)
                region = data.get("region") or inferred_region
                model = data.get("model") or inferred_model
                memory_mode = data.get("memory_mode") or data.get("mode") or inferred_mm
                ctx = data.get("context_text")
                if not ctx and isinstance(data.get("exploration_report"), dict):
                    ctx = data["exploration_report"].get("context_text") or data["exploration_report"].get("context")
                if not ctx and isinstance(data.get("exploration_data"), dict):
                    ctx = data["exploration_data"].get("context_text")
                if isinstance(memory_mode, str):
                    mm = memory_mode.strip().lower()
                else:
                    mm = None
                if mm not in ("context", "graph", "map"):
                    continue
                if not (isinstance(ctx, str) and ctx.strip()):
                    continue
                items.append({
                    "region": region,
                    "model": model or "qwen",
                    "memory_mode": mm,
                    "context_text": ctx.strip(),
                    "source_file": fp
                })
            except Exception:
                continue
    except Exception:
        pass
    return items

def reload_report(source_file: str) -> Optional[Dict[str, Any]]:
    try:
        name = os.path.basename(source_file)
        with open(source_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        inferred_region, inferred_model, inferred_mm = infer_meta_from_filename(name)
        region = data.get("region") or inferred_region
        model = data.get("model") or inferred_model
        memory_mode = data.get("memory_mode") or data.get("mode") or inferred_mm
        ctx = data.get("context_text")
        if not ctx and isinstance(data.get("exploration_report"), dict):
            ctx = data["exploration_report"].get("context_text") or data["exploration_report"].get("context")
        if not ctx and isinstance(data.get("exploration_data"), dict):
            ctx = data["exploration_data"].get("context_text")
        if isinstance(memory_mode, str):
            mm = memory_mode.strip().lower()
        else:
            mm = None
        if mm not in ("context", "graph", "map"):
            return None
        if not (isinstance(ctx, str) and ctx.strip()):
            return None
        return {
            "region": region,
            "model": model or "qwen",
            "memory_mode": mm,
            "context_text": ctx.strip(),
            "source_file": source_file
        }
    except Exception:
        return None

def build_combined_context(ctx_text: str, region: str) -> Tuple[str, bool]:
    if has_raw_marker(ctx_text):
        return ctx_text, False
    raw_text = ""
    try:
        resp = requests.post(f"{BASE_URL}/exploration/switch_region", json={"region_name": region})
    except Exception:
        pass
    try:
        raw_resp = requests.get(f"{BASE_URL}/memory/raw")
        if raw_resp.status_code == 200:
            payload = raw_resp.json()
            if isinstance(payload, dict) and payload.get("success"):
                raw_text = payload.get("data") or ""
    except Exception:
        raw_text = ""
    if isinstance(raw_text, str) and raw_text.strip():
        combined = f"{ctx_text}\n\n=== 原始记忆（Raw） ===\n{raw_text}".strip()
        return combined, True
    return ctx_text, False

def run_offline_evaluation():
    ensure_dirs()
    fieldnames = [
        'Region',
        'Model',
        'Memory Mode',
        'Strategy',
        'Total Score',
        'Accuracy',
        'Completed At',
        'Type_定位与定向',
        'Type_空间距离估算',
        'Type_邻近关系判断',
        'Type_POI密度识别',
        'Type_路径规划',
    ]
    output_csv = resolve_output_csv_path(OUTPUT_CSV, fieldnames)
    file_exists = os.path.isfile(output_csv)
    with open(output_csv, 'a', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

    items = load_reports(REPORT_INPUT_DIR)
    if not items:
        print("No valid reports found.")
        return

    for it in items:
        for strategy in QUESTION_STRATEGIES:
            refreshed = reload_report(it["source_file"])
            if not refreshed:
                print(f"Skip: reload failed {it.get('source_file')}")
                continue
            region = refreshed["region"]
            if not (isinstance(region, str) and region.strip()):
                print(f"Skip: missing region in {it.get('source_file')}")
                continue
            region = region.strip()
            model = refreshed["model"]
            memory_mode = refreshed["memory_mode"]
            ctx_text = refreshed["context_text"]
            print(f"\n=== Offline Evaluate: {region} | {model} | {memory_mode} | {strategy} ===")
            combined_ctx, appended = build_combined_context(ctx_text, region)
            try:
                eq_questions = fetch_questions_for_region(region)
                if not eq_questions:
                    raise RuntimeError("empty questions")
            except Exception:
                print("Generate questions failed.")
                continue
            try:
                requests.post(f"{BASE_URL}/evaluation/reset")
            except Exception:
                pass
            eval_req = {
                "questions": eq_questions,
                "exploration_data": {
                    "ai_location": [0, 0],
                    "exploration_path": [],
                    "visited_pois": [],
                    "context_mode": memory_mode,
                    "context_text": combined_ctx,
                },
                "model_provider": model,
                "strategies": [strategy],
            }
            try:
                start_resp = requests.post(f"{BASE_URL}/evaluation/start", json=eval_req)
                if start_resp.status_code != 200:
                    print(f"Evaluation start failed: {start_resp.text}")
                    continue
                print("Evaluation started...")
            except Exception as e:
                print(f"Evaluation start exception: {e}")
                continue
            finished_eval = wait_for_status("/evaluation/status", "status", "completed", timeout_sec=None, check_interval=5)
            if not finished_eval:
                print("Evaluation timed out or failed.")
                continue
            try:
                result_resp = requests.get(f"{BASE_URL}/evaluation/result")
                if result_resp.status_code != 200:
                    print(f"Error fetching results: {result_resp.text}")
                    continue
                result_data = result_resp.json().get("data", {}) or {}
                strat_result = result_data.get(strategy, {}) or {}
                type_scores = strat_result.get("type_scores", {}) or {}
                row = {
                    'Region': region,
                    'Model': model,
                    'Memory Mode': memory_mode,
                    'Strategy': strategy,
                    'Total Score': strat_result.get("total_score"),
                    'Accuracy': f"{strat_result.get('accuracy', 0):.2f}%",
                    'Completed At': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Type_定位与定向': f"{type_scores.get('定位与定向', {}).get('percentage', 0):.2f}%",
                    'Type_空间距离估算': f"{type_scores.get('空间距离估算', {}).get('percentage', 0):.2f}%",
                    'Type_邻近关系判断': f"{type_scores.get('邻近关系判断', {}).get('percentage', 0):.2f}%",
                    'Type_POI密度识别': f"{type_scores.get('POI密度识别', {}).get('percentage', 0):.2f}%",
                    'Type_路径规划': f"{type_scores.get('路径规划', {}).get('percentage', 0):.2f}%",
                }
                with open(output_csv, 'a', newline='', encoding='utf-8-sig') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writerow(row)
                base_name = f"{region}_{model}_{memory_mode}_{strategy}_离线评估.txt"
                safe_name = "".join([c if c not in '<>:\"/\\|?*' else "_" for c in base_name]).strip().rstrip(".")
                out_path = os.path.join(REPORT_DIR, safe_name)
                if os.path.exists(out_path):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    name, ext = os.path.splitext(safe_name)
                    out_path = os.path.join(REPORT_DIR, f"{name}_{ts}{ext or '.txt'}")
                out_report = {
                    "region": region,
                    "model": model,
                    "memory_mode": memory_mode,
                    "strategy": strategy,
                    "evaluation_result": strat_result,
                    "context_text": combined_ctx,
                    "source_file": refreshed["source_file"],
                    "combined_with_raw": appended,
                }
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(out_report, f, ensure_ascii=False, indent=2)
                print(f"Saved offline evaluation: {out_path}")
            except Exception as e:
                print(f"Error saving results: {e}")

if __name__ == "__main__":
    run_offline_evaluation()
