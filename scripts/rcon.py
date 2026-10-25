#!/usr/bin/env python3
"""Minimal Minecraft RCON client (protocol by Tetragrammaton)."""
import socket, struct, time

class Rcon:
    def __init__(self, host, port, password, timeout=8):
        self.rid = 0
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self._send(3, password)
        t, rid, payload = self._recv()
        if rid == -1:
            raise RuntimeError("RCON auth failed")

    def _send(self, t, payload, rid=None):
        if rid is None:
            self.rid += 1
            rid = self.rid
        data = struct.pack("<ii", rid, t) + payload.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(data)) + data)

    def _recv(self):
        ln = struct.unpack("<i", self._read(4))[0]
        data = self._read(ln)
        rid, t = struct.unpack("<ii", data[:8])
        payload = data[8:-2].decode("utf-8", errors="replace")
        return t, rid, payload

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("socket closed")
            buf += chunk
        return buf

    def command(self, cmd, wait=0.25):
        self._send(2, cmd)
        time.sleep(wait)
        out = []
        while True:
            try:
                t, rid, payload = self._recv()
            except (RuntimeError, socket.timeout):
                break
            out.append(payload)
            if len(out) > 20:
                break
        return "\n".join(out)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
