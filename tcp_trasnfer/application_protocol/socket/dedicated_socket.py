import socket
from threading import Lock
from ..package import Headers, Package

class DedicatedSocket:
    addr: tuple[str, int]
    sock: socket.socket

    def __init__(
        self,
        addr: tuple[str, int] = ("127.0.0.1", 5000),
        sock: socket.socket | None = None
    ) -> None:
        self.addr = addr
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) if sock is None else sock
        self._send_lock = Lock()

    def connect(self) -> None:
        self.sock.connect(self.addr)

    def recv_message(self):
        while True:
            headers = Headers.from_bytes(self._recv_exact(5))
            yield Package.from_bytes(self._recv_exact(headers.size), headers)
        
    def _recv_exact(self, size):
        data = bytearray()

        while len(data) < size:
            chunk = self.sock.recv(size - len(data))

            if not chunk:
                raise ConnectionError("Conexão encerrada")

            data.extend(chunk)

        return bytes(data)

    def send_data(self, data: bytes):
        with self._send_lock:
            self.sock.sendall(data)

    def close(self):
        self.sock.close()
