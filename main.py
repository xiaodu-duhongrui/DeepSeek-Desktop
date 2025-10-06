import sys
import os
import json
import markdown
import tempfile
import mimetypes
import base64
import re
import hashlib
from datetime import datetime
from threading import Thread
from queue import Queue
import secrets
from typing import Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QTextEdit, QLineEdit, QPushButton, QListWidget, 
                             QListWidgetItem, QSplitter, QTabWidget, QLabel, 
                             QFileDialog, QMessageBox, QProgressBar, QComboBox,
                             QCheckBox, QSlider, QToolBar, QStatusBar, QMenu,
                             QScrollArea, QFrame, QSizePolicy, QGroupBox, QTreeWidget,
                             QTreeWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
                             QFormLayout, QSpinBox, QDoubleSpinBox, QSystemTrayIcon,
                             QInputDialog, QProgressDialog, QStyle, QStackedWidget)
from PySide6.QtCore import (Qt, QThread, Signal, QPropertyAnimation, QEasingCurve, 
                         QTimer, QSize, QPoint, QSettings, QMimeData, QUrl, QDateTime)
from PySide6.QtGui import (QFont, QPalette, QColor, QTextCharFormat, QSyntaxHighlighter, 
                        QKeySequence, QIcon, QPixmap, QTextCursor, QDrag, QTextDocument,
                        QFontMetrics, QPainter, QPen, QLinearGradient, QAction,
                        QGuiApplication)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from openai import OpenAI
from src.assistant_dialog import AssistantDialog
from src.assistant_manager import AssistantManager

# API配置
DEFAULT_BASE_URL = "https://api.deepseek.com"

class SecureAPIKeyManager:
    """安全的API密钥管理器 - 使用AES加密存储"""
    
    def __init__(self):
        self.settings = QSettings("DeepSeek", "AI Client")
        self.encryption_key = self._get_or_create_encryption_key()
    
    def _get_or_create_encryption_key(self):
        """获取或创建加密密钥"""
        # 尝试从设置中获取加密密钥
        encrypted_key = self.settings.value("encryption_key")
        
        if encrypted_key:
            try:
                # 解密加密密钥（使用设备特定的密钥）
                return self._decrypt_with_device_key(encrypted_key)
            except Exception:
                # 如果解密失败，创建新的加密密钥
                pass
        
        # 创建新的加密密钥
        new_key = secrets.token_bytes(32)  # AES-256
        encrypted_new_key = self._encrypt_with_device_key(new_key)
        self.settings.setValue("encryption_key", encrypted_new_key)
        return new_key
    
    def _get_device_fingerprint(self):
        """生成设备特定的指纹，用于派生加密密钥"""
        # 使用多种设备特定信息创建指纹
        device_info = ""
        
        # 用户名
        try:
            import getpass
            device_info += getpass.getuser()
        except:
            pass
        
        # 机器名
        try:
            import socket
            device_info += socket.gethostname()
        except:
            pass
        
        # 应用程序特定信息
        device_info += "DeepSeek_AIClient_v1.0"
        
        # 创建SHA256哈希
        return hashlib.sha256(device_info.encode()).digest()
    
    def _encrypt_with_device_key(self, data):
        """使用设备密钥加密数据"""
        device_key = self._get_device_fingerprint()
        iv = secrets.token_bytes(16)  # AES块大小
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(device_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return base64.b64encode(iv + ciphertext).decode()
    
    def _decrypt_with_device_key(self, encrypted_data):
        """使用设备密钥解密数据"""
        try:
            device_key = self._get_device_fingerprint()
            data = base64.b64decode(encrypted_data)
            iv = data[:16]
            ciphertext = data[16:]
            
            cipher = Cipher(algorithms.AES(device_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            unpadder = padding.PKCS7(128).unpadder()
            original_data = unpadder.update(padded_data) + unpadder.finalize()
            return original_data
        except Exception as e:
            raise ValueError("解密失败，可能是设备环境变化") from e
    
    def _encrypt_api_key(self, api_key):
        """加密API密钥"""
        iv = secrets.token_bytes(16)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(api_key.encode('utf-8')) + padder.finalize()
        
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        return base64.b64encode(iv + ciphertext).decode()
    
    def _decrypt_api_key(self, encrypted_api_key):
        """解密API密钥"""
        try:
            data = base64.b64decode(encrypted_api_key)
            iv = data[:16]
            ciphertext = data[16:]
            
            cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            unpadder = padding.PKCS7(128).unpadder()
            decrypted = unpadder.update(padded_data) + unpadder.finalize()
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError("API密钥解密失败") from e
    
    def store_api_key(self, api_key):
        """安全地存储API密钥"""
        if not api_key:
            return False
        
        try:
            # 加密API密钥
            encrypted_key = self._encrypt_api_key(api_key)
            
            # 存储加密后的密钥
            self.settings.setValue("api_key_encrypted", encrypted_key)
            
            # 同时存储密钥哈希用于验证
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            self.settings.setValue("api_key_hash", key_hash)
            
            # 清除任何可能存在的明文存储
            self.settings.remove("api_key")
            self.settings.remove("api_key_plain")
            
            self.settings.sync()
            return True
        except Exception as e:
            print(f"存储API密钥时出错: {e}")
            return False
    
    def get_api_key(self):
        """安全地获取API密钥"""
        try:
            # 首先尝试获取加密的API密钥
            encrypted_key = self.settings.value("api_key_encrypted")
            if encrypted_key:
                return self._decrypt_api_key(encrypted_key)
            
            # 向后兼容：尝试获取明文存储的密钥（如果存在）
            plain_key = self.settings.value("api_key_plain")
            if plain_key:
                # 如果找到明文密钥，加密它并删除明文版本
                self.store_api_key(plain_key)
                self.settings.remove("api_key_plain")
                return plain_key
            
            # 尝试旧的明文存储位置
            old_key = self.settings.value("api_key")
            if old_key:
                self.store_api_key(old_key)
                self.settings.remove("api_key")
                return old_key
            
            # 如果没有找到任何密钥，返回空字符串
            return ""
            
        except Exception as e:
            print(f"获取API密钥时出错: {e}")
            # 如果解密失败，返回默认密钥
            return DEFAULT_API_KEY
    
    def verify_api_key(self, api_key=None):
        """验证API密钥的完整性"""
        if api_key is None:
            api_key = self.get_api_key()
        
        stored_hash = self.settings.value("api_key_hash")
        if not stored_hash:
            return False
        
        current_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return current_hash == stored_hash
    
    def clear_api_key(self):
        """清除所有存储的API密钥"""
        try:
            self.settings.remove("api_key")
            self.settings.remove("api_key_plain")
            self.settings.remove("api_key_encrypted")
            self.settings.remove("api_key_hash")
            self.settings.sync()
            return True
        except Exception as e:
            print(f"清除API密钥时出错: {e}")
            return False
    
    def has_custom_api_key(self):
        """检查是否设置了自定义API密钥（非默认密钥）"""
        try:
            current_key = self.get_api_key()
            return current_key != DEFAULT_API_KEY and self.verify_api_key(current_key)
        except:
            return False

# 其余代码保持不变...
class TokenCalculator:
    """Token计算器 - 使用近似算法"""
    
    def __init__(self):
        self.token_cache = {}
        
    def calculate_tokens(self, text):
        """计算文本的token数量（近似值）"""
        if not text:
            return 0
            
        # 使用缓存
        if text in self.token_cache:
            return self.token_cache[text]
        
        # 近似算法：对于中文，一个汉字约2-3个token，英文单词约1.3个token
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        other_chars = len(text) - chinese_chars - sum(len(word) for word in re.findall(r'[a-zA-Z]+', text))
        
        # 近似计算
        tokens = chinese_chars * 2.5 + english_words * 1.3 + other_chars * 0.8
        tokens = int(tokens)
        
        self.token_cache[text] = tokens
        return tokens
    
    def calculate_messages_tokens(self, messages):
        """计算消息列表的总token数"""
        total_tokens = 0
        for message in messages:
            content = message.get('content', '')
            total_tokens += self.calculate_tokens(content)
            
            # 角色信息也占用token
            role = message.get('role', '')
            total_tokens += self.calculate_tokens(role)
            
        return total_tokens

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
                 base_url=DEFAULT_BASE_URL, provider: Optional[str] = None,
                 custom_api_key: Optional[str] = None, custom_base_url: Optional[str] = None):
        super().__init__()
        self.api_key = custom_api_key if custom_api_key else api_key
        self.messages = messages
        self.model = model
        self.stream = stream
        self.base_url = custom_base_url if custom_base_url else base_url
        self.start_time = None
        self.token_calculator = TokenCalculator()
        self.is_reasoner_model = "reasoner" in model.lower()
        
        # 确定LLM提供商
        if provider:
            self.provider = provider.lower()
        elif "deepseek" in model.lower():
            self.provider = "deepseek"
        elif "gpt" in model.lower():
            self.provider = "openai"
        elif "gemini" in model.lower():
            self.provider = "gemini"
        elif "claude" in model.lower():
            self.provider = "anthropic"
        else:
            self.provider = "openai"  # 默认
        
    def run(self):
        try:
            self.start_time = datetime.now()
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            if self.stream:
                self.stream_response(client)
            else:
                self.normal_response(client)
                
        except Exception as e:
            self.error_occurred.emit(f"API调用错误: {str(e)}")
        finally:
            self.finished_signal.emit()
    
    def normal_response(self, client):
        """正常响应模式"""
        self.progress_updated.emit("正在与AI对话...")
        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=False
        )
        
        # 计算token使用量
        input_tokens = self.token_calculator.calculate_messages_tokens(self.messages)
        output_tokens = self.token_calculator.calculate_tokens(response.choices[0].message.content)
        total_tokens = input_tokens + output_tokens
        
        metadata = {
            "model": response.model,
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            },
            "created": response.created
        }
        
        content = response.choices[0].message.content
        self.response_received.emit(content, metadata)
        self.token_usage_updated.emit(input_tokens, output_tokens, total_tokens)
    
    def stream_response(self, client):
        """流式响应模式"""
        self.progress_updated.emit("开始流式响应...")
        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            stream=True
        )
        
        full_content = ""
        thinking_content = ""  # 用于累积思考过程
        chunk_count = 0
        is_thinking = False  # 标记是否在思考过程中
        
        # 计算输入token
        input_tokens = self.token_calculator.calculate_messages_tokens(self.messages)
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                
                # 检查是否是reasoner模型并且有思考过程
                if self.is_reasoner_model:
                    # 检查是否有reasoning_content（思考过程）
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        thinking_chunk = delta.reasoning_content
                        thinking_content += thinking_chunk
                        chunk_count += 1
                        
                        # 发射思考过程更新信号
                        self.thinking_process_updated.emit(thinking_chunk)
                        
                        current_time = datetime.now()
                        time_diff = current_time - self.start_time
                        timestamp = f"{time_diff.seconds}.{time_diff.microseconds // 100000:01d}"
                        
                        if chunk_count % 5 == 0:
                            self.progress_updated.emit(f"已接收 {chunk_count} 个思考数据块...")
                        
                        # 发送思考过程块
                        self.stream_chunk_received.emit(f"[思考] {thinking_chunk}", timestamp)
                        continue
                
                # 处理普通内容
                if hasattr(delta, 'content') and delta.content:
                    content_chunk = delta.content
                    full_content += content_chunk
                    chunk_count += 1
                    
                    current_time = datetime.now()
                    time_diff = current_time - self.start_time
                    timestamp = f"{time_diff.seconds}.{time_diff.microseconds // 100000:01d}"
                    
                    if chunk_count % 5 == 0:
                        self.progress_updated.emit(f"已接收 {chunk_count} 个数据块...")
                    
                    self.stream_chunk_received.emit(content_chunk, timestamp)
        
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

