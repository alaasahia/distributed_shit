from typing import Callable
from PyQt5.QtWidgets import QApplication, QWidget, QFrame, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QScrollArea, QLabel, QGridLayout, QMenu, QFileDialog, QDialog, QTableWidget, QTableWidgetItem
from PyQt5.QtGui import QPixmap, QIcon, QMovie
from PyQt5.QtCore import QSize, Qt, QObject, pyqtSignal as Signal, QThread
from c import FileManager, Union, logging
from rpyc.utils.server import ThreadedServer
import sys
import os

class FileDeletionListenerWorker(QObject):
    def __init__(self, listener):
        super().__init__()
        self.listener = listener

    def run(self):
        self.listener()


class FileDeletionCheckerWorker(QObject):
    delete = Signal(str)
    def __init__(self, target) -> None:
        super().__init__()
        self.target = target


    def run(self):
        while True:
            if self.target:
                for file in self.target[0]:
                    self.delete.emit(file)
                self.target.pop()


class FileAdditionListenerWorker(QObject):
    def __init__(self,listener):
        super().__init__()
        self.listener = listener

    def run(self):
        self.listener()

class FileAdditionCheckerWorker(QObject):
    finished = Signal(bool, str, bool)
    def __init__(self,target):
        super().__init__()
        self.target = target
    
    def run(self):
        while True:
            if self.target:
                print('target:', self.target) 
                for file in self.target[0]:
                    self.finished.emit(True, file,False)
                self.target.pop()

class GeneralWorker(QObject):
    def __init__(self, func: Callable):
        super().__init__()
        self.func: Callable = func
        self.run()

    def run(self):
        print('start database server it started really')
        self.func()

class Worker(QObject):
    finished = Signal(bool, str)
    finished_without_args =  Signal(list)
    def __init__(self, func: Callable, args = None):
        super().__init__()
        print('init database server thread')
        print('args',func, args)
        self.func = func
        self.args = args

    def run(self):
        status = None
        if self.args:
            status = self.func(self.args)
            self.finished.emit(status, self.args[0])
        else:
            print('running function in worker', self.func)
            files = self.func()
            self.finished_without_args.emit(files)            

class FileAdditionWorker(QObject):
    finished = Signal(bool, list, bool)
    def __init__(self, op, name):
        super().__init__()
        self.op = op
        self.name = name

    def run(self):
        status = self.op(self.name)
        self.finished.emit(status, [os.path.basename(self.name[0])], False)

class FileManagerWorker(QObject):
    def __init__(self, instance):
        super().__init__()
        self.instance = instance

    def run(self):
        print('file manager thread started')
        ThreadedServer(self.instance, port=self.instance.socket_port).start()

class FileDownloadWorker(QObject):
    finished = Signal(bool)
    progress = Signal(int)
    def __init__(self, queue, func, args):
        self.queue = queue
        self.func = func
        self.args = args

    def run(self):
        status = self.func(self.args)
        self.finished.emit(status)

class FileRenameWorker(QObject):
    finished = Signal(bool)
    def __init__(self, func, args):
        self.func = func
        self.args = args

    def run(self):
        status = self.func(self.args)
        self.finished.emit(status)

class FileDeletionWorker(QObject):
    finished = Signal(bool)
    def __init__(self, func, args):
        super().__init__()
        self.func = func
        self.args = args

    def run(self):
        status = self.func(self.args)
        self.finished.emit(status)


