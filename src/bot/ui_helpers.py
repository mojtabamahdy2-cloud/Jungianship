import re
import html
from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def markdown_to_telegram_html(text: str) -> str:
    """Convert standard markdown formatting to Telegram-compatible HTML."""
    if not text:
        return ""

    # 1. Escape HTML special characters first
    escaped = html.escape(text)

    # 2. Convert headers (### Heading -> <b>Heading</b>)
    escaped = re.sub(r'^(?:#{1,6})\s*(.+)$', r'<b>\1</b>', escaped, flags=re.MULTILINE)

    # 3. Convert bold (**text** or __text__ -> <b>text</b>)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)
    escaped = re.sub(r'__(.+?)__', r'<b>\1</b>', escaped)

    # 4. Convert italics (*text* or _text_ -> <i>text</i>)
    escaped = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'<i>\1</i>', escaped)
    escaped = re.sub(r'(?<!\w)_([^_\n]+?)_(?!\w)', r'<i>\1</i>', escaped)

    # 5. Convert blockquotes (> quote)
    escaped = re.sub(r'^&gt;\s*(.+)$', r'<blockquote>\1</blockquote>', escaped, flags=re.MULTILINE)

    # 6. Convert inline code (`code`)
    escaped = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', escaped)

    # 7. Convert horizontal rules (--- or ***)
    escaped = re.sub(r'^(?:---|\*\*\*|___)\s*$', r'—————————————', escaped, flags=re.MULTILINE)

    return escaped

def split_message(text: str, max_chars: int = 3800) -> List[str]:
    """Split long text into readable chunks adhering to Telegram limit (< 4096)."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= max_chars:
            current_chunk = f"{current_chunk}\n\n{p}" if current_chunk else p
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # If a single paragraph is longer than max_chars
            if len(p) > max_chars:
                lines = p.split("\n")
                sub_chunk = ""
                for line in lines:
                    if len(sub_chunk) + len(line) + 1 <= max_chars:
                        sub_chunk = f"{sub_chunk}\n{line}" if sub_chunk else line
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk.strip())
                        sub_chunk = line
                if sub_chunk:
                    current_chunk = sub_chunk
            else:
                current_chunk = p

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main navigation menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💭 Philosophical Consultation", callback_data="btn_ask_help"),
            InlineKeyboardButton("🌙 Dream Analysis", callback_data="btn_dream_help")
        ],
        [
            InlineKeyboardButton("📖 Jungian Glossary", callback_data="btn_concept_help"),
            InlineKeyboardButton("✨ Synchronicity / Quote", callback_data="btn_quote")
        ],
        [
            InlineKeyboardButton("🎭 Switch Persona Mode", callback_data="btn_toggle_mode"),
            InlineKeyboardButton("📊 Corpus Stats", callback_data="btn_stats")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_response_keyboard(citations: List[str]) -> InlineKeyboardMarkup:
    """Interactive follow-up keyboard after an answer."""
    buttons = []
    if citations:
        buttons.append(InlineKeyboardButton("📚 Sources & References", callback_data="btn_view_sources"))
    buttons.append(InlineKeyboardButton("⚖️ Tension of Opposites", callback_data="btn_opposites"))
    return InlineKeyboardMarkup([buttons])