class StreamDisplayManager:
    """流式显示管理器"""
    
    def __init__(self, raw_text_edit, chat_history_widget, markdown_view, thinking_text_edit=None):
        self.raw_text_edit = raw_text_edit
        self.chat_history_widget = chat_history_widget
        self.markdown_view = markdown_view
        self.thinking_text_edit = thinking_text_edit  # 新增：思考过程显示控件
        self.current_stream_content = ""
        self.current_thinking_content = ""  # 新增：当前思考过程内容
        self.stream_start_time = None
        self.chunk_count = 0
        self.is_reasoner_model = False
        
    def set_reasoner_model(self, is_reasoner):
        """设置是否为reasoner模型"""
        self.is_reasoner_model = is_reasoner
        
    def start_stream(self):
        """开始新的流式输出"""
        self.current_stream_content = ""
        self.current_thinking_content = ""  # 重置思考过程
        self.stream_start_time = datetime.now()
        self.chunk_count = 0
        
        if self.is_reasoner_model:
            self.raw_text_edit.append(f"\n🤖 AI响应 (推理模式) [{self.get_current_time()}]:\n")
            # 初始化思考过程显示
            if self.thinking_text_edit:
                self.thinking_text_edit.append(f"\n💭 思考过程 [{self.get_current_time()}]:\n")
        else:
            self.raw_text_edit.append(f"\n🤖 AI响应 [{self.get_current_time()}]:\n")
        
    def add_chunk(self, chunk, timestamp=None):
        """添加流式块"""
        self.chunk_count += 1
        
        # 检查是否为思考过程
        if self.is_reasoner_model and chunk.startswith("[思考] "):
            # 提取纯思考内容
            thinking_chunk = chunk[4:]  # 移除"[思考] "前缀
            self.current_thinking_content += thinking_chunk
            
            # 更新思考过程显示
            if self.thinking_text_edit:
                cursor = self.thinking_text_edit.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertText(thinking_chunk)
                self.thinking_text_edit.setTextCursor(cursor)
                self.thinking_text_edit.ensureCursorVisible()
            
            # 在原始文本中显示思考标记
            cursor = self.raw_text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText("💭")  # 用表情符号表示思考过程
            self.raw_text_edit.setTextCursor(cursor)
            
        else:
            # 普通内容
            self.current_stream_content += chunk
            
            cursor = self.raw_text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(chunk)
            self.raw_text_edit.setTextCursor(cursor)
            self.raw_text_edit.ensureCursorVisible()
        
        if timestamp and self.chunk_count % 10 == 0:
            time_info = f"\n⏱️ [{timestamp}s]"
            cursor = self.raw_text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(time_info)
        
        if self.chunk_count % 5 == 0:
            self.update_markdown_preview()
    
    def add_thinking_chunk(self, thinking_chunk):
        """直接添加思考过程块（通过信号传递）"""
        if not self.thinking_text_edit:
            return
            
        self.current_thinking_content += thinking_chunk
        
        cursor = self.thinking_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(thinking_chunk)
        self.thinking_text_edit.setTextCursor(cursor)
        self.thinking_text_edit.ensureCursorVisible()
        
        # 在原始文本中显示思考标记
        cursor = self.raw_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("💭")  # 用表情符号表示思考过程
        self.raw_text_edit.setTextCursor(cursor)
    
    def complete_stream(self):
        """完成流式输出"""
        self.update_markdown_preview()
        
        if self.stream_start_time:
            end_time = datetime.now()
            duration = end_time - self.stream_start_time
            time_info = f"\n\n✅ 响应完成 - 耗时: {duration.total_seconds():.2f}s, 共{self.chunk_count}个数据块"
            
            if self.is_reasoner_model and self.current_thinking_content:
                time_info += f", 包含思考过程"
                
            self.raw_text_edit.append(time_info)
        
        return self.current_stream_content, self.current_thinking_content
    
    def update_markdown_preview(self):
        """更新Markdown预览"""
        if self.current_stream_content:
            try:
                theme = "dark"
                self.markdown_view.render_markdown(self.current_stream_content, theme)
            except Exception:
                pass
    
    def get_current_time(self):
        """获取当前时间字符串"""
        return datetime.now().strftime("%H:%M:%S")

