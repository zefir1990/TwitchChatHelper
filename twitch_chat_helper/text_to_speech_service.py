import random
import re
import shutil
import subprocess
import threading
from collections import deque
from typing import List, Optional

_LANGUAGE_TOKEN_PATTERN = re.compile(r"\s[a-zA-Z]{2,3}[_-][a-zA-Z]{2,3}(?:\s|$)")


def discover_available_voices() -> List[str]:
    if shutil.which("say") is None:
        return []
    try:
        listing_result = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    voice_names = []
    for listing_line in listing_result.stdout.splitlines():
        language_token_match = _LANGUAGE_TOKEN_PATTERN.search(listing_line)
        if language_token_match is None:
            continue
        voice_name = listing_line[:language_token_match.start()].strip()
        if voice_name and voice_name not in voice_names:
            voice_names.append(voice_name)
    return voice_names


class SenderVoiceAssigner:
    def __init__(self, available_voices: List[str]) -> None:
        self._available_voices = list(available_voices)
        self._voices_by_sender = {}
        self._refill_voice_pool()

    def voice_for_sender(self, sender_name: str) -> Optional[str]:
        if not self._available_voices:
            return None
        if sender_name not in self._voices_by_sender:
            if not self._voice_pool:
                self._refill_voice_pool()
            self._voices_by_sender[sender_name] = self._voice_pool.pop()
        return self._voices_by_sender[sender_name]

    def _refill_voice_pool(self) -> None:
        self._voice_pool = list(self._available_voices)
        random.shuffle(self._voice_pool)


class TextToSpeechService:
    MAXIMUM_PENDING_MESSAGES = 64
    SPEECH_PROCESS_POLL_INTERVAL_SECONDS = 0.05

    def __init__(self, speech_command: List[str]) -> None:
        self._speech_command = speech_command
        self._pending_messages: deque = deque()
        self._condition = threading.Condition()
        self._current_process: Optional[subprocess.Popen] = None
        if speech_command:
            self._speech_worker = threading.Thread(target=self._speech_worker_loop, daemon=True)
            self._speech_worker.start()

    def speak(self, text: str, voice_name: Optional[str] = None) -> None:
        if not text or not self._speech_command:
            return
        with self._condition:
            if len(self._pending_messages) >= self.MAXIMUM_PENDING_MESSAGES:
                self._pending_messages.popleft()
            self._pending_messages.append((text, voice_name))
            self._condition.notify()

    def clear_pending_speech(self) -> None:
        with self._condition:
            self._pending_messages.clear()
            process_to_stop = self._current_process
            self._current_process = None
        if process_to_stop is not None:
            try:
                process_to_stop.terminate()
            except OSError:
                pass

    def _speech_worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._pending_messages:
                    self._condition.wait()
                text_to_speak, voice_name = self._pending_messages.popleft()
            speech_command_with_voice = self._speech_command
            if voice_name:
                speech_command_with_voice = self._speech_command + ["-v", voice_name]
            process_to_wait = subprocess.Popen(
                speech_command_with_voice + [text_to_speak],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            with self._condition:
                self._current_process = process_to_wait
            self._wait_until_process_finished(process_to_wait)
            with self._condition:
                if self._current_process is process_to_wait:
                    self._current_process = None

    def _wait_until_process_finished(self, process_to_wait: subprocess.Popen) -> None:
        while True:
            try:
                process_to_wait.wait(timeout=self.SPEECH_PROCESS_POLL_INTERVAL_SECONDS)
                return
            except subprocess.TimeoutExpired:
                with self._condition:
                    is_still_current = self._current_process is process_to_wait
                if not is_still_current:
                    process_to_wait.terminate()
                    process_to_wait.wait()
                    return


def create_platform_text_to_speech_service() -> TextToSpeechService:
    speech_command: List[str] = []
    if shutil.which("say") is not None:
        speech_command = ["say", "-r", "175"]
    return TextToSpeechService(speech_command)
