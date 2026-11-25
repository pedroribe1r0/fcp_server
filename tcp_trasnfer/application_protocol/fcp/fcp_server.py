from ..socket.server_socket import ServerSocket
from ..socket.dedicated_socket import DedicatedSocket
from threading import Lock, Thread
from ..package import Package, MessageType
from collections.abc import Callable

class FCPServer:
    server_sock: ServerSocket
    client_socks: set[DedicatedSocket]
    on_chat: Callable[["Response", Package], None]
    on_file_request: Callable[["Response", Package], None]
    on_error: Callable[["Response", Exception], None]

    def __init__(
            self, 
            on_chat: Callable[["Response", Package], None],
            on_file_request: Callable[["Response", Package], None],
            on_error: Callable[["Response", Exception], None],
            interface: str = "127.0.0.1", 
            port: int = 5000
        ):
        self.server_sock = ServerSocket(interface=interface, port=port)
        self.client_socks = set()
        self._clients_lock = Lock()

        self.on_chat = on_chat
        self.on_file_request = on_file_request
        self.on_error = on_error

    def listen(self):
        for client_sock in self.server_sock.listen():
            with self._clients_lock:
                self.client_socks.add(client_sock)
            Thread(
                target=self.connection_runner,
                args=[client_sock]
            ).start()

    def connection_runner(self, sock: DedicatedSocket):
        try:
            for data in sock.recv_message():
                try:
                    match(data.headers.type):
                        case MessageType.CHAT_MESSAGE:
                            data.payload = f"[{sock.addr}]{data.payload.decode('utf-8')}".encode("utf-8")
                            self.on_chat(
                                Response(
                                    sock=sock,
                                    fcp_server=self
                                ),
                                data
                            )
        
                        case MessageType.FILE_REQUEST:
                            self.on_file_request(
                                Response(
                                    sock=sock,
                                    fcp_server=self
                                ),
                                data
                            )
    
                except ConnectionError:
                    raise
                except Exception as e:
                    try:
                        self.on_error(
                            Response(
                                sock=sock,
                                fcp_server=self
                            ),
                            e
                        )
                    except:
                        raise
        except ConnectionError:
            pass

        finally:
            with self._clients_lock:
                self.client_socks.discard(sock)
            sock.close()
                
                
    def broadcast(self, package: Package):
        data = package.to_bytes()

        with self._clients_lock:
            clients = self.client_socks.copy()

        for client_sock in clients:
            try:
                client_sock.send_data(data)
                print(f"[INFO] Enviado {package.headers.type.name} | {len(package.payload)} bytes | cliente={client_sock.addr}")
            except OSError:
                with self._clients_lock:
                    self.client_socks.discard(client_sock)
                try:
                    client_sock.close()
                except OSError:
                    pass

class Response:
    sock: DedicatedSocket
    fcp_server: FCPServer

    def __init__(
        self,
        sock: DedicatedSocket,
        fcp_server: FCPServer
    ):
        self.sock = sock
        self.fcp_server = fcp_server

    def broadcast(self, package: Package):
        self.fcp_server.broadcast(package=package)

    def send(self, package: Package):
        self.sock.send_data(data=package.to_bytes())
        print(f"[INFO] Enviado {package.headers.type.name} | {len(package.payload)} bytes | cliente={self.sock.addr}")