class MarkdownRenderer(QWebEngineView):
    """Markdown渲染器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def render_markdown(self, text, theme="light"):
        """渲染Markdown文本"""
        try:
            # 转换Markdown为HTML
            html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
            
            css = self.get_css(theme)
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>{css}</style>
            </head>
            <body>
                <div class="markdown-body">
                    {html}
                </div>
            </body>
            </html>
            """
            self.setHtml(full_html)
        except Exception:
            # 如果markdown处理失败，直接显示原始文本
            self.setHtml(f"<pre>{text}</pre>")
    
    def get_css(self, theme):
        """获取CSS样式"""
        if theme == "dark":
            return """
            .markdown-body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #c9d1d9;
                background-color: #0d1117;
                padding: 20px;
            }
            pre { background: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 5px; }
            code { background: #161b22; }
            blockquote { border-left: 4px solid #30363d; color: #8b949e; padding-left: 15px; }
            table { border-color: #30363d; }
            th { background-color: #161b22; }
            """
        else:
            return """
            .markdown-body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #24292f;
                background-color: #ffffff;
                padding: 20px;
            }
            pre { background: #f6f8fa; border: 1px solid #e1e4e8; padding: 10px; border-radius: 5px; }
            code { background: #f6f8fa; }
            blockquote { border-left: 4px solid #dfe2e5; color: #6a737d; padding-left: 15px; }
            table { border-color: #e1e4e8; }
            th { background-color: #f6f8fa; }
            """

