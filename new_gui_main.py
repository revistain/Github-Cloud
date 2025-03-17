# -*- coding: utf-8 -*-
import os
import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeView, QFileSystemModel,
                            QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
                            QSplitter, QMessageBox, QLabel, QMenu, QFrame, QTabWidget,
                            QListWidget, QProgressDialog, QCheckBox, QLineEdit)
from PyQt5.QtCore import QDir, QFile, Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap, QImageReader
from PyQt5.QtCore import QSettings
from new_git_logic import GitManager
from utils import *

# Worker thread for Git push operations
class GitPushWorker(QThread):
    progress = pyqtSignal(int)  # Progress update signal
    log = pyqtSignal(str)      # Log message update signal
    finished = pyqtSignal()    # Operation completion signal

    def __init__(self, gitManager):
        super().__init__()
        self.gitManager = gitManager
    
    def run(self):
        self.progress.emit(25)
        self.progress.emit(75)
        self.gitManager.push()
        self.progress.emit(100)

# Worker thread for Git pull operations
class GitPullWorker(QThread):
    progress = pyqtSignal(int)  # Progress update signal
    log = pyqtSignal(str)      # Log message update signal
    finished = pyqtSignal()    # Operation completion signal

    def __init__(self, gitManager, selected_paths, download_path):
        super().__init__()
        self.gitManager = gitManager
        self.selected_paths = selected_paths
        self.download_path = download_path

    def run(self):
        self.progress.emit(10)
        self.gitManager.get_file(self.selected_paths, self.download_path, show_process=True, progress=self.progress)
        self.progress.emit(100)

class GitRefreshWorker(QThread):
    progress = pyqtSignal(int)  # Progress update signal
    log = pyqtSignal(str)      # Log message update signal
    finished = pyqtSignal()    # Operation completion signal

    def __init__(self, gitManager, listWidget):
        super().__init__()
        self.gitManager = gitManager
        self.listWidget = listWidget
    
    def run(self):
        self.progress.emit(10)
        self.update_custom_list()
        self.progress.emit(100)
        
    def update_custom_list(self):
        """Update the Custom List with remote files."""
        self.listWidget.clear()
        if self.gitManager is None:
            return
        self.progress.emit(60)
        remote_files = self.gitManager.get_remote_file_list()
        self.progress.emit(85)
        if remote_files is None:
            return
        for file_name in remote_files:
            self.listWidget.addItem(file_name)
        self.progress.emit(100)

