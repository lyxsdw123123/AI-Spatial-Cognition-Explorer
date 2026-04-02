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
from urllib.parse import urlparse

import requests


try:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding=sys.stdout.encoding, errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding=sys.stderr.encoding, errors="replace")
except Exception:
    pass


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
    "长沙五一广场",
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
    method_u = str(method or "").upper()
    max_attempts = 3 if method_u in ("GET", "HEAD", "OPTIONS") else 1
    last_exc: Optional[BaseException] = None
    for attempt in range(max_attempts):
        try:
            resp = requests.request(method_u, url, json=json_body, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt < max_attempts - 1:
                time.sleep(1 + attempt * 2)
                continue
            raise
        except Exception as e:
            last_exc = e
            raise
    raise RuntimeError(f"请求失败: {url} -> {last_exc}")


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
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
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
                    subprocess.run(
                        ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
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


def _switch_region(base_url: str, region: str) -> None:
    payload = _request_json(
        "POST",
        f"{base_url}/exploration/switch_region",
        json_body={"region_name": region},
        timeout=60,
    )
    if not payload.get("success"):
        raise RuntimeError(f"切换区域失败: {payload}")


def _set_local_data_paths(
    base_url: str,
    *,
    poi_shp_path: str,
    road_shp_path: str,
    road_nodes_shp_path: str,
    grid_shp_path: str,
) -> None:
    payload = _request_json(
        "POST",
        f"{base_url}/exploration/set_local_data_paths",
        json_body={
            "poi_shp_path": poi_shp_path,
            "road_shp_path": road_shp_path,
            "road_nodes_shp_path": road_nodes_shp_path,
            "grid_shp_path": grid_shp_path,
        },
        timeout=60,
    )
    if not payload.get("success"):
        raise RuntimeError(f"设置本地数据路径失败: {payload}")


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


def _reset_evaluation(base_url: str) -> None:
    payload = _request_json("POST", f"{base_url}/evaluation/reset", json_body={}, timeout=60)
    if not payload.get("success"):
        raise RuntimeError(f"重置评估失败: {payload}")


def _get_evaluation_status_payload(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/status", timeout=60)
    return payload if isinstance(payload, dict) else {}


def _get_evaluation_result(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/result", timeout=60)
    if not payload.get("success"):
        raise RuntimeError(f"获取评估结果失败: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"评估结果格式异常: {type(data)}")
    return data


def _run_evaluation_with_reset_and_watchdog(
    base_url: str,
    *,
    questions: List[Dict[str, Any]],
    model_provider: str,
    strategy: str,
    context_text: str,
    context_mode: str,
    total_timeout_sec: int = 1800,
    stall_timeout_sec: int = 180,
    max_restarts: int = 2,
) -> None:
    overall_start = time.time()
    last_error: Optional[str] = None
    for attempt in range(max_restarts + 1):
        elapsed = time.time() - overall_start
        remaining = total_timeout_sec - elapsed
        if remaining <= 0:
            raise RuntimeError(f"评估超时(总超时{total_timeout_sec}s)，最后错误: {last_error}")

        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 重置评估状态...", flush=True)
            _reset_evaluation(base_url)
        except Exception as e:
            last_error = str(e)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 重置评估失败(继续尝试启动): {e}", flush=True)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动评估(attempt={attempt + 1}/{max_restarts + 1})...", flush=True)
        _start_evaluation(
            base_url,
            questions=questions,
            model_provider=model_provider,
            strategy=strategy,
            context_text=context_text,
            context_mode=context_mode,
        )

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待评估结束(remaining={int(remaining)}s)...", flush=True)
        attempt_start = time.time()
        last_eval_fp: Optional[str] = None
        last_change_ts = time.time()
        consecutive_status_errors = 0
        last_status: Optional[str] = None
        last_progress: Optional[Any] = None
        last_cq: Optional[Any] = None
        last_tq: Optional[Any] = None
        last_error = None

        while time.time() - attempt_start < remaining:
            try:
                s_payload = _get_evaluation_status_payload(base_url)
                consecutive_status_errors = 0
            except Exception as e:
                consecutive_status_errors += 1
                last_error = str(e)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 获取评估状态失败(第{consecutive_status_errors}次): {e}", flush=True)
                if consecutive_status_errors >= 3:
                    if attempt >= max_restarts:
                        raise RuntimeError(f"评估状态连续超时/断连，且已达到最大重启次数: {e}")
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 评估状态连续失败，准备重启评估...", flush=True)
                    break
                time.sleep(5)
                continue
            st = s_payload.get("status")
            prog = s_payload.get("progress")
            cq = s_payload.get("current_question")
            tq = s_payload.get("total_questions")
            err = s_payload.get("error")

            fp = json.dumps(
                {"status": st, "progress": prog, "current_question": cq, "total_questions": tq, "error": err},
                ensure_ascii=False,
                sort_keys=True,
            )

            changed = (
                fp != last_eval_fp
                or st != last_status
                or prog != last_progress
                or cq != last_cq
                or tq != last_tq
                or err != last_error
            )
            if changed:
                last_eval_fp = fp
                last_change_ts = time.time()
                last_status, last_progress, last_cq, last_tq, last_error = st, prog, cq, tq, err
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] 评估状态: status={st} progress={prog} q={cq}/{tq} error={err}",
                    flush=True,
                )

            if st in ("completed", "failed"):
                if st == "completed":
                    return
                if attempt >= max_restarts:
                    raise RuntimeError(f"评估失败且已达到最大重启次数: error={err}")
                break

            if time.time() - last_change_ts > stall_timeout_sec:
                if attempt >= max_restarts:
                    raise RuntimeError(f"评估疑似卡死(超过{stall_timeout_sec}s无状态变化)，且已达到最大重启次数")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 评估疑似卡死(超过{stall_timeout_sec}s无状态变化)，准备重启评估...", flush=True)
                break

            time.sleep(5)

    raise RuntimeError(f"评估未完成，最后错误: {last_error}")


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


def _ensure_shp(path_without_ext_or_shp: str) -> str:
    p = str(path_without_ext_or_shp)
    if p.lower().endswith(".shp"):
        return p
    return p + ".shp"


def _get_dataset_paths(dataset_root: str, *, region: str, variant: int) -> Dict[str, str]:
    sub_dir = os.path.join(dataset_root, region, str(int(variant)))
    poi = _ensure_shp(os.path.join(sub_dir, f"POI{int(variant)}"))
    road = _ensure_shp(os.path.join(sub_dir, f"道路{int(variant)}"))
    road_nodes = _ensure_shp(os.path.join(sub_dir, f"道路节点{int(variant)}"))
    grid = _ensure_shp(os.path.join(sub_dir, f"{int(variant)}边界"))

    missing = []
    for label, p in [
        ("POI", poi),
        ("道路", road),
        ("道路节点", road_nodes),
        ("边界", grid),
    ]:
        if not os.path.exists(p):
            missing.append(f"{label}={p}")
    if missing:
        raise RuntimeError(f"本地数据缺失: region={region} variant={variant} -> " + "; ".join(missing))

    return {
        "poi_shp_path": os.path.abspath(poi),
        "road_shp_path": os.path.abspath(road),
        "road_nodes_shp_path": os.path.abspath(road_nodes),
        "grid_shp_path": os.path.abspath(grid),
    }


def _run_once(
    *,
    base_url: str,
    out_dir: str,
    dataset_root: str,
    region: str,
    variant: int,
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
            f"[DRY RUN] variant={variant} region={region} model={model_provider} memory={memory_mode} strategy={strategy} exploration={exploration_mode}"
        )
        return

    started_at = datetime.now()
    print(
        f"[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] 开始区域: {region} | 边界: {variant} | 模型: {model_provider} | 记忆: {memory_mode} | 提问: {strategy} | 策略: {exploration_mode}",
        flush=True,
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 切换区域中...", flush=True)
    _switch_region(base_url, region)

    paths = _get_dataset_paths(dataset_root, region=region, variant=variant)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 设置本地数据路径...", flush=True)
    _set_local_data_paths(
        base_url,
        poi_shp_path=paths["poi_shp_path"],
        road_shp_path=paths["road_shp_path"],
        road_nodes_shp_path=paths["road_nodes_shp_path"],
        grid_shp_path=paths["grid_shp_path"],
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 获取本地POI与边界...", flush=True)
    pois = _get_local_pois(base_url)
    boundary, start_location = _calculate_bounds_and_start(pois)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 初始化探索...", flush=True)
    _init_exploration(
        base_url,
        start_location=start_location,
        boundary=boundary,
        exploration_mode=exploration_mode,
        memory_mode=memory_mode,
        max_rounds=max_rounds,
        model_provider=model_provider,
        use_local_data=use_local_data,
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动探索...", flush=True)
    _start_exploration(base_url, memory_mode)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待探索结束(最长30分钟)...", flush=True)
    last_history_total_lines: Optional[int] = None
    last_status_fingerprint: Optional[str] = None
    exploration_start_ts = time.time()
    finished = False
    while time.time() - exploration_start_ts < 1800:
        st = _get_exploration_status(base_url)
        is_exploring = bool(st.get("is_exploring"))
        region_name = st.get("region_name")
        visited_cnt = st.get("visited_poi_count")
        current_status = st.get("current_status")
        last_decision = st.get("last_decision")

        fp = json.dumps(
            {
                "is_exploring": is_exploring,
                "region_name": region_name,
                "visited_poi_count": visited_cnt,
                "current_status": current_status,
                "last_decision": last_decision,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if fp != last_status_fingerprint:
            last_status_fingerprint = fp
            rn = region_name if isinstance(region_name, str) and region_name else region
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] 探索状态: region={rn} is_exploring={is_exploring} visited={visited_cnt} status={current_status}",
                flush=True,
            )
            if last_decision:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 最近决策: {json.dumps(last_decision, ensure_ascii=False)}", flush=True)

        hist = _get_exploration_raw_history_tail(base_url, tail_lines=120)
        total_lines = hist.get("total_lines")
        tail_text = hist.get("tail_text")
        if isinstance(total_lines, int) and (last_history_total_lines is None or total_lines != last_history_total_lines):
            last_history_total_lines = total_lines
            if isinstance(tail_text, str) and tail_text.strip():
                print("=" * 60, flush=True)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Agent探索思考过程(尾部，total_lines={total_lines})", flush=True)
                print("=" * 60, flush=True)
                print(tail_text, flush=True)
                print("=" * 60, flush=True)

        if not is_exploring:
            finished = True
            break
        time.sleep(10)

    if not finished:
        print(f"探索超时: {region} | 边界: {variant}", flush=True)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 停止探索并生成题目/上下文...", flush=True)
    stop_payload = _stop_exploration(base_url)
    eq_payload = stop_payload.get("evaluation_questions") or {}
    questions = eq_payload.get("questions") or []
    if not isinstance(questions, list) or not questions:
        raise RuntimeError(f"未获取到评估题目: {region} | 边界: {variant}")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 获取后端缓存的context_text...", flush=True)
    ctx_text, ctx_mode = _get_latest_context(base_url)
    if not ctx_text.strip():
        ctx_text = ""
    if not ctx_mode.strip():
        ctx_mode = memory_mode
    reselect_start_count = _extract_reselect_start_count(ctx_text)

    print("=" * 60, flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 传入评估Agent的探索上下文(context_mode={ctx_mode})", flush=True)
    print("=" * 60, flush=True)
    if ctx_text.strip():
        print(ctx_text, flush=True)
    else:
        print("[空上下文]", flush=True)
    print("=" * 60, flush=True)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动评估...", flush=True)
    _run_evaluation_with_reset_and_watchdog(
        base_url,
        questions=questions,
        model_provider=model_provider,
        strategy=strategy,
        context_text=ctx_text,
        context_mode=ctx_mode,
        total_timeout_sec=1800,
        stall_timeout_sec=180,
        max_restarts=2,
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 拉取评估结果...", flush=True)
    result_data = _get_evaluation_result(base_url)
    strat_result = result_data.get(strategy) or {}
    if not isinstance(strat_result, dict):
        raise RuntimeError(f"评估结果缺少策略 {strategy}: {region} | 边界: {variant}")

    csv_dir = os.path.join(out_dir, f"{int(variant)}csv")
    report_root = os.path.join(out_dir, f"{int(variant)}报告", "探索策略+最近评估结果报告")
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
        "variant": int(variant),
        "source_file": f"{region}_{model_provider}_{int(variant)}_report.txt",
        "evaluation_time": datetime.now().isoformat(),
        "context_text": result_data.get("context_text") or ctx_text,
        "evaluation_result": result_data,
    }

    report_filename = f"评估报告_{region}_{model_provider}_{int(variant)}_report.txt.json"
    report_path = os.path.join(report_root, report_filename)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    ended_at = datetime.now()
    duration = ended_at - started_at
    print(
        f"[{ended_at.strftime('%Y-%m-%d %H:%M:%S')}] 完成区域: {region} | 边界: {variant} | 用时: {str(duration).split('.')[0]} | 输出: {report_path}",
        flush=True,
    )


def _parse_args(argv: List[str]) -> argparse.Namespace:
    default_dataset_root = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "15不同格网4060数据",
        "4060制作",
        "区域",
    )
    default_out = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "15不同格网4060数据",
        "实验结果",
    )

    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--dataset-root", default=default_dataset_root)
    p.add_argument("--out-dir", default=default_out)
    p.add_argument("--regions", default=",".join(REGIONS_15))
    p.add_argument("--variants", default="40,60")
    p.add_argument("--model", default="qwen")
    p.add_argument("--memory-mode", default="context")
    p.add_argument("--strategy", default="Direct")
    p.add_argument("--exploration-mode", default="最近距离探索")
    p.add_argument("--max-rounds", type=int, default=1)
    p.add_argument("--use-local-data", action="store_true", default=True)
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--backend-logs", action="store_true", default=False)
    p.add_argument("--restart-backend-each-region", dest="restart_backend_each_region", action="store_true", default=True)
    p.add_argument("--no-restart-backend-each-region", dest="restart_backend_each_region", action="store_false")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)

    base_url = str(args.base_url).rstrip("/")
    out_dir = os.path.abspath(args.out_dir)
    dataset_root = os.path.abspath(str(args.dataset_root))
    regions = [r.strip() for r in str(args.regions).split(",") if r.strip()]
    variants: List[int] = []
    for v in [x.strip() for x in str(args.variants).split(",") if x.strip()]:
        try:
            variants.append(int(v))
        except Exception:
            raise RuntimeError(f"variants参数非法: {args.variants}")

    variants = [v for v in variants if v in (40, 60)]
    if not variants:
        variants = [40, 60]

    if 40 in variants and 60 in variants:
        variants = [40, 60]

    if not regions:
        print("未指定任何区域")
        return 2

    if not os.path.isdir(dataset_root):
        print(f"dataset-root不存在: {dataset_root}")
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

    _safe_mkdir(out_dir)

    try:
        for variant in variants:
            print("=" * 70, flush=True)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始批次: 边界={variant}", flush=True)
            print("=" * 70, flush=True)
            for region in regions:
                try:
                    if not args.dry_run and bool(args.restart_backend_each_region) and local_host and backend:
                        backend.restart()
                        ready = _wait_for_condition(lambda: _ping_server(base_url), timeout_sec=60, interval_sec=1)
                        if not ready:
                            raise RuntimeError(f"后端未就绪: {base_url}")

                    _run_once(
                        base_url=base_url,
                        out_dir=out_dir,
                        dataset_root=dataset_root,
                        region=region,
                        variant=int(variant),
                        model_provider=str(args.model),
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
                    print(f"失败: 边界={variant} 区域={region} -> {e}", flush=True)
    finally:
        try:
            if backend:
                backend.stop()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
