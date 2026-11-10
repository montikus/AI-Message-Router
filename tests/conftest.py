import socket
from email import policy
from email.parser import BytesParser

import pytest
from aiosmtpd.controller import Controller


# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
class Inbox:
    def __init__(self):
        self.messages = []
        self.envelopes = []
        self.reject = False

    async def handle_DATA(self, server, session, envelope):
        if self.reject:
            return "550 Rejected for testing"
        self.messages.append(BytesParser(policy=policy.default).parsebytes(envelope.content))
        self.envelopes.append(envelope)
        return "250 Message accepted"


@pytest.fixture
def smtp_server():
    inbox = Inbox()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    controller = Controller(
        inbox, hostname="127.0.0.1", server_hostname="test.local", port=port, ready_timeout=5
    )
    controller.start()
    try:
        yield inbox, port
    finally:
        controller.stop()
