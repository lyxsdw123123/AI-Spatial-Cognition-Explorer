# 集成智谱、Gemini 和 Claude 模型计划 (修正版)

您说得对，智谱确实有官方的 Python SDK 和 LangChain 适配器。为了确保最佳的兼容性和功能支持，我们将使用各自官方推荐的专用库进行集成。

## 具体实施步骤

### 1. 安装依赖
我们将安装三个模型对应的官方支持库：
*   **智谱**: `zhipuai` (将在代码中使用 `ChatZhipuAI`)
*   **Gemini**: `langchain-google-genai`
*   **Claude**: `langchain-anthropic`

### 2. 更新配置文件
*   **`.env`**: 添加 `ZHIPUAI_API_KEY` (注意智谱官方通常用这个变量名), `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`。
*   **`config/config.py`**: 增加相应的配置项读取。

### 3. 修改后端逻辑 (`backend/agent.py` & `evaluation_agent.py`)
我们将分别引入各自的 LangChain 专用类，确保代码结构清晰：

*   **智谱 (Zhipu)**:
    *   引入: `from langchain_community.chat_models import ChatZhipuAI`
    *   模型: `glm-4`

*   **Gemini**:
    *   引入: `from langchain_google_genai import ChatGoogleGenerativeAI`
    *   模型: `gemini-pro`

*   **Claude**:
    *   引入: `from langchain_anthropic import ChatAnthropic`
    *   模型: `claude-3-opus-20240229` (或 Sonnet)

同时，我会重构 `EvaluationAgent`，使其统一通过 LangChain 接口调用这些模型，避免手写不同的 HTTP 请求逻辑。

### 4. 修改前端界面 (`frontend/app.py`)
*   更新下拉菜单，支持选择：通义千问, DeepSeek, ChatGPT, 智谱GLM-4, Gemini, Claude 3。

这样每个模型都将使用其最原生、最稳定的连接方式。请确认执行？
