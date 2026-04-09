from typing import Optional
import pathlib

import plotly.express as px
import streamlit as st
from PIL import Image

from leksikograf.academic import AcademicDatabase
from leksikograf.config import SystemConfig
from leksikograf.ocr import AdvancedOCREngine, ProfessionalDigitalizer
from leksikograf.progress import StudyProgressTracker
from leksikograf.storage import NotesStorage
from leksikograf.study import (
    build_course_library,
    build_curriculum_report,
    generate_practice_questions,
    summarize_professor,
)


OCR_ENGINE = AdvancedOCREngine()
DIGITALIZER = ProfessionalDigitalizer(OCR_ENGINE)


def init_session() -> None:
    defaults = {
        "user_xp": 350,
        "digitalized_notes": [],
        "current_course": None,
        "selected_professor": None,
        "library_store": {},
        "exam": [],
        "notes_dir": SystemConfig.default_notes_dir(),
        "notes_storage": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def quality_badge(score: float) -> str:
    if score >= 80:
        return '<span class="quality-badge quality-excellent">YÜKSEK KALİTE</span>'
    if score >= 60:
        return '<span class="quality-badge quality-good">ORTA KALİTE</span>'
    return '<span class="quality-badge quality-fair">DÜŞÜK KALİTE</span>'


def save_unsaved_notes(storage: Optional[NotesStorage]) -> int:
    if not storage:
        return 0
    saved = 0
    for note in st.session_state.get("digitalized_notes", []):
        if not note.get("saved_json_path"):
            storage.save_note(note)
            saved += 1
    return saved


def sync_progress_checkbox(
    course_name: str,
    strategy_name: str,
    selected_topics: list[str],
    item_id: str,
    label: str,
    key: str,
    meta: Optional[dict] = None,
) -> bool:
    record = StudyProgressTracker.get_plan_record(course_name, strategy_name, selected_topics)
    saved_value = record.get("items", {}).get(item_id, {}).get("completed", False)
    checked = st.checkbox(label, value=saved_value, key=key)
    if checked != saved_value:
        StudyProgressTracker.set_item_status(course_name, strategy_name, selected_topics, item_id, label, checked, meta or {})
    return checked


def render_sidebar() -> Optional[NotesStorage]:
    with st.sidebar:
        st.header("Kontrol Paneli")
        st.caption("Bu sürüm tamamen yerel çalışır. API anahtarı gerekmez.")

        notes_dir = st.text_input(
            "Arşiv Klasörü (JSON + MD)",
            value=st.session_state.get("notes_dir", ""),
        )
        if notes_dir:
            st.session_state.notes_dir = notes_dir

        try:
            storage = NotesStorage(st.session_state.notes_dir)
            st.session_state.notes_storage = storage
            st.caption(f"Arşiv: {storage.base_dir}")
        except Exception as exc:
            st.session_state.notes_storage = None
            st.error(f"Arşiv klasörü hazırlanamadı: {exc}")
            storage = None

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Oturumu Kaydet"):
                saved = save_unsaved_notes(storage)
                st.success(f"Kaydedilen not: {saved}")
        with col_b:
            if st.button("Arşivi Oku") and storage:
                st.session_state["_archive_list"] = storage.list_notes()
                st.success(f"Arşiv yüklendi: {len(st.session_state['_archive_list'])}")

        archive_list = st.session_state.get("_archive_list", [])
        if archive_list and storage:
            labels = [
                f"{item.get('timestamp', '')[:16]} | {item.get('ders_adi', '')} | {item.get('hoca', '')}"
                for item in archive_list
            ]
            selected = st.selectbox(
                "Arşivden Not Seç",
                options=list(range(len(archive_list))),
                format_func=lambda index: labels[index],
            )
            if st.button("Seçili Notu Ekle"):
                note = storage.load_note_by_json_path(archive_list[selected]["json_path"])
                existing_ids = {item.get("id") for item in st.session_state["digitalized_notes"]}
                if note.get("id") in existing_ids:
                    st.info("Bu not zaten oturumda var.")
                else:
                    st.session_state["digitalized_notes"].append(note)
                    st.success("Not oturuma eklendi.")

        st.divider()
        st.markdown("### İstatistikler")
        st.metric("Dijital Not", len(st.session_state["digitalized_notes"]))
        st.metric("Akademik XP", st.session_state["user_xp"])
        total_words = sum(note.get("word_count", 0) for note in st.session_state["digitalized_notes"])
        st.metric("Toplam Kelime", f"{total_words:,}")

        st.divider()
        st.markdown("### Hızlı İşlemler")
        if st.button("Sayfayı Yenile", use_container_width=True):
            st.rerun()
        if st.button("Kalite Raporu", use_container_width=True):
            notes = st.session_state["digitalized_notes"]
            if notes:
                high_quality = len([n for n in notes if n.get("quality_score", 0) >= 80])
                medium_quality = len([n for n in notes if 60 <= n.get("quality_score", 0) < 80])
                low_quality = len([n for n in notes if n.get("quality_score", 0) < 60])
                st.info(
                    "\n".join(
                        [
                            "Kalite Analizi",
                            f"- Yüksek kalite: {high_quality}",
                            f"- Orta kalite: {medium_quality}",
                            f"- Düşük kalite: {low_quality}",
                        ]
                    )
                )
        return storage


def render_dashboard_tab() -> None:
    st.header("Akademik Dashboard")
    notes = st.session_state["digitalized_notes"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Dijital Not", len(notes))
    with col2:
        avg_conf = sum(note.get("confidence", 0) for note in notes) / len(notes) if notes else 0
        st.metric("Ort. Doğruluk", f"{avg_conf:.1f}%")
    with col3:
        st.metric("İşlenen Sayfa", len(notes))
    with col4:
        st.metric("Akademik XP", st.session_state["user_xp"])

    st.subheader("Son Dijitalleştirilen Notlar")
    if not notes:
        st.info("Henüz dijital not yok. 'Profesyonel OCR' sekmesinden başlayın.")
        return

    for note in reversed(notes[-3:]):
        badge = quality_badge(note.get("quality_score", 0))
        with st.expander(
            f"{note.get('ders_adi', 'Bilinmiyor')} - {note.get('hoca', 'Bilinmiyor')} {badge}",
            expanded=False,
        ):
            st.markdown(f"**Dosya:** {note.get('filename', 'Bilinmiyor')}")
            st.markdown(f"**İşlem Süresi:** {note.get('processing_time', 0):.1f}s")
            st.markdown(f"**Güven:** {note.get('confidence', 0):.1f}%")
            st.markdown(f"**Kalite:** {note.get('quality_score', 0):.1f}/100")
            preview = note.get("content", "")
            preview = preview[:400] + "..." if len(preview) > 400 else preview
            st.text(preview)
            st.download_button(
                label="İndir",
                data=note.get("content", "").encode("utf-8"),
                file_name=f"Not_{note.get('id', 'not')}.txt",
                mime="text/plain",
                key=f"dashboard_dl_{note.get('id')}",
            )


def render_ocr_tab(storage: Optional[NotesStorage]) -> None:
    st.header("Profesyonel OCR")
    st.info("Bu akış tamamen yerel çalışır. OCR sonrası yalnızca yerel terim düzeltmeleri uygulanır.")

    col_left, col_right = st.columns([1, 2])
    with col_left:
        ders_options = [
            "UTL111 - Hukukun Temel Kavramları",
            "UTL113 - Lojistik Bilimi",
            "UTL115 - Makroekonomi",
            "UTL103 - Uluslararası Ticaretin Temelleri",
            "Diğer (Manuel Girin)",
        ]
        selected_ders = st.selectbox("Ders", ders_options)
        ders_adi = st.text_input("Ders Adı") if selected_ders == "Diğer (Manuel Girin)" else selected_ders

        staff = AcademicDatabase.get_staff()
        selected_hoca = st.selectbox("Öğretim Üyesi", sorted(staff.keys()))
        auto_save = st.checkbox("İşlem sonrası arşive kaydet", value=bool(storage))

    with col_right:
        uploaded_files = st.file_uploader(
            "Not görsellerini yükleyin",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )
        if uploaded_files and len(uploaded_files) <= 6:
            columns = st.columns(3)
            for index, file in enumerate(uploaded_files):
                with columns[index % 3]:
                    st.image(Image.open(file), caption=file.name, width=150)

        if uploaded_files and st.button("Dijitalleştir", type="primary", use_container_width=True):
            if not ders_adi:
                st.error("Lütfen ders adını girin.")
                return
            with st.spinner("Notlar OCR ile işleniyor..."):
                results = DIGITALIZER.process_notes_batch(uploaded_files, ders_adi, selected_hoca)
                for note in results["notes"]:
                    st.session_state["digitalized_notes"].append(note)
                    if auto_save and storage:
                        storage.save_note(note)
                st.session_state["user_xp"] += results["successful"] * 10

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Başarılı", results["successful"])
            with col2:
                st.metric("Başarısız", results["failed"])
            with col3:
                st.metric("Toplam Süre", f"{results['total_time']:.1f}s")

            for note in results["notes"]:
                with st.expander(f"Sayfa {note['page']} - {note['filename']}", expanded=False):
                    st.markdown(f"**Kalite:** {note['quality_score']:.1f}/100")
                    st.markdown(f"**Güven:** {note['confidence']:.1f}%")
                    st.text_area(
                        "Tam Metin",
                        note["content"],
                        height=220,
                        key=f"ocr_note_{note['id']}",
                    )
                    st.download_button(
                        label="Bu Sayfayı İndir",
                        data=note["content"].encode("utf-8"),
                        file_name=f"{ders_adi.replace(' ', '_')}_Sayfa{note['page']}.txt",
                        mime="text/plain",
                        key=f"ocr_dl_{note['id']}",
                    )
            if results["errors"]:
                st.warning("\n".join(results["errors"]))


def render_library_tab() -> None:
    st.header("Akademik Kütüphane")
    col1, col2 = st.columns([1, 2])

    with col1:
        dersler = [
            "UTL111 - Hukukun Temel Kavramları",
            "UTL113 - Lojistik Bilimi",
            "UTL115 - Makroekonomi",
            "UTL103 - Uluslararası Ticaretin Temelleri",
        ]
        selected_course = st.selectbox("Ders", dersler, key="library_course")
        selected_prof = st.selectbox("Öğretim Üyesi", sorted(AcademicDatabase.get_staff().keys()), key="library_prof")
        pdf_file = st.file_uploader("PDF Kaynak Yükle", type=["pdf"], key="library_pdf")

        if st.button("Kütüphanemi Oluştur", type="primary", use_container_width=True):
            st.session_state["current_course"] = {"adi": selected_course, "hoca": selected_prof}
            if pdf_file:
                store = build_course_library(pdf_file.read())
                store["pdf_name"] = pdf_file.name
                st.session_state["library_store"][selected_course] = store
                st.success(f"PDF işlendi. {len(store['chunks'])} parça oluşturuldu.")
            else:
                st.info("PDF yüklemeden de yerel çalışma araçlarını kullanabilirsiniz.")

    with col2:
        course = st.session_state.get("current_course")
        if not course:
            st.info("Sol panelden ders ve PDF seçerek başlayın.")
            return

        store = st.session_state["library_store"].get(course["adi"])
        shelf_html = '<div class="shelf">' + "".join(
            [
                '<div class="book mid">Ders Notları</div>',
                '<div class="book hard">Sınavda Çıkar</div>',
                '<div class="book easy">Ek Kaynak</div>',
                '<div class="book mid">Önemli Terimler</div>',
            ]
        ) + "</div>"
        st.markdown(shelf_html, unsafe_allow_html=True)

        if not store:
            st.info("Bu ders için henüz PDF yüklenmemiş.")
            return

        if st.button("PDF'ten Yerel Soru Üret"):
            st.session_state["exam"] = generate_practice_questions(store["chunks"])
            st.success(f"{len(st.session_state['exam'])} soru oluşturuldu.")

        for index, question in enumerate(st.session_state.get("exam", []), start=1):
            with st.container(border=True):
                st.markdown(f"**Soru {index}**")
                st.text(question["text"])
                st.caption(f"Kaynak sayfa: {question['source_page']}")
                with st.expander("Kaynak Metni Gör"):
                    st.text(question["source_text"])

        st.subheader("PDF Analizi")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Chunk Sayısı", len(store["chunks"]))
        with col_b:
            total_chars = sum(len(item["text"]) for item in store["chunks"])
            st.metric("Toplam Karakter", f"{total_chars:,}")
        with col_c:
            max_page = max(store["pages"]) if store["pages"] else 0
            st.metric("Sayfa Aralığı", f"1-{max_page}")

        for index, chunk in enumerate(store["chunks"][:3], start=1):
            with st.expander(f"Chunk {index} - Sayfa {chunk['page']}"):
                st.text(chunk["text"][:300] + ("..." if len(chunk["text"]) > 300 else ""))


def render_staff_tab() -> None:
    st.header("BTÜ Akademik Kadrosu ve Bölüm Zekası")
    toolbar_left, toolbar_right = st.columns([3, 1])
    with toolbar_left:
        st.caption("Resmi BTÜ kaynakları ve yerel JSON önbellek birlikte kullanılır.")
    with toolbar_right:
        if st.button("Akademik Veriyi Yenile", use_container_width=True):
            AcademicDatabase.clear_runtime_cache()
            st.rerun()

    staff = AcademicDatabase.get_staff()
    snapshot = AcademicDatabase.get_department_snapshot()
    pages = AcademicDatabase.get_department_pages()

    stat_items = list(snapshot.get("stats", {}).items())[:5]
    if stat_items:
        stat_cols = st.columns(len(stat_items))
        for index, (label, value) in enumerate(stat_items):
            with stat_cols[index]:
                st.metric(label, value)
    st.caption(f"{snapshot.get('updated_note', 'Resmi BTÜ kaynakları ile zenginleştirilmiş bölüm görünümü.')} | Kaynak: {snapshot.get('data_source', '-')} | Son senkron: {snapshot.get('last_sync', '-')}")

    subtabs = st.tabs(["Bölüm Özeti", "Duyurular ve Haberler", "Etkinlikler ve İletişim", "Kadro ve Yayınlar", "Konu Bazlı Öneriler"])

    with subtabs[0]:
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("### Bölüm Kimliği")
            st.markdown(pages.get("general_info", "-"))
            st.markdown("### Vizyon / Misyon")
            st.markdown(pages.get("vision", "-"))
            st.markdown(pages.get("mission", "-"))
        with col_right:
            st.markdown("### Tarihçe")
            st.markdown(pages.get("history", "-"))
            st.markdown("### Ders Planı Notu")
            st.markdown(pages.get("curriculum_note", "-"))
            if pages.get("home_url"):
                st.link_button("Bölüm Anasayfası", pages["home_url"], use_container_width=True)
            if pages.get("performance_report_url"):
                st.link_button("Akademik Performans Raporu", pages["performance_report_url"], use_container_width=True)

    with subtabs[1]:
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("### Duyurular")
            for item in snapshot.get("announcements", []):
                st.markdown(f"- {item}")
        with col_right:
            st.markdown("### Haberler")
            for item in snapshot.get("news", []):
                st.markdown(f"- {item}")

    with subtabs[2]:
        col_left, col_right = st.columns(2)
        contact = snapshot.get("contact", {})
        with col_left:
            st.markdown("### Yaklaşan Etkinlikler")
            for item in snapshot.get("events", []):
                st.markdown(f"- {item}")
        with col_right:
            st.markdown("### İletişim")
            st.markdown(f"**Adres:** {contact.get('address', '-')}")
            st.markdown(f"**Telefon:** {contact.get('phone', '-')}")
            st.markdown(f"**E-posta:** {contact.get('email', '-')}")
            st.markdown(f"**KEP:** {contact.get('kep', '-')}")
            if pages.get("staff_url"):
                st.link_button("Resmi Akademik Kadro Sayfası", pages["staff_url"], use_container_width=True)
            if pages.get("iletisim_url"):
                st.link_button("Resmi İletişim Sayfası", pages["iletisim_url"], use_container_width=True)

    with subtabs[3]:
        query = st.text_input("İsim, rol veya uzmanlık ara", key="staff_search")
        areas = ["Tümü"] + sorted({info.get("area", "Genel") for info in staff.values()})
        selected_area = st.selectbox("Uzmanlık Alanı", areas, key="staff_area")

        filtered_names = []
        for name, info in sorted(staff.items()):
            haystack = " ".join([
                name,
                info.get("title", ""),
                info.get("role", ""),
                info.get("area", ""),
                " ".join(info.get("expertise", [])),
            ]).lower()
            search_match = not query or query.lower() in haystack
            area_match = selected_area == "Tümü" or info.get("area") == selected_area
            if search_match and area_match:
                filtered_names.append(name)

        if not filtered_names:
            st.warning("Filtreye uygun akademik personel bulunamadı.")
            return

        selected_name = st.selectbox("Detaylı profil", filtered_names, key="staff_detail_select")
        detail = AcademicDatabase.get_staff_detail(selected_name)
        st.caption(f"Profil kaynağı: {detail.get('data_source', '-')} | Son senkron: {detail.get('last_sync', '-')}")
        info_cols = st.columns(3)
        with info_cols[0]:
            st.markdown(f"### {selected_name}")
            st.markdown(f"**Unvan:** {detail.get('title', '-')}")
            st.markdown(f"**Rol:** {detail.get('role', '-')}")
            st.markdown(f"**Alan:** {detail.get('area', '-')}")
        with info_cols[1]:
            st.markdown(f"**E-posta:** {detail.get('email', '-')}")
            st.markdown(f"**Telefon:** {detail.get('phone', '-')}")
            st.markdown(f"**Oda:** {detail.get('room', '-')}")
        with info_cols[2]:
            expertise = ", ".join(detail.get("expertise", [])[:6]) or "-"
            st.markdown(f"**Uzmanlıklar:** {expertise}")
            st.info(detail.get("sinav_ipucu", ""))
            if detail.get("sayfam_url"):
                st.link_button("Sayfam Profili", detail["sayfam_url"], use_container_width=True)
            if detail.get("academic_url"):
                st.link_button("Akademik Yayın Sayfası", detail["academic_url"], use_container_width=True)

        metric_pairs = list(detail.get("metrics", {}).items()) + list(detail.get("publication_summary", {}).items())
        if metric_pairs:
            metric_cols = st.columns(min(4, len(metric_pairs)))
            for index, (label, value) in enumerate(metric_pairs[:4]):
                with metric_cols[index]:
                    st.metric(label, value)

        publications = detail.get("publications", {})
        if publications:
            st.markdown("### Yayın ve Bildiri Havuzu")
            for category, items in publications.items():
                with st.expander(f"{category} ({len(items)})", expanded=(category == "Makaleler")):
                    for item in items[:30]:
                        st.markdown(f"**{item.get('title', '-') }**")
                        meta_parts = [item.get("scope", ""), item.get("citation", "")]
                        meta_text = " | ".join([part for part in meta_parts if part])
                        if meta_text:
                            st.caption(meta_text)
                        if item.get("url"):
                            st.markdown(f"[Kaynak bağlantısı]({item['url']})")
                    if len(items) > 30:
                        st.info("İlk 30 kayıt gösteriliyor.")
        else:
            st.info("Bu profil için canlı yayın verisi okunamadı; temel akademik profil gösteriliyor.")

        st.markdown("### Filtrelenmiş Kadro Özeti")
        for name in filtered_names:
            info = staff[name]
            with st.container(border=True):
                st.markdown(f"### {name}")
                st.markdown(f"{info.get('title', '-')} | {info.get('role', '-')} | {info.get('area', '-')}")
                st.markdown(f"{info.get('email', '-')} | {info.get('phone', '-')}")
                st.caption(", ".join(info.get("expertise", [])[:5]))
                with st.expander("Yerel Profil Özeti"):
                    st.markdown(summarize_professor(name, info))

    with subtabs[4]:
        curriculum = AcademicDatabase.get_curriculum_topics()
        selected_course = st.selectbox("Ders", list(curriculum.keys()), key="pub_index_course")
        default_topics = curriculum[selected_course][:2]
        selected_topics = st.multiselect("Öncelikli Konular", curriculum[selected_course], default=default_topics, key="pub_index_topics")
        strategy_name = st.selectbox("Çalışma stratejisi", ["Vize Haftası", "Final Haftası", "Son 3 Gün Panik Modu"], index=0, key="strategy_name")
        study_days = st.slider("Günlük plan günü", 3, 10, 5, key="study_days")
        focus_minutes = st.selectbox("Mini çalışma modu", [30, 60, 90], index=1, key="focus_minutes")

        recommendations = AcademicDatabase.recommend_publications(selected_course, selected_topics, limit=12)
        reading_list = AcademicDatabase.build_reading_list(selected_course, selected_topics, limit=8)
        exam_priority = AcademicDatabase.build_exam_week_priority(selected_course, selected_topics)
        daily_plan = AcademicDatabase.build_daily_study_plan(selected_course, selected_topics, days=study_days, session_minutes=focus_minutes)
        focus_mode = AcademicDatabase.build_focus_mode(selected_course, selected_topics, minutes=focus_minutes)
        strategy_plan = AcademicDatabase.build_exam_strategy(selected_course, strategy_name, selected_topics)
        publication_index = AcademicDatabase.get_publication_index()

        reading_progress = []
        for item in reading_list.get("items", []):
            enriched = dict(item)
            enriched["id"] = StudyProgressTracker.make_item_id("reading", selected_course, strategy_name, str(item.get("order", "")), item.get("title", ""))
            reading_progress.append(enriched)

        exam_progress = []
        for item in exam_priority.get("items", []):
            enriched = dict(item)
            enriched["id"] = StudyProgressTracker.make_item_id("exam", selected_course, strategy_name, str(item.get("rank", "")), item.get("title", ""))
            exam_progress.append(enriched)

        day_progress = []
        for item in daily_plan.get("days", []):
            enriched = dict(item)
            enriched["id"] = StudyProgressTracker.make_item_id("day", selected_course, strategy_name, str(item.get("day", "")), item.get("reading_title", ""))
            day_progress.append(enriched)

        focus_progress = []
        for item in focus_mode.get("blocks", []):
            enriched = dict(item)
            enriched["id"] = StudyProgressTracker.make_item_id("focus", selected_course, strategy_name, str(item.get("block", "")), item.get("title", ""))
            focus_progress.append(enriched)

        expected_items = []
        expected_items.extend({"id": item["id"], "label": item.get("title", "-")} for item in reading_progress)
        expected_items.extend({"id": item["id"], "label": item.get("title", "-")} for item in exam_progress)
        expected_items.extend({"id": item["id"], "label": item.get("reading_title", "-")} for item in day_progress)
        expected_items.extend({"id": item["id"], "label": item.get("title", "-")} for item in focus_progress)

        st.caption(f"İndeks kaynağı: {recommendations.get('index_source', '-')} | Son senkron: {recommendations.get('index_last_sync', '-')} | Strateji: {strategy_name}")

        top_cols = st.columns(4)
        with top_cols[0]:
            st.metric("Öneri", recommendations.get("result_count", 0))
        with top_cols[1]:
            st.metric("Seçili Konu", len(recommendations.get("selected_topics", [])))
        with top_cols[2]:
            st.metric("İndekslenen Yayın", publication_index.get("entry_count", 0))
        with top_cols[3]:
            st.metric("Plan Görevi", len(expected_items))

        plan_col, exam_col = st.columns(2)
        with plan_col:
            st.markdown("### Otomatik Okuma Listesi")
            for item in reading_progress:
                with st.container(border=True):
                    st.markdown(f"**{item.get('order', '-')}. {item.get('title', '-')}**")
                    st.caption(f"{item.get('staff_name', '-')} | {item.get('priority', '-')} | {item.get('stage', '-')}")
                    sync_progress_checkbox(selected_course, strategy_name, selected_topics, item["id"], item.get("title", "-"), key=f"progress_{item['id']}", meta={"type": "reading"})
            st.download_button(
                label="Okuma Listesini İndir",
                data=reading_list.get("text", "").encode("utf-8"),
                file_name=f"Okuma_Listesi_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="reading_list_download",
                use_container_width=True,
            )
        with exam_col:
            st.markdown("### Sınav Haftası Öncelikli 5 Yayın")
            for item in exam_progress:
                with st.container(border=True):
                    st.markdown(f"**{item.get('rank', '-')}. {item.get('title', '-')}**")
                    st.caption(f"{item.get('staff_name', '-')} | {item.get('focus', '-')} | {item.get('action', '-')}" )
                    sync_progress_checkbox(selected_course, strategy_name, selected_topics, item["id"], item.get("title", "-"), key=f"progress_{item['id']}", meta={"type": "exam"})
            st.download_button(
                label="Sınav Haftası Listesini İndir",
                data=exam_priority.get("text", "").encode("utf-8"),
                file_name=f"Sinav_Haftasi_5_Yayin_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="exam_priority_download",
                use_container_width=True,
            )

        strategy_col_left, strategy_col_right = st.columns(2)
        with strategy_col_left:
            st.markdown(f"### {strategy_plan.get('strategy_name', '-')}" )
            st.markdown(f"**Odak:** {strategy_plan.get('focus', '-')}" )
            st.markdown(f"**Tempo:** {strategy_plan.get('rhythm', '-')}" )
            st.markdown(f"**Hedef:** {strategy_plan.get('goal', '-')}" )
            st.markdown(f"**Önerilen süre:** {strategy_plan.get('recommended_minutes', 0)} dk")
        with strategy_col_right:
            st.markdown("### Stratejiye Göre Kritik Yayınlar")
            for item in strategy_plan.get("priority_items", []):
                st.markdown(f"**{item.get('rank', '-')}. {item.get('title', '-')}**")
                st.caption(f"{item.get('staff_name', '-')} | {item.get('focus', '-')} | {item.get('action', '-')}" )
            st.download_button(
                label="Strateji Planını İndir",
                data=strategy_plan.get("text", "").encode("utf-8"),
                file_name=f"Strateji_{strategy_plan.get('strategy_name', 'plan').replace(' ', '_')}_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="strategy_plan_download",
                use_container_width=True,
            )

        schedule_col, mode_col = st.columns(2)
        with schedule_col:
            st.markdown("### Günlük Çalışma Takvimi")
            for item in day_progress:
                with st.container(border=True):
                    st.markdown(f"**Gün {item.get('day', '-')}**")
                    st.caption(f"{item.get('warmup_minutes', 0)} dk ısınma | {item.get('core_minutes', 0)} dk ana blok | {item.get('recall_minutes', 0)} dk pekiştirme")
                    st.markdown(f"Ana yayın: {item.get('reading_title', '-')} | Öncelik: {item.get('priority_title', '-')}" )
                    sync_progress_checkbox(selected_course, strategy_name, selected_topics, item["id"], f"Gün {item.get('day', '-')} tamamlandı", key=f"progress_{item['id']}", meta={"type": "day"})
            st.download_button(
                label="Günlük Takvimi İndir",
                data=daily_plan.get("text", "").encode("utf-8"),
                file_name=f"Gunluk_Calisma_Takvimi_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="daily_plan_download",
                use_container_width=True,
            )
        with mode_col:
            st.markdown(f"### {focus_minutes} Dakikalık Mini Çalışma Modu")
            for block in focus_progress:
                with st.container(border=True):
                    st.markdown(f"**Blok {block.get('block', '-')} - {block.get('label', '-')}**")
                    st.caption(f"{block.get('minutes', 0)} dk | {block.get('staff_name', '-')} | {block.get('task', '-')}" )
                    st.markdown(block.get('title', '-'))
                    sync_progress_checkbox(selected_course, strategy_name, selected_topics, block["id"], f"Blok {block.get('block', '-')} tamamlandı", key=f"progress_{block['id']}", meta={"type": "focus"})
            st.download_button(
                label="Mini Çalışma Modunu İndir",
                data=focus_mode.get("text", "").encode("utf-8"),
                file_name=f"Mini_Calisma_Modu_{focus_minutes}dk_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="focus_mode_download",
                use_container_width=True,
            )

        progress_summary = StudyProgressTracker.summarize_progress(selected_course, strategy_name, selected_topics, expected_items)
        adaptive_next = StudyProgressTracker.build_next_day_adjustment(
            selected_course,
            strategy_name,
            selected_topics,
            progress_summary,
            reading_progress,
            exam_progress,
            focus_minutes,
        )
        recovery_plan = StudyProgressTracker.build_recovery_plan(
            selected_course,
            strategy_name,
            selected_topics,
            progress_summary,
            reading_progress,
            exam_progress,
            day_progress,
        )
        weekly_report = StudyProgressTracker.build_weekly_success_report(
            selected_course,
            strategy_name,
            selected_topics,
            expected_items,
        )

        progress_cols = st.columns(4)
        with progress_cols[0]:
            st.metric("Tamamlanan", progress_summary.get("completed", 0))
        with progress_cols[1]:
            st.metric("Toplam", progress_summary.get("total", 0))
        with progress_cols[2]:
            st.metric("İlerleme", f"%{progress_summary.get('rate', 0.0) * 100:.0f}")
        with progress_cols[3]:
            st.metric("Uyarlama", progress_summary.get("label", "-"))

        adaptive_col, adaptive_right = st.columns(2)
        with adaptive_col:
            st.markdown(f"### {adaptive_next.get('title', '-')}" )
            st.markdown(f"**Önerilen süre:** {adaptive_next.get('recommended_minutes', 0)} dk")
            for item in adaptive_next.get("items", []):
                st.markdown(f"- {item.get('title', '-')} | {item.get('staff_name', '-')}" )
            st.download_button(
                label="Sonraki Gün Uyarlamasını İndir",
                data=adaptive_next.get("text", "").encode("utf-8"),
                file_name=f"Uyarlanmis_Sonraki_Gun_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="adaptive_next_download",
                use_container_width=True,
            )
        with adaptive_right:
            st.markdown(f"### {recovery_plan.get('title', '-')}" )
            for item in recovery_plan.get("items", []):
                st.markdown(f"- {item.get('title', '-')} | {item.get('staff_name', '-')} | {item.get('action', '-')}" )
            st.download_button(
                label="Telafi Planını İndir",
                data=recovery_plan.get("text", "").encode("utf-8"),
                file_name=f"Telafi_Plani_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="recovery_plan_download",
                use_container_width=True,
            )

        weekly_col, rec_col = st.columns(2)
        with weekly_col:
            st.markdown(f"### {weekly_report.get('title', '-')}" )
            st.markdown(f"**Bu hafta tamamlanan:** {weekly_report.get('weekly_completed', 0)}")
            st.markdown(f"**Haftalık başarı oranı:** %{weekly_report.get('weekly_rate', 0.0) * 100:.0f}")
            for item_type, count in weekly_report.get("by_type", {}).items():
                st.markdown(f"- {item_type}: {count}")
            st.download_button(
                label="Haftalık Raporu İndir",
                data=weekly_report.get("text", "").encode("utf-8"),
                file_name=f"Haftalik_Basari_Raporu_{selected_course.replace(' ', '_')}.txt",
                mime="text/plain",
                key="weekly_report_download",
                use_container_width=True,
            )
        with rec_col:
            st.markdown("### Ders ve Konu Odaklı Yayın Önerileri")
            if not recommendations.get("results"):
                st.info("Seçtiğiniz ders ve konular için eşleşen yayın bulunamadı. Önce akademik veriyi yenileyin veya farklı konu seçin.")
            else:
                for index, item in enumerate(recommendations.get("results", []), start=1):
                    with st.container(border=True):
                        st.markdown(f"**{index}. {item.get('title', '-')}**")
                        st.markdown(f"{item.get('staff_name', '-')} | {item.get('category', '-')} | {item.get('scope', '-')}" )
                        if item.get("citation"):
                            st.caption(item.get("citation"))
                        tags = []
                        if item.get("course_matches"):
                            tags.append("Ders eşleşmeleri: " + ", ".join(item.get("course_matches", [])[:5]))
                        if item.get("topic_matches"):
                            tags.append("Konu eşleşmeleri: " + ", ".join(item.get("topic_matches", [])[:5]))
                        if tags:
                            st.markdown(" | ".join(tags))
                        st.markdown(f"**Öneri skoru:** {item.get('score', 0)}")
                        if item.get("url"):
                            st.markdown(f"[Yayına git]({item['url']})")

def render_schedule_tab() -> None:
    st.header("Ders Programı (PDF Müfredat)")
    pdf_path = SystemConfig.find_pdf_path()
    if pdf_path:
        st.success(f"PDF bulundu: {pdf_path}")
    else:
        st.warning("PDF bulunamadı. Yedek program gösteriliyor.")

    schedule = AcademicDatabase.extract_pdf_schedule()
    st.dataframe(schedule, use_container_width=True, hide_index=True)
    if pdf_path:
        with open(pdf_path, "rb") as handle:
            st.download_button(
                label="PDF'i İndir",
                data=handle.read(),
                file_name=pathlib.Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
            )


def render_curriculum_tab() -> None:
    st.header("Müfredat Odaklı Yerel Araştırma")
    curriculum = AcademicDatabase.get_curriculum_topics()
    selected_course = st.selectbox("Ders", list(curriculum.keys()))
    topics = curriculum[selected_course]
    selected_topics = st.multiselect("Konular", topics, default=topics[:3])
    depth = st.slider("Araştırma Derinliği", 1, 5, 3)

    if st.button("Yerel Müfredat Raporu Oluştur", type="primary", use_container_width=True):
        if not selected_topics:
            st.error("Lütfen en az bir konu seçin.")
            return
        report = build_curriculum_report(selected_course, selected_topics, depth)
        st.session_state["user_xp"] += len(selected_topics) * depth * 4
        st.download_button(
            label="Raporu İndir",
            data=report.encode("utf-8"),
            file_name=f"Mufredat_Raporu_{selected_course.replace(' ', '_')}.txt",
            mime="text/plain",
        )
        st.markdown(report)


def render_system_tab() -> None:
    st.header("Sistem Ayarları ve İstatistikler")
    notes = st.session_state["digitalized_notes"]
    total_notes = len(notes)
    total_words = sum(note.get("word_count", 0) for note in notes)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Toplam Dijital Not", total_notes)
        st.metric("Toplam Kelime", f"{total_words:,}")
        st.metric("Akademik XP", st.session_state["user_xp"])
        if notes:
            avg_quality = sum(note.get("quality_score", 0) for note in notes) / len(notes)
            st.metric("Ort. Kalite", f"{avg_quality:.1f}/100")
            ders_counts: dict[str, int] = {}
            for note in notes:
                ders = note.get("ders_adi", "Bilinmiyor")
                ders_counts[ders] = ders_counts.get(ders, 0) + 1
            fig = px.pie(values=list(ders_counts.values()), names=list(ders_counts.keys()), title="Derslere Göre Not Dağılımı")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.info(
            "\n".join(
                [
                    "Yerel çalışma ilkeleri",
                    "- API anahtarı yok",
                    "- Uzak LLM çağrısı yok",
                    "- Arşivleme JSON + Markdown ile yerel",
                    "- OCR: Tesseract tabanlı",
                ]
            )
        )
        if st.button("Tüm Notları Temizle", use_container_width=True):
            st.session_state["digitalized_notes"] = []
            st.success("Tüm notlar temizlendi.")
            st.rerun()
        if st.button("Tam Sıfırlama", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("Oturum sıfırlandı.")
            st.rerun()


def main() -> None:
    SystemConfig.set_page_config()
    SystemConfig.apply_css()
    init_session()
    storage = render_sidebar()

    notes_count = len(st.session_state["digitalized_notes"])
    xp = st.session_state["user_xp"]
    st.markdown(
        f"""
        <div class="main-header">
            <h1>LEKSİKOGRAF v18 | Yerel Akademik Platform</h1>
            <h3>Güvenli, modüler ve API anahtarsız çalışma sürümü</h3>
            <div style="margin-top: 15px; display: flex; justify-content: center; gap: 15px;">
                <div style="background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 20px;">
                    <strong>{notes_count} Dijital Not</strong>
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 20px;">
                    <strong>{xp} Akademik XP</strong>
                </div>
                <div style="background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 20px;">
                    <strong>YEREL OCR</strong>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(
        [
            "Dashboard",
            "Profesyonel OCR",
            "Akademik Kadro",
            "Akademik Kütüphane",
            "Ders Programı",
            "Müfredat Araştırma",
            "Sistem",
        ]
    )

    with tabs[0]:
        render_dashboard_tab()
    with tabs[1]:
        render_ocr_tab(storage)
    with tabs[2]:
        render_staff_tab()
    with tabs[3]:
        render_library_tab()
    with tabs[4]:
        render_schedule_tab()
    with tabs[5]:
        render_curriculum_tab()
    with tabs[6]:
        render_system_tab()


if __name__ == "__main__":
    main()

























