from __future__ import annotations

import os
import pathlib
from typing import Optional

import streamlit as st


class SystemConfig:
    COLORS = {
        "primary": "#800000",
        "secondary": "#1e3a8a",
        "accent": "#0ea5e9",
        "gold": "#fbbf24",
        "success": "#10b981",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "bg": "#f8fafc",
    }

    PDF_PATHS = [
        pathlib.Path.cwd() / "data" / "BTÜ_UTL_Müfredat_2025-2026.pdf",
        pathlib.Path.cwd() / "müfredat.pdf",
        pathlib.Path.cwd() / "data" / "müfredat.pdf",
    ]

    @classmethod
    def find_pdf_path(cls) -> Optional[str]:
        for path in cls.PDF_PATHS:
            if os.path.exists(path):
                return str(path)
        return None

    @staticmethod
    def default_notes_dir() -> str:
        return str((pathlib.Path.cwd() / "notes_archive").resolve())

    @staticmethod
    def academic_cache_path() -> str:
        return str((pathlib.Path.cwd() / ".cache" / "academic_cache.json").resolve())

    @staticmethod
    def study_progress_path() -> str:
        return str((pathlib.Path.cwd() / ".cache" / "study_progress.json").resolve())

    @staticmethod
    def set_page_config() -> None:
        st.set_page_config(
            page_title="Leksikograf v18 | Yerel Akademik Platform",
            layout="wide",
            page_icon="📝",
            initial_sidebar_state="expanded",
        )

    @staticmethod
    def apply_css() -> None:
        st.markdown(
            """
            <style>
                .stApp { background-color: #f8fafc; }
                .main-header {
                    background: linear-gradient(135deg, #800000 0%, #1e3a8a 100%);
                    padding: 2rem;
                    border-radius: 0 0 20px 20px;
                    color: white;
                    text-align: center;
                    margin-bottom: 2rem;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
                }
                .quality-badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 600;
                }
                .quality-excellent {
                    background: #10b98120;
                    color: #10b981;
                    border: 1px solid #10b981;
                }
                .quality-good {
                    background: #f59e0b20;
                    color: #f59e0b;
                    border: 1px solid #f59e0b;
                }
                .quality-fair {
                    background: #ef444420;
                    color: #ef4444;
                    border: 1px solid #ef4444;
                }
                .book {
                    min-width: 70px;
                    height: 190px;
                    writing-mode: vertical-rl;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    border-radius: 6px;
                    color: white;
                    box-shadow: 2px 4px 8px rgba(0,0,0,.25);
                }
                .easy { background: linear-gradient(135deg, #047857, #10b981); }
                .mid { background: linear-gradient(135deg, #1e3a8a, #3730a3); }
                .hard { background: linear-gradient(135deg, #7f1d1d, #991b1b); }
                .shelf {
                    display: flex;
                    gap: 16px;
                    overflow-x: auto;
                    padding: 20px;
                    background: #f5f3ef;
                    border-radius: 12px;
                    margin-bottom: 20px;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

