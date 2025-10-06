import os
import sys
import json
import shutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                              QLabel, QPushButton, QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal

class UninstallerWindow(QMainWindow):
    def __init__(self, install_path):
        super().__init__()
        self.setWindowTitle("CherryStudio 卸载程序")
        self.setFixedSize(500, 300)
        self.install_path = install_path
        
        # 主部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 标题
        title = QLabel("CherryStudio 卸载向导")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 安装路径显示
        path_label = QLabel(f"安装路径: {install_path}")
        layout.addWidget(path_label)
        
        # 进度条
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        
        # 按钮
        btn_layout = QHBoxLayout()
        self.uninstall_btn = QPushButton("卸载")
        self.uninstall_btn.clicked.connect(self.start_uninstall)
        btn_layout.addWidget(self.uninstall_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
    def start_uninstall(self):
        # 启动卸载线程
        self.worker = UninstallWorker(self.install_path)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.uninstall_complete)
        self.worker.error.connect(self.uninstall_error)
        self.worker.start()
        
    def update_progress(self, value):
        self.progress.setValue(value)
        
    def uninstall_complete(self):
        QMessageBox.information(self, "完成", "卸载成功完成！")
        self.close()
        
    def uninstall_error(self, message):
        QMessageBox.critical(self, "错误", message)

class UninstallWorker(QThread):
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, install_path):
        super().__init__()
        self.install_path = install_path
        
    def run(self):
        try:
            # 加载安装信息
            info_file = os.path.join(self.install_path, "uninstall.json")
            if not os.path.exists(info_file):
                self.error.emit("找不到卸载信息文件！")
                return
                
            with open(info_file) as f:
                info = json.load(f)
            
            # 删除文件
            total_files = len(info["installed_files"])
            deleted_files = 0
            
            for file_path in info["installed_files"]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    deleted_files += 1
                    self.progress.emit(int((deleted_files / total_files) * 100))
                except Exception as e:
                    self.error.emit(f"无法删除文件 {file_path}: {str(e)}")
                    return
            
            # 删除快捷方式
            self.remove_shortcuts()
            
            # 删除安装目录
            try:
                shutil.rmtree(self.install_path)
            except Exception as e:
                self.error.emit(f"无法删除安装目录: {str(e)}")
                return
                
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"卸载过程中出错:\n{str(e)}")
    
    def remove_shortcuts(self):
        try:
            import winshell
            
            # 删除桌面快捷方式
            desktop = winshell.desktop()
            desktop_shortcut = os.path.join(desktop, "CherryStudio.lnk")
            if os.path.exists(desktop_shortcut):
                os.remove(desktop_shortcut)
                
            # 删除开始菜单快捷方式
            programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
            start_menu_shortcut = os.path.join(programs, "CherryStudio.lnk")
            if os.path.exists(start_menu_shortcut):
                os.remove(start_menu_shortcut)
                
        except ImportError:
            pass  # 忽略缺少依赖的错误
        except Exception as e:
            raise Exception(f"删除快捷方式失败: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请提供安装路径作为参数")
        sys.exit(1)
        
    app = QApplication(sys.argv)
    window = UninstallerWindow(sys.argv[1])
    window.show()
    sys.exit(app.exec())