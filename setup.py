import sys
import os
import shutil
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                              QWidget, QLabel, QPushButton, QProgressBar, QFileDialog,
                              QMessageBox, QCheckBox, QStackedWidget)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon

class SetupWindow(QMainWindow):
    def __init__(self, mode="install"):
        super().__init__()
        self.setWindowTitle("DeepSeek-Desktop 安装/卸载程序")
        self.setFixedSize(600, 400)
        
        # 主部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        # 模式选择
        self.mode = mode
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)
        
        # 初始化界面
        if self.mode == "install":
            self.init_install_ui()
        else:
            self.init_uninstall_ui()
    
    def init_install_ui(self):
        """初始化安装界面"""
        install_widget = QWidget()
        layout = QVBoxLayout(install_widget)
        
        # 标题
        title = QLabel("DeepSeek-Desktop 安装向导")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 安装路径选择
        path_layout = QHBoxLayout()
        path_label = QLabel("安装路径:")
        path_layout.addWidget(path_label)
        
        self.path_edit = QLabel("C:\\Program Files\\DeepSeek-Desktop")
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
        
        self.stacked_widget.addWidget(install_widget)
        self.stacked_widget.setCurrentIndex(0)
        
        # 初始化变量
        self.source_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.source_dir = os.path.join(self.source_dir, "dist", "DeepSeek-Desktop")
    
    def init_uninstall_ui(self):
        """初始化卸载界面"""
        uninstall_widget = QWidget()
        layout = QVBoxLayout(uninstall_widget)
        
        # 标题
        title = QLabel("DeepSeek-Desktop 卸载向导")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 安装路径显示
        self.uninstall_path_label = QLabel()
        layout.addWidget(self.uninstall_path_label)
        
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
        
        self.stacked_widget.addWidget(uninstall_widget)
        self.stacked_widget.setCurrentIndex(0)
        
        # 加载安装信息
        self.load_uninstall_info()
    
    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装目录", "C:\\Program Files")
        if path:
            self.path_edit.setText(os.path.join(path, "DeepSeek-Desktop"))
    
    def start_installation(self):
        """开始安装"""
        # 检查源目录是否存在
        if not os.path.exists(self.source_dir):
            QMessageBox.critical(self, "错误", "找不到安装源文件！")
            return
            
        # 系统检查
        if not self.system_check():
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
        self.worker.error.connect(self.show_error)
        self.worker.start()
    
    def start_uninstall(self):
        """开始卸载"""
        if not hasattr(self, 'install_path') or not os.path.exists(self.install_path):
            QMessageBox.critical(self, "错误", "找不到安装目录！")
            return
            
        # 确认对话框
            reply = QMessageBox.question(
              self,
              "确认卸载",
              "确定要卸载 DeepSeek-Desktop 吗？",
              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
          )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        # 启动卸载线程
        self.worker = UninstallWorker(self.install_path)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.uninstall_complete)
        self.worker.error.connect(self.show_error)
        self.worker.start()
    
    def load_uninstall_info(self):
        """加载卸载信息"""
        # 尝试从默认位置查找安装信息
        default_path = "C:\\Program Files\\DeepSeek-Desktop"
        info_file = os.path.join(default_path, "uninstall.json")
        
        if os.path.exists(info_file):
            try:
                with open(info_file) as f:
                    info = json.load(f)
                self.install_path = info["install_path"]
                self.uninstall_path_label.setText(f"安装路径: {self.install_path}")
                return
            except:
                pass
        
        # 如果找不到默认安装，让用户选择
        path = QFileDialog.getExistingDirectory(self, "选择DeepSeek-Desktop安装目录")
        if path:
            info_file = os.path.join(path, "uninstall.json")
            if os.path.exists(info_file):
                try:
                    with open(info_file) as f:
                        info = json.load(f)
                    self.install_path = info["install_path"]
                    self.uninstall_path_label.setText(f"安装路径: {self.install_path}")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法读取安装信息:\n{str(e)}")
            else:
                QMessageBox.critical(self, "错误", "找不到安装信息文件！")
    
    def update_progress(self, value):
        self.progress.setValue(value)
    
    def installation_complete(self):
            reply = QMessageBox.question(
            self,
            "安装完成",
            "安装成功完成！\n\n是否要立即启动 DeepSeek-Desktop？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes :
            self.launch_application()
            
        self.close()
        
    def launch_application(self):
        """启动应用程序"""
        try:
            exe_path = os.path.join(self.path_edit.text(), "DeepSeek-Desktop.exe")
            if os.path.exists(exe_path):
                os.startfile(exe_path)
            else:
                QMessageBox.warning(self, "警告", "找不到应用程序可执行文件！")
        except Exception as e:
            QMessageBox.warning(self, "启动错误", f"无法启动应用程序:\n{str(e)}")
    
    def uninstall_complete(self):
        QMessageBox.information(self, "完成", "卸载成功完成！")
        self.close()
    
    def show_error(self, message):
        QMessageBox.critical(self, "错误", message)

    def system_check(self):
        """系统环境检查"""
        try:
            # 检查磁盘空间
            target_drive = os.path.splitdrive(self.path_edit.text())[0]
            total, used, free = shutil.disk_usage(target_drive)
            required_space = 500 * 1024 * 1024  # 500MB
            
            if free < required_space:
                QMessageBox.critical(
                    self,
                    "磁盘空间不足",
                    f"目标驱动器 {target_drive} 空间不足！\n"
                    f"需要: {required_space//(1024*1024)}MB, "
                    f"可用: {free//(1024*1024)}MB"
                )
                return False
                
            # 检查Python版本
            if sys.version_info < (3, 7):
                QMessageBox.critical(
                    self,
                    "Python版本过低",
                    "需要Python 3.7或更高版本！"
                )
                return False
                
            return True
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "系统检查错误",
                f"系统检查时发生错误:\n{str(e)}\n\n将继续安装..."
            )
            return True

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
            exe_path = os.path.join(self.target_dir, "DeepSeek-Desktop.exe")
            
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
        from datetime import datetime
        info = {
            "install_path": self.target_dir,
            "installed_files": [],
            "install_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uninstaller": os.path.join(self.target_dir, "uninstall.exe"),
            "executable": os.path.join(self.target_dir, "DeepSeek-Desktop.exe")
        }
        
        # 记录所有安装的文件
        for root, _, files in os.walk(self.target_dir):
            for file in files:
                info["installed_files"].append(os.path.join(root, file))
                
        # 创建卸载程序快捷方式
        try:
            import winshell
            from win32com.client import Dispatch
            
            programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
            shortcut_path = os.path.join(programs, "DeepSeek-Desktop 卸载程序.lnk")
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{sys.argv[0]}" --uninstall "{self.target_dir}"'
            shortcut.WorkingDirectory = self.target_dir
            shortcut.IconLocation = os.path.join(self.target_dir, "DeepSeek-Desktop.exe")
            shortcut.save()
            
        except Exception:
            pass  # 忽略快捷方式创建错误
            
        with open(os.path.join(self.target_dir, "uninstall.json"), "w") as f:
            json.dump(info, f)

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
            desktop_shortcut = os.path.join(desktop, "DeepSeek-Desktop.lnk")
            if os.path.exists(desktop_shortcut):
                os.remove(desktop_shortcut)
                
            # 删除开始菜单快捷方式
            programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
            start_menu_shortcut = os.path.join(programs, "DeepSeek-Desktop.lnk")
            if os.path.exists(start_menu_shortcut):
                os.remove(start_menu_shortcut)
                
            # 删除卸载程序快捷方式
            uninstall_shortcut = os.path.join(programs, "DeepSeek-Desktop 卸载程序.lnk")
            if os.path.exists(uninstall_shortcut):
                os.remove(uninstall_shortcut)
                
        except ImportError:
            pass  # 忽略缺少依赖的错误
        except Exception as e:
            raise Exception(f"删除快捷方式失败: {str(e)}")

if __name__ == "__main__":
    # 解析命令行参数
    mode = "install"
    install_path = None
    
    if "--uninstall" in sys.argv:
        mode = "uninstall"
        try:
            install_path = sys.argv[sys.argv.index("--uninstall") + 1]
        except IndexError:
            pass
    
    app = QApplication(sys.argv)
    window = SetupWindow(mode)
    
    # 如果是从卸载快捷方式启动，设置安装路径
    if mode == "uninstall" and install_path:
        window.install_path = install_path
        window.uninstall_path_label.setText(f"安装路径: {install_path}")
    
    window.show()
    sys.exit(app.exec())
