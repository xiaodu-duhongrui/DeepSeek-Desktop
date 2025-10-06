import hashlib
import base64
import os
from PySide6.QtCore import QSettings
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.backends import default_backend

# 内置免费API配置
DEFAULT_API_KEY = "sk-eea642f2d36e46509907b8ce8caa4ba3"
DEFAULT_BASE_URL = "https://api.deepseek.com"

class SecureAPIKeyManager:
    """安全的API密钥管理器 - 使用AES加密存储（使用cryptography库）"""
    
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
        
        # 创建新的加密密钥 (32 bytes for AES-256)
        new_key = os.urandom(32)
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
        
        # 创建SHA256哈希并取前32字节作为密钥
        hash_obj = hashes.Hash(hashes.SHA256(), backend=default_backend())
        hash_obj.update(device_info.encode())
        return hash_obj.finalize()
    
    def _encrypt_with_device_key(self, data):
        """使用设备密钥加密数据"""
        device_key = self._get_device_fingerprint()
        iv = os.urandom(16)  # AES块大小
        
        # 创建加密器
        cipher = Cipher(algorithms.AES(device_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # 填充数据
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # 加密
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # 返回 IV + 密文
        return base64.b64encode(iv + ciphertext).decode()
    
    def _decrypt_with_device_key(self, encrypted_data):
        """使用设备密钥解密数据"""
        try:
            device_key = self._get_device_fingerprint()
            data = base64.b64decode(encrypted_data)
            
            # 提取IV和密文
            iv = data[:16]
            ciphertext = data[16:]
            
            # 创建解密器
            cipher = Cipher(algorithms.AES(device_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # 解密
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # 去除填充
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
            return plaintext
        except Exception as e:
            raise ValueError("解密失败，可能是设备环境变化") from e
    
    def _encrypt_api_key(self, api_key):
        """加密API密钥"""
        iv = os.urandom(16)  # AES块大小
        
        # 创建加密器
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # 填充数据
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(api_key.encode('utf-8')) + padder.finalize()
        
        # 加密
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # 返回 IV + 密文
        return base64.b64encode(iv + ciphertext).decode()
    
    def _decrypt_api_key(self, encrypted_api_key):
        """解密API密钥"""
        try:
            data = base64.b64decode(encrypted_api_key)
            
            # 提取IV和密文
            iv = data[:16]
            ciphertext = data[16:]
            
            # 创建解密器
            cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            # 解密
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # 去除填充
            unpadder = padding.PKCS7(128).unpadder()
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            
            return plaintext.decode('utf-8')
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
            
            # 如果没有找到任何密钥，返回默认密钥
            return DEFAULT_API_KEY
            
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