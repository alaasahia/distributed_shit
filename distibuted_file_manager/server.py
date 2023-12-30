import selectors
import sys
import socket
import types
from PyQt5.QtWidgets import QHBoxLayout, QMainWindow
from gui_components import SideBar
import psycopg2
from psycopg2 import errors
import os
from common import load_database
import rpyc
from rpyc.utils.server import ThreadedServer
from uuid import uuid5
from threading import Thread
port: int = 2323
count: int = 0
added_files: list = []
del_files: list = []
renamed_files: list = []
updated_files: dict = {}
#store devices that are connected to the delete file monitor event
deleted_devices: dict = {}
updated_devices = {}


class FileServerGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        button_names = ['files.png', 'devices.png', 'settings.png']
        self.side_bar = SideBar(button_names)
        self.init_ui()

    def init_ui(self):
        self.show()

class FileServer(rpyc.Service):
    config_path = os.path.join(os.path.expanduser('~'),'.config/fs_server/config')
    db_conn = load_database(config_path)
    class exposed_FileAdditionMonitor(object):
        def __init__(self, callback) -> None:
            self.callback = rpyc.async_(callback)
            self._len = len(added_files)
            self.thread = Thread(target=self.work)
            self.thread.start()
        def work(self):
            global count
            count += 1
            print('thread n=', count)
            while True:
                if self._len != len(added_files):
                    print('sending ntofication', added_files, f'self_len={self._len}, added files={len(added_files)}')
                    self._len += 1
                    print('after incrementing:', self._len,f'thread count:{count}')
                    self.callback(added_files[-1])

    # class exposed_FileUpdateMonitor(object):
    #     def __init__(self) -> None:
    #         pass
    #     def work(self):
    #         while True:
    #             pass

    class exposed_FileDeletionMonitor(object):
        def __init__(self, callback):
            self._len = len(del_files)
            self.callback = rpyc.async_(callback)
            self.thread = Thread(target=self.work)
            self.thread.start()
            
        def work(self):
            print('listening for deleting file', del_files)
            while True:
                if self._len != len(del_files):
                    self._len += 1
                    self.callback(del_files[-1])


    class exposed_FileRenamingMonitor(object):
        def __init__(self, callback, address) -> None:
            self.callback = rpyc.async_(callback)
            self._len = len(renamed_files)
            self.address = address
            self.thread = Thread(target=self.work)
            self.thread.start()
        def work(self):
            curs = FileServer.db_conn.cursor()
            # curs.execute('select oldName,name from exists where name!=oldName and address=%s;', (self.address,))
            # results = renamed_files.append([curs.fetchall()])
            # if results:
            #     curs.execute('update exists set oldName=name where name!=oldName and address=%s', (self.address))
            while True:
                if self._len != len(renamed_files):
                    print('started listening for renamed files', renamed_files, f'self._len={self._len}, renamed_files = {len(renamed_files)} = {renamed_files}')
                    self.callback(renamed_files[-1])
                    self._len = len(renamed_files)


                    

    def __init__(self):
        super().__init__()
        self.requests = {}
        self.next_server = None

    def notify_added_files(self):
        pass

    def get_cursor(self):
        cursor = self.db_conn.cursor()
        return cursor

    

    def get_next_server(self):
        cursor = self.get_cursor()
        if cursor:
            try:
                cursor.execute('select * from servers;')
                server = cursor.fetchone()
                return server
            except:
                return None


    def exposed_get_file_location(self, name, source = None):
        # host_name = socket.gethostname
        # host_addr = socket.gethostbyname(host_name)
        # if source and host_addr != source:
        #     cursor = self.db_conn.curosor()
        #     cursor.execute(f'select address from exists where name={self.db_conn};')
        #     address = cursor.fetchall()
        #     request_id = str(uuid5())
        #     conn = rpyc.connect(self.server, self.port)
        #     addresses = conn.root.get_file_location(name, source)
        #     return address
        cursor = self.get_cursor()
        if cursor:
            cursor.execute('select address from exists where name=%s;',(name,))
            return cursor.fetchall()
        return None


    def get_file_devices(self, name):
        curs = self.get_cursor()
        if curs:
            try:
                curs.execute('select address from exist where name="{name}";')
                return curs.fetchall()
            except:
                pass

    def exposed_get_files_list(self):
        curs = self.get_cursor()
        if curs:
            try:
                curs.execute('select files.name from files;')
                files = curs.fetchall()
                print('return', files)
                return files
            except:
                print('error happend')
                return ()


    def add_files(self, addr, names):
        print('hello worled')
        curs = self.get_cursor()
        if curs:
            print('hello world')
            try:
                curs.execute(f"insert into devices(address) values('{addr}');")
            except:
                pass

            finally:
                print('adding names')
                for name in names:
                    try:
                       curs.execute(f"insert into files(name) values(%s);",(name,))
                       added_files.append([name])
                    except errors.UniqueViolation:
                        pass
                    curs.execute(f"insert into exists(name, address) values(%s, %s);",(name, addr))
                    print('exists record has been inserted')
                   #  except:
                   #      return False
                return True


    def delete_files(self, address, names):
        #try:
        print('deleting fikes', names)
        cursor = self.get_cursor()
        if cursor:
            for name in names:
                print('deleting file:', name)
                cursor.execute("delete from exists where name=%s;", (name,))
                cursor.execute("delete from files where name=%s;", (name,))
            del_files.append(names)
            print('the content of deleted files are', del_files)
            return True
        #except:
        #    pass

    def exposed_is_permitted(self, name, address, op):
        curs = self.get_cursor()
        if curs:
            curs.execute('select * from devicePermission where address=%s', (address,))
            permission = curs.fetchone()
            if not permission:
                curs.execute('select * from files where nane=%s', (name))
                permission = curs.fetchone()
            

    def exposed_rename_file(self, name, new_name):
        if name != new_name:
            print(f'renaming file from {name} to {new_name}, {type(name)} {type(new_name)}')
            curs = self.get_cursor()
            if curs:
                curs.execute('select name from files where name=%s', (name,))
                if curs.fetchone():
                    curs.execute('update files set name=%s where name=%s',(new_name, name))
                    renamed_files.append((name, new_name))

                
            

    def exposed_sync(self, data):
        print('received address request:', data)
        #try:
        if data['op']=="add":
            print('adding files')
            self.add_files(data['address'], data['files'])
        elif data['op'] =='delete':
            print('deleting files')
            self.delete_files(data['address'], data['files'])
        return True            
                    
        #except:
        #    pass




