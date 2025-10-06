from datetime import datetime
from typing import Optional
from PySide6.QtCore import QThread, Signal
from .llm_adapters import LLMAdapter, LLMConfig, LLMProvider
from .token_calculator import TokenCalculator
from .api_key_manager import DEFAULT_BASE_URL

class APIWorker(QThread):
    """API调用工作线程"""
    response_received = Signal(str, dict)
    stream_chunk_received = Signal(str, str)
    error_occurred = Signal(str)
    finished_signal = Signal()
    progress_updated = Signal(str)
    token_usage_updated = Signal(int, int, int)  # 输入token, 输出token, 总token
    thinking_process_updated = Signal(str)  # 新增：思考过程更新信号
    
    def __init__(self, api_key, messages, model="deepseek-chat", stream=False, 
                 base_url=DEFAULT_BASE_URL, provider: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.messages = messages
        self.model = model
        self.stream = stream
        self.base_url = base_url
        self.start_time = None
        self.token_calculator = TokenCalculator()
        self.is_reasoner_model = "reasoner" in model.lower()
        
        # 确定LLM提供商
        if provider:
            self.provider = LLMProvider(provider.lower())
        elif "deepseek" in model.lower():
            self.provider = LLMProvider.DEEPSEEK
        elif "gpt" in model.lower():
            self.provider = LLMProvider.OPENAI
        elif "gemini" in model.lower():
            self.provider = LLMProvider.GEMINI
        elif "claude" in model.lower():
            self.provider = LLMProvider.ANTHROPIC
        else:
            self.provider = LLMProvider.OPENAI  # 默认
        
    def run(self):
        try:
            self.start_time = datetime.now()
            
            # 初始化LLM适配器
            config = LLMConfig(
                provider=self.provider,
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model
            )
            adapter = LLMAdapter(config)
            
            if self.stream:
                self.stream_response(adapter)
            else:
                self.normal_response(adapter)
                
        except Exception as e:
            self.error_occurred.emit(f"API调用错误: {str(e)}")
        finally:
            self.finished_signal.emit()
    
    def normal_response(self, adapter):
        """正常响应模式"""
        self.progress_updated.emit("正在与AI对话...")
        response = adapter.chat_completion(self.messages, stream=False)
        
        # 处理不同模型的响应格式
        if self.provider == LLMProvider.OPENAI or self.provider == LLMProvider.DEEPSEEK:
            content = response.choices[0].message.content
            model_name = response.model
        elif self.provider == LLMProvider.GEMINI:
            content = response
            model_name = self.model
        elif self.provider == LLMProvider.ANTHROPIC:
            content = response.content[0].text
            model_name = self.model
        else:
            content = str(response)
            model_name = self.model
        
        # 计算token使用量
        input_tokens = self.token_calculator.calculate_messages_tokens(self.messages)
        output_tokens = self.token_calculator.calculate_tokens(content)
        total_tokens = input_tokens + output_tokens
        
        metadata = {
            "model": model_name,
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            },
            "created": int(datetime.now().timestamp())
        }
        
        self.response_received.emit(content, metadata)
        self.token_usage_updated.emit(input_tokens, output_tokens, total_tokens)
    
    def stream_response(self, adapter):
        """流式响应模式"""
        self.progress_updated.emit("开始流式响应...")
        response = adapter.chat_completion(self.messages, stream=True)
        
        full_content = ""
        thinking_content = ""  # 用于累积思考过程
        chunk_count = 0
        
        # 计算输入token
        input_tokens = self.token_calculator.calculate_messages_tokens(self.messages)
        
        if self.provider == LLMProvider.OPENAI or self.provider == LLMProvider.DEEPSEEK:
            # 处理OpenAI/DEEPSEEK风格的流式响应
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    
                    # 处理思考过程
                    if self.is_reasoner_model and hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        thinking_chunk = delta.reasoning_content
                        thinking_content += thinking_chunk
                        chunk_count += 1
                        self.thinking_process_updated.emit(thinking_chunk)
                        self._emit_chunk(f"[思考] {thinking_chunk}", chunk_count)
                        continue
                    
                    # 处理普通内容
                    if hasattr(delta, 'content') and delta.content:
                        content_chunk = delta.content
                        full_content += content_chunk
                        chunk_count += 1
                        self._emit_chunk(content_chunk, chunk_count)
                        
        elif self.provider == LLMProvider.ANTHROPIC:
            # 处理Anthropic风格的流式响应
            for chunk in response:
                if chunk.event == "content_block_delta":
                    content_chunk = chunk.delta.text
                    full_content += content_chunk
                    chunk_count += 1
                    self._emit_chunk(content_chunk, chunk_count)
                    
        elif self.provider == LLMProvider.OLLAMA:
            # 处理Ollama风格的流式响应
            for chunk in response:
                if chunk.get("message"):
                    content_chunk = chunk["message"]["content"]
                    full_content += content_chunk
                    chunk_count += 1
                    self._emit_chunk(content_chunk, chunk_count)
        
        # 计算输出token（包括思考过程和最终回答）
        output_tokens = self.token_calculator.calculate_tokens(full_content + thinking_content)
        total_tokens = input_tokens + output_tokens
        
        metadata = {
            "model": self.model,
            "stream": True,
            "created": int(datetime.now().timestamp()),
            "chunks_received": chunk_count,
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            },
            "thinking_content": thinking_content  # 包含思考过程
        }
        
        self.response_received.emit(full_content, metadata)
        self.token_usage_updated.emit(input_tokens, output_tokens, total_tokens)
    
    def _emit_chunk(self, content_chunk, chunk_count):
        """发送数据块并更新进度"""
        current_time = datetime.now()
        time_diff = current_time - self.start_time
        timestamp = f"{time_diff.seconds}.{time_diff.microseconds // 100000:01d}"
        
        if chunk_count % 5 == 0:
            self.progress_updated.emit(f"已接收 {chunk_count} 个数据块...")
        
        self.stream_chunk_received.emit(content_chunk, timestamp)