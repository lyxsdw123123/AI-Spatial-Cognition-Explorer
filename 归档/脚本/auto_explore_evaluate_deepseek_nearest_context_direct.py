import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from urllib.parse import urlparse


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


REGIONS_15 = [
    "上海外滩",
    "伦敦大本钟",
    "北京天安门",
    "多伦多CN塔",
    "巴黎埃菲尔铁塔",
    "广州塔",    
    "旧金山联合广场",
    "柏林勃兰登堡门",
    "武汉黄鹤楼",
    "洛杉矶好莱坞",
    "纽约时代广场",
    "维也纳美泉宫",
    "罗马斗兽场",
    "芝加哥千禧公园",
    "长沙五一广场"  
]

MODELS_5 = [
    "deepseek",
    "gemini",
    "openai",
    "claude",
    "qwen",
]

DEEPSEEK_DONE_REGIONS = [
    "上海外滩",
    "伦敦大本钟",
    "北京天安门",
    "多伦多CN塔",
    "巴黎埃菲尔铁塔",
    "广州塔",
]


def _safe_mkdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _request_json(
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    resp = requests.request(method, url, json=json_body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _normalize_model_name(name: str) -> str:
    s = (str(name) or "").strip().lower()
    if s in ("chatgpt", "gpt", "gpt4", "gpt-4", "gpt5", "gpt-5", "openai"):
        return "openai"
    return s


def _parse_csv_list(v: str) -> List[str]:
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _parse_host_port(base_url: str) -> Tuple[str, int]:
    u = urlparse(base_url)
    host = u.hostname or "127.0.0.1"
    port = int(u.port or 8000)
    return host, port


def _kill_listeners_on_port(port: int) -> None:
    cmd = (
        "$pids = (Get-NetTCPConnection -LocalPort "
        + str(int(port))
        + " -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique);"
        + " if($pids){ foreach($pid in $pids){ try{ Stop-Process -Id $pid -Force -ErrorAction Stop } catch{} } }"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    except Exception:
        pass


class BackendProcess:
    def __init__(self, *, host: str, port: int, show_logs: bool) -> None:
        self.host = host
        self.port = int(port)
        self.show_logs = bool(show_logs)
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return

        _kill_listeners_on_port(self.port)
        stdout = None if self.show_logs else subprocess.DEVNULL
        stderr = None if self.show_logs else subprocess.DEVNULL
        try:
            self.proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app:app",
                    "--host",
                    str(self.host),
                    "--port",
                    str(self.port),
                    "--log-level",
                    "info",
                ],
                cwd=PROJECT_ROOT,
                stdout=stdout,
                stderr=stderr,
            )
        except Exception:
            self.proc = None

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            if self.proc.poll() is None:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
                except Exception:
                    pass
        finally:
            try:
                if self.proc and self.proc.poll() is None:
                    subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], check=False, capture_output=True, text=True)
            except Exception:
                pass
            self.proc = None

    def restart(self) -> None:
        self.stop()
        self.start()


