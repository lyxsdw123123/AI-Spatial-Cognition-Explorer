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


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


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


def _wait_for_condition(check_fn, *, timeout_sec: int, interval_sec: int) -> bool:
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


def _reset_evaluation(base_url: str) -> None:
    try:
        _request_json("POST", f"{base_url}/evaluation/reset", json_body={}, timeout=30)
    except Exception:
        pass


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


def _get_evaluation_status_payload(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/status", timeout=30)
    return payload if isinstance(payload, dict) else {}


def _get_evaluation_status(base_url: str) -> str:
    payload = _request_json("GET", f"{base_url}/evaluation/status", timeout=30)
    if not payload.get("success"):
        return "unknown"
    return str(payload.get("status") or "unknown")


def _get_evaluation_result(base_url: str) -> Dict[str, Any]:
    payload = _request_json("GET", f"{base_url}/evaluation/result", timeout=60)
    if not payload.get("success"):
        raise RuntimeError(f"获取评估结果失败: {payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"评估结果格式异常: {type(data)}")
    return data


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
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] 评估状态: status={st} progress={prog} q={cq}/{tq} error={err}",
                flush=True,
            )

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
    timeout_sec: int,
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


def _write_csv_header(csv_path: str, fieldnames: List[str]) -> None:
    _safe_mkdir(os.path.dirname(csv_path))
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        try:
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as rf:
                reader = csv.reader(rf)
                existing = next(reader, None)
            if existing and [h.strip() for h in existing] == fieldnames:
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


def _read_text_file_any_encoding(path: str) -> str:
    encs = ["utf-8", "utf-8-sig", "gb18030"]
    last_err: Optional[Exception] = None
    for enc in encs:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"读取文本失败: {path} ({last_err})")


def _extract_region_from_filename(filename: str) -> str:
    fn = os.path.basename(filename)
    m = re.search(r"^评估报告_(.+?)_qwen_report\.txt__", fn)
    if m:
        return str(m.group(1)).strip()
    m = re.search(r"^评估报告_(.+?)_", fn)
    if m:
        return str(m.group(1)).strip()
    base = fn
    if base.startswith("评估报告_"):
        base = base[len("评估报告_") :]
    base = base.split("_")[0]
    return base.strip()


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


def _parse_csv_list(v: str) -> List[str]:
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _normalize_model_name(name: str) -> str:
    s = (str(name) or "").strip().lower()
    if s in ("chatgpt", "gpt", "gpt4", "gpt-4", "gpt5", "gpt-5", "openai"):
        return "openai"
    return s


def _list_report_txt_files(input_dir: str) -> List[str]:
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入文件夹不存在: {input_dir}")
    out: List[str] = []
    for fn in os.listdir(input_dir):
        p = os.path.join(input_dir, fn)
        if not os.path.isfile(p):
            continue
        low = fn.lower()
        if low.endswith(".csv"):
            continue
        if "字节统计" in fn:
            continue
        if not low.endswith(".txt"):
            continue
        if not fn.startswith("评估报告_"):
            continue
        out.append(p)
    return sorted(out)


def _expected_json_path(report_out_dir: str, region: str, eval_model: str) -> str:
    return os.path.join(report_out_dir, f"评估结果_{region}_{eval_model}.json")


