import socket
from collections.abc import Callable, Iterator
from hashlib import sha256
from queue import Empty, Full, Queue
from threading import Event, Thread

from ..package import MessageType, Package
from ..socket.dedicated_socket import DedicatedSocket


FILE_BUFFER_SIZE = 16
QUEUE_TIMEOUT = 0.1


class FCPClient:
    def __init__(
        self,
        ip: str = "127.0.0.1",
        port: int = 5000,
        *,
        on_message: Callable[[str], None],
        on_error: Callable[[Exception], None] | None = None,
    ):
        self.sock = DedicatedSocket((ip, port))
        self.on_message = on_message
        self.on_error = on_error
        self._closed = Event()
        self._connection_error: Exception | None = None
        self._file_queue: Queue[Package] | None = None

    def connect(self) -> None:
        self.sock.connect()
        Thread(target=self._receive_messages, daemon=True).start()

    def send_chat(self, text: str) -> None:
        self._send(text.encode("utf-8"), MessageType.CHAT_MESSAGE)

    def get_file(self, filename: str) -> Iterator[bytes]:
        if self._file_queue is not None:
            raise RuntimeError("Já existe uma transferência ativa")

        chunks: Queue[Package] = Queue(maxsize=FILE_BUFFER_SIZE)
        self._file_queue = chunks
        sha = sha256()
        finished = False

        try:
            if not filename.startswith("/"):
                filename = f"/{filename}"
            self._send(filename.encode("utf-8"), MessageType.FILE_REQUEST)

            while True:
                try:
                    package = chunks.get(timeout=QUEUE_TIMEOUT)
                except Empty:
                    if self._closed.is_set():
                        raise self._connection_error or ConnectionError("Conexão encerrada")
                    continue

                match package.headers.type:
                    case MessageType.FILE_CHUNK:
                        sha.update(package.payload)
                        yield package.payload
                    case MessageType.EOF:
                        finished = True
                        print(f"[INFO] SHA-256 recebido: {package.payload.hex()}")
                        print(f"[INFO] SHA-256 calculado: {sha.hexdigest()}")
                        if package.payload != sha.digest():
                            raise ValueError("SHA-256 do arquivo não confere")
                        print("[INFO] Integridade SHA-256 validada")
                        return
                    case MessageType.ERR:
                        finished = True
                        raise RuntimeError(package.payload.decode("utf-8"))
        finally:
            if not finished:
                self.close()
                
            self._file_queue = None

    def close(self) -> None:
        if self._closed.is_set():
            return
        
        self._closed.set()
        try:
            self.sock.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()

    def _send(self, payload: bytes, message_type: MessageType) -> None:
        if self._closed.is_set():
            raise ConnectionError("Conexão encerrada")
        
        self.sock.send_data(Package.create(payload, message_type).to_bytes())

    def _receive_messages(self) -> None:
        try:
            for package in self.sock.recv_message():
                print(f"[INFO] Recebido {package.headers.type.name} | {len(package.payload)} bytes")
                match (package.headers.type):
                    case MessageType.CHAT_MESSAGE:
                        self.on_message(package.payload.decode("utf-8"))

                    case MessageType.FILE_CHUNK | MessageType.EOF | MessageType.ERR:
                        if self._file_queue is not None:
                            self._queue_file_message(package)

                        elif package.headers.type == MessageType.ERR:
                            if self.on_error is not None:
                                self.on_error(RuntimeError(package.payload.decode("utf-8")))

                        else:
                            raise ValueError("Mensagem de arquivo sem transferência ativa")
                
        except Exception as error:
            if not self._closed.is_set():
                self._connection_error = error
                self.close()
                if self.on_error is not None:
                    self.on_error(error)
        finally:
            self.close()

    def _queue_file_message(self, package: Package) -> None:
        chunks = self._file_queue
        while not self._closed.is_set():
            try:
                chunks.put(package, timeout=QUEUE_TIMEOUT)
                return
            except Full:
                continue
