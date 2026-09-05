import random
import socket
import threading
import time
from enum import Enum
from typing import Callable, Optional

from .chat_message import ChatMessage
from .irc_line_parser import IrcLineParser
from .time_utils import current_unix_time_ms


class ConnectionState(Enum):
    CONNECTED = 1
    DISCONNECTED = 2


class TwitchChatClient:
    HOST_NAME = "irc.chat.twitch.tv"
    PORT_NUMBER = 6667
    ANONYMOUS_PASSWORD = "SCHMOOPIIE"
    SOCKET_RECEIVE_TIMEOUT_SECONDS = 1.0
    CONNECT_TIMEOUT_SECONDS = 10.0
    JOIN_TIMEOUT_SECONDS = 12.0

    def __init__(self,
                 on_chat_message: Callable[[ChatMessage], None],
                 on_connection_state: Callable[[ConnectionState, str], None]) -> None:
        self._on_chat_message = on_chat_message
        self._on_connection_state = on_connection_state
        self._stop_event = threading.Event()
        self._connected_flag = threading.Event()
        self._connected_socket: Optional[socket.socket] = None
        self._worker_thread: Optional[threading.Thread] = None

    def connect_to_channel(self, channel_name: str) -> None:
        self.disconnect()
        self._stop_event.clear()
        self._connected_flag.clear()
        self._worker_thread = threading.Thread(
            target=self._connection_worker, args=(channel_name,), daemon=True)
        self._worker_thread.start()

    def disconnect(self) -> None:
        self._stop_event.set()
        active_socket = self._connected_socket
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._worker_thread is not None:
            self._worker_thread.join()
            self._worker_thread = None

    def is_connected(self) -> bool:
        return self._connected_flag.is_set()

    @staticmethod
    def _generate_anonymous_nickname() -> str:
        return "justinfan" + str(random.randint(10000, 99999))

    @staticmethod
    def _send_line(active_socket: socket.socket, line: str) -> bool:
        try:
            active_socket.sendall((line + "\r\n").encode("utf-8"))
            return True
        except OSError:
            return False

    @staticmethod
    def _is_welcome_message(line: str) -> bool:
        return " 001 " in line

    @staticmethod
    def _is_own_join_echo(line: str, nickname: str, channel_name: str) -> bool:
        return line.startswith(":" + nickname + "!") and " JOIN #" + channel_name in line

    def _connection_worker(self, channel_name: str) -> None:
        parser = IrcLineParser()
        try:
            self._run_connection(channel_name, parser)
        except OSError:
            if not self._stop_event.is_set():
                self._on_connection_state(ConnectionState.DISCONNECTED, "Connection to Twitch chat failed")
        finally:
            self._connected_flag.clear()
            if self._connected_socket is not None:
                try:
                    self._connected_socket.close()
                except OSError:
                    pass
                self._connected_socket = None

    def _run_connection(self, channel_name: str, parser: IrcLineParser) -> None:
        try:
            active_socket = socket.create_connection(
                (self.HOST_NAME, self.PORT_NUMBER), timeout=self.CONNECT_TIMEOUT_SECONDS)
        except OSError:
            if not self._stop_event.is_set():
                self._on_connection_state(ConnectionState.DISCONNECTED, "Could not connect to Twitch chat")
            return
        self._connected_socket = active_socket
        active_socket.settimeout(self.SOCKET_RECEIVE_TIMEOUT_SECONDS)
        nickname = self._generate_anonymous_nickname()
        self._send_line(active_socket, "PASS " + self.ANONYMOUS_PASSWORD)
        self._send_line(active_socket, "NICK " + nickname)
        receive_buffer = ""
        welcome_received = False
        join_echo_received = False
        join_request_time = time.monotonic()
        while not self._stop_event.is_set():
            try:
                received_data = active_socket.recv(4096)
            except socket.timeout:
                if (welcome_received and not join_echo_received and
                        time.monotonic() - join_request_time > self.JOIN_TIMEOUT_SECONDS):
                    self._on_connection_state(
                        ConnectionState.DISCONNECTED, "Channel not found or join timed out")
                    return
                continue
            except OSError:
                if not self._stop_event.is_set():
                    self._on_connection_state(ConnectionState.DISCONNECTED, "Connection to Twitch chat was lost")
                return
            if not received_data:
                if not self._stop_event.is_set():
                    self._on_connection_state(ConnectionState.DISCONNECTED, "Twitch closed the connection")
                return
            receive_buffer += received_data.decode("utf-8", errors="replace")
            line_end_position = receive_buffer.find("\n")
            while line_end_position != -1:
                single_line = receive_buffer[:line_end_position].rstrip("\r")
                receive_buffer = receive_buffer[line_end_position + 1:]
                if not single_line:
                    line_end_position = receive_buffer.find("\n")
                    continue
                if single_line.startswith("PING "):
                    self._send_line(active_socket, "PONG :tmi.twitch.tv")
                elif not welcome_received:
                    if self._is_welcome_message(single_line):
                        welcome_received = True
                        self._send_line(active_socket, "CAP REQ :twitch.tv/tags")
                        self._send_line(active_socket, "JOIN #" + channel_name)
                elif not join_echo_received:
                    if self._is_own_join_echo(single_line, nickname, channel_name):
                        join_echo_received = True
                        self._connected_flag.set()
                        self._on_connection_state(ConnectionState.CONNECTED, channel_name)
                else:
                    parsed_message = parser.parse_chat_message(single_line)
                    if parsed_message is not None:
                        if parsed_message.unix_time_ms == 0:
                            parsed_message.unix_time_ms = current_unix_time_ms()
                        self._on_chat_message(parsed_message)
                line_end_position = receive_buffer.find("\n")