# config_path = os.path.join(os.path.expanduser('~'),'.config/file_sys/config')
# def load_server():
#     return load_database(config_path)


# def add_client(ip, cursor):
#     cursor.execute(f'insert into devices(ip) values({ip});')


# def synchronize(cursor,device, op, names):
#     try:
#         cursor.execute('select * from devices where address={device};')
#         result = cursor.fetchall()
#         if op=="add":
#             if not result:
#                 cursor.execute('insert into devices(address) values("{name}");')
#             for name in names:
#                 cursor.execute('insert into files(name) values("{name}");')
#                 cursor.execute('insert into exists(name, device) values("{name}","{device}");')
#         else:
#             if not result:
#                 pass
#             else:
#                 for name in names:
#                     cursor.execute('delete from exists where name="{name}" and device="{device}";')
#                     cursor.execute('select * from exists where name="{name}";')
#                     results = cursor.fetchall()
#                     if not results:
#                         cursor.execute('delete from files where name="{name}";')
#     except:
#         pass


# def get_file(name, cursor):
#     cursor.execute('select address from exists where name="{name}";')
#     addresses = cursor.fetchall()

    
# def accept_wrapper(sel,sock):
#     conn, addr = sock.accept()
#     conn.setblocking(False)
#     data = types.SimpleNamespace(addr=addr,inb=b'', out=b'')
#     events = selectors.EVENT_READ | selectors.EVENT_WRITE
#     sel.register(conn, events, data = data)
port = 12334
thread = ThreadedServer(FileServer, port = port, hostname='192.168.1.8')
print('starting thread at port', port)
thread.start()