class ModernSettingsDialog(QDialog):
    """现代设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("设置")
        self.setFixedSize(600, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        self.tab_widget = QTabWidget()
        
        # API设置选项卡
        api_tab = self.create_api_tab()
        self.tab_widget.addTab(api_tab, "🔑 API设置")
        
        # 模型设置选项卡
        model_tab = self.create_model_tab()
        self.tab_widget.addTab(model_tab, "🤖 模型设置")
        
        # 外观设置选项卡
        appearance_tab = self.create_appearance_tab()
        self.tab_widget.addTab(appearance_tab, "🎨 外观设置")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.accept)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a6fd8, stop:1 #6a4190);
            }
        """)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        
        self.load_settings()
    
    def create_api_tab(self):
        """创建API设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # API基础设置
        api_base_group = QGroupBox("API基础设置")
        api_base_layout = QFormLayout(api_base_group)
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText(DEFAULT_BASE_URL)
        api_base_layout.addRow("API Base URL:", self.base_url_edit)
        
        # API密钥输入
        api_key_layout = QHBoxLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("输入DeepSeek API密钥")
        api_key_layout.addWidget(self.api_key_edit)
        
        self.toggle_key_visibility_btn = QPushButton("👁")
        self.toggle_key_visibility_btn.setFixedSize(30, 30)
        self.toggle_key_visibility_btn.setCheckable(True)
        self.toggle_key_visibility_btn.clicked.connect(self.toggle_key_visibility)
        self.toggle_key_visibility_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
            QPushButton:checked {
                background: #cbd5e1;
            }
        """)
        api_key_layout.addWidget(self.toggle_key_visibility_btn)
        
        api_base_layout.addRow("API密钥:", api_key_layout)
        
        # 密钥状态指示器
        self.key_status_label = QLabel("")
        self.update_key_status()
        api_base_layout.addRow("密钥状态:", self.key_status_label)
        
        # 密钥管理按钮
        key_management_layout = QHBoxLayout()
        self.test_key_btn = QPushButton("测试密钥")
        self.test_key_btn.clicked.connect(self.test_api_key)
        self.test_key_btn.setStyleSheet("""
            QPushButton {
                background: #f59e0b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #d97706;
            }
        """)
        key_management_layout.addWidget(self.test_key_btn)
        
        self.clear_key_btn = QPushButton("清除密钥")
        self.clear_key_btn.clicked.connect(self.clear_api_key)
        self.clear_key_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #dc2626;
            }
        """)
        key_management_layout.addWidget(self.clear_key_btn)
        
        api_base_layout.addRow("密钥管理:", key_management_layout)
        
        # 内置API信息
        # 移除内置免费API提示
        
        # 安全信息
        security_info = QLabel("🔒 您的API密钥已使用AES-256加密存储，仅在本设备上可解密")
        security_info.setStyleSheet("color: #6366f1; font-size: 12px; background: #eef2ff; padding: 8px; border-radius: 5px;")
        api_base_layout.addRow("安全说明:", security_info)
        
        layout.addWidget(api_base_group)
        
        # Token设置
        token_group = QGroupBox("Token计算设置")
        token_layout = QVBoxLayout(token_group)
        
        self.enable_token_calc = QCheckBox("启用Token用量计算")
        self.enable_token_calc.setChecked(True)
        token_layout.addWidget(self.enable_token_calc)
        
        token_info = QLabel("Token计算使用近似算法，用于估算API使用成本")
        token_info.setStyleSheet("color: #64748b; font-size: 12px;")
        token_layout.addWidget(token_info)
        
        layout.addWidget(token_group)
        
        layout.addStretch()
        return tab
    
    def toggle_key_visibility(self):
        """切换密钥显示/隐藏"""
        if self.toggle_key_visibility_btn.isChecked():
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_visibility_btn.setText("🙈")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_visibility_btn.setText("👁")
    
    def update_key_status(self):
        """更新密钥状态显示"""
        if self.parent and self.parent.api_key_manager:
            if self.parent.api_key_manager.has_custom_api_key():
                self.key_status_label.setText("✅ 已设置自定义密钥（已加密）")
                self.key_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
            else:
                self.key_status_label.setText("ℹ️ 使用内置免费API密钥")
                self.key_status_label.setStyleSheet("color: #f59e0b; font-weight: bold;")
    
    def test_api_key(self):
        """测试API密钥有效性"""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(self, "测试失败", "请输入API密钥进行测试")
            return
        
        # 显示测试进度
        progress_dialog = QProgressDialog("正在测试API密钥...", "取消", 0, 0, self)
        progress_dialog.setWindowTitle("测试API密钥")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.show()
        
        try:
            # 使用线程测试API密钥
            result_queue = Queue()
            
            def test_key():
                try:
                    client = OpenAI(api_key=api_key, base_url=self.base_url_edit.text() or DEFAULT_BASE_URL)
                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": "测试消息，请回复'连接成功'"}],
                        max_tokens=10
                    )
                    result_queue.put(("success", response.choices[0].message.content))
                except Exception as e:
                    result_queue.put(("error", str(e)))
            
            thread = Thread(target=test_key)
            thread.daemon = True
            thread.start()
            
            # 等待结果
            thread.join(timeout=10)
            
            if thread.is_alive():
                progress_dialog.close()
                QMessageBox.warning(self, "测试超时", "API测试超时，请检查网络连接")
                return
            
            progress_dialog.close()
            
            if not result_queue.empty():
                result_type, result_data = result_queue.get()
                if result_type == "success":
                    QMessageBox.information(self, "测试成功", f"API密钥有效！\n\nAI回复: {result_data}")
                    self.key_status_label.setText("✅ 密钥测试通过（有效）")
                    self.key_status_label.setStyleSheet("color: #10b981; font-weight: bold;")
                else:
                    QMessageBox.critical(self, "测试失败", f"API密钥无效或网络错误:\n\n{result_data}")
                    self.key_status_label.setText("❌ 密钥测试失败")
                    self.key_status_label.setStyleSheet("color: #ef4444; font-weight: bold;")
            else:
                QMessageBox.warning(self, "测试失败", "无法获取测试结果")
                
        except Exception as e:
            progress_dialog.close()
            QMessageBox.critical(self, "测试错误", f"测试过程中发生错误:\n\n{str(e)}")
    
    def clear_api_key(self):
        """清除API密钥"""
        reply = QMessageBox.question(
            self, 
            "确认清除", 
            "确定要清除已保存的API密钥吗？\n\n清除后将使用内置免费API密钥。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.parent and self.parent.api_key_manager:
                if self.parent.api_key_manager.clear_api_key():
                    self.api_key_edit.clear()
                    self.update_key_status()
                    QMessageBox.information(self, "清除成功", "API密钥已成功清除")
                else:
                    QMessageBox.warning(self, "清除失败", "清除API密钥时发生错误")
    
    def create_model_tab(self):
        """创建模型设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 模型选择
        model_group = QGroupBox("模型选择")
        model_layout = QFormLayout(model_group)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["deepseek-chat", "deepseek-reasoner"])
        model_layout.addRow("默认模型:", self.model_combo)
        
        model_info = QLabel("deepseek-chat: 通用对话模型\ndeepseek-reasoner: 推理增强模型（显示思考过程）")
        model_info.setStyleSheet("color: #64748b; font-size: 12px;")
        model_layout.addRow("模型说明:", model_info)
        
        layout.addWidget(model_group)
        
        # 参数设置
        param_group = QGroupBox("生成参数")
        param_layout = QFormLayout(param_group)
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0, 2)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setSingleStep(0.1)
        param_layout.addRow("温度:", self.temperature_spin)
        
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 32000)
        self.max_tokens_spin.setValue(2000)
        self.max_tokens_spin.setSingleStep(100)
        param_layout.addRow("最大Token数:", self.max_tokens_spin)
        
        layout.addWidget(param_group)
        
        # 流式输出设置
        stream_group = QGroupBox("流式输出")
        stream_layout = QVBoxLayout(stream_group)
        
        self.stream_enabled = QCheckBox("启用流式输出")
        self.stream_enabled.setChecked(True)
        stream_layout.addWidget(self.stream_enabled)
        
        self.show_timestamps = QCheckBox("显示时间戳")
        self.show_timestamps.setChecked(True)
        stream_layout.addWidget(self.show_timestamps)
        
        self.show_thinking = QCheckBox("显示思考过程（仅reasoner模型）")
        self.show_thinking.setChecked(True)
        stream_layout.addWidget(self.show_thinking)
        
        layout.addWidget(stream_group)
        
        layout.addStretch()
        return tab
    
    def create_appearance_tab(self):
        """创建外观设置选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 主题设置
        theme_group = QGroupBox("主题设置")
        theme_layout = QVBoxLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["自动", "浅色主题", "深色主题"])
        theme_layout.addWidget(QLabel("主题模式:"))
        theme_layout.addWidget(self.theme_combo)
        
        transparency_layout = QVBoxLayout()
        transparency_layout.addWidget(QLabel("窗口透明度:"))
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(50, 100)
        self.transparency_slider.setValue(100)
        transparency_layout.addWidget(self.transparency_slider)
        theme_layout.addLayout(transparency_layout)
        
        layout.addWidget(theme_group)
        
        layout.addStretch()
        return tab
    
    def load_settings(self):
        """加载设置"""
        settings = QSettings()
        
        # API设置
        self.base_url_edit.setText(settings.value("base_url", DEFAULT_BASE_URL))
        if self.parent and self.parent.api_key_manager:
            # 不直接显示加密的API密钥，只显示状态
            self.update_key_status()
        
        self.enable_token_calc.setChecked(settings.value("enable_token_calc", True, type=bool))
        
        # 模型设置
        self.model_combo.setCurrentText(settings.value("model", "deepseek-chat"))
        self.temperature_spin.setValue(settings.value("temperature", 0.7, type=float))
        self.max_tokens_spin.setValue(settings.value("max_tokens", 2000, type=int))
        self.stream_enabled.setChecked(settings.value("stream_enabled", True, type=bool))
        self.show_timestamps.setChecked(settings.value("show_timestamps", True, type=bool))
        self.show_thinking.setChecked(settings.value("show_thinking", True, type=bool))
        
        # 外观设置
        self.theme_combo.setCurrentText(settings.value("theme", "自动"))
        self.transparency_slider.setValue(settings.value("transparency", 100, type=int))
    
    def accept(self):
        """保存设置"""
        settings = QSettings()
        
        # API设置
        settings.setValue("base_url", self.base_url_edit.text())
        api_key = self.api_key_edit.text().strip()
        if api_key and self.parent and self.parent.api_key_manager:
            if self.parent.api_key_manager.store_api_key(api_key):
                self.update_key_status()
        
        settings.setValue("enable_token_calc", self.enable_token_calc.isChecked())
        
        # 模型设置
        settings.setValue("model", self.model_combo.currentText())
        settings.setValue("temperature", self.temperature_spin.value())
        settings.setValue("max_tokens", self.max_tokens_spin.value())
        settings.setValue("stream_enabled", self.stream_enabled.isChecked())
        settings.setValue("show_timestamps", self.show_timestamps.isChecked())
        settings.setValue("show_thinking", self.show_thinking.isChecked())
        
        # 外观设置
        settings.setValue("theme", self.theme_combo.currentText())
        settings.setValue("transparency", self.transparency_slider.value())
        
        if self.parent:
            self.parent.apply_settings()
            self.parent.update_api_config()
        
        super().accept()

class DeepSeekClient(QMainWindow):
    def __init__(self):
        super().__init__()
        # 初始化组件
        self.api_key_manager = SecureAPIKeyManager()
        self.api_key = self.api_key_manager.get_api_key()
        self.token_calculator = TokenCalculator()
        
        self.current_topic = None
        self.topics = {}
        self.conversations = {}
        self.settings = QSettings("DeepSeek", "AI Client")
        
        # Token统计
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        
        # API配置
        self.base_url = self.settings.value("base_url", DEFAULT_BASE_URL)
        self.current_model = self.settings.value("model", "deepseek-chat")
        self.temperature = self.settings.value("temperature", 0.7, type=float)
        self.max_tokens = self.settings.value("max_tokens", 2000, type=int)
        
        # 初始化UI
        self.init_ui()
        self.load_data()
        self.apply_settings()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('DeepSeek AI 客户端 - 内置免费API')
        self.setGeometry(100, 100, 1400, 900)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建侧边栏和主内容区域
        self.create_sidebar(main_layout)
        self.create_main_content(main_layout)
        
        # 创建状态栏
        self.setup_statusbar()
        
        # 创建菜单栏
        self.setup_menubar()
        
        # 应用样式
        self.apply_modern_style()
        
        # 初始化流式显示管理器
        self.stream_display_manager = StreamDisplayManager(
            self.raw_text_edit, 
            self.chat_history_widget, 
            self.markdown_view,
            self.thinking_text_edit
        )
    
    def create_sidebar(self, main_layout):
        """创建侧边栏"""
        self.sidebar = QWidget()
        self.sidebar.setMaximumWidth(300)
        self.sidebar.setMinimumWidth(250)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(15)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        
        # 应用标题
        title_label = QLabel("DeepSeek AI")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #667eea;
                padding: 10px 0px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                background-clip: text;
                text-fill-color: transparent;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title_label)
        
        # 免费API提示
        # 移除侧边栏免费API提示
        
        # 新建话题按钮
        self.new_topic_btn = QPushButton("🆕 新建话题")
        self.new_topic_btn.clicked.connect(self.create_new_topic)
        self.new_topic_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a6fd8, stop:1 #6a4190);
            }
        """)
        sidebar_layout.addWidget(self.new_topic_btn)
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索话题...")
        self.search_input.textChanged.connect(self.search_content)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #667eea;
            }
        """)
        sidebar_layout.addWidget(self.search_input)
        
        # 话题列表
        self.topic_list = QListWidget()
        self.topic_list.itemClicked.connect(self.load_topic)
        self.topic_list.setStyleSheet("""
            QListWidget {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                background: white;
                outline: none;
                font-size: 14px;
            }
            QListWidget::item {
                border-bottom: 1px solid #f1f5f9;
                padding: 12px 15px;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: #f8fafc;
                border-radius: 6px;
            }
        """)
        sidebar_layout.addWidget(self.topic_list)
        
        # Token统计
        token_group = QGroupBox("Token统计")
        token_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        token_layout = QVBoxLayout(token_group)
        
        self.token_stats = QLabel("输入: 0\n输出: 0\n总计: 0")
        self.token_stats.setStyleSheet("font-family: monospace; background: #f8fafc; padding: 10px; border-radius: 5px;")
        token_layout.addWidget(self.token_stats)
        
        sidebar_layout.addWidget(token_group)
        
        # 底部按钮组
        bottom_btn_layout = QHBoxLayout()
        
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.clicked.connect(self.show_settings)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        bottom_btn_layout.addWidget(self.settings_btn)
        
        self.export_btn = QPushButton("📤")
        self.export_btn.setFixedSize(40, 40)
        self.export_btn.clicked.connect(self.export_conversation)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        bottom_btn_layout.addWidget(self.export_btn)
        
        sidebar_layout.addLayout(bottom_btn_layout)
        
        main_layout.addWidget(self.sidebar)
    
    def create_main_content(self, main_layout):
        """创建主内容区域"""
        # 主内容容器
        main_content = QWidget()
        main_content_layout = QVBoxLayout(main_content)
        main_content_layout.setSpacing(0)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
            }
            QTabBar::tab {
                background: #f8fafc;
                border: none;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                color: #64748b;
            }
            QTabBar::tab:selected {
                background: white;
                color: #667eea;
                border-bottom: 2px solid #667eea;
            }
            QTabBar::tab:hover {
                background: #e2e8f0;
            }
        """)
        
        # Markdown渲染标签页
        self.markdown_view = MarkdownRenderer()
        self.tab_widget.addTab(self.markdown_view, "📄 Markdown")
        
        # 原始文本标签页
        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setFont(QFont("Consolas", 11))
        self.tab_widget.addTab(self.raw_text_edit, "📝 原始文本")
        
        # 聊天历史标签页
        self.chat_history_widget = QTextEdit()
        self.chat_history_widget.setReadOnly(True)
        self.tab_widget.addTab(self.chat_history_widget, "💬 聊天历史")
        
        # 思考过程标签页
        self.thinking_text_edit = QTextEdit()
        self.thinking_text_edit.setReadOnly(True)
        self.thinking_text_edit.setFont(QFont("Consolas", 10))
        self.thinking_text_edit.setStyleSheet("""
            QTextEdit {
                background: #f8fafc;
                border: none;
                color: #475569;
            }
        """)
        self.tab_widget.addTab(self.thinking_text_edit, "💭 思考过程")
        
        main_content_layout.addWidget(self.tab_widget)
        
        # 输入区域
        input_container = QWidget()
        input_container.setStyleSheet("background: white; border-top: 2px solid #f1f5f9;")
        input_layout = QVBoxLayout(input_container)
        input_layout.setSpacing(10)
        input_layout.setContentsMargins(20, 15, 20, 20)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        
        # 助手选择按钮
        self.assistant_btn = QPushButton("🤖 选择助手")
        self.assistant_btn.clicked.connect(self.select_assistant)
        self.assistant_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 15px;
                color: #64748b;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        toolbar_layout.addWidget(self.assistant_btn)
        
        # 模型选择
        toolbar_layout.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["deepseek-chat", "deepseek-reasoner"])
        self.model_combo.setCurrentText(self.current_model)
        self.model_combo.currentTextChanged.connect(self.update_model)
        toolbar_layout.addWidget(self.model_combo)
        
        # 模型说明标签
        self.model_info_label = QLabel()
        self.update_model_info_label()
        self.model_combo.currentTextChanged.connect(self.update_model_info_label)
        toolbar_layout.addWidget(self.model_info_label)
        
        self.file_upload_btn = QPushButton("📎 上传文件")
        self.file_upload_btn.clicked.connect(self.upload_file)
        self.file_upload_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 15px;
                color: #64748b;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        toolbar_layout.addWidget(self.file_upload_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.clicked.connect(self.clear_input)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #f8fafc;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 15px;
                color: #64748b;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        toolbar_layout.addWidget(self.clear_btn)
        
        self.stream_checkbox = QCheckBox("流式输出")
        self.stream_checkbox.setChecked(True)
        self.stream_checkbox.setStyleSheet("""
            QCheckBox {
                color: #64748b;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #cbd5e1;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #667eea;
                border-color: #667eea;
            }
        """)
        toolbar_layout.addWidget(self.stream_checkbox)
        
        # 流式状态指示器
        self.stream_status_label = QLabel("就绪")
        self.stream_status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        toolbar_layout.addWidget(self.stream_status_label)
        
        toolbar_layout.addStretch()
        
        input_layout.addLayout(toolbar_layout)
        
        # 输入框和发送按钮
        input_area_layout = QHBoxLayout()
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(120)
        self.message_input.setPlaceholderText("💭 输入您的问题... (Ctrl+Enter发送)")
        self.message_input.setAcceptRichText(False)
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e2e8f0;
                border-radius: 12px;
                padding: 15px;
                font-size: 14px;
                background: white;
                selection-background-color: #667eea;
            }
            QTextEdit:focus {
                border-color: #667eea;
            }
        """)
        input_area_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 80)
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 15px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a6fd8, stop:1 #6a4190);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4c5bc0, stop:1 #5a3579);
            }
        """)
        input_area_layout.addWidget(self.send_btn)
        
        input_layout.addLayout(input_area_layout)
        
        main_content_layout.addWidget(input_container)
        
        main_layout.addWidget(main_content, 1)
    
    def update_model_info_label(self):
        """更新模型说明标签"""
        model = self.model_combo.currentText()
        if model == "deepseek-reasoner":
            self.model_info_label.setText("🧠 推理模型（显示思考过程）")
            self.model_info_label.setStyleSheet("color: #dc2626; font-weight: bold; background: #fef2f2; padding: 4px 8px; border-radius: 4px;")
        else:
            self.model_info_label.setText("💬 聊天模型")
            self.model_info_label.setStyleSheet("color: #059669; font-weight: bold; background: #f0fdf4; padding: 4px 8px; border-radius: 4px;")
    
    def setup_statusbar(self):
        """设置状态栏"""
        self.statusBar().showMessage("就绪")
        
        # 添加永久部件
        self.token_label = QLabel("Tokens: 0")
        self.token_label.setStyleSheet("color: #64748b; padding: 5px;")
        self.statusBar().addPermanentWidget(self.token_label)
        
        self.model_label = QLabel(f"Model: {self.current_model}")
        self.model_label.setStyleSheet("color: #64748b; padding: 5px;")
        self.statusBar().addPermanentWidget(self.model_label)
        
        # API状态
        self.api_status_label = QLabel("✅ 内置免费API")
        self.api_status_label.setStyleSheet("color: #10b981; padding: 5px; font-weight: bold;")
        self.statusBar().addPermanentWidget(self.api_status_label)
        
        # 添加流式输出状态指示器
        self.stream_indicator = QLabel("")
        self.stream_indicator.setStyleSheet("color: #64748b; padding: 5px;")
        self.statusBar().addPermanentWidget(self.stream_indicator)
        
        # 添加思考过程状态指示器
        self.thinking_indicator = QLabel("")
        self.thinking_indicator.setStyleSheet("color: #dc2626; padding: 5px;")
        self.statusBar().addPermanentWidget(self.thinking_indicator)
    
    def setup_menubar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: white;
                border-bottom: 2px solid #f1f5f9;
                padding: 5px;
            }
            QMenuBar::item {
                padding: 8px 15px;
                border-radius: 6px;
                color: #64748b;
            }
            QMenuBar::item:selected {
                background: #667eea;
                color: white;
            }
        """)
        
        # 文件菜单
        file_menu = menubar.addMenu('📁 文件')
        
        new_topic_action = QAction('🆕 新建话题', self)
        new_topic_action.triggered.connect(self.create_new_topic)
        file_menu.addAction(new_topic_action)
        
        export_action = QAction('📤 导出对话', self)
        export_action.triggered.connect(self.export_conversation)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('🚪 退出', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 设置菜单
        settings_menu = menubar.addMenu('⚙️ 设置')
        
        settings_action = QAction('🎛️ 偏好设置', self)
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('❓ 帮助')
        
        about_action = QAction('ℹ️ 关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def apply_modern_style(self):
        """应用现代样式"""
        self.setStyleSheet("""
            QMainWindow {
                background: white;
                border: none;
            }
            QWidget {
                background: white;
            }
            QTextEdit, QListWidget, QLineEdit {
                background: white;
            }
        """)
    
    def apply_settings(self):
        """应用设置"""
        theme = self.settings.value("theme", "自动")
        if "深色" in theme:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()
        
        transparency = self.settings.value("transparency", 100, type=int)
        self.setWindowOpacity(transparency / 100.0)
    
    def update_api_config(self):
        """更新API配置"""
        self.base_url = self.settings.value("base_url", DEFAULT_BASE_URL)
        self.current_model = self.settings.value("model", "deepseek-chat")
        self.temperature = self.settings.value("temperature", 0.7, type=float)
        self.max_tokens = self.settings.value("max_tokens", 2000, type=int)
        
        # 更新UI
        self.model_combo.setCurrentText(self.current_model)
        self.model_label.setText(f"Model: {self.current_model}")
        
        # 更新API密钥
        self.api_key = self.api_key_manager.get_api_key()
    def select_assistant(self):
        """选择助手"""
        dialog = AssistantDialog(self)
        dialog.assistant_selected.connect(self.apply_assistant_config)
        dialog.exec()
    
    def apply_assistant_config(self, assistant_id):
        """应用助手配置"""
        manager = AssistantManager()
        assistant = manager.get_assistant(assistant_id)
        if assistant:
            self.current_assistant_id = assistant_id
            self.current_model = assistant.model
            self.model_combo.setCurrentText(assistant.model)
            self.model_label.setText(f"Model: {assistant.model}")
            
            # 更新流式显示管理器的模型状态
            is_reasoner = "reasoner" in assistant.model.lower()
            self.stream_display_manager.set_reasoner_model(is_reasoner)
            
            # 更新状态栏指示器
            if is_reasoner:
                self.thinking_indicator.setText("🧠 推理模式")
            else:
                self.thinking_indicator.setText("")
            
            # 更新API配置
            if assistant.custom_api:
                self.api_key = assistant.custom_api_key
                self.base_url = assistant.custom_base_url
    
    def update_model(self, model):
        """更新模型"""
        self.current_model = model
        self.settings.setValue("model", model)
        self.model_label.setText(f"Model: {model}")
        
        # 更新流式显示管理器的模型状态
        is_reasoner = "reasoner" in model.lower()
        self.stream_display_manager.set_reasoner_model(is_reasoner)
        
        # 更新状态栏指示器
        if is_reasoner:
            self.thinking_indicator.setText("🧠 推理模式")
        else:
            self.thinking_indicator.setText("")
    
    def apply_light_theme(self):
        """应用浅色主题"""
        light_palette = QPalette()
        light_palette.setColor(QPalette.ColorRole.Window, QColor(248, 250, 252))
        light_palette.setColor(QPalette.ColorRole.WindowText, QColor(30, 41, 59))
        light_palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(241, 245, 249))
        light_palette.setColor(QPalette.ColorRole.Text, QColor(30, 41, 59))
        light_palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.ButtonText, QColor(30, 41, 59))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor(102, 126, 234))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        self.setPalette(light_palette)
    
    def apply_dark_theme(self):
        """应用深色主题"""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 41, 59))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(226, 232, 240))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(15, 23, 42))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(30, 41, 59))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(226, 232, 240))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(30, 41, 59))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(226, 232, 240))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(102, 126, 234))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        
        self.setPalette(dark_palette)
        
        # 更新深色主题的样式表
        self.sidebar.setStyleSheet("background: #1e293b;")
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #0f172a;
            }
            QTabBar::tab {
                background: #1e293b;
                border: none;
                padding: 12px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                color: #94a3b8;
            }
            QTabBar::tab:selected {
                background: #0f172a;
                color: #667eea;
                border-bottom: 2px solid #667eea;
            }
            QTabBar::tab:hover {
                background: #334155;
            }
        """)
    
    def create_new_topic(self):
        """创建新话题"""
        name, ok = QInputDialog.getText(self, '新建话题', '输入话题名称:')
        if ok and name:
            topic_id = f"topic_{len(self.topics) + 1}"
            self.topics[topic_id] = {
                "name": name,
                "created": datetime.now().isoformat(),
                "conversations": []
            }
            self.conversations[topic_id] = []
            self.update_topic_list()
            
            # 选择新创建的话题
            for i in range(self.topic_list.count()):
                if self.topic_list.item(i).text() == name:
                    self.topic_list.setCurrentRow(i)
                    break

    def update_topic_list(self):
        """更新话题列表"""
        self.topic_list.clear()
        for topic_data in self.topics.values():
            item = QListWidgetItem(topic_data["name"])
            self.topic_list.addItem(item)

    def load_topic(self, item):
        """加载话题"""
        if not item:
            return
        
        topic_name = item.text()
        self.current_topic = None
        
        # 找到对应的话题ID
        for topic_id, topic_data in self.topics.items():
            if topic_data["name"] == topic_name:
                self.current_topic = topic_id
                break
        
        if self.current_topic:
            self.update_conversation_display()

    def search_content(self, text):
        """搜索内容"""
        if not text.strip():
            self.update_topic_list()
            return
        
        # 搜索话题名称和内容
        self.topic_list.clear()
        search_text = text.lower()
        
        for topic_id, topic_data in self.topics.items():
            topic_name = topic_data["name"]
            
            # 检查话题名称匹配
            if search_text in topic_name.lower():
                item = QListWidgetItem(topic_name)
                self.topic_list.addItem(item)
                continue
            
            # 检查对话内容匹配
            if topic_id in self.conversations:
                for conv in self.conversations[topic_id]:
                    if 'content' in conv and search_text in conv['content'].lower():
                        item = QListWidgetItem(topic_name)
                        self.topic_list.addItem(item)
                        break

    def send_message(self):
        """发送消息"""
        if not self.api_key:
            QMessageBox.warning(self, "错误", "请先设置API密钥")
            return
        
        if not self.current_topic:
            QMessageBox.warning(self, "错误", "请先选择或创建一个话题")
            return
        
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # 添加到对话历史
        if self.current_topic not in self.conversations:
            self.conversations[self.current_topic] = []
        
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        self.conversations[self.current_topic].append(user_message)
        
        # 构建消息列表
        messages = [{"role": "system", "content": "You are a helpful assistant"}]
        for conv in self.conversations[self.current_topic][-10:]:  # 只发送最近10条消息
            messages.append({"role": conv["role"], "content": conv["content"]})
        
        # 清空输入框
        self.message_input.clear()
        
        # 显示用户消息
        self.update_conversation_display()
        
        # 设置流式显示管理器的模型状态
        is_reasoner = "reasoner" in self.current_model.lower()
        self.stream_display_manager.set_reasoner_model(is_reasoner)
        
        # 初始化流式显示
        if self.stream_display_manager:
            self.stream_display_manager.start_stream()
        
        # 调用API
        self.call_api(messages)

    def call_api(self, messages):
        """调用API"""
        stream = self.stream_checkbox.isChecked()
        
        # 获取当前助手配置
        manager = AssistantManager()
        assistant = manager.get_assistant(self.current_assistant_id) if hasattr(self, 'current_assistant_id') else None
        
        self.api_worker = APIWorker(
            api_key=self.api_key,
            messages=messages,
            model=self.current_model,
            stream=stream,
            base_url=self.base_url,
            provider=assistant.provider if assistant and hasattr(assistant, 'provider') else None,
            custom_api_key=assistant.custom_api_key if assistant and hasattr(assistant, 'custom_api_key') else None,
            custom_base_url=assistant.custom_base_url if assistant and hasattr(assistant, 'custom_base_url') else None
        )
        
        if stream:
            self.api_worker.stream_chunk_received.connect(self.handle_stream_chunk)
            self.api_worker.progress_updated.connect(self.handle_stream_progress)
            # 连接思考过程信号
            self.api_worker.thinking_process_updated.connect(self.handle_thinking_process)
        
        self.api_worker.response_received.connect(self.handle_api_response)
        self.api_worker.error_occurred.connect(self.handle_api_error)
        self.api_worker.finished_signal.connect(self.handle_api_finished)
        self.api_worker.token_usage_updated.connect(self.handle_token_usage)
        
        self.statusBar().showMessage("正在与AI对话...")
        self.stream_status_label.setText("🔄 请求中...")
        self.stream_indicator.setText("🔄 流式传输")
        
        # 更新思考过程状态
        if "reasoner" in self.current_model.lower():
            self.thinking_indicator.setText("🧠 思考中...")
        
        self.api_worker.start()

    def handle_thinking_process(self, thinking_chunk):
        """处理思考过程更新"""
        self.stream_display_manager.add_thinking_chunk(thinking_chunk)

    def handle_stream_chunk(self, chunk, timestamp):
        """处理流式响应块"""
        # 更新流式显示管理器
        if self.stream_display_manager:
            self.stream_display_manager.add_chunk(chunk, timestamp)
        
        # 更新状态显示
        current_time = datetime.now().strftime("%H:%M:%S")
        self.stream_status_label.setText(f"📡 接收中... {timestamp}s")

    def handle_stream_progress(self, progress_message):
        """处理流式进度更新"""
        self.statusBar().showMessage(progress_message)

    def handle_api_response(self, content, metadata):
        """处理API响应"""
        # 完成流式显示
        if self.stream_display_manager:
            final_content, thinking_content = self.stream_display_manager.complete_stream()
        else:
            final_content = content
            thinking_content = ""
        
        # 保存AI响应
        ai_message = {
            "role": "assistant",
            "content": final_content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata
        }
        
        # 如果有关思考过程，也保存
        if thinking_content:
            ai_message["thinking_content"] = thinking_content
        
        if self.current_topic in self.conversations:
            self.conversations[self.current_topic].append(ai_message)
        
        # 更新显示
        self.update_conversation_display()
        
        # 更新状态栏
        if 'usage' in metadata:
            tokens = metadata['usage'].get('total_tokens', 0)
            self.token_label.setText(f"Tokens: {tokens}")
        
        self.model_label.setText(f"Model: {metadata.get('model', 'unknown')}")
        
        # 显示流式统计信息
        if metadata.get('stream'):
            chunks = metadata.get('chunks_received', 0)
            status_msg = f"流式响应完成，共接收 {chunks} 个数据块"
            if thinking_content:
                status_msg += f"，包含思考过程"
            self.statusBar().showMessage(status_msg)

    def handle_token_usage(self, input_tokens, output_tokens, total_tokens):
        """处理token使用量"""
        # 更新总统计
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tokens += total_tokens
        
        # 更新侧边栏显示
        self.token_stats.setText(f"输入: {self.total_input_tokens}\n输出: {self.total_output_tokens}\n总计: {self.total_tokens}")
        
        # 更新状态栏
        self.token_label.setText(f"Tokens: {total_tokens}")

    def handle_api_error(self, error_message):
        """处理API错误"""
        # 解析常见错误类型
        if "ConnectionError" in error_message:
            detailed_msg = "无法连接到API服务器，请检查网络连接和Base URL设置"
        elif "Timeout" in error_message:
            detailed_msg = "请求超时，可能是服务器响应慢或网络问题"
        elif "Invalid API key" in error_message:
            detailed_msg = "API密钥无效，请检查密钥是否正确"
        elif "Rate limit" in error_message:
            detailed_msg = "达到API调用频率限制，请稍后再试"
        else:
            detailed_msg = error_message
        
        # 显示详细错误信息
        error_dialog = QMessageBox(self)
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("API错误")
        error_dialog.setText("API调用失败")
        error_dialog.setInformativeText(detailed_msg)
        
        # 添加帮助按钮
        help_button = error_dialog.addButton("获取帮助", QMessageBox.ButtonRole.ActionRole)
        retry_button = error_dialog.addButton("重试", QMessageBox.ButtonRole.ActionRole)
        error_dialog.addButton(QMessageBox.StandardButton.Ok)
        
        # 显示对话框并处理响应
        error_dialog.exec()
        
        if error_dialog.clickedButton() == help_button:
            self.show_api_help()
        elif error_dialog.clickedButton() == retry_button:
            self.retry_last_request()
        
        # 更新状态显示
        self.statusBar().showMessage("API调用失败")
        self.stream_status_label.setText("❌ 错误")
        self.stream_indicator.setText("")
        self.thinking_indicator.setText("")
    
    def show_api_help(self):
        """显示API帮助信息"""
        help_text = """
        <h3>API错误帮助</h3>
        <p>常见API错误解决方法：</p>
        <ul>
            <li><b>连接错误</b>：检查网络连接和Base URL设置</li>
            <li><b>无效API密钥</b>：确认密钥是否正确，是否已启用</li>
            <li><b>频率限制</b>：降低请求频率或升级API套餐</li>
            <li><b>模型不可用</b>：检查模型名称是否正确</li>
        </ul>
        <p>如需进一步帮助，请参考API文档或联系支持团队。</p>
        """
        QMessageBox.information(self, "API帮助", help_text)
    
    def retry_last_request(self):
        """重试上次请求"""
        if hasattr(self, 'last_api_messages'):
            self.call_api(self.last_api_messages)

    def handle_api_finished(self):
        """API调用完成"""
        self.statusBar().showMessage("就绪")
        self.stream_status_label.setText("就绪")
        self.stream_indicator.setText("")
        self.thinking_indicator.setText("")
        self.save_data()

    def update_conversation_display(self):
        """更新对话显示"""
        if not self.current_topic or self.current_topic not in self.conversations:
            return
        
        # 更新聊天历史
        history_text = ""
        for conv in self.conversations[self.current_topic]:
            role = "👤 用户" if conv["role"] == "user" else "🤖 AI"
            timestamp = datetime.fromisoformat(conv["timestamp"]).strftime("%H:%M:%S")
            history_text += f"[{timestamp}] {role}:\n{conv['content']}\n\n"
            
            # 如果有思考过程，也显示在历史中
            if conv.get("thinking_content"):
                history_text += f"[{timestamp}] 🤖 AI思考过程:\n{conv['thinking_content']}\n\n"
        
        self.chat_history_widget.setPlainText(history_text)
        
        # 获取最新的AI回复进行渲染
        ai_responses = [conv for conv in self.conversations[self.current_topic] 
                       if conv["role"] == "assistant"]
        if ai_responses:
            latest_response = ai_responses[-1]["content"]
            self.raw_text_edit.setPlainText(latest_response)
            
            # 渲染Markdown
            theme = "dark" if "dark" in self.settings.value("theme", "").lower() else "light"
            self.markdown_view.render_markdown(latest_response, theme)
            
            # 如果有思考过程，显示在思考过程标签页
            if ai_responses[-1].get("thinking_content"):
                self.thinking_text_edit.setPlainText(ai_responses[-1]["thinking_content"])

    def upload_file(self):
        """上传文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "所有文件 (*);;文本文件 (*.txt *.md);;PDF文件 (*.pdf);;Word文档 (*.docx);;Excel文件 (*.xlsx *.xls *.csv);;图片文件 (*.jpg *.jpeg *.png *.gif *.bmp)"
        )
        
        if file_path:
            self.process_uploaded_file(file_path)

    def process_uploaded_file(self, file_path):
        """处理上传的文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 将文件内容添加到输入框
            current_text = self.message_input.toPlainText()
            if current_text:
                self.message_input.setPlainText(current_text + "\n\n" + content)
            else:
                self.message_input.setPlainText(content)
                
            self.statusBar().showMessage("文件处理完成")
        except Exception as e:
            QMessageBox.critical(self, "文件处理错误", f"无法读取文件: {str(e)}")

    def clear_input(self):
        """清空输入"""
        self.message_input.clear()

    def clear_conversation_display(self):
        """清空对话显示"""
        self.chat_history_widget.clear()
        self.raw_text_edit.clear()
        self.markdown_view.setHtml("")
        self.thinking_text_edit.clear()

    def export_conversation(self):
        """导出对话"""
        if not self.current_topic or self.current_topic not in self.conversations:
            QMessageBox.warning(self, "导出", "没有可导出的对话")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出对话",
            f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            "Markdown文件 (*.md);;文本文件 (*.txt);;JSON文件 (*.json)"
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    self.export_json(file_path)
                else:
                    self.export_markdown(file_path)
                QMessageBox.information(self, "导出成功", "对话已成功导出")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出时发生错误: {str(e)}")

    def export_markdown(self, file_path):
        """导出为Markdown格式"""
        with open(file_path, 'w', encoding='utf-8') as f:
            topic_name = self.topics[self.current_topic]["name"]
            f.write(f"# {topic_name}\n\n")
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"总Token使用量: 输入{self.total_input_tokens} + 输出{self.total_output_tokens} = {self.total_tokens}\n\n")
            
            for conv in self.conversations[self.current_topic]:
                role = "用户" if conv["role"] == "user" else "AI"
                timestamp = datetime.fromisoformat(conv["timestamp"]).strftime("%H:%M:%S")
                f.write(f"## {role} ({timestamp})\n\n")
                f.write(conv["content"] + "\n\n")
                
                # 如果有思考过程，也导出
                if conv.get("thinking_content"):
                    f.write(f"### {role}思考过程\n\n")
                    f.write(conv["thinking_content"] + "\n\n")

    def export_json(self, file_path):
        """导出为JSON格式"""
        export_data = {
            "topic": self.topics[self.current_topic],
            "conversations": self.conversations[self.current_topic],
            "token_usage": {
                "input_tokens": self.total_input_tokens,
                "output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens
            },
            "export_time": datetime.now().isoformat()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def show_settings(self):
        """显示设置对话框"""
        dialog = ModernSettingsDialog(self)
        dialog.exec()

    def show_about(self):
        """显示关于信息"""
        QMessageBox.about(self, "关于 DeepSeek AI 客户端",
                        f"DeepSeek AI 客户端\n\n"
                        f"API Base URL: {DEFAULT_BASE_URL}\n\n"
                        f"功能特性：\n"
                        f"• 支持自定义API密钥\n"
                        f"• 支持deepseek-chat和deepseek-reasoner模型\n"
                        f"• 实时Token用量计算\n"
                        f"• 流式输出显示\n"
                        f"• Markdown渲染\n"
                        f"• 话题管理\n"
                        f"• deepseek-reasoner模型思考过程显示\n"
                        f"• API密钥加密存储\n\n"
                        f"基于 PySide6 和 DeepSeek API 开发")

    def load_data(self):
        """加载数据"""
        # 加载话题和对话数据
        topics_data = self.settings.value("topics")
        conversations_data = self.settings.value("conversations")
        
        if topics_data:
            self.topics = json.loads(topics_data)
        else:
            # 创建默认话题
            self.topics = {
                "topic_1": {
                    "name": "默认话题",
                    "created": datetime.now().isoformat(),
                    "conversations": []
                }
            }
        
        if conversations_data:
            self.conversations = json.loads(conversations_data)
        else:
            self.conversations = {topic_id: [] for topic_id in self.topics.keys()}
        
        self.update_topic_list()
        if self.topic_list.count() > 0:
            self.topic_list.setCurrentRow(0)
            self.load_topic(self.topic_list.item(0))

    def save_data(self):
        """保存数据"""
        self.settings.setValue("topics", json.dumps(self.topics))
        self.settings.setValue("conversations", json.dumps(self.conversations))
        self.settings.sync()

    def closeEvent(self, event):
        """关闭事件"""
        self.save_data()
        event.accept()

def main():
    """主函数"""
    # 启用高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeek AI Client")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DeepSeek")
    
    # 设置字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    client = DeepSeekClient()
    client.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()