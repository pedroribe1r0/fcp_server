from contextlib import closing
from os import getpid
from pathlib import Path

from tcp_trasnfer.application_protocol.fcp.fcp_client import FCPClient


def error_handler(error: Exception):
    print(f"\nErro: {error}")


class MessageService:
    def execute(self, message: str):
        print(f"\nChat: {message}")


class FileService:
    def __init__(self, base_dir: Path = Path(__file__).resolve().parent / "client_files"):
        self.base_dir = Path(base_dir) / str(getpid())

    def execute(self, client: FCPClient, filename: str) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        destination = self.base_dir / Path(filename).name
        temporary = destination.with_name(destination.name + ".part")
        try:
            with closing(client.get_file(filename)) as chunks:
                with temporary.open("wb") as file:
                    for chunk in chunks:
                        file.write(chunk)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination


class ClientApp:
    def __init__(self, ip: str = "127.0.0.1", port: int = 5000):
        self.message_service = MessageService()
        self.file_service = FileService()
        self.fcp_client = FCPClient(
            ip=ip,
            port=port,
            on_message=self.message_service.execute,
            on_error=error_handler,
        )

    def run(self):
        try:
            self.fcp_client.connect()
            while True:
                print("\n1. receber arquivo\n2. enviar chat\n3. sair")
                option = input("> ").strip()
                try:
                    match option:
                        case "1":
                            filename = input("Nome do arquivo: ").strip()
                            path = self.file_service.execute(self.fcp_client, filename)
                            print(f"Arquivo salvo em {path}")
                        case "2":
                            self.fcp_client.send_chat(input("Mensagem: "))
                        case "3":
                            break
                        case _:
                            print("Opção inválida")
                except Exception as error:
                    error_handler(error)
        except (EOFError, KeyboardInterrupt):
            pass
        except OSError as error:
            error_handler(error)
        finally:
            self.fcp_client.close()


if __name__ == "__main__":
    ClientApp().run()
