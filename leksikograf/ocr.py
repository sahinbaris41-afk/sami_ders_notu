from __future__ import annotations

import io
import os
import re
import time
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image


@dataclass
class OCRResult:
    raw_ocr: str = ""
    corrected_text: str = ""
    processing_time: float = 0.0
    confidence: float = 0.0
    word_count: int = 0
    quality_score: float = 0.0
    warnings: list[str] = field(default_factory=list)


class AdvancedOCREngine:
    """Yerel çalışan OCR motoru."""

    def __init__(self) -> None:
        self._setup_tesseract()
        self.academic_terms = {
            "pasplik": "pasiflik",
            "teyve": "kişiye",
            "trafik kağıt": "trafik kazası",
            "konşimento": "konşimento",
            "akreditif": "akreditif",
            "murus": "mirasbırakan",
            "memoritik": "mikroiktisat",
            "sigursa": "sigorta",
            "vaka antifizi": "vaka analizi",
            "lojistik yazınının": "lojistik yönetiminin",
        }

    def _setup_tesseract(self) -> None:
        if os.name != "nt":
            return
        candidates = [
            os.environ.get("TESSERACT_CMD"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return

    def preprocess_image(self, image_bytes: bytes) -> Image.Image:
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

        height, width = img.shape[:2]
        x1 = int(width * 0.08)
        x2 = int(width * 0.98)
        y1 = int(height * 0.03)
        y2 = int(height * 0.98)
        img = img[y1:y2, x1:x2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        gray = cv2.bilateralFilter(gray, 7, 50, 50)
        blur = cv2.GaussianBlur(gray, (0, 0), 1.2)
        sharp = cv2.addWeighted(gray, 1.8, blur, -0.8, 0)

        threshold = cv2.adaptiveThreshold(
            sharp,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            10,
        )
        return Image.fromarray(threshold)

    def _quality_score(self, text: str) -> int:
        cleaned = (text or "").strip()
        if not cleaned:
            return 0
        letters = sum(ch.isalpha() for ch in cleaned)
        bad = len(re.findall(r"[�\?\|\{\}\[\]\\/_=<>]", cleaned))
        length_penalty = 0 if len(cleaned) >= 30 else (30 - len(cleaned))
        return max(0, letters - 2 * bad - length_penalty)

    def extract_text(self, image: Image.Image) -> tuple[str, str]:
        configs = [
            r"--oem 1 --psm 6 -l tur --dpi 300",
            r"--oem 1 --psm 11 -l tur --dpi 300",
            r"--oem 1 --psm 4 -l tur --dpi 300",
            r"--oem 1 --psm 6 -l tur+eng --dpi 300",
        ]

        best_text = ""
        best_cfg = ""
        best_score = -1

        for config in configs:
            try:
                text = pytesseract.image_to_string(image, config=config)
            except Exception:
                continue
            text = re.sub(r"\s+", " ", text).strip()
            score = self._quality_score(text)
            if score > best_score:
                best_score = score
                best_text = text
                best_cfg = config
        return best_text, best_cfg

    def correct_terms(self, text: str, course_name: str = "") -> str:
        fixed = text
        for wrong, correct in self.academic_terms.items():
            fixed = re.sub(rf"\b{re.escape(wrong)}\b", correct, fixed, flags=re.IGNORECASE)

        replacements = [
            (r"\b(egitim|eğitim|egıtım)\b", "eğitim"),
            (r"\b(ogrenci|ögrenci)\b", "öğrenci"),
            (r"\b(ogretim|öğretim|ogretım)\b", "öğretim"),
            (r"\b(yonetim|yönetim|yonetım)\b", "yönetim"),
            (r"\b(isletme|işletme|ısletme)\b", "işletme"),
        ]
        for pattern, replacement in replacements:
            fixed = re.sub(pattern, replacement, fixed, flags=re.IGNORECASE)

        if "hukuk" in course_name.lower():
            fixed = re.sub(r"\b(vek[aâ]let|vekalet)\b", "vekalet", fixed, flags=re.IGNORECASE)
            fixed = re.sub(r"\b(vel[aâ]yet|velayet)\b", "velayet", fixed, flags=re.IGNORECASE)
        return fixed

    def process_image(self, image_bytes: bytes, course_context: str = "") -> OCRResult:
        started = time.time()
        result = OCRResult()
        try:
            image = self.preprocess_image(image_bytes)
            raw_text, selected_cfg = self.extract_text(image)
            result.raw_ocr = raw_text
            if not raw_text or len(raw_text.strip()) < 10:
                result.corrected_text = "Yeterli metin bulunamadı. Lütfen daha net bir görsel yükleyin."
                result.warnings.append("low_text")
                return result

            result.corrected_text = self.correct_terms(raw_text, course_context)
            result.processing_time = time.time() - started
            result.word_count = len(result.corrected_text.split())

            unknown_count = result.corrected_text.count("[???]")
            if result.word_count > 0:
                confidence = 100 - (unknown_count / result.word_count * 100)
                result.confidence = min(95, max(50, confidence))

            quality_parts = [
                min(100, result.word_count),
                result.confidence,
                max(0, 100 - (result.processing_time * 10)),
            ]
            result.quality_score = sum(quality_parts) / len(quality_parts)
            if selected_cfg:
                result.warnings.append(f"tesseract:{selected_cfg}")
            return result
        except Exception as exc:
            result.corrected_text = f"İşleme hatası: {exc}"
            result.warnings.append("exception")
            return result


class ProfessionalDigitalizer:
    def __init__(self, engine: AdvancedOCREngine) -> None:
        self.engine = engine

    def process_notes_batch(self, files: list, ders_adi: str, hoca: str) -> dict:
        results = {
            "total_files": len(files),
            "successful": 0,
            "failed": 0,
            "total_words": 0,
            "total_time": 0.0,
            "notes": [],
            "avg_quality_score": 0.0,
            "errors": [],
        }
        started = time.time()

        for page_index, file in enumerate(files, start=1):
            try:
                ocr_result = self.engine.process_image(file.getvalue(), ders_adi)
                if not ocr_result.corrected_text or "İşleme hatası:" in ocr_result.corrected_text:
                    results["failed"] += 1
                    results["errors"].append(f"{file.name}: OCR başarısız")
                    continue

                note_data = {
                    "id": f"{int(time.time() * 1000)}_{page_index}",
                    "ders_adi": ders_adi,
                    "hoca": hoca,
                    "filename": file.name,
                    "content": ocr_result.corrected_text,
                    "raw_content": ocr_result.raw_ocr,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "processing_time": ocr_result.processing_time,
                    "confidence": ocr_result.confidence,
                    "word_count": ocr_result.word_count,
                    "quality_score": ocr_result.quality_score,
                    "page": page_index,
                    "warnings": ocr_result.warnings,
                }
                results["notes"].append(note_data)
                results["successful"] += 1
                results["total_words"] += note_data["word_count"]
            except Exception as exc:
                results["failed"] += 1
                results["errors"].append(f"{file.name}: {exc}")

        results["total_time"] = time.time() - started
        if results["notes"]:
            results["avg_quality_score"] = sum(
                note["quality_score"] for note in results["notes"]
            ) / len(results["notes"])
        return results
