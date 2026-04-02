import argparse
import asyncio
import csv
from datetime import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from dashscope import Generation
from openai import AsyncOpenAI

from backend.evaluation_agent import EvaluationAgent
from config.config import Config


PROJECT_ROOT = Path(__file__).resolve().parent
QWEN_PLUS_2025_12_01_PRICE_URL = "https://www.alibabacloud.com/help/en/model-studio/models"
QWEN_PLUS_2025_12_01_INPUT_PER_1M_USD = 0.4
QWEN_PLUS_2025_12_01_OUTPUT_PER_1M_USD = 1.2
DEEPSEEK_CHAT_PRICE_URL = "https://api-docs.deepseek.com/quick_start/pricing"
DEEPSEEK_CHAT_INPUT_CACHE_HIT_PER_1M_USD = 0.028
DEEPSEEK_CHAT_INPUT_CACHE_MISS_PER_1M_USD = 0.28
DEEPSEEK_CHAT_OUTPUT_PER_1M_USD = 0.42
OPENAI_GPT_5_2_PRICE_URL = "https://developers.openai.com/api/docs/models/gpt-5.2"
OPENAI_GPT_5_2_INPUT_PER_1M_USD = 1.75
OPENAI_GPT_5_2_INPUT_CACHED_PER_1M_USD = 0.175
OPENAI_GPT_5_2_OUTPUT_PER_1M_USD = 14.0
OPENROUTER_CLAUDE_SONNET_4_5_PRICE_URL = "https://openrouter.ai/anthropic/claude-sonnet-4.5"
OPENROUTER_CLAUDE_SONNET_4_5_MODEL = "anthropic/claude-sonnet-4.5"
OPENROUTER_CLAUDE_SONNET_4_5_INPUT_PER_1M_USD = 3.0
OPENROUTER_CLAUDE_SONNET_4_5_OUTPUT_PER_1M_USD = 15.0
OPENROUTER_GEMINI_2_5_PRO_PRICE_URL = "https://openrouter.ai/google/gemini-2.5-pro"
OPENROUTER_GEMINI_2_5_PRO_INPUT_PER_1M_USD = 1.25
OPENROUTER_GEMINI_2_5_PRO_OUTPUT_PER_1M_USD = 10.0


def _abs_path(p: str) -> Path:
    pp = Path(p)
    if pp.is_absolute():
        return pp
    return (PROJECT_ROOT / pp).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_first_json_string_value(raw: str, *, key: str) -> str:
    m = re.search(rf'"{re.escape(key)}"\s*:', raw)
    if not m:
        raise RuntimeError(f"未在报告JSON中找到字段: {key}")
    pos = m.end()
    while pos < len(raw) and raw[pos] in " \t\r\n":
        pos += 1
    dec = json.JSONDecoder()
    val, _end = dec.raw_decode(raw[pos:])
    if not isinstance(val, str):
        raise RuntimeError(f"字段 {key} 不是字符串类型: {type(val)}")
    return val


def _parse_first_beijing_question(md_text: str) -> Dict[str, Any]:
    block_m = re.search(
        r"##\s*一、定位与定向（8题）.*?###\s*问题1\s*(.*?)(?:\n---|\Z)",
        md_text,
        flags=re.S,
    )
    if not block_m:
        raise RuntimeError("未在问题集里定位到“定位与定向/问题1”区块")
    block = block_m.group(1)

    q_m = re.search(r"\*\*题目\*\*:\s*(.+?)\s*(?:\n|$)", block)
    if not q_m:
        raise RuntimeError("未解析到题目文本")
    question_text = q_m.group(1).strip()

    options_m = re.search(r"\*\*选项\*\*:\s*(.*?)(?:\n\*\*正确答案\*\*|\Z)", block, flags=re.S)
    if not options_m:
        raise RuntimeError("未解析到选项区块")
    opts_block = options_m.group(1)
    options = [ln.strip()[1:].strip() for ln in opts_block.splitlines() if ln.strip().startswith("-")]
    if len(options) != 4:
        raise RuntimeError(f"选项数量不是4个，实际为{len(options)}个: {options}")

    ans_m = re.search(r"\*\*正确答案\*\*:\s*([ABCD])\b", block)
    if not ans_m:
        raise RuntimeError("未解析到正确答案字母")
    correct_answer = ans_m.group(1).strip().upper()

    return {
        "id": 1,
        "category": "定位与定向",
        "question": question_text,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": "",
        "difficulty": "medium",
    }


