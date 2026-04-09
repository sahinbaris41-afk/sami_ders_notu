from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from .config import SystemConfig


class StudyProgressTracker:
    @staticmethod
    def _path() -> Path:
        return Path(SystemConfig.study_progress_path())

    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", value or "")
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9çğıöşü]+", "-", text.lower()).strip("-")

    @staticmethod
    def _stamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _parse_stamp(value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def _base() -> dict:
        return {"plans": {}}

    @staticmethod
    def _read() -> dict:
        path = StudyProgressTracker._path()
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return StudyProgressTracker._base()

    @staticmethod
    def _write(payload: dict) -> None:
        path = StudyProgressTracker._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def plan_key(course_name: str, strategy_name: str, selected_topics: list[str] | None = None) -> str:
        topics = selected_topics or []
        parts = [StudyProgressTracker._normalize(course_name), StudyProgressTracker._normalize(strategy_name)]
        if topics:
            parts.append(StudyProgressTracker._normalize("-".join(topics)))
        return "__".join([part for part in parts if part])

    @staticmethod
    def make_item_id(kind: str, *parts: str) -> str:
        normalized_parts = [StudyProgressTracker._normalize(kind)]
        normalized_parts.extend(StudyProgressTracker._normalize(part) for part in parts if part)
        return "::".join([part for part in normalized_parts if part])

    @staticmethod
    def get_plan_record(course_name: str, strategy_name: str, selected_topics: list[str] | None = None) -> dict:
        payload = StudyProgressTracker._read()
        return payload.get("plans", {}).get(StudyProgressTracker.plan_key(course_name, strategy_name, selected_topics), {"items": {}})

    @staticmethod
    def set_item_status(
        course_name: str,
        strategy_name: str,
        selected_topics: list[str] | None,
        item_id: str,
        label: str,
        completed: bool,
        meta: dict | None = None,
    ) -> None:
        payload = StudyProgressTracker._read()
        payload.setdefault("plans", {})
        key = StudyProgressTracker.plan_key(course_name, strategy_name, selected_topics)
        plan = payload["plans"].setdefault(
            key,
            {
                "course_name": course_name,
                "strategy_name": strategy_name,
                "selected_topics": selected_topics or [],
                "created_at": StudyProgressTracker._stamp(),
                "items": {},
            },
        )
        plan["items"][item_id] = {
            "label": label,
            "completed": completed,
            "meta": meta or {},
            "updated_at": StudyProgressTracker._stamp(),
        }
        StudyProgressTracker._write(payload)

    @staticmethod
    def summarize_progress(course_name: str, strategy_name: str, selected_topics: list[str] | None, expected_items: list[dict]) -> dict:
        record = StudyProgressTracker.get_plan_record(course_name, strategy_name, selected_topics)
        saved_items = record.get("items", {})
        total = len(expected_items)
        completed_items = [item for item in expected_items if saved_items.get(item["id"], {}).get("completed")]
        completed = len(completed_items)
        rate = (completed / total) if total else 0.0
        if rate >= 0.8:
            mode = "genislet"
            label = "Plan genişletilsin"
            minute_delta = 15
            task_delta = 1
        elif rate <= 0.4:
            mode = "daralt"
            label = "Plan daraltılsın"
            minute_delta = -15
            task_delta = -1
        else:
            mode = "koru"
            label = "Plan dengede kalsın"
            minute_delta = 0
            task_delta = 0
        return {
            "total": total,
            "completed": completed,
            "rate": rate,
            "mode": mode,
            "label": label,
            "minute_delta": minute_delta,
            "task_delta": task_delta,
            "completed_ids": [item["id"] for item in completed_items],
            "record": record,
        }

    @staticmethod
    def build_next_day_adjustment(
        course_name: str,
        strategy_name: str,
        selected_topics: list[str] | None,
        progress_summary: dict,
        reading_items: list[dict],
        exam_items: list[dict],
        base_minutes: int,
    ) -> dict:
        completed_ids = set(progress_summary.get("completed_ids", []))
        pending_readings = [item for item in reading_items if item.get("id") not in completed_ids]
        pending_exams = [item for item in exam_items if item.get("id") not in completed_ids]
        if progress_summary.get("mode") == "genislet":
            recommended_minutes = min(120, base_minutes + progress_summary.get("minute_delta", 0))
            reading_count = 3
            revision_count = 2
            title = "Genişletilmiş sonraki gün planı"
        elif progress_summary.get("mode") == "daralt":
            recommended_minutes = max(30, base_minutes + progress_summary.get("minute_delta", 0))
            reading_count = 1
            revision_count = 1
            title = "Daraltılmış sonraki gün planı"
        else:
            recommended_minutes = base_minutes
            reading_count = 2
            revision_count = 1
            title = "Dengeli sonraki gün planı"

        chosen_readings = pending_readings[:reading_count] if pending_readings else reading_items[:reading_count]
        chosen_revisions = pending_exams[:revision_count] if pending_exams else exam_items[:revision_count]
        lines = [
            f"# {course_name} - {strategy_name} için Sonraki Gün Uyarlaması",
            "",
            f"Uyarlama modu: {progress_summary.get('label', '-')}",
            f"Tamamlanma oranı: %{progress_summary.get('rate', 0.0) * 100:.0f}",
            f"Önerilen süre: {recommended_minutes} dakika",
            "",
            "## Ana Yayınlar",
        ]
        next_day_items = []
        for item in chosen_readings:
            next_day_items.append({"type": "reading", "title": item.get("title", "-"), "staff_name": item.get("staff_name", "-"), "url": item.get("url", "")})
            lines.extend([f"- {item.get('title', '-')}", f"  Akademisyen: {item.get('staff_name', '-')}", f"  Bağlantı: {item.get('url', '-') or '-'}"])
        lines.extend(["", "## Pekiştirme Başlıkları"])
        for item in chosen_revisions:
            next_day_items.append({"type": "revision", "title": item.get("title", "-"), "staff_name": item.get("staff_name", "-"), "url": item.get("url", "")})
            lines.extend([f"- {item.get('title', '-')}", f"  Akademisyen: {item.get('staff_name', '-')}", f"  Bağlantı: {item.get('url', '-') or '-'}"])
        return {"title": title, "recommended_minutes": recommended_minutes, "items": next_day_items, "text": "\n".join(lines)}

    @staticmethod
    def build_recovery_plan(
        course_name: str,
        strategy_name: str,
        selected_topics: list[str] | None,
        progress_summary: dict,
        reading_items: list[dict],
        exam_items: list[dict],
        day_items: list[dict],
    ) -> dict:
        completed_ids = set(progress_summary.get("completed_ids", []))
        pending_readings = [item for item in reading_items if item.get("id") not in completed_ids]
        pending_exams = [item for item in exam_items if item.get("id") not in completed_ids]
        pending_days = [item for item in day_items if item.get("id") not in completed_ids]
        lines = [
            f"# {course_name} - {strategy_name} için Telafi Planı",
            "",
            f"Tamamlanma oranı: %{progress_summary.get('rate', 0.0) * 100:.0f}",
            "",
            "## Telafi Edilecek Başlıklar",
        ]
        recovery_items = []
        for item in pending_readings[:3]:
            recovery_items.append({"type": "reading", "title": item.get("title", "-"), "staff_name": item.get("staff_name", "-"), "action": "Önce hızlı özet, sonra ana metin"})
        for item in pending_exams[:2]:
            recovery_items.append({"type": "exam", "title": item.get("title", "-"), "staff_name": item.get("staff_name", "-"), "action": "Çıkabilecek kavramları maddeler halinde çıkar"})
        for item in pending_days[:1]:
            recovery_items.append({"type": "day", "title": item.get("reading_title", "-"), "staff_name": item.get("reading_staff", "-"), "action": "Kaçırılan günü tek oturumda toparla"})
        for index, item in enumerate(recovery_items, start=1):
            lines.extend([f"{index}. {item.get('title', '-')}", f"   Akademisyen: {item.get('staff_name', '-')}", f"   Telafi aksiyonu: {item.get('action', '-')}", ""])
        if not recovery_items:
            lines.append("Aktif telafi gerektiren başlık görünmüyor.")
        return {"title": "Otomatik Telafi Planı", "items": recovery_items, "text": "\n".join(lines)}

    @staticmethod
    def build_weekly_success_report(
        course_name: str,
        strategy_name: str,
        selected_topics: list[str] | None,
        expected_items: list[dict],
    ) -> dict:
        record = StudyProgressTracker.get_plan_record(course_name, strategy_name, selected_topics)
        saved_items = record.get("items", {})
        cutoff = datetime.now() - timedelta(days=7)
        weekly_completed = []
        by_type: dict[str, int] = {}
        for item_id, item in saved_items.items():
            if not item.get("completed"):
                continue
            stamp = StudyProgressTracker._parse_stamp(item.get("updated_at", ""))
            if not stamp or stamp < cutoff:
                continue
            weekly_completed.append({"id": item_id, **item})
            item_type = item.get("meta", {}).get("type", "genel")
            by_type[item_type] = by_type.get(item_type, 0) + 1
        total_expected = len(expected_items)
        weekly_count = len(weekly_completed)
        weekly_rate = (weekly_count / total_expected) if total_expected else 0.0
        lines = [
            f"# {course_name} - {strategy_name} Haftalık Başarı Raporu",
            "",
            f"Son 7 günde tamamlanan görev: {weekly_count}",
            f"Toplam görev havuzu: {total_expected}",
            f"Haftalık başarı oranı: %{weekly_rate * 100:.0f}",
            "",
            "## Tür Bazlı Dağılım",
        ]
        for item_type, count in by_type.items():
            lines.append(f"- {item_type}: {count}")
        lines.extend(["", "## Tamamlanan Son Görevler"])
        for item in weekly_completed[:10]:
            lines.append(f"- {item.get('label', '-')} | {item.get('updated_at', '-')}")
        if not weekly_completed:
            lines.append("Bu hafta tamamlanan görev kaydı yok.")
        return {
            "title": "Haftalık Başarı Raporu",
            "weekly_completed": weekly_count,
            "weekly_rate": weekly_rate,
            "by_type": by_type,
            "items": weekly_completed,
            "text": "\n".join(lines),
        }
