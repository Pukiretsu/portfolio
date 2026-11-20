"""Bounded Minecraft Java Server List Ping; never accepts a client-supplied host."""

import json
import re
import socket
import struct
import time


def varint(value):
    value &= 0xFFFFFFFF
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        result.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(result)


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.recv(count - len(result))
        if not chunk:
            raise ValueError("Truncated Minecraft response")
        result.extend(chunk)
    return bytes(result)


def read_varint(stream):
    value = 0
    for shift in range(0, 35, 7):
        byte = read_exact(stream, 1)[0]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value
    raise ValueError("Oversized VarInt")


def plain_text(value, depth=0):
    if depth > 10:
        return ""
    if isinstance(value, str):
        return re.sub("§.", "", value)[:500]
    if isinstance(value, dict):
        return (plain_text(value.get("text", ""), depth + 1)
                + "".join(plain_text(item, depth + 1) for item in value.get("extra", [])[:20]))[:500]
    return ""


def ping(ipv4, hostname):
    start = time.monotonic()
    host = hostname.encode("utf-8")
    handshake = b"\x00" + varint(-1) + varint(len(host)) + host + struct.pack(">H", 25565) + b"\x01"
    # A non-VPC Lambda uses EC2's public IPv4 for probing; clients also get IPv6 DNS.
    with socket.create_connection((ipv4, 25565), timeout=2) as stream:
        stream.sendall(varint(len(handshake)) + handshake + b"\x01\x00")
        length = read_varint(stream)
        if not 1 <= length <= 65536:
            raise ValueError("Invalid Minecraft packet size")
        import io
        payload = io.BytesIO(read_exact(stream, length))

        class Reader:
            def recv(self, size):
                return payload.read(size)

        reader = Reader()
        if read_varint(reader) != 0:
            raise ValueError("Unexpected Minecraft status packet")
        size = read_varint(reader)
        if size > 32768:
            raise ValueError("Oversized status JSON")
        status = json.loads(read_exact(reader, size))
    players = status.get("players", {})
    return {
        "latencyMs": round((time.monotonic() - start) * 1000),
        "playersOnline": max(0, int(players.get("online", 0))),
        "playersMax": max(0, int(players.get("max", 0))),
        "version": str(status.get("version", {}).get("name", "Unknown"))[:80],
        "motd": plain_text(status.get("description", "")),
    }
