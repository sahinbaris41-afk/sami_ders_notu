from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import time


class NotesStorage:
    def __init__(self, base_dir: str):
        self.base_dir = pathlib.Path(base_dir).expanduser().resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "index.json"

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = (name or "GENEL").strip()
        cleaned = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü\-_ ]+", "", cleaned)
        cleaned = re.sub(r"\s+", "_", cleaned).strip("_")
        return cleaned[:80] if cleaned else "GENEL"

    def _load_index(self) -> list:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, items: list) -> None:
        self.index_path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save_note(self, note: dict) -> dict:
        ders = self._safe_name(note.get("ders_adi", "GENEL"))
        date_str = note.get("timestamp", "")[:10] or datetime.date.today().isoformat()
        folder = self.base_dir / ders / date_str
        folder.mkdir(parents=True, exist_ok=True)

        note_id = note.get("id") or hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        timestamp = note.get("timestamp", datetime.datetime.now().isoformat()).replace(":", "-")
        stem = f"{timestamp}_{note_id}"
        json_path = folder / f"{stem}.json"
        md_path = folder / f"{stem}.md"

        json_path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")

        markdown_lines = [
            f"# {note.get('ders_adi', 'GENEL')}",
            f"**Hoca:** {note.get('hoca', '')}",
            f"**Tarih:** {note.get('timestamp', '')}",
            "",
            "## Not İçeriği",
            note.get("content", "") or "",
            "",
            "---",
            "## Ham OCR (Referans)",
            note.get("raw_content", "") or "",
        ]
        md_path.write_text("\n".join(markdown_lines), encoding="utf-8")

        index = self._load_index()
        if not any(item.get("id") == note_id for item in index):
            index.append(
                {
                    "id": note_id,
                    "ders_adi": note.get("ders_adi", "GENEL"),
                    "hoca": note.get("hoca", ""),
                    "timestamp": note.get("timestamp", ""),
                    "word_count": note.get("word_count", 0),
                    "json_path": str(json_path),
                    "md_path": str(md_path),
                }
            )
            index.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
            self._save_index(index)

        note["saved_json_path"] = str(json_path)
        note["saved_md_path"] = str(md_path)
        note["saved_at"] = datetime.datetime.now().isoformat()
        return note

    def list_notes(self) -> list:
        return self._load_index()

    def load_note_by_json_path(self, json_path: str) -> dict:
        return json.loads(pathlib.Path(json_path).read_text(encoding="utf-8"))
