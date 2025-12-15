# 评估API模块

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime

from backend.evaluation_agent import EvaluationAgent
from backend.question_generator import EvaluationQuestions
import os

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

# 全局评估代理实例
evaluation_agent = EvaluationAgent()

# 数据模型
class QuestionModel(BaseModel):
    question: str
    type: str
    options: List[str]
    correct_answer: str
    explanation: Optional[str] = None

class ExplorationDataModel(BaseModel):
    ai_location: List[float]
    exploration_path: List[List[float]]
    visited_pois: List[Dict[str, Any]]
    exploration_report: Optional[Dict[str, Any]] = None
    road_memory: Optional[Dict[str, Any]] = None
    new_exploration_data: Optional[Dict[str, Any]] = None
    context_text: Optional[str] = None
    context_mode: Optional[str] = None
    prompt_rules: Optional[str] = None

class EvaluationRequestModel(BaseModel):
    questions: List[Dict[str, Any]]
    exploration_data: ExplorationDataModel
    model_provider: str = "qwen"
    strategies: Optional[List[str]] = None

@router.post("/start")
async def start_evaluation(request: EvaluationRequestModel):
    """开始AI评估（异步模式）"""
    try:
        # 初始化评估代理
        # 仅传递纯文本上下文，切断除上下文外的所有探索数据
        ctx = request.exploration_data.context_text or ""
        mode = (request.exploration_data.context_mode or "").strip().lower()

        # 优先使用后端缓存的最新上下文，确保与停止探索时生成的上下文完全一致
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:8000/exploration/context") as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        if isinstance(payload, dict) and payload.get("success"):
                            data = payload.get("data") or {}
                            cached_ctx = data.get("context_text")
                            cached_mode = (data.get("context_mode") or "").strip().lower()
                            if isinstance(cached_ctx, str) and cached_ctx.strip():
                                ctx = cached_ctx
                                if cached_mode:
                                    mode = cached_mode
        except Exception:
            pass

        # 按记忆模式统一上下文格式
        import aiohttp
        if mode == 'raw' and (not ctx or not ctx.strip()):
            # Raw模式下通常不需要额外的格式化，因为它是纯文本日志
            # 但如果上下文为空，我们无法在这里恢复它，因为我们无法访问explorer_agent实例
            # 依赖于前端传递或者后端在start_evaluation前已经准备好
            pass

        if mode in ('map', 'graph') and (not ctx or not ctx.strip()):
            async with aiohttp.ClientSession() as session:
                if mode == 'map':
                    snap = None
                    try:
                        async with session.get("http://127.0.0.1:8000/memory/map") as resp:
                            if resp.status == 200:
                                payload = await resp.json()
                                if isinstance(payload, dict) and payload.get("success"):
                                    snap = payload.get("data")
                    except Exception:
                        snap = None
                    try:
                        lines = []
                        nodes = (snap or {}).get('nodes') or []
                        grid = (snap or {}).get('road_grid') or {}
                        cells = grid.get('cells') or []
                        lines.append("# 第三种记忆map描述")
                        lines.append("## 节点列表")
                        lines.append("NODE[id,类型,附加属性，ij坐标]")
                        for nd in nodes[:200]:
                            cid = nd.get('id')
                            nm = nd.get('name')
                            tp = nd.get('type')
                            ii = int(nd.get('i') or 0)
                            jj = int(nd.get('j') or 0)
                            lines.append(f"NODE[{cid},{tp},name={nm}，（{ii}，{jj}）]")
                        lines.append("")
                        lines.append("## 道路列表")
                        lines.append("ROAD[道路坐标]")
                        for c in cells[:400]:
                            ii = int(c.get('i') or 0)
                            jj = int(c.get('j') or 0)
                            lines.append(f"ROAD[（{ii}，{jj}）]")
                        ctx = "\n".join(lines)
                    except Exception:
                        pass
                if mode == 'graph':
                    snap = None
                    try:
                        async with session.get("http://127.0.0.1:8000/memory/graph") as resp:
                            if resp.status == 200:
                                payload = await resp.json()
                                if isinstance(payload, dict) and payload.get("success"):
                                    snap = payload.get("data")
                    except Exception:
                        snap = None
                    try:
                        lines = []
                        nodes = (snap or {}).get('nodes') or []
                        edges = (snap or {}).get('edges') or []
                        lines.append("# 第二种记忆graph描述")
                        lines.append("## 节点列表")
                        lines.append("NODE[id,类型]")
                        for nd in nodes[:200]:
                            cid = nd.get('id')
                            tp = nd.get('type')
                            lines.append(f"NODE[{cid},{tp}]")
                        lines.append("")
                        lines.append("## 边列表")
                        lines.append("EDGE[起点ID,终点ID,道路长度]")
                        for e in edges[:400]:
                            f = e.get('from_id')
                            t = e.get('to_id')
                            lm = int(e.get('length_m') or 0)
                            lines.append(f"EDGE[{f},{t},{lm}m]")
                        ctx = "\n".join(lines)
                    except Exception:
                        pass
        try:
            lines = (ctx.splitlines() if isinstance(ctx, str) else [])
            # 过滤未命名路点（如“路点_<lat>_<lng>”）
            try:
                lines = [ln for ln in lines if not (ln.strip().startswith("→ 路点_") or ln.strip().startswith("- 路点_"))]
                ctx = "\n".join(lines)
            except Exception:
                pass
            preview = "\n".join(lines[:10])
            print("\n" + "="*48, flush=True)
            print("开始评估-上下文预览(前10行)", flush=True)
            print("="*48, flush=True)
            print(preview if preview else "[空上下文]", flush=True)
            print("="*48 + "\n", flush=True)
        except Exception:
            pass
        prompt_rules = request.exploration_data.prompt_rules or ""
        if not prompt_rules:
            if mode == 'graph':
                prompt_rules = (
                    "1. 方位角以地理正北为0°、顺时针递增\n"
                    "2. NODE[id,类型]，EDGE[起点ID,终点ID,道路长度m]；仅在给定节点与边集合内推理\n"
                    "3. 路径比较以length_m累加最小为准；并列按边数最少\n"
                    "4. 禁止引入未出现的连接或节点；仅用上下文提供的关系\n"
                )
            elif mode == 'map':
                prompt_rules = (
                    "1. 方位角以地理正北为0°、顺时针递增\n"
                    "2. 坐标系：i向北递增、j向东递增；ROAD为cells的上下左右邻接序列\n"
                    "3. 距离近似：|Δi|、|Δj|×grid_cell_size_m；路径为步数×grid_cell_size_m\n"
                    "4. 解释首行标注grid_size=<数值>米（若未提供则写未提供）；不得引入未出现字段\n"
                )
            elif mode == 'raw':
                prompt_rules = (
                    "1. 这是AI探索者与环境交互的原始日志（Raw Log），包含用户的指令、AI的思考过程(Thought)、工具调用(Action)和工具返回结果(Observation)。\n"
                    "2. 请通过阅读这些日志来还原AI的探索路径和所见所闻。\n"
                    "3. 关注日志中的 'Found ... visible POIs' (视野感知) 和 'Successfully moved to ...' (移动行为) 等关键信息。\n"
                    "4. 仅依据日志内容回答问题，不要引入外部知识。\n"
                )
            else:
                prompt_rules = (
                    "1. 方位角以地理正北为0°、顺时针递增\n"
                    "2. 距离题用直线距离而非路径距离\n"
                    "3. 仅引用上下文出现的实体/方向/距离；不引入外部常识\n"
                    "4. 依据不足需在解释中明确说明\n"
                )
        await evaluation_agent.initialize(
            questions=request.questions,
            exploration_data={"context_text": ctx, "context_mode": mode, "prompt_rules": prompt_rules},
            model_provider=request.model_provider,
            strategies=request.strategies
        )
        
        # 异步启动评估过程，不等待完成
        asyncio.create_task(evaluation_agent.start_evaluation())
        
        return {
            "success": True,
            "message": "评估已开始",
            "evaluation_id": evaluation_agent.evaluation_id,
            "status": "started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动评估失败: {str(e)}")

