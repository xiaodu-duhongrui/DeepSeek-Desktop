from datetime import datetime
from PySide6.QtGui import QTextCursor

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