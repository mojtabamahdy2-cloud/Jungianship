import re
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

def infer_metadata_from_filename(filename: str, default_author: str = "Unknown") -> Dict[str, str]:
    """Extract Volume reference, Title, Year, and Author from a corpus filename.

    The filename convention used here was designed for the Jung corpus
    (e.g. 'Jung,_C_G_CW_07_Two_Essays...epub'), but the parser works for any
    consistently-named collection. The `default_author` parameter allows callers
    to pass in the persona name from config.
    """
    # Match CW numbers: e.g. CW_07, [CW 01], CW_09_1, CW 06
    cw_match = re.search(r'(?:\[?CW[_\s]+(\d+(?:[_\.]\d+)?)\]?)', filename, re.IGNORECASE)
    cw_volume = ""
    if cw_match:
        num = cw_match.group(1).replace("_", ".")
        cw_volume = f"CW {num}"
    
    # Year match: 19xx or 20xx
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', filename)
    year = year_match.group(1) if year_match else ""

    # Clean title heuristics
    title = filename.replace(".epub", "").replace(".pdf", "")
    title = re.sub(r'^[A-Za-z]+,\s*[A-Za-z\s\._]+-\s*', '', title)  # Remove "Author, X. Y. - " prefix
    title = re.sub(r'^[A-Za-z]+,?\s*_?[A-Z]_?[A-Z]_?', '', title, flags=re.IGNORECASE)  # Remove short author codes
    title = re.sub(r'\[?CW[_\s]+\d+(?:[_\.]\d+)?\]?', '', title, flags=re.IGNORECASE)
    title = re.sub(r'_\d{4}.*$', '', title)
    title = re.sub(r'\(\w+,\s*\d{4}\)', '', title)
    title = title.replace("_", " ").strip(" -_,.")
    
    if not title:
        title = filename

    # Known standalone works (Jung corpus defaults — extend for other personas)
    if "Red Book" in filename or "Liber Novus" in filename:
        cw_volume = "The Red Book"
        title = "The Red Book: Liber Novus"
    elif "Memories, Dreams, Reflections" in filename:
        cw_volume = "MDR"
        title = "Memories, Dreams, Reflections"
    elif "Man and His Symbols" in filename:
        cw_volume = "Man and His Symbols"
        title = "Man and His Symbols"
    elif "Answer to Job" in filename:
        cw_volume = "CW 11 / Answer to Job" if not cw_volume else cw_volume
        title = "Answer to Job"
    elif "Modern Man in Search of a Soul" in filename:
        cw_volume = "Modern Man in Search of a Soul"
        title = "Modern Man in Search of a Soul"
    elif "Synchronicity" in filename:
        cw_volume = "CW 08 / Synchronicity" if not cw_volume else cw_volume
        title = "Synchronicity: An Acausal Connecting Principle"

    return {
        "title": title,
        "cw_volume": cw_volume,
        "year": year,
        "author": default_author,
    }

class EpubParser:
    """Extracts structured text, chapters, and paragraph indices from EPUB files.

    Works with any EPUB corpus — not limited to Jung's works.
    To adapt for a different author, set PERSONA_NAME in your .env file.
    """

    def __init__(self, epub_path: Path, author: str = None):
        from src.config import PERSONA_NAME
        self.epub_path = Path(epub_path)
        self.filename = self.epub_path.name
        self._default_author = author or PERSONA_NAME
        self.meta = infer_metadata_from_filename(self.filename, default_author=self._default_author)

    def parse(self) -> List[Dict[str, Any]]:
        """Parse EPUB and return list of sections with paragraphs and headers."""
        sections = []
        if not self.epub_path.exists():
            return sections

        with zipfile.ZipFile(self.epub_path, 'r') as z:
            html_files = [
                f for f in z.namelist()
                if f.endswith(('.html', '.xhtml', '.htm'))
                and not f.endswith(('fn.html', 'bmfn.html', 'nav.xhtml', 'toc.xhtml'))
            ]

            current_chapter = self.meta["title"]

            for name in html_files:
                try:
                    raw = z.read(name).decode('utf-8', errors='ignore')
                except Exception:
                    continue

                soup = BeautifulSoup(raw, 'html.parser')
                
                # Check for chapter title in file
                heading = soup.find(['h1', 'h2', 'h3'])
                if heading:
                    header_text = heading.get_text().strip()
                    # Filter out generic book title headers
                    if header_text and len(header_text) > 3 and header_text.lower() != self.meta["title"].lower():
                        current_chapter = header_text

                # Extract paragraphs
                paragraphs = []
                for p in soup.find_all(['p', 'blockquote']):
                    text = p.get_text().strip()
                    # Skip empty or navigational garbage
                    if not text or len(text) < 15:
                        continue
                    if text.startswith(('Table of Contents', 'INDEX', 'Cover', 'Title Page')):
                        continue

                    # Detect Jungian paragraph numbers [123] or § 123
                    para_num = None
                    m = re.match(r'^(?:\[(\d+)\]|§\s*(\d+)|\((\d+)\))\s*(.*)', text)
                    if m:
                        para_num = m.group(1) or m.group(2) or m.group(3)
                        clean_body = m.group(4).strip()
                    else:
                        clean_body = text

                    paragraphs.append({
                        "para_num": int(para_num) if para_num and para_num.isdigit() else None,
                        "text": clean_body,
                        "raw": text
                    })

                if paragraphs:
                    sections.append({
                        "file": name,
                        "chapter": current_chapter,
                        "paragraphs": paragraphs
                    })

        return sections
