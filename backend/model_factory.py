from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi
from config.config import Config
import json
from typing import Any

# Monkey Patch ChatTongyi to fix streaming issues with Qwen3
def safe_subtract_client_response(self, resp: Any, prev_resp: Any) -> Any:
    """Monkey patched subtract_client_response to handle None values safely."""
    try:
        resp_copy = json.loads(json.dumps(resp))
        choice = resp_copy["output"]["choices"][0]
        message = choice["message"]

        prev_resp_copy = json.loads(json.dumps(prev_resp))
        prev_choice = prev_resp_copy["output"]["choices"][0]
        prev_message = prev_choice["message"]

        if message.get("content") and prev_message.get("content"):
            message["content"] = message["content"].replace(prev_message["content"], "")

        if message.get("tool_calls"):
            for index, tool_call in enumerate(message["tool_calls"]):
                function = tool_call["function"]

                if prev_message.get("tool_calls") and len(prev_message["tool_calls"]) > index:
                    prev_function = prev_message["tool_calls"][index]["function"]
                    
                    # Safe replace for name
                    curr_name = function.get("name")
                    prev_name = prev_function.get("name")
                    if curr_name and prev_name:
                        function["name"] = curr_name.replace(prev_name, "")
                    
                    # Safe replace for arguments
                    curr_args = function.get("arguments")
                    prev_args = prev_function.get("arguments")
                    if curr_args and prev_args:
                        function["arguments"] = curr_args.replace(prev_args, "")
                        
        return resp_copy
    except Exception as e:
        # If anything goes wrong in subtraction, just return the current response
        # This prevents crashing on malformed/unexpected chunks
        return resp

# Apply the patch
ChatTongyi.subtract_client_response = safe_subtract_client_response

class ModelFactory:
    """
    模型工厂类
    负责创建和配置不同的 LLM 模型实例
    统一了接口，屏蔽了不同模型提供商的差异
    """
    
    @staticmethod
    def create_model(provider: str):
        provider = provider.lower()
        
        # 统一配置参数
        common_kwargs = {"temperature": 0.7}
        
        if provider == "qwen":
            if not Config.DASHSCOPE_API_KEY:
                 raise ValueError("DashScope API Key is missing. Please configure DASHSCOPE_API_KEY.")
            return ChatTongyi(
                dashscope_api_key=Config.DASHSCOPE_API_KEY,
                model_name="qwen-max-latest", # or qwen-max
                **common_kwargs
            )
            
        elif provider == "openai" or provider == "chatgpt":
            if not Config.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key is missing. Please configure OPENAI_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.OPENAI_API_KEY,
                model_name="gpt-5.2",
                **common_kwargs
            )
            
        elif provider == "deepseek":
            if not Config.DEEPSEEK_API_KEY:
                raise ValueError("DeepSeek API Key is missing. Please configure DEEPSEEK_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.DEEPSEEK_API_KEY,
                openai_api_base="https://api.deepseek.com",
                model_name="deepseek-chat",
                **common_kwargs
            )
            
        elif provider == "claude":
            if not Config.OPENROUTER_API_KEY:
                 raise ValueError("OpenRouter API Key is missing. Please configure OPENROUTER_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                model_name="anthropic/claude-sonnet-4.5",
                **common_kwargs
            )
            
        elif provider == "gemini":
            if not Config.OPENROUTER_API_KEY:
                 raise ValueError("OpenRouter API Key is missing. Please configure OPENROUTER_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                model_name="google/gemini-2.5-pro",
                **common_kwargs
            )
            
        elif provider == "zhipu":
            if not Config.OPENROUTER_API_KEY:
                 raise ValueError("OpenRouter API Key is missing. Please configure OPENROUTER_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                model_name="z-ai/glm-4.6",
                **common_kwargs
            )

        elif provider.startswith("qwen3"):
            if not Config.DASHSCOPE_API_KEY:
                 raise ValueError("DashScope API Key is missing. Please configure DASHSCOPE_API_KEY.")
            return ChatTongyi(
                dashscope_api_key=Config.DASHSCOPE_API_KEY,
                model_name=provider,
                streaming=False, # Ensure streaming is False
                model_kwargs={"enable_thinking": False},
                **common_kwargs
            )
            
        else:
            raise ValueError(f"Unknown model provider: {provider}. Supported: qwen, deepseek, openai, claude, gemini, zhipu, qwen3-*")