def _dashscope_usage_to_tokens(obj: Any) -> Tuple[int, int, int]:
    def _to_int(v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    usage = None
    if hasattr(obj, "usage"):
        usage = getattr(obj, "usage")
    if usage is None and hasattr(obj, "output") and hasattr(obj.output, "usage"):
        usage = obj.output.usage

    if usage is None:
        return 0, 0, 0

    if isinstance(usage, dict):
        if "input_tokens" in usage or "output_tokens" in usage:
            inp = _to_int(usage.get("input_tokens"))
            out = _to_int(usage.get("output_tokens"))
            tot = _to_int(usage.get("total_tokens")) or (inp + out)
            return inp, out, tot
        if "prompt_tokens" in usage or "completion_tokens" in usage:
            inp = _to_int(usage.get("prompt_tokens"))
            out = _to_int(usage.get("completion_tokens"))
            tot = _to_int(usage.get("total_tokens")) or (inp + out)
            return inp, out, tot
        return 0, 0, _to_int(usage.get("total_tokens"))

    inp = _to_int(getattr(usage, "input_tokens", 0)) or _to_int(getattr(usage, "prompt_tokens", 0))
    out = _to_int(getattr(usage, "output_tokens", 0)) or _to_int(getattr(usage, "completion_tokens", 0))
    tot = _to_int(getattr(usage, "total_tokens", 0)) or (inp + out)
    return inp, out, tot


def _openai_usage_to_tokens(obj: Any) -> Tuple[int, int, int, int]:
    def _to_int(v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    usage = getattr(obj, "usage", None)
    if usage is None:
        return 0, 0, 0, 0

    prompt_tokens = _to_int(getattr(usage, "prompt_tokens", 0) or (usage.get("prompt_tokens") if isinstance(usage, dict) else 0))
    completion_tokens = _to_int(
        getattr(usage, "completion_tokens", 0) or (usage.get("completion_tokens") if isinstance(usage, dict) else 0)
    )
    total_tokens = _to_int(getattr(usage, "total_tokens", 0) or (usage.get("total_tokens") if isinstance(usage, dict) else 0))

    cached_tokens = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is None and isinstance(usage, dict):
        details = usage.get("prompt_tokens_details")
    if details is not None:
        if isinstance(details, dict):
            cached_tokens = _to_int(details.get("cached_tokens"))
        else:
            cached_tokens = _to_int(getattr(details, "cached_tokens", 0))

    return prompt_tokens, completion_tokens, total_tokens, cached_tokens


@dataclass
class PriceSpec:
    input_per_1m: Optional[float]
    output_per_1m: Optional[float]
    currency: str
    pricing_url: Optional[str] = None
    input_cache_hit_per_1m: Optional[float] = None
    input_cache_miss_per_1m: Optional[float] = None
    billing_cache_mode: str = "no_cache"

    def cost(self, *, prompt_tokens: int, completion_tokens: int, cached_prompt_tokens: int = 0) -> Optional[float]:
        if self.input_per_1m is None or self.output_per_1m is None:
            return None
        if (
            self.billing_cache_mode == "auto"
            and self.input_cache_hit_per_1m is not None
            and self.input_cache_miss_per_1m is not None
            and cached_prompt_tokens > 0
        ):
            cached = max(0, int(cached_prompt_tokens))
            miss = max(0, int(prompt_tokens) - cached)
            return (
                (cached / 1_000_000.0) * float(self.input_cache_hit_per_1m)
                + (miss / 1_000_000.0) * float(self.input_cache_miss_per_1m)
                + (completion_tokens / 1_000_000.0) * float(self.output_per_1m)
            )
        return (prompt_tokens / 1_000_000.0) * float(self.input_per_1m) + (completion_tokens / 1_000_000.0) * float(self.output_per_1m)


class InstrumentedEvaluationAgent(EvaluationAgent):
    def __init__(self, *, price: PriceSpec) -> None:
        super().__init__()
        self.price = price
        self.usage_events: List[Dict[str, Any]] = []
        self._run_id = str(uuid4())
        self._current_phase: str = ""
        self.request_timeout_sec: float = 300.0

    async def _call_llm_with_meta(self, *, prompt: str, strategy: str, phase: str, temperature: float) -> str:
        self._current_phase = phase
        if (self.model_provider or "").startswith("qwen"):
            response = Generation.call(
                model=self.llm_config["model"],
                prompt=prompt,
                api_key=self.llm_config["api_key"],
                temperature=temperature,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"DashScope调用失败: status_code={response.status_code} message={getattr(response, 'message', '')}"
                )

            text = ""
            try:
                if response.output and getattr(response.output, "text", None):
                    text = response.output.text or ""
                elif response.output and getattr(response.output, "choices", None):
                    choices = response.output.choices or []
                    if choices:
                        msg = choices[0].message
                        if hasattr(msg, "content"):
                            text = msg.content or ""
                        elif isinstance(msg, dict):
                            text = msg.get("content", "") or ""
            except Exception:
                text = ""

            prompt_tokens, completion_tokens, total_tokens = _dashscope_usage_to_tokens(response)
            cached_tokens = 0
            provider = "qwen(dashscope)"
        else:
            client = AsyncOpenAI(
                api_key=self.llm_config["api_key"],
                base_url=self.llm_config.get("base_url"),
                timeout=float(self.request_timeout_sec),
            )
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.llm_config["model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                ),
                timeout=float(self.request_timeout_sec) + 5.0,
            )
            text = (resp.choices[0].message.content or "") if resp.choices else ""
            prompt_tokens, completion_tokens, total_tokens, cached_tokens = _openai_usage_to_tokens(resp)
            provider = str(self.model_provider or "openai_compatible")

        cost = self.price.cost(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cached_prompt_tokens=cached_tokens)
        self.usage_events.append(
            {
                "run_id": self._run_id,
                "provider": provider,
                "model": self.llm_config.get("model"),
                "strategy": strategy,
                "phase": phase,
                "temperature": temperature,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cached_prompt_tokens": cached_tokens,
                "cost": cost,
                "currency": self.price.currency if cost is not None else None,
            }
        )
        return text

    async def evaluate_one_question_four_strategies(self) -> Dict[str, Any]:
        if not self.questions:
            raise RuntimeError("未初始化 questions")
        if not isinstance(self.exploration_data, dict):
            raise RuntimeError("未初始化 exploration_data")

        q = self.questions[0]
        exploration_context = self.exploration_data.get("context_text") or ""
        context_mode = self.exploration_data.get("context_mode") or "text"
        rules_block = (self.exploration_data.get("prompt_rules") or "").strip()

        options_list = q.get("options") or []
        options_str = "\n".join([f"{chr(65 + j)}. {opt}" for j, opt in enumerate(options_list)])
        qtext = q.get("question") or ""

        base_tmpl = self._get_base_prompt_template(context_mode)
        base_prompt = base_tmpl.format(exploration_context=exploration_context, question=qtext, options=options_str)
        if not self.enable_explanation:
            base_prompt += (
                '\n\n输出要求（严格）：只输出一个大写字母作为答案（对应选项标签），不要输出"答案："前缀、不要输出解释、不要输出任何其他字符。'
            )
        if rules_block:
            base_prompt = f"附加规则（优先级最高）：\n{rules_block}\n\n" + base_prompt

        out: Dict[str, Any] = {}

        self.current_strategy = "Direct"
        resp = await self._call_llm_with_meta(prompt=base_prompt, strategy="Direct", phase="single", temperature=self.temperature)
        out["Direct"] = {"answer": self._extract_answer(resp), "raw": resp}

        self.current_strategy = "CoT"
        cot_prompt = base_prompt + "\n\nLet's think step by step."
        resp = await self._call_llm_with_meta(prompt=cot_prompt, strategy="CoT", phase="single", temperature=self.temperature)
        out["CoT"] = {"answer": self._extract_answer(resp), "raw": resp}

        self.current_strategy = "Self-Consistency"
        tasks = [
            self._call_llm_with_meta(prompt=cot_prompt, strategy="Self-Consistency", phase=f"sample_{i+1}", temperature=1.0)
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        valid_responses = [r for r in responses if isinstance(r, str)]
        extracted_answers = [self._extract_answer(r) for r in valid_responses if r.strip()]
        if extracted_answers:
            from collections import Counter

            vote_counts = Counter(extracted_answers)
            voted = vote_counts.most_common(1)[0][0]
        else:
            voted = "A"
        out["Self-Consistency"] = {"answer": voted, "raw": ""}

        self.current_strategy = "ToT"
        plan_prompt = self.tot_plan_prompt.format(exploration_context=exploration_context, question=qtext, options=options_str)
        plan = await self._call_llm_with_meta(prompt=plan_prompt, strategy="ToT", phase="plan", temperature=self.temperature)

        candidate_gen_prompt = base_prompt + f"\n\n请严格遵循以下推理计划进行思考：\n{plan}\n\nLet's think step by step."
        cand_tasks = [
            self._call_llm_with_meta(prompt=candidate_gen_prompt, strategy="ToT", phase=f"candidate_{i+1}", temperature=1.0)
            for i in range(3)
        ]
        cand_responses = await asyncio.gather(*cand_tasks, return_exceptions=True)
        valid_candidates = [r for r in cand_responses if isinstance(r, str) and r.strip()]
        candidates_text = ""
        for idx, cand in enumerate(valid_candidates, 1):
            candidates_text += f"候选答案 {idx}:\n{cand}\n{'-'*20}\n"

        select_prompt = self.tot_select_prompt.format(question=qtext, plan=plan, candidates=candidates_text)
        if not self.enable_explanation:
            select_prompt += (
                '\n\n输出要求（严格）：只输出一个大写字母作为答案（对应选项标签），不要输出"答案："前缀、不要输出解释、不要输出任何其他字符。'
            )
        selection = await self._call_llm_with_meta(prompt=select_prompt, strategy="ToT", phase="select", temperature=0.1)
        out["ToT"] = {"answer": self._extract_answer(selection), "raw": selection}

        return out


def _default_prompt_rules_text() -> str:
    return (
        "1. 方位角以地理正北为0°、顺时针递增\n"
        "2. 距离题用直线距离而非路径距离\n"
        "3. 仅引用上下文出现的实体/方向/距离；不引入外部常识\n"
        "4. 依据不足需在解释中明确说明\n"
    )


def _summarize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for e in events:
        s = e.get("strategy") or "unknown"
        if s not in out:
            out[s] = {
                "calls": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "cost_currency": None,
                "has_cost": True,
            }
        agg = out[s]
        agg["calls"] += 1
        agg["prompt_tokens"] += int(e.get("prompt_tokens") or 0)
        agg["completion_tokens"] += int(e.get("completion_tokens") or 0)
        agg["total_tokens"] += int(e.get("total_tokens") or 0)
        c = e.get("cost")
        if c is None:
            agg["has_cost"] = False
        else:
            agg["cost"] += float(c)
            agg["cost_currency"] = e.get("currency")
    for s, agg in out.items():
        if not agg.get("has_cost"):
            agg["cost"] = None
            agg["cost_currency"] = None
        agg.pop("has_cost", None)
    return out


def _write_csv(
    out_path: Path,
    *,
    meta: Dict[str, Any],
    usage_events: List[Dict[str, Any]],
    usage_summary_by_strategy: Dict[str, Any],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat()
    header = [
        "generated_at",
        "report_json",
        "question_md",
        "question_id",
        "question",
        "provider",
        "model",
        "strategy",
        "phase",
        "temperature",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_prompt_tokens",
        "input_price_per_1m",
        "input_cache_hit_per_1m",
        "input_cache_miss_per_1m",
        "output_price_per_1m",
        "currency",
        "pricing_url",
        "billing_cache_mode",
        "cost",
        "row_type",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()

        for e in usage_events:
            w.writerow(
                {
                    "generated_at": now,
                    "report_json": meta.get("report_json"),
                    "question_md": meta.get("question_md"),
                    "question_id": meta.get("question", {}).get("id"),
                    "question": meta.get("question", {}).get("question"),
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "strategy": e.get("strategy"),
                    "phase": e.get("phase"),
                    "temperature": e.get("temperature"),
                    "prompt_tokens": e.get("prompt_tokens"),
                    "completion_tokens": e.get("completion_tokens"),
                    "total_tokens": e.get("total_tokens"),
                    "cached_prompt_tokens": e.get("cached_prompt_tokens"),
                    "input_price_per_1m": meta.get("pricing", {}).get("input_per_1m"),
                    "input_cache_hit_per_1m": meta.get("pricing", {}).get("input_cache_hit_per_1m"),
                    "input_cache_miss_per_1m": meta.get("pricing", {}).get("input_cache_miss_per_1m"),
                    "output_price_per_1m": meta.get("pricing", {}).get("output_per_1m"),
                    "currency": meta.get("pricing", {}).get("currency"),
                    "pricing_url": meta.get("pricing", {}).get("pricing_url"),
                    "billing_cache_mode": meta.get("pricing", {}).get("billing_cache_mode"),
                    "cost": e.get("cost"),
                    "row_type": "event",
                }
            )

        for strategy, agg in usage_summary_by_strategy.items():
            w.writerow(
                {
                    "generated_at": now,
                    "report_json": meta.get("report_json"),
                    "question_md": meta.get("question_md"),
                    "question_id": meta.get("question", {}).get("id"),
                    "question": meta.get("question", {}).get("question"),
                    "provider": meta.get("provider"),
                    "model": meta.get("model"),
                    "strategy": strategy,
                    "phase": "",
                    "temperature": "",
                    "prompt_tokens": agg.get("prompt_tokens"),
                    "completion_tokens": agg.get("completion_tokens"),
                    "total_tokens": agg.get("total_tokens"),
                    "cached_prompt_tokens": "",
                    "input_price_per_1m": meta.get("pricing", {}).get("input_per_1m"),
                    "input_cache_hit_per_1m": meta.get("pricing", {}).get("input_cache_hit_per_1m"),
                    "input_cache_miss_per_1m": meta.get("pricing", {}).get("input_cache_miss_per_1m"),
                    "output_price_per_1m": meta.get("pricing", {}).get("output_per_1m"),
                    "currency": meta.get("pricing", {}).get("currency"),
                    "pricing_url": meta.get("pricing", {}).get("pricing_url"),
                    "billing_cache_mode": meta.get("pricing", {}).get("billing_cache_mode"),
                    "cost": agg.get("cost"),
                    "row_type": "summary",
                }
            )


async def _amain(args: argparse.Namespace) -> int:
    report_path = _abs_path(args.report_json)
    question_path = _abs_path(args.question_md)

    raw_report = _read_text(report_path)
    context_text = _extract_first_json_string_value(raw_report, key="context_text")

    md_text = _read_text(question_path)
    q = _parse_first_beijing_question(md_text)

    if not Config.DASHSCOPE_API_KEY:
        if str(args.model_provider).lower().startswith("qwen"):
            raise RuntimeError("未检测到 DASHSCOPE_API_KEY，请在项目根目录.env里配置")
    if not Config.DEEPSEEK_API_KEY:
        if str(args.model_provider).lower() == "deepseek":
            raise RuntimeError("未检测到 DEEPSEEK_API_KEY，请在项目根目录.env里配置")
    if not Config.OPENROUTER_API_KEY:
        if str(args.model_provider).lower() in {"claude", "gemini"}:
            raise RuntimeError("未检测到 OPENROUTER_API_KEY，请在项目根目录.env里配置")

    input_price_per_1m = float(args.input_price_per_1m) if args.input_price_per_1m is not None else None
    output_price_per_1m = float(args.output_price_per_1m) if args.output_price_per_1m is not None else None
    model_provider = str(args.model_provider or "qwen").lower().strip()
    currency = str(args.currency)
    pricing_url = str(args.pricing_url) if args.pricing_url else None
    billing_cache_mode = str(args.billing_cache_mode or "no_cache").strip().lower()
    if billing_cache_mode not in {"no_cache", "auto"}:
        billing_cache_mode = "no_cache"
    input_cache_hit_per_1m = None
    input_cache_miss_per_1m = None
    if input_price_per_1m is None and output_price_per_1m is None:
        if model_provider.startswith("qwen"):
            input_price_per_1m = QWEN_PLUS_2025_12_01_INPUT_PER_1M_USD
            output_price_per_1m = QWEN_PLUS_2025_12_01_OUTPUT_PER_1M_USD
            currency = "USD"
            pricing_url = QWEN_PLUS_2025_12_01_PRICE_URL
        elif model_provider == "deepseek":
            input_price_per_1m = DEEPSEEK_CHAT_INPUT_CACHE_MISS_PER_1M_USD
            output_price_per_1m = DEEPSEEK_CHAT_OUTPUT_PER_1M_USD
            input_cache_hit_per_1m = DEEPSEEK_CHAT_INPUT_CACHE_HIT_PER_1M_USD
            input_cache_miss_per_1m = DEEPSEEK_CHAT_INPUT_CACHE_MISS_PER_1M_USD
            currency = "USD"
            pricing_url = DEEPSEEK_CHAT_PRICE_URL
        elif model_provider in {"openai", "chatgpt"}:
            input_price_per_1m = OPENAI_GPT_5_2_INPUT_PER_1M_USD
            output_price_per_1m = OPENAI_GPT_5_2_OUTPUT_PER_1M_USD
            input_cache_hit_per_1m = OPENAI_GPT_5_2_INPUT_CACHED_PER_1M_USD
            input_cache_miss_per_1m = OPENAI_GPT_5_2_INPUT_PER_1M_USD
            currency = "USD"
            pricing_url = OPENAI_GPT_5_2_PRICE_URL
        elif model_provider == "claude":
            input_price_per_1m = OPENROUTER_CLAUDE_SONNET_4_5_INPUT_PER_1M_USD
            output_price_per_1m = OPENROUTER_CLAUDE_SONNET_4_5_OUTPUT_PER_1M_USD
            currency = "USD"
            pricing_url = OPENROUTER_CLAUDE_SONNET_4_5_PRICE_URL
        elif model_provider == "gemini":
            input_price_per_1m = OPENROUTER_GEMINI_2_5_PRO_INPUT_PER_1M_USD
            output_price_per_1m = OPENROUTER_GEMINI_2_5_PRO_OUTPUT_PER_1M_USD
            currency = "USD"
            pricing_url = OPENROUTER_GEMINI_2_5_PRO_PRICE_URL

    price = PriceSpec(
        input_per_1m=input_price_per_1m,
        output_per_1m=output_price_per_1m,
        currency=currency,
        pricing_url=pricing_url,
        input_cache_hit_per_1m=input_cache_hit_per_1m,
        input_cache_miss_per_1m=input_cache_miss_per_1m,
        billing_cache_mode=billing_cache_mode,
    )

    agent = InstrumentedEvaluationAgent(price=price)
    agent.request_timeout_sec = float(args.request_timeout_sec)
    agent.temperature = 0.1
    agent.model_provider = model_provider
    agent.enable_explanation = False

    await agent.initialize(
        questions=[q],
        exploration_data={
            "context_text": context_text,
            "context_mode": "text",
            "prompt_rules": _default_prompt_rules_text(),
        },
        model_provider=model_provider,
        strategies=["Direct", "CoT", "Self-Consistency", "ToT"],
    )
    if model_provider == "claude":
        agent.model_provider = "claude"
        agent.llm_config["api_key"] = Config.OPENROUTER_API_KEY
        agent.llm_config["base_url"] = "https://openrouter.ai/api/v1"
        agent.llm_config["model"] = OPENROUTER_CLAUDE_SONNET_4_5_MODEL

    if args.dry_run:
        print("dry_run=1：仅完成数据读取与题目解析，不实际调用模型。", flush=True)
        print(f"report_json: {str(report_path)}", flush=True)
        print(f"question_md: {str(question_path)}", flush=True)
        print(f"question_1: {q['question']}", flush=True)
        print(f"options: {q['options']}", flush=True)
        print(f"context_chars: {len(context_text)}", flush=True)
        return 0

    answers = await agent.evaluate_one_question_four_strategies()
    summary = _summarize_events(agent.usage_events)
    payload = {
        "report_json": str(report_path),
        "question_md": str(question_path),
        "question": q,
        "model": agent.llm_config.get("model"),
        "provider": agent.model_provider,
        "answers": answers,
        "usage_events": agent.usage_events,
        "usage_summary_by_strategy": summary,
        "pricing": {
            "input_per_1m": price.input_per_1m,
            "input_cache_hit_per_1m": price.input_cache_hit_per_1m,
            "input_cache_miss_per_1m": price.input_cache_miss_per_1m,
            "output_per_1m": price.output_per_1m,
            "currency": price.currency,
            "pricing_url": price.pricing_url,
            "billing_cache_mode": price.billing_cache_mode,
        },
    }

    if args.out_json:
        out_path = _abs_path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out_csv:
        csv_path = _abs_path(args.out_csv)
    else:
        safe_provider = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(agent.model_provider or "model"))
        safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(agent.llm_config.get("model") or "unknown"))
        csv_path = _abs_path(f".\\{safe_provider}_{safe_model}_beijing_q1_token_cost.csv")
    if csv_path:
        _write_csv(
            csv_path,
            meta=payload,
            usage_events=agent.usage_events,
            usage_summary_by_strategy=payload["usage_summary_by_strategy"],
        )

    print(json.dumps(payload["usage_summary_by_strategy"], ensure_ascii=False, indent=2), flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_provider", default="qwen")
    ap.add_argument(
        "--report_json",
        default=r"txt_statistics\大模型空间认知项目数据\3三种提问方式\三提问方式结果\三提问方式报告无原始记忆结果报告1\评估报告_北京天安门_qwen_context_report.txt.json",
    )
    ap.add_argument(
        "--question_md",
        default=r"txt_statistics\大模型空间认知项目数据\8问题集\北京天安门_AI探索评估-22题完整问题集.md",
    )
    ap.add_argument("--input_price_per_1m", default=None)
    ap.add_argument("--output_price_per_1m", default=None)
    ap.add_argument("--currency", default="RMB")
    ap.add_argument("--pricing_url", default=None)
    ap.add_argument("--billing_cache_mode", default="no_cache")
    ap.add_argument("--request_timeout_sec", default="300")
    ap.add_argument("--out_json", default=None)
    ap.add_argument("--out_csv", default=None)
    ap.add_argument("--dry_run", action="store_true", default=False)

    args = ap.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())

