from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QGroupBox, 
                             QFormLayout, QLineEdit, QLabel, QCheckBox, QComboBox,
                             QDoubleSpinBox, QSpinBox, QSlider, QHBoxLayout, QPushButton,
                             QMessageBox, QProgressDialog)
from PySide6.QtCore import Qt
from threading import Thread
from queue import Queue
from openai import OpenAI

from .api_key_manager import DEFAULT_BASE_URL, DEFAULT_API_KEY

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
        builtin_info = QLabel(f"内置免费API: {DEFAULT_API_KEY[:10]}...{DEFAULT_API_KEY[-6:]}")
        builtin_info.setStyleSheet("color: #10b981; font-weight: bold; background: #f0fdf4; padding: 8px; border-radius: 5px;")
        api_base_layout.addRow("内置密钥:", builtin_info)
        
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