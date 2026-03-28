import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.config import Config

try:
    from langchain.chains.summarize import load_summarize_chain
except Exception as e:
    raise RuntimeError("未能导入 load_summarize_chain，请确认已安装 langchain>=0.2") from e

try:
    from langchain_core.documents import Document
except Exception as e:
    raise RuntimeError("未能导入 Document，请确认已安装 langchain-core") from e

try:
    from langchain_community.chat_models import ChatTongyi
except Exception as e:
    raise RuntimeError("未能导入 ChatTongyi，请确认已安装 langchain-community>=0.2") from e

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:
    from langchain.text_splitter import RecursiveCharacterTextSplitter


def _collect_context_texts(obj: Any, out: List[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "context_text" and isinstance(v, str) and v.strip():
                out.append(v)
            else:
                _collect_context_texts(v, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect_context_texts(it, out)


def pick_one_context_text(data: Dict[str, Any]) -> str:
    ctxs: List[str] = []
    _collect_context_texts(data, ctxs)
    uniq: List[str] = []
    seen = set()
    for c in ctxs:
        key = c.strip()
        if key and key not in seen:
            seen.add(key)
            uniq.append(c)
    if not uniq:
        raise RuntimeError("报告中未找到有效 context_text")
    uniq.sort(key=lambda s: len(s.encode("utf-8")), reverse=True)
    return uniq[0]


def parse_turns(context_text: str) -> List[Tuple[str, str]]:
    parts = re.split(r"---\s*Step\s*\d+\s*---", context_text)
    turns: List[Tuple[str, str]] = []

    for raw in parts:
        chunk = raw.strip()
        if not chunk:
            continue

        user_in: Optional[str] = None
        ai_out: Optional[str] = None

        m_user = re.search(r"User Input:\s*(.*?)(?:\nAI Thought:|\Z)", chunk, flags=re.S)
        if m_user:
            user_in = m_user.group(1).strip()

        responded_blocks = re.findall(r"responded:\s*(.*?)(?:\n\n\nTool Output:|\Z)", chunk, flags=re.S)
        if responded_blocks:
            ai_out = "\n\n".join([b.strip() for b in responded_blocks if b.strip()]).strip()

        tool_blocks = re.findall(r"Tool Output:\s*(.*?)(?:\nAI Thought:|\Z)", chunk, flags=re.S)
        tool_text = "\n\n".join([b.strip() for b in tool_blocks if b.strip()]).strip()

        if user_in and tool_text:
            user_in = f"{user_in}\n\n[Tool Output]\n{tool_text}"
        elif tool_text and not user_in:
            user_in = f"[Tool Output]\n{tool_text}"

        if not user_in:
            user_in = chunk[:2000].strip()

        if not ai_out:
            m_invoke = re.findall(r"Invoking:\s*`([^`]+)`\s*with\s*`([^`]+)`", chunk)
            if m_invoke:
                inv_lines = [f"{name} {args_}".strip() for name, args_ in m_invoke]
                ai_out = "Invoked tools: " + " | ".join(inv_lines)
            else:
                ai_out = "No explicit agent response recorded in this step."

        turns.append((user_in, ai_out))

    return turns


def _extract_chain_output_text(out: Any) -> str:
    if isinstance(out, dict):
        v = out.get("output_text")
        if isinstance(v, str) and v.strip():
            return v.strip()
        for vv in out.values():
            if isinstance(vv, str) and vv.strip():
                return vv.strip()
    if isinstance(out, str) and out.strip():
        return out.strip()
    return ""


def summarize_default_iterative(
    llm,
    text: str,
    chunk_size: int = 6000,
    chunk_overlap: int = 200,
    passes: int = 1,
) -> str:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = [t for t in splitter.split_text(text) if t.strip()]
    if not chunks:
        return ""

    chain = load_summarize_chain(llm, chain_type="stuff")
    cur_docs = [Document(page_content=c) for c in chunks]
    print(f"[summarize] chunks={len(cur_docs)} passes={passes}", flush=True)

    for _ in range(max(1, passes)):
        summaries: List[str] = []
        for idx, d in enumerate(cur_docs, start=1):
            if len(cur_docs) > 1 and (idx == 1 or idx % 10 == 0 or idx == len(cur_docs)):
                print(f"[summarize] pass_chunk {idx}/{len(cur_docs)}", flush=True)
            try:
                out = chain.invoke({"input_documents": [d]})
            except Exception:
                out = chain({"input_documents": [d]})
            s = _extract_chain_output_text(out)
            if s:
                summaries.append(s)
        if not summaries:
            raise RuntimeError("默认摘要链未返回有效文本")
        merged = "\n".join(summaries)
        cur_docs = [Document(page_content=merged)]

    final_text = cur_docs[0].page_content.strip()
    if not final_text:
        raise RuntimeError("默认摘要链未返回有效文本")
    return final_text


def _extract_model_from_filename(name: str) -> str:
    m = re.search(r"_([a-zA-Z0-9]+)_report\.txt\.json$", name)
    return (m.group(1).lower() if m else "")


def compress_one_file(
    llm,
    input_path: Path,
    output_dir: Path,
    skip_existing: bool,
) -> Optional[Tuple[str, str, str, int, int, str]]:
    model = _extract_model_from_filename(input_path.name)
    with input_path.open("r", encoding="utf-8") as f:
        data = json.loads(f.read())

    region = data.get("region") or "unknown_region"
    base = input_path.stem
    out_50 = output_dir / f"{base}__{region}__summary_memory_50pct.txt"
    if skip_existing and out_50.exists():
        b = out_50.stat().st_size
        print(f"skip_existing: {str(out_50)}", flush=True)
        print("", flush=True)
        return (region, model, out_50.name, b, b * 8, str(out_50.parent))

    context_text = pick_one_context_text(data)
    ctx_bytes = len(context_text.encode("utf-8"))
    print(f"input: {str(input_path)}", flush=True)
    print(f"region: {region}", flush=True)
    if model:
        print(f"source_model: {model}", flush=True)
    print(f"context_bytes: {ctx_bytes}", flush=True)

    print("[run] generating 50% summary (1 pass default chain)...", flush=True)
    summary_50 = summarize_default_iterative(llm, context_text, passes=1)

    out_50.write_text(summary_50, encoding="utf-8")
    b = len(summary_50.encode("utf-8"))
    print(f"summary_50_bytes: {b} -> {str(out_50)}", flush=True)
    print("", flush=True)
    return (region, model, out_50.name, b, b * 8, str(out_50.parent))


def _split_csv_set(v: str) -> List[str]:
    items: List[str] = []
    for x in (v or "").split(","):
        x = x.strip().lower()
        if x:
            items.append(x)
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        default=r"txt_statistics\大模型空间认知项目数据\1三种探索策略\探索策略结果\最近\最近报告\探索策略+最近评估结果报告",
    )
    ap.add_argument(
        "--output_dir",
        default=r"txt_statistics\大模型空间认知项目数据\12压缩记忆\test\一次压缩_其他模型",
    )
    ap.add_argument(
        "--include_models",
        default="openai,deepseek,claude,gemini",
    )
    ap.add_argument(
        "--exclude_models",
        default="qwen",
    )
    ap.add_argument(
        "--stats_csv",
        default=r"txt_statistics\大模型空间认知项目数据\12压缩记忆\test\一次压缩_其他模型\csv\压缩记忆_50pct_其他模型字节统计.csv",
    )
    ap.add_argument(
        "--skip_existing",
        action="store_true",
        default=False,
    )
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parent
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = project_root / input_path
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"output_dir: {str(output_dir)}", flush=True)
    print("", flush=True)

    if not Config.DASHSCOPE_API_KEY:
        raise ValueError("DashScope API Key is missing. Please configure DASHSCOPE_API_KEY.")

    llm = ChatTongyi(
        dashscope_api_key=Config.DASHSCOPE_API_KEY,
        model_name="qwen-plus-2025-12-01",
        temperature=0.2,
    )

    include_models = set(_split_csv_set(args.include_models))
    exclude_models = set(_split_csv_set(args.exclude_models))

    targets: List[Path] = []
    if input_path.is_dir():
        for p in sorted(input_path.rglob("*_report.txt.json")):
            m = _extract_model_from_filename(p.name)
            if include_models and m not in include_models:
                continue
            if exclude_models and m in exclude_models:
                continue
            targets.append(p)
    else:
        targets.append(input_path)

    skipped = 0
    rows: List[Tuple[str, str, str, int, int, str]] = []
    for p in targets:
        out = compress_one_file(llm, p, output_dir, skip_existing=args.skip_existing)
        if out:
            rows.append(out)
        else:
            skipped += 1

    stats_csv = Path(args.stats_csv)
    if not stats_csv.is_absolute():
        stats_csv = project_root / stats_csv
    stats_csv.parent.mkdir(parents=True, exist_ok=True)

    with stats_csv.open("w", encoding="utf-8-sig", newline="") as w:
        cw = csv.writer(w)
        cw.writerow(["region", "source_model", "file_name", "compressed_bytes", "compressed_bits", "folder"])
        for r in sorted(rows, key=lambda x: (x[0], x[1], x[2])):
            cw.writerow(list(r))

    print(f"done_files: {len(rows)}", flush=True)
    print(f"skipped_files: {skipped}", flush=True)
    print(f"stats_csv: {str(stats_csv)}", flush=True)


if __name__ == "__main__":
    main()
