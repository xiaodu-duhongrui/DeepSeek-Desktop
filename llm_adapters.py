from typing import Dict, Any, Optional
import httpx
from dataclasses import dataclass
from enum import Enum

class LLMProvider(Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"

@dataclass
class LLMConfig:
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

class LLMAdapter:
    """统一的多模型服务适配器"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = self._initialize_client()
        
    def _initialize_client(self):
        """根据配置初始化客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            from openai import OpenAI
            return OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        elif self.config.provider == LLMProvider.GEMINI:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            return genai
        elif self.config.provider == LLMProvider.ANTHROPIC:
            import anthropic
            return anthropic.Anthropic(api_key=self.config.api_key)
        elif self.config.provider == LLMProvider.OLLAMA:
            return httpx.Client(base_url=self.config.base_url or "http://localhost:11434")
        else:
            raise ValueError(f"Unsupported provider: {self.config.provider}")
    
    async def chat_completion(self, messages: list[dict], stream: bool = False):
        """统一聊天补全接口"""
        if self.config.provider == LLMProvider.OPENAI:
            return await self._openai_chat(messages, stream)
        elif self.config.provider == LLMProvider.GEMINI:
            return await self._gemini_chat(messages)
        elif self.config.provider == LLMProvider.ANTHROPIC:
            return await self._anthropic_chat(messages, stream)
        elif self.config.provider == LLMProvider.OLLAMA:
            return await self._ollama_chat(messages, stream)
    
    async def _openai_chat(self, messages: list[dict], stream: bool):
        """处理OpenAI风格API调用"""
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            stream=stream,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        return response
    
    async def _gemini_chat(self, messages: list[dict]):
        """处理Gemini API调用"""
        model = self.client.GenerativeModel(self.config.model)
        chat = model.start_chat()
        response = await chat.send_message(messages[-1]["content"])
        return response.text
    
    async def _anthropic_chat(self, messages: list[dict], stream: bool):
        """处理Anthropic API调用"""
        message = self.client.messages.create(
            model=self.config.model,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=stream
        )
        return message
    
    async def _ollama_chat(self, messages: list[dict], stream: bool):
        """处理Ollama本地模型调用"""
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
        }
        response = await self.client.post("/api/chat", json=payload)
        return response.json()