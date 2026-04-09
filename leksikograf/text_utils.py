from __future__ import annotations

from typing import Iterable

from PyPDF2 import PdfReader


def pdf_to_text(pdf_path: str, max_pages: int = 10) -> str:
    reader = PdfReader(pdf_path)
    text_parts: list[str] = []
    for index, page in enumerate(reader.pages):
        if index >= max_pages:
            break
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def chunk_text(text: str, chunk_size: int = 1200) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    words: dict[str, int] = {}
    for raw_word in text.split():
        word = raw_word.strip(".,;:!?()[]{}\"'").lower()
        if len(word) < 5 or word.isdigit():
            continue
        words[word] = words.get(word, 0) + 1
    ranked = sorted(words.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def joined_lines(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line)
