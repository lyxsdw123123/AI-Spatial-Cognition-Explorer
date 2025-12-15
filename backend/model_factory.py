from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi
from backend.custom_zhipu import CustomChatZhipuAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from config.config import Config

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
                model_name="qwen-turbo", # or qwen-max
                **common_kwargs
            )
            
        elif provider == "openai" or provider == "chatgpt":
            if not Config.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key is missing. Please configure OPENAI_API_KEY.")
            return ChatOpenAI(
                openai_api_key=Config.OPENAI_API_KEY,
                model_name="gpt-4o",
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
            if not Config.ANTHROPIC_API_KEY:
                 raise ValueError("Anthropic API Key is missing. Please configure ANTHROPIC_API_KEY.")
            return ChatAnthropic(
                anthropic_api_key=Config.ANTHROPIC_API_KEY,
                model_name="claude-3-sonnet-20240229",
                **common_kwargs
            )
            
        elif provider == "gemini":
            if not Config.GOOGLE_API_KEY:
                 raise ValueError("Google API Key is missing. Please configure GOOGLE_API_KEY.")
            return ChatGoogleGenerativeAI(
                google_api_key=Config.GOOGLE_API_KEY,
                model="gemini-pro",
                convert_system_message_to_human=True, # 解决一些模型对System Message支持的问题
                **common_kwargs
            )
            
        elif provider == "zhipu":
            if not Config.ZHIPUAI_API_KEY:
                 raise ValueError("ZhipuAI API Key is missing. Please configure ZHIPUAI_API_KEY.")
            return CustomChatZhipuAI(
                api_key=Config.ZHIPUAI_API_KEY,
                model_name="glm-4",
                **common_kwargs
            )
            
        else:
            raise ValueError(f"Unknown model provider: {provider}. Supported: qwen, deepseek, openai, claude, gemini, zhipu")
