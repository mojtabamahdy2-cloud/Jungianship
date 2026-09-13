import unittest
from pathlib import Path
from src.config import CORPUS_DIR, DB_PATH
from src.db.database import init_db
from src.db.repository import Repository
from src.ingestion.epub_parser import EpubParser, infer_metadata_from_filename
from src.ingestion.chunker import Chunker
from src.engine.retriever import HybridRetriever
from src.bot.ui_helpers import markdown_to_telegram_html, split_message

class TestJungianship(unittest.TestCase):

    def setUp(self):
        init_db()
        self.repo = Repository()

    def test_infer_metadata(self):
        meta1 = infer_metadata_from_filename("Jung,_C_G_CW_07_Two_Essays_on_Analytical_Psychology_Princeton,_1972.epub")
        self.assertEqual(meta1["cw_volume"], "CW 07")

        meta2 = infer_metadata_from_filename("Jung, C. G. - Answer to Job (Princeton, 2011).epub")
        self.assertIn("Answer to Job", meta2["cw_volume"])

        meta3 = infer_metadata_from_filename("Jung,_C_G_CW_09_1_Archetypes_and_the_Collective_Unconscious_Princeton.epub")
        self.assertEqual(meta3["cw_volume"], "CW 09.1")

    def test_markdown_to_telegram_html(self):
        md = "### The Shadow\n\nThis is **bold** and *italic*. Also `code`.\n\n> quote"
        html_out = markdown_to_telegram_html(md)
        self.assertIn("<b>The Shadow</b>", html_out)
        self.assertIn("<b>bold</b>", html_out)
        self.assertIn("<i>italic</i>", html_out)
        self.assertIn("<code>code</code>", html_out)
        self.assertIn("<blockquote>quote</blockquote>", html_out)

    def test_split_message(self):
        short_text = "A short philosophical passage."
        self.assertEqual(len(split_message(short_text)), 1)

        long_text = "Paragraph one.\n\n" * 500
        parts = split_message(long_text, max_chars=1000)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p), 1050)

    def test_database_fts_search(self):
        # We indexed the core corpus earlier; let's verify FTS search works
        hits = self.repo.fts_search("shadow persona", limit=5)
        self.assertGreater(len(hits), 0)
        first = hits[0]
        self.assertIn("content", first)
        self.assertIn("cw_volume", first)

    def test_quotes_repository(self):
        q = self.repo.get_random_quote()
        self.assertIsNotNone(q)
        self.assertIn("quote", q)
        self.assertIn("source", q)

    def test_user_session_and_history(self):
        test_uid = 999888777
        self.repo.set_user_mode(test_uid, mode="scholar")
        self.assertEqual(self.repo.get_user_mode(test_uid), "scholar")

        self.repo.save_message(test_uid, "user", "What is individuation?")
        self.repo.save_message(test_uid, "assistant", "Individuation is the realization of the Self.", citations=["CW 07"])
        
        history = self.repo.get_history(test_uid, limit=2)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

        self.repo.clear_history(test_uid)
        self.assertEqual(len(self.repo.get_history(test_uid)), 0)

    def test_hybrid_retriever(self):
        retriever = HybridRetriever(self.repo)
        results = retriever.search("collective unconscious archetypes", top_k=3)
        self.assertGreater(len(results), 0)
        formatted = retriever.format_context_for_llm(results)
        self.assertIn("Source:", formatted)

if __name__ == "__main__":
    unittest.main()
