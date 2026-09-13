import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from src.db.repository import Repository
from src.engine.generator import DialecticalEngine
from src.config import PERSONA_NAME, PERSONA_DOMAIN
from src.bot.ui_helpers import (
    markdown_to_telegram_html,
    split_message,
    get_main_menu_keyboard,
    get_response_keyboard
)

logger = logging.getLogger(__name__)

class BotHandlers:
    def __init__(self, repository: Repository, engine: DialecticalEngine):
        self.repo = repository
        self.engine = engine

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message and introduction."""
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        self.repo.set_user_mode(user_id, mode="first_person", chat_id=chat_id)

        welcome_text = (
            f"Greetings, <b>{user.first_name}</b>.\n\n"
            f"I am <b>{PERSONA_NAME}</b>. Welcome to a sanctuary for "
            f"contemplating the deep, unspoken questions of {PERSONA_DOMAIN}.\n\n"
            "My discourse is drawn directly from my primary writings and corpus.\n\n"
            "<b>How you may engage with me:</b>\n"
            "• Simply send any philosophical question or inner struggle.\n"
            "• <code>/dream &lt;description&gt;</code> — Unfold the symbols of a dream or inner vision.\n"
            "• <code>/concept &lt;term&gt;</code> — Look up an authoritative definition.\n"
            "• <code>/quote</code> — Receive a meaningful aphorism.\n"
            "• <code>/mode</code> — Switch between speaking with me directly or with a scholarly guide.\n"
            "• <code>/clear</code> — Reset our dialogue history.\n\n"
            "<i>\"Who looks outside, dreams; who looks inside, awakes.\"</i>"
        )

        await update.message.reply_text(
            welcome_text,
            parse_mode=constants.ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help guide."""
        help_text = (
            f"<b>🌿 Consultation Guide</b>\n\n"
            "<b>Available Inquiries:</b>\n"
            "• <b>Direct Message</b> or <code>/ask &lt;question&gt;</code>\n"
            "  Ask deep questions regarding life, relationships, morality, or existential crises.\n\n"
            "• <code>/dream &lt;your dream&gt;</code>\n"
            "  Examine a dream through personal associations and symbolic amplification.\n\n"
            "• <code>/concept &lt;term&gt;</code>\n"
            f"  Authoritative definitions from the primary corpus.\n\n"
            "• <code>/quote</code> or <code>/synchronicity</code>\n"
            "  Draw a meaningful passage or aphorism.\n\n"
            "• <code>/mode [first_person|scholar]</code>\n"
            f"  Switch between 1st-person {PERSONA_NAME} and an academic guide.\n\n"
            "• <code>/sources</code>\n"
            "  Inspect the primary sources cited in our dialogue.\n\n"
            "• <code>/clear</code>\n"
            "  Clear conversation context to start fresh."
        )
        await update.message.reply_text(help_text, parse_mode=constants.ParseMode.HTML)

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /ask command or plain text messages."""
        user = update.effective_user
        user_id = user.id

        # Extract text if invoked via /ask or direct text
        if update.message.text.startswith("/ask"):
            query = update.message.text[4:].strip()
            if not query:
                await update.message.reply_text(
                    "Please share the philosophical question you wish to explore.\n"
                    "Example: <code>/ask What is the purpose of suffering?</code>",
                    parse_mode=constants.ParseMode.HTML
                )
                return
        else:
            query = update.message.text.strip()

        if not query:
            return

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

        # Retrieve user history & mode
        mode = self.repo.get_user_mode(user_id)
        history = self.repo.get_history(user_id, limit=4)

        # Generate grounded response
        result = self.engine.generate_response(query, mode=mode, history=history)
        reply_text = result["text"]
        citations = result["citations"]

        # Persist conversation
        self.repo.save_message(user_id, "user", query)
        self.repo.save_message(user_id, "assistant", reply_text, citations=citations)

        # Format and send in chunks
        html_text = markdown_to_telegram_html(reply_text)
        chunks = split_message(html_text)

        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            markup = get_response_keyboard(citations) if is_last else None
            try:
                await update.message.reply_text(
                    chunk,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=markup
                )
            except Exception as e:
                logger.warning(f"HTML parse failed ({e}), falling back to plain text.")
                await update.message.reply_text(reply_text, reply_markup=markup)

    async def dream(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /dream command."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Please describe your dream after the command:\n"
                "Example: <code>/dream I was in a dark subterranean basement and found an ancient key...</code>",
                parse_mode=constants.ParseMode.HTML
            )
            return

        dream_text = " ".join(args).strip()
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

        result = self.engine.analyze_dream(dream_text)
        reply_text = result["text"]

        html_text = markdown_to_telegram_html(reply_text)
        chunks = split_message(html_text)
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode=constants.ParseMode.HTML)
            except Exception:
                await update.message.reply_text(reply_text)

    async def concept(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /concept command."""
        args = context.args
        if not args:
            await update.message.reply_text(
                "Specify the term you wish to explore:\n"
                "Example: <code>/concept shadow</code> or <code>/concept transcendent function</code>",
                parse_mode=constants.ParseMode.HTML
            )
            return

        term = " ".join(args).strip()
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

        result = self.engine.define_concept(term)
        reply_text = result["text"]

        html_text = markdown_to_telegram_html(reply_text)
        try:
            await update.message.reply_text(html_text, parse_mode=constants.ParseMode.HTML)
        except Exception:
            await update.message.reply_text(reply_text)

    async def quote_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /quote command."""
        q = self.repo.get_random_quote()
        if not q:
            await update.message.reply_text("No aphorisms found.")
            return

        text = (
            f"✨ <b>Meaningful Aphorism</b>\n\n"
            f"<blockquote>\"{q['quote']}\"</blockquote>\n\n"
            f"— <b>{q['source']}</b>\n"
            f"<i>Source: {q.get('cw_ref', 'Primary Works')}</i>\n"
            f"<i>Theme: {q.get('theme', 'Wisdom')}</i>"
        )
        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

    async def mode_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /mode command."""
        user_id = update.effective_user.id
        args = context.args

        if args and args[0].lower() in ["first_person", "scholar", "jung"]:
            new_mode = args[0].lower()
            # Normalize legacy 'jung' to 'first_person'
            if new_mode == "jung":
                new_mode = "first_person"
            self.repo.set_user_mode(user_id, mode=new_mode)
            desc = f"First-Person {PERSONA_NAME}" if new_mode == "first_person" else "Scholarly Academic Guide"
            await update.message.reply_text(f"Voice mode updated to: <b>{desc}</b>.", parse_mode=constants.ParseMode.HTML)
            return

        current = self.repo.get_user_mode(user_id)
        desc = f"First-Person {PERSONA_NAME}" if current in ("first_person", "jung") else "Scholarly Academic Guide"
        text = (
            f"Current voice mode: <b>{desc}</b>\n\n"
            "To change, use:\n"
            f"• <code>/mode first_person</code> — Speaks directly as {PERSONA_NAME}.\n"
            "• <code>/mode scholar</code> — Speaks as an academic analytical guide."
        )
        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

    async def sources_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show sources and citations from recent messages."""
        user_id = update.effective_user.id
        history = self.repo.get_history(user_id, limit=6)
        citations = []
        for h in history:
            if h.get("citations"):
                citations.extend(h["citations"])

        if not citations:
            await update.message.reply_text("No citations recorded in recent messages yet.")
            return

        unique_cits = list(dict.fromkeys(citations))
        text = "📚 <b>Primary Sources Cited in Our Dialogue:</b>\n\n"
        for c in unique_cits:
            text += f"• <i>{c}</i>\n"

        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

    async def clear_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear chat history."""
        user_id = update.effective_user.id
        self.repo.clear_history(user_id)
        await update.message.reply_text("Our prior dialogue has returned to silence. The slate is clear.")

    async def stats_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Corpus and database stats."""
        stats = self.repo.get_stats()
        vols = "\n".join(f"  • {v}" for v in stats["volumes"][:8])
        text = (
            "📊 <b>Corpus Statistics:</b>\n\n"
            f"• <b>Documents Indexed:</b> {stats['document_count']}\n"
            f"• <b>Total Text Chunks:</b> {stats['chunk_count']:,}\n"
            f"• <b>Vector Embedded Chunks:</b> {stats['embedded_count']:,}\n"
            f"• <b>Key Volumes:</b>\n{vols}"
        )
        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks."""
        query = update.callback_query
        await query.answer()

        data = query.data
        if data == "btn_quote":
            q = self.repo.get_random_quote()
            if q:
                text = (
                    f"✨ <b>Meaningful Aphorism</b>\n\n"
                    f"<blockquote>\"{q['quote']}\"</blockquote>\n\n"
                    f"— <b>{q['source']}</b> ({q.get('cw_ref', 'Primary Works')})"
                )
                await query.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

        elif data == "btn_stats":
            stats = self.repo.get_stats()
            text = (
                f"📊 <b>Indexed Corpus:</b> {stats['document_count']} works, "
                f"{stats['chunk_count']:,} text passages."
            )
            await query.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

        elif data == "btn_toggle_mode":
            user_id = update.effective_user.id
            curr = self.repo.get_user_mode(user_id)
            new_mode = "scholar" if curr in ("first_person", "jung") else "first_person"
            self.repo.set_user_mode(user_id, new_mode)
            desc = f"First-Person {PERSONA_NAME}" if new_mode == "first_person" else "Scholarly Academic Guide"
            await query.message.reply_text(f"Voice mode toggled to: <b>{desc}</b>.", parse_mode=constants.ParseMode.HTML)

        elif data == "btn_view_sources":
            user_id = update.effective_user.id
            history = self.repo.get_history(user_id, limit=4)
            cits = []
            for h in history:
                if h.get("citations"):
                    cits.extend(h["citations"])
            cits = list(dict.fromkeys(cits))
            if cits:
                msg = "📚 <b>Primary Sources Cited:</b>\n\n" + "\n".join(f"• <i>{c}</i>" for c in cits)
            else:
                msg = "No recent citations recorded."
            await query.message.reply_text(msg, parse_mode=constants.ParseMode.HTML)

        elif data == "btn_opposites":
            await query.message.reply_text(
                "⚖️ <b>The Tension of Opposites:</b>\n\n"
                "Every conscious attitude has an unconscious opposite. "
                "Whenever an extreme one-sided position is maintained, an unconscious reaction sets in.\n\n"
                "What is the opposing viewpoint or feeling that your current attitude is pushing away?",
                parse_mode=constants.ParseMode.HTML
            )

        elif data == "btn_ask_help":
            await query.message.reply_text(
                "Simply type your philosophical question directly, or use <code>/ask &lt;question&gt;</code>.",
                parse_mode=constants.ParseMode.HTML
            )

        elif data == "btn_dream_help":
            await query.message.reply_text(
                "To analyze a dream, send <code>/dream &lt;describe your dream&gt;</code>.",
                parse_mode=constants.ParseMode.HTML
            )

        elif data == "btn_concept_help":
            await query.message.reply_text(
                "To look up any term, send <code>/concept &lt;term&gt;</code>.",
                parse_mode=constants.ParseMode.HTML
            )
