import sys
import os
import ctypes
from git_logic import *
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeView, QFileSystemModel,
                            QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
                            QSplitter, QMessageBox, QLabel, QMenu, QFrame, QTabWidget,
                            QListWidget, QHeaderView, QProgressDialog, QTextEdit)
from PyQt5.QtCore import QDir, QFile, Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap, QImageReader

def run_as_admin():
    if sys.platform == "win32":
        # 관리자 권한으로 실행을 시도
        if ctypes.windll.shell32.IsUserAnAdmin() != 0:
            print("User has admin privileges.")
            return True
        else:
            # 관리자 권한 없이 실행 중이라면 재실행
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit(0)
    return False

# git_push 작업을 위한 스레드 클래스
class GitPushWorker(QThread):
    progress = pyqtSignal(int)  # 진행률 업데이트
    log = pyqtSignal(str)      # 로그 메시지 업데이트
    finished = pyqtSignal()    # 작업 완료

    def run(self):
        self.progress.emit(25)
        exclueded_files = check_file()  # 파일 체크
        self.progress.emit(75)
        git_push(exclueded_files)  # 실제 푸시
        self.progress.emit(100)

class GitPullWorker(QThread):
    progress = pyqtSignal(int)  # 진행률 업데이트
    log = pyqtSignal(str)      # 로그 메시지 업데이트
    finished = pyqtSignal()    # 작업 완료

    def __init__(self, root_path, selected_paths, download_path):
        super().__init__()
        self.root_path = root_path
        self.selected_paths = selected_paths
        self.download_path = download_path

    def run(self):
        self.progress.emit(25)

        self.progress.emit(75)
        git_pull(self.root_path, self.selected_paths, self.download_path)
        self.progress.emit(100)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # data
        self.push_root = None
        self.pull_root = None

        self.setWindowTitle("Github Storage")
        self.setGeometry(100, 100, 800, 600)

        # 중앙 위젯과 레이아웃 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 탭 위젯 추가
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Tree View 탭
        tree_tab = QWidget()
        tree_layout = QHBoxLayout(tree_tab)
        self.tree_splitter = QSplitter(Qt.Horizontal)
        tree_layout.addWidget(self.tree_splitter)

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

        self.tree_right_panel = self.create_tree_right_panel()
        self.tree_splitter.addWidget(self.tree_right_panel)
        # # 로그 표시용 QTextEdit 추가
        # self.log_display = QTextEdit()
        # self.log_display.setReadOnly(True)
        # self.tree_splitter.addWidget(self.log_display)

        self.tree_splitter.setSizes([600, 200])

        # Custom List 탭
        list_tab = QWidget()
        list_layout = QHBoxLayout(list_tab)
        self.list_splitter = QSplitter(Qt.Horizontal)
        list_layout.addWidget(self.list_splitter)

        self.listWidget = QListWidget()
        self.update_custom_list()
        self.list_splitter.addWidget(self.listWidget)

        self.list_right_panel = self.create_list_right_panel()
        self.list_splitter.addWidget(self.list_right_panel)
        self.list_splitter.setSizes([600, 200])

        self.tab_widget.addTab(tree_tab, "File Explorer")
        self.tab_widget.addTab(list_tab, "Custom List")

        # 시그널 연결
        self.treeView.selectionModel().selectionChanged.connect(self.update_tree_remove_button)
        self.treeView.selectionModel().selectionChanged.connect(self.update_tree_file_info)
        self.treeView.activated.connect(self.open_file)
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self.show_context_menu)

        self.listWidget.itemSelectionChanged.connect(self.update_list_remove_button)
        self.listWidget.itemSelectionChanged.connect(self.update_list_file_info)

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        initial_root = self.model.rootPath()
        last_folder = os.path.basename(initial_root)
        self.tree_right_panel.findChild(QLabel, "current_folder_label").setText(f"Current Folder: {last_folder}")
        self.list_right_panel.findChild(QLabel, "current_download_folder_label").setText(f"Current Folder: {last_folder}")

        run_as_admin()
        
    def create_tree_right_panel(self):
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        current_folder_label = QLabel("Current Folder: ")
        current_folder_label.setObjectName("current_folder_label")
        right_layout.addWidget(current_folder_label)

        specify_folder_btn = QPushButton("Specify Folder")
        specify_folder_btn.clicked.connect(self.specify_folder)
        right_layout.addWidget(specify_folder_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_folder)
        right_layout.addWidget(open_folder_btn)

        add_files_btn = QPushButton("Add Files")
        add_files_btn.clicked.connect(self.add_files)
        right_layout.addWidget(add_files_btn)

        remove_selected_btn = QPushButton("Remove Selected")
        remove_selected_btn.setObjectName("remove_selected_btn")
        remove_selected_btn.clicked.connect(self.remove_selected)
        right_layout.addWidget(remove_selected_btn)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(divider)

        git_init_btn = QPushButton("Init Git")
        git_init_btn.setObjectName("git_init_btn")
        git_init_btn.clicked.connect(self.git_init)
        right_layout.addWidget(git_init_btn)

        git_push_btn = QPushButton("Push to Git")
        git_push_btn.clicked.connect(self.async_git_push)  # 비동기 호출로 변경
        right_layout.addWidget(git_push_btn)

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
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        current_folder_label = QLabel("Current Download Folder: ")
        current_folder_label.setObjectName("current_download_folder_label")
        right_layout.addWidget(current_folder_label)

        specify_download_folder_btn = QPushButton("Specify Download Folder")
        specify_download_folder_btn.clicked.connect(self.specify_download_folder)
        right_layout.addWidget(specify_download_folder_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_custom_list)
        right_layout.addWidget(refresh_btn)

        git_pull_btn = QPushButton("Refresh Data")
        git_pull_btn.clicked.connect(self.async_git_pull)
        right_layout.addWidget(git_pull_btn)

        right_layout.addStretch()
        return right_panel

    def update_custom_list(self):
        """커스텀 리스트 업데이트"""
        self.listWidget.clear()
        # root_path = self.model.filePath(self.treeView.rootIndex())

        remote_files = get_file_list_in_remote()
        if remote_files is None:
            return
        for file_name in remote_files:
            self.listWidget.addItem(file_name)

    def specify_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.model.setRootPath(folder)
            self.treeView.setRootIndex(self.model.index(folder))
            last_folder = os.path.basename(folder)
            self.tree_right_panel.findChild(QLabel, "current_folder_label").setText(f"Current Folder: {last_folder}")
            self.push_root = folder
            
            # git 폴더 체크 후 초기화
            # git_init_btn = self.tree_right_panel.findChild(QPushButton, "git_init_btn")
            # if os.path.exists(os.path.join(folder, '.git')):
            #     self.git_init()
            #     if git_init_btn:
            #         git_init_btn.setEnabled(False)
            # else:
            #     if git_init_btn:
            #         git_init_btn.setEnabled(True)

    def specify_download_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            last_folder = os.path.basename(folder)
            self.list_right_panel.findChild(QLabel, "current_download_folder_label").setText(f"Current Download Folder: {last_folder}")
            self.pull_root = folder

    def open_folder(self):
        root_path = self.push_root
        if os.path.isdir(root_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(root_path))
        else:
            QMessageBox.warning(self, "Not a Folder", "Please select a valid folder.")

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            root_path = self.push_root
            for file in files:
                file_name = os.path.basename(file)
                dest_path = os.path.join(root_path, file_name)
                if QFile.exists(dest_path):
                    QMessageBox.information(self, "File Exists", f"File {file_name} already exists.")
                else:
                    if not QFile.copy(file, dest_path):
                        QMessageBox.warning(self, "Error", f"Failed to copy file: {file}")

    def git_init(self):
        init_variables(self.push_root)
        init_git()

    def async_git_push(self):
        """비동기 git push 실행"""
        self.worker = GitPushWorker()
        self.worker.progress.connect(self.update_progress)
        # self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.on_git_push_finished)

        # 진행 대화 상자 표시
        self.progress_dialog = QProgressDialog("Pushing to Git...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.worker.terminate)
        self.progress_dialog.show()

        self.worker.start()

    def async_git_pull(self):
        """비동기 git pull 실행"""
        if not is_git_inited():
            return
        
        download_path = self.pull_root
        # listWidget에서 선택된 항목 가져오기
        selected_items = self.listWidget.selectedItems()
        if not selected_items:
            return

        # 선택된 항목을 파일 경로로 변환 (root_path와 결합)
        selected_paths = [item.text() for item in selected_items]

        # GitPullWorker에 선택된 파일 경로 전달
        self.worker = GitPullWorker(self.push_root, selected_paths, download_path)  # selected_items 대신 selected_paths 전달
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.finished.connect(self.on_git_push_finished)

        # 진행 대화 상자 표시
        self.progress_dialog = QProgressDialog("Pulling from Git...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.worker.terminate)
        self.progress_dialog.show()

        self.worker.start()

    def update_progress(self, value):
        """진행률 업데이트"""
        self.progress_dialog.setValue(value)

    def update_log(self, message):
        """로그 업데이트"""
        ...
        # self.log_display.append(message)

    def on_git_push_finished(self):
        """git push 완료 시 호출"""
        self.progress_dialog.close()
        QMessageBox.information(self, "Git Push", "Push to Git completed!")

    def remove_selected(self):
        current_tab = self.tab_widget.currentIndex()
        if current_tab == 0:  # Tree View 탭
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
        else:  # Custom List 탭
            selected_items = self.listWidget.selectedItems()
            if not selected_items:
                QMessageBox.information(self, "No Selection", "No items selected.")
                return
            reply = QMessageBox.question(self, "Confirm Delete", "Are you sure?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                root_path = self.push_root
                for item in selected_items:
                    file_path = os.path.join(root_path, item.text())
                    if QFile(file_path).remove():
                        self.listWidget.takeItem(self.listWidget.row(item))
                    else:
                        QMessageBox.warning(self, "Error", f"Failed to delete: {file_path}")

    def update_tree_remove_button(self):
        self.tree_right_panel.findChild(QPushButton, "remove_selected_btn").setEnabled(
            self.treeView.selectionModel().hasSelection()
        )

    def update_list_remove_button(self):
        # Custom List 탭에는 "Remove Selected" 버튼이 없으므로 무시
        pass

    def update_tree_file_info(self):
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
        # Custom List 탭에서 file_info_label과 image_preview_label이 제거되었으므로 무시
        pass

    def show_image_preview(self, file_path, preview_label):
        image_reader = QImageReader(file_path)
        if image_reader.canRead():
            pixmap = QPixmap(file_path)
            preview_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))
        else:
            preview_label.clear()

    def open_file(self, index):
        if self.model.isDir(index):
            return
        file_path = self.model.filePath(index)
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def show_context_menu(self, position):
        index = self.treeView.indexAt(position)
        if index.isValid():
            menu = QMenu(self)
            remove_action = menu.addAction("Remove File")
            action = menu.exec_(self.treeView.mapToGlobal(position))
            if action == remove_action:
                file_path = self.model.filePath(index)
                self.remove_file(file_path)

    def remove_file(self, file_path):
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {file_path}?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if QFile.exists(file_path):
                if not QFile(file_path).remove():
                    QMessageBox.warning(self, "Error", f"Failed to delete: {file_path}")
            else:
                QMessageBox.warning(self, "Error", "File not found.")

    def on_tab_changed(self, index):
        if index == 0:
            self.update_tree_remove_button()
            self.update_tree_file_info()
        else:
            self.update_list_remove_button()
            self.update_list_file_info()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())