class Loading(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation = QMovie('loading.gif')
        self.setMovie(self.animation)
        self.start()

    def start(self):
        self.animation.start()

    def stop(self):
        self.animation.stop()


class TextFileReview(QLabel):
    def __init__(self):
        super().__init__()
        self.init()
        self.movie()

    def init(self):
        pass


class FileListItemOptions(QTableWidgetItem):
    def __init__(self, is_local):
        super().__init__()
        

class FileDescriptionListItem(QLabel):
    def __init__(self, is_local):
        super().__init__()
        self._layout = QHBoxLayout()
        self._open = QPushButton()
        self._save = QPushButton()
        self._delete = QPushButton()


class FileNameListItem(QTableWidgetItem):
    def __init__(self, icon, name, is_local = True) -> None:
        super().__init__()
        icon = QIcon(QPixmap(icon))
        self.setIcon(icon)
        self.name = name
        self.is_local = is_local
        self.setText(name)
        
        # self.to_save = to_save
        # self.rename = to_rename
        # self.to_delete = to_delete
        # self.properties = properites

    def contextMenuEvent(self, event) -> None:
        print('context_menu')
        

    def rename(self, new_name):
        pass
    def finish_file_dowload(self, status):
        pass

    def increase_progress(self, progress):
        pass

    def rename(self):
        pass
    def init(self):
        self._icon.setScaledContents(True)
        self.name.setStyleSheet('color:white;')
        self.setMaximumHeight(50)
        self.layout.addWidget(self._icon)
        self.layout.addWidget(self.name)
        self.layout.addStretch()
        self.layout.setSpacing(0)

class _FilesList(QTableWidget):
    def __init__(self, *args):
        self.selected_item = None
        super().__init__(*args)
        self.delete_thread = None
        self.delete_worker = None
        self.save_thread = None
        self.save_worker = None


    def contextMenuEvent(self, event) -> None:
        print('context menu triggered')
        qmenu = QMenu(self)
        qmenu.setStyleSheet('border: 1px solid white; color:white;')
        open = qmenu.addAction('open')
        rename = qmenu.addAction('rename')
        delete = qmenu.addAction('delete')
        properties = qmenu.addAction('properites')
        save = None
        target_item = self.itemAt(event.pos())
        self.selected_item = target_item
        # if not self.is_local:
        #     save = qmenu.addAction('save')
        if not target_item.is_local:
            save = qmenu.addAction('save')
        action = qmenu.exec_(self.mapToGlobal(event.pos()))
        if action == save:
            #copy changes
            self.save_worker = Worker(func = self.parent().file_manager.get_shared_file,args = target_item.name)
            self.save_worker.finished.connect(self.finish_download_file)
            #worker.progress.connect(self.increase_progress)
            self.save_thread = QThread()
            self.save_worker.moveToThread(self.save_thread)
            self.save_thread.started.connect(self.save_worker.run)
            self.save_thread.start()

        # if action == open:
        #     pass

        # elif action == rename:
        #     dialog = QDialog()
        #     layout = QVBoxLayout(dialog)
        #     edit = QTextEdit()
        #     apply_button = QPushButton()
        #     layout.addWidget(edit)
        #     layout.addWidget(apply_button)
        #     dialog.exec_()
        #     new_name = None
        #     worker = FileRenameWorker(self.parent().file_manager.rename_file(self.name, new_name))
            
        elif action == delete:
            self.delete_worker = FileDeletionWorker(self.parent().file_manager.remove_files, args=[target_item.name])
            self.delete_worker.finished.connect(self.finish_file_delete)
            self.delete_thread = QThread()
            self.delete_worker.moveToThread(self.delete_thread)
            self.delete_thread.started.connect(self.delete_worker.run)
            self.delete_thread.start()

        # elif action == properties:
        #     pass

    def finish_download_file(self, status):
        print('finishing download file')
        if status:
            icon = QIcon(QPixmap('files.png'))
            self.selected_item.setIcon(icon)
    

    def finish_file_delete(self, status):
        if status:
            self.removeRow(self.selected_item.row())
            self.delete_thread.quit()


    def remove_file(self, name):
        pass



class FilesList(QFrame):
    def __init__(self):
        super().__init__()
        self.file_manager = FileManager('files')  
        self.file_manager_thread = QThread()
        self.file_manager_worker = FileManagerWorker(self.file_manager)
        self.file_manager.connect_to_database()
        self.file_manager_worker.moveToThread(self.file_manager_thread)
        self.file_manager_thread.started.connect(self.file_manager_worker.run)
        self.file_manager_thread.start()
        self.file_addition_listener_thread = QThread()

        #handling the database query execution function
        logging.info('attempting to start the database execution server')
        self.database_query_server_thread = QThread()
        self.database_query_server_worker = GeneralWorker(self.file_manager.start_database_server)
        self.database_query_server_worker.moveToThread(self.database_query_server_thread)
        self.database_query_server_thread.start()
        # self.file_addition_listener_worker = FileAdditionListenerWorker(self.file_manager.listen_for_new_files)
        # self.file_addition_listener_worker.moveToThread(self.file_addition_listener_thread)
        # self.file_addition_listener_thread.started.connect(self.file_addition_listener_worker.run)
        #self.file_addition_listener_thread.start()

        # self.file_addition_checker_thread = QThread()
        # self.file_addition_checker_worker = FileAdditionCheckerWorker(self.file_manager.added_files)
        # self.file_addition_checker_worker.moveToThread(self.file_addition_checker_thread)
        # self.file_addition_checker_worker.finished.connect(self.finish_add_file)
        # self.file_addition_checker_thread.started.connect(self.file_addition_checker_worker.run)
        # self.file_addition_checker_thread.start()

        # self.file_deletion_listener_thread = QThread()
        # self.file_deletion_listener_worker = FileDeletionListenerWorker(self.file_manager.listen_for_deleted_files)
        # self.file_deletion_listener_worker.moveToThread(self.file_deletion_listener_thread)
        # self.file_deletion_listener_thread.started.connect(self.file_deletion_listener_worker.run)
        # self.file_deletion_listener_thread.start()

        # self.file_deletion_checker_thread = QThread()
        # self.file_deletion_checker_worker = FileDeletionCheckerWorker(self.file_manager.deleted_files)
        # self.file_deletion_checker_worker.delete.connect(self.delete_file)
        # self.file_deletion_checker_worker.moveToThread(self.file_deletion_checker_thread)
        # self.file_deletion_checker_thread.started.connect(self.file_deletion_checker_worker.run)
        # self.file_deletion_checker_thread.start()

        #a thread to to add a file to the database
        self.new_file_thread: QThread = QThread()
        #a worker that handles adding files to the database
        self.new_file_worker: Union[FileAdditionWorker, None] = None
        self.shared_file_thread = None
        self.shared_files_worker = None
        self.local_files_wroker = None
        self.local_files_thread = None 

        self.filemanager_server_thread = QThread()
        self.filemanager_server_worker = Worker(self.file_manager.start_server, args = None)
        self.filemanager_server_worker.moveToThread(self.file_manager_thread)
        self.file_manager_thread.started.connect(self.filemanager_server_worker.run)
        self.file_manager_thread.start()
        self.layout = QVBoxLayout()
        self._list = _FilesList(self)
        self._list.setColumnCount(100)
        self._list.setSortingEnabled(True)
        # self.layout.setAlignment(Qt.AlignmentFlag.Align)
        self.row = 0
        self.init()

    def init(self):
        self._list.setColumnWidth(0, 400)
        self._list.setColumnWidth(1, 500)
        self._list.setColumnWidth(2, 500)
        # self._list.setRowCount(3)
        # self._list.insertRow(1)
        # self._list.setCellWidget(1,1, QLabel('   asdfsdfsd'))
        self._list.setHorizontalHeaderLabels(['name','type','options'])
        # self._list.setVerticalHeaderLabels([''])
        self._list.setStyleSheet('color:white;')
        self._list.setMinimumSize(1200,600)
        #self._list.setMaximumSize(499, 400)
        self.layout.addWidget(self._list)
        self.layout.setSpacing(-200)
        self.setMinimumHeight(550)
        #self._area.setWidget(self)
        # s  = 3
        # for i in range(10):
        #     self.add_item('files.png',f'new file {i}', True)
        # self.shared_files_worker = Worker(self.file_manager.get_shared_files_list, None)
        # self.shared_file_thread = QThread()
        # print('shared files thread:', self.shared_file_thread)
        # self.shared_files_worker.moveToThread(self.shared_file_thread)
        # print('shared files thread:', self.shared_file_thread)
        # self.shared_files_worker.finished_without_args.connect(self.load_shared_files)
        # self.shared_file_thread.started.connect(self.shared_files_worker.run)
        # self.shared_file_thread.start()
        """
        take care of the local thread first
        """
        # self.local_files_thread = QThread()
        # self.local_files_wroker = Worker(self.file_manager.get_local_files, None)
        # self.local_files_wroker.moveToThread(self.local_files_thread)
        # self.local_files_wroker.finished_without_args.connect(self.load_local_files)
        # self.local_files_thread.started.connect(self.local_files_wroker.run)
        # self.local_files_thread.start()


    def delete_file(self, name):
        matching_item = self._list.findItems(name)

        if matching_item:
            row = matching_item[0].row()
            self._list.removeRow(row)

    #add files to the database
    def add_file(self) -> None:
        file_name = QFileDialog.getOpenFileName(self,'choose a file')
        print('file name:', file_name[0])
        if file_name[0]:
            logging.info(f"adding file f{file_name[0]} to the database")
            file_name = file_name[0]
            self.new_file_thread = QThread()
            self.new_file_worker = FileAdditionWorker(self.file_manager.add_files, [file_name])
            self.new_file_worker.finished.connect(self.finish_add_file)
            self.new_file_thread.started.connect(self.new_file_worker.run)
            self.new_file_thread.start()

    #execute specific tasks after finishing the file addition process
    #such as add the file to be visible in the ui
    def finish_add_file(self, status: bool, name: str, is_local: bool) -> None:
        logging.info(f"file {name} has been added successfully")
        #the icon of the file item
        icon: Union[str, None] = None
        if is_local:
            icon = 'files.png'
        else:
            icon = 'cloud_file.png'
        self._list.insertRow(self._list.rowCount())
        if isinstance(name, list):
            name = name[0]
        file_item: FileNameListItem = FileNameListItem(icon,name=name, is_local=is_local)
        self._list.setItem(self._list.rowCount() - 1,0, file_item)
        self.row += 1
        if self.new_file_thread:
            self.new_file_thread.quit()

    def load_shared_files(self, files):
        print('loading files', files)
        for file in files:
            print(f'shared file {file[0]}:{self.file_manager.get_local_file(file[0])}')
            #if not self.file_manager.get_local_file(file[0]):
            self.finish_add_file(True, file[0], is_local = False)
        self.shared_file_thread.quit()

    def load_local_files(self, files):
        print('loading local files:', files)
        for file in files:
            self.finish_add_file(True, file[0], is_local=True)

        

class SearchBar(QFrame):
    def __init__(self):
        super().__init__()
        self._bar = QTextEdit()
        self.search_button = QPushButton()
        self.add_file = QPushButton()
        self.layout = QHBoxLayout(self)
        self._bar.setStyleSheet('background-color:#1f2424; color:white; line-height:50px')
  
        self.init()


    def init(self):
        self._bar.setMaximumHeight(50)
        pixmap = QPixmap('search.png')
        self.search_button.setIcon(QIcon(pixmap))
        self.search_button.setMaximumSize(70, 50)
        self.search_button.setIconSize(QSize(50,50))
        self.search_button.setStyleSheet('border:none')
        pixmap = QPixmap('add.png')
        self.add_file.setIcon(QIcon(pixmap))
        self.add_file.setMaximumSize(70,50)
        self.add_file.setIconSize(QSize(50,50))
        self.add_file.setStyleSheet('border:none')
        self.layout.addWidget(self._bar)
        self.layout.addWidget(self.search_button)
        self.layout.addWidget(self.add_file)

class SideBar(QFrame):
    def __init__(self):
        super().__init__()
        self._files_button = QPushButton()
        self.setMaximumWidth(70)
        self.settings = QPushButton()
        self.layout = QVBoxLayout(self)
        self.init()

    def init(self):
        files_pix = QPixmap("files.png")
        self._files_button.setIcon(QIcon(files_pix))
        self._files_button.setMinimumSize(50,50)
        self._files_button.setIconSize(QSize(50,50))
        self._files_button.setStyleSheet('border:none')
        settings_pix = QPixmap('settings.png')
        self.settings.setIcon(QIcon(settings_pix))
        self.settings.setMinimumSize(50,50)
        self.settings.setIconSize(QSize(50,50))
        self.settings.setStyleSheet('border:none')
        self.setStyleSheet('background-color:#2a2b30')
        self.layout.addWidget(self._files_button)
        self.layout.addWidget(self.settings)
        self.layout.addStretch()
        self.layout.setSpacing(20)


class FilesWindow(QFrame):
    def __init__(self):
        super().__init__()
        #self.file_manager = FileManager()
        self.search_bar = SearchBar()
        self._list = FilesList()
        self.loading = Loading()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignJustify)
        self.setStyleSheet('background-color:#2d2d31')
        self.init()


            

    def show_message(self, message, warning = False):
        dialog = QDialog(self)
        message = QLabel(message)
        accept_button = QPushButton('ok')
        layout = QVBoxLayout()
        pixmap = None
        if warning:
            pixmap = QPixmap('warning.png')
        else:
            pixmap = QPixmap('info.png')
        message.setPixmap(pixmap)
        layout.addWidget(message)
        layout.addWidget(accept_button)
        dialog.setLayout(layout)
        dialog.exec()

    def init(self):
        self.layout.addWidget(self.search_bar)
        self.layout.addWidget(self._list)
        self.layout.setSpacing(3)
        self.layout.addStretch()
        self.search_bar.add_file.clicked.connect(self._list.add_file)
        
