import sys
import json
import os
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject, QThread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from merger import merge_binaries

if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # extends the sys module by a flag frozen=True
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

LAYOUT_FILE = os.path.join(application_path, "layout_config.json")
STYLE_FILE = os.path.join(application_path, "style.qss")

class ConfigWatcher(QObject):
    config_changed = Signal()

    def __init__(self, watch_dir):
        super().__init__()
        self.watch_dir = watch_dir
        self.observer = Observer()
        
        class Handler(FileSystemEventHandler):
            def __init__(self, signal):
                self.signal = signal
            def on_modified(self, event):
                if event.src_path.endswith(LAYOUT_FILE) or event.src_path.endswith(STYLE_FILE):
                    self.signal.emit()
                    
        self.handler = Handler(self.config_changed)
        self.observer.schedule(self.handler, self.watch_dir, recursive=False)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()

class MergeRow(QWidget):
    removed = Signal(object)

    def __init__(self, ratios):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("選擇目標文件...")
        self.path_input.setReadOnly(True)
        
        self.offset_input = QLineEdit()
        self.offset_input.setPlaceholderText("偏移(如 0x1000) 留空自動接續")
        
        self.select_btn = QPushButton("選擇")
        self.select_btn.clicked.connect(self.browse_file)
        
        layout.addWidget(self.path_input, ratios.get("path_ratio", 3))
        layout.addWidget(self.offset_input, ratios.get("offset_ratio", 1))
        layout.addWidget(self.select_btn, ratios.get("button_ratio", 1))
        
        self.remove_btn = QPushButton("刪除")
        self.remove_btn.setObjectName("deleteBtn")
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self.remove_btn, ratios.get("button_ratio", 1))
            
        self.setLayout(layout)
        
    def browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "選擇二進制文件", "", "Binary Files (*.bin);;All Files (*.*)")
        if filepath:
            self.path_input.setText(filepath)

    def get_data(self):
        path = self.path_input.text().strip()
        offset_str = self.offset_input.text().strip()
        if not path:
            return None
            
        if not offset_str:
            offset = None # None means auto-append
        else:
            try:
                offset = int(offset_str, 16) if offset_str.startswith("0x") else int(offset_str)
            except ValueError:
                return None
        return {"path": path, "offset": offset}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.rows = []
        
        self.init_ui()
        self.load_config()
        self.load_style()
        
        self.watcher = ConfigWatcher(application_path)
        self.watcher.config_changed.connect(self.reload_ui)
        
    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        title = QLabel("二進制文件合併工具", self)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)
        

        # Targets Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area)
        
        # Add target button
        self.add_btn = QPushButton("添加目標文件")
        self.add_btn.clicked.connect(self.add_target_row)
        self.main_layout.addWidget(self.add_btn)
        
        # Process controls
        self.process_layout = QHBoxLayout()
        self.merge_btn = QPushButton("開始合併")
        self.merge_btn.clicked.connect(self.run_merge)
        self.process_layout.addWidget(self.merge_btn)
        self.main_layout.addLayout(self.process_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)
        
        # Debug Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.main_layout.addWidget(self.console)
        
    def add_target_row(self):
        ratios = self.config.get("merge_row", {})
        row = MergeRow(ratios)
        row.removed.connect(self.remove_target_row)
        self.scroll_layout.addWidget(row)
        self.rows.append(row)
        
    def remove_target_row(self, row):
        self.scroll_layout.removeWidget(row)
        row.deleteLater()
        if row in self.rows:
            self.rows.remove(row)
            
    def load_config(self):
        try:
            with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)
                
            win_conf = self.config.get("window", {})
            self.resize(win_conf.get("width", 800), win_conf.get("height", 600))
            self.setWindowTitle(win_conf.get("title", "Binary Merger"))
            
            vis_conf = self.config.get("visibility", {})
            self.progress_bar.setVisible(vis_conf.get("progress_bar", True))
            self.console.setVisible(vis_conf.get("debug_console", True))
            

            
            self.log("配置已加載 (Config loaded).")
        except Exception as e:
            self.log(f"加載配置失敗: {str(e)}")

    def load_style(self):
        try:
            with open(STYLE_FILE, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
            self.log("樣式已加載 (Style loaded).")
        except Exception as e:
            self.log(f"加載樣式失敗: {str(e)}")

    def reload_ui(self):
        # Watchdog triggers might be in a different thread, use QMetaObject.invokeMethod if needed
        # But for simplicity, direct call usually works if not manipulating core UI loops heavily
        # Better safe:
        self.load_config()
        self.load_style()

    def log(self, text):
        self.console.append(text)

    def run_merge(self):
        self.progress_bar.setValue(0)
        self.log("開始合併...")
        
        if not self.rows:
            QMessageBox.warning(self, "錯誤", "請至少提供一個目標文件！")
            return
            
        targets = []
        for row in self.rows:
            data = row.get_data()
            if data:
                targets.append(data)
            else:
                self.log("警告: 有目標文件未提供完整路徑或偏移，已跳過。")
        
        if not targets:
            QMessageBox.warning(self, "錯誤", "請至少提供一個有效的目標文件！")
            return
                
        # Pre-flight Check for Overlaps
        # Simulate offsets to check if an overlap will occur
        import os
        total_header_size = 0x20 + (len(targets) * 0x50)
        current_offset = total_header_size
        
        intervals = []
        overlaps_detected = []
        
        for idx, target in enumerate(targets):
            filepath = target["path"]
            offset = target.get("offset", 0)
            try:
                size = os.path.getsize(filepath)
            except OSError:
                self.log(f"無法讀取文件大小，跳過預先檢查: {filepath}")
                continue
                
            if offset is None:
                offset = max(current_offset, total_header_size)
            elif offset < total_header_size:
                offset = total_header_size
                
            end_offset = offset + size
            
            # Check against previous intervals
            for prev_idx, prev_start, prev_end, prev_path in intervals:
                # If intervals intersect: (StartA < EndB) and (EndA > StartB)
                if offset < prev_end and end_offset > prev_start:
                    overlaps_detected.append(
                        f"• {os.path.basename(prev_path)} 與 {os.path.basename(filepath)} \n"
                        f"  (位址: 0x{prev_start:X}~0x{prev_end:X} 和 0x{offset:X}~0x{end_offset:X})"
                    )
            
            intervals.append((idx, offset, end_offset, filepath))
            current_offset = end_offset

        if overlaps_detected:
            msg = "偵測到以下目標文件的寫入位址發生重疊：\n\n" + "\n".join(overlaps_detected) + "\n\n較後方的文件將會覆蓋前方的內容，是否繼續？"
            reply = QMessageBox.question(self, '重疊警告', msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.log("已取消合併。")
                return

        save_path, _ = QFileDialog.getSaveFileName(self, "保存合併文件", "", "Binary Files (*.bin)")
        if not save_path:
            self.log("已取消保存。")
            return
            
        try:
            header_sz, total_sz = merge_binaries(targets, save_path)
            self.progress_bar.setValue(100)
            self.log(f"合併成功！保存至: {save_path}")
            self.log(f"標頭大小: 0x{header_sz:X}, 總大小: 0x{total_sz:X}")
            QMessageBox.information(self, "成功", "文件合併完成！")
        except Exception as e:
            self.log(f"合併失敗: {traceback.format_exc()}")
            QMessageBox.critical(self, "錯誤", f"合併時發生錯誤:\n{str(e)}")

    def closeEvent(self, event):
        self.watcher.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
