from typing import Optional

from .chat_message import ChatMessage


class IrcLineParser:
    @staticmethod
    def _split_tag_pairs(tags_section: str) -> dict:
        tag_pairs = {}
        if not tags_section:
            return tag_pairs
        for single_tag in tags_section.split(";"):
            if "=" not in single_tag:
                continue
            key, value = single_tag.split("=", 1)
            unescaped_value = ""
            index = 0
            while index < len(value):
                if value[index] == "\\" and index + 1 < len(value):
                    escaped_character = value[index + 1]
                    if escaped_character == "s":
                        unescaped_value += " "
                    elif escaped_character == ":":
                        unescaped_value += ";"
                    elif escaped_character == "\\":
                        unescaped_value += "\\"
                    elif escaped_character == "r":
                        unescaped_value += "\r"
                    elif escaped_character == "n":
                        unescaped_value += "\n"
                    else:
                        unescaped_value += escaped_character
                    index += 2
                else:
                    unescaped_value += value[index]
                    index += 1
            tag_pairs[key] = unescaped_value
        return tag_pairs

    @staticmethod
    def _parse_author_name_from_prefix(prefix: str) -> str:
        bang_position = prefix.find("!")
        return prefix if bang_position == -1 else prefix[:bang_position]

    def parse_chat_message(self, raw_line: str) -> Optional[ChatMessage]:
        cursor_position = 0
        tags_section = ""
        if raw_line.startswith("@"):
            tags_end_position = raw_line.find(" ")
            if tags_end_position == -1:
                return None
            tags_section = raw_line[1:tags_end_position]
            cursor_position = tags_end_position + 1
        line_without_tags = raw_line[cursor_position:]
        if not line_without_tags:
            return None
        prefix = ""
        if line_without_tags.startswith(":"):
            prefix_end_position = line_without_tags.find(" ")
            if prefix_end_position == -1:
                return None
            prefix = line_without_tags[1:prefix_end_position]
            cursor_position = prefix_end_position + 1
        else:
            cursor_position = 0
        line_tokens = line_without_tags[cursor_position:].split(" ")
        if not line_tokens or line_tokens[0] != "PRIVMSG":
            return None
        message_start_position = line_without_tags.find(":", cursor_position)
        if message_start_position == -1:
            return None
        message_content = line_without_tags[message_start_position + 1:]
        if message_content.startswith("\x01ACTION") and message_content.endswith("\x01"):
            inner_action_text = message_content[len("\x01ACTION"):-1].strip()
            message_content = "" if not inner_action_text else "* " + inner_action_text
        tag_pairs = self._split_tag_pairs(tags_section)
        author_name = tag_pairs.get("display-name", "")
        if not author_name:
            author_name = self._parse_author_name_from_prefix(prefix)
        try:
            sent_time_ms = int(tag_pairs["tmi-sent-ts"])
        except (KeyError, ValueError):
            sent_time_ms = 0
        return ChatMessage(author_name, message_content, sent_time_ms)
