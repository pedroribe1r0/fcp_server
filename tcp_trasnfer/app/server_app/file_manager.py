from pathlib import Path

CHUNK_SIZE = 64 * 1024

class FileManager:
    def read_chunk(self, path: Path, position: int) -> bytes:
        with path.open("rb") as file:
            file.seek(position)
            return file.read(CHUNK_SIZE)

    def read_file(self, path: Path):
        with path.open("rb") as file:
            while chunk := file.read(CHUNK_SIZE):
                yield chunk

    def write_chunk(self, path: Path, data: bytes, position: int) -> None:
        mode = "wb" if position == 0 else "r+b"
        with path.open(mode) as file:
            file.seek(position)
            file.write(data)

    def delete_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)