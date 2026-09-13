from typing import List, Dict, Any

class Chunker:
    """Chunks structured paragraphs into semantically cohesive passages."""

    def __init__(self, target_words: int = 350, overlap_words: int = 50):
        self.target_words = target_words
        self.overlap_words = overlap_words

    def chunk_sections(self, sections: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks = []

        for sec in sections:
            chapter = sec.get("chapter", meta.get("title", ""))
            paras = sec.get("paragraphs", [])
            if not paras:
                continue

            current_paras = []
            current_word_count = 0
            para_numbers = []

            for p in paras:
                words = p["text"].split()
                w_len = len(words)
                if p["para_num"] is not None:
                    para_numbers.append(p["para_num"])

                current_paras.append(p)
                current_word_count += w_len

                if current_word_count >= self.target_words:
                    # Construct chunk content
                    chunk_text = self._build_chunk_text(current_paras)
                    para_range_str = self._format_para_range(para_numbers)

                    chunks.append({
                        "chapter": chapter,
                        "section": sec.get("file", ""),
                        "para_range": para_range_str,
                        "content": chunk_text,
                        "token_count": current_word_count
                    })

                    # Carry over last paragraph for overlap context if possible
                    if len(current_paras) > 1 and len(current_paras[-1]["text"].split()) <= self.overlap_words * 2:
                        last_p = current_paras[-1]
                        current_paras = [last_p]
                        current_word_count = len(last_p["text"].split())
                        para_numbers = [last_p["para_num"]] if last_p["para_num"] is not None else []
                    else:
                        current_paras = []
                        current_word_count = 0
                        para_numbers = []

            # Remaining paragraphs
            if current_paras:
                chunk_text = self._build_chunk_text(current_paras)
                para_range_str = self._format_para_range(para_numbers)
                chunks.append({
                    "chapter": chapter,
                    "section": sec.get("file", ""),
                    "para_range": para_range_str,
                    "content": chunk_text,
                    "token_count": current_word_count
                })

        return chunks

    def _build_chunk_text(self, paras: List[Dict[str, Any]]) -> str:
        parts = []
        for p in paras:
            if p["para_num"] is not None:
                parts.append(f"[§{p['para_num']}] {p['text']}")
            else:
                parts.append(p["text"])
        return "\n\n".join(parts)

    def _format_para_range(self, para_numbers: List[int]) -> str:
        if not para_numbers:
            return ""
        para_numbers = sorted(list(set(para_numbers)))
        if len(para_numbers) == 1:
            return f"§{para_numbers[0]}"
        return f"§{para_numbers[0]}–§{para_numbers[-1]}"
