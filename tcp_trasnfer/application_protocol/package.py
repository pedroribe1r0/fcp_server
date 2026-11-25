from enum import Enum
from dataclasses import dataclass

class MessageType(Enum):
    FILE_REQUEST = "R"
    FILE_CHUNK = "C"
    EOF = "F"
    ERR = "E"
    CHAT_MESSAGE = "M"

@dataclass
class Headers:
    type: MessageType
    size: int

    @classmethod
    def from_bytes(cls, data: bytes):
        message_type = MessageType(
            data[0:1].decode("ascii")
        )
        size = int.from_bytes(data[1:5], "big")

        return cls(
            type=message_type,
            size=size
        )


@dataclass
class Package:
    headers: Headers
    payload: bytes

    def to_bytes(self) -> bytes:
        message_type = self.headers.type.value.encode("ascii")
        size = self.headers.size.to_bytes(4, "big")
        
        return message_type + size + self.payload

    @classmethod
    def from_bytes(cls, data: bytes, headers: Headers | None = None) -> "Package":
        headers, payload = (
            (Headers.from_bytes(data[0:5]), data[5:]) if headers is None
            else (headers, data)
        )
        # its good to add a package validation later

        return cls(
            headers=headers,
            payload=payload
        )

    @classmethod
    def create(cls, payload: bytes, type: MessageType):
        return Package(
            Headers(
                type=type,
                size=len(payload)
            ),
            payload
        )


