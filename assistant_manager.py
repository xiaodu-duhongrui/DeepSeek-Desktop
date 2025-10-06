from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QSettings

class AssistantCategory(Enum):
    GENERAL = "通用"
    CODE = "编程"
    WRITING = "写作"
    RESEARCH = "研究"
    CREATIVE = "创意"
    ACADEMIC = "学术"
    BUSINESS = "商业"

@dataclass
class AssistantConfig:
    id: str
    name: str
    description: str
    category: AssistantCategory
    provider: str
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000
    is_preset: bool = True
    custom_api: bool = False
    custom_base_url: Optional[str] = None
    custom_api_key: Optional[str] = None

class AssistantManager:
    """管理预设和自定义助手"""
    
    def __init__(self):
        self.settings = QSettings("DeepSeek", "AI Assistants")
        self.preset_assistants = self._load_preset_assistants()
        self.custom_assistants = self._load_custom_assistants()
    
    def _load_preset_assistants(self) -> Dict[str, AssistantConfig]:
        """加载预设助手"""
        presets = []
        presets_path = Path(__file__).parent / "presets" / "assistants.json"
        
        try:
            with open(presets_path, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            # 如果预设文件不存在，使用内置默认助手
            presets = [{
                "id": "default",
                "name": "默认助手",
                "description": "通用AI助手",
                "category": "GENERAL",
                "provider": "deepseek",
                "model": "deepseek-chat",
                "system_prompt": "你是一个乐于助人的AI助手",
                "temperature": 0.7,
                "max_tokens": 2000
            }]
        
        return {a["id"]: AssistantConfig(**a) for a in presets}
    
    def _load_custom_assistants(self) -> Dict[str, AssistantConfig]:
        """加载自定义助手"""
        custom = self.settings.value("custom_assistants", [])
        return {a["id"]: AssistantConfig(**a) for a in custom}
    
    def get_all_assistants(self) -> List[AssistantConfig]:
        """获取所有助手"""
        return list(self.preset_assistants.values()) + list(self.custom_assistants.values())
    
    def get_assistant(self, assistant_id: str) -> Optional[AssistantConfig]:
        """根据ID获取助手配置"""
        if assistant_id in self.preset_assistants:
            return self.preset_assistants[assistant_id]
        return self.custom_assistants.get(assistant_id)
    
    def create_custom_assistant(self, config: dict) -> AssistantConfig:
        """创建自定义助手"""
        config["is_preset"] = False
        assistant = AssistantConfig(**config)
        self.custom_assistants[assistant.id] = assistant
        self._save_custom_assistants()
        return assistant
    
    def update_custom_assistant(self, assistant_id: str, config: dict) -> Optional[AssistantConfig]:
        """更新自定义助手"""
        if assistant_id not in self.custom_assistants:
            return None
        
        assistant = AssistantConfig(**config)
        self.custom_assistants[assistant_id] = assistant
        self._save_custom_assistants()
        return assistant
    
    def delete_custom_assistant(self, assistant_id: str) -> bool:
        """删除自定义助手"""
        if assistant_id in self.custom_assistants:
            del self.custom_assistants[assistant_id]
            self._save_custom_assistants()
            return True
        return False
    
    def _save_custom_assistants(self):
        """保存自定义助手到设置"""
        custom = [a.__dict__ for a in self.custom_assistants.values()]
        self.settings.setValue("custom_assistants", custom)