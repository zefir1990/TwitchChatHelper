from unidecode import unidecode


def transliterate_to_latin(text: str) -> str:
    if text.isascii():
        return text
    return unidecode(text)
