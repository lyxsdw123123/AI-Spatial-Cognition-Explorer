
from typing import Any, List, Optional, Dict, Iterator, AsyncIterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ChatMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.pydantic_v1 import Field, SecretStr, PrivateAttr
from zhipuai import ZhipuAI
import os

class CustomChatZhipuAI(BaseChatModel):
    """
    Custom ChatModel for ZhipuAI using the official SDK (v4+).
    This bypasses langchain-community's implementation which might have compatibility issues.
    """
    
    api_key: Optional[str] = Field(default=None, alias="api_key")
    model_name: str = Field(default="glm-4", alias="model")
    temperature: float = 0.7
    top_p: float = 0.7
    
    _client: Any = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.api_key:
            self.api_key = os.environ.get("ZHIPUAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("ZhipuAI API Key not found. Please set ZHIPUAI_API_KEY environment variable or pass it to the constructor.")
            
        self._client = ZhipuAI(api_key=self.api_key)

    @property
    def _llm_type(self) -> str:
        return "zhipuai-custom"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        zhipu_messages = self._convert_messages(messages)
        
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=zhipu_messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=stop,
            stream=False,
            **kwargs
        )
        
        content = response.choices[0].message.content
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        zhipu_messages = self._convert_messages(messages)
        
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=zhipu_messages,
            temperature=self.temperature,
            top_p=self.top_p,
            stop=stop,
            stream=True,
            **kwargs
        )
        
        for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield ChatGenerationChunk(message=AIMessage(content=delta))
                    if run_manager:
                        run_manager.on_llm_new_token(delta)

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        zhipu_messages = []
        for message in messages:
            role = "user"
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            elif isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, ChatMessage):
                role = message.role
            
            zhipu_messages.append({"role": role, "content": message.content})
        return zhipu_messages
