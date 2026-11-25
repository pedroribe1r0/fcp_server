import socket
from .dedicated_socket import DedicatedSocket

class ServerSocket:
    server: socket.socket

    def __init__(
        self,
        interface: str,
        port: int
    ) -> None:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((interface, port))


    def listen(self):
        self.server.listen()

        while True:
            client_socket, address = self.server.accept()
            yield DedicatedSocket(address, client_socket)
        

    