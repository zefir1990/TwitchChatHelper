import wx
from datetime import datetime
from typing import Optional

from .chat_message import ChatMessage
from .settings_store import SettingsStore
from .text_to_speech_service import (
    SenderVoiceAssigner,
    TextToSpeechService,
    create_platform_text_to_speech_service,
    discover_available_voices)
from .time_utils import current_unix_time_ms
from .transliteration import transliterate_to_latin
from .twitch_chat_client import ConnectionState, TwitchChatClient


class ChatFrame(wx.Frame):
    MAXIMUM_CHAT_LOG_LINES = 2000

    def __init__(self) -> None:
        super().__init__(None, title="Twitch Chat Helper", size=(640, 560))
        self._is_closing = False
        self._connection_active = False
        self._tts_enabled_at_unix_ms = 0
        self._text_to_speech_service: Optional[TextToSpeechService] = None
        self._settings_store = SettingsStore()
        self._sender_voice_assigner = SenderVoiceAssigner(discover_available_voices())
        self._twitch_client = TwitchChatClient(
            on_chat_message=lambda message: wx.CallAfter(self._on_chat_message_received, message),
            on_connection_state=lambda state, description: wx.CallAfter(
                self._on_connection_state_changed, state, description))

        self.SetMinSize((480, 360))
        self.CenterOnScreen()
        self.CreateStatusBar(1)
        self.SetStatusText("Enter a Twitch account name and press Connect")

        account_label = wx.StaticText(self, label="Twitch account:")
        self._channel_name_input = wx.TextCtrl(
            self, size=(240, -1), style=wx.TE_PROCESS_ENTER)
        self._connect_button = wx.Button(self, label="Connect")
        connection_row = wx.BoxSizer(wx.HORIZONTAL)
        connection_row.Add(account_label, 0, wx.ALIGN_CENTER_VERTICAL)
        connection_row.Add(self._channel_name_input, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        connection_row.Add(self._connect_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)

        self._chat_log = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._chat_log.SetFont(wx.Font(13, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        self._tts_checkbox = wx.CheckBox(self, label="Read new messages aloud (TTS)")
        self._tts_checkbox.SetValue(self._settings_store.load_tts_checkbox_state())
        self._synchronize_tts_enabled_state()

        main_layout = wx.BoxSizer(wx.VERTICAL)
        main_layout.Add(connection_row, 0, wx.EXPAND | wx.ALL, 8)
        main_layout.Add(self._chat_log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        main_layout.Add(self._tts_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, 8)
        self.SetSizer(main_layout)

        self._connect_button.Bind(wx.EVT_BUTTON, self._on_connect_button_clicked)
        self._channel_name_input.Bind(wx.EVT_TEXT_ENTER, self._on_channel_name_entered)
        self._tts_checkbox.Bind(wx.EVT_CHECKBOX, self._on_tts_checkbox_changed)
        self.Bind(wx.EVT_CLOSE, self._on_close_window)

        self._channel_name_input.SetFocus()

    def _on_connect_button_clicked(self, _event) -> None:
        if self._connection_active:
            self._stop_connection()
            return
        self._begin_connection_attempt()

    def _on_channel_name_entered(self, _event) -> None:
        if not self._connection_active:
            self._begin_connection_attempt()

    def _on_tts_checkbox_changed(self, _event) -> None:
        self._synchronize_tts_enabled_state()
        self._settings_store.save_tts_checkbox_state(self._tts_checkbox.GetValue())

    def _synchronize_tts_enabled_state(self) -> None:
        if self._tts_checkbox.GetValue():
            self._tts_enabled_at_unix_ms = current_unix_time_ms()
            if self._text_to_speech_service is None:
                self._text_to_speech_service = create_platform_text_to_speech_service()
        elif self._text_to_speech_service is not None:
            self._text_to_speech_service.clear_pending_speech()

    def _on_chat_message_received(self, chat_message: ChatMessage) -> None:
        if self._is_closing or not chat_message.content:
            return
        self._append_chat_message_to_log(chat_message)
        if (self._tts_checkbox.GetValue() and
                chat_message.unix_time_ms >= self._tts_enabled_at_unix_ms and
                self._text_to_speech_service is not None):
            spoken_text = transliterate_to_latin(chat_message.content)
            if not spoken_text:
                return
            sender_voice = self._sender_voice_assigner.voice_for_sender(chat_message.author_name)
            self._text_to_speech_service.speak(spoken_text, sender_voice)

    def _on_connection_state_changed(self, connection_state: ConnectionState, description: str) -> None:
        if self._is_closing:
            return
        if connection_state == ConnectionState.CONNECTED:
            self._connection_active = True
            self._connect_button.SetLabel("Stop")
            self.SetStatusText("Connected to #" + description + " chat")
            return
        self._connection_active = False
        self._connect_button.SetLabel("Connect")
        self.SetStatusText(description if description else "Disconnected")

    def _on_close_window(self, event) -> None:
        self._is_closing = True
        self._twitch_client.disconnect()
        self._settings_store.save_tts_checkbox_state(self._tts_checkbox.GetValue())
        if self._text_to_speech_service is not None:
            self._text_to_speech_service.clear_pending_speech()
        event.Skip()

    def _begin_connection_attempt(self) -> None:
        channel_name = self._channel_name_input.GetValue().strip()
        if channel_name.startswith("#"):
            channel_name = channel_name[1:].strip()
        if not channel_name:
            self.SetStatusText("Enter a Twitch account name to join its chat")
            self._channel_name_input.SetFocus()
            return
        if " " in channel_name or "\t" in channel_name:
            self.SetStatusText("Twitch account names cannot contain spaces")
            return
        channel_name = channel_name.lower()
        self._connection_active = True
        self._connect_button.SetLabel("Stop")
        self.SetStatusText("Connecting to #" + channel_name + " chat...")
        self._twitch_client.connect_to_channel(channel_name)

    def _stop_connection(self) -> None:
        if not self._connection_active:
            return
        self._connection_active = False
        self._connect_button.SetLabel("Connect")
        self.SetStatusText("Disconnected")
        self._twitch_client.disconnect()

    def _append_chat_message_to_log(self, chat_message: ChatMessage) -> None:
        time_text = datetime.fromtimestamp(chat_message.unix_time_ms / 1000).strftime("%H:%M:%S")
        self._chat_log.AppendText(
            "[" + time_text + "] " + chat_message.author_name + ": " + chat_message.content + "\n")
        self._trim_chat_log_to_maximum_lines()

    def _trim_chat_log_to_maximum_lines(self) -> None:
        while self._chat_log.GetNumberOfLines() > self.MAXIMUM_CHAT_LOG_LINES:
            first_line_length = self._chat_log.GetLineLength(0)
            self._chat_log.Remove(0, first_line_length + 1)
