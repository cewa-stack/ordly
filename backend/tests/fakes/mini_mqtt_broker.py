"""
Minimalny broker MQTT 3.1.1 do testów mostu Control Huba.

Nie jest "udawaną odpowiedzią biblioteki": prawdziwy klient (aiomqtt /
paho-mqtt) łączy się z nim po TCP i rozmawia pełnym protokołem - CONNECT
z hasłem i LWT, SUBSCRIBE, PUBLISH z QoS 0/1, wiadomości retained,
PINGREQ, DISCONNECT. Dzięki temu test sprawdza dokładnie to, co poleci
po kablu do Mosquitto na Raspberry Pi.

Uproszczenia (bez znaczenia dla testów): do subskrybentów wszystko idzie
z QoS 0, brak sesji trwałych i QoS 2.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class _Session:
    writer: asyncio.StreamWriter
    client_id: str = ""
    filters: list[str] = field(default_factory=list)
    will: tuple[str, bytes, bool] | None = None


@dataclass(frozen=True)
class PublishedMessage:
    """Wiadomość, którą broker przyjął od któregoś klienta."""

    client_id: str
    topic: str
    payload: bytes
    retain: bool


def topic_matches(topic_filter: str, topic: str) -> bool:
    """Dopasowanie tematu do filtra z `+` i `#` (MQTT 3.1.1, 4.7)."""
    filter_parts = topic_filter.split("/")
    topic_parts = topic.split("/")
    for index, part in enumerate(filter_parts):
        if part == "#":
            return True
        if index >= len(topic_parts):
            return False
        if part not in ("+", topic_parts[index]):
            return False
    return len(filter_parts) == len(topic_parts)


def _encode_length(length: int) -> bytes:
    out = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length:
            byte |= 0x80
        out.append(byte)
        if not length:
            return bytes(out)


def _string(data: bytes, offset: int) -> tuple[bytes, int]:
    length = int.from_bytes(data[offset : offset + 2], "big")
    start = offset + 2
    return data[start : start + length], start + length


class MiniMqttBroker:
    """Broker na 127.0.0.1 z losowym portem. Użycie: `async with MiniMqttBroker(...)`."""

    def __init__(self, users: dict[str, str]) -> None:
        self._users = users
        self._server: asyncio.Server | None = None
        self._sessions: list[_Session] = []
        self._retained: dict[str, bytes] = {}
        self.published: list[PublishedMessage] = []
        self.port = 0
        self._new_message = asyncio.Event()

    async def __aenter__(self) -> MiniMqttBroker:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._server is not None
        for session in list(self._sessions):
            session.writer.close()
        self._server.close()
        await self._server.wait_closed()

    def retained(self, topic: str) -> bytes | None:
        """Aktualna wiadomość retained na temacie."""
        return self._retained.get(topic)

    async def wait_for(
        self, topic: str, count: int = 1, within_seconds: float = 5.0
    ) -> list[bytes]:
        """Czeka, aż na temat trafi `count` wiadomości; zwraca je wszystkie."""

        async def _wait() -> list[bytes]:
            while True:
                found = [m.payload for m in self.published if m.topic == topic]
                if len(found) >= count:
                    return found
                self._new_message.clear()
                await self._new_message.wait()

        return await asyncio.wait_for(_wait(), within_seconds)

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        session = _Session(writer=writer)
        self._sessions.append(session)
        clean = False
        try:
            while True:
                header = await reader.readexactly(1)
                length = 0
                multiplier = 1
                while True:
                    byte = (await reader.readexactly(1))[0]
                    length += (byte & 0x7F) * multiplier
                    multiplier *= 128
                    if not byte & 0x80:
                        break
                body = await reader.readexactly(length)
                packet_type = header[0] >> 4
                flags = header[0] & 0x0F
                if packet_type == 1:
                    if not await self._on_connect(session, body):
                        return
                elif packet_type == 3:
                    await self._on_publish(session, flags, body)
                elif packet_type == 8:
                    await self._on_subscribe(session, body)
                elif packet_type == 10:
                    writer.write(bytes([0xB0, 2]) + body[:2])
                elif packet_type == 12:
                    writer.write(bytes([0xD0, 0]))
                elif packet_type == 14:
                    clean = True
                    return
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._sessions.remove(session)
            writer.close()
            if not clean and session.will is not None:
                topic, payload, retain = session.will
                self._deliver(session.client_id, topic, payload, retain)

    async def _on_connect(self, session: _Session, body: bytes) -> bool:
        _, offset = _string(body, 0)  # "MQTT"
        offset += 1  # poziom protokołu
        flags = body[offset]
        offset += 3  # flagi + keepalive
        client_id, offset = _string(body, offset)
        session.client_id = client_id.decode()
        if flags & 0x04:
            will_topic, offset = _string(body, offset)
            will_payload, offset = _string(body, offset)
            session.will = (will_topic.decode(), will_payload, bool(flags & 0x20))
        username = password = b""
        if flags & 0x80:
            username, offset = _string(body, offset)
        if flags & 0x40:
            password, offset = _string(body, offset)
        accepted = self._users.get(username.decode()) == password.decode()
        session.writer.write(bytes([0x20, 2, 0, 0 if accepted else 5]))
        await session.writer.drain()
        return accepted

    async def _on_publish(self, session: _Session, flags: int, body: bytes) -> None:
        qos = (flags >> 1) & 0x03
        retain = bool(flags & 0x01)
        topic, offset = _string(body, 0)
        if qos:
            packet_id = body[offset : offset + 2]
            offset += 2
            session.writer.write(bytes([0x40, 2]) + packet_id)
        self._deliver(session.client_id, topic.decode(), body[offset:], retain)

    def _deliver(self, client_id: str, topic: str, payload: bytes, retain: bool) -> None:
        self.published.append(PublishedMessage(client_id, topic, payload, retain))
        self._new_message.set()
        if retain:
            if payload:
                self._retained[topic] = payload
            else:
                self._retained.pop(topic, None)
        for other in self._sessions:
            if any(topic_matches(f, topic) for f in other.filters):
                other.writer.write(self._publish_packet(topic, payload, retain=False))

    async def _on_subscribe(self, session: _Session, body: bytes) -> None:
        packet_id = body[:2]
        offset = 2
        granted = bytearray()
        new_filters: list[str] = []
        while offset < len(body):
            topic_filter, offset = _string(body, offset)
            offset += 1  # żądany QoS
            new_filters.append(topic_filter.decode())
            granted.append(0)
        session.filters.extend(new_filters)
        session.writer.write(
            bytes([0x90]) + _encode_length(2 + len(granted)) + packet_id + granted
        )
        for topic, payload in self._retained.items():
            if any(topic_matches(f, topic) for f in new_filters):
                session.writer.write(self._publish_packet(topic, payload, retain=True))
        await session.writer.drain()

    @staticmethod
    def _publish_packet(topic: str, payload: bytes, retain: bool) -> bytes:
        encoded = topic.encode()
        body = len(encoded).to_bytes(2, "big") + encoded + payload
        return bytes([0x30 | (1 if retain else 0)]) + _encode_length(len(body)) + body
