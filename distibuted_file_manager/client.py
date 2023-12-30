import socket
import os
from sqlite3 import Cursor, connect
from typing import Union
from uuid import UUID, uuid4
from rpyc.utils.helpers import BgServingThread
import pickle
import selectors
import types
import rpyc
from rpyc.utils.server import ThreadedServer, logging
from datetime import datetime
from threading import Thread
from rpyc.utils import exposed
from client_database import Database, schema
from decorators import run_in_thread

database_name: str = 'files'
logging.basicConfig(level=logging.DEBUG)
class FileManager(rpyc.Service):
    def __init__(self, database_name: str):
        self.database: Database = Database('files')
        #handle incoming queires from different threads
        self.database_queue: dict = {}
        self.server: Union[str, None] = None
        self.server_port: Union[int, None] = None
        self.socket_port = 32345
        self.server_socket = 12334
        self.selector = selectors.DefaultSelector()
        #self.add_listen = Thread(target=self.listen_for_new_files)
        # self.add_listen.start()
        self.added_files = []
        self.deleted_files = []
        self.listen_target = None
        self.listen_args = None
        #the file addition listener that will file addition notifications
        self.add_listener = None

    #add queries to the queries to the queries queue
    #it returns a uuid object to track the state of the transaction
        #connect to the database, this function will run in a separate thread
    def connect_to_database(self) -> bool:
        logging.info('attempt to connect to database')
        #check if the database exists
        if not self.database.is_database_exists():
            logging.info(f"database {self.database.database_name} doesn't exists")
            self.database.setup(schema)
        status: bool = self.database.connect()
        logging.info(f"database connection:{status}")
        return status

    def start_database_server(self):
        self.database.execute_queries()
    #listen for new files that is added and notified by the server
    def listen_for_new_files(self) -> None:
        #connect to the server
        conn: rpyc.Connection = rpyc.connect(self.get_server(), self.server_port)
        conn._config['sync_request_timeout'] = None
        #create a new thread to handle the listener
        bgsrv: BgServingThread = rpyc.BgServingThread(conn)
        #
        self.add_listener = conn.root.FileAdditionMonitor(self.log_new_files)



    def log_new_files(self, files):
        self.added_files.append(files)

    def listen_for_deleted_files(self):
        conn = rpyc.connect(self.server, self.server_socket)
        conn._config['sync_request_timeout'] = None  
        bgsrv = rpyc.BgServingThread(conn)
        self.delete_listener = conn.root.FileDeletionMonitor(self.log_deleted_files)

    def log_deleted_files(self, files):
        self.deleted_files.append(files)

        
    def on_connect(self, conn):
        return super().on_connect(conn)

    def exposed_new_files(self):
        pass

    def get_cursor(self):
        return self.database.get_cursor()

    #set the server and add it to the database
    #return true if the server added successfully
    #otherwise return False
    def set_server(self, address: str) -> bool:
        cursor: Cursor = self.get_cursor()
        if cursor:
            try:
                cursor.execute(f'delete from server;')
                logging.info("deleting the old server")
                cursor.execute(f"insert into server(address) values('{address}');")
                self.server = address
                return True
            except:
                logging.warn("server creation error")
                return False

    #get the server that the client is connected to
    def get_server(self) -> Union[str, None]:
        #try:
        cursor = self.get_cursor()
        cursor.execute('select address from server;')
        server = cursor.fetchall()
        print('getting server ', server)
        if server:
            return server[0]
        return None
        #except:
        #    pass

    def check_conn(self):
        try:
            server = self.get_server()
            if server:
                conn = rpyc.connect(server, self.port)
                return True
        except:
            return False


    def send_sync_info(self, op, files):
        server = self.get_server()
        print('sending sync info to server', server)
        if server:
            #try:
            conn = rpyc.connect(self.server, self.server_socket)
            print(conn.root)
            status = conn.root.sync(
                    {
                        'op':op,
                        'address':'127.0.0.1',
                        'files':files
                    }
                )
            print('deletion status:', status)
            return status
            #except:
            #    return False

    def sync(self, operation = None):
        #try:
        op = None
        files = None
        if operation:
            return self.send_sync_info(operation['op'],operation['files'])
        while True:
            try:
                cursor = self.get_cursor()
                cursor.execute('select op, files from sync;')
                operations = cursor.fetchall()
                for operation in operations:
                    status = self.send_sync_info(operation[0],operation[1])
                    if not status:
                        return status
            except:
                pass
        #except:
        #    pass
    


    def get_file_location(self, name):
        try:
            cursor = self.get_cursor()
            cursor.execute('select name,location from files where name="{name}";')
            location = cursor.fetchone()
            # if not location:
            #     conn = rpyc.connect(self.server, self.port)
            #     locations = conn.root.get_file_location(name)
            #     return locations
            return location
        except:
            pass

    def get_local_file(self, name):
        cursor = self.get_cursor()
        cursor.execute('select location from files where name=%s;',(name,))
        return cursor.fetchone()

    def exposed_get_attrs(self, name):
        try:
            locations = self.get_file_location(name)
            # if len(location) > 1:
            #       for location in locations:
            #         try:
            #             conn = rpyc.connect(location, self.port)
            #             info = conn.root.get_file_attrs(name)
            #             break
            #         except:
            #             pass
            # else:
            path = os.path.join(locations[0][1],locations[0][0])
            stat = os.stat(path)
            return {
                'name':name,
                'size':stat.st_size
            }
        except:
            pass
                

    def start_file_retrieve(self, ip ,name, seek):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, self.socket_port))
        info = pickle.dumps(
            {
                'type':'get',
                'name':name,
                'seek':seek
            }
        )
        sock.sendall(info)
        print('file info sent')
        return sock

    def get_local_files(self,filter = 'name'):
        print('getting local files')
        #try:
        cursor = self.get_cursor()
        cursor.execute('select name from files order by name;')
        files = cursor.fetchall()
        print('local files:', files)
        return files
        #except:            
        #    pass

    def get_shared_files_list(self):
        #try:
        conn = rpyc.connect(self.server, self.server_socket)
        files = conn.root.get_files_list()
        print('client:', list(files))
        return list(files)
        #except:
        #    pass

    def get_shared_file(self,name, signal = None):
        print('file download started', name)
        server = self.get_server()
        if server:
            #try:
            conn = rpyc.connect(self.server, self.server_socket)
            addresses = conn.root.get_file_location(name)
            # addresses = ['127.0.0.1']
            print('addresses:', addresses)
            file = open('/home/alaa/shared/'+name, 'wb')
            size = 0
            if addresses:
                size = 0
                current_addr = 0
                info = None
                while current_addr < len(addresses):
                    #try:
                    conn = rpyc.connect(addresses[current_addr][0], 12336)
                    print('attrs conn:', conn)
                    info = conn.root.get_attrs(name)
                    break
                    
                    #except:
                        #current_addr += 1
                print('rpc info', info)
                if info:
                    sock = self.start_file_retrieve(addresses[current_addr][0],name, 0)
                    print('getting socket', sock)
                    while current_addr < len(addresses):
                        print('receiving bytes')
                        data = b''
                        data += sock.recv(1024)
                        print(data)
                        if data:
                            file.write(data)
                            size += len(data)
                            if signal:
                                signal.emit(size)
                        else:
                            sock.close()
                            if info['size'] == size:
                                cursor = self.get_cursor()
                                cursor.execute(f'insert into files(name, location) values(%s, %s);',(name, os.path.join(os.getcwd())))
                                self.sync({'op':'add', 'files' : [name]})
                                return True
                            else:
                                current_addr += 1
                                sock = self.start_file_retrieve(addresses[current_addr], name, size)              
                                            
            #except:
            #    pass

    def get_path_components(self, file):
        print('file to scan', file)
        index = None
        for i in range(len(file)):
            if file[i] == "/" or file[i] == "\\":
                index = i
                print('index')
        info = {
            'path':file[:index],
            'name':file[index + 1:]
             
        }
        print('path info:', info)
        return info


    #add files to the database
    def add_files(self, files: list[str]) -> bool:
        # try:
        # cursor = self.get_cursor()
        print('files_to add:', files)
        for  index in range(len(files)):
            path_info = self.get_path_components(files[index])
            query: str = f"insert into files(name, location) values('{path_info['name']}','{path_info['path']}' );"
            query_id: UUID = self.database.add_query(query)
            #wait for the query to get executed
            query_status: Union[bool, None] = self.database.get_query_status(query_id)
            while not query_status:
                query_status = self.database.get_query_status(query_id)
            if not self.sync({'op':'add','files':[path_info['name']]}):
                cursor.execute(f'insert into sync(date,op,files) values({datetime.now()},"add","{files}"))')
            return True
        # except:
        #     return False

    def rename(self, name, new_name):
        pass

    def remove_files(self, files):
        #+try:
        cursor = self.get_cursor()
        print('files to delete:', files)
        for file in files:
            cursor.execute(f'delete from files where name=%s;', (file,))
        if not self.sync({'op':'delete', 'files':files}):
            cursor.execute(f'insert into sync(date, op, files) values("{datetime.now()}", "delete",{files});', (datetime.now(), files))
        return True
        #except:
        #    pass

    def accept_connection(self,sock):
        print('new connection:', sock)
        conn, addr = sock.accept()
        self.selector.register(conn, selectors.EVENT_WRITE | selectors.EVENT_READ, data=True)

    def serve_connection(self, sock):
        print('hello world')
        data = b''
        request = b''
        while True:
            try:
                data = sock.recv(1024)
                if data:
                    request += data
                else:
                    break 
            except:
                break
        request = pickle.loads(request)
        file_name = request['name']
        locations = self.get_file_location(file_name)
        if locations:
            file = open(os.path.join(locations[1], file_name),'rb')
            file.seek(request['seek'])
            while True:
                data = file.read(1024)
                if data:
                    sock.sendall(data)
                else:
                    file.close()
                    sock.close()

    #start the server for sharing files
    def start_server(self) -> None:
        logging.info("starting server")
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hostname = socket.gethostname()
        host_addr = socket.gethostbyname(hostname)
        lsock.bind((host_addr,45634))
        with lsock:
            #listen to incoming connections
            while True:
               sock.listen()
               conn, addr = sock.accept()
               conn.setblocking(0)
               thread = Thread(target=self.serve_connection, args=(conn,))
               thread.start()