def _parse_args(argv: List[str]) -> argparse.Namespace:
    default_input = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "12压缩记忆",
        "一次压缩",
    )
    default_skip_regions = ""
    default_report_out = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "12压缩记忆",
        "评估结果",
        "评估结果报告",
    )
    default_csv_out = os.path.join(
        PROJECT_ROOT,
        "txt_statistics",
        "大模型空间认知项目数据",
        "12压缩记忆",
        "评估结果",
        "评估csv",
    )

    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", default=default_input)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--report-out-dir", default=default_report_out)
    p.add_argument("--csv-out-dir", default=default_csv_out)
    p.add_argument("--csv-name", default="一次压缩_评估汇总.csv")
    p.add_argument("--models", default="gemini")
    p.add_argument("--skip-regions", default=default_skip_regions)
    p.add_argument("--strategy", default="Direct")
    p.add_argument("--context-mode", default="一次压缩")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--backend-logs", action="store_true", default=False)
    p.add_argument("--restart-backend-each-region", dest="restart_backend_each_region", action="store_true", default=True)
    p.add_argument("--no-restart-backend-each-region", dest="restart_backend_each_region", action="store_false")
    p.add_argument("--resume", dest="resume", action="store_true", default=False)
    p.add_argument("--no-resume", dest="resume", action="store_false")
    p.add_argument("--timeout-sec", type=int, default=1800)
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = _parse_args(argv)

    base_url = str(args.base_url).rstrip("/")
    input_dir = str(args.input_dir)
    report_out_dir = os.path.abspath(str(args.report_out_dir))
    csv_out_dir = os.path.abspath(str(args.csv_out_dir))
    csv_path = os.path.join(csv_out_dir, str(args.csv_name))
    strategy = str(args.strategy)
    context_mode = str(args.context_mode)
    timeout_sec = int(args.timeout_sec)

    models = [_normalize_model_name(m) for m in _parse_csv_list(str(args.models))]
    models = [m for m in models if m in ("gemini",)]
    if not models:
        print("未指定任何评估模型（仅支持 gemini）")
        return 2

    skip_regions = set(_parse_csv_list(str(getattr(args, "skip_regions", "") or "")))

    report_files = _list_report_txt_files(input_dir)
    if not report_files:
        print(f"未找到任何待评估txt报告: {input_dir}")
        return 2

    host, port = _parse_host_port(base_url)
    local_host = host in ("127.0.0.1", "localhost")
    backend = BackendProcess(host=host, port=port, show_logs=bool(args.backend_logs)) if local_host else None

    if not args.dry_run and local_host:
        backend.start() if backend else None
        ready = _wait_for_condition(lambda: _ping_server(base_url), timeout_sec=60, interval_sec=1)
        if not ready:
            print(f"无法连接后端: {base_url}")
            return 1
    elif not args.dry_run and not _ping_server(base_url):
        print(f"无法连接后端: {base_url}")
        return 1

    _safe_mkdir(report_out_dir)
    _safe_mkdir(csv_out_dir)

    fieldnames = [
        "Region",
        "Eval Model",
        "Source File",
        "Context Mode",
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

    try:
        for report_path in report_files:
            region = _extract_region_from_filename(os.path.basename(report_path))
            if region in skip_regions:
                print(f"[SKIP] 已跳过区域: {region}", flush=True)
                continue
            print("=" * 80, flush=True)
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始报告: {os.path.basename(report_path)} | 区域: {region}",
                flush=True,
            )

            if not args.dry_run and bool(args.restart_backend_each_region) and local_host and backend:
                backend.restart()
                ready = _wait_for_condition(lambda: _ping_server(base_url), timeout_sec=60, interval_sec=1)
                if not ready:
                    print(f"后端未就绪: {base_url}")
                    continue

            if args.dry_run:
                print(
                    f"[DRY RUN] 将读取全文并评估: region={region} models={models} strategy={strategy} context_mode={context_mode}",
                    flush=True,
                )
                continue

            try:
                _switch_region(base_url, region)
            except Exception as e:
                print(f"切换区域失败: {region} -> {e}", flush=True)
                continue

            try:
                questions = _get_questions_for_region(base_url, region)
            except Exception as e:
                print(f"生成题目失败: {region} -> {e}", flush=True)
                continue

            try:
                ctx_text = _read_text_file_any_encoding(report_path)
            except Exception as e:
                print(f"读取报告失败: {report_path} -> {e}", flush=True)
                continue

            reselect_start_count = _extract_reselect_start_count(ctx_text)

            for eval_model in models:
                expected_json = _expected_json_path(report_out_dir, region, eval_model)
                if bool(args.resume) and os.path.exists(expected_json):
                    print(f"[SKIP] 已存在: {os.path.basename(expected_json)}", flush=True)
                    continue

                started_at = datetime.now()
                print(
                    f"[{started_at.strftime('%H:%M:%S')}] 启动评估: region={region} eval_model={eval_model} strategy={strategy}",
                    flush=True,
                )

                try:
                    result_data = _run_single_evaluation(
                        base_url=base_url,
                        questions=questions,
                        model_provider=eval_model,
                        strategy=strategy,
                        context_text=ctx_text,
                        context_mode=context_mode,
                        timeout_sec=timeout_sec,
                    )
                except Exception as e:
                    print(
                        f"失败: report={os.path.basename(report_path)} region={region} model={eval_model} -> {e}",
                        flush=True,
                    )
                    continue

                strat_result = result_data.get(strategy) or {}
                if not isinstance(strat_result, dict):
                    print(
                        f"评估结果缺少策略 {strategy}: report={os.path.basename(report_path)} region={region} model={eval_model}",
                        flush=True,
                    )
                    continue

                type_scores = strat_result.get("type_scores") or {}
                row = {
                    "Region": region,
                    "Eval Model": eval_model,
                    "Source File": os.path.basename(report_path),
                    "Context Mode": context_mode,
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
                    "eval_model": eval_model,
                    "strategy": strategy,
                    "context_mode": context_mode,
                    "source_file": os.path.basename(report_path),
                    "source_path": os.path.abspath(report_path),
                    "evaluation_time": datetime.now().isoformat(),
                    "context_text": result_data.get("context_text") or ctx_text,
                    "evaluation_result": result_data,
                }
                with open(expected_json, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)

                ended_at = datetime.now()
                duration = ended_at - started_at
                print(
                    f"[{ended_at.strftime('%H:%M:%S')}] 完成: region={region} model={eval_model} "
                    f"score={strat_result.get('total_score')} acc={strat_result.get('accuracy')} "
                    f"用时={str(duration).split('.')[0]} 输出={os.path.basename(expected_json)}",
                    flush=True,
                )

        print("=" * 80, flush=True)
        print(f"全部完成。报告输出目录: {report_out_dir}", flush=True)
        print(f"CSV输出: {csv_path}", flush=True)
    finally:
        try:
            if backend:
                backend.stop()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