class SettingsWindow(QFrame):
    def __init__(self):
        super().__init__()
        self.layout: QHBoxLayout = QHBoxLayout(self)
        #to type and set the server address
        self.server_edit: QTextEdit = QTextEdit()
        self.thread = None
        self.worker = None
        self.server_edit.setMaximumSize(1000,40)
        self.server_edit.setStyleSheet('border:1px solid white;color:white;')
        self.save_server = QPushButton('save')
        self.save_server.setMaximumSize(50,40)
        self.save_server.setStyleSheet('background:white;')
        self.save_server.clicked.connect(self.set_server)
        self.layout.addWidget(self.server_edit)
        self.layout.addWidget(self.save_server)


    def set_server(self):
        new_server: str= self.server_edit.toPlainText()
        print('text:',new_server)
        if len(new_server):
            print('thread started')
            self.parent().files_window._list.file_manager.set_server(new_server)
            # self.worker.moveToThread(self.thread)
            # self.worker.finished.connect(self.finish_setting_server)
            # self.thread.started.connect(self.worker.run)
        # self.thread.start()

    def finish_setting_server(self, status):
        if status:
            pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        #self.file_manager = FileManager()
        self.bar: SideBar = SideBar()
        self.loading: Loading = Loading()
        self.files_window: FilesWindow = FilesWindow()
        self.settings_window: SettingsWindow = SettingsWindow()
        # self.files_window.hide()
        self.layout: QHBoxLayout = QHBoxLayout(self)
        self.init_ui()

    def show_files(self):
        self.loading.show()
        self.Loading.start()
        files = self.file_manager.get_all_files()
        for file in files:
           self.files_window._list.add_item(file['name'])
        self.Loading.hide()
        self.Loading.hide()
        self.files_window.show()


    def init_ui(self):
        self.setStyleSheet('background-color:#2a2424')
        self.layout.addWidget(self.bar)
        self.bar._files_button.clicked.connect(self.show_files_window)
        self.bar.settings.clicked.connect(self.show_setting_window)
        # self.layout.addWidget(self.loading_screen)
        self.layout.addWidget(self.files_window)
        self.layout.addWidget(self.settings_window)
        self.settings_window.hide()
        # self.show_files()

    #show the settings 
    def show_setting_window(self) -> None:
        self.files_window.hide()
        self.settings_window.show()

    #showthe files
    def show_files_window(self) -> None:
        self.settings_window.hide()
        self.files_window.show()




app: QApplication = QApplication(sys.argv)
window: MainWindow = MainWindow()
window.show()
app.exec()
