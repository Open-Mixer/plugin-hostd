# SPDX-License-Identifier: GPL-3.0-or-later
"""The mod-host line protocol from Python, the one client every test of plugin-hostd, omx-clap-host and the controllers
imports: a command is one line ended by a NUL, a reply is one NUL-ended line. Installed by plugin-hostd-tests as
/usr/libexec/plugin-hostd/tests/lib/plugin_hostd_client.py, and in this tree as tests/lib/plugin_hostd_client.py. The
codec (a command's encoding, a reply's parsing, words and paths, codes and their sentences) is plugin_hostd_protocol's,
never this module's own: this module holds the transport and what the tests add on top of it.

    c = Client(sock)            a connected socket, or Client.connect(port)
    c.send(line)                the reply; ConnectionError when the peer closes, socket.timeout when none comes in time
    c.try_send(line, timeout)   (reply, None), or (None, 'closed' | 'timeout' | 'oserror <why>'): a test that expects a death
    c.expect(line, wanted)      the reply, AssertionError when it is not wanted
    c.command(verb, *args)      send(), its line built by protocol().encode(verb, args)
    c.reply(line)               protocol().parse(line): a reply already read, structured
"""
import os
import socket
import sys
import time

try:
    import plugin_hostd_protocol
except ImportError:
    # no python3-plugin-hostd-protocol installed: this tree's own clients/python, as a checkout runs it
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                     "clients", "python"))
    import plugin_hostd_protocol

_protocol = None


def protocol():
    """plugin_hostd_protocol.Protocol(), built once: the codec every command and reply of this module goes through."""
    global _protocol
    if _protocol is None:
        _protocol = plugin_hostd_protocol.Protocol()
    return _protocol


class Client:
    def __init__(self, sock, timeout=10.0):
        self.sock = sock
        self.timeout = timeout
        self.buf = b""

    @classmethod
    def connect(cls, port, host="127.0.0.1", timeout=10.0):
        return cls(socket.create_connection((host, port), timeout=timeout), timeout)

    def send(self, line, timeout=None):
        self.sock.sendall(line.encode() + b"\0")
        end = time.monotonic() + (self.timeout if timeout is None else timeout)
        while b"\0" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                raise socket.timeout("no reply to %r" % line)
            self.sock.settimeout(left)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("the peer closed on " + line)
            self.buf += chunk
        reply, self.buf = self.buf.split(b"\0", 1)
        return reply.decode(errors="replace")

    def try_send(self, line, timeout=None):
        try:
            return self.send(line, timeout), None
        except socket.timeout:
            return None, "timeout"
        except ConnectionError:
            return None, "closed"
        except OSError as e:
            return None, "oserror %s" % e

    def expect(self, line, wanted):
        reply = self.send(line)
        if reply != wanted:
            raise AssertionError("%s -> %r, wanted %r" % (line, reply, wanted))
        return reply

    def command(self, verb, *args, tag=None, timeout=None):
        """send(), its line built by protocol().encode(): no caller of this client spells a command's quoting by
        hand."""
        return self.send(protocol().encode(verb, args, tag), timeout)

    def reply(self, line):
        """protocol().parse() of a reply already read (send()'s or try_send()'s return, or a feedback line):
        its tag, sequence number and, by kind, a resp code and its name, a feedback line's arguments, or a
        protocol error."""
        return protocol().parse(line)

    def close(self):
        self.sock.close()
