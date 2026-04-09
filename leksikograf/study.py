from __future__ import annotations

import io

import pdfplumber

from .text_utils import chunk_text, extract_keywords


def build_course_library(pdf_bytes: bytes) -> dict:
    pages_data: list[dict] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages[:10], start=1):
            pages_data.append({"page": page_number, "text": page.extract_text() or ""})

    chunks: list[dict] = []
    for page in pages_data:
        parts = chunk_text(page["text"], chunk_size=800)
        if not parts:
            continue
        for part in parts:
            chunks.append({"page": page["page"], "text": part})

    return {
        "chunks": chunks,
        "texts": [chunk["text"] for chunk in chunks],
        "pages": [chunk["page"] for chunk in chunks],
    }


def generate_practice_questions(chunks: list[dict], limit: int = 3) -> list[dict]:
    questions: list[dict] = []
    for chunk in chunks[:limit]:
        keywords = extract_keywords(chunk["text"], limit=4)
        if not keywords:
            continue
        answer = ", ".join(keywords[:2])
        question_lines = [
            f"Soru: Sayfa {chunk['page']} içeriğinde öne çıkan iki kavram nedir?",
            f"A) {answer}",
            f"B) {', '.join(reversed(keywords[:2]))}",
            f"C) {', '.join(keywords[2:4]) if len(keywords) > 3 else answer}",
            "D) Genel tekrar notları",
            "Cevap: A",
        ]
        questions.append(
            {
                "text": "\n".join(question_lines),
                "source_page": chunk["page"],
                "source_text": chunk["text"][:250],
            }
        )
    return questions


def summarize_professor(name: str, info: dict) -> str:
    expertise = ", ".join(info.get("expertise", [])[:3])
    yayinlar = ", ".join(info.get("yayinlar", [])[:2])
    return (
        f"**Alan:** {info.get('area', '-')}\n\n"
        f"**Öne çıkan uzmanlıklar:** {expertise or '-'}\n\n"
        f"**Çalışma başlıkları:** {yayinlar or '-'}\n\n"
        f"**Sınav yaklaşımı:** {info.get('sinav_ipucu', '-')}"
    )


def build_curriculum_report(course_name: str, topics: list[str], depth: int) -> str:
    lines = [
        f"# {course_name} Yerel Çalışma Raporu",
        "",
        f"Derinlik seviyesi: {depth}/5",
        "",
        "## Çalışma Planı",
    ]
    for index, topic in enumerate(topics, start=1):
        lines.extend(
            [
                f"### {index}. {topic}",
                "- Kavramı kısa tanımla ve kendi cümlenle yeniden yaz.",
                f"- Ders notlarında {topic} ile ilişkili örnekleri işaretle.",
                f"- {topic} için en az 3 soru-cevap kartı hazırla.",
                f"- Derinlik seviyesi {depth} olduğu için {depth + 1} örnek vaka çöz.",
                "",
            ]
        )
    lines.extend(
        [
            "## Tekrar Protokolü",
            "- İlk tekrar: aynı gün 20 dakika.",
            "- İkinci tekrar: 24 saat sonra kısa soru çözümü.",
            "- Üçüncü tekrar: 1 hafta sonra karışık konu denemesi.",
        ]
    )
    return "\n".join(lines)
