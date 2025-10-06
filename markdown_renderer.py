import markdown
from PySide6.QtWebEngineWidgets import QWebEngineView

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