from tcp_trasnfer.application_protocol.fcp.fcp_server import FCPServer, Response
from tcp_trasnfer.application_protocol.package import Package, MessageType
from pathlib import Path
from .file_manager import FileManager
from hashlib import sha256

def error_handler(res: Response, e: Exception):
    error_response = Package.create(
        str(e).encode("utf-8"),
        MessageType.ERR
    )

    res.send(error_response)

class FileService:
    base_dir: Path
    file_manager: FileManager

    def __init__(self, base_dir: Path = (Path(__file__).resolve().parent / "server_files")):
        self.base_dir = Path(base_dir).resolve()
        self.file_manager = FileManager()

    def parse_request(self, data: str) -> Path:
        if not data.startswith("/"):
            raise ValueError("Path must start with /")

        filename = data[1:]

        if not filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename")

        path = (self.base_dir / filename).resolve()

        if path.parent != self.base_dir:
            raise ValueError("Invalid path")

        if not path.is_file():
            raise ValueError("File not exist")

        return path

    def execute(self, res: Response, package: Package):
        path = self.parse_request(package.payload.decode("utf-8"))
        sha = sha256()

        for chunk in self.file_manager.read_file(path):
            sha.update(chunk)
            res.send(Package.create(
                chunk,
                MessageType.FILE_CHUNK
            ))

        final_hash = sha.digest()

        res.send(Package.create(
            final_hash,
            MessageType.EOF
        ))
        print(f"[INFO] SHA-256 {path.name} | cliente={res.sock.addr} | {sha.hexdigest()}")

        

class MessageService:
    def execute(self, res: Response, package: Package):
        res.broadcast(Package.create(
            package.payload,
            MessageType.CHAT_MESSAGE
        ))

class ServerApp:
    fcp_server: FCPServer
    message_service: MessageService
    file_service: FileService

    def __init__(self):
        self.message_service = MessageService()
        self.file_service = FileService()

        self.fcp_server = FCPServer(
            on_error=error_handler,
            on_chat=self.message_service.execute,
            on_file_request=self.file_service.execute
        )

    def run(self):
        self.fcp_server.listen()


if __name__ == "__main__":
    app = ServerApp()
    app.run()
