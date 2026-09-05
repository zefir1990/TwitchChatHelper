# Twitch Chat Helper

A small wxPython desktop application that connects to a Twitch channel's chat and displays every incoming message. An optional text-to-speech mode reads new messages aloud.

## Features

- Connect to any Twitch channel by entering its account name — no OAuth token required (read-only anonymous connection)
- Live chat log with local timestamps (`[HH:MM:SS] author: message`), capped at the most recent 2000 lines
- **TTS mode**: "Read new messages aloud (TTS)" is checked by default and its state is remembered between launches (stored in `~/Library/Application Support/TwitchChatHelper/tts_settings.json`). When on, new messages are spoken aloud (message content only, without the sender name — the per-sender voice is what tells speakers apart)
  - "New" is decided by Unix time: the moment the checkbox is enabled is recorded, and only messages whose server timestamp is at or after that moment are spoken — messages that were already in the chat are never re-read
  - Unchecking stops the current utterance and drops the pending speech queue
- **One voice per sender**: the first time a sender is spoken, they are assigned a random system voice; the mapping stays fixed for the rest of the session, so you can tell chat participants apart by voice. Voices are drawn without repeats until the pool is exhausted, then the cycle restarts
- **Transliteration**: non-English text (Cyrillic, Chinese, Arabic, Greek, etc.) is converted to Latin letters before being read, so any voice can pronounce it. The chat log always keeps the original text

## Requirements

- Python 3.9+
- macOS (speech uses the built-in `say` command; other platforms run without audio)
- wxPython

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running

```bash
.venv/bin/python main.py
```

Type a Twitch account name (for example `xqc`) and press **Connect** or **Enter**. The status bar shows connection progress; the button becomes **Stop** while connected.

## How it works

- `TwitchChatClient` runs a socket worker thread speaking the Twitch IRC protocol (`irc.chat.twitch.tv:6667`): anonymous registration, `twitch.tv/tags` capability, channel `JOIN`, and `PING`/`PONG` keep-alive. Messages are delivered to the UI thread via `wx.CallAfter`.
- `IrcLineParser` extracts the display name, message text, and the server-provided `tmi-sent-ts` Unix timestamp (falling back to receive time when absent).
- `TextToSpeechService` speaks through the native macOS `say` command with a serialized queue, so rapid chat never overlaps speech. `SenderVoiceAssigner` randomly maps each sender to a voice from `say -v '?'` on their first spoken message and keeps that mapping for the app's lifetime. `transliteration.py` converts non-Latin text to its Latin reading first.

## Project layout

| Path | Responsibility |
| --- | --- |
| `main.py` | wx.App entry point |
| `twitch_chat_helper/chat_frame.py` | Window, controls, and the TTS Unix-time gate |
| `twitch_chat_helper/twitch_chat_client.py` | Threaded IRC connection lifecycle |
| `twitch_chat_helper/irc_line_parser.py` | IRC line → `ChatMessage` parsing |
| `twitch_chat_helper/text_to_speech_service.py` | Native speech queue and per-sender voice assignment |
| `twitch_chat_helper/transliteration.py` | Non-Latin text → Latin transliteration for speech |
| `twitch_chat_helper/settings_store.py` | Persistent storage for the TTS checkbox state |
| `twitch_chat_helper/chat_message.py` | `ChatMessage` data model |
| `twitch_chat_helper/time_utils.py` | Unix time helpers |
