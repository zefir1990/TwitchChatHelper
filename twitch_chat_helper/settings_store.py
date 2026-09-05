import json
import wx
from pathlib import Path
from typing import Optional


class SettingsStore:
    SETTINGS_FILE_NAME = "tts_settings.json"

    def __init__(self, settings_file_path: Optional[Path] = None) -> None:
        self._settings_file_path = settings_file_path or self._default_settings_file_path()

    def load_tts_checkbox_state(self) -> bool:
        try:
            with open(self._settings_file_path, encoding="utf-8") as settings_file:
                stored_state = json.load(settings_file)
        except (OSError, json.JSONDecodeError):
            return True
        return stored_state if isinstance(stored_state, bool) else True

    def save_tts_checkbox_state(self, is_checked: bool) -> None:
        self._settings_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._settings_file_path, "w", encoding="utf-8") as settings_file:
            json.dump(is_checked, settings_file)

    @staticmethod
    def _default_settings_file_path() -> Path:
        return Path(wx.StandardPaths.Get().GetUserDataDir()) / SettingsStore.SETTINGS_FILE_NAME
