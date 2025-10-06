import sys
import os
import shutil
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                              QWidget, QLabel, QPushButton, QProgressBar, QFileDialog,
                              QMessageBox, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon

class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSeek-Windows客户端安装程序")
        self.setFixedSize(600, 400)
        
        # 主部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("CherryStudio 安装向导")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 安装路径选择
        path_layout = QHBoxLayout()
        self.path_label = QLabel("安装路径:")
        path_layout.addWidget(self.path_label)
        
        self.path_edit = QLabel("C:\\Program Files\\CherryStudio")
        self.path_edit.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
        path_layout.addWidget(self.path_edit)
        
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)
        
        # 选项
        self.desktop_shortcut = QCheckBox("创建桌面快捷方式")
        self.desktop_shortcut.setChecked(True)
        layout.addWidget(self.desktop_shortcut)
        
        self.start_menu_shortcut = QCheckBox("添加到开始菜单")
        self.start_menu_shortcut.setChecked(True)
        layout.addWidget(self.start_menu_shortcut)
        
        # 进度条
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("安装")
        self.install_btn.clicked.connect(self.start_installation)
        btn_layout.addWidget(self.install_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        # 初始化变量
        self.source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.source_dir = os.path.join(self.source_dir, "dist", "CherryStudio_v1.0")
        
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装目录", "C:\\Program Files")
        if path:
            self.path_edit.setText(os.path.join(path, "CherryStudio"))
    
    def start_installation(self):
        # 检查源目录是否存在
        if not os.path.exists(self.source_dir):
            QMessageBox.critical(self, "错误", "找不到安装源文件！")
            return
            
        # 创建目标目录
        target_dir = self.path_edit.text()
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法创建安装目录:\n{str(e)}")
            return
            
        # 启动安装线程
        self.worker = InstallWorker(self.source_dir, target_dir, 
                                  self.desktop_shortcut.isChecked(),
                                  self.start_menu_shortcut.isChecked())
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.installation_complete)
        self.worker.error.connect(self.installation_error)
        self.worker.start()
        
    def update_progress(self, value):
        self.progress.setValue(value)
        
    def installation_complete(self):
        QMessageBox.information(self, "完成", "安装成功完成！")
        self.close()
        
    def installation_error(self, message):
        QMessageBox.critical(self, "错误", message)

class InstallWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, source_dir, target_dir, create_desktop, create_start_menu):
        super().__init__()
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.create_desktop = create_desktop
        self.create_start_menu = create_start_menu
        
    def run(self):
        try:
            # 计算总文件大小用于进度显示
            total_size = 0
            file_list = []
            
            for root, dirs, files in os.walk(self.source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                    file_list.append((root, file))
            
            copied_size = 0
            self.progress.emit(0)
            
            # 复制文件
            for root, file in file_list:
                src = os.path.join(root, file)
                rel_path = os.path.relpath(root, self.source_dir)
                dst_dir = os.path.join(self.target_dir, rel_path)
                dst = os.path.join(dst_dir, file)
                
                # 确保目标目录存在
                os.makedirs(dst_dir, exist_ok=True)
                
                # 复制文件并更新进度
                try:
                    shutil.copy2(src, dst)
                    copied_size += os.path.getsize(src)
                    progress = int((copied_size / total_size) * 100)
                    self.progress.emit(progress)
                except Exception as e:
                    self.error.emit(f"无法复制文件 {file}: {str(e)}")
                    return
            
            # 创建快捷方式
            if self.create_desktop:
                self.create_shortcut("desktop")
                
            if self.create_start_menu:
                self.create_shortcut("startmenu")
                
            # 保存安装信息
            self.save_installation_info()
            
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"安装过程中出错:\n{str(e)}")
    
    def create_shortcut(self, shortcut_type):
        try:
            import winshell
            from win32com.client import Dispatch
            
            # 获取可执行文件路径
            exe_path = os.path.join(self.target_dir, "CherryStudio_v1.0.exe")
            
            if shortcut_type == "desktop":
                # 桌面快捷方式
                desktop = winshell.desktop()
                shortcut_path = os.path.join(desktop, "CherryStudio.lnk")
            else:
                # 开始菜单快捷方式
                programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
                shortcut_path = os.path.join(programs, "CherryStudio.lnk")
            
            # 创建快捷方式
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = exe_path
            shortcut.WorkingDirectory = self.target_dir
            shortcut.IconLocation = exe_path
            shortcut.save()
            
        except ImportError:
            self.error.emit("无法创建快捷方式: 缺少必要的依赖库 (pywin32)")
            return
        except Exception as e:
            self.error.emit(f"创建快捷方式失败: {str(e)}")
            return
        
    def save_installation_info(self):
        info = {
            "install_path": self.target_dir,
            "installed_files": [],
            "install_date": "2025-10-06",  # 应该使用datetime.now()
            "uninstaller": os.path.join(self.target_dir, "uninstall.exe")
        }
        
        # 记录所有安装的文件
        for root, _, files in os.walk(self.target_dir):
            for file in files:
                info["installed_files"].append(os.path.join(root, file))
                
        # 创建卸载程序
        uninstaller_path = os.path.join(self.target_dir, "uninstall.exe")
        shutil.copy2(os.path.join(os.path.dirname(__file__), "uninstaller.py"), 
                    os.path.join(self.target_dir, "uninstaller.py"))
        
        # 创建卸载程序快捷方式
        try:
            import winshell
            from win32com.client import Dispatch
            
            programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
            shortcut_path = os.path.join(programs, "CherryStudio 卸载程序.lnk")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{os.path.join(self.target_dir, "uninstaller.py")}" "{self.target_dir}"'
            shortcut.WorkingDirectory = self.target_dir
            shortcut.IconLocation = os.path.join(self.target_dir, "CherryStudio_v1.0.exe")
            shortcut.save()
            
        except Exception:
            pass  # 忽略快捷方式创建错误
            
        with open(os.path.join(self.target_dir, "uninstall.json"), "w") as f:
            json.dump(info, f)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())