def _ping_server(base_url: str) -> bool:
    try:
        resp = requests.get(f"{base_url}/config", timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def _wait_for_condition(
    check_fn,
    *,
    timeout_sec: int,
    interval_sec: int,
) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            if check_fn():
                return True
        except Exception:
            pass
        time.sleep(interval_sec)
    return False


def _get_local_pois(base_url: str) -> List[Dict[str, Any]]:
    try:
        payload = _request_json("GET", f"{base_url}/exploration/local_pois", timeout=60)
        if payload.get("success"):
            data = payload.get("data")
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _calculate_bounds_and_start(pois: List[Dict[str, Any]]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    if not pois:
        return [], {"latitude": 39.9087, "longitude": 116.3975}

    lats: List[float] = []
    lngs: List[float] = []
    for p in pois:
        loc = p.get("location") if isinstance(p, dict) else None
        if not isinstance(loc, dict):
            continue
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        if lat is None or lng is None:
            continue
        try:
            lats.append(float(lat))
            lngs.append(float(lng))
        except Exception:
            continue

    if not lats or not lngs:
        return [], {"latitude": 39.9087, "longitude": 116.3975}

    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    margin = 0.002
    boundary = [
        {"latitude": min_lat - margin, "longitude": min_lng - margin},
        {"latitude": max_lat + margin, "longitude": min_lng - margin},
        {"latitude": max_lat + margin, "longitude": max_lng + margin},
        {"latitude": min_lat - margin, "longitude": max_lng + margin},
    ]

    start_location = {
        "latitude": (min_lat + max_lat) / 2.0,
        "longitude": (min_lng + max_lng) / 2.0,
    }

    return boundary, start_location


def _switch_region(base_url: str, region: str) -> None:
    payload = _request_json("POST", f"{base_url}/exploration/switch_region", json_body={"region_name": region}, timeout=60)
    if not payload.get("success"):
        raise RuntimeError(f"切换区域失败: {payload}")


def _init_exploration(
    base_url: str,
    *,
    start_location: Dict[str, float],
    boundary: List[Dict[str, float]],
    exploration_mode: str,
    memory_mode: str,
    max_rounds: int,
    model_provider: str,
    use_local_data: bool,
) -> None:
    init_payload: Dict[str, Any] = {
        "start_location": start_location,
        "boundary": {"points": boundary},
        "use_local_data": use_local_data,
        "exploration_mode": exploration_mode,
        "memory_mode": memory_mode,
        "max_rounds": max_rounds,
        "model_provider": model_provider,
    }
    _request_json("POST", f"{base_url}/exploration/init", json_body=init_payload, timeout=120)


def _start_exploration(base_url: str, memory_mode: str) -> None:
    _request_json("POST", f"{base_url}/exploration/start", json_body={"memory_mode": memory_mode}, timeout=60)


def _is_exploring(base_url: str) -> bool:
    payload = _request_json("GET", f"{base_url}/exploration/status", timeout=30)
    if not payload.get("success"):
        return False
    data = payload.get("data") or {}
    return bool(data.get("is_exploring"))


def _stop_exploration(base_url: str) -> Dict[str, Any]:
    return _request_json("POST", f"{base_url}/exploration/stop", timeout=120)


def _get_latest_context(base_url: str) -> Tuple[str, str]:
    payload = _request_json("GET", f"{base_url}/exploration/context", timeout=30)
    if not payload.get("success"):
        return "", ""
    data = payload.get("data") or {}
    ctx = data.get("context_text") or ""
    mode = data.get("context_mode") or ""
    return str(ctx), str(mode)


def _collect_context_texts(obj: Any, acc: List[str]) -> None:
    if isinstance(obj, dict):
        v = obj.get("context_text")
        if isinstance(v, str) and v.strip():
            acc.append(v)
        for vv in obj.values():
            _collect_context_texts(vv, acc)
        return
    if isinstance(obj, list):
        for it in obj:
            _collect_context_texts(it, acc)


def _load_context_text_from_report(
    input_report_dir: str,
    *,
    region: str,
    model_provider: str,
    memory_mode: str,
) -> str:
    raw_dir = str(input_report_dir)
    report_dir = raw_dir if os.path.isabs(raw_dir) else os.path.abspath(os.path.join(PROJECT_ROOT, raw_dir))
    if not os.path.isdir(report_dir):
        raise FileNotFoundError(f"输入文件夹不存在: {report_dir}")

    model = (str(model_provider) or "").strip().lower()
    mem = (str(memory_mode) or "").strip().lower()

    candidates = [
        os.path.join(report_dir, f"评估报告_{region}_{model}_{mem}_report.txt.json"),
        os.path.join(report_dir, f"评估报告_{region}_{model}_{mem}_report.txt"),
        os.path.join(report_dir, f"评估报告_{region}_{model}_{mem}_report.json"),
    ]

    chosen = ""
    for p in candidates:
        if os.path.exists(p):
            chosen = p
            break

    if not chosen:
        matched: List[str] = []
        for fn in os.listdir(report_dir):
            if not fn.startswith(f"评估报告_{region}_"):
                continue
            low = fn.lower()
            if model and model not in low:
                continue
            if mem and mem not in low:
                continue
            if not (low.endswith(".txt") or low.endswith(".json") or low.endswith(".txt.json")):
                continue
            matched.append(os.path.join(report_dir, fn))
        matched = sorted(set(matched))
        if matched:
            chosen = matched[0]

    if not chosen:
        raise FileNotFoundError(f"未找到匹配的报告文件: region={region} model={model} memory={mem} dir={report_dir}")

    with open(chosen, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except Exception:
        raise RuntimeError(f"报告不是有效JSON，无法读取context_text: {chosen}")

    ctxs: List[str] = []
    _collect_context_texts(data, ctxs)
    for c in ctxs:
        if isinstance(c, str) and c.strip():
            return c

    if isinstance(data, dict):
        v = data.get("context_text")
        if isinstance(v, str) and v.strip():
            return v

    raise RuntimeError(f"报告中未找到有效context_text: {chosen}")


def _get_questions_for_region(base_url: str, region: str) -> List[Dict[str, Any]]:
    payload = _request_json(
        "POST",
        f"{base_url}/evaluation/questions",
        json_body={"region_name": region},
        timeout=120,
    )
    if not payload.get("success"):
        raise RuntimeError(f"生成题目失败: {payload}")
    data = payload.get("data") or {}
    questions = data.get("questions") or []
    if not isinstance(questions, list) or not questions:
        raise RuntimeError(f"题目为空: {region}")
    return questions


def _extract_reselect_start_count(context_text: str) -> int:
    try:
        if not isinstance(context_text, str) or not context_text.strip():
            return 0
        m = re.search(r"(?:重新|重选)起点次数\s*[:：]\s*(\d+)", context_text)
        if not m:
            return 0
        return int(m.group(1))
    except Exception:
        return 0

def _get_exploration_status(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/exploration/status", timeout=30)
    if not payload.get("success"):
        return {}
    data = payload.get("data") or {}
    return data if isinstance(data, dict) else {}

def _get_exploration_raw_history_tail(base_url: str, tail_lines: int = 80) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/exploration/raw_history?tail_lines={int(tail_lines)}", timeout=30)
    if not payload.get("success"):
        return {}
    data = payload.get("data") or {}
    return data if isinstance(data, dict) else {}


def _start_evaluation(
    base_url: str,
    *,
    questions: List[Dict[str, Any]],
    model_provider: str,
    strategy: str,
    context_text: str,
    context_mode: str,
) -> None:
    eval_req = {
        "questions": questions,
        "exploration_data": {
            "ai_location": [0.0, 0.0],
            "exploration_path": [],
            "visited_pois": [],
            "context_text": context_text,
            "context_mode": context_mode,
        },
        "model_provider": model_provider,
        "strategies": [strategy],
    }
    payload = _request_json("POST", f"{base_url}/evaluation/start", json_body=eval_req, timeout=120)
    if not payload.get("success"):
        raise RuntimeError(f"启动评估失败: {payload}")


def _get_evaluation_status(base_url: str) -> str:
    payload = _request_json("GET", f"{base_url}/evaluation/status", timeout=30)
    if not payload.get("success"):
        return "unknown"
    return str(payload.get("status") or "unknown")

def _get_evaluation_status_payload(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/status", timeout=30)
    return payload if isinstance(payload, dict) else {}


def _get_evaluation_result(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/result", timeout=60)
    if not payload.get("success"):
        raise RuntimeError(f"获取评估结果失败: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"评估结果格式异常: {type(data)}")
    return data


def _reset_evaluation(base_url: str) -> None:
    try:
        _request_json("POST", f"{base_url}/evaluation/reset", json_body={}, timeout=30)
    except Exception:
        pass


def _write_csv_header(csv_path: str, fieldnames: List[str]) -> None:
    _safe_mkdir(os.path.dirname(csv_path))
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as rf:
                reader = csv.reader(rf)
                existing = next(reader, None)
            if existing and [h.strip() for h in existing] == fieldnames:
                return
            rows: List[Dict[str, Any]] = []
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as rf:
                dr = csv.DictReader(rf)
                for r in dr:
                    if isinstance(r, dict):
                        rows.append(r)
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as wf:
                dw = csv.DictWriter(wf, fieldnames=fieldnames)
                dw.writeheader()
                for r in rows:
                    out = {k: "" for k in fieldnames}
                    for k, v in r.items():
                        if k in out:
                            out[k] = v
                    dw.writerow(out)
            return
        except Exception:
            pass

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def _append_csv_row(csv_path: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(row)


def _expected_report_path(out_dir: str, region: str, model_provider: str) -> str:
    report_root = os.path.join(out_dir, "最近报告", "探索策略+最近评估结果报告")
    report_filename = f"评估报告_{region}_{model_provider}_report.txt.json"
    return os.path.join(report_root, report_filename)


def _wait_evaluation_done(base_url: str, *, timeout_sec: int, stall_sec: int) -> None:
    eval_start_ts = time.time()
    eval_done = False
    last_eval_fp: Optional[str] = None

    last_cq: Optional[int] = None
    last_progress_ts = time.time()

    while time.time() - eval_start_ts < timeout_sec:
        s_payload = _get_evaluation_status_payload(base_url)
        st = s_payload.get("status")
        prog = s_payload.get("progress")
        cq = s_payload.get("current_question")
        tq = s_payload.get("total_questions")
        err = s_payload.get("error")

        cq_int: Optional[int] = None
        try:
            if cq is not None:
                cq_int = int(cq)
        except Exception:
            cq_int = None

        if st in ("running", "started"):
            if cq_int is not None and cq_int != last_cq:
                last_cq = cq_int
                last_progress_ts = time.time()
            if time.time() - last_progress_ts >= float(stall_sec):
                raise RuntimeError("评估卡住")

        fp = json.dumps(
            {"status": st, "progress": prog, "current_question": cq, "total_questions": tq, "error": err},
            ensure_ascii=False,
            sort_keys=True,
        )
        if fp != last_eval_fp:
            last_eval_fp = fp
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 评估状态: status={st} progress={prog} q={cq}/{tq} error={err}", flush=True)

        if st in ("completed", "failed"):
            eval_done = True
            break

        time.sleep(5)

    if not eval_done:
        raise RuntimeError("评估超时")


def _run_single_evaluation(
    *,
    base_url: str,
    questions: List[Dict[str, Any]],
    model_provider: str,
    strategy: str,
    context_text: str,
    context_mode: str,
    timeout_sec: int = 1800,
) -> Dict[str, Any]:
    max_restarts = 2
    stall_sec = 90

    last_err: Optional[Exception] = None
    for attempt in range(max_restarts + 1):
        _reset_evaluation(base_url)
        _start_evaluation(
            base_url,
            questions=questions,
            model_provider=model_provider,
            strategy=strategy,
            context_text=context_text,
            context_mode=context_mode,
        )

        try:
            _wait_evaluation_done(base_url, timeout_sec=timeout_sec, stall_sec=stall_sec)
        except Exception as e:
            last_err = e
            if str(e) == "评估卡住" and attempt < max_restarts:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 检测到评估卡住，执行reset→start重启评估 (第{attempt + 1}/{max_restarts}次重启)",
                    flush=True,
                )
                continue
            raise

        status = _get_evaluation_status(base_url)
        if status != "completed":
            raise RuntimeError("评估失败")
        return _get_evaluation_result(base_url)

    raise RuntimeError(f"评估失败: {last_err}")


def _save_evaluation_outputs(
    *,
    out_dir: str,
    region: str,
    model_provider: str,
    memory_mode: str,
    strategy: str,
    reselect_start_count: int,
    ctx_text: str,
    result_data: Dict[str, Any],
) -> str:
    strat_result = result_data.get(strategy) or {}
    if not isinstance(strat_result, dict):
        raise RuntimeError(f"评估结果缺少策略 {strategy}: {region}")

    csv_dir = os.path.join(out_dir, "最近csv")
    report_root = os.path.join(out_dir, "最近报告", "探索策略+最近评估结果报告")
    _safe_mkdir(csv_dir)
    _safe_mkdir(report_root)

    csv_path = os.path.join(csv_dir, "探索策略+最近评估结果汇总.csv")
    fieldnames = [
        "Region",
        "Model",
        "Memory Mode",
        "Strategy",
        "Total Score",
        "Accuracy",
        "Completed At",
        "重选起点次数",
        "Type_定位与定向",
        "Type_空间距离估算",
        "Type_邻近关系判断",
        "Type_POI密度识别",
        "Type_路径规划",
    ]
    _write_csv_header(csv_path, fieldnames)

    type_scores = strat_result.get("type_scores") or {}
    row = {
        "Region": region,
        "Model": model_provider,
        "Memory Mode": memory_mode,
        "Strategy": strategy,
        "Total Score": strat_result.get("total_score", 0),
        "Accuracy": f"{float(strat_result.get('accuracy', 0) or 0):.2f}%",
        "Completed At": strat_result.get("completed_at") or datetime.now().isoformat(),
        "重选起点次数": reselect_start_count,
        "Type_定位与定向": f"{float((type_scores.get('定位与定向') or {}).get('percentage', 0) or 0):.2f}%",
        "Type_空间距离估算": f"{float((type_scores.get('空间距离估算') or {}).get('percentage', 0) or 0):.2f}%",
        "Type_邻近关系判断": f"{float((type_scores.get('邻近关系判断') or {}).get('percentage', 0) or 0):.2f}%",
        "Type_POI密度识别": f"{float((type_scores.get('POI密度识别') or {}).get('percentage', 0) or 0):.2f}%",
        "Type_路径规划": f"{float((type_scores.get('路径规划') or {}).get('percentage', 0) or 0):.2f}%",
    }
    _append_csv_row(csv_path, fieldnames, row)

    report = {
        "region": region,
        "source_file": f"{region}_{model_provider}_report.txt",
        "evaluation_time": datetime.now().isoformat(),
        "context_text": result_data.get("context_text") or ctx_text,
        "evaluation_result": result_data,
    }

    report_filename = f"评估报告_{region}_{model_provider}_report.txt.json"
    report_path = os.path.join(report_root, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report_path


def _run_once(
    *,
    base_url: str,
    input_report_dir: str,
    out_dir_first: str,
    out_dir_second: str,
    run_indices: List[int],
    region: str,
    model_provider: str,
    exploration_mode: str,
    memory_mode: str,
    strategy: str,
    max_rounds: int,
    use_local_data: bool,
    dry_run: bool,
) -> None:
    if dry_run:
        print(
            f"[DRY RUN] region={region} model={model_provider} memory={memory_mode} "
            f"strategy={strategy} exploration={exploration_mode} "
            f"out1={out_dir_first} out2={out_dir_second} runs={run_indices} input_report_dir={input_report_dir}"
        )
        return

    started_at = datetime.now()
    print(f"[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] 开始区域: {region} | 模型: {model_provider} | 记忆: {memory_mode} | 提问: {strategy} | 策略: {exploration_mode}", flush=True)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 切换区域中...", flush=True)
    _switch_region(base_url, region)

    ctx_text = _load_context_text_from_report(
        input_report_dir,
        region=region,
        model_provider=model_provider,
        memory_mode=memory_mode,
    )
    ctx_mode = (str(memory_mode) or "").strip().lower() or str(memory_mode)
    reselect_start_count = _extract_reselect_start_count(ctx_text)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 生成评估题目...", flush=True)
    questions = _get_questions_for_region(base_url, region)

    print("=" * 60, flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 传入评估Agent的探索上下文(context_mode={ctx_mode})", flush=True)
    print("=" * 60, flush=True)
    if ctx_text.strip():
        print(ctx_text, flush=True)
    else:
        print("[空上下文]", flush=True)
    print("=" * 60, flush=True)

    report_paths: List[str] = []
    summaries: List[Dict[str, Any]] = []
    pairs: Dict[int, str] = {1: out_dir_first, 2: out_dir_second}
    eval_out_dirs: List[Tuple[int, str]] = [(i, pairs[i]) for i in run_indices if i in pairs]
    for idx, eval_out_dir in eval_out_dirs:
        _safe_mkdir(eval_out_dir)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动第{idx}次评估...", flush=True)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待评估结束(最长30分钟)...", flush=True)
        result_data = _run_single_evaluation(
            base_url=base_url,
            questions=questions,
            model_provider=model_provider,
            strategy=strategy,
            context_text=ctx_text,
            context_mode=ctx_mode,
            timeout_sec=1800,
        )
        strat_result = result_data.get(strategy) or {}
        summaries.append(strat_result if isinstance(strat_result, dict) else {})
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 拉取评估结果并写入输出目录...", flush=True)
        report_path = _save_evaluation_outputs(
            out_dir=eval_out_dir,
            region=region,
            model_provider=model_provider,
            memory_mode=memory_mode,
            strategy=strategy,
            reselect_start_count=reselect_start_count,
            ctx_text=ctx_text,
            result_data=result_data,
        )
        report_paths.append(report_path)

    ended_at = datetime.now()
    duration = ended_at - started_at
    out1 = report_paths[0] if len(report_paths) > 0 else ""
    out2 = report_paths[1] if len(report_paths) > 1 else ""
    s1 = summaries[0] if len(summaries) > 0 else {}
    s2 = summaries[1] if len(summaries) > 1 else {}
    print(
        f"[{ended_at.strftime('%Y-%m-%d %H:%M:%S')}] 完成区域: {region} | 用时: {str(duration).split('.')[0]} | "
        f"第一次: score={s1.get('total_score')} acc={s1.get('accuracy')} | "
        f"第二次: score={s2.get('total_score')} acc={s2.get('accuracy')} | "
        f"第一次输出: {out1} | 第二次输出: {out2}",
        flush=True,
    )


def _parse_args(argv: List[str]) -> argparse.Namespace:
    default_out = os.path.join(PROJECT_ROOT, "txt_statistics", "大模型空间认知项目数据", "11验证随机性")
    default_input = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "2三种记忆",
        "三记忆+direct+是否有原始记忆",
        "无",
        "修改三记忆报告无原始记忆结果报告",
    )

    p = argparse.ArgumentParser()
    p.add_argument("--input-report-dir", default=default_input)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--out-dir", default=default_out)
    p.add_argument("--regions", default=",".join(REGIONS_15))
    p.add_argument("--models", default="")
    p.add_argument("--model", default="deepseek")
    p.add_argument("--memory-mode", default="context")
    p.add_argument("--strategy", default="Direct")
    p.add_argument("--exploration-mode", default="最近距离探索")
    p.add_argument("--max-rounds", type=int, default=1)
    p.add_argument("--use-local-data", action="store_true", default=True)
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--backend-logs", action="store_true", default=False)
    p.add_argument("--restart-backend-each-region", dest="restart_backend_each_region", action="store_true", default=True)
    p.add_argument("--no-restart-backend-each-region", dest="restart_backend_each_region", action="store_false")
    p.add_argument("--skip-deepseek-done", dest="skip_deepseek_done", action="store_true", default=True)
    p.add_argument("--no-skip-deepseek-done", dest="skip_deepseek_done", action="store_false")
    p.add_argument("--resume", dest="resume", action="store_true", default=True)
    p.add_argument("--no-resume", dest="resume", action="store_false")
    p.add_argument("--resume-partial", dest="resume_partial", action="store_true", default=True)
    p.add_argument("--no-resume-partial", dest="resume_partial", action="store_false")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)

    base_url = str(args.base_url).rstrip("/")
    out_root_dir = os.path.abspath(args.out_dir)
    out_dir_first = os.path.join(out_root_dir, "第一次结果")
    out_dir_second = os.path.join(out_root_dir, "第二次结果")
    regions = [r.strip() for r in str(args.regions).split(",") if r.strip()]

    has_models_flag = any(a == "--models" or str(a).startswith("--models=") for a in argv)
    has_model_flag = any(a == "--model" or str(a).startswith("--model=") for a in argv)
    if has_models_flag:
        raw_models = str(getattr(args, "models", "") or "")
    elif has_model_flag:
        raw_models = str(getattr(args, "model", "") or "")
    else:
        raw_models = ",".join(MODELS_5)

    models = _parse_csv_list(raw_models) if "," in raw_models else ([raw_models] if raw_models.strip() else [])
    models = [_normalize_model_name(m) for m in models if _normalize_model_name(m)]

    if not regions:
        print("未指定任何区域")
        return 2
    if not models:
        print("未指定任何模型")
        return 2

    host, port = _parse_host_port(base_url)
    local_host = host in ("127.0.0.1", "localhost")
    backend = BackendProcess(host=host, port=port, show_logs=bool(args.backend_logs)) if local_host else None

    if not args.dry_run and bool(args.restart_backend_each_region) and local_host:
        backend.restart() if backend else None
        ready = _wait_for_condition(lambda: _ping_server(base_url), timeout_sec=60, interval_sec=1)
        if not ready:
            print(f"无法连接后端: {base_url}")
            return 1
    elif not args.dry_run and not _ping_server(base_url):
        print(f"无法连接后端: {base_url}")
        return 1

    _safe_mkdir(out_dir_first)
    _safe_mkdir(out_dir_second)

    try:
        for model_provider in models:
            for region in regions:
                try:
                    if bool(args.skip_deepseek_done) and _normalize_model_name(model_provider) == "deepseek" and region in DEEPSEEK_DONE_REGIONS:
                        print(f"[SKIP] 已完成: model=deepseek region={region}")
                        continue

                    expected_1 = _expected_report_path(out_dir_first, region, model_provider)
                    expected_2 = _expected_report_path(out_dir_second, region, model_provider)
                    exists_1 = os.path.exists(expected_1)
                    exists_2 = os.path.exists(expected_2)

                    run_indices = [1, 2]
                    if bool(args.resume):
                        if exists_1 and exists_2:
                            print(f"[SKIP] 已存在: model={model_provider} region={region}")
                            continue
                        if bool(args.resume_partial):
                            run_indices = []
                            if not exists_1:
                                run_indices.append(1)
                            if not exists_2:
                                run_indices.append(2)
                            if not run_indices:
                                print(f"[SKIP] 已存在: model={model_provider} region={region}")
                                continue
                        else:
                            if exists_1 or exists_2:
                                print(f"[SKIP] 已存在(部分): model={model_provider} region={region}")
                                continue

                    if not args.dry_run and bool(args.restart_backend_each_region) and local_host and backend:
                        backend.restart()
                        ready = _wait_for_condition(lambda: _ping_server(base_url), timeout_sec=60, interval_sec=1)
                        if not ready:
                            raise RuntimeError(f"后端未就绪: {base_url}")

                    _run_once(
                        base_url=base_url,
                        input_report_dir=str(args.input_report_dir),
                        out_dir_first=out_dir_first,
                        out_dir_second=out_dir_second,
                        run_indices=run_indices,
                        region=region,
                        model_provider=model_provider,
                        exploration_mode=str(args.exploration_mode),
                        memory_mode=str(args.memory_mode),
                        strategy=str(args.strategy),
                        max_rounds=int(args.max_rounds),
                        use_local_data=bool(args.use_local_data),
                        dry_run=bool(args.dry_run),
                    )
                except KeyboardInterrupt:
                    return 130
                except Exception as e:
                    print(f"失败: model={model_provider} region={region} -> {e}")
    finally:
        try:
            if backend:
                backend.stop()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