# Main application window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize data
        self.push_root = None
        self.pull_root = None
        self.gitManager = None  # Initialized later when push_root is set
        
        # 설정 불러오기
        self.setting_panel = QWidget()
        self.gitpub_pat_input = QLineEdit()
        self.gitpub_url_input = QLineEdit()
        
        self.setWindowTitle("Github Storage")
        self.setGeometry(100, 100, 800, 600)

        # Set up central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Add tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- File Explorer Tab (Tree View) ---
        tree_tab = QWidget()
        tree_layout = QHBoxLayout(tree_tab)
        self.tree_splitter = QSplitter(Qt.Horizontal)
        tree_layout.addWidget(self.tree_splitter)

        # Set up QTreeView
        self.treeView = QTreeView()
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.homePath())
        self.model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)
        self.treeView.setModel(self.model)
        self.treeView.setRootIndex(self.model.index(QDir.homePath()))
        self.treeView.setColumnWidth(0, 250)
        self.treeView.setColumnHidden(1, True)
        self.treeView.setColumnHidden(2, True)
        self.treeView.setColumnHidden(3, True)
        self.treeView.setSelectionMode(QTreeView.ExtendedSelection)
        self.tree_splitter.addWidget(self.treeView)
        
        # Add right panel for Tree View
        self.tree_right_panel = self.create_tree_right_panel()
        self.tree_splitter.addWidget(self.tree_right_panel)
        self.tree_splitter.setSizes([600, 200])

        # --- Custom List Tab ---
        list_tab = QWidget()
        list_layout = QHBoxLayout(list_tab)
        self.list_splitter = QSplitter(Qt.Horizontal)
        list_layout.addWidget(self.list_splitter)

        # Set up QListWidget
        self.listWidget = QListWidget()
        self.listWidget.setSelectionMode(QListWidget.MultiSelection)  # Enable multi-selection
        self.listWidget.setDragEnabled(True)  # Enable drag
        self.list_splitter.addWidget(self.listWidget)

        # Add right panel for Custom List
        self.list_right_panel = self.create_list_right_panel()
        self.list_splitter.addWidget(self.list_right_panel)
        self.list_splitter.setSizes([600, 200])
        
        # --- Setting List Tab ---
        setting_tab = QWidget()
        setting_list_layout = QHBoxLayout(setting_tab)
        self.setting_list_splitter = QSplitter(Qt.Horizontal)
        setting_list_layout.addWidget(self.setting_list_splitter)

        # Set up QListWidget
        # self.listWidget = QListWidget()
        # self.listWidget.setSelectionMode(QListWidget.MultiSelection)  # Enable multi-selection
        # self.listWidget.setDragEnabled(True)  # Enable drag
        # self.setting_list_splitter.addWidget(self.listWidget)

        # Add right panel for Custom List
        self.setting_list_right_panel = self.create_setting_panel()
        self.setting_list_splitter.addWidget(self.setting_list_right_panel)
        self.setting_list_splitter.setSizes([600, 200])

        ############################################
        # Add tabs to tab widget
        self.tab_widget.addTab(tree_tab, "Local Files")
        self.tab_widget.addTab(list_tab, "Remote Files")
        self.tab_widget.addTab(setting_tab, "Settings")
        
        # Connect signals
        self.treeView.selectionModel().selectionChanged.connect(self.update_tree_remove_button)
        self.treeView.selectionModel().selectionChanged.connect(self.update_tree_file_info)
        self.treeView.activated.connect(self.open_file)
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.show_context_menu)
        self.listWidget.itemSelectionChanged.connect(self.update_list_remove_button)
        self.listWidget.itemSelectionChanged.connect(self.update_list_file_info)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Initialize labels
        # self.tree_right_panel.findChild(QLabel, "current_folder_label").setText("Current Folder: Not Set")
        self.list_right_panel.findChild(QLabel, "current_download_folder_label").setText("Current Download Folder: Not Set")
        
        # settings 
        self.load_settings()
        if self.push_root is not None:
            self.gitManager = GitManager(self.push_root)
            self.model.setRootPath(self.push_root)
            self.treeView.setRootIndex(self.model.index(self.push_root))
        self.save_settings()

    def save_settings(self):
        """현재 설정을 JSON 파일에 저장합니다."""
        settings = {
            "GitpubURL": self.gitpub_url_input.text(),
            "GitpubPAT": self.gitpub_pat_input.text(),
            "PushRoot": self.push_root,
            "PullRoot": self.pull_root
        }
        with open("settings.json", "w") as f:
            json.dump(settings, f)
            
        user, repo = is_proper_SSH_url(self.gitpub_url_input.text())
        pat = is_valid_github_pat(self.gitpub_pat_input.text())
        if user and repo and pat:
            if self.gitManager:
                self.gitManager.set_repo_url(git_user=user, git_repo=repo, git_pat=pat)

    def load_settings(self):
        """JSON 파일에서 설정을 불러와 UI에 반영합니다."""
        try:
            print("Loading settings from settings.json...")
            with open("settings.json", "r") as f:
                settings = json.load(f)
                self.gitpub_url_input.setText(settings.get("GitpubURL", ""))
                self.gitpub_pat_input.setText(settings.get("GitpubPAT", ""))
                self.push_root = settings.get("PushRoot", "")
                self.pull_root = settings.get("PullRoot", "")
                if self.push_root:
                    last_folder = self.push_root.split("/")[-1] or self.push_root
                    self.setting_panel.findChild(QLabel, "current_folder_label").setText(f"Folder To Upload: {last_folder}")
                if self.pull_root:
                    print("self.pull_root: ", self.pull_root)
                    last_folder = self.pull_root.split("/")[-1] or self.pull_root
                    self.list_right_panel.findChild(QLabel, "current_download_folder_label").setText(f"Current Download Folder: {last_folder}")
        except FileNotFoundError as e:
            print(f"설정 파일을 찾을 수 없습니다: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON 파일 형식이 잘못되었습니다: {e}")
        except Exception as e:
            print(f"설정 불러오기 중 오류 발생: {e}")
            
    def create_tree_right_panel(self):
        """Create the right panel for the File Explorer tab."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_folder)
        right_layout.addWidget(open_folder_btn)

        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(self.add_files)
        right_layout.addWidget(add_files_btn)

        remove_selected_btn = QPushButton("Remove Selected Files")
        remove_selected_btn.setObjectName("remove_selected_btn")
        remove_selected_btn.clicked.connect(self.remove_selected)
        right_layout.addWidget(remove_selected_btn)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(divider)

        git_push_btn = QPushButton("Upload to Git")
        git_push_btn.clicked.connect(self.async_git_push)
        right_layout.addWidget(git_push_btn)
        
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(divider)


        file_info_label = QLabel("")
        file_info_label.setObjectName("file_info_label")
        file_info_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(file_info_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(divider)

        image_preview_label = QLabel("")
        image_preview_label.setObjectName("image_preview_label")
        image_preview_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(image_preview_label)

        return right_panel

    def create_list_right_panel(self):
        """Create the right panel for the Custom List tab."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        current_folder_label = QLabel("Current Download Folder: Not Set")
        current_folder_label.setObjectName("current_download_folder_label")
        right_layout.addWidget(current_folder_label)

        specify_download_folder_btn = QPushButton("Specify Download Folder")
        specify_download_folder_btn.clicked.connect(self.specify_download_folder)
        right_layout.addWidget(specify_download_folder_btn)

        refresh_btn = QPushButton("Refresh Files List")
        refresh_btn.clicked.connect(self.async_refresh_list)
        right_layout.addWidget(refresh_btn)

        git_pull_btn = QPushButton("Download Selected Files")
        git_pull_btn.clicked.connect(self.async_git_pull)
        right_layout.addWidget(git_pull_btn)

        right_layout.addStretch()
        return right_panel
    
    def create_setting_panel(self):
        """Create the right panel for the Custom List tab."""
        setting_layout = QVBoxLayout(self.setting_panel)

        # Folder 추가
        folder_layout = QHBoxLayout()
        current_folder_label = QLabel("Folder To Upload: Not Set")
        current_folder_label.setObjectName("current_folder_label")
        folder_layout.addWidget(current_folder_label)

        specify_folder_btn = QPushButton("Specify Folder")
        specify_folder_btn.clicked.connect(self.specify_folder)
        folder_layout.addWidget(specify_folder_btn)

        folder_widget = QWidget()
        folder_widget.setLayout(folder_layout)
        setting_layout.addWidget(folder_widget)
        
        # Gitpub URL 설정 추가
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Gitpub URL:"))
        self.gitpub_url_input.textChanged.connect(self.save_settings)
        url_layout.addWidget(self.gitpub_url_input)
        setting_layout.addLayout(url_layout)

        # Gitpub PAT 설정 추가 (체크박스 포함)
        pat_layout = QHBoxLayout()
        pat_layout.addWidget(QLabel("Gitpub PAT:"))
        
        self.gitpub_pat_input.textChanged.connect(self.save_settings)
        pat_layout.addWidget(self.gitpub_pat_input)
        self.hide_pat_checkbox = QCheckBox("Hide PAT")
        pat_layout.addWidget(self.hide_pat_checkbox)
        setting_layout.addLayout(pat_layout)

        # PAT 입력 필드 초기 상태 설정 (기본적으로 숨김)
        self.gitpub_pat_input.setEchoMode(QLineEdit.Password)
        self.hide_pat_checkbox.setChecked(True)

        # 체크박스 상태 변경 시 토글 함수 연결
        self.hide_pat_checkbox.stateChanged.connect(self.toggle_pat_visibility)

        explain_label = QLabel(""" 
            1. Create an empty private repository (for storage purposes).

            2. Provide the repository's SSH URL in the URL input field.
                - Example: GitHub URL: git@github.com:revistain/testStorage.git

            3. Generate a GitHub Personal Access Token (PAT)
                from the "Fine-grained personal access tokens" section in GitHub's developer settings.
                (For security, ensure that the PAT is only accessible to the storage repository created above.)
                - Example: GitHub PAT: github_pat_ABCDEF~~

            CAUTION!: If you set a directory that has already been git-initialized as the storage folder,
                        IT WILL ERASE THE ENTIRE GIT HISTORY!
        """)
        setting_layout.addWidget(explain_label)
        
        # 여백 추가 (Spacing)
        setting_layout.addStretch()

        return self.setting_panel

    def toggle_pat_visibility(self, state):
        """체크박스 상태에 따라 PAT 입력 필드의 표시를 토글합니다."""
        if state == Qt.Checked:
            self.gitpub_pat_input.setEchoMode(QLineEdit.Password)  # *****로 표시
        else:
            self.gitpub_pat_input.setEchoMode(QLineEdit.Normal)    # 일반 텍스트로 표시

    def async_refresh_list(self):
        self.worker = GitRefreshWorker(self.gitManager, self.listWidget)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.on_git_push_finished)

        self.progress_dialog = QProgressDialog("Refreshing from Git...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.worker.terminate)
        self.progress_dialog.show()

        self.worker.start()

    def specify_folder(self):
        """Specify the directory for the File Explorer tab."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.model.setRootPath(folder)
            self.treeView.setRootIndex(self.model.index(folder))
            last_folder = os.path.basename(folder)
            self.setting_list_right_panel.findChild(QLabel, "current_folder_label").setText(f"Folder To Upload: {last_folder}")
            self.push_root = folder
            # Initialize GitManager with the selected push_root
            self.gitManager = GitManager(self.push_root)
            self.save_settings() 

    def specify_download_folder(self):
        """Specify the download directory for the Custom List tab."""
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            last_folder = os.path.basename(folder)
            self.list_right_panel.findChild(QLabel, "current_download_folder_label").setText(f"Current Download Folder: {last_folder}")
            self.pull_root = folder
            self.save_settings() 

    def open_folder(self):
        """Open the current push_root folder in the file explorer."""
        if self.push_root is None:
            QMessageBox.warning(self, "Error", "Please specify a folder first.")
            return
        if os.path.isdir(self.push_root):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.push_root))
        else:
            QMessageBox.warning(self, "Not a Folder", "Please select a valid folder.")

    def add_files(self):
        """Add files to the push_root directory."""
        if self.push_root is None:
            QMessageBox.warning(self, "Error", "Please specify a folder first.")
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            for file in files:
                file_name = os.path.basename(file)
                dest_path = os.path.join(self.push_root, file_name)
                if QFile.exists(dest_path):
                    QMessageBox.information(self, "File Exists", f"File {file_name} already exists.")
                else:
                    if not QFile.copy(file, dest_path):
                        QMessageBox.warning(self, "Error", f"Failed to copy file: {file}")

    def async_git_push(self):
        """Asynchronously push files to Git."""
        if self.push_root is None or self.gitManager is None:
            QMessageBox.warning(self, "Error", "Please specify a folder first.")
            return
        self.worker = GitPushWorker(self.gitManager)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_git_push_finished)

        self.progress_dialog = QProgressDialog("Pushing to Git...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.worker.terminate)
        self.progress_dialog.show()

        self.worker.start()

    def async_git_pull(self):
        """Asynchronously pull selected files from Git."""
        if self.pull_root is None:
            QMessageBox.warning(self, "Error", "Please specify a download folder first.")
            return
        download_path = self.pull_root
        selected_items = self.listWidget.selectedItems()
        if not selected_items:
            return

        selected_paths = [item.text() for item in selected_items]
        self.worker = GitPullWorker(self.gitManager, selected_paths, download_path)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.on_git_push_finished)

        self.progress_dialog = QProgressDialog("Pulling from Git...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.worker.terminate)
        self.progress_dialog.show()

        self.worker.start()

    def update_progress(self, value):
        """Update the progress dialog."""
        self.progress_dialog.setValue(value)

    def update_log(self, message):
        """Placeholder for log updates (not implemented)."""
        pass

    def on_git_push_finished(self):
        """Handle completion of Git operations."""
        self.progress_dialog.close()
        QMessageBox.information(self, "Git Operation", "Operation completed!")

    def remove_selected(self):
        """Remove selected items from the current tab."""
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # File Explorer tab
            selected_rows = self.treeView.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.information(self, "No Selection", "No items selected.")
                return
            reply = QMessageBox.question(self, "Confirm Delete", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                for index in selected_rows:
                    path = self.model.filePath(index)
                    if self.model.isDir(index):
                        if not QDir(path).removeRecursively():
                            QMessageBox.warning(self, "Error", f"Failed to delete: {path}")
                    else:
                        if not QFile(path).remove():
                            QMessageBox.warning(self, "Error", f"Failed to delete: {path}")
        else:  # Custom List tab
            selected_items = self.listWidget.selectedItems()
            if not selected_items:
                QMessageBox.information(self, "No Selection", "No items selected.")
                return
            reply = QMessageBox.question(self, "Confirm Delete", "Are you sure?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                for item in selected_items:
                    file_path = os.path.join(self.push_root, item.text())
                    if QFile(file_path).remove():
                        self.listWidget.takeItem(self.listWidget.row(item))
                    else:
                        QMessageBox.warning(self, "Error", f"Failed to delete: {file_path}")

    def update_tree_remove_button(self):
        """Enable/disable the Remove Selected button in the File Explorer tab."""
        self.tree_right_panel.findChild(QPushButton, "remove_selected_btn").setEnabled(
            self.treeView.selectionModel().hasSelection()
        )

    def update_list_remove_button(self):
        """Placeholder (no Remove Selected button in Custom List tab)."""
        pass

    def update_tree_file_info(self):
        """Update file info and image preview in the File Explorer tab."""
        selected_indexes = self.treeView.selectionModel().selectedIndexes()
        file_info_label = self.tree_right_panel.findChild(QLabel, "file_info_label")
        image_preview_label = self.tree_right_panel.findChild(QLabel, "image_preview_label")
        if selected_indexes:
            index = selected_indexes[0]
            file_info = self.model.fileInfo(index)
            file_name = file_info.fileName()
            created_time = file_info.created().toString("yyyy-MM-dd HH:mm:ss")
            file_info_label.setText(f"File: {file_name}\nCreated: {created_time}")
            self.show_image_preview(file_info.absoluteFilePath(), image_preview_label)
        else:
            file_info_label.setText("Select a file to see details")
            image_preview_label.clear()

    def update_list_file_info(self):
        """Placeholder (no file info in Custom List tab)."""
        pass

    def show_image_preview(self, file_path, preview_label):
        """Show an image preview if the file is an image."""
        image_reader = QImageReader(file_path)
        if image_reader.canRead():
            pixmap = QPixmap(file_path)
            preview_label.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio))
        else:
            preview_label.clear()

    def open_file(self, index):
        """Open a file when double-clicked in the File Explorer tab."""
        if self.model.isDir(index):
            return
        file_path = self.model.filePath(index)
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def show_context_menu(self, position):
        """Show a context menu for the File Explorer tab."""
        index = self.treeView.indexAt(position)
        if index.isValid():
            menu = QMenu(self)
            remove_action = menu.addAction("Remove File")
            action = menu.exec_(self.treeView.mapToGlobal(position))
            if action == remove_action:
                file_path = self.model.filePath(index)
                self.remove_file(file_path)

    def remove_file(self, file_path):
        """Remove a file after confirmation."""
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {file_path}?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if QFile.exists(file_path):
                if not QFile(file_path).remove():
                    QMessageBox.warning(self, "Error", f"Failed to delete: {file_path}")
            else:
                QMessageBox.warning(self, "Error", "File not found.")

    def on_tab_changed(self, index):
        """Update UI elements when switching tabs."""
        if index == 0:
            self.update_tree_remove_button()
            self.update_tree_file_info()
        else:
            self.update_list_remove_button()
            self.update_list_file_info()

    # Drag and drop event handlers
    def dragEnterEvent(self, event):
        """Handle drag enter event for the drop area."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Handle drag move event for the drop area."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle drop event for the drop area."""
        if event.mimeData().hasText():
            file_names = event.mimeData().text().split('\n')  # List of dragged file names
            if not self.pull_root:
                QMessageBox.warning(self, "Error", "Please specify a download folder first.")
                return
            
            download_path = self.pull_root
            for file_name in file_names:
                if file_name:  # Skip empty strings
                    self.gitManager.get_file([file_name], download_path)  # Download file
            
            QMessageBox.information(self, "Download Complete", "Files downloaded successfully!")
            event.acceptProposedAction()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
