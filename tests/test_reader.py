import pytest

from attendance_terminal.reader import GET_UID, _read_uid


class FakeConnection:
    def __init__(self, response):
        self.response = response
        self.connected = False
        self.disconnected = False
        self.released = False
        self.commands = []

    def connect(self):
        self.connected = True

    def transmit(self, command):
        self.commands.append(command)
        return self.response

    def disconnect(self):
        self.disconnected = True

    def release(self):
        self.released = True


class FakeCard:
    def __init__(self, response):
        self.connection = FakeConnection(response)

    def createConnection(self):
        return self.connection


def test_read_uid_reads_once_and_disconnects():
    card = FakeCard(([0x04, 0xA1, 0xB2, 0xC3], 0x90, 0x00))

    assert _read_uid(card) == "04A1B2C3"
    assert card.connection.connected
    assert card.connection.commands == [GET_UID]
    assert card.connection.disconnected
    assert card.connection.released


def test_read_uid_disconnects_after_failed_command():
    card = FakeCard(([], 0x6A, 0x82))

    with pytest.raises(RuntimeError, match="GET UID failed: 6A82"):
        _read_uid(card)

    assert card.connection.disconnected
    assert card.connection.released
