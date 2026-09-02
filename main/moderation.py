import unicodedata

from django.conf import settings


def normalize_moderation_text(value):
    """Normalize text into case-insensitive, punctuation-separated tokens."""
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join(
        "".join(
            character if character.isalnum() else " " for character in normalized
        ).split()
    )


def contains_trigger_word(value, trigger_words=None):
    """Return whether value contains a configured whole-word or whole-phrase trigger."""
    words = settings.MODERATION_TRIGGER_WORDS if trigger_words is None else trigger_words
    normalized_value = f" {normalize_moderation_text(value)} "

    for word in words:
        normalized_word = normalize_moderation_text(word)
        if normalized_word and f" {normalized_word} " in normalized_value:
            return True
    return False
