
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import pdfplumber

from .config import SystemConfig

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

DEPARTMENT_HOME_URL = "https://itbf.btu.edu.tr/tr/utl"
ACADEMIC_STAFF_URL = "https://itbf.btu.edu.tr/tr/utl/sayfa/akademikkadro"
DEPARTMENT_PAGES = {
    "vizyon_misyon": "https://itbf.btu.edu.tr/tr/utl/sayfa/detay/7033/vizyon-ve-misyon",
    "genel_bilgiler": "https://itbf.btu.edu.tr/tr/utl/sayfa/detay/7195/bolum-hakkinda-genel-bilgiler",
    "tarihce": "https://itbf.btu.edu.tr/tr/utl/sayfa/detay/2668/tarihce",
    "ders_plani": "https://itbf.btu.edu.tr/tr/utl/sayfa/detay/2654/ders-plani-guncellendi",
    "iletisim": "https://itbf.btu.edu.tr/tr/utl/sayfa/iletisim",
}
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}
CACHE_PATH = Path(SystemConfig.academic_cache_path())

STAFF_ROWS = [
    ("Prof. Dr. Hilal YILDIRIR KESER", "Profesör Doktor", "Öğretim Üyesi", "Uluslararası Ticaret", "hilal.yildirir@btu.edu.tr", "+90 (224) 300 34 47", "Yıldırım Bayezid Yerleşkesi B Blok / 451", "Uluslararası Ticaret|İthalat-İhracat Yönetimi|Uluslararası Lojistik|E-İhracat", "Güncel ticaret uygulamalarını kavramlarla ilişkilendirmek avantaj sağlar."),
    ("Prof. Dr. Orhan ÇAĞLAYAN", "Profesör Doktor", "Öğretim Üyesi", "Lojistik", "orhan.caglayan@btu.edu.tr", "+90 (224) 808 10 38", "Yıldırım Bayezid Yerleşkesi B Blok / 368", "Lojistik|Girişimcilik|Toplam Kalite Yönetimi|Üretim Yönetimi ve Pazarlama", "Süreç yönetimi ve uygulama örnekleri üzerinden düşünmek yararlı olur."),
    ("Prof. Dr. Serkan ÖZDEMİR", "Profesör Doktor", "Bölüm Başkanı", "Muhasebe", "serkan.ozdemir@btu.edu.tr", "+90 (224) 300 37 05", "Yıldırım Bayezid Yerleşkesi B Blok / 366", "Muhasebe|Finansal Muhasebe|Maliyet Muhasebesi|Yönetim Muhasebesi", "Finansal tabloların mantığını kavramak ezberden daha değerlidir."),
    ("Doç. Dr. Ayberk ŞEKER", "Doçent Doktor", "Öğretim Üyesi", "Uluslararası Ticaret", "ayberk.seker@btu.edu.tr", "+90 (224) 300 38 73", "Yıldırım Bayezid Yerleşkesi B Blok / 363", "Uluslararası Ticaret|İthalat ve İhracat Yönetimi|Ekonomik Entegrasyon|Uluslararası Ticari Örgütler|Gümrük ve Dış Ticaret Mevzuatı|E-Ticaret|Uluslararası Ticarette Risk Yönetimi", "Mevzuat ve dış ticaret süreçlerini uygulama basamaklarıyla birlikte çalışmak gerekir."),
    ("Doç. Dr. Cevat BİLGİN", "Doçent Doktor", "Öğretim Üyesi", "Makro İktisat", "cevat.bilgin@btu.edu.tr", "+90 (224) 300 37 93", "Yıldırım Bayezid Yerleşkesi B Blok / 369", "Makro İktisat|Büyüme|Gelişme Ekonomisi|Uluslararası İktisat", "Grafik yorumlama ve teori-uygulama bağlantısı bu alanda belirleyici olur."),
    ("Doç. Dr. Hüseyin ÇETİN", "Doçent Doktor", "Bölüm Başkan Yardımcısı", "Uluslararası Finans", "huseyin.cetin@btu.edu.tr", "+90 (224) 300 35 68", "Yıldırım Bayezid Yerleşkesi B Blok / 263", "İşletme Finansı|Uluslararası Finans|Uluslararası Ticaret|Uluslararası İktisat|Lojistik Maliyet Analizi|Teknoloji Ekonomisi|Bankacılık|Dış Ticaret Finansmanı", "Finansal kavramları tablo ve oran mantığıyla eşleştirerek çalışmak yararlıdır."),
    ("Doç. Dr. Salih KALAYCI", "Doçent Doktor", "Öğretim Üyesi", "Çevre Ekonomisi", "salih.kalayci@btu.edu.tr", "+90 (224) 808 11 60", "Yıldırım Bayezid Yerleşkesi B Blok / 266", "Çevre Ekonomisi|Uluslararası Ticaret|Uluslararası İktisat|Katılım Bankacılığı", "Kavramsal çerçeveyi uluslararası ekonomi örnekleriyle eşleştirmek puan getirir."),
    ("Doç. Dr. Tuğçe DANACI ÜNAL", "Doçent Doktor", "Öğretim Üyesi", "Uluslararası Lojistik", "tugce.unal@btu.edu.tr", "+90 (224) 300 35 97", "Yıldırım Bayezid Yerleşkesi B Blok / 357", "Uluslararası Lojistik|Uluslararası Ticaret|İthalat-İhracat Yönetimi|Uluslararası Pazarlama", "Lojistik akışları ile ticari kararların nasıl bağlandığını net kurmak gerekir."),
    ("Dr. Öğr. Üyesi Yunus Emre SÜRMEN", "Doktor Öğretim Üyesi", "Bölüm Başkan Yardımcısı", "Küresel Ticaret ve Rekabet", "yunusemre.surmen@btu.edu.tr", "+90 (224) 300 36 23", "Yıldırım Bayezid Yerleşkesi B Blok / 159", "Küresel Ticaret ve Rekabet|Uluslararası Ekonomi Politik|Yenilikçi Teknolojiler|Havacılık", "Küresel eğilimleri kavramsal çerçeveye bağlamak önemlidir."),
    ("Arş. Gör. (Dr.) Ayşenur EFE PARLAK", "Araştırma Görevlisi (Dr.)", "Araştırma Görevlisi", "Uluslararası Pazarlama", "aysenur.efe@btu.edu.tr", "+90 (224) 300 37 12", "Yıldırım Bayezid Yerleşkesi B Blok / 166", "Uluslararası Pazarlama|Elektronik Ticaret|Tüketici Davranışı|Kültürlerarası Çalışmalar", "Pazarlama kavramlarını güncel dijital örneklerle düşünmek faydalıdır."),
    ("Arş. Gör. (Dr.) Kemal SÜR", "Araştırma Görevlisi (Dr.)", "Araştırma Görevlisi", "Uluslararası Ticaret", "kemal.sur@btu.edu.tr", "+90 (224) 808 12 09", "Yıldırım Bayezid Yerleşkesi B Blok / 153", "Uluslararası Ticaret|Gümrük Mevzuatı|Fikri ve Sınai Mülkiyet Hakları", "Mevzuat kavramlarını örnek senaryolarla tekrar etmek avantaj sağlar."),
    ("Arş. Gör. (Dr.) Nihal ALTUN", "Araştırma Görevlisi (Dr.)", "Araştırma Görevlisi", "Uluslararası Ticaret", "nihal.altun@btu.edu.tr", "+90 (224) 300 37 27", "Yıldırım Bayezid Yerleşkesi B Blok / 161", "Uluslararası Ticaret|Ekonomik Yığılmalar|İhracat Yoğunlaşması|Sürdürülebilirlik", "Dış ticaret göstergelerini neden-sonuç ilişkisiyle yorumlamak gerekir."),
    ("Arş. Gör. Furkan SAĞLAM", "Araştırma Görevlisi", "Araştırma Görevlisi", "Uluslararası Lojistik", "furkan.saglam@btu.edu.tr", "+90 (224) 300 39 39", "Yıldırım Bayezid Yerleşkesi B Blok / 153", "Uluslararası Lojistik|İhracat ve İthalat Analizleri|Yeşil Lojistik|Dijital Dönüşüm", "Lojistikte dönüşüm konularını güncel sektör örnekleriyle ilişkilendirmek yararlıdır."),
]
STATIC_DEPARTMENT = {
    "home_url": DEPARTMENT_HOME_URL,
    "staff_url": ACADEMIC_STAFF_URL,
    "title": "Bursa Teknik Üniversitesi Uluslararası Ticaret ve Lojistik Bölümü",
    "stats": {"Öğrenci": "542", "Akademik Personel": "13", "Program": "1", "İç Kaynaklı Projeler": "1", "Mezun": "279"},
    "announcements": ["06.03.2026 Gümrükte Kariyer ve Dijitalleşme, Açılış Dersinde Ele Alındı", "14.02.2026 2025-2026 Eğitim-Öğretim Yılı Bahar Dönemi Açılış Dersi", "13.02.2026 Azami Öğrenim Süresi Sonunda Mezun Olamayan Öğrenciler (1.Ek Sınavlar) Hakkında", "02.02.2026 2025-2026 Eğitim Öğretim Yılı Bahar Dönemi Ders Programı"],
    "news": ["24.11.2025 Lisansüstü'nde Mezuniyet Gururu", "10.10.2025 Kariyer Yönetiminde Dijitalleşmenin Yeri ve Önemi", "25.09.2025 BTÜ'den 8 Akademisyen Dünyanın En İyileri Arasında", "24.07.2025 BTÜ Tercih Günleri Başlıyor"],
    "events": ["18 Nisan Ara Sınavlar", "19 Nisan Ara Sınavlar", "20 Nisan Ara Sınavlar", "21 Nisan Ara Sınavlar", "22 Nisan Ara Sınavlar", "23 Nisan Ulusal Egemenlik ve Çocuk Bayramı"],
    "contact": {"address": "Bursa Teknik Üniversitesi Yıldırım Yerleşkesi İnsan ve Toplum Bilimleri Fakültesi Uluslararası Ticaret ve Lojistik Bölümü 16330 Yıldırım/BURSA", "phone": "300 38 74", "email": "utl@btu.edu.tr", "kep": "bursateknikuniversitesi@hs01.kep.tr"},
    "vision": "Uluslararası ticaret ve lojistik alanlarında çağın gereksinimlerine uyumlu, analitik düşünebilen ve sektörle güçlü bağ kurabilen mezunlar yetiştirmeyi hedefleyen yenilikçi bölüm vizyonu.",
    "mission": "Araştırma, uygulama ve sektör iş birlikleriyle uluslararası ticaret ve lojistik alanında nitelikli insan kaynağı yetiştirmek; öğrencileri etik, analitik ve küresel bakış açısıyla geliştirmek.",
    "general_info": "Bölüm; dış ticaret, lojistik, finans, muhasebe, ekonomi ve pazarlama başlıklarını aynı yapıda birleştirerek öğrencileri çok disiplinli iş yaşamına hazırlar.",
    "history": "Uluslararası Ticaret ve Lojistik Bölümü, küresel ticaret ile lojistik yönetimini bütünleşik biçimde ele alan program yaklaşımıyla gelişimini sürdürmektedir.",
    "performance_report_url": "https://depo.btu.edu.tr/dosyalar/itbf/Dokumanlar/UTL%20Akademik%20Performans%20Raporu.pdf",
    "updated_note": "Canlı içerik okunamazsa resmi BTÜ sayfalarından derlenen yedek veri gösterilir.",
}
METRIC_LABELS = {"Yayın": "Yayın", "Atıf": "Atıf", "Atif": "Atıf", "H-index": "H-index", "H İndex": "H-index", "I10-İndex": "I10-İndex", "I10-Index": "I10-İndex"}
CATEGORY_LABELS = {"makaleler": "Makaleler", "articles": "Makaleler", "bildiriler": "Bildiriler", "proceedings": "Bildiriler", "kitaplar": "Kitaplar", "books": "Kitaplar", "projeler": "Projeler", "projects": "Projeler", "yonetilen tezler": "Yönetilen Tezler", "yönetilen tezler": "Yönetilen Tezler", "theses managed": "Yönetilen Tezler", "dersler": "Dersler", "lessons": "Dersler"}
NOISE = {"Academic", "Akademik", "Articles", "Makaleler", "Projects", "Projeler", "Proceedings", "Bildiriler", "Books", "Kitaplar", "Theses Managed", "Yönetilen Tezler", "Lessons", "Dersler", "User image", "Image: User image", "SAYFA BAŞI"}
TITLE_RE = re.compile(r"^(Prof\. Dr\.|Doç\. Dr\.|Dr\. Öğr\. Üyesi|Arş\. Gör\. \(Dr\.\)|Arş\. Gör\.|Öğr\. Gör\.|Öğrt\. Gör\.)")

