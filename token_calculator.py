import re

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