@router.get("/status")
async def get_evaluation_status():
    """获取评估状态"""
    try:
        status = evaluation_agent.get_status()
        return {
            "success": True,
            "status": status["status"],
            "progress": status.get("progress", 0),
            "current_question": status.get("current_question", 0),
            "total_questions": status.get("total_questions", 0),
            "error": status.get("error")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评估状态失败: {str(e)}")

@router.get("/result")
async def get_evaluation_result():
    """获取评估结果"""
    try:
        result = evaluation_agent.get_result()
        
        if not result:
            raise HTTPException(status_code=404, detail="评估结果不存在或未完成")
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评估结果失败: {str(e)}")

@router.post("/regenerate_md")
async def regenerate_markdown(regions: Optional[List[str]] = None):
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(project_root, 'data')
        targets = regions if regions else [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        outputs = []
        for region in targets:
            try:
                eq = EvaluationQuestions(region)
                path = eq.save_markdown()
                outputs.append({"region": region, "path": path})
            except Exception as e:
                outputs.append({"region": region, "error": str(e)})
        return {"success": True, "outputs": outputs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重生成评估MD失败: {str(e)}")

@router.post("/reset")
async def reset_evaluation():
    """重置评估状态"""
    try:
        evaluation_agent.reset()
        return {
            "success": True,
            "message": "评估状态已重置"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置评估失败: {str(e)}")
