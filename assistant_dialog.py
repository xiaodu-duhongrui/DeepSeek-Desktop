from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QLabel, 
    QDialogButtonBox, QHBoxLayout, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QTextEdit, QDoubleSpinBox, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from .assistant_manager import AssistantManager, AssistantCategory

class AssistantDialog(QDialog):
    """助手选择与配置对话框"""
    assistant_selected = Signal(str)  # 发射选中的助手ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = AssistantManager()
        self.setup_ui()
        
    def setup_ui(self):
        """初始化UI"""
        self.setWindowTitle("选择AI助手")
        self.setMinimumSize(800, 600)
        
        main_layout = QVBoxLayout(self)
        
        # 助手列表区域
        self.assistant_list = QListWidget()
        self.assistant_list.itemDoubleClicked.connect(self.accept_selection)
        self.populate_assistant_list()
        
        # 助手详情区域
        detail_group = QGroupBox("助手详情")
        detail_layout = QFormLayout(detail_group)
        
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.category_combo = QComboBox()
        self.category_combo.addItems([c.value for c in AssistantCategory])
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["deepseek", "openai", "gemini", "anthropic", "ollama"])
        self.model_edit = QLineEdit()
        self.prompt_edit = QTextEdit()
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0, 2)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 32000)
        self.max_tokens_spin.setValue(2000)
        
        detail_layout.addRow("名称:", self.name_edit)
        detail_layout.addRow("描述:", self.description_edit)
        detail_layout.addRow("类别:", self.category_combo)
        detail_layout.addRow("提供商:", self.provider_combo)
        detail_layout.addRow("模型:", self.model_edit)
        detail_layout.addRow("系统提示:", self.prompt_edit)
        detail_layout.addRow("温度:", self.temperature_spin)
        detail_layout.addRow("最大Token数:", self.max_tokens_spin)

        # 自定义API设置
        custom_api_group = QGroupBox("自定义API设置")
        custom_api_layout = QFormLayout(custom_api_group)
        
        self.custom_api_check = QCheckBox("使用自定义API")
        self.custom_api_check.stateChanged.connect(self.toggle_custom_api_fields)
        custom_api_layout.addRow(self.custom_api_check)
        
        self.custom_base_url_edit = QLineEdit()
        self.custom_base_url_edit.setPlaceholderText("https://api.example.com")
        custom_api_layout.addRow("Base URL:", self.custom_base_url_edit)
        
        self.custom_api_key_edit = QLineEdit()
        self.custom_api_key_edit.setPlaceholderText("sk-...")
        self.custom_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        custom_api_layout.addRow("API Key:", self.custom_api_key_edit)
        
        detail_layout.addRow(custom_api_group)
        
        # 按钮区域
        button_box = QDialogButtonBox()
        self.select_button = QPushButton("选择")
        self.select_button.clicked.connect(self.accept_selection)
        self.new_button = QPushButton("新建")
        self.new_button.clicked.connect(self.create_new_assistant)
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_assistant)
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_assistant)
        button_box.addButton(self.select_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(self.new_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(self.save_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(self.delete_button, QDialogButtonBox.ButtonRole.ActionRole)
        
        # 主布局
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.assistant_list, 1)
        content_layout.addWidget(detail_group, 2)
        
        main_layout.addLayout(content_layout)
        main_layout.addWidget(button_box)
        
        # 连接信号
        self.assistant_list.currentItemChanged.connect(self.show_assistant_details)
        
    def populate_assistant_list(self):
        """填充助手列表"""
        self.assistant_list.clear()
        for assistant in self.manager.get_all_assistants():
            self.assistant_list.addItem(f"{assistant.name} ({assistant.category})")
    
    def show_assistant_details(self, current, previous):
        """显示选中助手的详细信息"""
        if not current:
            return
            
        index = self.assistant_list.row(current)
        assistant = self.manager.get_all_assistants()[index]
        
        self.name_edit.setText(assistant.name)
        self.description_edit.setPlainText(assistant.description)
        self.category_combo.setCurrentText(assistant.category.value)
        self.provider_combo.setCurrentText(assistant.provider)
        self.model_edit.setText(assistant.model)
        self.prompt_edit.setPlainText(assistant.system_prompt)
        self.temperature_spin.setValue(assistant.temperature)
        self.max_tokens_spin.setValue(assistant.max_tokens)
        
        # 自定义API设置
        self.custom_api_check.setChecked(getattr(assistant, 'custom_api', False))
        self.custom_base_url_edit.setText(getattr(assistant, 'custom_base_url', ''))
        self.custom_api_key_edit.setText(getattr(assistant, 'custom_api_key', ''))
        self.toggle_custom_api_fields()
        
        # 根据是否是预设助手启用/禁用控件
        is_preset = assistant.is_preset
        self.name_edit.setEnabled(not is_preset)
        self.description_edit.setEnabled(not is_preset)
        self.category_combo.setEnabled(not is_preset)
        self.provider_combo.setEnabled(not is_preset)
        self.model_edit.setEnabled(not is_preset)
        self.prompt_edit.setEnabled(not is_preset)
        self.custom_api_check.setEnabled(not is_preset)
        self.custom_base_url_edit.setEnabled(not is_preset and self.custom_api_check.isChecked())
        self.custom_api_key_edit.setEnabled(not is_preset and self.custom_api_check.isChecked())
        self.save_button.setEnabled(not is_preset)
        self.delete_button.setEnabled(not is_preset)
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(not is_preset)
        self.toggle_custom_api_fields()
    
    def accept_selection(self):
        """接受当前选择的助手"""
        current = self.assistant_list.currentItem()
        if current:
            index = self.assistant_list.row(current)
            assistant = self.manager.get_all_assistants()[index]
            self.assistant_selected.emit(assistant.id)
            self.accept()
    
    def create_new_assistant(self):
        """创建新助手"""
        self.name_edit.clear()
        self.description_edit.clear()
        self.category_combo.setCurrentIndex(0)
        self.provider_combo.setCurrentIndex(0)
        self.model_edit.clear()
        self.prompt_edit.clear()
        self.temperature_spin.setValue(0.7)
        self.max_tokens_spin.setValue(2000)
        self.custom_api_check.setChecked(False)
        self.custom_base_url_edit.clear()
        self.custom_api_key_edit.clear()
        self.toggle_custom_api_fields()
        
        # 启用所有控件
        for widget in [
            self.name_edit, self.description_edit, self.category_combo,
            self.provider_combo, self.model_edit, self.prompt_edit
        ]:
            widget.setEnabled(True)
        
        self.save_button.setEnabled(True)
        self.delete_button.setEnabled(False)
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
        self.custom_api_check.setEnabled(True)
        self.toggle_custom_api_fields()
    
    def save_assistant(self):
        """保存助手配置"""
        config = {
            "id": f"custom_{len(self.manager.custom_assistants) + 1}",
            "name": self.name_edit.text(),
            "description": self.description_edit.toPlainText(),
            "category": self.category_combo.currentText(),
            "provider": self.provider_combo.currentText(),
            "model": self.model_edit.text(),
            "system_prompt": self.prompt_edit.toPlainText(),
            "temperature": self.temperature_spin.value(),
            "max_tokens": self.max_tokens_spin.value(),
            "custom_api": self.custom_api_check.isChecked(),
            "custom_base_url": self.custom_base_url_edit.text() if self.custom_api_check.isChecked() else None,
            "custom_api_key": self.custom_api_key_edit.text() if self.custom_api_check.isChecked() else None
        }
        
        self.manager.create_custom_assistant(config)
        self.populate_assistant_list()
    
    def delete_assistant(self):
        """删除当前助手"""
        current = self.assistant_list.currentItem()
        if current:
            index = self.assistant_list.row(current)
            assistant = self.manager.get_all_assistants()[index]
            if not assistant.is_preset:
                self.manager.delete_custom_assistant(assistant.id)
                self.populate_assistant_list()