def _slug(email: str) -> str:
    return (email or "").split("@")[0].strip().lower()

def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _row_to_dict(row: tuple) -> dict:
    name, title, role, area, email, phone, room, expertise, tip = row
    slug = _slug(email)
    return {
        "title": title,
        "role": role,
        "area": area,
        "email": email,
        "phone": phone,
        "room": room,
        "expertise": [item.strip() for item in expertise.split("|") if item.strip()],
        "sayfam_url": f"https://sayfam.btu.edu.tr/{slug}" if slug else "",
        "academic_url": f"https://sayfam.btu.edu.tr/{slug}/akademik" if slug else "",
        "sinav_ipucu": tip,
        "yayinlar": [],
    }

STATIC_STAFF = {row[0]: _row_to_dict(row) for row in STAFF_ROWS}

class AcademicDatabase:
    @staticmethod
    def _normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", value or "")
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", text).strip().lower()

    @staticmethod
    def _clean_lines(text: str) -> list[str]:
        return [re.sub(r"\s+", " ", raw).strip() for raw in (text or "").splitlines() if re.sub(r"\s+", " ", raw).strip()]

    @staticmethod
    def _cache_base() -> dict:
        return {"staff": {}, "department_snapshot": {}, "department_pages": {}, "staff_detail": {}, "publication_index": {}}

    @staticmethod
    def _read_cache() -> dict:
        try:
            if CACHE_PATH.exists():
                return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return AcademicDatabase._cache_base()

    @staticmethod
    def _write_cache(payload: dict) -> None:
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _cache_get(section: str, key: str = "") -> dict:
        cache = AcademicDatabase._read_cache()
        bucket = cache.get(section, {})
        return bucket.get(key, {}) if key else bucket

    @staticmethod
    def _cache_put(section: str, data: dict, key: str = "") -> None:
        cache = AcademicDatabase._read_cache()
        cache.setdefault(section, {})
        payload = {"data": data, "last_sync": _stamp()}
        if key:
            cache[section][key] = payload
        else:
            cache[section] = payload
        AcademicDatabase._write_cache(cache)

    @staticmethod
    def clear_runtime_cache() -> None:
        AcademicDatabase.get_staff.cache_clear()
        AcademicDatabase.get_department_snapshot.cache_clear()
        AcademicDatabase.get_department_pages.cache_clear()
        AcademicDatabase.get_staff_detail.cache_clear()
        AcademicDatabase.get_publication_index.cache_clear()

    @staticmethod
    def _fetch_html(url: str) -> str:
        if not requests or not url:
            return ""
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except Exception:
            return ""

    @staticmethod
    def _make_soup(html: str):
        if not html or not BeautifulSoup:
            return None
        return BeautifulSoup(html, "html.parser")

    @staticmethod
    def _annotate(data: dict, source: str, last_sync: str) -> dict:
        payload = dict(data)
        payload["data_source"] = source
        payload["last_sync"] = last_sync
        return payload

    @staticmethod
    def _merge_record(name: str, parsed: dict) -> dict:
        base = dict(STATIC_STAFF.get(name, {}))
        merged = {**base, **parsed}
        expertise = merged.get("expertise") or []
        if isinstance(expertise, str):
            expertise = [expertise]
        merged["expertise"] = [item.strip() for item in expertise if item and item.strip()]
        merged.setdefault("area", merged["expertise"][0] if merged["expertise"] else base.get("area", "Genel"))
        merged.setdefault("role", base.get("role", "Öğretim Üyesi"))
        merged.setdefault("sinav_ipucu", base.get("sinav_ipucu", "Ders kavramlarını güncel örneklerle ilişkilendirmek yararlıdır."))
        if not merged.get("sayfam_url") and merged.get("email"):
            slug = _slug(merged["email"])
            merged["sayfam_url"] = f"https://sayfam.btu.edu.tr/{slug}"
            merged["academic_url"] = f"https://sayfam.btu.edu.tr/{slug}/akademik"
        return merged

    @staticmethod
    def _parse_staff_page(html: str) -> dict:
        soup = AcademicDatabase._make_soup(html)
        if not soup:
            return {}
        link_map = {}
        for anchor in soup.find_all("a", href=True):
            text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            href = urljoin(ACADEMIC_STAFF_URL, anchor["href"])
            if text and "sayfam.btu.edu.tr" in href:
                link_map[text] = href
        lines = AcademicDatabase._clean_lines(soup.get_text("\n"))
        staff, current_name, current_block, active = {}, "", [], False

        def flush() -> None:
            nonlocal current_name, current_block
            if not current_name:
                return
            email = next((line for line in current_block if "@" in line and "btu.edu.tr" in line), "")
            room = next((line for line in current_block if "Yerleşkesi" in line or "Blok" in line), "")
            phone = next((line for line in current_block if re.fullmatch(r"[+\d\s()/-]+", line) and len(re.sub(r"\D", "", line)) >= 7), "")
            role = next((line.strip("()") for line in current_block if line.startswith("(") and line.endswith(")")), "Öğretim Üyesi")
            expertise = []
            for line in current_block:
                if line in {current_name, email, room, phone, "* * *", "Uluslararası Ticaret ve Lojistik Bölümü"} or TITLE_RE.match(line):
                    continue
                if line.startswith("(") and line.endswith(")"):
                    continue
                expertise.extend([part.strip() for part in line.split(",") if part.strip()])
            sayfam_url = link_map.get(current_name, "")
            staff[current_name] = AcademicDatabase._merge_record(current_name, {"email": email, "room": room, "phone": f"+90 (224) {phone}" if phone and not phone.startswith("+") else phone, "role": role, "expertise": expertise, "sayfam_url": sayfam_url, "academic_url": f"{sayfam_url.rstrip('/')}/akademik" if sayfam_url else ""})
            current_name, current_block = "", []

        for line in lines:
            if line == "Akademik Personel":
                active = True
                continue
            if not active:
                continue
            if line == "İletişim Bilgileri":
                flush()
                break
            if TITLE_RE.match(line):
                flush()
                current_name, current_block = line, [line]
                continue
            if current_name:
                current_block.append(line)
        flush()
        return staff

    @staticmethod
    def _section_items(lines: list[str], heading: str, stops: list[str], limit: int = 6) -> list[str]:
        items, capture = [], False
        for line in lines:
            if AcademicDatabase._normalize(line) == AcademicDatabase._normalize(heading):
                capture = True
                continue
            if not capture:
                continue
            if any(AcademicDatabase._normalize(line) == AcademicDatabase._normalize(stop) for stop in stops):
                break
            if line in {"TÜMÜNÜ GÖSTER", "TÜM HABERLER", "Etkinlik", "Akademik Takvim"}:
                continue
            if re.search(r"\d{2}\.\d{2}\.\d{4}|\d{1,2}\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+", line):
                items.append(line)
            elif items and len(line.split()) > 2:
                items[-1] = f"{items[-1]} {line}"
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def _parse_stats(lines: list[str]) -> dict:
        stats = {}
        for line in lines:
            match = re.match(r"^(\d+)\s+(.+)$", line)
            if match and match.group(2) in {"Öğrenci", "Akademik Personel", "Program", "İç Kaynaklı Projeler", "Mezun"}:
                stats[match.group(2)] = match.group(1)
        return stats

    @staticmethod
    def _parse_contact(lines: list[str]) -> dict:
        contact, capture = dict(STATIC_DEPARTMENT["contact"]), False
        for line in lines:
            if line == "İletişim Bilgileri":
                capture = True
                continue
            if not capture:
                continue
            if "Yıldırım/BURSA" in line:
                contact["address"] = line
            elif "@" in line and "kep" in line.lower():
                contact["kep"] = line.replace("* ", "").strip()
            elif "@" in line:
                contact["email"] = line.replace("* ", "").strip()
            elif re.fullmatch(r"[+\d\s()/-]+", line):
                contact["phone"] = line.strip()
        return contact

    @staticmethod
    def _extract_page_text(url: str, fallback: str) -> str:
        soup = AcademicDatabase._make_soup(AcademicDatabase._fetch_html(url))
        if not soup:
            return fallback
        lines = []
        for line in AcademicDatabase._clean_lines(soup.get_text("\n")):
            if line in NOISE or line == "İletişim Bilgileri":
                continue
            if len(line) > 3:
                lines.append(line)
            if len(lines) >= 18:
                break
        return " ".join(lines) or fallback

    @staticmethod
    def _parse_profile_metrics(html: str) -> dict:
        soup = AcademicDatabase._make_soup(html)
        if not soup:
            return {}
        lines = AcademicDatabase._clean_lines(soup.get_text("\n"))
        metrics = {}
        for index, line in enumerate(lines[:-1]):
            label = METRIC_LABELS.get(line)
            if label and re.fullmatch(r"\d+", lines[index + 1]):
                metrics[label] = lines[index + 1]
        return metrics

    @staticmethod
    def _category_links(html: str, base_url: str) -> dict:
        soup = AcademicDatabase._make_soup(html)
        if not soup:
            return {}
        links = {}
        for anchor in soup.find_all("a", href=True):
            key = CATEGORY_LABELS.get(AcademicDatabase._normalize(anchor.get_text(" ", strip=True)))
            if key:
                links[key] = urljoin(base_url, anchor["href"])
        return links

    @staticmethod
    def _parse_publications(html: str) -> list[dict]:
        soup = AcademicDatabase._make_soup(html)
        if not soup:
            return []
        lines = AcademicDatabase._clean_lines(soup.get_text("\n"))
        items, seen, current_scope, current, started = [], set(), "Genel", None, False
        scopes = {"Uluslararası", "Ulusal", "International", "National", "SCI", "SSCI", "ESCI", "Diğer", "Other", "ULUSLARARASI", "ULUSAL"}

        def flush() -> None:
            nonlocal current
            if not current or not current.get("title"):
                current = None
                return
            signature = AcademicDatabase._normalize(current["title"])
            if signature and signature not in seen:
                seen.add(signature)
                current["citation"] = " | ".join(current.get("details", [])[:2])
                items.append(current)
            current = None

        for line in lines:
            if line in NOISE:
                continue
            if line == "İletişim Bilgileri":
                break
            if line in scopes:
                flush()
                current_scope = line.title() if line.isupper() else line
                started = True
                continue
            if re.fullmatch(r"\d+", line):
                flush()
                current = {"index": line, "scope": current_scope, "title": "", "details": []}
                started = True
                continue
            if not started:
                continue
            if current is None:
                current = {"index": "", "scope": current_scope, "title": "", "details": []}
            if line.startswith("http"):
                current["url"] = line
            elif not current["title"]:
                current["title"] = line
            else:
                current["details"].append(line)
        flush()
        return items

    @staticmethod
    @lru_cache(maxsize=1)
    def get_staff() -> dict:
        parsed = AcademicDatabase._parse_staff_page(AcademicDatabase._fetch_html(ACADEMIC_STAFF_URL))
        if parsed:
            merged = {name: AcademicDatabase._merge_record(name, parsed.get(name, {})) for name in STATIC_STAFF}
            for name, info in parsed.items():
                if name not in merged:
                    merged[name] = AcademicDatabase._merge_record(name, info)
            AcademicDatabase._cache_put("staff", merged)
            return merged
        cached = AcademicDatabase._cache_get("staff")
        if cached:
            return cached.get("data", STATIC_STAFF)
        return STATIC_STAFF

    @staticmethod
    @lru_cache(maxsize=1)
    def get_department_snapshot() -> dict:
        soup = AcademicDatabase._make_soup(AcademicDatabase._fetch_html(DEPARTMENT_HOME_URL))
        if soup:
            lines = AcademicDatabase._clean_lines(soup.get_text("\n"))
            data = dict(STATIC_DEPARTMENT)
            data["stats"] = AcademicDatabase._parse_stats(lines) or dict(STATIC_DEPARTMENT["stats"])
            data["announcements"] = AcademicDatabase._section_items(lines, "Duyurular", ["HABERLER", "Haberler", "Sayılarla Bölüm"], 6) or list(STATIC_DEPARTMENT["announcements"])
            data["news"] = AcademicDatabase._section_items(lines, "HABERLER", ["Sayılarla Bölüm", "Etkinlikler ve Akademik Takvim"], 6) or list(STATIC_DEPARTMENT["news"])
            data["events"] = AcademicDatabase._section_items(lines, "Yaklaşan Etkinlikler", ["İletişim Bilgileri", "Bursa Teknik Üniversitesi"], 8) or list(STATIC_DEPARTMENT["events"])
            data["contact"] = AcademicDatabase._parse_contact(lines)
            data = AcademicDatabase._annotate(data, "Canlı BTÜ kaynağı", _stamp())
            AcademicDatabase._cache_put("department_snapshot", data)
            return data
        cached = AcademicDatabase._cache_get("department_snapshot")
        if cached:
            return AcademicDatabase._annotate(cached.get("data", STATIC_DEPARTMENT), "Yerel JSON önbellek", cached.get("last_sync", "-"))
        return AcademicDatabase._annotate(STATIC_DEPARTMENT, "Yerel statik yedek", "-")

    @staticmethod
    @lru_cache(maxsize=1)
    def get_department_pages() -> dict:
        data = {
            "home_url": DEPARTMENT_HOME_URL,
            "staff_url": ACADEMIC_STAFF_URL,
            "vizyon_misyon_url": DEPARTMENT_PAGES["vizyon_misyon"],
            "genel_bilgiler_url": DEPARTMENT_PAGES["genel_bilgiler"],
            "tarihce_url": DEPARTMENT_PAGES["tarihce"],
            "ders_plani_url": DEPARTMENT_PAGES["ders_plani"],
            "iletisim_url": DEPARTMENT_PAGES["iletisim"],
            "performance_report_url": STATIC_DEPARTMENT["performance_report_url"],
            "vision": AcademicDatabase._extract_page_text(DEPARTMENT_PAGES["vizyon_misyon"], STATIC_DEPARTMENT["vision"]),
            "mission": AcademicDatabase._extract_page_text(DEPARTMENT_PAGES["vizyon_misyon"], STATIC_DEPARTMENT["mission"]),
            "general_info": AcademicDatabase._extract_page_text(DEPARTMENT_PAGES["genel_bilgiler"], STATIC_DEPARTMENT["general_info"]),
            "history": AcademicDatabase._extract_page_text(DEPARTMENT_PAGES["tarihce"], STATIC_DEPARTMENT["history"]),
            "curriculum_note": AcademicDatabase._extract_page_text(DEPARTMENT_PAGES["ders_plani"], "Ders planı için resmi BTÜ ders planı bağlantısı kullanılmalıdır."),
        }
        live_hit = any(data[key] != STATIC_DEPARTMENT.get(key, None) for key in ["vision", "mission", "general_info", "history"])
        if live_hit:
            data = AcademicDatabase._annotate(data, "Canlı BTÜ sayfaları", _stamp())
            AcademicDatabase._cache_put("department_pages", data)
            return data
        cached = AcademicDatabase._cache_get("department_pages")
        if cached:
            return AcademicDatabase._annotate(cached.get("data", data), "Yerel JSON önbellek", cached.get("last_sync", "-"))
        return AcademicDatabase._annotate(data, "Yerel statik yedek", "-")

    @staticmethod
    @lru_cache(maxsize=32)
    def get_staff_detail(name: str) -> dict:
        base = dict(AcademicDatabase.get_staff().get(name, {}))
        cached = AcademicDatabase._cache_get("staff_detail", name)
        if not base and cached:
            return AcademicDatabase._annotate(cached.get("data", {}), "Yerel JSON önbellek", cached.get("last_sync", "-"))
        if not base:
            return {}

        profile_html = AcademicDatabase._fetch_html(base.get("sayfam_url", ""))
        academic_html = AcademicDatabase._fetch_html(base.get("academic_url", ""))
        metrics = AcademicDatabase._parse_profile_metrics(profile_html)
        publications = {}
        links = AcademicDatabase._category_links(academic_html, base.get("academic_url", ""))
        if links:
            for category, url in links.items():
                items = AcademicDatabase._parse_publications(AcademicDatabase._fetch_html(url))
                if items:
                    publications[category] = items
        elif academic_html:
            items = AcademicDatabase._parse_publications(academic_html)
            if items:
                publications["Makaleler"] = items

        if cached and not publications:
            cached_data = cached.get("data", {})
            publications = cached_data.get("publications", {})
            metrics = metrics or cached_data.get("metrics", {})

        if not publications and base.get("yayinlar"):
            publications["Yerel Başlıklar"] = [{"scope": "Yerel", "title": title, "details": [], "citation": "Yerel özet verisi"} for title in base["yayinlar"]]

        base["metrics"] = metrics
        base["publications"] = publications
        base["publication_summary"] = {category: len(items) for category, items in publications.items()}
        base["publication_summary"]["Toplam"] = sum(base["publication_summary"].values())
        base["publication_categories"] = list(publications.keys())

        if profile_html or academic_html or publications:
            payload = AcademicDatabase._annotate(base, "Canlı BTÜ + Sayfam", _stamp())
            AcademicDatabase._cache_put("staff_detail", payload, name)
            return payload
        if cached:
            return AcademicDatabase._annotate(cached.get("data", base), "Yerel JSON önbellek", cached.get("last_sync", "-"))
        return AcademicDatabase._annotate(base, "Yerel statik yedek", "-")

    @staticmethod
    def _course_keyword_map() -> dict:
        return {
            "UTL111 - Hukukun Temel Kavramları": ["hukuk", "borçlar", "ticaret hukuku", "sözleşme", "kanun", "nafaka", "boşanma", "aile hukuku"],
            "UTL113 - Lojistik Bilimi": ["lojistik", "tedarik zinciri", "depolama", "envanter", "taşıma", "gümrük", "yeşil lojistik"],
            "UTL115 - Makroekonomi": ["makro", "büyüme", "enflasyon", "işsizlik", "döviz", "milli gelir", "ekonomi"],
            "UTL103 - Uluslararası Ticaretin Temelleri": ["uluslararası ticaret", "ihracat", "ithalat", "incoterms", "ticaret politikası", "gümrük", "dış ticaret"],
        }

    @staticmethod
    def _tokenize_terms(values: list[str]) -> list[str]:
        tokens: list[str] = []
        for value in values:
            clean = AcademicDatabase._normalize(value)
            if not clean:
                continue
            tokens.append(clean)
            tokens.extend([part for part in re.split(r"[^a-z0-9çğıöşü]+", clean) if len(part) > 2])
        return list(dict.fromkeys(tokens))

    @staticmethod
    def _publication_text(item: dict, detail: dict, staff_name: str, category: str) -> str:
        fields = [staff_name, detail.get("area", ""), " ".join(detail.get("expertise", [])), category, item.get("scope", ""), item.get("title", ""), item.get("citation", ""), " ".join(item.get("details", []))]
        return AcademicDatabase._normalize(" ".join(fields))

    @staticmethod
    def _score_matches(search_text: str, terms: list[str]) -> tuple[int, list[str]]:
        matches: list[str] = []
        score = 0
        for term in AcademicDatabase._tokenize_terms(terms):
            if term and term in search_text:
                matches.append(term)
                score += max(1, len(term.split()))
        return score, list(dict.fromkeys(matches))

    @staticmethod
    @lru_cache(maxsize=1)
    def get_publication_index() -> dict:
        cached = AcademicDatabase._cache_get("publication_index")
        entries: list[dict] = []
        source = "Yerel JSON önbellek"
        last_sync = cached.get("last_sync", "-") if cached else "-"

        for staff_name in AcademicDatabase.get_staff().keys():
            detail = AcademicDatabase.get_staff_detail(staff_name)
            for category, items in detail.get("publications", {}).items():
                for item in items:
                    entries.append({
                        "staff_name": staff_name,
                        "category": category,
                        "scope": item.get("scope", "Genel"),
                        "title": item.get("title", ""),
                        "citation": item.get("citation", ""),
                        "url": item.get("url", ""),
                        "area": detail.get("area", ""),
                        "expertise": detail.get("expertise", []),
                        "search_text": AcademicDatabase._publication_text(item, detail, staff_name, category),
                    })
            if detail.get("data_source", "").startswith("Canlı"):
                source = "Canlı BTÜ + Sayfam"
                last_sync = detail.get("last_sync", last_sync)

        if entries:
            payload = {"entries": entries, "entry_count": len(entries)}
            AcademicDatabase._cache_put("publication_index", payload)
            return AcademicDatabase._annotate(payload, source, _stamp() if source.startswith("Canlı") else last_sync)
        if cached:
            return AcademicDatabase._annotate(cached.get("data", {"entries": [], "entry_count": 0}), "Yerel JSON önbellek", cached.get("last_sync", "-"))
        return AcademicDatabase._annotate({"entries": [], "entry_count": 0}, "Yerel statik yedek", "-")

    @staticmethod
    def recommend_publications(course_name: str, selected_topics: list[str] | None = None, limit: int = 12) -> dict:
        selected_topics = selected_topics or []
        index = AcademicDatabase.get_publication_index()
        course_terms = AcademicDatabase._course_keyword_map().get(course_name, [])
        topic_terms = selected_topics or AcademicDatabase.get_curriculum_topics().get(course_name, [])[:3]
        recommendations: list[dict] = []

        for entry in index.get("entries", []):
            course_score, course_matches = AcademicDatabase._score_matches(entry.get("search_text", ""), [course_name] + course_terms)
            topic_score, topic_matches = AcademicDatabase._score_matches(entry.get("search_text", ""), topic_terms)
            total_score = course_score * 2 + topic_score * 3
            if total_score <= 0:
                continue
            enriched = dict(entry)
            enriched["score"] = total_score
            enriched["course_matches"] = course_matches
            enriched["topic_matches"] = topic_matches
            recommendations.append(enriched)

        recommendations.sort(key=lambda item: (-item.get("score", 0), item.get("staff_name", ""), item.get("title", "")))
        top = recommendations[:limit]
        return {
            "course_name": course_name,
            "selected_topics": topic_terms,
            "results": top,
            "result_count": len(top),
            "index_source": index.get("data_source", "-"),
            "index_last_sync": index.get("last_sync", "-"),
        }

    @staticmethod
    def build_reading_list(course_name: str, selected_topics: list[str] | None = None, limit: int = 8) -> dict:
        recommendations = AcademicDatabase.recommend_publications(course_name, selected_topics, limit=limit)
        items = recommendations.get("results", [])
        lines = [
            f"# {course_name} Otomatik Okuma Listesi",
            "",
            f"Kaynak: {recommendations.get('index_source', '-')}",
            f"Son senkron: {recommendations.get('index_last_sync', '-')}",
            f"Odak konular: {', '.join(recommendations.get('selected_topics', [])) or '-'}",
            "",
            "## Okuma Sırası",
        ]
        plan = []
        for index, item in enumerate(items, start=1):
            priority = "Yüksek" if item.get("score", 0) >= 12 else "Orta" if item.get("score", 0) >= 6 else "Destek"
            stage = "1. tur kavrama" if index <= 3 else "2. tur pekiştirme" if index <= 6 else "3. tur derinleştirme"
            note = {
                "order": index,
                "title": item.get("title", "-"),
                "staff_name": item.get("staff_name", "-"),
                "score": item.get("score", 0),
                "priority": priority,
                "stage": stage,
                "category": item.get("category", "-"),
                "scope": item.get("scope", "-"),
                "course_matches": item.get("course_matches", []),
                "topic_matches": item.get("topic_matches", []),
                "url": item.get("url", ""),
            }
            plan.append(note)
            lines.extend([
                f"### {index}. {note['title']}",
                f"- Akademisyen: {note['staff_name']}",
                f"- Tür: {note['category']} / {note['scope']}",
                f"- Öncelik: {priority}",
                f"- Okuma aşaması: {stage}",
                f"- Ders eşleşmeleri: {', '.join(note['course_matches'][:5]) or '-'}",
                f"- Konu eşleşmeleri: {', '.join(note['topic_matches'][:5]) or '-'}",
                f"- Öneri skoru: {note['score']}",
                f"- Bağlantı: {note['url'] or '-'}",
                "",
            ])
        if not plan:
            lines.append("Uygun okuma önerisi üretilemedi.")
        return {
            "course_name": course_name,
            "selected_topics": recommendations.get("selected_topics", []),
            "items": plan,
            "text": "\n".join(lines),
            "index_source": recommendations.get("index_source", "-"),
            "index_last_sync": recommendations.get("index_last_sync", "-"),
        }

    @staticmethod
    def build_exam_week_priority(course_name: str, selected_topics: list[str] | None = None) -> dict:
        recommendations = AcademicDatabase.recommend_publications(course_name, selected_topics, limit=5)
        items = recommendations.get("results", [])[:5]
        lines = [
            f"# {course_name} Sinav Haftasi Icin Oncelikli 5 Yayin",
            "",
            f"Odak konular: {', '.join(recommendations.get('selected_topics', [])) or '-'}",
            "",
            "## Hizli Oncelik Listesi",
        ]
        priorities = []
        for index, item in enumerate(items, start=1):
            focus = "Temel kavram" if index <= 2 else "Vaka/uygulama" if index <= 4 else "Son tekrar"
            action = "Baslik ve ozet cikar" if index <= 2 else "Kritik kavramlari notlastir" if index <= 4 else "Tek sayfalik tekrar yap"
            record = {
                "rank": index,
                "title": item.get("title", "-"),
                "staff_name": item.get("staff_name", "-"),
                "score": item.get("score", 0),
                "focus": focus,
                "action": action,
                "topic_matches": item.get("topic_matches", []),
                "url": item.get("url", ""),
            }
            priorities.append(record)
            lines.extend([
                f"{index}. {record['title']}",
                f"   Akademisyen: {record['staff_name']}",
                f"   Odak: {focus}",
                f"   Aksiyon: {action}",
                f"   Konu eslesmeleri: {', '.join(record['topic_matches'][:5]) or '-'}",
                f"   Skor: {record['score']}",
                f"   Baglanti: {record['url'] or '-'}",
                "",
            ])
        if not priorities:
            lines.append("Oncelikli 5 yayin listesi olusturulamadi.")
        return {
            "course_name": course_name,
            "selected_topics": recommendations.get("selected_topics", []),
            "items": priorities,
            "text": "\n".join(lines),
            "index_source": recommendations.get("index_source", "-"),
            "index_last_sync": recommendations.get("index_last_sync", "-"),
        }

    @staticmethod
    def build_daily_study_plan(course_name: str, selected_topics: list[str] | None = None, days: int = 5, session_minutes: int = 60) -> dict:
        reading_list = AcademicDatabase.build_reading_list(course_name, selected_topics, limit=max(days, 6))
        exam_priority = AcademicDatabase.build_exam_week_priority(course_name, selected_topics)
        reading_items = reading_list.get("items", [])
        exam_items = exam_priority.get("items", [])
        plan_days = []
        lines = [
            f"# {course_name} Günlük Çalışma Takvimi",
            "",
            f"Gün sayısı: {days}",
            f"Oturum süresi: {session_minutes} dakika",
            f"Konular: {', '.join(reading_list.get('selected_topics', [])) or '-'}",
            "",
        ]

        for day in range(1, days + 1):
            reading_item = reading_items[(day - 1) % len(reading_items)] if reading_items else {}
            exam_item = exam_items[(day - 1) % len(exam_items)] if exam_items else {}
            warmup = min(10, max(5, session_minutes // 6))
            core = max(15, session_minutes // 2)
            recall = max(10, session_minutes - warmup - core)
            agenda = {
                "day": day,
                "warmup_minutes": warmup,
                "core_minutes": core,
                "recall_minutes": recall,
                "reading_title": reading_item.get("title", "-"),
                "reading_staff": reading_item.get("staff_name", "-"),
                "priority_title": exam_item.get("title", reading_item.get("title", "-")),
                "priority_focus": exam_item.get("focus", "Kavram tekrarı"),
                "action": exam_item.get("action", "Anahtar kavramları çıkar"),
            }
            plan_days.append(agenda)
            lines.extend([
                f"## Gün {day}",
                f"- Isınma ({warmup} dk): Önceki günün kısa tekrarını yap ve konu başlıklarını gözden geçir.",
                f"- Ana blok ({core} dk): {agenda['reading_title']} / {agenda['reading_staff']}",
                f"- Pekiştirme ({recall} dk): {agenda['priority_focus']} - {agenda['action']}",
                "",
            ])

        if not plan_days:
            lines.append("Günlük plan üretilemedi.")
        return {
            "course_name": course_name,
            "selected_topics": reading_list.get("selected_topics", []),
            "days": plan_days,
            "session_minutes": session_minutes,
            "text": "\n".join(lines),
            "index_source": reading_list.get("index_source", "-"),
            "index_last_sync": reading_list.get("index_last_sync", "-"),
        }

    @staticmethod
    def build_focus_mode(course_name: str, selected_topics: list[str] | None = None, minutes: int = 30) -> dict:
        recommendations = AcademicDatabase.recommend_publications(course_name, selected_topics, limit=3)
        items = recommendations.get("results", [])
        mode_templates = {
            30: [(5, "Hızlı tarama"), (15, "Ana okuma"), (10, "Kısa tekrar")],
            60: [(10, "Isınma"), (30, "Ana okuma"), (20, "Not çıkarma")],
            90: [(15, "Isınma ve kavram haritası"), (45, "Derin okuma"), (30, "Soru-cevap ve tekrar")],
        }
        blocks = mode_templates.get(minutes, mode_templates[60])
        lines = [
            f"# {course_name} {minutes} Dakikalık Mini Çalışma Modu",
            "",
            f"Konular: {', '.join(recommendations.get('selected_topics', [])) or '-'}",
            "",
            "## Zaman Blokları",
        ]
        plan = []
        for index, (block_minutes, label) in enumerate(blocks, start=1):
            item = items[min(index - 1, len(items) - 1)] if items else {}
            task = {
                "block": index,
                "minutes": block_minutes,
                "label": label,
                "title": item.get("title", "-"),
                "staff_name": item.get("staff_name", "-"),
                "task": "Ana kavramları işaretle" if index == 1 else "Kritik pasajları notlaştır" if index == 2 else "5 maddelik özet çıkar",
                "url": item.get("url", ""),
            }
            plan.append(task)
            lines.extend([
                f"### Blok {index} - {label} ({block_minutes} dk)",
                f"- Yayın: {task['title']}",
                f"- Akademisyen: {task['staff_name']}",
                f"- Görev: {task['task']}",
                f"- Bağlantı: {task['url'] or '-'}",
                "",
            ])

        if not plan:
            lines.append("Mini çalışma modu üretilemedi.")
        return {
            "course_name": course_name,
            "minutes": minutes,
            "selected_topics": recommendations.get("selected_topics", []),
            "blocks": plan,
            "text": "\n".join(lines),
            "index_source": recommendations.get("index_source", "-"),
            "index_last_sync": recommendations.get("index_last_sync", "-"),
        }

    @staticmethod
    def build_exam_strategy(course_name: str, strategy_name: str, selected_topics: list[str] | None = None) -> dict:
        normalized = AcademicDatabase._normalize(strategy_name)
        recommendations = AcademicDatabase.recommend_publications(course_name, selected_topics, limit=10)
        reading_list = AcademicDatabase.build_reading_list(course_name, selected_topics, limit=8)
        exam_priority = AcademicDatabase.build_exam_week_priority(course_name, selected_topics)

        strategies = {
            "vize haftasi": {
                "label": "Vize Haftası",
                "days": 7,
                "focus": "Temel kavramlar, tanımlar ve dersin çekirdek çerçevesi",
                "rhythm": "Orta yoğunluk + günlük tekrar",
                "minutes": 60,
                "goal": "Kavramları netleştirip konu haritası oluşturmak",
            },
            "final haftasi": {
                "label": "Final Haftası",
                "days": 10,
                "focus": "Kapsamlı tekrar, bağlantı kurma ve bütün ünite sentezi",
                "rhythm": "Yüksek yoğunluk + iki katmanlı tekrar",
                "minutes": 90,
                "goal": "Tüm üniteleri birbirine bağlayıp soru çözümüne hazır hale gelmek",
            },
            "son 3 gun panik modu": {
                "label": "Son 3 Gün Panik Modu",
                "days": 3,
                "focus": "Yüksek getirili başlıklar ve son dakika ezber-kavrama dengesi",
                "rhythm": "Çok yüksek yoğunluk + kısa hızlı bloklar",
                "minutes": 30,
                "goal": "En kritik yayın ve kavramlarla hızlı puan kazanımı",
            },
        }
        selected = strategies.get(normalized, strategies["vize haftasi"])
        daily_plan = AcademicDatabase.build_daily_study_plan(course_name, selected_topics, days=selected["days"], session_minutes=selected["minutes"])
        focus_mode = AcademicDatabase.build_focus_mode(course_name, selected_topics, minutes=selected["minutes"])
        top_reading = reading_list.get("items", [])[:5]
        top_priority = exam_priority.get("items", [])[:5]

        lines = [
            f"# {course_name} - {selected['label']} Stratejisi",
            "",
            f"Odak: {selected['focus']}",
            f"Tempo: {selected['rhythm']}",
            f"Ana hedef: {selected['goal']}",
            f"Önerilen günlük süre: {selected['minutes']} dakika",
            f"Konular: {', '.join(recommendations.get('selected_topics', [])) or '-'}",
            "",
            "## Kritik Yayınlar",
        ]
        priority_items = []
        for index, item in enumerate(top_priority, start=1):
            priority_items.append({
                "rank": index,
                "title": item.get("title", "-"),
                "staff_name": item.get("staff_name", "-"),
                "focus": item.get("focus", "-"),
                "action": item.get("action", "-"),
                "score": item.get("score", 0),
                "url": item.get("url", ""),
            })
            lines.extend([
                f"{index}. {item.get('title', '-')}",
                f"   Akademisyen: {item.get('staff_name', '-')}",
                f"   Odak: {item.get('focus', '-')}",
                f"   Aksiyon: {item.get('action', '-')}",
                f"   Bağlantı: {item.get('url', '-') or '-'}",
                "",
            ])

        lines.extend(["## Günlük Akış Özeti", ""])
        for day in daily_plan.get("days", [])[: selected["days"]]:
            lines.extend([
                f"Gün {day.get('day', '-')}: {day.get('reading_title', '-')} | {day.get('priority_focus', '-')}",
                f"- Süre blokları: {day.get('warmup_minutes', 0)} + {day.get('core_minutes', 0)} + {day.get('recall_minutes', 0)} dk",
                "",
            ])

        lines.extend(["## Mini Mod Özeti", ""])
        for block in focus_mode.get("blocks", []):
            lines.extend([
                f"Blok {block.get('block', '-')}: {block.get('label', '-')} ({block.get('minutes', 0)} dk)",
                f"- Yayın: {block.get('title', '-')}",
                f"- Görev: {block.get('task', '-')}",
                "",
            ])

        return {
            "strategy_name": selected["label"],
            "course_name": course_name,
            "selected_topics": recommendations.get("selected_topics", []),
            "focus": selected["focus"],
            "rhythm": selected["rhythm"],
            "goal": selected["goal"],
            "recommended_minutes": selected["minutes"],
            "daily_plan": daily_plan,
            "focus_mode": focus_mode,
            "priority_items": priority_items,
            "reading_items": top_reading,
            "text": "\n".join(lines),
            "index_source": recommendations.get("index_source", "-"),
            "index_last_sync": recommendations.get("index_last_sync", "-"),
        }

    @staticmethod
    def extract_pdf_schedule() -> pd.DataFrame:
        pdf_path = SystemConfig.find_pdf_path()
        if not pdf_path:
            return AcademicDatabase.get_fallback_schedule()
        try:
            schedule_data = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    current_day = ""
                    for line in text.splitlines():
                        clean = line.strip()
                        upper = clean.upper()
                        if "PAZARTESİ" in upper:
                            current_day = "Pazartesi"
                        elif "SALI" in upper:
                            current_day = "Salı"
                        elif "ÇARŞAMBA" in upper:
                            current_day = "Çarşamba"
                        elif "PERŞEMBE" in upper:
                            current_day = "Perşembe"
                        elif "CUMA" in upper:
                            current_day = "Cuma"
                        if current_day and any(code in upper for code in ["UTL", "MAT", "ING"]):
                            schedule_data.append({"Gün": current_day, "Ders": re.sub(r"\s+", " ", clean)})
            if not schedule_data:
                return AcademicDatabase.get_fallback_schedule()
            hours = ["08:30-09:20", "09:30-10:20", "10:30-11:20", "11:30-12:20", "13:30-14:20", "14:30-15:20", "15:30-16:20"]
            days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
            data = {"Saat": hours}
            for day in days:
                courses = [item["Ders"] for item in schedule_data if item["Gün"] == day]
                data[day] = courses[: len(hours)] + ["-"] * max(0, len(hours) - len(courses[: len(hours)]))
            return pd.DataFrame(data)
        except Exception:
            return AcademicDatabase.get_fallback_schedule()

    @staticmethod
    def get_fallback_schedule() -> pd.DataFrame:
        return pd.DataFrame({
            "Saat": ["08:30-09:20", "09:30-10:20", "10:30-11:20", "11:30-12:20", "13:30-14:20", "14:30-15:20", "15:30-16:20", "16:30-17:20"],
            "Pazartesi": ["UTL113 Lojistik Bilimi", "UTL113 Lojistik Bilimi", "UTL113 Lojistik Bilimi", "Öğle Arası", "UTL317 Ulus. Tic. Hukuku", "UTL317 Ulus. Tic. Hukuku", "UTL317 Ulus. Tic. Hukuku", "-"],
            "Salı": ["UTL101 Matematik", "UTL101 Matematik", "UTL101 Matematik", "Öğle Arası", "UTL215 İth. İhr. Yön.", "UTL215 İth. İhr. Yön.", "UTL215 İth. İhr. Yön.", "-"],
            "Çarşamba": ["UTL115 Makroekonomi", "UTL115 Makroekonomi", "UTL115 Makroekonomi", "Öğle Arası", "UTL111 Hukukun T.K.", "UTL111 Hukukun T.K.", "UTL111 Hukukun T.K.", "-"],
            "Perşembe": ["UTL213 Lojistik Hukuku", "UTL213 Lojistik Hukuku", "UTL213 Lojistik Hukuku", "Öğle Arası", "UTL309 Lojistik Maliyet", "UTL309 Lojistik Maliyet", "UTL309 Lojistik Maliyet", "-"],
            "Cuma": ["UTL103 Ulus. Tic. Tem.", "UTL103 Ulus. Tic. Tem.", "UTL103 Ulus. Tic. Tem.", "Öğle Arası", "Seçmeli Dersler", "Seçmeli Dersler", "Seçmeli Dersler", "-"],
        })

    @staticmethod
    def get_curriculum_topics() -> dict:
        return {
            "UTL111 - Hukukun Temel Kavramları": ["Hukukun Kaynakları", "Hukuk Sistemleri", "Hukuk Kuralları", "Borçlar Hukuku", "Ticaret Hukuku"],
            "UTL113 - Lojistik Bilimi": ["Lojistiğin Temelleri", "Tedarik Zinciri Yönetimi", "Depolama ve Envanter", "Gümrük İşlemleri", "Risk Yönetimi"],
            "UTL115 - Makroekonomi": ["Makroekonomik Göstergeler", "Milli Gelir", "Enflasyon ve İşsizlik", "Döviz Kurları", "Ekonomik Büyüme"],
            "UTL103 - Uluslararası Ticaretin Temelleri": ["Uluslararası Ticaret Teorileri", "Ticaret Politikaları", "İhracat ve İthalat Prosedürleri", "Incoterms 2020", "Küresel Tedarik Zinciri"],
        }







