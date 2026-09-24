from __future__ import annotations

import base64
import csv
import html
import io
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
import streamlit as st

try:
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except Exception:
    go = None
    PLOTLY_AVAILABLE = False


CM_UNIT = "เซนติเมตร (cm)"
INCH_UNIT = "นิ้ว (inch)"
UNITS = [CM_UNIT, INCH_UNIT]
ROUND_DIGITS = 2
MAX_TOTAL_QUANTITY = 10000
ROLL_HISTORY_LIMIT = 5
PRESET_LIMIT = 20
ROLL_PREVIEW_PALETTE = [
    "#f2a33b", "#4c9bd6", "#77d18a", "#d686ff", "#ffcf8a",
    "#f06f64", "#7ed3d1", "#c9d45a", "#9ca3ff", "#f498c2",
    "#a3e635", "#38bdf8", "#fb7185", "#c084fc", "#facc15",
]
ROLL_PREVIEW_OVERFLOW_COLOR = "#d47f2a"
ROLL_PREVIEW_MAX_LENGTH_CM = 1200.0
ROLL_CUT_SECTION_LENGTH_CM = 260.0
APP_DATA_DIR = Path(__file__).resolve().parent / "sticker_layout_data"
APP_HISTORY_PATH = APP_DATA_DIR / "history.json"
APP_PRESET_PATH = APP_DATA_DIR / "presets.json"
APP_LOADING_VIDEO_PATH = Path(__file__).resolve().parent / "hugprint_loading_x2.mp4"
APP_LOADING_DURATION_SECONDS = 5.2

ROLL_LAYOUT_MODE_SMART = "เรียงประหยัดพื้นที่"
ROLL_LAYOUT_MODE_ORIGINAL = "เรียงตามลำดับเดิม"
ROLL_LAYOUT_MODE_PRODUCTION = "เรียงให้ดูง่ายสำหรับผลิต"
ROLL_LAYOUT_MODES = [
    ROLL_LAYOUT_MODE_SMART,
    ROLL_LAYOUT_MODE_PRODUCTION,
    ROLL_LAYOUT_MODE_ORIGINAL,
]

ROLL_AREA_CALC_MODE_FIXED_QUANTITY = "คำนวณจากจำนวนที่กรอก"
ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED = "คำนวณพื้นที่ หลายขนาด"
ROLL_AREA_CALC_MODE_TARGET_AREA = "โหมดพื้นที่เป้าหมาย (ปิดใช้งาน)"  # legacy only: ไม่แสดงใน UI แล้ว
ROLL_AREA_CALC_MODES = [
    ROLL_AREA_CALC_MODE_FIXED_QUANTITY,
    ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED,
]


def normalize_roll_area_calculation_mode(mode: str | None) -> str:
    """กันค่าโหมดเก่าจาก Session/Preset ที่ถูกปิดใช้งาน ไม่ให้หลุดเข้า logic หลัก"""
    return mode if mode in ROLL_AREA_CALC_MODES else ROLL_AREA_CALC_MODE_FIXED_QUANTITY
DEFAULT_TARGET_AREA_SQM = 1.0
DEFAULT_TARGET_MIN_MARK_COUNT = 2
DEFAULT_TARGET_MARK_STEP = 2
DEFAULT_TARGET_FORCE_MARK_PAIR = True

FIXED_MARK_WIDTH_CM = 57.0
FIXED_MARK_HEIGHT_CM = 41.0
FIXED_MARK_TOLERANCE_CM = 2.0
# ค่าเริ่มต้นสำหรับโหมด "คำนวณจากจำนวนที่กรอก" — ปรับได้จาก Sidebar
DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM = FIXED_MARK_TOLERANCE_CM

STICKER_GAP_PRESET_SMALL = "สติกเกอร์ขนาดเล็ก — 0.4 cm"
STICKER_GAP_PRESET_STANDARD = "สติกเกอร์ขนาดทั่วไป — 0.6 cm"
STICKER_GAP_PRESETS_CM = {
    STICKER_GAP_PRESET_SMALL: 0.40,
    STICKER_GAP_PRESET_STANDARD: 0.60,
}
DEFAULT_STICKER_GAP_PRESET = STICKER_GAP_PRESET_STANDARD
DEFAULT_STICKER_GAP_CM = STICKER_GAP_PRESETS_CM[DEFAULT_STICKER_GAP_PRESET]

QUANTITY_MARK_PRESET_HALF = "ครึ่ง ตรม. (2 มาร์ค)"
QUANTITY_MARK_PRESET_FULL = "1 ตรม. (4 มาร์ค)"
QUANTITY_MARK_PRESETS = {
    QUANTITY_MARK_PRESET_HALF: 2,
    QUANTITY_MARK_PRESET_FULL: 4,
}
DEFAULT_QUANTITY_MARK_PRESET = QUANTITY_MARK_PRESET_FULL
DEFAULT_QUANTITY_MARK_COUNT = QUANTITY_MARK_PRESETS[DEFAULT_QUANTITY_MARK_PRESET]

# ช่องไฟมาตรฐานเดิมยังคงชื่อ constant เดิมไว้ เพื่อให้ฟังก์ชันเก่าเรียกใช้ได้
FIXED_MARK_GAP_CM = DEFAULT_STICKER_GAP_CM
FIXED_MARK_GAP_MM = FIXED_MARK_GAP_CM * 10
# โหมด "คำนวณจากจำนวนที่กรอก" แบบแบ่งมาร์คผลิต
# - มาร์คกว้าง 57 cm
# - ความสูงมาร์ค Auto แต่ไม่ต่ำกว่า 41 cm
# - เรียงมาร์คเป็นคู่ 2 คอลัมน์
# - ช่องไฟระหว่างมาร์ค 4 cm
FIXED_QUANTITY_MARK_COLUMNS = 2
FIXED_QUANTITY_MARK_GAP_CM = 4.0
FIXED_QUANTITY_STRATEGY = "fixed_quantity_mark_pairs"
FIXED_MARK_AREA_PRESET_HALF = "ครึ่ง ตรม. (2 มาร์ค)"
FIXED_MARK_AREA_PRESET_FULL = "1 ตรม. (4 มาร์ค)"
FIXED_MARK_AREA_PRESET_CUSTOM = "กำหนดจำนวนมาร์คเอง"  # ใช้รองรับ Preset เก่าเท่านั้น ไม่แสดงใน UI แล้ว
FIXED_MARK_AREA_PRESETS = {
    FIXED_MARK_AREA_PRESET_HALF: 2,
    FIXED_MARK_AREA_PRESET_FULL: 4,
}
DEFAULT_FIXED_MARK_AREA_PRESET = FIXED_MARK_AREA_PRESET_FULL
DEFAULT_FIXED_MARK_COUNT = 4
MIXED_MARK_PREVIEW_PATCH_LIMIT = 450
MIXED_MARK_PRODUCTION_REPEAT_MODE = "จัด 1 มาร์คต้นแบบ แล้วคัดลอกซ้ำทุกมาร์ค"
MIXED_MARK_LAYOUT_STYLE_BLOCK = "เรียงเป็นบล็อก / เป็นระเบียบ (เร็ว)"
MIXED_MARK_LAYOUT_STYLE_COMPACT = "เรียงประหยัดพื้นที่ (ยังเป็นระเบียบ)"
MIXED_MARK_LAYOUT_STYLES = [MIXED_MARK_LAYOUT_STYLE_BLOCK, MIXED_MARK_LAYOUT_STYLE_COMPACT]

MIXED_RATIO_MODE_EQUAL = "เท่ากันทุก Size (1:1:1)"
MIXED_RATIO_MODE_SMALL_MORE = "เน้นชิ้นเล็ก — ชิ้นเล็กได้มากกว่า"
MIXED_RATIO_MODE_LARGE_MORE = "เน้นชิ้นใหญ่ — ชิ้นใหญ่ได้มากกว่า"
MIXED_RATIO_MODE_FIRST_MORE = "เน้น Size แรก — Size แรกได้มากกว่า"
MIXED_RATIO_MODE_CUSTOM = "กำหนดน้ำหนักเอง"
MIXED_RATIO_MODES = [
    MIXED_RATIO_MODE_EQUAL,
    MIXED_RATIO_MODE_SMALL_MORE,
    MIXED_RATIO_MODE_LARGE_MORE,
    MIXED_RATIO_MODE_FIRST_MORE,
    MIXED_RATIO_MODE_CUSTOM,
]
MIXED_RATIO_LEGACY_MAP = {
    "เท่ากันทุกขนาด": MIXED_RATIO_MODE_EQUAL,
    "ชิ้นเล็กได้มากกว่า": MIXED_RATIO_MODE_SMALL_MORE,
    "ชิ้นใหญ่ได้มากกว่า": MIXED_RATIO_MODE_LARGE_MORE,
    "ขนาดแรกได้มากกว่า": MIXED_RATIO_MODE_FIRST_MORE,
    "กำหนดเอง เช่น 2:1:1": MIXED_RATIO_MODE_CUSTOM,
    "กำหนดเอง เช่น 2:1": MIXED_RATIO_MODE_CUSTOM,
}
SHOW_PREVIEW_TEXT_ON_PIECES = False

MIXED_FILL_MODE_SMALLEST = "เติมพื้นที่เหลือด้วยชิ้นเล็กที่สุด"
MIXED_FILL_MODE_SELECTED = "เติมพื้นที่เหลือให้ Size ที่เลือก"
MIXED_FILL_MODE_RATIO_ORDER = "เติมพื้นที่เหลือตามอัตราส่วน"
MIXED_FILL_MODE_NONE = "ไม่เติมเพิ่ม"
MIXED_FILL_MODES = [
    MIXED_FILL_MODE_SMALLEST,
    MIXED_FILL_MODE_SELECTED,
    MIXED_FILL_MODE_RATIO_ORDER,
    MIXED_FILL_MODE_NONE,
]


def normalize_mixed_ratio_mode(mode: str | None) -> str:
    """ปรับค่าอัตราส่วนจาก Preset/Session เก่าให้ตรงกับตัวเลือกปัจจุบัน"""
    mode_text = str(mode or "").strip()
    mode_text = MIXED_RATIO_LEGACY_MAP.get(mode_text, mode_text)
    return mode_text if mode_text in MIXED_RATIO_MODES else MIXED_RATIO_MODE_EQUAL


def mixed_ratio_mode_help_text(mode: str | None) -> str:
    """คำอธิบายสั้น ๆ สำหรับช่วยเลือกโหมดอัตราส่วน"""
    mode = normalize_mixed_ratio_mode(mode)
    if mode == MIXED_RATIO_MODE_EQUAL:
        return "เหมาะกับงานที่ต้องการให้ทุก Size ได้จำนวนใกล้เคียงกันก่อนเติมพื้นที่เหลือ"
    if mode == MIXED_RATIO_MODE_SMALL_MORE:
        return "เหมาะกับงานที่อยากให้ Size เล็กได้จำนวนหลักมากกว่า เพราะใช้พื้นที่ต่อชิ้นน้อย"
    if mode == MIXED_RATIO_MODE_LARGE_MORE:
        return "เหมาะกับงานที่ต้องการดัน Size ใหญ่ให้ได้จำนวนมากขึ้นก่อน Size อื่น"
    if mode == MIXED_RATIO_MODE_FIRST_MORE:
        return "เหมาะกับงานที่ Size แรกเป็นตัวหลัก เช่น ลูกค้าอยากได้ Size แรกมากกว่า Size อื่น"
    if mode == MIXED_RATIO_MODE_CUSTOM:
        return "กำหนดน้ำหนักในแต่ละ Size ด้านล่าง เช่น น้ำหนัก 3, 1, 1 = Size แรกมากกว่า"
    return "เลือกอัตราส่วนตั้งต้น แล้วระบบจะเติมพื้นที่เหลือตามตัวเลือกด้านล่าง"


DEFAULT_MIXED_MARK_GAP_CM = DEFAULT_STICKER_GAP_CM
# เก็บค่า MM ไว้เพื่อรองรับ Preset/Session เก่าที่บันทึกด้วย key เดิม
DEFAULT_MIXED_MARK_GAP_MM = DEFAULT_MIXED_MARK_GAP_CM * 10
DEFAULT_MIXED_MARK_PREVIEW_MARKS = 2


def is_fixed_mark_calculation_mode(mode: str | None = None) -> bool:
    """ตรวจว่าโหมดปัจจุบันเป็นกลุ่มมาร์ค 57×41 หรือไม่"""
    current_mode = mode or st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)
    return current_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED


PAGE_QUANTITY = "คำนวณจำนวนสติกเกอร์ต่อวัสดุพิมพ์"
# Legacy page name: kept for old Session/Preset compatibility, but no longer shown as a main menu button.
PAGE_AREA = "คำนวณพื้นที่ตามหน้ากว้างม้วน และแสดงตัวอย่างชิ้นงาน"
# แยก 2 โหมดเดิมของหน้า PAGE_AREA ออกมาเป็นเมนูหลักตามที่ต้องการ
PAGE_AREA_FIXED_QUANTITY = ROLL_AREA_CALC_MODE_FIXED_QUANTITY
PAGE_AREA_FIXED_MARK_MIXED = ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED
PAGE_QUICK = "คำนวณด่วนขนาดและจำนวน"

AREA_CALCULATOR_MAIN_PAGES = (
    PAGE_AREA,  # legacy only
    PAGE_AREA_FIXED_QUANTITY,
    PAGE_AREA_FIXED_MARK_MIXED,
)
MAIN_MENU_PAGES = (
    PAGE_QUANTITY,
    PAGE_AREA_FIXED_QUANTITY,
    PAGE_AREA_FIXED_MARK_MIXED,
)
AREA_MAIN_PAGE_TO_CALC_MODE = {
    PAGE_AREA_FIXED_QUANTITY: ROLL_AREA_CALC_MODE_FIXED_QUANTITY,
    PAGE_AREA_FIXED_MARK_MIXED: ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED,
}


def is_area_calculator_page(page: str | None = None) -> bool:
    current_page = page or st.session_state.get("selected_page", PAGE_QUANTITY)
    return current_page in AREA_CALCULATOR_MAIN_PAGES


def get_area_calc_mode_from_main_page(page: str | None = None) -> str | None:
    current_page = page or st.session_state.get("selected_page", PAGE_QUANTITY)
    return AREA_MAIN_PAGE_TO_CALC_MODE.get(current_page)


def sync_area_calc_mode_from_main_page() -> None:
    """ล็อกโหมดคำนวณพื้นที่ให้ตรงกับเมนูหลักที่เลือก"""
    locked_mode = get_area_calc_mode_from_main_page()
    if locked_mode:
        st.session_state["roll_area_calculation_mode"] = locked_mode


def normalize_selected_main_page() -> None:
    """กัน Session/Preset เก่าที่เคยเก็บ PAGE_AREA รวมไว้ ให้ย้ายไปเมนูย่อยใหม่อัตโนมัติ"""
    selected_page = st.session_state.get("selected_page", PAGE_QUANTITY)
    if selected_page == PAGE_AREA:
        current_mode = normalize_roll_area_calculation_mode(
            st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)
        )
        st.session_state["selected_page"] = (
            PAGE_AREA_FIXED_MARK_MIXED
            if current_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED
            else PAGE_AREA_FIXED_QUANTITY
        )
        sync_area_calc_mode_from_main_page()
        return

    # เมนูคำนวณด่วนถูกยุบออกจากเมนูหลักแล้ว
    # หาก Session เก่ายังชี้มาหน้านี้ ให้ย้ายกลับไปหน้า “คำนวณจากจำนวนที่กรอก” ซึ่งเป็นฟังก์ชันหลักแทน
    if selected_page == PAGE_QUICK:
        st.session_state["selected_page"] = PAGE_AREA_FIXED_QUANTITY
        sync_area_calc_mode_from_main_page()
        return

    if selected_page not in MAIN_MENU_PAGES:
        st.session_state["selected_page"] = PAGE_QUANTITY
        return

    sync_area_calc_mode_from_main_page()

QUICK_MARK_MODE_OFF = "ไม่คำนวณมาร์ค"
QUICK_MARK_MODE_ON = "คำนวณมาร์ค"
QUICK_MARK_MODES = [QUICK_MARK_MODE_OFF, QUICK_MARK_MODE_ON]

QUICK_SHAPE_CIRCLE = "วงกลม"
QUICK_SHAPE_RECTANGLE = "สี่เหลี่ยม"
QUICK_SHAPE_DIECUT = "ไดคัทรูปทรงอิสระ"
QUICK_SHAPES = [
    QUICK_SHAPE_CIRCLE,
    QUICK_SHAPE_RECTANGLE,
    QUICK_SHAPE_DIECUT,
]

MODE_EASY = "โหมดง่าย"
MODE_DETAIL = "โหมดละเอียด"
CUSTOM_PRESET = "กำหนดเอง"

ROLL_WIDTH_PRESETS_CM = {
    # ค่าด้านขวาคือหน้าพิมพ์ที่ใช้คำนวณจริง
    # ค่าเริ่มต้นใช้หน้าพิมพ์ 120 cm ตามงานผลิตหลัก
    "หน้าพิมพ์ 120 (หน้าจริง 127cm)": 120.0,
    "หน้าพิมพ์ 130 (หน้าจริง 137cm)": 130.0,
    "หน้าพิมพ์ 152 cm": 152.0,
}
DEFAULT_ROLL_WIDTH_PRESET = "หน้าพิมพ์ 120 (หน้าจริง 127cm)"
APP_VERSION_LABEL = "v124-3-main-menu-no-quick-20260620"

SHEET_SIZE_PRESETS_CM = {
    CUSTOM_PRESET: None,
    "A4 แนวตั้ง": (21.0, 29.7),
    "A3 แนวตั้ง": (29.7, 42.0),
    "Mark 57 x 41 cm": (57.0, 41.0),
    "Mark 60 x 40 cm": (60.0, 40.0),
    "Mark 127 x 100 cm": (127.0, 100.0),
}

THAI_FONT_REGULAR_PROP = None
THAI_FONT_BOLD_PROP = None


# =========================================================
# Persistent storage helpers
# =========================================================
def ensure_app_data_dir() -> None:
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def load_json_file(path: Path, default):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def save_json_file(path: Path, data) -> bool:
    try:
        ensure_app_data_dir()
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        # ไม่ให้ระบบคำนวณล่มเพราะเขียนไฟล์ไม่ได้ แต่ต้องแจ้งผู้ใช้ว่า Preset/History อาจไม่ถูกบันทึก
        try:
            st.session_state["last_storage_error"] = f"บันทึกไฟล์ {path.name} ไม่สำเร็จ: {exc}"
        except Exception:
            pass
        return False


def load_persistent_history() -> dict:
    data = load_json_file(APP_HISTORY_PATH, {})
    if not isinstance(data, dict):
        data = {}
    return {
        "quantity_history": list(data.get("quantity_history", []))[:ROLL_HISTORY_LIMIT],
        "roll_history": list(data.get("roll_history", []))[:ROLL_HISTORY_LIMIT],
        "last_quantity_history_signature": data.get("last_quantity_history_signature", ""),
        "last_roll_history_signature": data.get("last_roll_history_signature", ""),
    }


def save_persistent_history() -> bool:
    data = {
        "quantity_history": list(st.session_state.get("quantity_history", []))[:ROLL_HISTORY_LIMIT],
        "roll_history": list(st.session_state.get("roll_history", []))[:ROLL_HISTORY_LIMIT],
        "last_quantity_history_signature": st.session_state.get("last_quantity_history_signature", ""),
        "last_roll_history_signature": st.session_state.get("last_roll_history_signature", ""),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return save_json_file(APP_HISTORY_PATH, data)


def load_user_presets() -> dict:
    data = load_json_file(APP_PRESET_PATH, {"quantity": {}, "roll": {}})
    if not isinstance(data, dict):
        data = {"quantity": {}, "roll": {}}
    quantity = data.get("quantity", {}) if isinstance(data.get("quantity", {}), dict) else {}
    roll = data.get("roll", {}) if isinstance(data.get("roll", {}), dict) else {}
    return {"quantity": quantity, "roll": roll}


def save_user_presets(presets: dict) -> bool:
    return save_json_file(APP_PRESET_PATH, presets)


def fig_to_png_bytes(fig: plt.Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_data(show_spinner=False)
def load_startup_video_data_uri(video_path: str) -> str:
    """อ่านไฟล์ loading video แล้วแปลงเป็น Data URI สำหรับ overlay หน้าเว็บ"""
    path = Path(video_path)

    if not path.exists():
        st.error(f"ไม่พบไฟล์วิดีโอ Loading: {path}")
        return ""

    if path.stat().st_size <= 0:
        st.error(f"ไฟล์วิดีโอว่างหรือเสีย: {path}")
        return ""

    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception as exc:
        st.error(f"อ่านไฟล์วิดีโอ Loading ไม่สำเร็จ: {exc}")
        return ""

    return f"data:video/mp4;base64,{encoded}"


def inject_startup_loading_overlay(force_show: bool = False) -> None:
    """แสดงวิดีโอ Loading เต็มหน้าจอตอนเข้าเว็บ

    force_show=True ใช้ตอนทดสอบ เพื่อให้เห็นวิดีโอทุกครั้งหลัง Streamlit rerun
    force_show=False ใช้งานจริง ให้แสดงแค่ครั้งแรกของ browser session
    """
    if force_show:
        st.session_state.pop("startup_loading_overlay_shown", None)

    if st.session_state.get("startup_loading_overlay_shown"):
        return

    video_uri = load_startup_video_data_uri(str(APP_LOADING_VIDEO_PATH))
    if not video_uri:
        return

    hide_delay = float(APP_LOADING_DURATION_SECONDS)

    st.markdown(
        f"""
        <style>
        @keyframes hugprintLoaderFadeOut {{
            0% {{ opacity: 1; visibility: visible; }}
            82% {{ opacity: 1; visibility: visible; }}
            100% {{ opacity: 0; visibility: hidden; pointer-events: none; }}
        }}

        .hugprint-startup-loader {{
            position: fixed;
            inset: 0;
            z-index: 2147483647;
            width: 100vw;
            height: 100vh;
            background: #020617;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            animation: hugprintLoaderFadeOut {hide_delay:.2f}s ease forwards;
        }}

        .hugprint-startup-loader video {{
            width: 100vw;
            height: 100vh;
            object-fit: cover;
            display: block;
        }}

        .hugprint-startup-loader::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 50% 50%, transparent 45%, rgba(2, 6, 23, .38) 100%);
            pointer-events: none;
        }}
        </style>

        <div class="hugprint-startup-loader" aria-label="Loading HUGPRINT app">
            <video autoplay muted playsinline preload="auto">
                <source src="{video_uri}" type="video/mp4">
            </video>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.session_state["startup_loading_overlay_shown"] = True


# =========================================================
# Font / Format helpers
# =========================================================
def configure_matplotlib_fonts() -> None:
    """ตั้งค่า font ของ matplotlib ให้รองรับภาษาไทยในภาพ preview
    
    ใช้ session_state cache ผลลัพธ์ไว้ ไม่ต้องวน loop หาฟอนต์ทุก rerun
    """
    global THAI_FONT_REGULAR_PROP, THAI_FONT_BOLD_PROP

    # ถ้าเคย configure แล้วในรอบนี้ ใช้ค่าเดิมได้เลย
    if st.session_state.get("_matplotlib_fonts_configured"):
        THAI_FONT_REGULAR_PROP = st.session_state.get("_thai_font_regular")
        THAI_FONT_BOLD_PROP = st.session_state.get("_thai_font_bold")
        return

    font_pairs = [
        # Windows fallback: เหมาะกับการรัน Streamlit บนเครื่องออฟฟิศ
        (
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
        ),
        (
            "C:/Windows/Fonts/leelawui.ttf",
            "C:/Windows/Fonts/leelauib.ttf",
        ),
        (
            "C:/Windows/Fonts/angsa.ttf",
            "C:/Windows/Fonts/angsab.ttf",
        ),
        # macOS fallback
        (
            "/System/Library/Fonts/Supplemental/Thonburi.ttc",
            "/System/Library/Fonts/Supplemental/Thonburi Bold.ttf",
        ),
        # Linux / Streamlit Cloud fallback
        (
            "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/noto/NotoSansThaiUI-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansThaiUI-Bold.ttf",
        ),
        (
            "/usr/share/fonts/opentype/tlwg/Garuda.otf",
            "/usr/share/fonts/opentype/tlwg/Garuda-Bold.otf",
        ),
    ]

    THAI_FONT_REGULAR_PROP = None
    THAI_FONT_BOLD_PROP = None

    for regular_path, bold_path in font_pairs:
        try:
            font_manager.fontManager.addfont(regular_path)
            font_manager.fontManager.addfont(bold_path)
            regular_prop = font_manager.FontProperties(fname=regular_path)
            bold_prop = font_manager.FontProperties(fname=bold_path)
            rcParams["font.family"] = regular_prop.get_name()
            rcParams["axes.unicode_minus"] = False
            THAI_FONT_REGULAR_PROP = regular_prop
            THAI_FONT_BOLD_PROP = bold_prop
            # Cache ผลลัพธ์ไว้ใน session_state เพื่อไม่ต้องวน loop อีกในทุก rerun
            st.session_state["_matplotlib_fonts_configured"] = True
            st.session_state["_thai_font_regular"] = regular_prop
            st.session_state["_thai_font_bold"] = bold_prop
            return
        except Exception:
            continue

    st.session_state["_matplotlib_fonts_configured"] = True
    st.session_state["_thai_font_regular"] = None
    st.session_state["_thai_font_bold"] = None
    rcParams["axes.unicode_minus"] = False


def get_thai_font(bold: bool = False):
    if bold and THAI_FONT_BOLD_PROP is not None:
        return THAI_FONT_BOLD_PROP
    if THAI_FONT_REGULAR_PROP is not None:
        return THAI_FONT_REGULAR_PROP
    return None


def round2(value: float) -> float:
    return round(float(value), ROUND_DIGITS)


def round_number_value(key: str) -> None:
    if key in st.session_state:
        st.session_state[key] = round2(st.session_state[key])


def to_cm(value: float, unit: str) -> float:
    return round2(value * 2.54 if unit == INCH_UNIT else value)


def from_cm(value: float, unit: str) -> float:
    return round2(value / 2.54 if unit == INCH_UNIT else value)


def unit_label(unit: str) -> str:
    return "inch" if unit == INCH_UNIT else "cm"


def gap_preset_label_from_cm(gap_cm: float | int | None) -> str:
    """เลือก Preset ช่องไฟที่ใกล้ค่าปัจจุบันที่สุด และล็อกให้เหลือ 0.4/0.6 cm"""
    try:
        current_gap_cm = float(gap_cm)
    except Exception:
        return DEFAULT_STICKER_GAP_PRESET
    return min(
        STICKER_GAP_PRESETS_CM,
        key=lambda label: abs(STICKER_GAP_PRESETS_CM[label] - current_gap_cm),
    )


def gap_preset_label_from_value(value: float | int | None, unit: str) -> str:
    return gap_preset_label_from_cm(to_cm(float(value or 0), unit))


def quantity_mark_preset_label_from_count(mark_count: int | float | None) -> str:
    """เลือก Preset จำนวนมาร์คจากค่าปัจจุบัน โดยเหลือเฉพาะ 2 หรือ 4 มาร์ค"""
    try:
        current_mark_count = int(mark_count)
    except Exception:
        current_mark_count = DEFAULT_QUANTITY_MARK_COUNT
    return min(
        QUANTITY_MARK_PRESETS,
        key=lambda label: abs(QUANTITY_MARK_PRESETS[label] - current_mark_count),
    )


def render_gap_preset_selectbox(
    label: str,
    preset_key: str,
    value_key: str,
    unit: str,
    help_text: str | None = None,
) -> str:
    """แสดงตัวเลือกช่องไฟมาตรฐาน 2 แบบ แล้วอัปเดตค่าที่ใช้คำนวณให้ตรงหน่วยปัจจุบัน"""
    options = list(STICKER_GAP_PRESETS_CM.keys())
    if st.session_state.get(preset_key) not in options:
        current_gap_cm = to_cm(st.session_state.get(value_key, from_cm(DEFAULT_STICKER_GAP_CM, unit)), unit)
        st.session_state[preset_key] = gap_preset_label_from_cm(current_gap_cm)

    selected_preset = st.selectbox(label, options, key=preset_key, help=help_text)
    selected_gap_cm = STICKER_GAP_PRESETS_CM[selected_preset]
    st.session_state[value_key] = round2(from_cm(selected_gap_cm, unit))

    display_value = from_cm(selected_gap_cm, unit)
    st.caption(f"ใช้ช่องไฟ {selected_gap_cm:.1f} cm ({display_value:.2f} {unit_label(unit)})")
    return selected_preset


def render_quantity_mark_preset_selectbox() -> str:
    """แสดงตัวเลือกจำนวนมาร์คของหน้าคำนวณจำนวน ให้เหลือแค่ครึ่ง/หนึ่ง ตรม."""
    options = list(QUANTITY_MARK_PRESETS.keys())
    if st.session_state.get("quantity_mark_preset") not in options:
        st.session_state["quantity_mark_preset"] = quantity_mark_preset_label_from_count(
            st.session_state.get("marks_count", DEFAULT_QUANTITY_MARK_COUNT)
        )

    selected_preset = st.selectbox(
        "จำนวนมาร์ค",
        options,
        key="quantity_mark_preset",
        help="เลือกพื้นที่มาตรฐานแทนการกรอกจำนวนมาร์คเอง",
    )
    st.session_state["marks_count"] = QUANTITY_MARK_PRESETS[selected_preset]
    st.caption(f"{selected_preset} · ใช้คำนวณรวม {st.session_state['marks_count']} มาร์ค")
    return selected_preset


def sync_gap_and_mark_preset_keys() -> None:
    """ซิงก์ key ของ selectbox กับค่าคำนวณจริง เพื่อรองรับ Preset/Session เก่า"""
    st.session_state["quantity_gap_preset"] = gap_preset_label_from_value(
        st.session_state.get("gap", DEFAULT_STICKER_GAP_CM),
        st.session_state.get("option_unit", CM_UNIT),
    )
    st.session_state["roll_gap_preset"] = gap_preset_label_from_value(
        st.session_state.get("roll_gap", DEFAULT_STICKER_GAP_CM),
        st.session_state.get("area_unit", CM_UNIT),
    )
    st.session_state["mixed_mark_gap_preset"] = gap_preset_label_from_cm(
        st.session_state.get("mixed_mark_gap_cm", DEFAULT_MIXED_MARK_GAP_CM)
    )
    st.session_state["quantity_mark_preset"] = quantity_mark_preset_label_from_count(
        st.session_state.get("marks_count", DEFAULT_QUANTITY_MARK_COUNT)
    )


def format_piece_area(single_area_sqcm: float) -> str:
    single_area_sqm = single_area_sqcm / 10000
    if single_area_sqm >= 0.1:
        return f"{single_area_sqm:.2f} sq.m."
    if single_area_sqm >= 0.01:
        return f"{single_area_sqm:.3f} sq.m."
    return f"{single_area_sqcm:.0f} sq.cm."


def safe_preview_label(text: str, fallback: str, max_len: int = 22) -> str:
    """เตรียมชื่อสำหรับแสดงบน preview ให้รองรับภาษาไทยและไม่ยาวเกินกล่อง"""
    cleaned = (text or "").strip()
    if not cleaned:
        return fallback
    return cleaned[:max_len] + ("…" if len(cleaned) > max_len else "")


def roll_preview_color(item_index: int, overflow: bool = False) -> str:
    if overflow:
        return ROLL_PREVIEW_OVERFLOW_COLOR
    return ROLL_PREVIEW_PALETTE[item_index % len(ROLL_PREVIEW_PALETTE)]


def _size_color_signature(width_cm: float, height_cm: float) -> tuple[float, float]:
    """ใช้ขนาดจริงเป็น key สี: ขนาดเดียวกันต้องสีเดียวกัน แม้หมุน 90°"""
    first = round2(width_cm)
    second = round2(height_cm)
    return tuple(sorted((first, second)))


def build_size_color_map(items: list) -> dict[tuple[float, float], int]:
    """สร้าง map สีตามขนาด เพื่อไม่ให้ Size เดียวกันกระจายหลายสีใน Preview"""
    color_map: dict[tuple[float, float], int] = {}
    for item in items:
        signature = _size_color_signature(getattr(item, "width_cm", 0.0), getattr(item, "height_cm", 0.0))
        if signature not in color_map:
            color_map[signature] = len(color_map)
    return color_map


def preview_color_for_size(width_cm: float, height_cm: float, fallback_index: int = 0, overflow: bool = False, color_map: dict | None = None) -> str:
    if overflow:
        return ROLL_PREVIEW_OVERFLOW_COLOR
    if color_map:
        signature = _size_color_signature(width_cm, height_cm)
        if signature in color_map:
            return roll_preview_color(int(color_map[signature]), overflow=False)
    return roll_preview_color(fallback_index, overflow=False)


def build_roll_legend_entries(area_items: list, area_unit: str, max_items: int = 18) -> list[dict]:
    """สร้างรายการสรุปสีแบบ legend สำหรับ Preview และไฟล์ PNG"""
    entries: list[dict] = []
    color_map = build_size_color_map(area_items)
    for index, item in enumerate(area_items[:max_items]):
        entries.append({
            "name": safe_preview_label(item.name, f"Size {index + 1}", max_len=24),
            "color": preview_color_for_size(item.width_cm, item.height_cm, index, False, color_map),
            "detail": f"{item.shape} · {sticker_shape_dimension_text(item.shape, item.width_cm, item.height_cm, area_unit)} / {item.quantity:,} ชิ้น",
        })
    remaining = max(0, len(area_items) - max_items)
    if remaining:
        entries.append({
            "name": f"+{remaining:,} Size",
            "color": "#94a3b8",
            "detail": "รายการอื่น ๆ ดูได้ในตารางด้านล่าง",
        })
    return entries


def inject_premium_roll_preview_css() -> None:
    """CSS สำหรับ Preview/Legend โทน HUGPRINT แบบ Premium Production"""
    st.markdown(
        """
        <style>
        .preview-legend-panel {
            position: relative;
            background:
                radial-gradient(circle at top left, rgba(242,163,59,.24), transparent 34%),
                linear-gradient(145deg, rgba(2,6,23,.96), rgba(15,23,42,.92));
            border: 1px solid rgba(148,163,184,.22);
            border-radius: 24px;
            padding: 16px;
            margin: 10px 0 18px;
            box-shadow: 0 22px 54px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.06);
            overflow: hidden;
        }
        .preview-legend-panel::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
            background-size: 18px 18px;
            mask-image: linear-gradient(to bottom, rgba(0,0,0,.65), transparent 80%);
            pointer-events: none;
        }
        .preview-legend-title-row {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 12px;
        }
        .preview-legend-title {
            color: #f8fafc;
            font-weight: 950;
            font-size: 1.02rem;
            letter-spacing: -.01em;
        }
        .preview-legend-badge {
            color: #020617;
            background: linear-gradient(135deg, #facc15, #fb923c);
            font-weight: 900;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: .76rem;
            white-space: nowrap;
            box-shadow: 0 10px 24px rgba(251,146,60,.24);
        }
        .preview-legend-grid {
            position: relative;
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }
        .preview-legend-row {
            display: flex;
            gap: 10px;
            align-items: center;
            padding: 10px 10px;
            border-radius: 16px;
            background: rgba(255,255,255,.055);
            border: 1px solid rgba(148,163,184,.12);
            backdrop-filter: blur(8px);
            transition: transform .16s ease, background .16s ease, border-color .16s ease;
        }
        .preview-legend-row:hover {
            transform: translateY(-1px);
            background: rgba(255,255,255,.085);
            border-color: rgba(250,204,21,.28);
        }
        .preview-legend-dot-wrap {
            width: 28px;
            height: 28px;
            border-radius: 11px;
            background: rgba(255,255,255,.08);
            display: grid;
            place-items: center;
            flex: 0 0 auto;
        }
        .preview-legend-dot {
            width: 15px;
            height: 15px;
            border-radius: 5px;
            box-shadow: 0 0 18px currentColor;
            outline: 2px solid rgba(255,255,255,.12);
        }
        .preview-legend-text {
            min-width: 0;
        }
        .preview-legend-name {
            color: #e2e8f0;
            font-weight: 900;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .preview-legend-detail {
            color: #94a3b8;
            font-size: .82rem;
            margin-top: 3px;
            line-height: 1.25;
        }
        .preview-legend-footnote {
            position: relative;
            color: #64748b;
            font-size: .78rem;
            margin-top: 12px;
            padding-top: 10px;
            border-top: 1px solid rgba(148,163,184,.14);
        }
        .premium-preview-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin: 4px 0 12px;
        }
        .premium-preview-kpi {
            background: linear-gradient(145deg, rgba(15,23,42,.88), rgba(30,41,59,.72));
            border: 1px solid rgba(148,163,184,.16);
            border-radius: 18px;
            padding: 12px 14px;
            box-shadow: 0 14px 34px rgba(0,0,0,.18);
        }
        .premium-preview-kpi-label {
            color: #94a3b8;
            font-size: .78rem;
            font-weight: 750;
            margin-bottom: 3px;
        }
        .premium-preview-kpi-value {
            color: #f8fafc;
            font-size: 1.12rem;
            font-weight: 950;
            letter-spacing: -.02em;
        }
        .premium-preview-kpi.accent .premium-preview-kpi-value { color: #facc15; }
        @media (max-width: 900px) {
            .premium-preview-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_premium_roll_preview_kpis(layout: RollLayoutResult) -> None:
    """แถบสรุปด้านบน Preview ให้เห็นตัวเลขสำคัญก่อนดูรูป"""
    inject_premium_roll_preview_css()
    warning_class = " accent" if layout.overflow_count or layout.empty_area_percent > layout.waste_threshold_percent else ""
    st.markdown(
        f"""
        <div class="premium-preview-kpi-grid">
            <div class="premium-preview-kpi accent">
                <div class="premium-preview-kpi-label">จำนวนรวม</div>
                <div class="premium-preview-kpi-value">{layout.total_quantity:,} ชิ้น</div>
            </div>
            <div class="premium-preview-kpi">
                <div class="premium-preview-kpi-label">ความยาวเข้าม้วน</div>
                <div class="premium-preview-kpi-value">{layout.required_length_cm / 100:.2f} ม.</div>
            </div>
            <div class="premium-preview-kpi{warning_class}">
                <div class="premium-preview-kpi-label">พื้นที่ว่าง</div>
                <div class="premium-preview-kpi-value">{layout.empty_area_percent:.2f}%</div>
            </div>
            <div class="premium-preview-kpi">
                <div class="premium-preview-kpi-label">พื้นที่คิดเงิน</div>
                <div class="premium-preview-kpi-value">{layout.final_charge_area_sqm:.2f} ตรม.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_roll_preview_legend(area_items: list, area_unit: str, max_items: int = 14) -> None:
    """Legend แบบการ์ด Premium สำหรับสรุปสี Size สติกเกอร์"""
    inject_premium_roll_preview_css()
    entries = build_roll_legend_entries(area_items, area_unit, max_items=max_items)
    if not entries:
        return

    item_html = []
    for entry in entries:
        color = html.escape(entry["color"])
        item_html.append(
            f"""
            <div class="preview-legend-row">
                <div class="preview-legend-dot-wrap">
                    <span class="preview-legend-dot" style="background:{color}; color:{color};"></span>
                </div>
                <div class="preview-legend-text">
                    <div class="preview-legend-name">{html.escape(entry['name'])}</div>
                    <div class="preview-legend-detail">{html.escape(entry['detail'])}</div>
                </div>
            </div>
            """
        )

    total_qty = sum(max(0, int(getattr(item, "quantity", 0))) for item in area_items)
    total_sizes = len(area_items)

  

def metric_card(label: str, value: str, detail: str = "", accent: bool = False) -> None:
    # เพิ่ม metric-card เพื่อให้ CSS คุมขนาดกล่อง KPI ได้เท่ากันทุกใบ
    class_name = "summary-card metric-card accent-card" if accent else "summary-card metric-card"
    detail_html = f"<div class='metric-detail'>{detail}</div>" if detail else "<div class='metric-detail'>&nbsp;</div>"
    st.markdown(
        f"""
        <div class="{class_name}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge(text: str, level: str = "good") -> None:
    level_class = {
        "good": "status-pill good",
        "warn": "status-pill warn",
        "danger": "status-pill danger",
        "info": "status-pill info",
    }.get(level, "status-pill info")
    st.markdown(f'<div class="{level_class}">{text}</div>', unsafe_allow_html=True)


def strip_html_tags(value) -> str:
    """ล้าง HTML จากข้อความสรุปก่อนส่งออกไฟล์"""
    text = html.unescape(str(value))
    text = text.replace("<br>", " / ").replace("<br/>", " / ").replace("<br />", " / ")
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def table_rows_to_csv_bytes(rows: list[dict]) -> bytes:
    """สร้าง CSV พร้อม BOM เพื่อให้ Excel อ่านภาษาไทยได้ถูกต้อง"""
    if not rows:
        return "".encode("utf-8-sig")

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: strip_html_tags(row.get(key, "")) for key in fieldnames})
    return output.getvalue().encode("utf-8-sig")


def rows_to_plain_text(title: str, rows: list[dict]) -> str:
    lines = [title.strip(), ""]
    for row in rows:
        if "รายการ" in row and "ค่า" in row:
            lines.append(f"{strip_html_tags(row['รายการ'])}: {strip_html_tags(row['ค่า'])}")
        else:
            parts = [f"{key}: {strip_html_tags(value)}" for key, value in row.items()]
            lines.append(" | ".join(parts))
    return "\n".join(lines).strip() + "\n"


def render_compact_export_bar(title: str, rows: list[dict], file_prefix: str, extra_text: str = "", csv_rows: list[dict] = None) -> None:
    """แสดง export เป็นตัวเลือกเสริมแบบเบา ไม่แย่งพื้นที่คำนวณหลัก"""
    if not rows:
        return

    summary_text = extra_text.strip() or rows_to_plain_text(title, rows)
    csv_export_rows = csv_rows if csv_rows is not None else rows
    st.markdown(
        f"""
        <div class="compact-export-wrap">
            <div class="compact-export-title">Export</div>
            <div class="compact-export-note">{html.escape(title)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    export_cols = st.columns([0.46, 0.46, 5.0])
    with export_cols[0]:
        st.download_button(
            "CSV",
            data=table_rows_to_csv_bytes(csv_export_rows),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            key=f"download_{file_prefix}_csv",
            use_container_width=True,
        )
    with export_cols[1]:
        st.download_button(
            "TXT",
            data=summary_text.encode("utf-8-sig"),
            file_name=f"{file_prefix}_summary.txt",
            mime="text/plain",
            key=f"download_{file_prefix}_txt",
            use_container_width=True,
        )
    with export_cols[2]:
        st.caption("ตัวเลือกส่งออกไฟล์ — วางไว้ท้ายส่วน ไม่รบกวนการคำนวณ")


def set_action_feedback(message: str, kind: str = "info") -> None:
    """เก็บข้อความ feedback สั้น ๆ เพื่อแสดงหลัง user กดปุ่ม/เปลี่ยนค่า"""
    st.session_state["action_feedback"] = {
        "message": message,
        "kind": kind,
    }


def render_action_feedback() -> None:
    """แสดง toast แบบ custom แล้วล้างค่าออกในการ rerun ถัดไป"""
    feedback = st.session_state.pop("action_feedback", None)
    if not feedback:
        return

    message = html.escape(str(feedback.get("message", "อัปเดตแล้ว")))
    kind = html.escape(str(feedback.get("kind", "info")))
    st.markdown(
        f"""
        <div class="action-toast {kind}">
            <div class="action-toast-icon">✦</div>
            <div class="action-toast-text">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def notify_page_change() -> None:
    selected = st.session_state.get("selected_page", PAGE_QUANTITY)
    set_action_feedback(f"เปลี่ยนหน้าเป็น: {selected}", "page")


def set_main_page(page: str) -> None:
    """เปลี่ยนเมนูหลักจากปุ่มการ์ดด้านซ้าย โดยไม่กระทบ radio/checkbox ตัวอื่น"""
    st.session_state["selected_page"] = page
    sync_area_calc_mode_from_main_page()
    set_action_feedback(f"เปลี่ยนหน้าเป็น: {page}", "page")


def notify_quantity_mode_change() -> None:
    set_action_feedback(f"โหมดคำนวณจำนวน: {st.session_state.get('quantity_mode', MODE_EASY)}", "mode")


def notify_area_mode_change() -> None:
    set_action_feedback(f"โหมดคำนวณพื้นที่ม้วน: {st.session_state.get('area_mode', MODE_EASY)}", "mode")


def notify_sheet_preset_change() -> None:
    set_action_feedback(f"เลือก Preset วัสดุ: {st.session_state.get('sheet_size_preset', CUSTOM_PRESET)}", "preset")


def notify_roll_preset_change() -> None:
    set_action_feedback(f"เลือกหน้าพิมพ์: {st.session_state.get('roll_width_preset', '')}", "preset")


def notify_auto_rotate_change() -> None:
    state = "เปิด" if st.session_state.get("roll_auto_rotate", False) else "ปิด"
    set_action_feedback(f"Auto Rotate: {state}", "rotate")


def notify_roll_layout_mode_change() -> None:
    mode = st.session_state.get("roll_layout_mode", ROLL_LAYOUT_MODE_SMART)
    set_action_feedback(f"รูปแบบการเรียง: {mode}", "mode")


def notify_roll_area_calculation_mode_change() -> None:
    mode = st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)
    set_action_feedback(f"วิธีคำนวณ: {mode}", "mode")


def sync_mixed_mark_gap_legacy() -> None:
    """ซิงก์ key เก่าแบบ mm เพื่อให้ Preset เก่ายังอ่าน/เขียนได้ แต่ UI ใช้ cm เท่านั้น"""
    gap_cm = round2(max(0.0, float(st.session_state.get("mixed_mark_gap_cm", DEFAULT_MIXED_MARK_GAP_CM))))
    st.session_state["mixed_mark_gap_cm"] = gap_cm
    st.session_state["mixed_mark_gap_mm"] = round2(gap_cm * 10)


# =========================================================
# Dataclasses
# =========================================================
@dataclass(frozen=True)
class StickerPlacement:
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float
    rotated: bool
    overflow: bool


@dataclass(frozen=True)
class LayoutResult:
    total_per_mark: int
    columns: int
    rows: int
    sticker_width_cm: float
    sticker_height_cm: float
    orientation: str
    used_width_cm: float
    used_height_cm: float
    overflow_width_cm: float
    overflow_height_cm: float
    material_usage_percent: float
    placements: tuple[StickerPlacement, ...]
    normal_count: int
    rotated_count: int
    grid_summary: str
    layout_mode: str


@dataclass(frozen=True)
class StickerAreaItem:
    name: str
    shape: str
    width_cm: float
    height_cm: float
    quantity: int
    single_area_sqcm: float
    total_area_sqcm: float
    total_area_sqm: float
    charge_area_sqm: float
    charge_mode: str
    needs_face_charge: bool
    over_print_width: bool


@dataclass(frozen=True)
class RollStickerPlacement:
    name: str
    shape: str
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float
    item_index: int
    overflow: bool
    rotated: bool


@dataclass(frozen=True)
class RollLayoutResult:
    print_width_cm: float
    usable_width_cm: float
    gap_cm: float
    margin_left_cm: float
    margin_right_cm: float
    head_margin_cm: float
    tail_margin_cm: float
    total_quantity: int
    rows_count: int
    required_length_cm: float
    actual_area_sqcm: float
    actual_area_sqm: float
    roll_face_area_sqm: float
    charged_rule_area_sqm: float
    material_usage_percent: float
    empty_area_sqm: float
    empty_area_percent: float
    waste_threshold_percent: float
    charge_by_page_due_to_waste: bool
    final_charge_area_sqm: float
    placements: tuple[RollStickerPlacement, ...]
    preview_placements: tuple[RollStickerPlacement, ...]
    preview_limit: int
    overflow_count: int
    face_charge_names: tuple[str, ...]
    rotated_count: int
    auto_rotate_enabled: bool
    layout_mode: str = ROLL_LAYOUT_MODE_SMART
    strategy_name: str = ""
    # ใช้กับโหมดแบ่งเป็นมาร์คคู่จากจำนวนที่กรอก
    mark_boxes: tuple = tuple()
    mark_summary: dict | None = None


@dataclass(frozen=True)
class MixedMarkItem:
    name: str
    shape: str
    width_cm: float
    height_cm: float
    ratio: int
    item_id: int


@dataclass(frozen=True)
class MixedMarkPlacement:
    mark_index: int
    name: str
    shape: str
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float
    item_index: int
    rotated: bool
    overflow: bool


@dataclass(frozen=True)
class MixedMarkLayout:
    mark_count: int
    set_count: int
    total_quantity: int
    material_area_sqm: float
    tolerance_area_sqm: float
    total_piece_area_sqm: float
    usage_percent: float
    tolerance_usage_percent: float
    placements: tuple[MixedMarkPlacement, ...]
    item_quantities: dict
    item_piece_area_sqm: dict
    overflow_count: int
    rotated_count: int
    failed_set_count: int = 0
    per_mark_item_quantities: dict | None = None
    calculation_mode: str = "ratio"
    layout_style: str = MIXED_MARK_LAYOUT_STYLE_BLOCK
    gap_cm: float = FIXED_MARK_GAP_CM



# =========================================================
# Quick Calculator: ขนาด + จำนวน + เลือกคำนวณมาร์ค / ไม่คำนวณมาร์ค
# =========================================================
@dataclass(frozen=True)
class QuickCalcItem:
    item_id: int
    name: str
    shape: str
    width_cm: float
    height_cm: float
    quantity: int
    area_each_sqcm: float
    area_total_sqm: float


@dataclass(frozen=True)
class QuickMarkPlacement:
    mark_index: int
    item_index: int
    name: str
    shape: str
    x_cm: float
    y_cm: float
    width_cm: float
    height_cm: float
    rotated: bool
    overflow: bool


@dataclass(frozen=True)
class QuickMarkLayout:
    raw_mark_count: int
    even_mark_count: int
    total_quantity: int
    total_area_sqm: float
    mark_area_sqm: float
    placements: tuple[QuickMarkPlacement, ...]
    overflow_count: int
    gap_cm: float


def quick_item_keys(item_id: int) -> tuple[str, str, str, str, str]:
    return (
        f"quick_name_{item_id}",
        f"quick_shape_{item_id}",
        f"quick_width_{item_id}",
        f"quick_height_{item_id}",
        f"quick_qty_{item_id}",
    )


def set_quick_item_defaults(item_id: int) -> None:
    name_key, shape_key, width_key, height_key, qty_key = quick_item_keys(item_id)

    st.session_state.setdefault(name_key, f"Size {item_id}")
    st.session_state.setdefault(shape_key, QUICK_SHAPE_CIRCLE)
    st.session_state.setdefault(width_key, 10.0)
    st.session_state.setdefault(height_key, 10.0)
    st.session_state.setdefault(qty_key, 1)

    if st.session_state.get(shape_key) not in QUICK_SHAPES:
        st.session_state[shape_key] = QUICK_SHAPE_CIRCLE


def ensure_quick_calc_defaults() -> None:
    if "quick_item_ids" not in st.session_state or not st.session_state["quick_item_ids"]:
        st.session_state["quick_item_ids"] = [1]
        st.session_state["quick_next_id"] = 2

    st.session_state.setdefault("quick_unit", CM_UNIT)
    st.session_state.setdefault("quick_mark_mode", QUICK_MARK_MODE_OFF)
    st.session_state.setdefault("quick_gap_preset", DEFAULT_STICKER_GAP_PRESET)
    st.session_state.setdefault("quick_auto_rotate", True)
    st.session_state.setdefault("quick_preview_marks", 4)

    for item_id in st.session_state["quick_item_ids"]:
        set_quick_item_defaults(int(item_id))


def add_quick_item() -> None:
    item_id = int(st.session_state.get("quick_next_id", 1))
    st.session_state.setdefault("quick_item_ids", [])
    st.session_state["quick_item_ids"].append(item_id)
    st.session_state["quick_next_id"] = item_id + 1
    set_quick_item_defaults(item_id)
    set_action_feedback(f"เพิ่ม Size #{item_id} แล้ว", "add")


def remove_quick_item(item_id: int) -> None:
    item_ids = list(st.session_state.get("quick_item_ids", []))
    if len(item_ids) <= 1:
        set_action_feedback("ต้องเหลืออย่างน้อย 1 Size", "warn")
        return

    st.session_state["quick_item_ids"] = [
        current_id for current_id in item_ids if int(current_id) != int(item_id)
    ]

    for key in quick_item_keys(int(item_id)):
        st.session_state.pop(key, None)

    set_action_feedback(f"ลบ Size #{int(item_id)} แล้ว", "delete")


def reset_quick_items() -> None:
    for item_id in st.session_state.get("quick_item_ids", []):
        for key in quick_item_keys(int(item_id)):
            st.session_state.pop(key, None)

    st.session_state["quick_item_ids"] = [1]
    st.session_state["quick_next_id"] = 2
    set_quick_item_defaults(1)
    set_action_feedback("ล้างรายการคำนวณด่วนแล้ว", "reset")


def quick_piece_area_sqcm(shape: str, width_cm: float, height_cm: float) -> float:
    if shape == QUICK_SHAPE_CIRCLE:
        diameter_cm = width_cm
        return math.pi * (diameter_cm / 2) ** 2

    # สี่เหลี่ยม / ไดคัทรูปทรงอิสระ ใช้กรอบกว้าง x สูง
    return width_cm * height_cm


def quick_dimension_text(item: QuickCalcItem) -> str:
    if item.shape == QUICK_SHAPE_CIRCLE:
        return f"Ø {item.width_cm:.2f} cm"
    return f"{item.width_cm:.2f} × {item.height_cm:.2f} cm"

def sticker_shape_dimension_text(shape: str, width_cm: float, height_cm: float, unit: str = CM_UNIT) -> str:
    """ข้อความขนาดตามรูปทรง ใช้ซ้ำทุกหน้าที่มีการเลือกขนาด"""
    display_w = from_cm(width_cm, unit)
    display_h = from_cm(height_cm, unit)
    if shape == QUICK_SHAPE_CIRCLE:
        return f"Ø {display_w:.2f} {unit_label(unit)}"
    return f"{display_w:.2f} × {display_h:.2f} {unit_label(unit)}"


def normalize_sticker_shape(shape: str | None) -> str:
    shape_text = str(shape or "").strip()
    return shape_text if shape_text in QUICK_SHAPES else QUICK_SHAPE_RECTANGLE


def sync_circle_height(width_key: str, height_key: str, shape: str) -> None:
    """ถ้าเป็นวงกลม ให้ค่า height ตาม diameter เสมอ เพื่อไม่ให้ session เก่าทำให้กว้าง/สูงไม่เท่ากัน"""
    if normalize_sticker_shape(shape) == QUICK_SHAPE_CIRCLE:
        st.session_state[height_key] = round2(st.session_state.get(width_key, 0.0))


def collect_quick_items(unit: str) -> list[QuickCalcItem]:
    items: list[QuickCalcItem] = []

    for item_id in st.session_state.get("quick_item_ids", []):
        item_id = int(item_id)
        name_key, shape_key, width_key, height_key, qty_key = quick_item_keys(item_id)
        set_quick_item_defaults(item_id)

        name = str(st.session_state.get(name_key, f"Size {item_id}")).strip() or f"Size {item_id}"
        shape = st.session_state.get(shape_key, QUICK_SHAPE_CIRCLE)

        width_value = float(st.session_state.get(width_key, 0.0) or 0.0)
        height_value = float(st.session_state.get(height_key, 0.0) or 0.0)
        quantity = int(st.session_state.get(qty_key, 0) or 0)

        if shape == QUICK_SHAPE_CIRCLE:
            height_value = width_value

        width_cm = to_cm(width_value, unit)
        height_cm = to_cm(height_value, unit)

        if width_cm <= 0 or height_cm <= 0 or quantity <= 0:
            continue

        area_each_sqcm = quick_piece_area_sqcm(shape, width_cm, height_cm)
        area_total_sqm = (area_each_sqcm * quantity) / 10000

        items.append(
            QuickCalcItem(
                item_id=item_id,
                name=name,
                shape=shape,
                width_cm=round2(width_cm),
                height_cm=round2(height_cm),
                quantity=quantity,
                area_each_sqcm=round2(area_each_sqcm),
                area_total_sqm=round2(area_total_sqm),
            )
        )

    return items


def choose_quick_orientation(
    piece_width_cm: float,
    piece_height_cm: float,
    shape: str,
    x_cm: float,
    y_cm: float,
    mark_width_cm: float,
    mark_height_cm: float,
    auto_rotate: bool,
) -> tuple[float, float, bool] | None:
    candidates = [(piece_width_cm, piece_height_cm, False)]

    if auto_rotate and shape != QUICK_SHAPE_CIRCLE and abs(piece_width_cm - piece_height_cm) > 0.001:
        candidates.append((piece_height_cm, piece_width_cm, True))

    fitting = [
        candidate for candidate in candidates
        if x_cm + candidate[0] <= mark_width_cm + 0.001
        and y_cm + candidate[1] <= mark_height_cm + 0.001
    ]

    if not fitting:
        return None

    # เลือกแนวที่กินความสูงแถวน้อยกว่า
    return min(fitting, key=lambda value: (value[1], value[0]))


def build_quick_mark_layout(
    items: list[QuickCalcItem],
    gap_cm: float,
    auto_rotate: bool = True,
) -> QuickMarkLayout:
    mark_width_cm = FIXED_MARK_WIDTH_CM
    mark_height_cm = FIXED_MARK_HEIGHT_CM

    pieces: list[dict] = []
    for item_index, item in enumerate(items):
        pack_width_cm = item.width_cm
        pack_height_cm = item.width_cm if item.shape == QUICK_SHAPE_CIRCLE else item.height_cm

        for _ in range(max(0, int(item.quantity))):
            pieces.append(
                {
                    "item_index": item_index,
                    "name": item.name,
                    "shape": item.shape,
                    "width_cm": pack_width_cm,
                    "height_cm": pack_height_cm,
                }
            )

    pieces.sort(
        key=lambda piece: (
            max(piece["width_cm"], piece["height_cm"]),
            min(piece["width_cm"], piece["height_cm"]),
        ),
        reverse=True,
    )

    placements: list[QuickMarkPlacement] = []

    current_mark = 0
    x_cm = 0.0
    y_cm = 0.0
    row_height_cm = 0.0

    for piece in pieces:
        fit = choose_quick_orientation(
            piece["width_cm"],
            piece["height_cm"],
            piece["shape"],
            x_cm,
            y_cm,
            mark_width_cm,
            mark_height_cm,
            auto_rotate,
        )

        # ลองขึ้นแถวใหม่
        if fit is None and x_cm > 0:
            x_cm = 0.0
            y_cm += row_height_cm + gap_cm
            row_height_cm = 0.0

            fit = choose_quick_orientation(
                piece["width_cm"],
                piece["height_cm"],
                piece["shape"],
                x_cm,
                y_cm,
                mark_width_cm,
                mark_height_cm,
                auto_rotate,
            )

        # ลองขึ้นมาร์คใหม่
        if fit is None:
            current_mark += 1
            x_cm = 0.0
            y_cm = 0.0
            row_height_cm = 0.0

            fit = choose_quick_orientation(
                piece["width_cm"],
                piece["height_cm"],
                piece["shape"],
                x_cm,
                y_cm,
                mark_width_cm,
                mark_height_cm,
                auto_rotate,
            )

        # ชิ้นใหญ่เกินมาร์ค 57x41
        if fit is None:
            overflow_width_cm = piece["width_cm"]
            overflow_height_cm = piece["height_cm"]

            placements.append(
                QuickMarkPlacement(
                    mark_index=current_mark,
                    item_index=int(piece["item_index"]),
                    name=piece["name"],
                    shape=piece["shape"],
                    x_cm=0.0,
                    y_cm=0.0,
                    width_cm=overflow_width_cm,
                    height_cm=overflow_height_cm,
                    rotated=False,
                    overflow=True,
                )
            )

            current_mark += 1
            x_cm = 0.0
            y_cm = 0.0
            row_height_cm = 0.0
            continue

        placed_width_cm, placed_height_cm, rotated = fit

        placements.append(
            QuickMarkPlacement(
                mark_index=current_mark,
                item_index=int(piece["item_index"]),
                name=piece["name"],
                shape=piece["shape"],
                x_cm=round2(x_cm),
                y_cm=round2(y_cm),
                width_cm=round2(placed_width_cm),
                height_cm=round2(placed_height_cm),
                rotated=rotated,
                overflow=False,
            )
        )

        x_cm += placed_width_cm + gap_cm
        row_height_cm = max(row_height_cm, placed_height_cm)

    raw_mark_count = max((placement.mark_index for placement in placements), default=-1) + 1
    even_mark_count = raw_mark_count if raw_mark_count % 2 == 0 else raw_mark_count + 1

    total_quantity = sum(item.quantity for item in items)
    total_area_sqm = sum(item.area_total_sqm for item in items)
    mark_area_sqm = even_mark_count * FIXED_MARK_WIDTH_CM * FIXED_MARK_HEIGHT_CM / 10000
    overflow_count = sum(1 for placement in placements if placement.overflow)

    return QuickMarkLayout(
        raw_mark_count=raw_mark_count,
        even_mark_count=even_mark_count,
        total_quantity=total_quantity,
        total_area_sqm=round2(total_area_sqm),
        mark_area_sqm=round2(mark_area_sqm),
        placements=tuple(placements),
        overflow_count=overflow_count,
        gap_cm=round2(gap_cm),
    )


def build_quick_mark_preview_figure(
    layout: QuickMarkLayout,
    items: list[QuickCalcItem],
    max_preview_marks: int = 4,
) -> plt.Figure:
    mark_width_cm = FIXED_MARK_WIDTH_CM
    mark_height_cm = FIXED_MARK_HEIGHT_CM
    mark_gap_cm = 6.0

    preview_mark_count = min(max(1, int(max_preview_marks)), max(1, int(layout.even_mark_count)))
    columns = 2
    rows = math.ceil(preview_mark_count / columns)

    total_width_cm = columns * mark_width_cm + (columns - 1) * mark_gap_cm
    total_height_cm = rows * mark_height_cm + (rows - 1) * 10

    fig_width = 12
    fig_height = max(4, rows * 4.2)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")

    color_map = build_size_color_map(items)

    for mark_index in range(preview_mark_count):
        col = mark_index % columns
        row = mark_index // columns

        offset_x = col * (mark_width_cm + mark_gap_cm)
        offset_y = row * (mark_height_cm + 10)

        ax.add_patch(
            patches.Rectangle(
                (offset_x, offset_y),
                mark_width_cm,
                mark_height_cm,
                linewidth=1.4,
                edgecolor="#e5e7eb",
                facecolor="#1e293b",
                linestyle="--",
            )
        )

        ax.text(
            offset_x + 1.2,
            offset_y + 2.2,
            f"Mark {mark_index + 1}",
            color="#f8fafc",
            fontsize=9,
            fontproperties=get_thai_font(bold=True),
            va="top",
        )

    for placement in layout.placements:
        if placement.mark_index >= preview_mark_count:
            continue
        if placement.item_index < 0 or placement.item_index >= len(items):
            continue

        item = items[placement.item_index]
        col = placement.mark_index % columns
        row = placement.mark_index // columns

        offset_x = col * (mark_width_cm + mark_gap_cm)
        offset_y = row * (mark_height_cm + 10)

        color = preview_color_for_size(
            item.width_cm,
            item.height_cm,
            fallback_index=placement.item_index,
            overflow=placement.overflow,
            color_map=color_map,
        )

        piece_x = offset_x + placement.x_cm
        piece_y = offset_y + placement.y_cm

        if placement.shape == QUICK_SHAPE_CIRCLE:
            radius = placement.width_cm / 2
            ax.add_patch(
                patches.Circle(
                    (piece_x + radius, piece_y + radius),
                    radius=radius,
                    linewidth=0.7,
                    edgecolor="#ffffff",
                    facecolor=color,
                    alpha=0.88,
                )
            )
        else:
            ax.add_patch(
                patches.Rectangle(
                    (piece_x, piece_y),
                    placement.width_cm,
                    placement.height_cm,
                    linewidth=0.7,
                    edgecolor="#ffffff",
                    facecolor=color,
                    alpha=0.88,
                )
            )

        if placement.width_cm >= 5 and placement.height_cm >= 4:
            ax.text(
                piece_x + placement.width_cm / 2,
                piece_y + placement.height_cm / 2,
                safe_preview_label(item.name, f"S{placement.item_index + 1}", max_len=10),
                color="#020617",
                fontsize=6.5,
                ha="center",
                va="center",
                fontproperties=get_thai_font(bold=True),
            )

    ax.set_xlim(-1, total_width_cm + 1)
    ax.set_ylim(total_height_cm + 1, -1)
    ax.set_aspect("equal")
    ax.axis("off")

    return fig


def render_quick_calculator_page() -> None:
    render_action_feedback()
    st.markdown('<div class="page-motion-anchor"></div>', unsafe_allow_html=True)
    ensure_quick_calc_defaults()

    st.markdown(
        """
        <div class="page-hero">
            <div class="eyebrow">HUGPRINT QUICK CALC</div>
            <h1>คำนวณด่วนขนาดและจำนวน</h1>
            <p>กรอกขนาดและจำนวนเอง เลือกได้ว่าจะคำนวณมาร์คหรือคำนวณเฉพาะพื้นที่</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_cols = st.columns([1.2, 1.8, 1.2])
    with top_cols[0]:
        st.selectbox("หน่วย", UNITS, key="quick_unit")

    with top_cols[1]:
        st.radio(
            "วิธีคำนวณ",
            QUICK_MARK_MODES,
            key="quick_mark_mode",
            horizontal=True,
            help="เลือกไม่คำนวณมาร์ค = แสดงเฉพาะพื้นที่ / เลือกคำนวณมาร์ค = จัดลงมาร์ค 57×41 และปัดมาร์คคู่",
        )

    with top_cols[2]:
        st.button("↺ ล้างรายการ", on_click=reset_quick_items, use_container_width=True)

    st.markdown('<div class="section-title">รายการขนาด</div>', unsafe_allow_html=True)

    area_unit = st.session_state.get("quick_unit", CM_UNIT)
    area_unit_short = unit_label(area_unit)

    for item_id in list(st.session_state.get("quick_item_ids", [])):
        item_id = int(item_id)
        set_quick_item_defaults(item_id)

        name_key, shape_key, width_key, height_key, qty_key = quick_item_keys(item_id)

        with st.container(border=True):
            row_cols = st.columns([1.15, 1.2, 1.05, 1.05, 0.9, 0.55])

            with row_cols[0]:
                st.text_input("ชื่อ", key=name_key)

            with row_cols[1]:
                selected_shape = st.selectbox("รูปทรง", QUICK_SHAPES, key=shape_key)

            with row_cols[2]:
                width_label = "เส้นผ่านศูนย์กลาง" if selected_shape == QUICK_SHAPE_CIRCLE else "กว้าง"
                st.number_input(
                    f"{width_label} ({area_unit_short})",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                    key=width_key,
                    on_change=round_number_value,
                    args=(width_key,),
                )

            with row_cols[3]:
                if selected_shape == QUICK_SHAPE_CIRCLE:
                    st.caption("วงกลมใช้ค่าเดียว")
                    st.caption("กว้าง = สูง")
                else:
                    st.number_input(
                        f"สูง ({area_unit_short})",
                        min_value=0.0,
                        step=0.1,
                        format="%.2f",
                        key=height_key,
                        on_change=round_number_value,
                        args=(height_key,),
                    )

            with row_cols[4]:
                st.number_input(
                    "จำนวน",
                    min_value=0,
                    step=1,
                    key=qty_key,
                )

            with row_cols[5]:
                st.write("")
                st.write("")
                st.button(
                    "ลบ",
                    key=f"quick_remove_{item_id}",
                    on_click=remove_quick_item,
                    args=(item_id,),
                    disabled=len(st.session_state.get("quick_item_ids", [])) <= 1,
                    use_container_width=True,
                )

    st.button("➕ เพิ่ม Size", on_click=add_quick_item, use_container_width=True)

    items = collect_quick_items(area_unit)

    if not items:
        st.warning("กรุณากรอกขนาดและจำนวนอย่างน้อย 1 รายการ")
        return

    total_quantity = sum(item.quantity for item in items)
    total_area_sqm = sum(item.area_total_sqm for item in items)

    st.markdown('<div class="section-title">สรุปพื้นที่</div>', unsafe_allow_html=True)

    summary_cols = st.columns(4)
    with summary_cols[0]:
        metric_card("จำนวนรวม", f"{total_quantity:,} ชิ้น", "รวมทุก Size", accent=True)
    with summary_cols[1]:
        metric_card("จำนวน Size", f"{len(items):,} Size", "ตามรายการที่กรอก")
    with summary_cols[2]:
        metric_card("พื้นที่จริง", f"{total_area_sqm:.3f} ตรม.", "ยังไม่รวมการปัดมาร์ค")
    with summary_cols[3]:
        metric_card("โหมด", st.session_state.get("quick_mark_mode"), "เลือกได้ว่าจะคำนวณมาร์คหรือไม่")

    rows = []
    for item in items:
        rows.append(
            {
                "ชื่อ": item.name,
                "รูปทรง": item.shape,
                "ขนาด": quick_dimension_text(item),
                "จำนวน": f"{item.quantity:,}",
                "พื้นที่/ชิ้น": f"{item.area_each_sqcm:.2f} ตร.ซม.",
                "พื้นที่รวม": f"{item.area_total_sqm:.3f} ตรม.",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    mark_mode = st.session_state.get("quick_mark_mode", QUICK_MARK_MODE_OFF)

    if mark_mode == QUICK_MARK_MODE_OFF:
        st.info("ตอนนี้เลือก: ไม่คำนวณมาร์ค — ระบบแสดงเฉพาะพื้นที่จริงของชิ้นงาน")
        return

    st.markdown('<div class="section-title">ตั้งค่ามาร์ค</div>', unsafe_allow_html=True)

    mark_cols = st.columns([1.2, 1.2, 1.0])
    with mark_cols[0]:
        gap_preset = st.selectbox(
            "ช่องไฟระหว่างชิ้น",
            list(STICKER_GAP_PRESETS_CM.keys()),
            key="quick_gap_preset",
        )
        gap_cm = STICKER_GAP_PRESETS_CM[gap_preset]

    with mark_cols[1]:
        st.checkbox(
            "อนุญาตให้หมุน 90°",
            key="quick_auto_rotate",
            help="ใช้กับสี่เหลี่ยม / ไดคัทรูปทรงอิสระ เพื่อช่วยประหยัดพื้นที่",
        )

    with mark_cols[2]:
        st.number_input(
            "จำนวนมาร์คที่แสดง Preview",
            min_value=1,
            max_value=12,
            step=1,
            key="quick_preview_marks",
        )

    layout = build_quick_mark_layout(
        items=items,
        gap_cm=gap_cm,
        auto_rotate=bool(st.session_state.get("quick_auto_rotate", True)),
    )

    st.markdown('<div class="section-title">สรุปมาร์ค</div>', unsafe_allow_html=True)

    mark_summary_cols = st.columns(4)
    with mark_summary_cols[0]:
        metric_card("มาร์คที่ใช้จริง", f"{layout.raw_mark_count:,} มาร์ค", "ก่อนปัดมาร์คคู่", accent=True)
    with mark_summary_cols[1]:
        metric_card("ปัดเป็นมาร์คคู่", f"{layout.even_mark_count:,} มาร์ค", "1→2 / 3→4 / 5→6")
    with mark_summary_cols[2]:
        metric_card("พื้นที่ตามมาร์ค", f"{layout.mark_area_sqm:.3f} ตรม.", "57×41 cm ต่อมาร์ค")
    with mark_summary_cols[3]:
        usage_percent = (layout.total_area_sqm / layout.mark_area_sqm * 100) if layout.mark_area_sqm > 0 else 0
        metric_card("ใช้พื้นที่", f"{usage_percent:.2f}%", f"ช่องไฟ {layout.gap_cm:.1f} cm")

    if layout.overflow_count > 0:
        st.error(
            f"มีชิ้นงาน {layout.overflow_count:,} ชิ้นที่ใหญ่เกินมาร์ค 57×41 cm "
            "กรุณาตรวจสอบขนาด หรือเปลี่ยนไปคำนวณแบบหน้ากว้างม้วน"
        )

    fig = build_quick_mark_preview_figure(
        layout=layout,
        items=items,
        max_preview_marks=int(st.session_state.get("quick_preview_marks", 4)),
    )

    st.markdown('<div class="section-title">Preview การวางมาร์ค</div>', unsafe_allow_html=True)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


# =========================================================
# Quantity calculation history
# =========================================================
def clear_quantity_history() -> None:
    st.session_state["quantity_history"] = []
    st.session_state["last_quantity_history_signature"] = ""
    save_persistent_history()
    set_action_feedback("ล้างประวัติคำนวณจำนวนแล้ว", "reset")


def make_quantity_history_signature(
    layout: LayoutResult,
    sticker_width_cm: float,
    sticker_height_cm: float,
    sheet_width_cm: float,
    sheet_height_cm: float,
    gap_cm: float,
    tolerance_cm: float,
    marks_count: int,
) -> str:
    return "::".join(
        [
            f"sticker={sticker_width_cm:.2f}x{sticker_height_cm:.2f}",
            f"sheet={sheet_width_cm:.2f}x{sheet_height_cm:.2f}",
            f"gap={gap_cm:.2f}",
            f"tol={tolerance_cm:.2f}",
            f"marks={int(marks_count)}",
            f"layout={layout.layout_mode}",
            f"orientation={layout.orientation}",
            f"count={layout.total_per_mark}",
        ]
    )


def add_quantity_history_entry(
    layout: LayoutResult,
    sticker_width_cm: float,
    sticker_height_cm: float,
    sheet_width_cm: float,
    sheet_height_cm: float,
    gap_cm: float,
    tolerance_cm: float,
    marks_count: int,
    status_is_clean: bool,
) -> None:
    if layout.total_per_mark <= 0:
        return

    signature = make_quantity_history_signature(
        layout=layout,
        sticker_width_cm=sticker_width_cm,
        sticker_height_cm=sticker_height_cm,
        sheet_width_cm=sheet_width_cm,
        sheet_height_cm=sheet_height_cm,
        gap_cm=gap_cm,
        tolerance_cm=tolerance_cm,
        marks_count=marks_count,
    )
    if st.session_state.get("last_quantity_history_signature") == signature:
        return

    total_all_marks = layout.total_per_mark * int(marks_count)
    st.session_state["last_quantity_history_signature"] = signature
    history = list(st.session_state.get("quantity_history", []))
    history.insert(
        0,
        {
            "เวลา": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "สติกเกอร์": f"{sticker_width_cm:.2f} x {sticker_height_cm:.2f} cm",
            "วัสดุพิมพ์": f"{sheet_width_cm:.2f} x {sheet_height_cm:.2f} cm",
            "มาร์ค": f"{int(marks_count):,}",
            "ต่อมาร์ค": f"{layout.total_per_mark:,}",
            "รวมทั้งหมด": f"{total_all_marks:,}",
            "ทิศทาง": layout.orientation,
            "รูปแบบ": strip_html_tags(layout.grid_summary),
            "ใช้พื้นที่": f"{layout.material_usage_percent:.2f}%",
            "หมุน": f"{layout.rotated_count:,}",
            "สถานะ": "อยู่ในขอบ" if status_is_clean else "อยู่ในระยะอนุโลม",
            "ช่องไฟ": f"{gap_cm:.2f} cm",
            "อนุโลม": f"{tolerance_cm:.2f} cm",
            "_signature": signature,
        },
    )
    st.session_state["quantity_history"] = history[:ROLL_HISTORY_LIMIT]
    save_persistent_history()


def render_quantity_history() -> None:
    history = list(st.session_state.get("quantity_history", []))
    st.markdown('<div class="section-title">ประวัติคำนวณจำนวนล่าสุด</div>', unsafe_allow_html=True)
    if not history:
        st.caption("ยังไม่มีประวัติคำนวณจำนวนในรอบการใช้งานนี้")
        return

    display_rows = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in history[:ROLL_HISTORY_LIMIT]
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)
    hist_cols = st.columns([0.85, 0.95, 3.2])
    with hist_cols[0]:
        st.button("ล้างประวัติ", key="clear_quantity_history_button", on_click=clear_quantity_history, use_container_width=True)
    with hist_cols[1]:
        st.download_button(
            "CSV",
            data=table_rows_to_csv_bytes(display_rows),
            file_name="quantity_history.csv",
            mime="text/csv",
            key="download_quantity_history_csv",
            use_container_width=True,
        )
    with hist_cols[2]:
        st.caption(f"เก็บถาวร 5 ครั้งล่าสุดในไฟล์ {APP_HISTORY_PATH.name} — รีสตาร์ทแอปแล้วโหลดกลับได้")


# =========================================================
# Roll calculation history
# =========================================================
def clear_roll_history() -> None:
    st.session_state["roll_history"] = []
    st.session_state["last_roll_history_signature"] = ""
    save_persistent_history()
    set_action_feedback("ล้างประวัติการคำนวณแล้ว", "reset")


def compact_area_items_label(area_items: list[StickerAreaItem], limit: int = 3) -> str:
    labels = []
    for item in area_items[:limit]:
        labels.append(f"{item.name} {item.width_cm:.0f}x{item.height_cm:.0f}cm x{item.quantity}")
    if len(area_items) > limit:
        labels.append(f"+{len(area_items) - limit} Size")
    return " / ".join(labels) if labels else "ไม่มีรายการ"


def make_roll_history_signature(
    area_items: list[StickerAreaItem],
    layout: RollLayoutResult,
    layout_mode: str,
    print_width_cm: float,
    gap_cm: float,
    margin_left_cm: float,
    margin_right_cm: float,
    head_margin_cm: float,
    tail_margin_cm: float,
    auto_rotate_enabled: bool,
) -> str:
    item_part = "|".join(
        f"{item.name}:{item.width_cm:.2f}x{item.height_cm:.2f}:{item.quantity}" for item in area_items
    )
    return "::".join(
        [
            layout_mode,
            f"w={print_width_cm:.2f}",
            f"gap={gap_cm:.2f}",
            f"m={margin_left_cm:.2f},{margin_right_cm:.2f},{head_margin_cm:.2f},{tail_margin_cm:.2f}",
            f"auto={int(auto_rotate_enabled)}",
            f"len={layout.required_length_cm:.2f}",
            f"area={layout.roll_face_area_sqm:.4f}",
            item_part,
        ]
    )


def add_roll_history_entry(
    area_items: list[StickerAreaItem],
    layout: RollLayoutResult,
    baseline_layout: RollLayoutResult,
    savings_percent: float,
    layout_mode: str,
    print_width_cm: float,
    gap_cm: float,
    margin_left_cm: float,
    margin_right_cm: float,
    head_margin_cm: float,
    tail_margin_cm: float,
    auto_rotate_enabled: bool,
) -> None:
    if not area_items or layout.total_quantity <= 0:
        return

    signature = make_roll_history_signature(
        area_items=area_items,
        layout=layout,
        layout_mode=layout_mode,
        print_width_cm=print_width_cm,
        gap_cm=gap_cm,
        margin_left_cm=margin_left_cm,
        margin_right_cm=margin_right_cm,
        head_margin_cm=head_margin_cm,
        tail_margin_cm=tail_margin_cm,
        auto_rotate_enabled=auto_rotate_enabled,
    )
    if st.session_state.get("last_roll_history_signature") == signature:
        return

    st.session_state["last_roll_history_signature"] = signature
    history = list(st.session_state.get("roll_history", []))
    history.insert(
        0,
        {
            "เวลา": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "โหมดเรียง": layout_mode,
            "หน้าพิมพ์": f"{print_width_cm:.2f} cm",
            "รายการ": compact_area_items_label(area_items),
            "จำนวน": f"{layout.total_quantity:,}",
            "ความยาวม้วน": f"{layout.required_length_cm / 100:.2f} ม.",
            "พื้นที่หน้าม้วน": f"{layout.roll_face_area_sqm:.2f} ตรม.",
            "พื้นที่คิดเงิน": f"{layout.final_charge_area_sqm:.2f} ตรม.",
            "พื้นที่ว่าง": f"{layout.empty_area_percent:.2f}%",
            "ประหยัด": f"{max(0.0, savings_percent):.2f}%",
            "หมุน": f"{layout.rotated_count:,}",
            "กลยุทธ์": roll_strategy_display_name(layout.strategy_name),
            "_signature": signature,
        },
    )
    st.session_state["roll_history"] = history[:ROLL_HISTORY_LIMIT]
    save_persistent_history()


def render_roll_history() -> None:
    history = list(st.session_state.get("roll_history", []))
    st.markdown('<div class="section-title">ประวัติการคำนวณล่าสุด</div>', unsafe_allow_html=True)
    if not history:
        st.caption("ยังไม่มีประวัติการคำนวณในรอบการใช้งานนี้")
        return

    display_rows = [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in history[:ROLL_HISTORY_LIMIT]
    ]
    st.dataframe(display_rows, use_container_width=True, hide_index=True)
    hist_cols = st.columns([0.85, 0.95, 3.2])
    with hist_cols[0]:
        st.button("ล้างประวัติ", key="clear_roll_history_button", on_click=clear_roll_history, use_container_width=True)
    with hist_cols[1]:
        st.download_button(
            "CSV",
            data=table_rows_to_csv_bytes(display_rows),
            file_name="roll_history.csv",
            mime="text/csv",
            key="download_roll_history_csv",
            use_container_width=True,
        )
    with hist_cols[2]:
        st.caption(f"เก็บถาวร 5 ครั้งล่าสุดในไฟล์ {APP_HISTORY_PATH.name} — รีสตาร์ทแอปแล้วโหลดกลับได้")

# =========================================================
# Area / Roll item management
# =========================================================
def calculate_sticker_area_item(
    name: str,
    width_value: float,
    height_value: float,
    quantity: int,
    unit: str,
    usable_print_width_cm: float,
    face_charge_threshold_cm: float,
    auto_rotate_enabled: bool = False,
    shape: str = QUICK_SHAPE_RECTANGLE,
) -> StickerAreaItem:
    shape = normalize_sticker_shape(shape)
    width_cm = to_cm(width_value, unit)
    height_cm = to_cm(height_value, unit)
    if shape == QUICK_SHAPE_CIRCLE:
        height_cm = width_cm
    quantity = max(0, int(quantity))
    single_area_sqcm = round2(quick_piece_area_sqcm(shape, width_cm, height_cm))
    total_area_sqcm = round2(single_area_sqcm * quantity)
    total_area_sqm = round2(total_area_sqcm / 10000)

    # ใช้แนวที่วางบนม้วนได้จริงเป็นฐานคิดหน้าพิมพ์: ถ้า Auto Rotate เปิดอยู่ ระบบจะหมุนชิ้นงานเมื่อช่วยลดหน้ากว้าง
    if auto_rotate_enabled and height_cm < width_cm:
        charge_width_basis_cm = height_cm
        charge_length_basis_cm = width_cm
    else:
        charge_width_basis_cm = width_cm
        charge_length_basis_cm = height_cm

    needs_face_charge = charge_width_basis_cm > face_charge_threshold_cm
    over_print_width = charge_width_basis_cm > usable_print_width_cm

    if needs_face_charge:
        charge_width_cm = max(usable_print_width_cm, charge_width_basis_cm)
        charge_area_sqm = round2(charge_width_cm * charge_length_basis_cm * quantity / 10000)
        charge_mode = "คิดตามหน้าพิมพ์"
    else:
        charge_area_sqm = total_area_sqm
        charge_mode = "คิดตามขนาดชิ้นงาน"

    return StickerAreaItem(
        name=name.strip() or "ไม่ระบุชื่อ",
        shape=shape,
        width_cm=width_cm,
        height_cm=height_cm,
        quantity=quantity,
        single_area_sqcm=single_area_sqcm,
        total_area_sqcm=total_area_sqcm,
        total_area_sqm=total_area_sqm,
        charge_area_sqm=charge_area_sqm,
        charge_mode=charge_mode,
        needs_face_charge=needs_face_charge,
        over_print_width=over_print_width,
    )


def area_item_keys(item_id: int) -> tuple[str, str, str, str]:
    return (
        f"area_name_{item_id}",
        f"area_width_{item_id}",
        f"area_height_{item_id}",
        f"area_qty_{item_id}",
    )


def area_shape_key(item_id: int) -> str:
    return f"area_shape_{int(item_id)}"


def clear_area_item_state(item_id: int) -> None:
    for key in area_item_keys(int(item_id)):
        st.session_state.pop(key, None)
    st.session_state.pop(area_shape_key(int(item_id)), None)
    st.session_state.pop(f"mixed_ratio_weight_{int(item_id)}", None)


def set_area_item_defaults(item_id: int) -> None:
    name_key, width_key, height_key, qty_key = area_item_keys(item_id)
    shape_key = area_shape_key(item_id)
    if not str(st.session_state.get(name_key, "")).strip():
        st.session_state[name_key] = f"Size {item_id}"
    st.session_state.setdefault(shape_key, QUICK_SHAPE_RECTANGLE)
    if st.session_state.get(shape_key) not in QUICK_SHAPES:
        st.session_state[shape_key] = QUICK_SHAPE_RECTANGLE
    st.session_state.setdefault(width_key, 10.0)
    st.session_state.setdefault(height_key, 10.0)
    st.session_state.setdefault(qty_key, 1)
    sync_circle_height(width_key, height_key, st.session_state.get(shape_key))


def enforce_single_area_item_for_fixed_quantity() -> None:
    """โหมดคำนวณจากจำนวนที่กรอกใช้ได้แค่ 1 Size เท่านั้น

    ใช้ทั้งตอนเปลี่ยนโหมด / โหลด Preset / มี Session เก่าที่เคยเพิ่มหลาย Size ไว้
    เพื่อกันไม่ให้ข้อมูลหลาย Size หลุดไปคำนวณในโหมด Fixed Quantity
    """
    if normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode")) != ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
        return

    item_ids = [int(item_id) for item_id in st.session_state.get("area_item_ids", [])]
    if not item_ids:
        item_ids = [1]

    keep_id = item_ids[0]
    for remove_id in item_ids[1:]:
        clear_area_item_state(remove_id)

    st.session_state["area_item_ids"] = [keep_id]
    st.session_state["area_next_id"] = max(int(st.session_state.get("area_next_id", keep_id + 1)), keep_id + 1)
    st.session_state.pop("confirm_remove_area_item_id", None)
    set_area_item_defaults(keep_id)


def add_area_item() -> None:
    if normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode")) == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
        enforce_single_area_item_for_fixed_quantity()
        set_action_feedback("โหมดคำนวณจากจำนวนที่กรอกใช้ได้แค่ 1 Size", "warn")
        return

    item_id = int(st.session_state.get("area_next_id", 1))
    st.session_state.setdefault("area_item_ids", [])
    st.session_state["area_item_ids"].append(item_id)
    st.session_state["area_next_id"] = item_id + 1
    set_area_item_defaults(item_id)
    set_action_feedback(f"เพิ่ม Size #{item_id} แล้ว", "add")


def clear_area_confirmations() -> None:
    """ล้างสถานะยืนยันคำสั่งที่มีความเสี่ยงในหน้า Size"""
    st.session_state.pop("confirm_reset_area_items", None)
    st.session_state.pop("confirm_remove_area_item_id", None)


def cancel_area_confirmation() -> None:
    clear_area_confirmations()
    set_action_feedback("ยกเลิกคำสั่งแล้ว", "info")


def request_reset_area_items() -> None:
    clear_area_confirmations()
    st.session_state["confirm_reset_area_items"] = True
    set_action_feedback("ต้องยืนยันก่อนล้างรายการ Size", "warn")


def confirm_reset_area_items() -> None:
    clear_area_confirmations()
    reset_area_items()


def request_remove_area_item(item_id: int) -> None:
    clear_area_confirmations()
    st.session_state["confirm_remove_area_item_id"] = int(item_id)
    set_action_feedback(f"ต้องยืนยันก่อนลบ Size #{int(item_id)}", "warn")


def confirm_remove_area_item(item_id: int) -> None:
    clear_area_confirmations()
    remove_area_item(int(item_id))


def remove_area_item(item_id: int) -> None:
    item_ids = list(st.session_state.get("area_item_ids", []))
    if len(item_ids) <= 1:
        set_action_feedback("ต้องเหลืออย่างน้อย 1 Size", "warn")
        return
    st.session_state["area_item_ids"] = [current_id for current_id in item_ids if current_id != item_id]
    clear_area_item_state(item_id)
    set_action_feedback(f"ลบ Size #{item_id} แล้ว", "delete")


def duplicate_area_item(source_item_id: int) -> None:
    if normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode")) == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
        enforce_single_area_item_for_fixed_quantity()
        set_action_feedback("โหมดคำนวณจากจำนวนที่กรอกไม่ใช้การคัดลอก Size", "warn")
        return

    source_item_id = int(source_item_id)
    source_name_key, source_width_key, source_height_key, source_qty_key = area_item_keys(source_item_id)

    item_id = int(st.session_state.get("area_next_id", 1))
    st.session_state.setdefault("area_item_ids", [])
    st.session_state["area_item_ids"].append(item_id)
    st.session_state["area_next_id"] = item_id + 1

    name_key, width_key, height_key, qty_key = area_item_keys(item_id)
    shape_key = area_shape_key(item_id)
    source_shape_key = area_shape_key(source_item_id)
    source_name = str(st.session_state.get(source_name_key, f"Size {source_item_id}")).strip()
    st.session_state[name_key] = f"{source_name} สำเนา" if source_name else f"Size {item_id}"
    st.session_state[shape_key] = normalize_sticker_shape(st.session_state.get(source_shape_key, QUICK_SHAPE_RECTANGLE))
    st.session_state[width_key] = round2(st.session_state.get(source_width_key, 10.0))
    st.session_state[height_key] = round2(st.session_state.get(source_height_key, 10.0))
    st.session_state[qty_key] = int(st.session_state.get(source_qty_key, 1))
    sync_circle_height(width_key, height_key, st.session_state.get(shape_key))
    set_action_feedback(f"คัดลอก Size #{source_item_id} เป็น Size #{item_id} แล้ว", "add")


def swap_area_item_dimensions(item_id: int) -> None:
    item_id = int(item_id)
    _, width_key, height_key, _ = area_item_keys(item_id)
    current_width = round2(st.session_state.get(width_key, 0.0))
    current_height = round2(st.session_state.get(height_key, 0.0))
    st.session_state[width_key] = current_height
    st.session_state[height_key] = current_width
    set_action_feedback(f"สลับกว้าง/ยาวของ Size #{item_id} แล้ว", "edit")


def reset_area_items() -> None:
    for item_id in st.session_state.get("area_item_ids", []):
        clear_area_item_state(int(item_id))
    st.session_state["area_item_ids"] = [1]
    st.session_state["area_next_id"] = 2
    set_area_item_defaults(1)
    set_action_feedback("ล้างรายการ Size แล้ว", "reset")


def sync_area_unit_values() -> None:
    previous_unit = st.session_state.get("previous_area_unit", CM_UNIT)
    current_unit = st.session_state["area_unit"]
    if previous_unit == current_unit:
        return

    factor = 1 / 2.54 if current_unit == INCH_UNIT else 2.54

    for item_id in st.session_state.get("area_item_ids", []):
        _, width_key, height_key, _ = area_item_keys(int(item_id))
        if width_key in st.session_state:
            st.session_state[width_key] = round2(float(st.session_state[width_key]) * factor)
        if height_key in st.session_state:
            st.session_state[height_key] = round2(float(st.session_state[height_key]) * factor)

    for key in (
        "roll_print_width",
        "roll_gap",
        # fixed_quantity_mark_tolerance เป็นค่ามาร์ค 57cm จึงเก็บเป็น cm ตลอด ไม่แปลงตามหน่วย inch/cm
        "face_charge_threshold",
        "roll_margin_left",
        "roll_margin_right",
        "roll_head_margin",
        "roll_tail_margin",
    ):
        if key in st.session_state:
            st.session_state[key] = round2(float(st.session_state[key]) * factor)

    st.session_state["previous_area_unit"] = current_unit
    set_action_feedback(f"เปลี่ยนหน่วยรายการเป็น {current_unit}", "edit")


def collect_area_items(
    area_unit: str,
    usable_print_width_cm: float,
    face_charge_threshold_cm: float,
    auto_rotate_enabled: bool,
) -> list[StickerAreaItem]:
    items: list[StickerAreaItem] = []
    for item_id in st.session_state.get("area_item_ids", []):
        item_id = int(item_id)
        name_key, width_key, height_key, qty_key = area_item_keys(item_id)
        shape_key = area_shape_key(item_id)
        set_area_item_defaults(item_id)

        width_value = round2(st.session_state.get(width_key, 0.0))
        height_value = round2(st.session_state.get(height_key, 0.0))
        shape = normalize_sticker_shape(st.session_state.get(shape_key, QUICK_SHAPE_RECTANGLE))
        if shape == QUICK_SHAPE_CIRCLE:
            height_value = width_value
            st.session_state[height_key] = width_value
        quantity = int(st.session_state.get(qty_key, 0))

        if width_value <= 0 or height_value <= 0 or quantity <= 0:
            continue

        items.append(
            calculate_sticker_area_item(
                name=st.session_state.get(name_key, f"Size {item_id}"),
                width_value=width_value,
                height_value=height_value,
                quantity=quantity,
                unit=area_unit,
                usable_print_width_cm=usable_print_width_cm,
                face_charge_threshold_cm=face_charge_threshold_cm,
                auto_rotate_enabled=auto_rotate_enabled,
                shape=shape,
            )
        )
    return items


def normalize_even_mark_value(value: int, minimum: int = 2) -> int:
    """คืนค่าจำนวนชุด/มาร์คเป็นเลขคู่และไม่ต่ำกว่าขั้นต่ำ"""
    normalized = max(int(minimum), int(value))
    if normalized % 2 != 0:
        normalized += 1
    return normalized


def normalize_mark_value(value: int, minimum: int = 1, require_even: bool = False) -> int:
    """คืนค่าจำนวนชุด/มาร์ค โดยเลือกได้ว่าจะบังคับเลขคู่หรือไม่"""
    if require_even:
        return normalize_even_mark_value(value, minimum=max(2, int(minimum)))
    return max(int(minimum), int(value))


def scale_area_items_for_marks(base_items: list[StickerAreaItem], mark_count: int) -> list[StickerAreaItem]:
    """คูณจำนวนของแต่ละ Size ตามจำนวนชุด/มาร์ค โดยถือว่าจำนวนที่ผู้ใช้กรอกคือจำนวนต่อ 1 ชุด/มาร์ค"""
    mark_count = max(1, int(mark_count))
    scaled_items: list[StickerAreaItem] = []

    for item in base_items:
        base_quantity = max(0, int(item.quantity))
        new_quantity = base_quantity * mark_count
        total_area_sqcm = round2(item.single_area_sqcm * new_quantity)
        total_area_sqm = round2(total_area_sqcm / 10000)

        # charge_area_sqm เดิมเป็นพื้นที่คิดเงินของจำนวนต่อ 1 ชุด/มาร์ค จึงคูณตามจำนวนชุด/มาร์คได้ตรงตัว
        charge_area_sqm = round2(item.charge_area_sqm * mark_count)

        scaled_items.append(
            replace(
                item,
                quantity=new_quantity,
                total_area_sqcm=total_area_sqcm,
                total_area_sqm=total_area_sqm,
                charge_area_sqm=charge_area_sqm,
            )
        )

    return scaled_items


def find_max_pieces_in_target_area(
    base_items: list[StickerAreaItem],
    target_area_sqm: float,
    build_layout_kwargs: dict,
    min_mark_count: int = DEFAULT_TARGET_MIN_MARK_COUNT,
    mark_step: int = DEFAULT_TARGET_MARK_STEP,
    require_even_mark_pair: bool = DEFAULT_TARGET_FORCE_MARK_PAIR,
) -> dict | None:
    """หาจำนวนชิ้นสูงสุดในพื้นที่ที่กำหนดแบบเสถียรกว่าเดิม

    หลักคิด:
    - จำนวนที่กรอกในแต่ละ Size = จำนวนต่อ 1 ชุด/มาร์ค หรือสัดส่วนของชุดงาน
    - ระบบไล่จำนวนชุดแบบ min + n*step เช่น 2, 4, 6 หรือ 1, 2, 3 ตามค่าที่ผู้ใช้เลือก
    - ใช้พื้นที่หน้าม้วนจริงจาก build_roll_layout เป็นตัวตัดสิน ไม่ใช่แค่พื้นที่ชิ้นงานดิบ
    - ช่วงค้นหาใช้ preview_limit=0 เพื่อลดอาการหน่วง แล้วค่อย rebuild layout ที่เลือกอีกครั้งเพื่อใช้แสดง Preview
    """
    if not base_items:
        return None

    target_area_sqm = round2(max(0.0, float(target_area_sqm)))
    require_even_mark_pair = bool(require_even_mark_pair)
    min_mark_count = normalize_mark_value(
        min_mark_count,
        minimum=2 if require_even_mark_pair else 1,
        require_even=require_even_mark_pair,
    )
    mark_step = normalize_mark_value(
        mark_step,
        minimum=2 if require_even_mark_pair else 1,
        require_even=require_even_mark_pair,
    )

    base_quantity = sum(max(0, int(item.quantity)) for item in base_items)
    base_actual_area_sqm = sum(float(item.single_area_sqcm) * max(0, int(item.quantity)) for item in base_items) / 10000
    if base_quantity <= 0 or base_actual_area_sqm <= 0 or target_area_sqm <= 0:
        return None

    preview_layout_kwargs = dict(build_layout_kwargs)
    search_layout_kwargs = dict(build_layout_kwargs)
    search_layout_kwargs["preview_limit"] = 0

    def make_result(
        *,
        mark_count: int,
        area_items: list[StickerAreaItem],
        layout: RollLayoutResult | None,
        failed_mark_count: int | None = None,
        failed_area_items: list[StickerAreaItem] | None = None,
        failed_layout: RollLayoutResult | None = None,
        is_valid: bool = True,
    ) -> dict:
        used_area_sqm = float(layout.roll_face_area_sqm) if layout else 0.0
        remaining_area_sqm = round2(target_area_sqm - used_area_sqm)
        target_usage_percent = round2((used_area_sqm / target_area_sqm * 100) if target_area_sqm > 0 else 0.0)
        return {
            "mark_count": int(mark_count),
            "area_items": area_items,
            "layout": layout,
            "target_area_sqm": target_area_sqm,
            "min_mark_count": min_mark_count,
            "mark_step": mark_step,
            "require_even_mark_pair": require_even_mark_pair,
            "failed_mark_count": failed_mark_count,
            "failed_area_items": failed_area_items,
            "failed_layout": failed_layout,
            "base_items": base_items,
            "is_valid": bool(is_valid),
            "remaining_area_sqm": remaining_area_sqm,
            "target_usage_percent": target_usage_percent,
        }

    max_by_quantity = max(0, MAX_TOTAL_QUANTITY // base_quantity)
    # พื้นที่ชิ้นงานจริงเป็น lower bound ของพื้นที่หน้าม้วน จึงใช้เป็นเพดานค้นหาเพื่อลดความหน่วง
    max_by_raw_area = max(0, int(math.floor(target_area_sqm / base_actual_area_sqm)))
    max_candidate_mark_count = min(max_by_quantity, max_by_raw_area)

    if max_candidate_mark_count < min_mark_count:
        failed_area_items = scale_area_items_for_marks(base_items, min_mark_count)
        failed_layout = build_roll_layout(area_items=failed_area_items, **preview_layout_kwargs)
        return make_result(
            mark_count=0,
            area_items=[],
            layout=None,
            failed_mark_count=min_mark_count,
            failed_area_items=failed_area_items,
            failed_layout=failed_layout,
            is_valid=False,
        )

    max_index = max(0, (max_candidate_mark_count - min_mark_count) // mark_step)
    low_index = 0
    high_index = max_index
    best_mark_count = 0

    while low_index <= high_index:
        mid_index = (low_index + high_index) // 2
        mark_count = min_mark_count + mid_index * mark_step
        scaled_items = scale_area_items_for_marks(base_items, mark_count)
        layout = build_roll_layout(area_items=scaled_items, **search_layout_kwargs)

        if layout.roll_face_area_sqm <= target_area_sqm + 1e-9:
            best_mark_count = mark_count
            low_index = mid_index + 1
        else:
            high_index = mid_index - 1

    if best_mark_count <= 0:
        failed_area_items = scale_area_items_for_marks(base_items, min_mark_count)
        failed_layout = build_roll_layout(area_items=failed_area_items, **preview_layout_kwargs)
        return make_result(
            mark_count=0,
            area_items=[],
            layout=None,
            failed_mark_count=min_mark_count,
            failed_area_items=failed_area_items,
            failed_layout=failed_layout,
            is_valid=False,
        )

    best_area_items = scale_area_items_for_marks(base_items, best_mark_count)
    best_layout = build_roll_layout(area_items=best_area_items, **preview_layout_kwargs)

    failed_mark_count = None
    failed_area_items = None
    failed_layout = None
    next_mark_count = best_mark_count + mark_step
    if next_mark_count <= max_by_quantity:
        failed_mark_count = next_mark_count
        failed_area_items = scale_area_items_for_marks(base_items, failed_mark_count)
        failed_layout = build_roll_layout(area_items=failed_area_items, **preview_layout_kwargs)

    return make_result(
        mark_count=best_mark_count,
        area_items=best_area_items,
        layout=best_layout,
        failed_mark_count=failed_mark_count,
        failed_area_items=failed_area_items,
        failed_layout=failed_layout,
        is_valid=True,
    )

def find_max_mark_pair_for_target_area(*args, **kwargs) -> dict | None:
    """Alias เก่า เพื่อไม่ให้ Preset/โค้ดเดิมที่อ้างชื่อเดิมพัง"""
    kwargs["require_even_mark_pair"] = True
    return find_max_pieces_in_target_area(*args, **kwargs)


def orientation_options(item: StickerAreaItem, auto_rotate_enabled: bool) -> list[tuple[float, float, bool]]:
    options = [(item.width_cm, item.height_cm, False)]
    if auto_rotate_enabled and abs(item.width_cm - item.height_cm) > 1e-9:
        options.append((item.height_cm, item.width_cm, True))
    return options


def choose_orientation_for_row(
    item: StickerAreaItem,
    auto_rotate_enabled: bool,
    current_x: float,
    left_margin: float,
    usable_right: float,
    usable_width: float,
    gap_cm: float,
) -> tuple[float, float, bool, float, bool]:
    """เลือกแนววางที่เหมาะกับแถวปัจจุบันก่อน ถ้าไม่ได้ให้เริ่มแถวใหม่"""
    options = orientation_options(item, auto_rotate_enabled)

    x_if_current = current_x if current_x <= left_margin + 1e-9 else round2(current_x + gap_cm)
    current_candidates = []
    for width_cm, height_cm, rotated in options:
        overflow = width_cm > usable_width + 1e-9
        if not overflow and x_if_current + width_cm <= usable_right + 1e-9:
            remaining = round2(usable_right - (x_if_current + width_cm))
            current_candidates.append((remaining, height_cm, width_cm, rotated, x_if_current, overflow))

    if current_candidates:
        remaining, height_cm, width_cm, rotated, x_pos, overflow = min(current_candidates)
        return width_cm, height_cm, rotated, x_pos, overflow

    new_row_candidates = []
    for width_cm, height_cm, rotated in options:
        overflow = width_cm > usable_width + 1e-9
        if not overflow:
            remaining = round2(usable_width - width_cm)
            new_row_candidates.append((height_cm, remaining, width_cm, rotated, left_margin, overflow))

    if new_row_candidates:
        height_cm, remaining, width_cm, rotated, x_pos, overflow = min(new_row_candidates)
        return width_cm, height_cm, rotated, x_pos, overflow

    # ถ้าไม่มีแนวไหนเข้า usable width ให้ใช้แนวที่กว้างน้อยที่สุดเพื่อให้ preview อ่านง่ายที่สุด
    width_cm, height_cm, rotated = min(options, key=lambda opt: opt[0])
    return width_cm, height_cm, rotated, left_margin, True



def merge_skyline_segments(segments: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """รวม segment ที่ติดกันและมีความสูงเท่ากัน เพื่อลดจำนวนจุดคำนวณ"""
    cleaned = [
        (round2(x), round2(width), round2(height))
        for x, width, height in segments
        if width > 1e-9
    ]
    if not cleaned:
        return []

    cleaned.sort(key=lambda item: (item[0], item[2]))
    merged: list[tuple[float, float, float]] = []
    for x, width, height in cleaned:
        if not merged:
            merged.append((x, width, height))
            continue

        prev_x, prev_width, prev_height = merged[-1]
        prev_end = round2(prev_x + prev_width)
        if abs(prev_end - x) <= 1e-6 and abs(prev_height - height) <= 1e-6:
            merged[-1] = (prev_x, round2(prev_width + width), prev_height)
        else:
            merged.append((x, width, height))
    return merged


def skyline_position_for_item(
    skyline: list[tuple[float, float, float]],
    item_width_cm: float,
    item_height_cm: float,
    usable_right_cm: float,
    gap_cm: float,
) -> tuple:
    """หา position แบบ bottom-left/skyline เพื่อเติมช่องว่างใต้ชิ้นเล็กก่อนขึ้นแถวใหม่"""
    best_score = None
    best_position = None

    for x, _, _ in skyline:
        if x + item_width_cm > usable_right_cm + 1e-9:
            continue

        used_width_cm = item_width_cm + gap_cm if x + item_width_cm + gap_cm <= usable_right_cm + 1e-9 else item_width_cm
        x_end = round2(x + used_width_cm)
        covered_width = 0.0
        y_cm = 0.0

        for seg_x, seg_width, seg_height in skyline:
            seg_end = round2(seg_x + seg_width)
            overlap_left = max(x, seg_x)
            overlap_right = min(x_end, seg_end)
            if overlap_right <= overlap_left + 1e-9:
                continue
            covered_width = round2(covered_width + overlap_right - overlap_left)
            y_cm = max(y_cm, seg_height)

        if covered_width + 1e-6 < used_width_cm:
            continue

        # เรียงความสำคัญ: ต่ำสุดก่อน > จบงานต่ำกว่า > ซ้ายกว่า > ใช้ช่วงกว้างน้อยกว่า
        score = (round2(y_cm), round2(y_cm + item_height_cm), round2(x), round2(used_width_cm))
        if best_score is None or score < best_score:
            best_score = score
            best_position = (round2(x), round2(y_cm), round2(used_width_cm), round2(item_height_cm + gap_cm))

    if best_score is None or best_position is None:
        return None
    return best_score, best_position


def add_skyline_level(
    skyline: list[tuple[float, float, float]],
    x_cm: float,
    used_width_cm: float,
    new_height_cm: float,
) -> list[tuple[float, float, float]]:
    """อัปเดต skyline หลังวางชิ้นงาน โดยตัด segment ที่ถูกใช้งานและแทรกความสูงใหม่"""
    x_end = round2(x_cm + used_width_cm)
    updated: list[tuple[float, float, float]] = []
    inserted = False

    for seg_x, seg_width, seg_height in skyline:
        seg_end = round2(seg_x + seg_width)
        if seg_end <= x_cm + 1e-9 or seg_x >= x_end - 1e-9:
            updated.append((seg_x, seg_width, seg_height))
            continue

        if seg_x < x_cm - 1e-9:
            updated.append((seg_x, round2(x_cm - seg_x), seg_height))

        if not inserted:
            updated.append((round2(x_cm), round2(used_width_cm), round2(new_height_cm)))
            inserted = True

        if seg_end > x_end + 1e-9:
            updated.append((x_end, round2(seg_end - x_end), seg_height))

    if not inserted:
        updated.append((round2(x_cm), round2(used_width_cm), round2(new_height_cm)))

    return merge_skyline_segments(updated)


def skyline_max_height_cm(skyline: list[tuple[float, float, float]]) -> float:
    if not skyline:
        return 0.0
    return round2(max(height for _, _, height in skyline))


def skyline_roughness_score(skyline: list[tuple[float, float, float]]) -> float:
    """ให้คะแนนความขรุขระของ skyline ยิ่งน้อยยิ่งดี เพื่อคุมไม่ให้เกิดช่องว่างใช้งานยาก"""
    if len(skyline) <= 1:
        return 0.0
    roughness = 0.0
    for index in range(1, len(skyline)):
        roughness += abs(skyline[index][2] - skyline[index - 1][2])
    return round2(roughness)


def build_probe_items(
    area_items: list[StickerAreaItem],
    remaining_counts: list[int],
    start_index: int,
    probe_limit: int,
) -> list[StickerAreaItem]:
    """ดึงชิ้นถัดไปจำนวนเล็กน้อยมาใช้มองล่วงหน้า (lookahead)"""
    probes: list[StickerAreaItem] = []
    if probe_limit <= 0:
        return probes

    for probe_index in range(start_index, len(area_items)):
        qty = max(0, int(remaining_counts[probe_index]))
        for _ in range(qty):
            probes.append(area_items[probe_index])
            if len(probes) >= probe_limit:
                return probes
    return probes


def estimate_future_skyline_cost(
    skyline: list[tuple[float, float, float]],
    probe_items: list[StickerAreaItem],
    usable_right_cm: float,
    gap_cm: float,
    auto_rotate_enabled: bool,
) -> tuple[float, float, float]:
    """จำลองชิ้นถัดไปแบบสั้น ๆ เพื่อช่วยตัดสินใจว่าจะหมุนชิ้นปัจจุบันหรือไม่

    คืนค่า: (ความสูงรวมหลังจำลอง, ความขรุขระ skyline, พื้นที่/ความสูงที่ใช้เพิ่มจาก probe)
    ยิ่งน้อยยิ่งดี
    """
    if not probe_items:
        return skyline_max_height_cm(skyline), skyline_roughness_score(skyline), 0.0

    simulated = list(skyline)
    base_height = skyline_max_height_cm(simulated)
    furthest_bottom = base_height

    for probe_item in probe_items:
        best_probe = None
        for width_cm, height_cm, rotated in orientation_options(probe_item, auto_rotate_enabled):
            candidate = skyline_position_for_item(
                skyline=simulated,
                item_width_cm=round2(width_cm),
                item_height_cm=round2(height_cm),
                usable_right_cm=usable_right_cm,
                gap_cm=round2(gap_cm),
            )
            if candidate is None:
                continue

            score, position = candidate
            probe_score = (*score, 1 if rotated else 0)
            if best_probe is None or probe_score < best_probe[0]:
                best_probe = (probe_score, position, round2(width_cm), round2(height_cm))

        if best_probe is None:
            continue

        _, position, width_cm, height_cm = best_probe
        x_pos, y_pos, used_width_cm, _ = position
        furthest_bottom = round2(max(furthest_bottom, y_pos + height_cm))
        simulated = add_skyline_level(
            skyline=simulated,
            x_cm=round2(x_pos),
            used_width_cm=round2(used_width_cm),
            new_height_cm=round2(y_pos + height_cm + gap_cm),
        )

    final_height = skyline_max_height_cm(simulated)
    added_height = round2(max(0.0, furthest_bottom - base_height))
    return final_height, skyline_roughness_score(simulated), added_height



# =========================================================
# Smart roll optimizer / MaxRects strip packing
# =========================================================
def expanded_roll_units(area_items: list[StickerAreaItem]) -> list[tuple[int, int]]:
    """แปลงรายการ Size เป็นรายการชิ้นงานรายชิ้นสำหรับ optimizer"""
    units: list[tuple[int, int]] = []
    for item_index, item in enumerate(area_items):
        for serial in range(int(item.quantity)):
            units.append((item_index, serial))
    return units


def roll_unit_sort_key(unit: tuple[int, int], area_items: list[StickerAreaItem], strategy: str) -> tuple:
    item_index, serial = unit
    item = area_items[item_index]
    width = round2(item.width_cm)
    height = round2(item.height_cm)
    area = round2(width * height)
    max_side = round2(max(width, height))
    min_side = round2(min(width, height))
    perimeter = round2(width + height)
    aspect = round2(max_side / max(min_side, 0.01))

    if strategy == "area_desc":
        return (-area, -max_side, -min_side, item_index, serial)
    if strategy == "height_desc":
        return (-height, -width, -area, item_index, serial)
    if strategy == "width_desc":
        return (-width, -height, -area, item_index, serial)
    if strategy == "max_side_desc":
        return (-max_side, -area, -min_side, item_index, serial)
    if strategy == "perimeter_desc":
        return (-perimeter, -area, item_index, serial)
    if strategy == "thin_tall_first":
        return (-aspect, -max_side, -area, item_index, serial)
    if strategy == "balanced_first":
        return (aspect, -area, -max_side, item_index, serial)
    if strategy == "small_fill_last":
        return (-area, min_side, -max_side, item_index, serial)
    if strategy == "production_grouped":
        return (item_index, serial)
    if strategy == "production_area":
        return (item_index, -area, -max_side, serial)
    # original
    return (item_index, serial)


def packing_strategies_for_quantity(total_quantity: int, layout_mode: str = ROLL_LAYOUT_MODE_SMART) -> list[str]:
    """เลือกกลยุทธ์ตามโหมดการเรียงและจำนวนชิ้น เพื่อไม่ให้แอปหน่วงเกินไป"""
    if layout_mode == ROLL_LAYOUT_MODE_ORIGINAL:
        return ["original"]

    if layout_mode == ROLL_LAYOUT_MODE_PRODUCTION:
        # เน้นอ่านง่าย/ผลิตง่าย: จัดกลุ่ม Size เดียวกันไว้ใกล้กันก่อน แล้วค่อยเลือกแบบที่สั้นกว่า
        return ["production_grouped", "production_area", "original"]

    # Smart Optimizer: เน้นประหยัดพื้นที่สูงสุด
    if total_quantity <= 500:
        return [
            "area_desc",
            "height_desc",
            "width_desc",
            "max_side_desc",
            "perimeter_desc",
            "thin_tall_first",
            "balanced_first",
            "small_fill_last",
            "production_area",
            "original",
        ]
    if total_quantity <= 2500:
        return ["area_desc", "height_desc", "width_desc", "max_side_desc", "thin_tall_first", "production_area"]
    return ["area_desc", "height_desc", "max_side_desc"]


def rect_contains(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (
        ix >= ox - 1e-9
        and iy >= oy - 1e-9
        and ix + iw <= ox + ow + 1e-9
        and iy + ih <= oy + oh + 1e-9
    )


def rects_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw <= bx + 1e-9
        or bx + bw <= ax + 1e-9
        or ay + ah <= by + 1e-9
        or by + bh <= ay + 1e-9
    )


def prune_free_rects(free_rects: list[tuple[float, float, float, float]], max_free_rects: int = 320) -> list[tuple[float, float, float, float]]:
    """ลบ free rect ที่ถูกครอบโดย rect อื่น และจำกัดจำนวน rect กันเครื่องหน่วง"""
    cleaned = [
        (round2(x), round2(y), round2(w), round2(h))
        for x, y, w, h in free_rects
        if w > 1e-9 and h > 1e-9
    ]
    pruned: list[tuple[float, float, float, float]] = []

    for index, rect in enumerate(cleaned):
        contained = False
        for other_index, other in enumerate(cleaned):
            if index == other_index:
                continue
            if rect_contains(other, rect):
                contained = True
                break
        if not contained:
            pruned.append(rect)

    # เก็บ rect ที่อยู่ต่ำและมีพื้นที่ใช้ประโยชน์ก่อน เพื่อเน้นประหยัดความยาวม้วน
    pruned.sort(key=lambda r: (round2(r[1]), round2(r[0]), -round2(r[2] * r[3]), -round2(r[2]), -round2(r[3])))
    if len(pruned) > max_free_rects:
        pruned = pruned[:max_free_rects]
    return pruned


def split_free_rects(
    free_rects: list[tuple[float, float, float, float]],
    used_rect: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """MaxRects split: ตัดพื้นที่ที่ถูกใช้แล้วออกจาก free rect ทั้งหมด"""
    ux, uy, uw, uh = used_rect
    ux2 = round2(ux + uw)
    uy2 = round2(uy + uh)
    next_rects: list[tuple[float, float, float, float]] = []

    for rect in free_rects:
        x, y, w, h = rect
        x2 = round2(x + w)
        y2 = round2(y + h)

        if not rects_intersect(rect, used_rect):
            next_rects.append(rect)
            continue

        # พื้นที่ซ้าย
        if ux > x + 1e-9:
            next_rects.append((x, y, round2(ux - x), h))

        # พื้นที่ขวา
        if ux2 < x2 - 1e-9:
            next_rects.append((ux2, y, round2(x2 - ux2), h))

        # พื้นที่บน
        if uy > y + 1e-9:
            next_rects.append((x, y, w, round2(uy - y)))

        # พื้นที่ล่าง
        if uy2 < y2 - 1e-9:
            next_rects.append((x, uy2, w, round2(y2 - uy2)))

    return prune_free_rects(next_rects)


def maxrects_candidate_for_item(
    free_rects: list[tuple[float, float, float, float]],
    item: StickerAreaItem,
    usable_right_cm: float,
    gap_cm: float,
    auto_rotate_enabled: bool,
) -> tuple | None:
    """เลือกตำแหน่งและแนวหมุนที่ประหยัดที่สุดสำหรับชิ้นงานหนึ่งชิ้น"""
    best = None

    for free_x, free_y, free_w, free_h in free_rects:
        for width_cm, height_cm, rotated in orientation_options(item, auto_rotate_enabled):
            width_cm = round2(width_cm)
            height_cm = round2(height_cm)

            if free_x + width_cm > usable_right_cm + 1e-9:
                continue

            # ใช้ gap เป็น footprint เพื่อกันชิ้นงานชนกัน แต่ถ้าชิดขอบขวาพอดีไม่บังคับให้มี gap เกินหน้าพิมพ์
            footprint_w = round2(width_cm + gap_cm)
            if free_x + footprint_w > usable_right_cm + 1e-9:
                footprint_w = width_cm
            footprint_h = round2(height_cm + gap_cm)

            if footprint_w > free_w + 1e-9 or footprint_h > free_h + 1e-9:
                continue

            bottom = round2(free_y + height_cm)
            footprint_bottom = round2(free_y + footprint_h)
            leftover_w = round2(free_w - footprint_w)
            leftover_h = round2(free_h - footprint_h)
            short_side_leftover = round2(min(leftover_w, leftover_h))
            long_side_leftover = round2(max(leftover_w, leftover_h))

            # คะแนนหลัก: ความยาวม้วนต้องต่ำสุดก่อน แล้วค่อยดูความพอดีของช่องว่าง
            score = (
                bottom,
                footprint_bottom,
                free_y,
                short_side_leftover,
                long_side_leftover,
                free_x,
                1 if rotated else 0,
            )
            candidate = (
                score,
                round2(free_x),
                round2(free_y),
                width_cm,
                height_cm,
                footprint_w,
                footprint_h,
                rotated,
            )
            if best is None or score < best[0]:
                best = candidate

    return best


def roll_strategy_display_name(strategy_name: str) -> str:
    """แปลงชื่อกลยุทธ์ภายในระบบให้เป็นข้อความที่ทีมผลิตอ่านเข้าใจง่าย"""
    labels = {
        "smart_optimizer": "Smart Optimizer",
        "original_sequence": "เรียงทีละชิ้นตามลำดับที่กรอก",
        "production_grouped_rows": "แยกบล็อกตาม Size สำหรับผลิต",
        FIXED_QUANTITY_STRATEGY: "แบ่งเป็นมาร์คคู่ 57cm จากจำนวนที่กรอก",
        "target_mark_pair": "โหมดพื้นที่เป้าหมาย (ปิดใช้งาน)",
        "area_desc": "ชิ้นพื้นที่ใหญ่ก่อน",
        "height_desc": "ชิ้นสูงก่อน",
        "width_desc": "ชิ้นกว้างก่อน",
        "max_side_desc": "ด้านยาวมากก่อน",
        "perimeter_desc": "รอบรูปมากก่อน",
        "thin_tall_first": "ชิ้นแคบ/ยาวก่อน",
        "balanced_first": "ชิ้นสัดส่วนสมดุลก่อน",
        "small_fill_last": "ชิ้นเล็กเติมช่องว่าง",
        "production_area": "จัดกลุ่ม Size แล้วพื้นที่ใหญ่ก่อน",
        "original": "ลำดับเดิม",
        "invalid_margin": "Margin ไม่ถูกต้อง",
    }
    return labels.get(strategy_name or "", strategy_name or "-")


def choose_sequential_orientation(
    item: StickerAreaItem,
    usable_width_cm: float,
    gap_cm: float,
    auto_rotate_enabled: bool,
    production_mode: bool,
) -> tuple[float, float, bool]:
    """เลือกแนววางสำหรับโหมดที่ต้องอ่านง่าย ไม่ใช้ MaxRects เติมช่องว่าง"""
    options = orientation_options(item, auto_rotate_enabled)

    if not production_mode:
        # โหมดลำดับเดิม: รักษาแนวที่กรอกก่อน ถ้ากว้างเกินจึงค่อยหมุนเมื่อ Auto Rotate เปิดและหมุนแล้วเข้า
        width_cm, height_cm, rotated = options[0]
        if width_cm <= usable_width_cm + 1e-9:
            return round2(width_cm), round2(height_cm), rotated
        fitting_options = [opt for opt in options if opt[0] <= usable_width_cm + 1e-9]
        if fitting_options:
            width_cm, height_cm, rotated = min(fitting_options, key=lambda opt: (opt[2] is False, opt[0]))
            return round2(width_cm), round2(height_cm), rotated
        width_cm, height_cm, rotated = min(options, key=lambda opt: opt[0])
        return round2(width_cm), round2(height_cm), rotated

    # โหมดผลิตง่าย: ใช้แนวเดียวกันทั้ง Size และเลือกแนวที่ทำให้บล็อก Size นั้นสั้น/นับง่ายที่สุด
    best = None
    for width_cm, height_cm, rotated in options:
        width_cm = round2(width_cm)
        height_cm = round2(height_cm)
        overflow = width_cm > usable_width_cm + 1e-9
        if overflow:
            per_row = 1
        else:
            per_row = max(1, math.floor((usable_width_cm + gap_cm + 1e-9) / (width_cm + gap_cm)))
        row_count = math.ceil(max(1, item.quantity) / per_row)
        block_length = row_count * height_cm + max(0, row_count - 1) * gap_cm
        score = (1 if overflow else 0, round2(block_length), row_count, 1 if rotated else 0, width_cm)
        candidate = (score, width_cm, height_cm, rotated)
        if best is None or score < best[0]:
            best = candidate

    _, width_cm, height_cm, rotated = best
    return round2(width_cm), round2(height_cm), rotated


def pack_units_sequential_rows(
    area_items: list[StickerAreaItem],
    print_width_cm: float,
    usable_width_cm: float,
    usable_right_cm: float,
    gap_cm: float,
    margin_left_cm: float,
    head_margin_cm: float,
    tail_margin_cm: float,
    auto_rotate_enabled: bool,
    preview_limit: int,
    strategy: str,
) -> dict:
    """จัดเรียงแบบแถวธรรมดา เพื่อให้โหมดผลิตง่ายและลำดับเดิมแตกต่างจาก Smart Optimizer ชัดเจน

    - original_sequence: เรียงทีละชิ้นตามลำดับที่ผู้ใช้กรอก ไม่เติมช่องว่างย้อนหลัง
    - production_grouped_rows: แยก Size เป็นบล็อก เริ่ม Size ใหม่ที่แถวใหม่ เพื่อให้นับและผลิตง่าย
    """
    production_mode = strategy == "production_grouped_rows"
    placements: list[RollStickerPlacement] = []
    current_x = round2(margin_left_cm)
    current_y = round2(head_margin_cm)
    row_height = 0.0
    row_has_items = False
    max_bottom_cm = round2(head_margin_cm)
    placement_levels: set[float] = set()
    overflow_count = 0
    rotated_count = 0

    def start_new_row() -> None:
        nonlocal current_x, current_y, row_height, row_has_items
        if not row_has_items:
            current_x = round2(margin_left_cm)
            row_height = 0.0
            return
        current_y = round2(current_y + row_height + gap_cm)
        current_x = round2(margin_left_cm)
        row_height = 0.0
        row_has_items = False

    for item_index, item in enumerate(area_items):
        if production_mode and row_has_items:
            # โหมดผลิตง่าย: ไม่เอา Size ถัดไปไปปนในแถวเดิม แม้ยังมีช่องว่างเหลือ
            start_new_row()

        width_cm, height_cm, rotated = choose_sequential_orientation(
            item=item,
            usable_width_cm=usable_width_cm,
            gap_cm=round2(gap_cm),
            auto_rotate_enabled=auto_rotate_enabled,
            production_mode=production_mode,
        )

        for _ in range(int(item.quantity)):
            overflow = width_cm > usable_width_cm + 1e-9
            if overflow:
                if row_has_items:
                    start_new_row()
                x_pos = round2(margin_left_cm)
                y_pos = round2(current_y)
                overflow_count += 1
            else:
                if row_has_items and current_x + width_cm > usable_right_cm + 1e-9:
                    start_new_row()
                x_pos = round2(current_x)
                y_pos = round2(current_y)

            if rotated:
                rotated_count += 1

            if len(placements) < preview_limit:
                placements.append(
                    RollStickerPlacement(
                        name=item.name,
                        shape=item.shape,
                        x_cm=x_pos,
                        y_cm=y_pos,
                        width_cm=round2(width_cm),
                        height_cm=round2(height_cm),
                        item_index=item_index,
                        overflow=overflow,
                        rotated=rotated,
                    )
                )

            placement_levels.add(y_pos)
            max_bottom_cm = round2(max(max_bottom_cm, y_pos + height_cm))

            if overflow:
                current_y = round2(y_pos + height_cm + gap_cm)
                current_x = round2(margin_left_cm)
                row_height = 0.0
                row_has_items = False
            else:
                current_x = round2(x_pos + width_cm + gap_cm)
                row_height = round2(max(row_height, height_cm))
                row_has_items = True

    required_length_cm = round2((max_bottom_cm if area_items else head_margin_cm) + tail_margin_cm)
    roll_face_area_sqm = round2(print_width_cm * required_length_cm / 10000) if print_width_cm > 0 else 0.0
    actual_area_sqm = round2(sum(item.total_area_sqcm for item in area_items) / 10000)
    usage = round2(actual_area_sqm / roll_face_area_sqm * 100) if roll_face_area_sqm > 0 else 0.0
    empty_percent = round2(max(0.0, 100.0 - usage)) if roll_face_area_sqm > 0 else 0.0

    return {
        "strategy": strategy,
        "placements": placements,
        "rows_count": len(placement_levels),
        "required_length_cm": required_length_cm,
        "roll_face_area_sqm": roll_face_area_sqm,
        "empty_percent": empty_percent,
        "overflow_count": overflow_count,
        "rotated_count": rotated_count,
        "score": (overflow_count, required_length_cm, roll_face_area_sqm, empty_percent, len(placement_levels), -rotated_count),
    }


def get_roll_preview_length_cm(layout: RollLayoutResult) -> float:
    """กำหนดความยาว Preview ให้เห็นมากกว่า 260 cm แต่ยังกันภาพหนักเกินไป"""
    return min(max(layout.required_length_cm, 20.0), ROLL_PREVIEW_MAX_LENGTH_CM)


def target_area_limit_length_cm(layout: RollLayoutResult, target_area_sqm: float | None) -> float | None:
    """แปลงพื้นที่ที่กำหนดเป็นเส้นความยาวบน Preview เพื่อให้เห็นว่าขอบพื้นที่อยู่ตรงไหน"""
    if target_area_sqm is None or target_area_sqm <= 0 or layout.print_width_cm <= 0:
        return None
    return round2(float(target_area_sqm) * 10000 / layout.print_width_cm)


def draw_target_area_limit_matplotlib(
    ax,
    layout: RollLayoutResult,
    preview_length_cm: float,
    target_area_sqm: float | None,
) -> None:
    target_y = target_area_limit_length_cm(layout, target_area_sqm)
    if target_y is None or target_y <= 0 or target_y > preview_length_cm + 1e-9:
        return

    ax.axhline(target_y, color="#22c55e", linewidth=1.1, linestyle="-.", alpha=0.86, zorder=6)
    ax.text(
        layout.print_width_cm,
        target_y - max(1.2, preview_length_cm * 0.006),
        f"ขอบพื้นที่ {target_area_sqm:.2f} ตรม.",
        color="#dcfce7",
        fontsize=7.8,
        ha="right",
        va="bottom",
        zorder=7,
        bbox=dict(facecolor="#14532d", edgecolor="#22c55e", boxstyle="round,pad=0.28", alpha=0.86),
        fontproperties=get_thai_font(bold=True),
    )


def draw_target_area_limit_plotly(
    fig,
    layout: RollLayoutResult,
    preview_length_cm: float,
    target_area_sqm: float | None,
) -> None:
    target_y = target_area_limit_length_cm(layout, target_area_sqm)
    if target_y is None or target_y <= 0 or target_y > preview_length_cm + 1e-9:
        return

    fig.add_shape(
        type="line",
        x0=0,
        y0=target_y,
        x1=layout.print_width_cm,
        y1=target_y,
        line=dict(color="#22c55e", width=2, dash="dashdot"),
        layer="above",
    )
    fig.add_annotation(
        x=layout.print_width_cm,
        y=target_y,
        xanchor="right",
        yanchor="bottom",
        text=f"ขอบพื้นที่ {target_area_sqm:.2f} ตรม.",
        showarrow=False,
        font=dict(color="#dcfce7", size=11, family="Noto Sans Thai, Inter, sans-serif"),
        bgcolor="rgba(20,83,45,0.88)",
        bordercolor="#22c55e",
        borderwidth=1,
        borderpad=5,
    )


def roll_cut_section_summary(layout: RollLayoutResult, section_length_cm: float = ROLL_CUT_SECTION_LENGTH_CM) -> tuple[int, float]:
    """คืนจำนวนช่วงตัดและความยาวช่วงสุดท้าย เมื่อกำหนดไม่ให้ตัดเกิน section_length_cm"""
    if layout.required_length_cm <= 0 or section_length_cm <= 0:
        return 0, 0.0
    section_count = int(math.ceil(layout.required_length_cm / section_length_cm))
    last_length = round2(layout.required_length_cm - section_length_cm * (section_count - 1))
    return section_count, last_length


def draw_cut_guides_matplotlib(ax, layout: RollLayoutResult, preview_length_cm: float) -> None:
    """ตีเส้นไกด์ทุก 260 cm เพื่อไม่ให้เข้าใจว่า Preview คือจุดตัดสุดท้าย"""
    if ROLL_CUT_SECTION_LENGTH_CM <= 0:
        return
    cut_y = ROLL_CUT_SECTION_LENGTH_CM
    while cut_y < min(layout.required_length_cm, preview_length_cm) - 1e-9:
        ax.axhline(cut_y, color="#ffcf8a", linewidth=0.85, linestyle="--", alpha=0.74, zorder=5)
        ax.text(
            layout.print_width_cm,
            cut_y - max(1.2, preview_length_cm * 0.006),
            f"ตัดช่วง {cut_y:.0f} cm",
            color="#ffcf8a",
            fontsize=7.4,
            ha="right",
            va="bottom",
            zorder=6,
            fontproperties=get_thai_font(bold=True),
        )
        cut_y += ROLL_CUT_SECTION_LENGTH_CM


def draw_cut_guides_plotly(fig, layout: RollLayoutResult, preview_length_cm: float) -> None:
    """ตีเส้นไกด์ทุก 260 cm สำหรับ Interactive Preview"""
    if ROLL_CUT_SECTION_LENGTH_CM <= 0:
        return
    cut_y = ROLL_CUT_SECTION_LENGTH_CM
    while cut_y < min(layout.required_length_cm, preview_length_cm) - 1e-9:
        fig.add_shape(
            type="line",
            x0=0,
            y0=cut_y,
            x1=layout.print_width_cm,
            y1=cut_y,
            line=dict(color="#ffcf8a", width=1, dash="dash"),
            layer="above",
        )
        fig.add_annotation(
            x=layout.print_width_cm,
            y=cut_y,
            xanchor="right",
            yanchor="bottom",
            text=f"ตัดช่วง {cut_y:.0f} cm",
            showarrow=False,
            font=dict(color="#ffcf8a", size=10, family="Noto Sans Thai, Inter, sans-serif"),
            bgcolor="rgba(16,17,20,0.74)",
            bordercolor="rgba(255,207,138,0.35)",
            borderwidth=1,
            borderpad=3,
        )
        cut_y += ROLL_CUT_SECTION_LENGTH_CM


def pack_units_maxrects(
    area_items: list[StickerAreaItem],
    units: list[tuple[int, int]],
    print_width_cm: float,
    usable_width_cm: float,
    usable_right_cm: float,
    gap_cm: float,
    margin_left_cm: float,
    head_margin_cm: float,
    tail_margin_cm: float,
    auto_rotate_enabled: bool,
    preview_limit: int,
    strategy: str,
) -> dict:
    """จัดเรียงด้วย MaxRects บน strip ความกว้างคงที่ แล้วคืน candidate สำหรับเลือกตัวที่ประหยัดที่สุด"""
    ordered_units = sorted(units, key=lambda unit: roll_unit_sort_key(unit, area_items, strategy))
    max_strip_height = round2(
        head_margin_cm
        + tail_margin_cm
        + sum(max(area_items[item_index].width_cm, area_items[item_index].height_cm) + gap_cm for item_index, _ in ordered_units)
        + 100.0
    )
    free_rects: list[tuple[float, float, float, float]] = [
        (round2(margin_left_cm), round2(head_margin_cm), round2(usable_width_cm), max_strip_height)
    ]

    placements: list[RollStickerPlacement] = []
    max_bottom_cm = round2(head_margin_cm)
    placement_levels: set[float] = set()
    overflow_count = 0
    rotated_count = 0

    for item_index, _ in ordered_units:
        item = area_items[item_index]
        candidate = maxrects_candidate_for_item(
            free_rects=free_rects,
            item=item,
            usable_right_cm=usable_right_cm,
            gap_cm=round2(gap_cm),
            auto_rotate_enabled=auto_rotate_enabled,
        )

        if candidate is None:
            # กรณีชิ้นใหญ่เกินหน้าพิมพ์: วางเป็น overflow เต็มแถวเพื่อคุมไม่ให้ทับกับชิ้นอื่น
            width_cm, height_cm, rotated = min(
                orientation_options(item, auto_rotate_enabled),
                key=lambda option: (option[0], option[1]),
            )
            width_cm = round2(width_cm)
            height_cm = round2(height_cm)
            x_pos = round2(margin_left_cm)
            y_pos = round2(max_bottom_cm + (gap_cm if max_bottom_cm > head_margin_cm else 0.0))
            footprint_w = round2(usable_width_cm)
            footprint_h = round2(height_cm + gap_cm)
            overflow = True
            overflow_count += 1
        else:
            _, x_pos, y_pos, width_cm, height_cm, footprint_w, footprint_h, rotated = candidate
            overflow = False

        if rotated:
            rotated_count += 1

        if len(placements) < preview_limit:
            placements.append(
                RollStickerPlacement(
                    name=item.name,
                    shape=item.shape,
                    x_cm=round2(x_pos),
                    y_cm=round2(y_pos),
                    width_cm=round2(width_cm),
                    height_cm=round2(height_cm),
                    item_index=item_index,
                    overflow=overflow,
                    rotated=rotated,
                )
            )

        max_bottom_cm = round2(max(max_bottom_cm, y_pos + height_cm))
        placement_levels.add(round2(y_pos))
        used_rect = (round2(x_pos), round2(y_pos), round2(footprint_w), round2(footprint_h))
        free_rects = split_free_rects(free_rects, used_rect)

    required_length_cm = round2((max_bottom_cm if ordered_units else head_margin_cm) + tail_margin_cm)
    roll_face_area_sqm = round2(print_width_cm * required_length_cm / 10000) if print_width_cm > 0 else 0.0
    actual_area_sqm = round2(sum(item.total_area_sqcm for item in area_items) / 10000)
    usage = round2(actual_area_sqm / roll_face_area_sqm * 100) if roll_face_area_sqm > 0 else 0.0
    empty_percent = round2(max(0.0, 100.0 - usage)) if roll_face_area_sqm > 0 else 0.0

    return {
        "strategy": strategy,
        "placements": placements,
        "rows_count": len(placement_levels),
        "required_length_cm": required_length_cm,
        "roll_face_area_sqm": roll_face_area_sqm,
        "empty_percent": empty_percent,
        "overflow_count": overflow_count,
        "rotated_count": rotated_count,
        "score": (
            overflow_count,
            required_length_cm,
            roll_face_area_sqm,
            empty_percent,
            len(placement_levels),
            -rotated_count,
        ),
    }


def build_roll_layout(
    area_items: list[StickerAreaItem],
    print_width_cm: float,
    gap_cm: float,
    margin_left_cm: float = 0.0,
    margin_right_cm: float = 0.0,
    head_margin_cm: float = 0.0,
    tail_margin_cm: float = 0.0,
    waste_threshold_percent: float = 40.0,
    auto_rotate_enabled: bool = True,
    preview_limit: int = 900,
    layout_mode: str = ROLL_LAYOUT_MODE_SMART,
) -> RollLayoutResult:
    """จัดวางชิ้นงานบนหน้าม้วนด้วย Smart MaxRects Optimizer

    ต่างจาก skyline แบบเดิมที่เดินตามรายการทีละชิ้น ฟังก์ชันนี้จะ:
    - แตกงานเป็นรายชิ้น
    - ประเมินหลายลำดับการวาง เช่น ชิ้นใหญ่ก่อน / สูงก่อน / กว้างก่อน / สัดส่วนแคบยาวก่อน
    - ลองหมุนรายชิ้นแบบอิสระ
    - เลือก layout ที่ใช้ความยาวม้วนน้อยที่สุด
    """
    usable_width_cm = round2(max(0.0, print_width_cm - margin_left_cm - margin_right_cm))
    usable_right_cm = round2(margin_left_cm + usable_width_cm)
    total_quantity = sum(item.quantity for item in area_items)

    if usable_width_cm <= 0:
        return RollLayoutResult(
            print_width_cm=round2(print_width_cm),
            usable_width_cm=usable_width_cm,
            gap_cm=round2(gap_cm),
            margin_left_cm=round2(margin_left_cm),
            margin_right_cm=round2(margin_right_cm),
            head_margin_cm=round2(head_margin_cm),
            tail_margin_cm=round2(tail_margin_cm),
            total_quantity=total_quantity,
            rows_count=0,
            required_length_cm=round2(head_margin_cm + tail_margin_cm),
            actual_area_sqcm=0.0,
            actual_area_sqm=0.0,
            roll_face_area_sqm=0.0,
            charged_rule_area_sqm=0.0,
            material_usage_percent=0.0,
            empty_area_sqm=0.0,
            empty_area_percent=0.0,
            waste_threshold_percent=round2(waste_threshold_percent),
            charge_by_page_due_to_waste=False,
            final_charge_area_sqm=0.0,
            placements=tuple(),
            preview_placements=tuple(),
            preview_limit=preview_limit,
            overflow_count=total_quantity,
            face_charge_names=tuple(item.name for item in area_items if item.needs_face_charge),
            rotated_count=0,
            auto_rotate_enabled=auto_rotate_enabled,
            layout_mode=layout_mode,
            strategy_name="invalid_margin",
        )

    if layout_mode == ROLL_LAYOUT_MODE_ORIGINAL:
        # โหมดนี้ต้องเห็นความต่างชัด: เดินซ้ายไปขวา บนลงล่าง ตามลำดับที่กรอก ไม่เติมช่องว่างแบบ optimizer
        best_candidate = pack_units_sequential_rows(
            area_items=area_items,
            print_width_cm=round2(print_width_cm),
            usable_width_cm=usable_width_cm,
            usable_right_cm=usable_right_cm,
            gap_cm=round2(gap_cm),
            margin_left_cm=round2(margin_left_cm),
            head_margin_cm=round2(head_margin_cm),
            tail_margin_cm=round2(tail_margin_cm),
            auto_rotate_enabled=auto_rotate_enabled,
            preview_limit=preview_limit,
            strategy="original_sequence",
        )
    elif layout_mode == ROLL_LAYOUT_MODE_PRODUCTION:
        # โหมดผลิตง่าย: แยก Size เป็นบล็อก ไม่ปน Size ในแถวเดียวกัน เพื่อให้นับ/ตัด/แยกงานง่าย
        best_candidate = pack_units_sequential_rows(
            area_items=area_items,
            print_width_cm=round2(print_width_cm),
            usable_width_cm=usable_width_cm,
            usable_right_cm=usable_right_cm,
            gap_cm=round2(gap_cm),
            margin_left_cm=round2(margin_left_cm),
            head_margin_cm=round2(head_margin_cm),
            tail_margin_cm=round2(tail_margin_cm),
            auto_rotate_enabled=auto_rotate_enabled,
            preview_limit=preview_limit,
            strategy="production_grouped_rows",
        )
    else:
        units = expanded_roll_units(area_items)
        strategies = packing_strategies_for_quantity(total_quantity, layout_mode=layout_mode)
        candidates = [
            pack_units_maxrects(
                area_items=area_items,
                units=units,
                print_width_cm=round2(print_width_cm),
                usable_width_cm=usable_width_cm,
                usable_right_cm=usable_right_cm,
                gap_cm=round2(gap_cm),
                margin_left_cm=round2(margin_left_cm),
                head_margin_cm=round2(head_margin_cm),
                tail_margin_cm=round2(tail_margin_cm),
                auto_rotate_enabled=auto_rotate_enabled,
                preview_limit=preview_limit,
                strategy=strategy,
            )
            for strategy in strategies
        ]
        best_candidate = min(candidates, key=lambda candidate: candidate["score"]) if candidates else {
            "strategy": "smart_optimizer",
            "placements": [],
            "rows_count": 0,
            "required_length_cm": round2(head_margin_cm + tail_margin_cm),
            "overflow_count": 0,
            "rotated_count": 0,
        }

    actual_area_sqcm = round2(sum(item.total_area_sqcm for item in area_items))
    actual_area_sqm = round2(actual_area_sqcm / 10000)
    required_length_cm = round2(best_candidate["required_length_cm"])
    roll_face_area_sqm = round2(print_width_cm * required_length_cm / 10000) if print_width_cm > 0 else 0.0
    charged_rule_area_sqm = round2(sum(item.charge_area_sqm for item in area_items))
    usage = round2(actual_area_sqm / roll_face_area_sqm * 100) if roll_face_area_sqm > 0 else 0.0
    empty_area_sqm = round2(max(0.0, roll_face_area_sqm - actual_area_sqm))
    empty_area_percent = round2(max(0.0, 100.0 - usage)) if roll_face_area_sqm > 0 else 0.0
    charge_by_page_due_to_waste = empty_area_percent > waste_threshold_percent
    final_charge_area_sqm = round2(roll_face_area_sqm if charge_by_page_due_to_waste else charged_rule_area_sqm)
    face_charge_names = tuple(item.name for item in area_items if item.needs_face_charge)
    placements_tuple = tuple(best_candidate["placements"])

    return RollLayoutResult(
        print_width_cm=round2(print_width_cm),
        usable_width_cm=usable_width_cm,
        gap_cm=round2(gap_cm),
        margin_left_cm=round2(margin_left_cm),
        margin_right_cm=round2(margin_right_cm),
        head_margin_cm=round2(head_margin_cm),
        tail_margin_cm=round2(tail_margin_cm),
        total_quantity=total_quantity,
        rows_count=int(best_candidate["rows_count"]),
        required_length_cm=required_length_cm,
        actual_area_sqcm=actual_area_sqcm,
        actual_area_sqm=actual_area_sqm,
        roll_face_area_sqm=roll_face_area_sqm,
        charged_rule_area_sqm=charged_rule_area_sqm,
        material_usage_percent=usage,
        empty_area_sqm=empty_area_sqm,
        empty_area_percent=empty_area_percent,
        waste_threshold_percent=round2(waste_threshold_percent),
        charge_by_page_due_to_waste=charge_by_page_due_to_waste,
        final_charge_area_sqm=final_charge_area_sqm,
        placements=placements_tuple,
        preview_placements=placements_tuple,
        preview_limit=preview_limit,
        overflow_count=int(best_candidate["overflow_count"]),
        face_charge_names=face_charge_names,
        rotated_count=int(best_candidate["rotated_count"]),
        auto_rotate_enabled=auto_rotate_enabled,
        layout_mode=layout_mode,
        strategy_name=str(best_candidate.get("strategy", "")),
    )


# =========================================================
# Quantity calculator layout
# =========================================================
def count_that_fits(sheet_size: float, sticker_size: float, gap: float, tolerance: float) -> int:
    if sheet_size <= 0 or sticker_size <= 0:
        return 0
    return max(0, math.floor((sheet_size + tolerance + gap + 1e-9) / (sticker_size + gap)))


def count_that_fits_in_rect(rect_size: float, sticker_size: float, gap: float) -> int:
    if rect_size <= 0 or sticker_size <= 0:
        return 0
    return max(0, math.floor((rect_size + gap + 1e-9) / (sticker_size + gap)))


def footprint(count: int, size: float, gap: float) -> float:
    if count <= 0:
        return 0.0
    return round2(count * size + (count - 1) * gap)


def make_grid_placements(
    x_start: float,
    y_start: float,
    columns: int,
    rows: int,
    sticker_width_cm: float,
    sticker_height_cm: float,
    gap_cm: float,
    rotated: bool,
    sheet_width_cm: float,
    sheet_height_cm: float,
) -> list[StickerPlacement]:
    placements: list[StickerPlacement] = []
    for row in range(rows):
        for col in range(columns):
            x_pos = round2(x_start + col * (sticker_width_cm + gap_cm))
            y_pos = round2(y_start + row * (sticker_height_cm + gap_cm))
            is_overflow = (
                x_pos + sticker_width_cm > sheet_width_cm + 1e-9
                or y_pos + sticker_height_cm > sheet_height_cm + 1e-9
            )
            placements.append(
                StickerPlacement(
                    x_cm=x_pos,
                    y_cm=y_pos,
                    width_cm=round2(sticker_width_cm),
                    height_cm=round2(sticker_height_cm),
                    rotated=rotated,
                    overflow=is_overflow,
                )
            )
    return placements


def used_bounds(placements: tuple[StickerPlacement, ...]) -> tuple[float, float]:
    if not placements:
        return 0.0, 0.0
    used_width = max(item.x_cm + item.width_cm for item in placements)
    used_height = max(item.y_cm + item.height_cm for item in placements)
    return round2(used_width), round2(used_height)


def build_layout_result(
    sheet_width_cm: float,
    sheet_height_cm: float,
    sticker_width_cm: float,
    sticker_height_cm: float,
    orientation: str,
    columns: int,
    rows: int,
    placements: list[StickerPlacement],
    grid_summary: str,
    layout_mode: str,
) -> LayoutResult:
    placements_tuple = tuple(placements)
    used_width, used_height = used_bounds(placements_tuple)
    sheet_area = sheet_width_cm * sheet_height_cm
    sticker_area = sum(item.width_cm * item.height_cm for item in placements_tuple)
    usage = round2(sticker_area / sheet_area * 100) if sheet_area > 0 else 0
    normal_count = sum(1 for item in placements_tuple if not item.rotated)
    rotated_count = sum(1 for item in placements_tuple if item.rotated)

    return LayoutResult(
        total_per_mark=len(placements_tuple),
        columns=columns,
        rows=rows,
        sticker_width_cm=round2(sticker_width_cm),
        sticker_height_cm=round2(sticker_height_cm),
        orientation=orientation,
        used_width_cm=round2(used_width),
        used_height_cm=round2(used_height),
        overflow_width_cm=round2(max(0.0, used_width - sheet_width_cm)),
        overflow_height_cm=round2(max(0.0, used_height - sheet_height_cm)),
        material_usage_percent=round2(usage),
        placements=placements_tuple,
        normal_count=normal_count,
        rotated_count=rotated_count,
        grid_summary=grid_summary,
        layout_mode=layout_mode,
    )


def evaluate_layout(
    sheet_width_cm: float,
    sheet_height_cm: float,
    sticker_width_cm: float,
    sticker_height_cm: float,
    gap_cm: float,
    tolerance_cm: float,
    rotated: bool,
) -> LayoutResult:
    final_w = round2(sticker_height_cm if rotated else sticker_width_cm)
    final_h = round2(sticker_width_cm if rotated else sticker_height_cm)
    columns = count_that_fits(sheet_width_cm, final_w, gap_cm, tolerance_cm)
    rows = count_that_fits(sheet_height_cm, final_h, gap_cm, tolerance_cm)
    placements = make_grid_placements(
        0.0,
        0.0,
        columns,
        rows,
        final_w,
        final_h,
        gap_cm,
        rotated,
        sheet_width_cm,
        sheet_height_cm,
    )
    return build_layout_result(
        sheet_width_cm=sheet_width_cm,
        sheet_height_cm=sheet_height_cm,
        sticker_width_cm=final_w,
        sticker_height_cm=final_h,
        orientation="หมุน 90 องศา" if rotated else "ปกติ",
        columns=columns,
        rows=rows,
        placements=placements,
        grid_summary=f"{columns} คอลัมน์ x {rows} แถว",
        layout_mode="single",
    )


def add_rotated_fill_candidates(
    sheet_width_cm: float,
    sheet_height_cm: float,
    effective_width_cm: float,
    effective_height_cm: float,
    gap_cm: float,
    base_columns: int,
    base_rows: int,
    base_w: float,
    base_h: float,
    split_mode: str,
) -> tuple[int, int, int, int, str]:
    add_w = round2(base_h)
    add_h = round2(base_w)
    base_used_w = footprint(base_columns, base_w, gap_cm)
    base_used_h = footprint(base_rows, base_h, gap_cm)
    right_x = round2(base_used_w + (gap_cm if base_columns > 0 else 0.0))
    top_y = round2(base_used_h + (gap_cm if base_rows > 0 else 0.0))
    right_rect_w = round2(max(0.0, effective_width_cm - right_x))
    top_rect_h = round2(max(0.0, effective_height_cm - top_y))

    if split_mode == "right_full":
        right_rect_h = effective_height_cm
        top_rect_w = base_used_w
        summary_prefix = "เสริมขวาสูงเต็ม + เสริมบนเท่าชุดหลัก"
    else:
        right_rect_h = base_used_h
        top_rect_w = effective_width_cm
        summary_prefix = "เสริมบนกว้างเต็ม + เสริมขวาเท่าชุดหลัก"

    right_cols = count_that_fits_in_rect(right_rect_w, add_w, gap_cm)
    right_rows = count_that_fits_in_rect(right_rect_h, add_h, gap_cm)
    top_cols = count_that_fits_in_rect(top_rect_w, add_w, gap_cm)
    top_rows = count_that_fits_in_rect(top_rect_h, add_h, gap_cm)
    return right_cols, right_rows, top_cols, top_rows, summary_prefix


def evaluate_mixed_layout(
    sheet_width_cm: float,
    sheet_height_cm: float,
    sticker_width_cm: float,
    sticker_height_cm: float,
    gap_cm: float,
    tolerance_cm: float,
    base_rotated: bool,
) -> LayoutResult:
    effective_width_cm = round2(sheet_width_cm + tolerance_cm)
    effective_height_cm = round2(sheet_height_cm + tolerance_cm)
    base_w = round2(sticker_height_cm if base_rotated else sticker_width_cm)
    base_h = round2(sticker_width_cm if base_rotated else sticker_height_cm)
    max_columns = count_that_fits_in_rect(effective_width_cm, base_w, gap_cm)
    max_rows = count_that_fits_in_rect(effective_height_cm, base_h, gap_cm)

    if max_columns * max_rows <= 8000:
        column_candidates = range(0, max_columns + 1)
        row_candidates = range(0, max_rows + 1)
    else:
        column_candidates = sorted(set(range(max(0, max_columns - 8), max_columns + 1)) | {0})
        row_candidates = sorted(set(range(max(0, max_rows - 8), max_rows + 1)) | {0})

    best_data = None
    for base_columns in column_candidates:
        for base_rows in row_candidates:
            base_total = base_columns * base_rows
            if base_total == 0:
                continue
            for split_mode in ("right_full", "top_full"):
                right_cols, right_rows, top_cols, top_rows, summary_prefix = add_rotated_fill_candidates(
                    sheet_width_cm=sheet_width_cm,
                    sheet_height_cm=sheet_height_cm,
                    effective_width_cm=effective_width_cm,
                    effective_height_cm=effective_height_cm,
                    gap_cm=gap_cm,
                    base_columns=base_columns,
                    base_rows=base_rows,
                    base_w=base_w,
                    base_h=base_h,
                    split_mode=split_mode,
                )
                extra_total = right_cols * right_rows + top_cols * top_rows
                total = base_total + extra_total
                score = (total, extra_total, base_total)
                if best_data is None or score > best_data[0]:
                    best_data = (
                        score,
                        base_columns,
                        base_rows,
                        right_cols,
                        right_rows,
                        top_cols,
                        top_rows,
                        split_mode,
                        summary_prefix,
                    )

    if best_data is None:
        return evaluate_layout(
            sheet_width_cm,
            sheet_height_cm,
            sticker_width_cm,
            sticker_height_cm,
            gap_cm,
            tolerance_cm,
            rotated=base_rotated,
        )

    _, base_columns, base_rows, right_cols, right_rows, top_cols, top_rows, split_mode, summary_prefix = best_data
    base_used_w = footprint(base_columns, base_w, gap_cm)
    base_used_h = footprint(base_rows, base_h, gap_cm)
    add_w = round2(base_h)
    add_h = round2(base_w)
    add_rotated = not base_rotated

    placements: list[StickerPlacement] = []
    placements.extend(
        make_grid_placements(
            0.0,
            0.0,
            base_columns,
            base_rows,
            base_w,
            base_h,
            gap_cm,
            base_rotated,
            sheet_width_cm,
            sheet_height_cm,
        )
    )
    right_x = round2(base_used_w + (gap_cm if base_columns > 0 else 0.0))
    top_y = round2(base_used_h + (gap_cm if base_rows > 0 else 0.0))
    placements.extend(
        make_grid_placements(
            right_x,
            0.0,
            right_cols,
            right_rows,
            add_w,
            add_h,
            gap_cm,
            add_rotated,
            sheet_width_cm,
            sheet_height_cm,
        )
    )
    placements.extend(
        make_grid_placements(
            0.0,
            top_y,
            top_cols,
            top_rows,
            add_w,
            add_h,
            gap_cm,
            add_rotated,
            sheet_width_cm,
            sheet_height_cm,
        )
    )

    base_label = "หมุน 90°" if base_rotated else "ปกติ"
    add_label = "ปกติ" if base_rotated else "หมุน 90°"
    grid_summary = (
        f"หลัก {base_columns}x{base_rows} ({base_label}) + "
        f"เสริม {right_cols * right_rows + top_cols * top_rows} ชิ้น ({add_label})"
    )

    return build_layout_result(
        sheet_width_cm=sheet_width_cm,
        sheet_height_cm=sheet_height_cm,
        sticker_width_cm=base_w,
        sticker_height_cm=base_h,
        orientation=f"ผสม: {base_label} + {add_label}",
        columns=base_columns,
        rows=base_rows,
        placements=placements,
        grid_summary=f"{grid_summary}<br><span style='font-size:0.78rem;font-weight:600;color:#aeb5c1'>{summary_prefix}</span>",
        layout_mode="mixed",
    )


def best_layout(
    sheet_width_cm: float,
    sheet_height_cm: float,
    sticker_width_cm: float,
    sticker_height_cm: float,
    gap_cm: float,
    tolerance_cm: float,
) -> LayoutResult:
    candidates = [
        evaluate_layout(sheet_width_cm, sheet_height_cm, sticker_width_cm, sticker_height_cm, gap_cm, tolerance_cm, rotated=False),
        evaluate_layout(sheet_width_cm, sheet_height_cm, sticker_width_cm, sticker_height_cm, gap_cm, tolerance_cm, rotated=True),
        evaluate_mixed_layout(sheet_width_cm, sheet_height_cm, sticker_width_cm, sticker_height_cm, gap_cm, tolerance_cm, base_rotated=False),
        evaluate_mixed_layout(sheet_width_cm, sheet_height_cm, sticker_width_cm, sticker_height_cm, gap_cm, tolerance_cm, base_rotated=True),
    ]

    def candidate_score(layout: LayoutResult) -> tuple[int, float]:
        return (layout.total_per_mark, layout.material_usage_percent)

    return max(candidates, key=candidate_score)


def normalize_even_mark_count(value: int) -> int:
    """บังคับจำนวนมาร์คให้เป็นเลขคู่เสมอ เช่น 1→2, 3→4"""
    mark_count = max(2, int(math.ceil(max(0, value))))
    if mark_count % 2 != 0:
        mark_count += 1
    return mark_count


def distribute_quantity_full_then_balance_last_pair(total_quantity: int, mark_count: int, capacity_per_mark: int) -> list[int]:
    """กระจายจำนวนชิ้นแบบผลิตจริง: มาร์คก่อนหน้าเต็มตาม capacity แล้วเฉลี่ยเฉพาะ 2 มาร์คสุดท้าย

    ตัวอย่าง: 130 ชิ้น / capacity 25 / 6 มาร์ค = 25, 25, 25, 25, 15, 15
    กรณีเหลือเป็นเลขคี่ จะให้มาร์คก่อนในคู่สุดท้ายมากกว่า 1 ชิ้น เช่น 31 = 16, 15
    """
    mark_count = max(1, int(mark_count))
    capacity_per_mark = max(1, int(capacity_per_mark))
    total_quantity = max(0, int(total_quantity))

    distribution = [0 for _ in range(mark_count)]

    # ถ้ามีไม่เกิน 2 มาร์ค ให้ถือว่าทั้งหมดคือคู่สุดท้าย แล้วเฉลี่ยกันเลย
    if mark_count <= 2:
        first_qty = min(capacity_per_mark, int(math.ceil(total_quantity / 2)))
        second_qty = min(capacity_per_mark, max(0, total_quantity - first_qty))
        distribution[0] = first_qty
        if mark_count == 2:
            distribution[1] = second_qty
        return distribution

    # มาร์คก่อนหน้าคู่สุดท้ายให้เรียงเต็มตามปกติ
    remaining_quantity = total_quantity
    last_pair_start_index = mark_count - 2
    for index in range(last_pair_start_index):
        qty = min(capacity_per_mark, remaining_quantity)
        distribution[index] = qty
        remaining_quantity -= qty

    # เฉลี่ยเฉพาะ 2 มาร์คสุดท้ายให้ใกล้เคียงกันที่สุด
    first_last_qty = min(capacity_per_mark, int(math.ceil(remaining_quantity / 2)))
    second_last_qty = min(capacity_per_mark, max(0, remaining_quantity - first_last_qty))
    distribution[last_pair_start_index] = first_last_qty
    distribution[last_pair_start_index + 1] = second_last_qty

    return distribution


# Alias เก่า เผื่อมีส่วนอื่นเรียกชื่อเดิมในอนาคต
# แต่พฤติกรรมใหม่คือ "เต็มก่อน แล้วบาลานซ์เฉพาะคู่สุดท้าย"
def distribute_quantity_evenly(total_quantity: int, mark_count: int, capacity_per_mark: int) -> list[int]:
    return distribute_quantity_full_then_balance_last_pair(total_quantity, mark_count, capacity_per_mark)


def fixed_quantity_mark_candidate(
    item: StickerAreaItem,
    gap_cm: float,
    tolerance_cm: float,
    auto_rotate_enabled: bool,
) -> dict:
    """เลือกแนววางใน 1 มาร์คสำหรับโหมดคำนวณจากจำนวนที่กรอก

    หลักการอิงหน้า "คำนวณจำนวนสติกเกอร์ต่อวัสดุพิมพ์":
    - กว้างมาร์ค 57 cm และใช้ค่าอนุโลมจาก Sidebar ตอนคำนวณจำนวนที่วางได้
    - ความสูงมาร์ค Auto แต่ไม่ต่ำกว่า 41 cm
    - ถ้าเปิด Auto Rotate จะลองปกติและหมุน 90° แล้วเลือกแบบที่ได้จำนวนต่อมาร์คมากกว่า
    """
    tolerance_cm = round2(max(0.0, float(tolerance_cm)))
    options: list[dict] = []
    rotations = [False, True] if auto_rotate_enabled and abs(item.width_cm - item.height_cm) > 1e-9 else [False]

    for rotated in rotations:
        piece_w = round2(item.height_cm if rotated else item.width_cm)
        piece_h = round2(item.width_cm if rotated else item.height_cm)
        mark_h = round2(max(FIXED_MARK_HEIGHT_CM, piece_h))
        cols = count_that_fits(FIXED_MARK_WIDTH_CM, piece_w, gap_cm, tolerance_cm)
        rows = count_that_fits(mark_h, piece_h, gap_cm, tolerance_cm)
        capacity = cols * rows
        used_w = footprint(cols, piece_w, gap_cm)
        used_h = footprint(rows, piece_h, gap_cm)
        mark_area = FIXED_MARK_WIDTH_CM * mark_h
        used_area = piece_w * piece_h * capacity
        usage = (used_area / mark_area * 100) if mark_area > 0 else 0.0
        options.append({
            "piece_w": piece_w,
            "piece_h": piece_h,
            "mark_h": mark_h,
            "cols": cols,
            "rows": rows,
            "capacity": capacity,
            "rotated": rotated,
            "used_w": round2(used_w),
            "used_h": round2(used_h),
            "usage": round2(usage),
        })

    valid = [option for option in options if option["capacity"] > 0]
    if valid:
        return max(valid, key=lambda option: (option["capacity"], option["usage"], -option["mark_h"], 0 if option["rotated"] else 1))

    # กรณีชิ้นงานกว้างเกินมาร์ค 57 cm + ค่าอนุโลม ทั้งสองแนว: ยังสร้างมาร์คให้เห็นตำแหน่ง แต่แจ้ง overflow
    fallback_rotated = bool(auto_rotate_enabled and item.height_cm < item.width_cm)
    piece_w = round2(item.height_cm if fallback_rotated else item.width_cm)
    piece_h = round2(item.width_cm if fallback_rotated else item.height_cm)
    return {
        "piece_w": piece_w,
        "piece_h": piece_h,
        "mark_h": round2(max(FIXED_MARK_HEIGHT_CM, piece_h)),
        "cols": 1,
        "rows": 1,
        "capacity": 1,
        "rotated": fallback_rotated,
        "used_w": piece_w,
        "used_h": piece_h,
        "usage": 0.0,
        "force_overflow": True,
    }


def build_fixed_quantity_mark_pair_layout(
    area_items: list[StickerAreaItem],
    print_width_cm: float,
    gap_cm: float,
    margin_left_cm: float = 0.0,
    margin_right_cm: float = 0.0,
    head_margin_cm: float = 0.0,
    tail_margin_cm: float = 0.0,
    auto_rotate_enabled: bool = True,
    preview_limit: int = 900,
    mark_tolerance_cm: float = DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM,
) -> RollLayoutResult:
    """จัดงานที่กรอกจำนวนจริงให้แบ่งเป็นมาร์คคู่ 57 cm และเรียง 2 คอลัมน์

    ใช้สำหรับโหมด "คำนวณจากจำนวนที่กรอก" ตามสเปกงานผลิต:
    - หนึ่งมาร์คกว้าง 57 cm พร้อมคำนวณค่าอนุโลมจาก Sidebar
    - ใช้ความสูง 41 cm เป็นฐานสำหรับคำนวณจำนวนต่อมาร์คเท่านั้น
    - พื้นที่คิดเงิน/ความยาวเข้าม้วนอิงจุดสิ้นสุดของสติกเกอร์จริง ไม่ล็อกขั้นต่ำ 41 cm
    - จำนวนมาร์คปัดขึ้นเป็นเลขคู่เสมอ
    - ช่องไฟระหว่างมาร์ค 4 cm ทั้งแนวนอนและแนวตั้ง
    """
    print_width_cm = round2(print_width_cm)
    margin_left_cm = round2(margin_left_cm)
    margin_right_cm = round2(margin_right_cm)
    head_margin_cm = round2(head_margin_cm)
    tail_margin_cm = round2(tail_margin_cm)
    usable_width_cm = round2(max(0.0, print_width_cm - margin_left_cm - margin_right_cm))
    usable_right_cm = round2(margin_left_cm + usable_width_cm)
    mark_gap_cm = FIXED_QUANTITY_MARK_GAP_CM
    mark_tolerance_cm = round2(max(0.0, float(mark_tolerance_cm)))
    mark_columns = FIXED_QUANTITY_MARK_COLUMNS

    total_quantity = sum(max(0, int(item.quantity)) for item in area_items)
    actual_area_sqcm = round2(sum(item.total_area_sqcm for item in area_items))
    actual_area_sqm = round2(actual_area_sqcm / 10000)
    charged_rule_area_sqm = round2(sum(item.charge_area_sqm for item in area_items))
    face_charge_names = tuple(item.name for item in area_items if item.needs_face_charge)

    placements: list[RollStickerPlacement] = []
    preview_placements: list[RollStickerPlacement] = []
    mark_boxes: list[dict] = []
    item_mark_rows: list[dict] = []
    overflow_count = 0
    rotated_count = 0
    global_mark_index = 0
    y_cursor = round2(head_margin_cm)
    # ใช้ความสูงจริงของสติกเกอร์ที่วางในแต่ละคู่มาร์ค เพื่อให้พื้นที่คิดเงินจบตรงชิ้นงานสุดท้าย
    pair_max_height = 0.0
    pair_mark_position = 0
    pair_rows_count = 0

    mark_x_positions = [round2(margin_left_cm + column * (FIXED_MARK_WIDTH_CM + mark_gap_cm)) for column in range(mark_columns)]

    for item_index, item in enumerate(area_items):
        quantity = max(0, int(item.quantity))
        if quantity <= 0:
            continue

        candidate = fixed_quantity_mark_candidate(
            item,
            gap_cm=gap_cm,
            tolerance_cm=mark_tolerance_cm,
            auto_rotate_enabled=auto_rotate_enabled,
        )
        piece_w = round2(candidate["piece_w"])
        piece_h = round2(candidate["piece_h"])
        mark_h = round2(candidate["mark_h"])
        cols = max(1, int(candidate["cols"]))
        rows = max(1, int(candidate["rows"]))
        capacity = max(1, int(candidate["capacity"]))
        mark_count_raw = int(math.ceil(quantity / capacity))
        mark_count = normalize_even_mark_count(mark_count_raw)
        quantity_distribution = distribute_quantity_full_then_balance_last_pair(quantity, mark_count, capacity)

        item_mark_rows.append({
            "name": item.name,
            "quantity": quantity,
            "capacity_per_mark": capacity,
            "mark_count_raw": mark_count_raw,
            "mark_count": mark_count,
            "mark_height_cm": mark_h,
            "full_mark_used_height_cm": round2(candidate.get("used_h", 0.0)),
            "columns": cols,
            "rows": rows,
            "rotated": bool(candidate.get("rotated", False)),
            "quantity_per_mark_min": min(quantity_distribution) if quantity_distribution else 0,
            "quantity_per_mark_max": max(quantity_distribution) if quantity_distribution else 0,
        })

        for local_mark_index in range(mark_count):
            if pair_mark_position == 0:
                if global_mark_index > 0:
                    # ขึ้นคู่มาร์คใหม่จากจุดจบสติกเกอร์จริงของคู่ก่อนหน้า ไม่ใช้ความสูงขั้นต่ำ 41 cm
                    y_cursor = round2(y_cursor + pair_max_height + mark_gap_cm)
                pair_max_height = 0.0
                pair_rows_count += 1

            column_index = pair_mark_position % mark_columns
            mark_x = mark_x_positions[column_index]
            mark_y = y_cursor
            global_mark_index += 1
            quantity_in_mark = min(capacity, quantity_distribution[local_mark_index])

            actual_rows_in_mark = int(math.ceil(quantity_in_mark / cols)) if quantity_in_mark > 0 else 0
            actual_cols_in_mark = min(cols, quantity_in_mark) if quantity_in_mark > 0 else 0
            actual_mark_used_w = round2(footprint(actual_cols_in_mark, piece_w, gap_cm)) if actual_cols_in_mark > 0 else 0.0
            actual_mark_used_h = round2(footprint(actual_rows_in_mark, piece_h, gap_cm)) if actual_rows_in_mark > 0 else 0.0
            pair_max_height = round2(max(pair_max_height, actual_mark_used_h))

            mark_overflow = mark_x + FIXED_MARK_WIDTH_CM + mark_tolerance_cm > usable_right_cm + 1e-9
            mark_boxes.append({
                "x": mark_x,
                "y": mark_y,
                "width": FIXED_MARK_WIDTH_CM,
                "height": actual_mark_used_h,
                "template_height": mark_h,
                "used_width": actual_mark_used_w,
                "used_height": actual_mark_used_h,
                "label": f"Mark {global_mark_index}",
                "name": item.name,
                "quantity": quantity_in_mark,
                "capacity": capacity,
                "columns": cols,
                "rows": rows,
                "actual_rows": actual_rows_in_mark,
                "overflow": mark_overflow,
            })

            placed_in_mark = 0
            for row in range(rows):
                for col in range(cols):
                    if placed_in_mark >= quantity_in_mark:
                        break
                    x_pos = round2(mark_x + col * (piece_w + gap_cm))
                    y_pos = round2(mark_y + row * (piece_h + gap_cm))
                    overflow = bool(
                        candidate.get("force_overflow", False)
                        or mark_overflow
                        or x_pos + piece_w > mark_x + FIXED_MARK_WIDTH_CM + mark_tolerance_cm + 1e-9
                        or y_pos + piece_h > mark_y + mark_h + mark_tolerance_cm + 1e-9
                    )
                    placement = RollStickerPlacement(
                        name=item.name,
                        shape=item.shape,
                        x_cm=x_pos,
                        y_cm=y_pos,
                        width_cm=piece_w,
                        height_cm=piece_h,
                        item_index=item_index,
                        overflow=overflow,
                        rotated=bool(candidate.get("rotated", False)),
                    )
                    placements.append(placement)
                    if len(preview_placements) < preview_limit:
                        preview_placements.append(placement)
                    if overflow:
                        overflow_count += 1
                    if candidate.get("rotated", False):
                        rotated_count += 1
                    placed_in_mark += 1
                if placed_in_mark >= quantity_in_mark:
                    break

            pair_mark_position = (pair_mark_position + 1) % mark_columns

    if global_mark_index > 0:
        required_length_cm = round2(y_cursor + pair_max_height + tail_margin_cm)
    else:
        required_length_cm = round2(head_margin_cm + tail_margin_cm)

    roll_face_area_sqm = round2(print_width_cm * required_length_cm / 10000) if print_width_cm > 0 else 0.0
    usage = round2(actual_area_sqm / roll_face_area_sqm * 100) if roll_face_area_sqm > 0 else 0.0
    empty_area_sqm = round2(max(0.0, roll_face_area_sqm - actual_area_sqm))
    empty_area_percent = round2(max(0.0, 100.0 - usage)) if roll_face_area_sqm > 0 else 0.0

    mark_summary = {
        "mark_count": int(global_mark_index),
        "pair_count": int(math.ceil(global_mark_index / FIXED_QUANTITY_MARK_COLUMNS)) if global_mark_index else 0,
        "mark_gap_cm": mark_gap_cm,
        "mark_width_cm": FIXED_MARK_WIDTH_CM,
        "mark_tolerance_cm": mark_tolerance_cm,
        "min_mark_height_cm": FIXED_MARK_HEIGHT_CM,
        "calculation_height_mode": "actual_sticker_end",
        "actual_required_length_cm": required_length_cm,
        "item_mark_rows": item_mark_rows,
    }

    return RollLayoutResult(
        print_width_cm=print_width_cm,
        usable_width_cm=usable_width_cm,
        gap_cm=round2(gap_cm),
        margin_left_cm=margin_left_cm,
        margin_right_cm=margin_right_cm,
        head_margin_cm=head_margin_cm,
        tail_margin_cm=tail_margin_cm,
        total_quantity=total_quantity,
        rows_count=pair_rows_count,
        required_length_cm=required_length_cm,
        actual_area_sqcm=actual_area_sqcm,
        actual_area_sqm=actual_area_sqm,
        roll_face_area_sqm=roll_face_area_sqm,
        charged_rule_area_sqm=round2(max(charged_rule_area_sqm, roll_face_area_sqm)),
        material_usage_percent=usage,
        empty_area_sqm=empty_area_sqm,
        empty_area_percent=empty_area_percent,
        waste_threshold_percent=0.0,
        charge_by_page_due_to_waste=False,
        final_charge_area_sqm=roll_face_area_sqm,
        placements=tuple(placements),
        preview_placements=tuple(preview_placements),
        preview_limit=preview_limit,
        overflow_count=overflow_count,
        face_charge_names=face_charge_names,
        rotated_count=rotated_count,
        auto_rotate_enabled=auto_rotate_enabled,
        layout_mode="มาร์คคู่ 57cm",
        strategy_name=FIXED_QUANTITY_STRATEGY,
        mark_boxes=tuple(mark_boxes),
        mark_summary=mark_summary,
    )


def sync_unit_values(prefix: str, fields: tuple[str, ...], unit_key: str, previous_unit_key: str) -> None:
    previous_unit = st.session_state.get(previous_unit_key, CM_UNIT)
    current_unit = st.session_state[unit_key]
    if previous_unit == current_unit:
        return
    factor = 1 / 2.54 if current_unit == INCH_UNIT else 2.54
    for field in fields:
        st.session_state[field] = round2(float(st.session_state[field]) * factor)
    st.session_state[previous_unit_key] = current_unit
    set_action_feedback(f"เปลี่ยนหน่วยเป็น {current_unit}", "edit")


# =========================================================
# Preview figures
# =========================================================
def build_layout_figure(
    sheet_width_cm: float,
    sheet_height_cm: float,
    layout: LayoutResult,
    gap_cm: float,
    tolerance_cm: float,
    sticker_shape: str = QUICK_SHAPE_RECTANGLE,
) -> plt.Figure:
    width = max(sheet_width_cm + tolerance_cm, layout.used_width_cm, 1)
    height = max(sheet_height_cm + tolerance_cm, layout.used_height_cm, 1)
    ratio = width / height if height else 1
    fig_width = min(13, max(7, 8.5 * ratio))

    fig, ax = plt.subplots(figsize=(fig_width, 7), dpi=130)
    fig.patch.set_facecolor("#101114")
    ax.set_facecolor("#101114")

    tolerance_zone = patches.Rectangle(
        (0, 0),
        sheet_width_cm + tolerance_cm,
        sheet_height_cm + tolerance_cm,
        linewidth=1,
        edgecolor="#5a4631",
        facecolor="#2b2117",
        linestyle="--",
        alpha=0.55,
        zorder=0,
    )
    sheet = patches.Rectangle(
        (0, 0),
        sheet_width_cm,
        sheet_height_cm,
        linewidth=1.3,
        edgecolor="#e7eefc",
        facecolor="#1d2128",
        zorder=1,
    )
    ax.add_patch(tolerance_zone)
    ax.add_patch(sheet)

    for item in layout.placements:
        edge_color = "#ffcf8a" if item.overflow else ("#9fd0ff" if item.rotated else "#f6b45c")
        face_color = "#d47f2a" if item.overflow else ("#4c9bd6" if item.rotated else "#f2a33b")
        if normalize_sticker_shape(sticker_shape) == QUICK_SHAPE_CIRCLE:
            radius = item.width_cm / 2
            patch = patches.Circle(
                (item.x_cm + radius, item.y_cm + radius),
                radius=radius,
                linewidth=0.8,
                edgecolor=edge_color,
                facecolor=face_color,
                alpha=0.86 if item.overflow else 0.92,
                zorder=3,
            )
        else:
            patch = patches.FancyBboxPatch(
                (item.x_cm, item.y_cm),
                item.width_cm,
                item.height_cm,
                boxstyle="round,pad=0.015,rounding_size=0.12",
                linewidth=0.8,
                edgecolor=edge_color,
                facecolor=face_color,
                alpha=0.86 if item.overflow else 0.92,
                zorder=3,
            )
        ax.add_patch(patch)
        if layout.layout_mode == "mixed":
            ax.text(
                item.x_cm + item.width_cm / 2,
                item.y_cm + item.height_cm / 2,
                "90°" if item.rotated else "0°",
                color="#101114",
                fontsize=6.8,
                ha="center",
                va="center",
                weight="bold",
                zorder=4,
            )

    ax.set_xlim(-max(1, width * 0.035), width + max(1, width * 0.055))
    ax.set_ylim(-max(1, height * 0.035), height + max(1, height * 0.055))
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.text(0, sheet_height_cm + max(0.5, height * 0.025), f"Material {sheet_width_cm:.2f} x {sheet_height_cm:.2f} cm", color="#d7dde8", fontsize=10, weight="bold")
    if tolerance_cm > 0:
        ax.text(sheet_width_cm + tolerance_cm, sheet_height_cm + tolerance_cm + max(0.4, height * 0.012), f"Tolerance +{tolerance_cm:.2f} cm", color="#c98b45", fontsize=8.5, ha="right")
    if layout.layout_mode == "mixed":
        ax.text(0, -max(0.8, height * 0.035), "Orange = normal / Blue = rotated 90°", color="#aeb5c1", fontsize=8.5, ha="left", va="top")
    return fig


def build_roll_preview_figure(layout: RollLayoutResult, area_items: list[StickerAreaItem], area_unit: str, target_area_sqm: float | None = None) -> plt.Figure:
    preview_length_cm = get_roll_preview_length_cm(layout)
    ratio = layout.print_width_cm / preview_length_cm if preview_length_cm > 0 else 1
    fig_width = min(13, max(7, 8.5 * ratio))
    fig_height = min(11, max(5.2, 8.5 / max(ratio, 0.45)))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=130)
    fig.patch.set_facecolor("#101114")
    ax.set_facecolor("#101114")

    roll_rect = patches.Rectangle(
        (0, 0),
        layout.print_width_cm,
        preview_length_cm,
        linewidth=1.25,
        edgecolor="#e7eefc",
        facecolor="#1d2128",
        zorder=1,
    )
    ax.add_patch(roll_rect)

    # Margin zones
    margin_color = "#2b2117"
    if layout.margin_left_cm > 0:
        ax.add_patch(patches.Rectangle((0, 0), layout.margin_left_cm, preview_length_cm, linewidth=0, facecolor=margin_color, alpha=0.62, zorder=2))
    if layout.margin_right_cm > 0:
        ax.add_patch(patches.Rectangle((layout.print_width_cm - layout.margin_right_cm, 0), layout.margin_right_cm, preview_length_cm, linewidth=0, facecolor=margin_color, alpha=0.62, zorder=2))
    if layout.head_margin_cm > 0:
        ax.add_patch(patches.Rectangle((0, 0), layout.print_width_cm, min(layout.head_margin_cm, preview_length_cm), linewidth=0, facecolor=margin_color, alpha=0.46, zorder=2))
    if layout.tail_margin_cm > 0 and layout.required_length_cm <= preview_length_cm:
        tail_y = max(0.0, layout.required_length_cm - layout.tail_margin_cm)
        ax.add_patch(patches.Rectangle((0, tail_y), layout.print_width_cm, layout.tail_margin_cm, linewidth=0, facecolor=margin_color, alpha=0.46, zorder=2))

    draw_cut_guides_matplotlib(ax, layout, preview_length_cm)
    draw_target_area_limit_matplotlib(ax, layout, preview_length_cm, target_area_sqm)

    for mark in getattr(layout, "mark_boxes", tuple()):
        mark_x = float(mark.get("x", 0.0))
        mark_y = float(mark.get("y", 0.0))
        mark_w = float(mark.get("width", FIXED_MARK_WIDTH_CM))
        mark_h = float(mark.get("height", FIXED_MARK_HEIGHT_CM))
        if mark_y > preview_length_cm:
            continue
        edge = "#ff7166" if mark.get("overflow") else "#94a3b8"
        ax.add_patch(
            patches.Rectangle(
                (mark_x, mark_y),
                mark_w,
                mark_h,
                linewidth=1.1,
                edgecolor=edge,
                facecolor="#0b1220",
                linestyle="--",
                alpha=0.55,
                zorder=2.4,
            )
        )
        if mark_h >= 10:
            ax.text(
                mark_x + 1.1,
                mark_y + 2.4,
                f"{mark.get('label', 'Mark')} · {int(mark.get('quantity', 0))}/{int(mark.get('capacity', 0))}",
                color="#cbd5e1",
                fontsize=6.4,
                ha="left",
                va="top",
                zorder=5,
                fontproperties=get_thai_font(bold=True),
            )

    legend_entries = build_roll_legend_entries(area_items, area_unit, max_items=16)
    size_color_map = build_size_color_map(area_items)
    legend_width_cm = max(24.0, layout.print_width_cm * 0.33) if legend_entries else 0.0
    legend_x = layout.print_width_cm + max(3.0, layout.print_width_cm * 0.035)

    for item in layout.preview_placements:
        if item.y_cm > preview_length_cm:
            continue

        item_info = area_items[item.item_index]
        display_name = safe_preview_label(item.name, f"Item {item.item_index + 1}")
        display_w = from_cm(item.width_cm, area_unit)
        display_h = from_cm(item.height_cm, area_unit)
        area_text = format_piece_area(item_info.single_area_sqcm)

        face_color = preview_color_for_size(item_info.width_cm, item_info.height_cm, item.item_index, item.overflow, size_color_map)
        edge_color = "#ff7166" if item.overflow else ("#9fd0ff" if item.rotated else "#101114")

        if normalize_sticker_shape(getattr(item, "shape", getattr(item_info, "shape", QUICK_SHAPE_RECTANGLE))) == QUICK_SHAPE_CIRCLE:
            radius = item.width_cm / 2
            patch = patches.Circle(
                (item.x_cm + radius, item.y_cm + radius),
                radius=radius,
                linewidth=0.85,
                edgecolor=edge_color,
                facecolor=face_color,
                alpha=0.92,
                zorder=3,
            )
        else:
            patch = patches.FancyBboxPatch(
                (item.x_cm, item.y_cm),
                item.width_cm,
                item.height_cm,
                boxstyle="round,pad=0.01,rounding_size=0.18",
                linewidth=0.85,
                edgecolor=edge_color,
                facecolor=face_color,
                alpha=0.92,
                zorder=3,
            )
        ax.add_patch(patch)

        if SHOW_PREVIEW_TEXT_ON_PIECES and item.width_cm >= 16 and item.height_cm >= 9:
            rotate_label = " / R90" if item.rotated else ""
            label = (
                f"{display_name}{rotate_label}\n"
                f"{display_w:.2f} x {display_h:.2f} {unit_label(area_unit)}\n"
                f"Area {area_text}"
            )
            ax.text(
                item.x_cm + item.width_cm / 2,
                item.y_cm + item.height_cm / 2,
                label,
                color="#101114",
                fontsize=6.6,
                ha="center",
                va="center",
                zorder=4,
                linespacing=1.15,
                wrap=True,
                fontproperties=get_thai_font(bold=True),
            )
        elif SHOW_PREVIEW_TEXT_ON_PIECES and item.width_cm >= 10 and item.height_cm >= 5.5:
            ax.text(
                item.x_cm + item.width_cm / 2,
                item.y_cm + item.height_cm / 2,
                f"{display_name}{' R90' if item.rotated else ''}",
                color="#101114",
                fontsize=6.5,
                ha="center",
                va="center",
                zorder=4,
                fontproperties=get_thai_font(bold=True),
            )

    if layout.required_length_cm > preview_length_cm:
        ax.text(
            layout.print_width_cm / 2,
            preview_length_cm - max(4, preview_length_cm * 0.035),
            f"แสดง Preview ช่วงแรก {preview_length_cm:.2f} cm จากความยาวรวม {layout.required_length_cm:.2f} cm",
            color="#ffcf8a",
            fontsize=8.5,
            ha="center",
            va="center",
            zorder=6,
            bbox=dict(facecolor="#101114", edgecolor="#5a4631", boxstyle="round,pad=0.35", alpha=0.86),
            fontproperties=get_thai_font(bold=True),
        )

    ax.text(
        0,
        -max(1.8, preview_length_cm * 0.04),
        f"Print width {layout.print_width_cm:.2f} cm / Usable {layout.usable_width_cm:.2f} cm / Roll length {layout.required_length_cm:.2f} cm / Levels {layout.rows_count:,}",
        color="#d7dde8",
        fontsize=9.0,
        ha="left",
        va="top",
        fontproperties=get_thai_font(bold=True),
    )

    if layout.auto_rotate_enabled:
        ax.text(
            layout.print_width_cm,
            -max(1.8, preview_length_cm * 0.04),
            f"Auto Rotate: {layout.rotated_count:,} pcs",
            color="#aeb5c1",
            fontsize=8.2,
            ha="right",
            va="top",
            fontproperties=get_thai_font(bold=False),
        )

    if legend_entries:
        legend_row_h = max(6.0, min(9.0, preview_length_cm * 0.045))
        legend_pad = max(1.6, legend_row_h * 0.32)
        legend_height = min(preview_length_cm - 2.0, legend_pad * 2.3 + legend_row_h * len(legend_entries))
        legend_bg = patches.FancyBboxPatch(
            (legend_x - legend_pad, 0.8),
            legend_width_cm,
            legend_height,
            boxstyle="round,pad=0.02,rounding_size=0.75",
            linewidth=0.8,
            edgecolor="#303846",
            facecolor="#f8fafc",
            alpha=0.96,
            zorder=7,
        )
        ax.add_patch(legend_bg)
        ax.text(
            legend_x,
            0.8 + legend_pad,
            "สรุปสีใน Preview",
            color="#475569",
            fontsize=8.6,
            ha="left",
            va="top",
            zorder=8,
            fontproperties=get_thai_font(bold=True),
        )
        start_y = 0.8 + legend_pad + legend_row_h * 0.9
        square_size = max(1.5, legend_row_h * 0.30)
        for idx, entry in enumerate(legend_entries):
            y = start_y + idx * legend_row_h
            if y > preview_length_cm - legend_row_h * 0.35:
                break
            ax.add_patch(
                patches.Rectangle(
                    (legend_x, y - square_size * 0.55),
                    square_size,
                    square_size,
                    linewidth=0,
                    facecolor=entry["color"],
                    zorder=8,
                )
            )
            ax.text(
                legend_x + square_size + max(0.9, legend_width_cm * 0.035),
                y - square_size * 0.15,
                entry["name"],
                color="#6b7280",
                fontsize=7.6,
                ha="left",
                va="center",
                zorder=8,
                fontproperties=get_thai_font(bold=True),
            )
            ax.text(
                legend_x + square_size + max(0.9, legend_width_cm * 0.035),
                y + square_size * 0.82,
                entry["detail"],
                color="#94a3b8",
                fontsize=6.4,
                ha="left",
                va="center",
                zorder=8,
                fontproperties=get_thai_font(bold=False),
            )

    ax.set_xlim(
        -max(1, layout.print_width_cm * 0.025),
        layout.print_width_cm + max(1, layout.print_width_cm * 0.025) + legend_width_cm + (max(3.0, layout.print_width_cm * 0.035) if legend_entries else 0),
    )
    ax.set_ylim(preview_length_cm + max(1, preview_length_cm * 0.05), -max(3.2, preview_length_cm * 0.10))
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return fig


def build_roll_preview_plotly(layout: RollLayoutResult, area_items: list[StickerAreaItem], area_unit: str, target_area_sqm: float | None = None):
    """สร้าง Preview หน้าม้วนแบบ Interactive โทน Premium Production / Dark Neon"""
    if not PLOTLY_AVAILABLE or go is None:
        return None

    preview_length_cm = get_roll_preview_length_cm(layout)
    if preview_length_cm <= 0 or layout.print_width_cm <= 0:
        return None

    display_height = min(860, max(500, int(preview_length_cm / max(layout.print_width_cm, 1) * 650)))
    display_height = max(460, min(display_height, 860))

    legend_entries = build_roll_legend_entries(area_items, area_unit, max_items=18)
    size_color_map = build_size_color_map(area_items)

    fig = go.Figure()

    # =====================================================
    # Background / roll face
    # =====================================================
    fig.add_shape(
        type="rect",
        x0=-layout.print_width_cm * 0.025,
        y0=-preview_length_cm * 0.035,
        x1=layout.print_width_cm * 1.025,
        y1=preview_length_cm * 1.045,
        line=dict(width=0),
        fillcolor="rgba(2,6,23,1)",
        layer="below",
    )
    fig.add_shape(
        type="rect",
        x0=0,
        y0=0,
        x1=layout.print_width_cm,
        y1=preview_length_cm,
        line=dict(color="rgba(226,232,240,.92)", width=1.4),
        fillcolor="rgba(15,23,42,.94)",
        layer="below",
    )

    # Usable area highlight
    usable_x0 = layout.margin_left_cm
    usable_x1 = layout.print_width_cm - layout.margin_right_cm
    if usable_x1 > usable_x0:
        fig.add_shape(
            type="rect",
            x0=usable_x0,
            y0=min(layout.head_margin_cm, preview_length_cm),
            x1=usable_x1,
            y1=preview_length_cm if layout.required_length_cm > preview_length_cm else max(0, layout.required_length_cm - layout.tail_margin_cm),
            line=dict(color="rgba(56,189,248,.18)", width=1),
            fillcolor="rgba(8,47,73,.18)",
            layer="below",
        )

    # Margin zones
    margin_fill = "rgba(251,146,60,0.17)"
    margin_line = "rgba(251,146,60,0.24)"
    if layout.margin_left_cm > 0:
        fig.add_shape(type="rect", x0=0, y0=0, x1=layout.margin_left_cm, y1=preview_length_cm, line=dict(color=margin_line, width=.5), fillcolor=margin_fill, layer="below")
    if layout.margin_right_cm > 0:
        fig.add_shape(type="rect", x0=layout.print_width_cm - layout.margin_right_cm, y0=0, x1=layout.print_width_cm, y1=preview_length_cm, line=dict(color=margin_line, width=.5), fillcolor=margin_fill, layer="below")
    if layout.head_margin_cm > 0:
        fig.add_shape(type="rect", x0=0, y0=0, x1=layout.print_width_cm, y1=min(layout.head_margin_cm, preview_length_cm), line=dict(color=margin_line, width=.5), fillcolor="rgba(251,146,60,0.12)", layer="below")
    if layout.tail_margin_cm > 0 and layout.required_length_cm <= preview_length_cm:
        tail_y = max(0.0, layout.required_length_cm - layout.tail_margin_cm)
        fig.add_shape(type="rect", x0=0, y0=tail_y, x1=layout.print_width_cm, y1=layout.required_length_cm, line=dict(color=margin_line, width=.5), fillcolor="rgba(251,146,60,0.12)", layer="below")

    draw_cut_guides_plotly(fig, layout, preview_length_cm)
    draw_target_area_limit_plotly(fig, layout, preview_length_cm, target_area_sqm)

    # =====================================================
    # Mark boxes: โหมดแบ่งมาร์คคู่
    # =====================================================
    for mark in getattr(layout, "mark_boxes", tuple()):
        mark_x = float(mark.get("x", 0.0))
        mark_y = float(mark.get("y", 0.0))
        mark_w = float(mark.get("width", FIXED_MARK_WIDTH_CM))
        mark_h = float(mark.get("height", FIXED_MARK_HEIGHT_CM))
        if mark_y > preview_length_cm:
            continue

        mark_overflow = bool(mark.get("overflow"))
        mark_edge = "rgba(248,113,113,.90)" if mark_overflow else "rgba(148,163,184,.58)"
        fig.add_shape(
            type="rect",
            x0=mark_x,
            y0=mark_y,
            x1=mark_x + mark_w,
            y1=mark_y + mark_h,
            line=dict(color=mark_edge, width=1.15, dash="dash"),
            fillcolor="rgba(2,6,23,0.20)",
            layer="below",
        )
        if mark_h >= 10:
            fig.add_annotation(
                x=mark_x + 1.4,
                y=mark_y + 2.4,
                text=f"{html.escape(str(mark.get('label', 'Mark')))} · {int(mark.get('quantity', 0))}/{int(mark.get('capacity', 0))}",
                showarrow=False,
                xanchor="left",
                yanchor="top",
                font=dict(color="#cbd5e1", size=9, family="Noto Sans Thai, Inter, sans-serif"),
                bgcolor="rgba(15,23,42,0.72)",
                bordercolor="rgba(148,163,184,0.20)",
                borderwidth=1,
                borderpad=4,
            )

    # =====================================================
    # Pieces
    # =====================================================
    hover_x: list[float] = []
    hover_y: list[float] = []
    hover_texts: list[str] = []
    label_x: list[float] = []
    label_y: list[float] = []
    label_texts: list[str] = []
    label_count = 0
    label_limit = int(st.session_state.get("roll_preview_label_limit", 120))
    show_piece_labels = bool(st.session_state.get("roll_preview_show_labels", True))

    visible_placements = [item for item in layout.preview_placements if item.y_cm <= preview_length_cm]

    for item in visible_placements:
        if item.item_index < 0 or item.item_index >= len(area_items):
            continue

        item_info = area_items[item.item_index]
        display_name = safe_preview_label(item.name, f"Item {item.item_index + 1}")
        display_w = from_cm(item.width_cm, area_unit)
        display_h = from_cm(item.height_cm, area_unit)
        area_text = format_piece_area(item_info.single_area_sqcm)
        status = "⚠️ กว้างเกินหน้าพิมพ์" if item.overflow else ("↻ หมุน 90°" if item.rotated else "พร้อมผลิต")

        face_color = preview_color_for_size(item_info.width_cm, item_info.height_cm, item.item_index, item.overflow, size_color_map)
        edge_color = "rgba(248,113,113,1)" if item.overflow else ("rgba(125,211,252,1)" if item.rotated else "rgba(255,255,255,.70)")
        glow_color = "rgba(248,113,113,.22)" if item.overflow else ("rgba(125,211,252,.18)" if item.rotated else "rgba(255,255,255,.10)")

        shape_type = "circle" if normalize_sticker_shape(getattr(item, "shape", getattr(item_info, "shape", QUICK_SHAPE_RECTANGLE))) == QUICK_SHAPE_CIRCLE else "rect"
        # glow/shadow layer
        fig.add_shape(
            type=shape_type,
            x0=item.x_cm - 0.22,
            y0=item.y_cm - 0.22,
            x1=item.x_cm + item.width_cm + 0.22,
            y1=item.y_cm + item.height_cm + 0.22,
            line=dict(width=0),
            fillcolor=glow_color,
            layer="above",
        )
        # main piece
        fig.add_shape(
            type=shape_type,
            x0=item.x_cm,
            y0=item.y_cm,
            x1=item.x_cm + item.width_cm,
            y1=item.y_cm + item.height_cm,
            line=dict(color=edge_color, width=1.05),
            fillcolor=face_color,
            opacity=0.94,
            layer="above",
        )

        # R90 badge
        if item.rotated and item.width_cm >= 5 and item.height_cm >= 3:
            fig.add_annotation(
                x=item.x_cm + min(item.width_cm - .5, 4.8),
                y=item.y_cm + min(item.height_cm - .4, 2.4),
                text="R90",
                showarrow=False,
                xanchor="right",
                yanchor="middle",
                font=dict(color="#082f49", size=8, family="Inter, sans-serif"),
                bgcolor="rgba(186,230,253,.92)",
                bordercolor="rgba(14,165,233,.55)",
                borderwidth=1,
                borderpad=2,
            )

        hover_x.append(item.x_cm + item.width_cm / 2)
        hover_y.append(item.y_cm + item.height_cm / 2)
        hover_texts.append(
            "<b>{}</b><br>ขนาดวางจริง: {:.2f} × {:.2f} {}<br>พื้นที่ต่อชิ้น: {}<br>ตำแหน่ง: x {:.2f}, y {:.2f} cm<br>สถานะ: {}".format(
                html.escape(display_name),
                display_w,
                display_h,
                unit_label(area_unit),
                area_text,
                item.x_cm,
                item.y_cm,
                status,
            )
        )

        if show_piece_labels and label_count < label_limit:
            if item.width_cm >= 13 and item.height_cm >= 6.2:
                label_x.append(item.x_cm + item.width_cm / 2)
                label_y.append(item.y_cm + item.height_cm / 2)
                label_texts.append(f"<b>{html.escape(display_name)}</b>{'<br>R90' if item.rotated else ''}")
                label_count += 1
            elif item.width_cm >= 8 and item.height_cm >= 4.8 and len(visible_placements) <= 80:
                label_x.append(item.x_cm + item.width_cm / 2)
                label_y.append(item.y_cm + item.height_cm / 2)
                label_texts.append(f"<b>{html.escape(display_name)}</b>")
                label_count += 1

    # Hover layer
    if hover_x:
        fig.add_trace(
            go.Scatter(
                x=hover_x,
                y=hover_y,
                mode="markers",
                marker=dict(size=20, color="rgba(255,255,255,0.01)", line=dict(width=0)),
                hovertext=hover_texts,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )

    # Text labels
    if label_x:
        fig.add_trace(
            go.Scatter(
                x=label_x,
                y=label_y,
                mode="text",
                text=label_texts,
                textfont=dict(color="#020617", size=10, family="Noto Sans Thai, Inter, sans-serif"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Preview length warning
    if layout.required_length_cm > preview_length_cm:
        fig.add_annotation(
            x=layout.print_width_cm / 2,
            y=preview_length_cm - max(4, preview_length_cm * 0.035),
            text=f"แสดง Preview ช่วงแรก {preview_length_cm:.2f} cm จากความยาวรวม {layout.required_length_cm:.2f} cm",
            showarrow=False,
            font=dict(color="#facc15", size=12, family="Noto Sans Thai, Inter, sans-serif"),
            bgcolor="rgba(2,6,23,0.92)",
            bordercolor="rgba(250,204,21,.42)",
            borderwidth=1,
            borderpad=8,
        )

    # Header annotations
    fig.add_annotation(
        x=0,
        y=preview_length_cm + max(5, preview_length_cm * 0.035),
        xanchor="left",
        yanchor="top",
        text=(
            f"<b>HUGPRINT Production Preview</b> · Print {layout.print_width_cm:.2f} cm / "
            f"Usable {layout.usable_width_cm:.2f} cm / Length {layout.required_length_cm:.2f} cm / Rows {layout.rows_count:,}"
        ),
        showarrow=False,
        font=dict(color="#e2e8f0", size=12, family="Noto Sans Thai, Inter, sans-serif"),
    )

    right_status = []
    if layout.auto_rotate_enabled:
        right_status.append(f"Auto Rotate {layout.rotated_count:,} pcs")
    if layout.overflow_count:
        right_status.append(f"Overflow {layout.overflow_count:,} pcs")
    if not right_status:
        right_status.append("Ready for production")

    fig.add_annotation(
        x=layout.print_width_cm,
        y=preview_length_cm + max(5, preview_length_cm * 0.035),
        xanchor="right",
        yanchor="top",
        text=" · ".join(right_status),
        showarrow=False,
        font=dict(color="#94a3b8", size=11, family="Noto Sans Thai, Inter, sans-serif"),
    )

    # Legend traces
    for entry in legend_entries:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(symbol="square", size=11, color=entry["color"], line=dict(color="rgba(255,255,255,.72)", width=.8)),
                name=f"{entry['name']}  {entry['detail']}",
                hoverinfo="skip",
                showlegend=True,
            )
        )

    # Layout
    fig.update_layout(
        height=display_height,
        margin=dict(l=14, r=220 if legend_entries else 14, t=24, b=60),
        paper_bgcolor="#020617",
        plot_bgcolor="#020617",
        font=dict(color="#e5e7eb", family="Noto Sans Thai, Inter, sans-serif"),
        hoverlabel=dict(
            bgcolor="rgba(15,23,42,.96)",
            bordercolor="#facc15",
            font=dict(color="#f8fafc", size=12, family="Noto Sans Thai, Inter, sans-serif"),
        ),
        legend=dict(
            title=dict(text="สรุป Size สติกเกอร์", font=dict(size=12, color="#f8fafc")),
            orientation="v",
            x=1.02,
            y=1,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(15,23,42,0.94)",
            bordercolor="rgba(148,163,184,0.25)",
            borderwidth=1,
            font=dict(size=10, color="#cbd5e1", family="Noto Sans Thai, Inter, sans-serif"),
            itemclick=False,
            itemdoubleclick=False,
        ),
        dragmode="pan",
        uirevision="roll-preview-premium",
    )
    fig.update_xaxes(
        range=[-max(1, layout.print_width_cm * 0.025), layout.print_width_cm + max(1, layout.print_width_cm * 0.025)],
        showgrid=True,
        gridcolor="rgba(148,163,184,0.10)",
        zeroline=False,
        title_text="หน้ากว้างพิมพ์ (cm)",
        tickfont=dict(size=10, color="#94a3b8"),
        title_font=dict(color="#cbd5e1", size=11),
    )
    fig.update_yaxes(
        range=[preview_length_cm + max(6, preview_length_cm * 0.08), -max(3.2, preview_length_cm * 0.08)],
        showgrid=True,
        gridcolor="rgba(148,163,184,0.10)",
        zeroline=False,
        title_text="ความยาวเข้าม้วน (cm)",
        tickfont=dict(size=10, color="#94a3b8"),
        title_font=dict(color="#cbd5e1", size=11),
        scaleanchor="x",
        scaleratio=1,
    )

    return fig


# =========================================================
# Table helpers
# =========================================================
def area_table_rows(
    area_items: list[StickerAreaItem],
    base_items: list[StickerAreaItem] | None = None,
    mark_count: int | None = None,
) -> list[dict]:
    rows = []
    base_items = base_items or []
    target_mode = bool(base_items and mark_count)

    for index, item in enumerate(area_items):
        row = {
            "Size": item.name,
            "รูปทรง": item.shape,
            "ขนาด": sticker_shape_dimension_text(item.shape, item.width_cm, item.height_cm),
            "กว้าง (cm)": f"{item.width_cm:.2f}",
            "ยาว (cm)": f"{item.height_cm:.2f}",
            "จำนวน": f"{item.quantity:,}",
            "พื้นที่จริง (ตรม.)": f"{item.total_area_sqm:.2f}",
            "พื้นที่คิดตามกฎ (ตรม.)": f"{item.charge_area_sqm:.2f}",
            "หมายเหตุ": "คิดตามหน้าพิมพ์" if item.needs_face_charge else item.charge_mode,
        }
        if target_mode:
            base_qty = base_items[index].quantity if index < len(base_items) else 0
            row = {
                "Size": item.name,
                "รูปทรง": item.shape,
                "ขนาด": sticker_shape_dimension_text(item.shape, item.width_cm, item.height_cm),
                "กว้าง (cm)": f"{item.width_cm:.2f}",
                "ยาว (cm)": f"{item.height_cm:.2f}",
                "จำนวนต่อชุด/มาร์ค": f"{base_qty:,}",
                "จำนวนชุด/มาร์ค": f"{int(mark_count):,}",
                "จำนวนรวม": f"{item.quantity:,}",
                "พื้นที่จริง (ตรม.)": f"{item.total_area_sqm:.2f}",
                "พื้นที่คิดตามกฎ (ตรม.)": f"{item.charge_area_sqm:.2f}",
                "หมายเหตุ": "คิดตามหน้าพิมพ์" if item.needs_face_charge else item.charge_mode,
            }
        rows.append(row)
    return rows


def get_fixed_mark_count() -> int:
    """คืนค่าจำนวนมาร์คจาก Preset พื้นที่คงที่ 57×41

    โหมดนี้ล็อกให้เลือกเฉพาะ 2 หรือ 4 มาร์ค ตามพื้นที่มาตรฐาน:
    ครึ่ง ตรม. = 2 มาร์ค / 1 ตรม. = 4 มาร์ค
    """
    preset = st.session_state.get("fixed_mark_area_preset", DEFAULT_FIXED_MARK_AREA_PRESET)
    if preset not in FIXED_MARK_AREA_PRESETS:
        preset = DEFAULT_FIXED_MARK_AREA_PRESET
        st.session_state["fixed_mark_area_preset"] = preset

    mark_count = int(FIXED_MARK_AREA_PRESETS[preset])
    st.session_state["fixed_mark_custom_count"] = mark_count
    return mark_count


def fixed_mark_area_label(mark_count: int) -> str:
    if mark_count == 2:
        return "ครึ่ง ตรม."
    if mark_count == 4:
        return "1 ตรม."
    material_area_sqm = FIXED_MARK_WIDTH_CM * FIXED_MARK_HEIGHT_CM * mark_count / 10000
    return f"{mark_count:,} มาร์ค ≈ {material_area_sqm:.2f} ตรม."


def _current_area_item_labels_for_select() -> list[str]:
    """สร้างรายการ Size จาก sidebar สำหรับ selectbox โดยไม่ต้องอ่านเป็น MixedMarkItem ก่อน"""
    labels: list[str] = []
    for index, item_id in enumerate(st.session_state.get("area_item_ids", []), start=1):
        item_id = int(item_id)
        set_area_item_defaults(item_id)
        name_key, width_key, height_key, _ = area_item_keys(item_id)
        name = str(st.session_state.get(name_key, f"Size {item_id}")).strip() or f"Size {item_id}"
        width_value = round2(st.session_state.get(width_key, 0.0))
        height_value = round2(st.session_state.get(height_key, 0.0))
        labels.append(f"{item_id} | {name} ({width_value:.2f}×{height_value:.2f})")
    return labels


def _selected_fill_item_id_from_label() -> int | None:
    label = str(st.session_state.get("mixed_fill_selected_label", ""))
    try:
        return int(label.split("|", 1)[0].strip())
    except Exception:
        return None


def _parse_custom_ratio_values(count: int) -> list[int]:
    """อ่านอัตราส่วนรวมจากช่องเดียว เช่น 2:1:1 / 2,1,1 / 2 1 1"""
    raw = str(st.session_state.get("mixed_ratio_custom_text", "")).strip()
    if not raw:
        return [1] * count
    parts = [part for part in re.split(r"[,:/\s]+", raw) if part.strip()]
    values: list[int] = []
    for part in parts[:count]:
        try:
            values.append(max(1, int(float(part))))
        except Exception:
            values.append(1)
    while len(values) < count:
        values.append(1)
    return values[:count]


def _mixed_ratio_values_for_raw_items(raw_items: list[dict]) -> dict[int, int]:
    """กำหนดอัตราส่วนจากตัวเลือกกลาง ไม่ต้องกรอกในแต่ละ Size

    ห้ามเขียนกลับไปที่ st.session_state["mixed_ratio_mode"] ในฟังก์ชันนี้
    เพราะฟังก์ชันนี้ถูกเรียกหลัง selectbox key="mixed_ratio_mode" ถูกสร้างแล้ว
    Streamlit จะ error: cannot be modified after the widget is instantiated.
    """
    if not raw_items:
        return {}
    mode = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))
    count = len(raw_items)
    ratios = {int(row["item_id"]): 1 for row in raw_items}

    if mode == MIXED_RATIO_MODE_CUSTOM:
        legacy_values = _parse_custom_ratio_values(count)
        for index, row in enumerate(raw_items):
            item_id = int(row["item_id"])
            weight_key = f"mixed_ratio_weight_{item_id}"
            if weight_key not in st.session_state:
                st.session_state[weight_key] = max(1, int(legacy_values[index] if index < len(legacy_values) else 1))
            ratios[item_id] = max(1, int(st.session_state.get(weight_key, 1)))
        return ratios

    if mode == MIXED_RATIO_MODE_FIRST_MORE:
        first_id = int(raw_items[0]["item_id"])
        ratios[first_id] = 2
        return ratios

    if mode == MIXED_RATIO_MODE_SMALL_MORE:
        ordered = sorted(raw_items, key=lambda row: (row["width_cm"] * row["height_cm"], row["item_id"]))
        for rank, row in enumerate(ordered):
            ratios[int(row["item_id"])] = max(1, count - rank)
        return ratios

    if mode == MIXED_RATIO_MODE_LARGE_MORE:
        ordered = sorted(raw_items, key=lambda row: (-(row["width_cm"] * row["height_cm"]), row["item_id"]))
        for rank, row in enumerate(ordered):
            ratios[int(row["item_id"])] = max(1, count - rank)
        return ratios

    return ratios


def collect_fixed_mark_mixed_size_inputs(area_unit: str) -> list[MixedMarkItem]:
    """อ่านชื่อ/ขนาด สำหรับโหมดคำนวนพื้นที่หลายขนาด และใส่อัตราส่วนจากตัวเลือกกลาง"""
    raw_items: list[dict] = []
    for item_id in st.session_state.get("area_item_ids", []):
        item_id = int(item_id)
        set_area_item_defaults(item_id)
        name_key, width_key, height_key, _ = area_item_keys(item_id)
        shape_key = area_shape_key(item_id)
        width_value = round2(st.session_state.get(width_key, 0.0))
        height_value = round2(st.session_state.get(height_key, 0.0))
        shape = normalize_sticker_shape(st.session_state.get(shape_key, QUICK_SHAPE_RECTANGLE))
        if shape == QUICK_SHAPE_CIRCLE:
            height_value = width_value
            st.session_state[height_key] = width_value
        if width_value <= 0 or height_value <= 0:
            continue
        raw_items.append(
            {
                "item_id": item_id,
                "name": str(st.session_state.get(name_key, f"Size {item_id}")).strip() or f"Size {item_id}",
                "shape": shape,
                "width_cm": to_cm(width_value, area_unit),
                "height_cm": to_cm(height_value, area_unit),
            }
        )

    ratio_map = _mixed_ratio_values_for_raw_items(raw_items)
    items: list[MixedMarkItem] = []
    for row in raw_items:
        items.append(
            MixedMarkItem(
                name=row["name"],
                shape=normalize_sticker_shape(row.get("shape", QUICK_SHAPE_RECTANGLE)),
                width_cm=row["width_cm"],
                height_cm=row["height_cm"],
                ratio=max(1, int(ratio_map.get(int(row["item_id"]), 1))),
                item_id=int(row["item_id"]),
            )
        )
    return items


def mixed_ratio_label(items: list[MixedMarkItem]) -> str:
    if not items:
        return "-"
    mode = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))
    values = " : ".join(str(max(1, int(item.ratio))) for item in items)
    names = " / ".join(safe_preview_label(item.name, f"Size {index + 1}", 12) for index, item in enumerate(items))
    return f"{mode} ({values}) · {names}"



def get_mixed_mark_gap_cm() -> float:
    """อ่านช่องไฟของโหมด Mixed Mark เป็น cm — UI และคำนวณใช้หน่วยเดียวกัน"""
    if "mixed_mark_gap_cm" in st.session_state:
        gap_cm = round2(st.session_state.get("mixed_mark_gap_cm", DEFAULT_MIXED_MARK_GAP_CM))
    else:
        gap_cm = round2(st.session_state.get("mixed_mark_gap_mm", DEFAULT_MIXED_MARK_GAP_MM) / 10.0)
    return round2(max(0.0, gap_cm))


def get_mixed_mark_layout_style() -> str:
    style = st.session_state.get("mixed_mark_layout_style", MIXED_MARK_LAYOUT_STYLE_BLOCK)
    return style if style in MIXED_MARK_LAYOUT_STYLES else MIXED_MARK_LAYOUT_STYLE_BLOCK


def _mixed_group_order(items: list[MixedMarkItem], layout_style: str) -> list[int]:
    """เรียงลำดับ Size สำหรับผลิต: ใหญ่ก่อนเพื่อให้แถวเป็นระเบียบและคำนวณเร็ว"""
    indexes = list(range(len(items)))
    if layout_style == MIXED_MARK_LAYOUT_STYLE_COMPACT:
        indexes.sort(key=lambda idx: (-(items[idx].width_cm * items[idx].height_cm), -max(items[idx].width_cm, items[idx].height_cm), -items[idx].ratio, idx))
    else:
        indexes.sort(key=lambda idx: (-max(items[idx].height_cm, items[idx].width_cm), -(items[idx].width_cm * items[idx].height_cm), idx))
    return indexes


def _mixed_orientation_for_item(
    item: MixedMarkItem,
    usable_width_cm: float,
    gap_cm: float,
    auto_rotate_enabled: bool,
    layout_style: str,
) -> tuple[float, float, bool]:
    """เลือกแนววางต่อ Size แบบคงที่ทั้งกลุ่ม เพื่อให้ Preview อ่านง่าย"""
    options = orientation_options(item, auto_rotate_enabled)
    scored = []
    for width_cm, height_cm, rotated in options:
        width_cm = round2(width_cm)
        height_cm = round2(height_cm)
        if width_cm <= 0 or height_cm <= 0:
            continue
        columns = max(0, int(math.floor((usable_width_cm + gap_cm) / (width_cm + gap_cm))))
        if columns <= 0:
            continue
        rows_for_ratio = math.ceil(max(1, item.ratio) / max(1, columns))
        used_height = round2(rows_for_ratio * height_cm + max(0, rows_for_ratio - 1) * gap_cm)
        # default เน้นไม่หมุน ถ้าผลไม่ได้ต่างชัด เพื่อให้ผลิตอ่านง่าย
        if layout_style == MIXED_MARK_LAYOUT_STYLE_COMPACT:
            score = (-columns, used_height, height_cm, 1 if rotated else 0)
        else:
            score = (1 if rotated else 0, -columns, used_height, height_cm)
        scored.append((score, width_cm, height_cm, rotated))
    if not scored:
        width_cm, height_cm, rotated = options[0]
        return round2(width_cm), round2(height_cm), bool(rotated)
    _, width_cm, height_cm, rotated = min(scored, key=lambda row: row[0])
    return round2(width_cm), round2(height_cm), bool(rotated)


def _mixed_mark_quantities_from_sets(items: list[MixedMarkItem], set_count: int) -> dict[int, int]:
    return {item.item_id: max(0, int(item.ratio) * int(set_count)) for item in items}


def _build_mixed_layout_from_master(
    items: list[MixedMarkItem],
    mark_count: int,
    set_count: int,
    master_placements: list[MixedMarkPlacement],
    per_mark_quantities: dict[int, int],
    failed_set_count: int = 0,
    calculation_mode: str = "ratio",
    layout_style: str = MIXED_MARK_LAYOUT_STYLE_BLOCK,
    gap_cm: float = FIXED_MARK_GAP_CM,
) -> MixedMarkLayout:
    mark_count = max(2, int(mark_count))
    if mark_count % 2 != 0:
        mark_count += 1
    per_mark_quantity_total = sum(max(0, int(per_mark_quantities.get(item.item_id, 0))) for item in items)
    total_quantity = per_mark_quantity_total * mark_count
    item_quantities = {item.name: max(0, int(per_mark_quantities.get(item.item_id, 0))) * mark_count for item in items}
    item_piece_area_sqm = {
        item.name: round2(quick_piece_area_sqcm(item.shape, item.width_cm, item.height_cm) * max(0, int(per_mark_quantities.get(item.item_id, 0))) * mark_count / 10000)
        for item in items
    }
    total_piece_area_sqm = round2(sum(item_piece_area_sqm.values()))
    material_area_sqm = round2(FIXED_MARK_WIDTH_CM * FIXED_MARK_HEIGHT_CM * mark_count / 10000)
    tolerance_area_sqm = round2((FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM) * (FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM) * mark_count / 10000)
    usage_percent = round2((total_piece_area_sqm / material_area_sqm * 100) if material_area_sqm else 0.0)
    tolerance_usage_percent = round2((total_piece_area_sqm / tolerance_area_sqm * 100) if tolerance_area_sqm else 0.0)
    return MixedMarkLayout(
        mark_count=mark_count,
        set_count=max(0, int(set_count)),
        total_quantity=total_quantity,
        material_area_sqm=material_area_sqm,
        tolerance_area_sqm=tolerance_area_sqm,
        total_piece_area_sqm=total_piece_area_sqm,
        usage_percent=usage_percent,
        tolerance_usage_percent=tolerance_usage_percent,
        placements=tuple(master_placements),
        item_quantities=item_quantities,
        item_piece_area_sqm=item_piece_area_sqm,
        overflow_count=sum(1 for placement in master_placements if placement.overflow) * mark_count,
        rotated_count=sum(1 for placement in master_placements if placement.rotated) * mark_count,
        failed_set_count=max(0, int(failed_set_count)),
        per_mark_item_quantities=dict(per_mark_quantities),
        calculation_mode=calculation_mode,
        layout_style=layout_style,
        gap_cm=gap_cm,
    )


def pack_mixed_mark_quantities_orderly(
    items: list[MixedMarkItem],
    mark_count: int,
    per_mark_quantities: dict[int, int],
    gap_cm: float,
    auto_rotate_enabled: bool = True,
    layout_style: str = MIXED_MARK_LAYOUT_STYLE_BLOCK,
    set_count: int = 0,
    failed_set_count: int = 0,
    calculation_mode: str = "manual",
) -> MixedMarkLayout | None:
    """แพ็ก 1 มาร์คต้นแบบแบบ Row/Shelf เท่านั้น: เร็วกว่า MaxRects และได้แถวเป็นระเบียบ

    - วางเฉพาะ 1 มาร์คต้นแบบ แล้วคูณซ้ำทุกมาร์ค
    - มี margin เท่าช่องไฟรอบขอบงาน เพื่อให้ชิ้นงานไม่ชนขอบ Preview/พื้นที่อนุโลม
    - โหมดบล็อกจะจบกลุ่ม Size เดิมก่อนขึ้นกลุ่มถัดไป ทำให้งานผลิตอ่านง่าย
    """
    if not items:
        return None
    mark_count = max(2, int(mark_count))
    if mark_count % 2 != 0:
        mark_count += 1
    gap_cm = round2(max(0.0, float(gap_cm)))
    layout_style = layout_style if layout_style in MIXED_MARK_LAYOUT_STYLES else MIXED_MARK_LAYOUT_STYLE_BLOCK

    usable_width_cm = round2(FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM)
    usable_height_cm = round2(FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM)
    margin_cm = gap_cm
    left_cm = margin_cm
    top_limit_cm = round2(usable_height_cm - margin_cm)
    right_limit_cm = round2(usable_width_cm - margin_cm)
    available_row_width = round2(max(0.0, right_limit_cm - left_cm))
    if available_row_width <= 0 or top_limit_cm <= 0:
        return None

    total_per_mark = sum(max(0, int(per_mark_quantities.get(item.item_id, 0))) for item in items)
    if total_per_mark <= 0 or total_per_mark > MAX_TOTAL_QUANTITY:
        return None

    placements: list[MixedMarkPlacement] = []
    current_x = left_cm
    current_y = margin_cm
    row_height = 0.0

    def new_row() -> None:
        nonlocal current_x, current_y, row_height
        current_x = left_cm
        current_y = round2(current_y + row_height + gap_cm)
        row_height = 0.0

    for item_index in _mixed_group_order(items, layout_style):
        item = items[item_index]
        quantity = max(0, int(per_mark_quantities.get(item.item_id, 0)))
        if quantity <= 0:
            continue

        width_cm, height_cm, rotated = _mixed_orientation_for_item(
            item=item,
            usable_width_cm=available_row_width,
            gap_cm=gap_cm,
            auto_rotate_enabled=auto_rotate_enabled,
            layout_style=layout_style,
        )
        if width_cm > available_row_width + 1e-9:
            return None

        # โหมดบล็อก: ถ้าเริ่ม Size ใหม่และแถวก่อนหน้ามีของอยู่ ให้ขึ้นแถวใหม่เพื่อให้ดูเป็นระเบียบ
        if layout_style == MIXED_MARK_LAYOUT_STYLE_BLOCK and row_height > 0 and current_x > left_cm + 1e-9:
            new_row()

        for _ in range(quantity):
            if current_x > left_cm + 1e-9 and current_x + width_cm > right_limit_cm + 1e-9:
                new_row()
            if current_y + height_cm > top_limit_cm + 1e-9:
                return None
            overflow = (current_x + width_cm > FIXED_MARK_WIDTH_CM + 1e-9) or (current_y + height_cm > FIXED_MARK_HEIGHT_CM + 1e-9)
            placements.append(
                MixedMarkPlacement(
                    mark_index=0,
                    name=item.name,
                    shape=item.shape,
                    x_cm=round2(current_x),
                    y_cm=round2(current_y),
                    width_cm=width_cm,
                    height_cm=height_cm,
                    item_index=item_index,
                    rotated=rotated,
                    overflow=overflow,
                )
            )
            current_x = round2(current_x + width_cm + gap_cm)
            row_height = round2(max(row_height, height_cm))

    return _build_mixed_layout_from_master(
        items=items,
        mark_count=mark_count,
        set_count=set_count,
        master_placements=placements,
        per_mark_quantities=per_mark_quantities,
        failed_set_count=failed_set_count,
        calculation_mode=calculation_mode,
        layout_style=layout_style,
        gap_cm=gap_cm,
    )


def pack_mixed_mark_layout(
    items: list[MixedMarkItem],
    mark_count: int,
    set_count: int,
    auto_rotate_enabled: bool = True,
    gap_cm: float | None = None,
    layout_style: str | None = None,
) -> MixedMarkLayout | None:
    """แพ็กตามอัตราส่วน: จำนวนต่อ 1 มาร์ค = ratio × set_count"""
    if gap_cm is None:
        gap_cm = get_mixed_mark_gap_cm()
    if layout_style is None:
        layout_style = get_mixed_mark_layout_style()
    set_count = max(0, int(set_count))
    if set_count <= 0:
        return None
    per_mark_quantities = _mixed_mark_quantities_from_sets(items, set_count)
    return pack_mixed_mark_quantities_orderly(
        items=items,
        mark_count=mark_count,
        per_mark_quantities=per_mark_quantities,
        gap_cm=gap_cm,
        auto_rotate_enabled=auto_rotate_enabled,
        layout_style=layout_style,
        set_count=set_count,
        calculation_mode="ratio",
    )


def _mixed_fill_priority_item_ids(items: list[MixedMarkItem]) -> list[int]:
    """ลำดับ Size ที่จะใช้เติมพื้นที่เหลือหลังคำนวณจากอัตราส่วนหรือหลังปรับเอง"""
    fill_mode = st.session_state.get("mixed_fill_mode", MIXED_FILL_MODE_SMALLEST)
    if fill_mode == MIXED_FILL_MODE_NONE:
        return []
    if fill_mode == MIXED_FILL_MODE_SELECTED:
        selected_id = _selected_fill_item_id_from_label()
        if selected_id is not None and any(item.item_id == selected_id for item in items):
            return [selected_id]
        return [items[0].item_id] if items else []
    if fill_mode == MIXED_FILL_MODE_RATIO_ORDER:
        ordered = sorted(items, key=lambda item: (-max(1, int(item.ratio)), item.width_cm * item.height_cm, item.item_id))
        return [item.item_id for item in ordered]
    ordered = sorted(items, key=lambda item: (item.width_cm * item.height_cm, max(item.width_cm, item.height_cm), item.item_id))
    return [item.item_id for item in ordered]


def _mixed_current_piece_area_sqm(items: list[MixedMarkItem], quantities: dict[int, int]) -> float:
    return sum(item.width_cm * item.height_cm * max(0, int(quantities.get(item.item_id, 0))) for item in items) / 10000


def _mixed_max_extra_for_item(
    items: list[MixedMarkItem],
    mark_count: int,
    quantities: dict[int, int],
    item_id: int,
    gap_cm: float,
    layout_style: str,
    auto_rotate_enabled: bool,
) -> tuple[int, MixedMarkLayout | None]:
    """หา extra สูงสุดของ Size เดียวด้วย binary search เพื่อลดการวนทีละชิ้น"""
    item_lookup = {item.item_id: item for item in items}
    item = item_lookup.get(item_id)
    if item is None:
        return 0, None

    one_mark_tolerance_area_sqm = (FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM) * (FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM) / 10000
    current_area_sqm = _mixed_current_piece_area_sqm(items, quantities)
    single_area_sqm = max(0.000001, item.width_cm * item.height_cm / 10000)
    high_by_area = max(0, int(math.floor((one_mark_tolerance_area_sqm - current_area_sqm) / single_area_sqm)) + 2)
    current_total = sum(max(0, int(value)) for value in quantities.values())
    high_by_limit = max(0, MAX_TOTAL_QUANTITY - current_total)
    high = min(high_by_area, high_by_limit)
    if high <= 0:
        return 0, None

    best_extra = 0
    best_layout: MixedMarkLayout | None = None
    low = 1
    while low <= high:
        mid = (low + high) // 2
        test_quantities = dict(quantities)
        test_quantities[item_id] = max(0, int(test_quantities.get(item_id, 0))) + mid
        layout = pack_mixed_mark_quantities_orderly(
            items=items,
            mark_count=mark_count,
            per_mark_quantities=test_quantities,
            gap_cm=gap_cm,
            auto_rotate_enabled=auto_rotate_enabled,
            layout_style=layout_style,
            set_count=0,
            calculation_mode="manual",
        )
        if layout is not None:
            best_extra = mid
            best_layout = layout
            low = mid + 1
        else:
            high = mid - 1
    return best_extra, best_layout


def auto_fill_mixed_mark_leftover(
    items: list[MixedMarkItem],
    mark_count: int,
    base_quantities: dict[int, int],
    gap_cm: float,
    layout_style: str,
    auto_rotate_enabled: bool = True,
    set_count: int = 0,
    failed_set_count: int = 0,
    calculation_mode: str = "ratio",
    locked_item_ids: set[int] | None = None,
) -> MixedMarkLayout | None:
    """เติมพื้นที่ที่เหลือให้เต็มขึ้น โดยไม่บังคับให้ทุก Size ได้เท่ากัน

    locked_item_ids = Size ที่ผู้ใช้ระบุจำนวนเองแล้ว ห้ามระบบเติมเพิ่มทับ
    เช่น ลูกค้าต้องการ 7×7 = 60 ชิ้นพอดี ให้ล็อก Size นี้ไว้ แล้วเติมพื้นที่ที่เหลือให้ Size อื่นแทน
    """
    clean_quantities = {item.item_id: max(0, int(base_quantities.get(item.item_id, 0))) for item in items}
    layout = pack_mixed_mark_quantities_orderly(
        items=items,
        mark_count=mark_count,
        per_mark_quantities=clean_quantities,
        gap_cm=gap_cm,
        auto_rotate_enabled=auto_rotate_enabled,
        layout_style=layout_style,
        set_count=set_count,
        failed_set_count=failed_set_count,
        calculation_mode=calculation_mode,
    )
    if layout is None:
        return None

    locked_item_ids = set(locked_item_ids or set())
    priority_ids = [item_id for item_id in _mixed_fill_priority_item_ids(items) if item_id not in locked_item_ids]
    if not priority_ids:
        return layout

    best_layout = layout
    for _ in range(min(3, max(1, len(priority_ids)))):
        improved = False
        for item_id in priority_ids:
            extra, candidate_layout = _mixed_max_extra_for_item(
                items=items,
                mark_count=mark_count,
                quantities=clean_quantities,
                item_id=item_id,
                gap_cm=gap_cm,
                layout_style=layout_style,
                auto_rotate_enabled=auto_rotate_enabled,
            )
            if extra > 0 and candidate_layout is not None:
                clean_quantities[item_id] = max(0, int(clean_quantities.get(item_id, 0))) + extra
                best_layout = candidate_layout
                improved = True
        if not improved:
            break

    return replace(
        best_layout,
        set_count=max(0, int(set_count)),
        failed_set_count=max(0, int(failed_set_count)),
        calculation_mode=calculation_mode,
    )


def calculate_fixed_mark_mixed_result(items: list[MixedMarkItem], mark_count: int) -> MixedMarkLayout | None:
    """หาจำนวนชุดต่อ 1 มาร์คสูงสุด แล้วเติมพื้นที่เหลือด้วยชิ้นเดี่ยวตามตัวเลือก"""
    if not items:
        return None

    mark_count = max(2, int(mark_count))
    if mark_count % 2 != 0:
        mark_count += 1
    gap_cm = get_mixed_mark_gap_cm()
    layout_style = get_mixed_mark_layout_style()

    ratio_total = sum(max(1, int(item.ratio)) for item in items)
    raw_area_per_set_sqm = sum(item.width_cm * item.height_cm * max(1, int(item.ratio)) for item in items) / 10000
    one_mark_tolerance_area_sqm = (FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM) * (FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM) / 10000
    if ratio_total <= 0 or raw_area_per_set_sqm <= 0:
        return None

    max_by_quantity = max(0, MAX_TOTAL_QUANTITY // ratio_total)
    max_by_area = max(0, int(math.floor(one_mark_tolerance_area_sqm / raw_area_per_set_sqm)))
    high = min(max_by_quantity, max_by_area)

    empty_layout = MixedMarkLayout(
        mark_count=mark_count,
        set_count=0,
        total_quantity=0,
        material_area_sqm=round2(FIXED_MARK_WIDTH_CM * FIXED_MARK_HEIGHT_CM * mark_count / 10000),
        tolerance_area_sqm=round2((FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM) * (FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM) * mark_count / 10000),
        total_piece_area_sqm=0.0,
        usage_percent=0.0,
        tolerance_usage_percent=0.0,
        placements=tuple(),
        item_quantities={item.name: 0 for item in items},
        item_piece_area_sqm={item.name: 0.0 for item in items},
        overflow_count=0,
        rotated_count=0,
        failed_set_count=1,
        per_mark_item_quantities={item.item_id: 0 for item in items},
        calculation_mode="ratio",
        layout_style=layout_style,
        gap_cm=gap_cm,
    )
    if high < 1:
        return empty_layout

    low = 1
    best_set_count = 0
    best_quantities: dict[int, int] | None = None
    while low <= high:
        mid = (low + high) // 2
        test_quantities = _mixed_mark_quantities_from_sets(items, mid)
        layout = pack_mixed_mark_quantities_orderly(
            items=items,
            mark_count=mark_count,
            per_mark_quantities=test_quantities,
            gap_cm=gap_cm,
            auto_rotate_enabled=True,
            layout_style=layout_style,
            set_count=mid,
            calculation_mode="ratio",
        )
        if layout is not None:
            best_set_count = mid
            best_quantities = test_quantities
            low = mid + 1
        else:
            high = mid - 1

    if not best_quantities or best_set_count <= 0:
        return empty_layout

    filled_layout = auto_fill_mixed_mark_leftover(
        items=items,
        mark_count=mark_count,
        base_quantities=best_quantities,
        gap_cm=gap_cm,
        layout_style=layout_style,
        auto_rotate_enabled=True,
        set_count=best_set_count,
        failed_set_count=best_set_count + 1,
        calculation_mode="ratio",
    )
    return filled_layout or empty_layout


def calculate_fixed_mark_mixed_manual_result(
    items: list[MixedMarkItem],
    mark_count: int,
    per_mark_quantities: dict[int, int],
    locked_item_ids: set[int] | None = None,
) -> MixedMarkLayout | None:
    """คำนวณจากจำนวนต่อ 1 มาร์คที่ผู้ใช้ปรับเอง แล้วเติมพื้นที่เหลือให้ Size ที่ไม่ได้ล็อก"""
    return auto_fill_mixed_mark_leftover(
        items=items,
        mark_count=mark_count,
        base_quantities=per_mark_quantities,
        gap_cm=get_mixed_mark_gap_cm(),
        auto_rotate_enabled=True,
        layout_style=get_mixed_mark_layout_style(),
        set_count=0,
        calculation_mode="manual",
        locked_item_ids=locked_item_ids,
    )


def fixed_mark_mixed_result_rows(items: list[MixedMarkItem], layout: MixedMarkLayout) -> list[dict]:
    rows: list[dict] = []
    per_mark_quantities = layout.per_mark_item_quantities or {}
    for item in items:
        per_mark_quantity = int(per_mark_quantities.get(item.item_id, int(item.ratio) * int(layout.set_count)))
        base_ratio_quantity = int(item.ratio) * int(layout.set_count) if layout.set_count > 0 else 0
        extra_per_mark = max(0, per_mark_quantity - base_ratio_quantity)
        total_quantity = int(layout.item_quantities.get(item.name, per_mark_quantity * int(layout.mark_count)))
        total_extra = extra_per_mark * int(layout.mark_count)
        note = "ปรับเอง + เติมพื้นที่เหลือ" if layout.calculation_mode == "manual" else "คำนวณจากอัตราส่วน + เติมพื้นที่เหลือ"
        if extra_per_mark > 0:
            note += f" (+{extra_per_mark:,}/มาร์ค)"
        rows.append({
            "ขนาดสติกเกอร์": f"{item.width_cm:.2f} × {item.height_cm:.2f} cm",
            "ชื่อ Size": item.name,
            "จำนวนที่ได้ในพื้นที่นี้": f"{total_quantity:,} ชิ้น",
            "ต่อ 1 มาร์ค": f"{per_mark_quantity:,} ชิ้น",
            "จำนวนมาร์ค": f"{layout.mark_count:,} มาร์ค",
            "เพิ่มจากพื้นที่เหลือ": f"{total_extra:,} ชิ้น" if total_extra > 0 else "-",
            "อัตราส่วนตั้งต้น": f"{item.ratio:,}",
            "หมายเหตุ": note,
        })
    return rows


def mixed_mark_result_sentence(items: list[MixedMarkItem], layout: MixedMarkLayout) -> str:
    area_label = fixed_mark_area_label(layout.mark_count)
    parts = []
    for item in items:
        total_quantity = int(layout.item_quantities.get(item.name, 0))
        parts.append(f"ขนาด {item.width_cm:.0f}×{item.height_cm:.0f} ได้ {total_quantity:,} ชิ้น")
    joined = " · ".join(parts)
    size_text = " และ ".join(f"{item.width_cm:.0f}×{item.height_cm:.0f}" for item in items[:3])
    if len(items) > 3:
        size_text += f" และอีก {len(items) - 3} ขนาด"
    return f"ในพื้นที่ {area_label} สำหรับสติกเกอร์ {size_text} จำนวนที่ได้คือ {joined}"


def _align_total_to_mark_count(total_quantity: int, mark_count: int) -> int:
    """บังคับจำนวนรวมให้หารลงตามจำนวนมาร์ค เพื่อให้ทุกมาร์คเป็น Exact Copy ได้จริง"""
    mark_count = max(1, int(mark_count))
    total_quantity = max(0, int(total_quantity))
    return int(round(total_quantity / mark_count)) * mark_count


def _reset_mixed_adjust_totals(items: list[MixedMarkItem], suggested_layout: MixedMarkLayout) -> None:
    for item in items:
        st.session_state[f"mixed_adjust_total_{item.item_id}"] = int(suggested_layout.item_quantities.get(item.name, 0))
    set_action_feedback("รีเซ็ตจำนวนที่แก้เองเป็นค่าคำนวณแนะนำแล้ว", "reset")



def _mixed_item_ids(items: list[MixedMarkItem]) -> list[int]:
    return [int(item.item_id) for item in items]


def _get_active_mixed_lock_item_id(items: list[MixedMarkItem]) -> int | None:
    """คืนค่า Size ที่ผู้ใช้แก้ล่าสุดเท่านั้น

    หลักใหม่:
    - ช่องที่แก้ล่าสุด = ล็อกจำนวน
    - Size อื่น = ปล่อยให้ระบบคำนวณพื้นที่เหลือใหม่แบบ realtime
    - แก้ช่องอื่นเมื่อไร active lock จะย้ายไปช่องนั้นทันที
    """
    valid_ids = set(_mixed_item_ids(items))
    try:
        active_id = int(st.session_state.get("mixed_active_lock_item_id", 0))
    except Exception:
        active_id = 0
    return active_id if active_id in valid_ids else None


def _normalize_mixed_adjust_total_callback(item_id: int, mark_count: int) -> None:
    """ปรับเลขที่ผู้ใช้กรอกให้หารลงตามจำนวนมาร์ค และให้ช่องนี้เป็น Size ที่ล็อกล่าสุด"""
    item_id = int(item_id)
    key = f"mixed_adjust_total_{item_id}"
    try:
        raw_value = int(st.session_state.get(key, 0))
    except Exception:
        raw_value = 0
    st.session_state[key] = _align_total_to_mark_count(raw_value, mark_count)
    # จุดแก้หลัก: ล็อกเฉพาะช่องที่แก้ล่าสุด ไม่ล็อกทุกช่องที่เคยถูกแก้
    st.session_state["mixed_active_lock_item_id"] = item_id


def calculate_mixed_layout_from_requested_totals(
    items: list[MixedMarkItem],
    mark_count: int,
    suggested_layout: MixedMarkLayout,
    requested_totals: dict[int, int],
) -> tuple[MixedMarkLayout, set[int], dict[int, int]]:
    """คำนวณ layout ใหม่จากจำนวนรวมที่ผู้ใช้กรอกแบบสด

    Logic ใหม่เพื่อให้ใช้งานตรงความต้องการ:
    - ล็อกเฉพาะ Size ที่แก้ล่าสุดเท่านั้น
    - Size อื่นไม่ถือว่าเป็นค่าล็อก แม้ช่อง input จะเคยมีค่าเก่าอยู่
    - เมื่อแก้ Size 10×10 เป็น 30 ชิ้น ระบบจะใช้ 10×10 = 30 เป็นฐาน แล้วคำนวณ Size 7×7 จากพื้นที่เหลือทันที
    - จำนวนรวมถูกปัดให้หารลงด้วยจำนวนมาร์ค เพื่อให้ทุกมาร์คเป็น Exact Copy ได้จริง
    """
    suggested_totals = {item.item_id: int(suggested_layout.item_quantities.get(item.name, 0)) for item in items}
    active_lock_item_id = _get_active_mixed_lock_item_id(items)

    locked_item_ids: set[int] = set()
    base_per_mark_quantities = {item.item_id: 0 for item in items}
    aligned_requested_totals: dict[int, int] = {}

    for item in items:
        suggested_total = suggested_totals[item.item_id]
        raw_total = int(requested_totals.get(item.item_id, suggested_total))
        requested_total = _align_total_to_mark_count(raw_total, mark_count)
        aligned_requested_totals[item.item_id] = requested_total

        if active_lock_item_id == item.item_id and requested_total != suggested_total:
            locked_item_ids.add(item.item_id)
            base_per_mark_quantities[item.item_id] = max(0, requested_total // max(1, mark_count))

    if not locked_item_ids:
        # ถ้าไม่มี Size ที่แก้ล่าสุด หรือค่าที่แก้เท่าค่าแนะนำ ให้กลับไปใช้ layout แนะนำ
        return suggested_layout, locked_item_ids, aligned_requested_totals

    adjusted_layout = calculate_fixed_mark_mixed_manual_result(
        items=items,
        mark_count=mark_count,
        per_mark_quantities=base_per_mark_quantities,
        locked_item_ids=locked_item_ids,
    )
    if adjusted_layout is None or adjusted_layout.total_quantity <= 0:
        return suggested_layout, locked_item_ids, aligned_requested_totals
    return adjusted_layout, locked_item_ids, aligned_requested_totals


def calculate_mixed_layout_from_editable_total_cards(
    items: list[MixedMarkItem],
    mark_count: int,
    suggested_layout: MixedMarkLayout,
) -> tuple[MixedMarkLayout, set[int], dict[int, int]]:
    """อ่านค่าจาก session_state แล้วคำนวณ layout ใหม่"""
    suggested_totals = {item.item_id: int(suggested_layout.item_quantities.get(item.name, 0)) for item in items}
    requested_totals: dict[int, int] = {}
    for item in items:
        key = f"mixed_adjust_total_{item.item_id}"
        if key not in st.session_state:
            st.session_state[key] = suggested_totals[item.item_id]
        requested_totals[item.item_id] = int(st.session_state.get(key, suggested_totals[item.item_id]))
    return calculate_mixed_layout_from_requested_totals(items, mark_count, suggested_layout, requested_totals)


def render_mixed_mark_easy_summary(items: list[MixedMarkItem], layout: MixedMarkLayout) -> MixedMarkLayout:
    """แสดงผลรวมแบบอ่านง่าย + การ์ดแก้จำนวนแบบคำนวณสด และคืน layout ที่ใช้งานจริง

    เวอร์ชันนี้แก้ปัญหาเดิม:
    - เดิม: ถ้าเคยแก้ Size 7×7 เป็น 60 แล้วไปแก้ Size 10×10 เป็น 30 ระบบล็อกทั้งสอง Size
    - ใหม่: ช่องที่แก้ล่าสุดเท่านั้นที่ล็อก ส่วน Size อื่นจะคำนวณจากพื้นที่เหลือและแสดงผลทันที
    """
    suggested_totals = {item.item_id: int(layout.item_quantities.get(item.name, 0)) for item in items}
    for item in items:
        key = f"mixed_adjust_total_{item.item_id}"
        if key not in st.session_state:
            st.session_state[key] = suggested_totals[item.item_id]

    # คำนวณก่อนสร้าง widget เพื่อให้ช่องที่ไม่ได้ล็อกถูก sync เป็นจำนวนใหม่จากพื้นที่เหลือทันที
    requested_totals: dict[int, int] = {}
    for item in items:
        key = f"mixed_adjust_total_{item.item_id}"
        requested_totals[item.item_id] = int(st.session_state.get(key, suggested_totals[item.item_id]))

    active_layout, locked_item_ids, aligned_requested_totals = calculate_mixed_layout_from_requested_totals(
        items=items,
        mark_count=layout.mark_count,
        suggested_layout=layout,
        requested_totals=requested_totals,
    )

    # Sync ช่อง input ให้ตรงกับผลลัพธ์ล่าสุดก่อน render widget
    # สำคัญ: ทำให้ Size ที่ไม่ได้ล็อกเปลี่ยนตัวเลขตามพื้นที่เหลือแบบ realtime
    for item in items:
        key = f"mixed_adjust_total_{item.item_id}"
        if item.item_id in locked_item_ids:
            st.session_state[key] = int(aligned_requested_totals.get(item.item_id, suggested_totals[item.item_id]))
        else:
            st.session_state[key] = int(active_layout.item_quantities.get(item.name, 0))

    sentence = mixed_mark_result_sentence(items, active_layout)
    st.markdown(
        ''.join([
            '<div class="multi-result-head">',
            '<div class="multi-result-kicker">ผลคำนวณที่ใช้อธิบายลูกค้า</div>',
            f'<div class="multi-result-sentence">{html.escape(sentence)}</div>',
            '</div>',
        ]),
        unsafe_allow_html=True,
    )

    control_cols = st.columns([1.0, 1.2, 3.2])
    with control_cols[0]:
        if st.button("รีเซ็ตจำนวน", key="mixed_reset_adjust_totals", use_container_width=True):
            _reset_mixed_adjust_totals(items, layout)
            st.session_state.pop("mixed_active_lock_item_id", None)
            st.rerun()
    with control_cols[1]:
        status_text = "คำนวณสดจากช่องที่แก้ล่าสุด" if locked_item_ids else "ใช้จำนวนแนะนำ"
        status_level = "warn" if locked_item_ids else "good"
        status_badge(status_text, status_level)
    with control_cols[2]:
        st.caption("แก้ช่องไหนล่าสุด ระบบจะล็อกเฉพาะ Size นั้น แล้วให้ Size อื่นรับพื้นที่เหลือทันที")

    card_cols = st.columns(min(3, max(1, len(items))))
    per_mark_quantities = active_layout.per_mark_item_quantities or {}
    active_lock_item_id = _get_active_mixed_lock_item_id(items)

    for index, item in enumerate(items):
        with card_cols[index % len(card_cols)]:
            card_border_color = roll_preview_color(index)
            with st.container(border=True):
                total_qty = int(active_layout.item_quantities.get(item.name, 0))
                per_mark_qty = int(per_mark_quantities.get(item.item_id, 0))
                suggested_total = suggested_totals[item.item_id]
                is_locked = item.item_id in locked_item_ids
                base_ratio_qty = int(item.ratio) * int(active_layout.set_count) if active_layout.set_count > 0 else 0
                extra = max(0, per_mark_qty - base_ratio_qty) * int(active_layout.mark_count)
                extra_text = f"เติมจากพื้นที่เหลือ +{extra:,} ชิ้น" if extra > 0 else "ไม่มีชิ้นเติมเพิ่ม"
                delta_vs_suggested = total_qty - suggested_total
                if delta_vs_suggested > 0:
                    live_text = f"หลังปรับ: เพิ่มจากค่าแนะนำ +{delta_vs_suggested:,} ชิ้น"
                    live_color = "#7dd3fc"
                elif delta_vs_suggested < 0:
                    live_text = f"หลังปรับ: ลดจากค่าแนะนำ {abs(delta_vs_suggested):,} ชิ้น"
                    live_color = "#fca5a5"
                else:
                    live_text = "หลังปรับ: เท่ากับค่าแนะนำ"
                    live_color = "#94a3b8"

                if is_locked:
                    lock_text = f"🔒 ล็อก Size นี้ {total_qty:,} ชิ้น"
                    lock_color = "#fbbf24"
                elif active_lock_item_id is not None:
                    lock_text = f"คำนวณจากพื้นที่เหลือ = {total_qty:,} ชิ้น"
                    lock_color = "#7dd3fc"
                else:
                    lock_text = "ยังไม่ล็อก — ใช้จำนวนแนะนำ"
                    lock_color = "#94a3b8"

                result_html = f"""
                <div style="border-left:6px solid {card_border_color}; padding-left:10px; margin-bottom:8px;">
                    <div style="color:#e2e8f0; font-size:1.02rem; font-weight:900;">{item.width_cm:.2f} × {item.height_cm:.2f} cm</div>
                    <div style="color:#94a3b8; font-size:.86rem; margin-top:2px;">{html.escape(item.name)}</div>
                    <div style="color:#facc15; font-size:2rem; line-height:1.05; font-weight:950; margin-top:8px;">{total_qty:,}<span style="color:#cbd5e1; font-size:.9rem; font-weight:700;"> ชิ้น</span></div>
                    <div style="color:#cbd5e1; font-size:.82rem; margin-top:4px;">ต่อ 1 มาร์ค {per_mark_qty:,} ชิ้น · {active_layout.mark_count:,} มาร์ค</div>
                    <div style="color:#7dd3fc; font-size:.82rem; margin-top:4px;">{html.escape(extra_text)}</div>
                    <div style="color:{live_color}; font-size:.82rem; margin-top:4px;">{html.escape(live_text)}</div>
                    <div style="color:{lock_color}; font-size:.82rem; margin-top:4px;">{html.escape(lock_text)}</div>
                </div>
                """
                st.markdown(result_html, unsafe_allow_html=True)
                st.number_input(
                    "แก้จำนวนรวมในพื้นที่นี้",
                    min_value=0,
                    step=max(1, int(active_layout.mark_count)),
                    key=f"mixed_adjust_total_{item.item_id}",
                    on_change=_normalize_mixed_adjust_total_callback,
                    args=(item.item_id, active_layout.mark_count),
                    help=(
                        f"จำนวนต้องเพิ่ม/ลดทีละ {active_layout.mark_count} ชิ้น เพราะผลิตแบบ Exact Copy ทุกมาร์คต้องเหมือนกัน "
                        f"ค่าแนะนำเดิม {suggested_total:,} ชิ้น"
                    ),
                )

    if locked_item_ids:
        locked_names = [item.name for item in items if item.item_id in locked_item_ids]
        free_names = [item.name for item in items if item.item_id not in locked_item_ids]
        st.info("ล็อกจำนวน: " + ", ".join(locked_names) + " · คำนวณพื้นที่เหลือให้: " + (", ".join(free_names) if free_names else "ไม่มี Size อื่น"))
    return active_layout

def build_mixed_mark_preview_figure(items: list[MixedMarkItem], layout: MixedMarkLayout, max_preview_marks: int = DEFAULT_MIXED_MARK_PREVIEW_MARKS) -> plt.Figure:
    preview_mark_count = min(layout.mark_count, max_preview_marks)
    usable_width_cm = round2(FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM)
    usable_height_cm = round2(FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM)
    panel_gap_cm = 7.0
    columns = 2 if preview_mark_count > 1 else 1
    rows = max(1, math.ceil(preview_mark_count / columns))
    canvas_width = columns * usable_width_cm + (columns - 1) * panel_gap_cm
    canvas_height = rows * usable_height_cm + (rows - 1) * panel_gap_cm
    fig_width = min(15, max(8, canvas_width / 10))
    fig_height = min(18, max(6, canvas_height / 10))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=130)
    fig.patch.set_facecolor("#101114")
    ax.set_facecolor("#101114")

    master_placements = list(layout.placements)
    size_color_map = build_size_color_map(items)
    max_draw_per_mark = max(1, MIXED_MARK_PREVIEW_PATCH_LIMIT // max(1, preview_mark_count))
    drawn_placements = master_placements[:max_draw_per_mark]
    preview_limited = len(master_placements) > len(drawn_placements)

    for mark_index in range(preview_mark_count):
        col = mark_index % columns
        row = mark_index // columns
        origin_x = col * (usable_width_cm + panel_gap_cm)
        origin_y = (rows - 1 - row) * (usable_height_cm + panel_gap_cm)

        tolerance_rect = patches.Rectangle(
            (origin_x, origin_y),
            usable_width_cm,
            usable_height_cm,
            linewidth=1,
            edgecolor="#5a4631",
            facecolor="#2b2117",
            linestyle="--",
            alpha=0.55,
            zorder=0,
        )
        mark_rect = patches.Rectangle(
            (origin_x, origin_y),
            FIXED_MARK_WIDTH_CM,
            FIXED_MARK_HEIGHT_CM,
            linewidth=1.35,
            edgecolor="#e7eefc",
            facecolor="#1d2128",
            zorder=1,
        )
        ax.add_patch(tolerance_rect)
        ax.add_patch(mark_rect)
        pair_label = f"คู่ {(mark_index // 2) + 1}" if layout.mark_count >= 2 else ""
        ax.text(
            origin_x,
            origin_y + usable_height_cm + 1.1,
            f"Mark {mark_index + 1} / {layout.mark_count}  {pair_label}  · layout เดียวกัน",
            color="#e7eefc",
            fontsize=9,
            fontproperties=get_thai_font(bold=True),
            ha="left",
            va="bottom",
        )

        # วาดจากมาร์คต้นแบบซ้ำทุกมาร์ค เพื่อให้ Preview สะท้อนงานผลิตจริง
        for placement in drawn_placements:
            color = preview_color_for_size(placement.width_cm, placement.height_cm, placement.item_index, placement.overflow, size_color_map)
            if normalize_sticker_shape(getattr(placement, "shape", QUICK_SHAPE_RECTANGLE)) == QUICK_SHAPE_CIRCLE:
                radius = placement.width_cm / 2
                patch = patches.Circle(
                    (origin_x + placement.x_cm + radius, origin_y + placement.y_cm + radius),
                    radius=radius,
                    linewidth=0.55,
                    edgecolor="#0f172a",
                    facecolor=color,
                    alpha=0.92,
                    zorder=3,
                )
            else:
                patch = patches.Rectangle(
                    (origin_x + placement.x_cm, origin_y + placement.y_cm),
                    placement.width_cm,
                    placement.height_cm,
                    linewidth=0.55,
                    edgecolor="#0f172a",
                    facecolor=color,
                    alpha=0.92,
                    zorder=3,
                )
            ax.add_patch(patch)
            label = safe_preview_label(placement.name, f"Size {placement.item_index + 1}", max_len=10)
            if placement.rotated:
                label += " R"
            if SHOW_PREVIEW_TEXT_ON_PIECES and placement.width_cm >= 7 and placement.height_cm >= 4 and not preview_limited:
                ax.text(
                    origin_x + placement.x_cm + placement.width_cm / 2,
                    origin_y + placement.y_cm + placement.height_cm / 2,
                    label,
                    color="#111827",
                    fontsize=6.5,
                    fontproperties=get_thai_font(bold=True),
                    ha="center",
                    va="center",
                    zorder=4,
                )

    legend_x = 0
    legend_y = -5.2
    for index, item in enumerate(items[:10]):
        per_mark_qty = int((layout.per_mark_item_quantities or {}).get(item.item_id, int(item.ratio) * int(layout.set_count)))
        total_qty = int(layout.item_quantities.get(item.name, 0))
        ax.add_patch(patches.Rectangle((legend_x, legend_y), 2.3, 2.3, facecolor=preview_color_for_size(item.width_cm, item.height_cm, index, False, size_color_map), edgecolor="none"))
        ax.text(
            legend_x + 3.0,
            legend_y + 1.15,
            f"{safe_preview_label(item.name, f'Size {index + 1}', 16)}  {sticker_shape_dimension_text(item.shape, item.width_cm, item.height_cm)}  /มาร์ค {per_mark_qty:,}  รวม {total_qty:,}",
            color="#dbeafe",
            fontsize=8,
            fontproperties=get_thai_font(),
            ha="left",
            va="center",
        )
        legend_y -= 3.3

    if preview_limited:
        ax.text(
            0,
            legend_y - 1.2,
            f"Preview เร่งความเร็ว: แสดง {len(drawn_placements):,} จาก {len(master_placements):,} ชิ้นต่อมาร์ค แต่จำนวนคำนวณจริงครบทั้งหมด",
            color="#facc15",
            fontsize=8.5,
            fontproperties=get_thai_font(bold=True),
            ha="left",
            va="top",
        )
        legend_y -= 3.0

    if layout.mark_count > max_preview_marks:
        ax.text(
            0,
            legend_y - 1.2,
            f"แสดง Preview เฉพาะ {max_preview_marks} มาร์คแรก จากทั้งหมด {layout.mark_count} มาร์ค",
            color="#facc15",
            fontsize=8.5,
            fontproperties=get_thai_font(bold=True),
            ha="left",
            va="top",
        )

    ax.set_xlim(-1, canvas_width + 1)
    ax.set_ylim(min(-8, legend_y - 5), canvas_height + 5)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    mode_title = "ปรับจำนวนเอง" if layout.calculation_mode == "manual" else f"{layout.set_count:,} ชุด/มาร์ค"
    title = f"Mixed Size Mark Layout · {mode_title} · {layout.total_quantity:,} ชิ้นรวม · {layout.mark_count:,} มาร์คซ้ำแบบเดียวกัน"
    ax.set_title(title, color="#f8fafc", fontsize=13, fontproperties=get_thai_font(bold=True), pad=14)
    return fig



def render_fixed_mark_mixed_result_cards(items: list[MixedMarkItem], layout: MixedMarkLayout) -> None:
    status_text = "อยู่ในขอบ" if layout.overflow_count == 0 else "มีบางชิ้นใช้ระยะอนุโลม"
    status_class = "good" if layout.overflow_count == 0 else "warn"
    per_mark_quantities = layout.per_mark_item_quantities or {}
    per_mark_quantity = sum(max(0, int(per_mark_quantities.get(item.item_id, 0))) for item in items)
    total_set_count = int(layout.set_count) * int(layout.mark_count)
    first_card_label = "จำนวนชุดต่อ 1 มาร์ค" if layout.calculation_mode == "ratio" else "โหมดปรับจำนวนเอง"
    first_card_value = f"{layout.set_count:,}" if layout.calculation_mode == "ratio" else "Manual"
    first_card_unit = " ชุด/มาร์ค" if layout.calculation_mode == "ratio" else ""
    first_card_meta = f"อัตราส่วน {html.escape(mixed_ratio_label(items))}" if layout.calculation_mode == "ratio" else "ใช้จำนวนต่อ 1 มาร์คที่ปรับเอง"
    first_card_grid = f"ชุดถัดไปที่ไม่ผ่านต่อมาร์ค: {layout.failed_set_count:,} ชุด" if layout.calculation_mode == "ratio" else "ลด Size หนึ่งเพื่อเพิ่มอีก Size ได้จากช่องปรับจำนวน"
    total_set_text = f"รวม {total_set_count:,} ชุด" if layout.calculation_mode == "ratio" else "คำนวณจากจำนวนต่อมาร์ค"

    # เขียน HTML เป็นบรรทัดสั้น ๆ เพื่อไม่ให้ Markdown render เป็นกล่อง code ดิบ
    # เอาการ์ด "จำนวนชุดต่อ 1 มาร์ค" ออกตามการใช้งานจริง เหลือเฉพาะข้อมูลที่ใช้ผลิต/คุยกับลูกค้า
    card_html = ''.join([
        '<div class="fixed-mark-card-grid">',
        '<div class="fixed-mark-card">',
        '<div class="fixed-card-topline"><span>จำนวนรวมทุก Size</span><span class="fixed-status good">ผลิตซ้ำ</span></div>',
        f'<div class="fixed-card-qty">{layout.total_quantity:,}<span> ชิ้น</span></div>',
        f'<div class="fixed-card-meta">ต่อ 1 มาร์ค {per_mark_quantity:,} ชิ้น · {total_set_text}</div>',
        f'<div class="fixed-card-gridline">พื้นที่ชิ้นงาน {layout.total_piece_area_sqm:.2f} ตรม.</div>',
        '</div>',
        '<div class="fixed-mark-card">',
        '<div class="fixed-card-topline"><span>รูปแบบผลิต</span><span class="fixed-status good">Exact Copy</span></div>',
        f'<div class="fixed-card-qty">{layout.mark_count:,}<span> มาร์ค</span></div>',
        '<div class="fixed-card-meta">จัด 1 มาร์คต้นแบบ แล้วคัดลอกซ้ำ</div>',
        '<div class="fixed-card-gridline">มาร์คขวาต้องเหมือนมาร์คซ้ายทุกตำแหน่ง</div>',
        '</div>',
        '<div class="fixed-mark-card">',
        '<div class="fixed-card-topline"><span>ช่องไฟ / การเรียง</span><span class="fixed-status good">เร็ว</span></div>',
        f'<div class="fixed-card-qty">{layout.gap_cm:.2f}<span> cm</span></div>',
        f'<div class="fixed-card-meta">{html.escape(layout.layout_style)}</div>',
        f'<div class="fixed-card-gridline">ใช้พื้นที่จริง {layout.usage_percent:.2f}%</div>',
        '</div>',
        '</div>',
    ])
    st.markdown(card_html, unsafe_allow_html=True)

def render_fixed_mark_mixed_calculator_content(area_unit: str) -> None:
    # หน้าคำนวนพื้นที่หลายขนาด
    mark_count = get_fixed_mark_count()
    material_area_sqm = round2(FIXED_MARK_WIDTH_CM * FIXED_MARK_HEIGHT_CM * mark_count / 10000)
    tolerance_area_sqm = round2((FIXED_MARK_WIDTH_CM + FIXED_MARK_TOLERANCE_CM) * (FIXED_MARK_HEIGHT_CM + FIXED_MARK_TOLERANCE_CM) * mark_count / 10000)
    items = collect_fixed_mark_mixed_size_inputs(area_unit)
    suggested_layout = calculate_fixed_mark_mixed_result(items, mark_count)

    st.markdown(
        f"""
        <div class="fixed-mark-hero">
            <div class="fixed-mark-kicker">MULTI SIZE AREA · FAST EXACT COPY</div>
            <div class="fixed-mark-title">คำนวนพื้นที่หลายขนาด ในพื้นที่ {html.escape(fixed_mark_area_label(mark_count))}</div>
            <div class="fixed-mark-subtitle">
                มาร์คมาตรฐาน {FIXED_MARK_WIDTH_CM:.0f}×{FIXED_MARK_HEIGHT_CM:.0f} cm · ช่องไฟปรับได้ {get_mixed_mark_gap_cm():.2f} cm · จัด 1 มาร์คต้นแบบ แล้วคัดลอกซ้ำทุกมาร์ค
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    summary_cols = st.columns(4)
    with summary_cols[0]:
        metric_card("พื้นที่ที่เลือก", fixed_mark_area_label(mark_count), f"พื้นที่จริง {material_area_sqm:.2f} ตรม.", accent=True)
    with summary_cols[1]:
        metric_card("จำนวนมาร์ค", f"{mark_count:,} มาร์ค", f"รวมอนุโลม {tolerance_area_sqm:.2f} ตรม.")
    with summary_cols[2]:
        metric_card("จำนวน Size", f"{len(items):,} Size", f"ตัวเลือกอัตราส่วน {mixed_ratio_label(items)}")
    with summary_cols[3]:
        metric_card("หลักผลิต", "Exact Copy", "ขวาเหมือนซ้ายทุกตำแหน่ง")

    st.info(
        "โหมดนี้จัดแค่ 1 มาร์คต้นแบบ 57×41 แล้วคัดลอกซ้ำทุกมาร์ค จึงเร็วกว่าเดิม และ Mark 1/2/3/4 จะเหมือนกันทุกตำแหน่ง — หลังคำนวณสามารถเปิดโหมดปรับจำนวนเอง เพื่อลด Size หนึ่งแล้วเพิ่มอีก Size ได้"
    )

    if not items:
        st.warning("กรุณาเพิ่ม Size แล้วใส่กว้าง/ยาวให้มากกว่า 0")
        return
    if suggested_layout is None:
        st.error("ยังคำนวณไม่ได้ กรุณาตรวจสอบขนาดและอัตราส่วน")
        return
    if suggested_layout.set_count <= 0:
        st.error("พื้นที่ 1 มาร์คต้นแบบไม่พอสำหรับชุดเริ่มต้นที่เลือก กรุณาลดขนาดชิ้นงาน ลดช่องไฟ หรือปรับอัตราส่วน")
        return

    # ตั้งค่าเริ่มต้นของช่องแก้จำนวนรวมจากผลแนะนำ แต่ไม่ทับค่าที่ผู้ใช้แก้เองแล้ว
    suggested_per_mark = suggested_layout.per_mark_item_quantities or {}
    for item in items:
        adjust_key = f"mixed_adjust_total_{item.item_id}"
        if adjust_key not in st.session_state:
            st.session_state[adjust_key] = int(suggested_layout.item_quantities.get(item.name, 0))

    active_layout = render_mixed_mark_easy_summary(items, suggested_layout)
    render_fixed_mark_mixed_result_cards(items, active_layout)
    rows = fixed_mark_mixed_result_rows(items, active_layout)

    preview_marks = int(st.session_state.get("mixed_mark_preview_marks", DEFAULT_MIXED_MARK_PREVIEW_MARKS))
    fig = build_mixed_mark_preview_figure(items, active_layout, max_preview_marks=preview_marks)
    st.markdown('<div class="section-title">Preview: มาร์คขวาเหมือนมาร์คซ้าย</div>', unsafe_allow_html=True)
    st.pyplot(fig, use_container_width=True)
    if st.checkbox("สร้างไฟล์ PNG สำหรับดาวน์โหลด Preview", value=False, key="mixed_generate_preview_png", help="ปิดไว้เพื่อให้โปรแกรมลื่นขึ้น เปิดเฉพาะตอนต้องการโหลดภาพ"):
        preview_png = fig_to_png_bytes(fig)
        st.download_button(
            "ดาวน์โหลด Preview PNG แบบคำนวนพื้นที่หลายขนาด",
            data=preview_png,
            file_name="multi_size_area_57x41_preview.png",
            mime="image/png",
            key="download_mixed_fixed_mark_preview_png",
            use_container_width=True,
        )
    plt.close(fig)

    st.markdown('<div class="section-title">ตารางรายละเอียดจำนวนแต่ละ Size</div>', unsafe_allow_html=True)
    st.dataframe(rows, use_container_width=True, hide_index=True)

    summary_rows = [
        {"รายการ": "ฟังก์ชัน", "ค่า": ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED},
        {"รายการ": "โหมดจำนวน", "ค่า": "ปรับจำนวนเอง" if active_layout.calculation_mode == "manual" else "คำนวณจากอัตราส่วน"},
        {"รายการ": "พื้นที่ที่เลือก", "ค่า": fixed_mark_area_label(mark_count)},
        {"รายการ": "จำนวนมาร์ค", "ค่า": f"{mark_count:,} มาร์ค"},
        {"รายการ": "ขนาดมาร์ค", "ค่า": f"{FIXED_MARK_WIDTH_CM:.0f} × {FIXED_MARK_HEIGHT_CM:.0f} cm"},
        {"รายการ": "ตัวเลือกอัตราส่วน", "ค่า": mixed_ratio_label(items)},
        {"รายการ": "จำนวนชุดต่อ 1 มาร์ค", "ค่า": f"{active_layout.set_count:,} ชุด/มาร์ค" if active_layout.calculation_mode == "ratio" else "-"},
        {"รายการ": "จำนวนรวมทุก Size", "ค่า": f"{active_layout.total_quantity:,} ชิ้น"},
        {"รายการ": "รูปแบบผลิต", "ค่า": MIXED_MARK_PRODUCTION_REPEAT_MODE},
        {"รายการ": "รูปแบบการเรียง", "ค่า": active_layout.layout_style},
        {"รายการ": "พื้นที่จริงจากมาร์ค", "ค่า": f"{active_layout.material_area_sqm:.2f} ตรม."},
        {"รายการ": "พื้นที่รวมระยะอนุโลม", "ค่า": f"{active_layout.tolerance_area_sqm:.2f} ตรม."},
        {"รายการ": "การใช้พื้นที่จริง", "ค่า": f"{active_layout.usage_percent:.2f}%"},
        {"รายการ": "การใช้พื้นที่รวมอนุโลม", "ค่า": f"{active_layout.tolerance_usage_percent:.2f}%"},
        {"รายการ": "ช่องไฟ", "ค่า": f"{active_layout.gap_cm:.2f} cm"},
        {"รายการ": "ระยะอนุโลม", "ค่า": f"+{FIXED_MARK_TOLERANCE_CM:.0f} cm"},
    ]
    export_text = rows_to_plain_text("สรุปคำนวนพื้นที่หลายขนาด 57x41 แบบ Exact Copy", summary_rows)
    export_text += "\n\nรายการ Size\n" + rows_to_plain_text("", rows)
    csv_export_rows = build_roll_area_export_rows(summary_rows, rows)
    render_compact_export_bar(
        title="สรุปคำนวนพื้นที่หลายขนาด 57×41 แบบ Exact Copy",
        rows=rows,
        file_prefix="multi_size_area_57x41_summary",
        extra_text=export_text,
        csv_rows=csv_export_rows,
    )


def build_roll_area_export_rows(summary_rows: list[dict], size_rows: list[dict]) -> list[dict]:
    """รวมข้อมูลสรุปและรายการ Size เป็น CSV เดียว โดยใช้คอลัมน์ชุดเดียวกันทั้งหมด"""
    columns = [
        "หมวด",
        "รายการ",
        "ค่า",
        "Size",
        "กว้าง (cm)",
        "ยาว (cm)",
        "ขนาด (cm)",
        "จำนวน",
        "ได้ต่อ 1 มาร์ค",
        "จำนวนต่อชุด/มาร์ค",
        "อัตราส่วนต่อชุด",
        "จำนวนชุดที่วางได้",
        "จำนวนชุด/มาร์ค",
        "จำนวนมาร์ค",
        "จำนวนรวม",
        "รูปแบบเรียง",
        "พื้นที่ชิ้นงานรวม",
        "การใช้พื้นที่",
        "พื้นที่จริง (ตรม.)",
        "พื้นที่คิดตามกฎ (ตรม.)",
        "หมายเหตุ",
    ]

    def blank_row(section: str = "") -> dict:
        row = {column: "" for column in columns}
        row["หมวด"] = section
        return row

    export_rows: list[dict] = []
    for row in summary_rows:
        export_row = blank_row("สรุปงาน")
        export_row["รายการ"] = row.get("รายการ", "")
        export_row["ค่า"] = row.get("ค่า", "")
        export_rows.append(export_row)

    if summary_rows and size_rows:
        export_rows.append(blank_row())

    for row in size_rows:
        export_row = blank_row("รายการ Size")
        for key in row:
            if key in export_row:
                export_row[key] = row.get(key, "")
        export_row["รายการ"] = row.get("Size", "")
        export_rows.append(export_row)

    return export_rows


# =========================================================
# User presets
# =========================================================
def get_preset_store() -> dict:
    presets = st.session_state.setdefault("user_presets", {"quantity": {}, "roll": {}})
    presets.setdefault("quantity", {})
    presets.setdefault("roll", {})
    return presets


def save_quantity_preset_from_state() -> None:
    name = str(st.session_state.get("quantity_preset_name", "")).strip()
    if not name:
        set_action_feedback("กรุณาตั้งชื่อ Preset ก่อนบันทึก", "warn")
        return
    presets = get_preset_store()
    if name not in presets["quantity"] and len(presets["quantity"]) >= PRESET_LIMIT:
        set_action_feedback(f"จำนวน Preset เกิน {PRESET_LIMIT} รายการ กรุณาลบบางรายการก่อน", "warn")
        return
    presets["quantity"][name] = {
        "sticker_unit": st.session_state.get("sticker_unit", CM_UNIT),
        "sheet_unit": st.session_state.get("sheet_unit", CM_UNIT),
        "option_unit": st.session_state.get("option_unit", CM_UNIT),
        "sheet_size_preset": st.session_state.get("sheet_size_preset", CUSTOM_PRESET),
        "sticker_shape": st.session_state.get("sticker_shape", QUICK_SHAPE_RECTANGLE),
        "sticker_width": round2(st.session_state.get("sticker_width", 10.0)),
        "sticker_height": round2(st.session_state.get("sticker_height", 10.0)),
        "sheet_width": round2(st.session_state.get("sheet_width", 57.0)),
        "sheet_height": round2(st.session_state.get("sheet_height", 41.0)),
        "gap": round2(st.session_state.get("gap", DEFAULT_STICKER_GAP_CM)),
        "gap_preset": st.session_state.get("quantity_gap_preset", DEFAULT_STICKER_GAP_PRESET),
        "tolerance": round2(st.session_state.get("tolerance", 2.0)),
        "marks_count": int(st.session_state.get("marks_count", DEFAULT_QUANTITY_MARK_COUNT)),
        "quantity_mark_preset": st.session_state.get("quantity_mark_preset", DEFAULT_QUANTITY_MARK_PRESET),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["user_presets"] = presets
    if save_user_presets(presets):
        set_action_feedback(f"บันทึก Preset คำนวณจำนวน: {name}", "add")
    else:
        set_action_feedback(st.session_state.get("last_storage_error", "บันทึก Preset ไม่สำเร็จ"), "warn")


def load_quantity_preset_from_state() -> None:
    name = str(st.session_state.get("quantity_preset_selected", "")).strip()
    presets = get_preset_store().get("quantity", {})
    data = presets.get(name)
    if not data:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะโหลด", "warn")
        return
    for key in (
        "sticker_unit", "sheet_unit", "option_unit", "sheet_size_preset",
        "sticker_shape", "sticker_width", "sticker_height", "sheet_width", "sheet_height",
        "gap", "tolerance", "marks_count",
    ):
        if key in data:
            st.session_state[key] = data[key]
    st.session_state["previous_sticker_unit"] = st.session_state.get("sticker_unit", CM_UNIT)
    st.session_state["previous_sheet_unit"] = st.session_state.get("sheet_unit", CM_UNIT)
    st.session_state["previous_option_unit"] = st.session_state.get("option_unit", CM_UNIT)
    sync_gap_and_mark_preset_keys()
    set_action_feedback(f"โหลด Preset คำนวณจำนวน: {name}", "preset")


def clear_preset_confirmations() -> None:
    st.session_state.pop("confirm_delete_quantity_preset_name", None)
    st.session_state.pop("confirm_delete_roll_preset_name", None)


def cancel_preset_confirmation() -> None:
    clear_preset_confirmations()
    set_action_feedback("ยกเลิกคำสั่งแล้ว", "info")


def request_delete_quantity_preset_from_state() -> None:
    name = str(st.session_state.get("quantity_preset_selected", "")).strip()
    presets = get_preset_store()
    if name in presets.get("quantity", {}):
        clear_preset_confirmations()
        st.session_state["confirm_delete_quantity_preset_name"] = name
        set_action_feedback(f"ต้องยืนยันก่อนลบ Preset คำนวณจำนวน: {name}", "warn")
    else:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะลบ", "warn")


def confirm_delete_quantity_preset_from_state() -> None:
    st.session_state["quantity_preset_selected"] = st.session_state.get("confirm_delete_quantity_preset_name", "")
    clear_preset_confirmations()
    delete_quantity_preset_from_state()


def delete_quantity_preset_from_state() -> None:
    name = str(st.session_state.get("quantity_preset_selected", "")).strip()
    presets = get_preset_store()
    if name in presets.get("quantity", {}):
        presets["quantity"].pop(name, None)
        st.session_state["user_presets"] = presets
        if save_user_presets(presets):
            st.session_state["quantity_preset_selected"] = ""
            set_action_feedback(f"ลบ Preset คำนวณจำนวน: {name}", "delete")
        else:
            set_action_feedback(st.session_state.get("last_storage_error", "ลบ Preset ไม่สำเร็จ"), "warn")
    else:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะลบ", "warn")


def save_roll_preset_from_state() -> None:
    name = str(st.session_state.get("roll_preset_name", "")).strip()
    if not name:
        set_action_feedback("กรุณาตั้งชื่อ Preset ก่อนบันทึก", "warn")
        return
    presets = get_preset_store()
    if name not in presets["roll"] and len(presets["roll"]) >= PRESET_LIMIT:
        set_action_feedback(f"จำนวน Preset เกิน {PRESET_LIMIT} รายการ กรุณาลบบางรายการก่อน", "warn")
        return
    items = []
    for item_id in st.session_state.get("area_item_ids", []):
        item_id = int(item_id)
        name_key, width_key, height_key, qty_key = area_item_keys(item_id)
        shape_key = area_shape_key(item_id)
        items.append({
            "name": st.session_state.get(name_key, f"Size {item_id}"),
            "shape": normalize_sticker_shape(st.session_state.get(shape_key, QUICK_SHAPE_RECTANGLE)),
            "width": round2(st.session_state.get(width_key, 10.0)),
            "height": round2(st.session_state.get(height_key, 10.0)),
            "qty": int(st.session_state.get(qty_key, 1)),
            "weight": int(st.session_state.get(f"mixed_ratio_weight_{item_id}", 1)),
        })
    presets["roll"][name] = {
        "area_unit": st.session_state.get("area_unit", CM_UNIT),
        "roll_width_preset": st.session_state.get("roll_width_preset", DEFAULT_ROLL_WIDTH_PRESET),
        "roll_print_width": round2(st.session_state.get("roll_print_width", 120.0)),
        "roll_gap": round2(st.session_state.get("roll_gap", DEFAULT_STICKER_GAP_CM)),
        "roll_gap_preset": st.session_state.get("roll_gap_preset", DEFAULT_STICKER_GAP_PRESET),
        "fixed_quantity_mark_tolerance": round2(st.session_state.get("fixed_quantity_mark_tolerance", DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM)),
        "face_charge_threshold": round2(st.session_state.get("face_charge_threshold", 60.0)),
        "waste_threshold_percent": round2(st.session_state.get("waste_threshold_percent", 40.0)),
        "roll_margin_left": round2(st.session_state.get("roll_margin_left", 0.0)),
        "roll_margin_right": round2(st.session_state.get("roll_margin_right", 0.0)),
        "roll_head_margin": round2(st.session_state.get("roll_head_margin", 0.0)),
        "roll_tail_margin": round2(st.session_state.get("roll_tail_margin", 0.0)),
        "roll_auto_rotate": bool(st.session_state.get("roll_auto_rotate", True)),
        "roll_layout_mode": st.session_state.get("roll_layout_mode", ROLL_LAYOUT_MODE_SMART),
        "roll_area_calculation_mode": st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY),
        "target_area_sqm": round2(st.session_state.get("target_area_sqm", DEFAULT_TARGET_AREA_SQM)),
        "target_min_mark_count": int(st.session_state.get("target_min_mark_count", DEFAULT_TARGET_MIN_MARK_COUNT)),
        "target_mark_step": int(st.session_state.get("target_mark_step", DEFAULT_TARGET_MARK_STEP)),
        "target_force_mark_pair": bool(st.session_state.get("target_force_mark_pair", DEFAULT_TARGET_FORCE_MARK_PAIR)),
        "fixed_mark_area_preset": st.session_state.get("fixed_mark_area_preset", DEFAULT_FIXED_MARK_AREA_PRESET),
        "fixed_mark_custom_count": int(st.session_state.get("fixed_mark_custom_count", DEFAULT_FIXED_MARK_COUNT)),
        "mixed_mark_gap_cm": round2(st.session_state.get("mixed_mark_gap_cm", DEFAULT_MIXED_MARK_GAP_CM)),
        "mixed_mark_gap_preset": st.session_state.get("mixed_mark_gap_preset", DEFAULT_STICKER_GAP_PRESET),
        "mixed_mark_gap_mm": round2(st.session_state.get("mixed_mark_gap_cm", DEFAULT_MIXED_MARK_GAP_CM) * 10),
        "mixed_mark_layout_style": st.session_state.get("mixed_mark_layout_style", MIXED_MARK_LAYOUT_STYLE_BLOCK),
        "mixed_mark_preview_marks": int(st.session_state.get("mixed_mark_preview_marks", DEFAULT_MIXED_MARK_PREVIEW_MARKS)),
        "mixed_ratio_mode": normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL)),
        "mixed_ratio_custom_text": st.session_state.get("mixed_ratio_custom_text", "1:1"),
        "mixed_fill_mode": st.session_state.get("mixed_fill_mode", MIXED_FILL_MODE_SMALLEST),
        "mixed_fill_selected_label": st.session_state.get("mixed_fill_selected_label", ""),
        "items": items,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["user_presets"] = presets
    if save_user_presets(presets):
        set_action_feedback(f"บันทึก Preset งานม้วน: {name}", "add")
    else:
        set_action_feedback(st.session_state.get("last_storage_error", "บันทึก Preset ไม่สำเร็จ"), "warn")


def load_roll_preset_from_state() -> None:
    name = str(st.session_state.get("roll_preset_selected", "")).strip()
    presets = get_preset_store().get("roll", {})
    data = presets.get(name)
    if not data:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะโหลด", "warn")
        return
    for key in (
        "area_unit", "roll_width_preset", "roll_print_width", "roll_gap", "roll_gap_preset",
        "fixed_quantity_mark_tolerance",
        "face_charge_threshold", "waste_threshold_percent", "roll_margin_left",
        "roll_margin_right", "roll_head_margin", "roll_tail_margin",
        "roll_auto_rotate", "roll_layout_mode", "roll_area_calculation_mode",
        "target_area_sqm", "target_min_mark_count", "target_mark_step", "target_force_mark_pair",
        "fixed_mark_area_preset", "fixed_mark_custom_count",
        "mixed_mark_gap_cm", "mixed_mark_gap_preset", "mixed_mark_gap_mm", "mixed_mark_layout_style", "mixed_mark_preview_marks",
    ):
        if key in data:
            st.session_state[key] = data[key]
    st.session_state["previous_area_unit"] = st.session_state.get("area_unit", CM_UNIT)
    if "mixed_mark_gap_cm" not in data and "mixed_mark_gap_mm" in data:
        st.session_state["mixed_mark_gap_cm"] = round2(float(data.get("mixed_mark_gap_mm", DEFAULT_MIXED_MARK_GAP_MM)) / 10.0)
    if st.session_state.get("fixed_mark_area_preset") not in FIXED_MARK_AREA_PRESETS:
        st.session_state["fixed_mark_area_preset"] = DEFAULT_FIXED_MARK_AREA_PRESET
        st.session_state["fixed_mark_custom_count"] = DEFAULT_FIXED_MARK_COUNT
    sync_gap_and_mark_preset_keys()
    sync_mixed_mark_gap_legacy()
    st.session_state["mixed_ratio_mode"] = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))

    for item_id in st.session_state.get("area_item_ids", []):
        clear_area_item_state(int(item_id))
    items = list(data.get("items", [])) or [{"name": "Size 1", "width": 10.0, "height": 10.0, "qty": 1}]
    new_ids = list(range(1, len(items) + 1))
    st.session_state["area_item_ids"] = new_ids
    st.session_state["area_next_id"] = len(items) + 1
    for item_id, item in zip(new_ids, items):
        name_key, width_key, height_key, qty_key = area_item_keys(item_id)
        shape_key = area_shape_key(item_id)
        st.session_state[name_key] = item.get("name", f"Size {item_id}")
        st.session_state[shape_key] = normalize_sticker_shape(item.get("shape", QUICK_SHAPE_RECTANGLE))
        st.session_state[width_key] = round2(item.get("width", 10.0))
        st.session_state[height_key] = round2(item.get("height", 10.0))
        sync_circle_height(width_key, height_key, st.session_state.get(shape_key))
        st.session_state[qty_key] = int(item.get("qty", 1))
        st.session_state[f"mixed_ratio_weight_{item_id}"] = max(1, int(item.get("weight", 1)))
    clear_area_confirmations()
    set_action_feedback(f"โหลด Preset งานม้วน: {name}", "preset")


def request_delete_roll_preset_from_state() -> None:
    name = str(st.session_state.get("roll_preset_selected", "")).strip()
    presets = get_preset_store()
    if name in presets.get("roll", {}):
        clear_preset_confirmations()
        st.session_state["confirm_delete_roll_preset_name"] = name
        set_action_feedback(f"ต้องยืนยันก่อนลบ Preset งานม้วน: {name}", "warn")
    else:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะลบ", "warn")


def confirm_delete_roll_preset_from_state() -> None:
    st.session_state["roll_preset_selected"] = st.session_state.get("confirm_delete_roll_preset_name", "")
    clear_preset_confirmations()
    delete_roll_preset_from_state()


def delete_roll_preset_from_state() -> None:
    name = str(st.session_state.get("roll_preset_selected", "")).strip()
    presets = get_preset_store()
    if name in presets.get("roll", {}):
        presets["roll"].pop(name, None)
        st.session_state["user_presets"] = presets
        if save_user_presets(presets):
            st.session_state["roll_preset_selected"] = ""
            set_action_feedback(f"ลบ Preset งานม้วน: {name}", "delete")
        else:
            set_action_feedback(st.session_state.get("last_storage_error", "ลบ Preset ไม่สำเร็จ"), "warn")
    else:
        set_action_feedback("ยังไม่ได้เลือก Preset ที่จะลบ", "warn")


def render_quantity_preset_manager() -> None:
    presets = get_preset_store().get("quantity", {})
    names = [""] + sorted(presets.keys())
    with st.expander("Preset งานประจำ", expanded=False):
        st.selectbox("เลือก Preset", names, key="quantity_preset_selected", format_func=lambda value: "— เลือก —" if not value else value)
        preset_cols = st.columns(2)
        with preset_cols[0]:
            st.button("โหลด", key="load_quantity_preset_button", on_click=load_quantity_preset_from_state, use_container_width=True)
        with preset_cols[1]:
            st.button("ลบ", key="delete_quantity_preset_button", on_click=request_delete_quantity_preset_from_state, use_container_width=True)
        confirm_name = st.session_state.get("confirm_delete_quantity_preset_name")
        if confirm_name:
            st.warning(f"ยืนยันลบ Preset คำนวณจำนวน: {confirm_name}")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                st.button("⚠️ ยืนยันลบ", key="confirm_delete_quantity_preset_button", on_click=confirm_delete_quantity_preset_from_state, use_container_width=True)
            with confirm_cols[1]:
                st.button("ยกเลิก", key="cancel_delete_quantity_preset_button", on_click=cancel_preset_confirmation, use_container_width=True)
        st.text_input("ชื่อ Preset ใหม่/เขียนทับ", key="quantity_preset_name", placeholder="เช่น Mark 57x41 ช่องไฟ 0.6")
        st.button("บันทึก Preset", key="save_quantity_preset_button", on_click=save_quantity_preset_from_state, use_container_width=True)
        st.caption(f"บันทึกในไฟล์ {APP_PRESET_PATH.name} สูงสุด {PRESET_LIMIT} รายการ")


def render_roll_preset_manager() -> None:
    presets = get_preset_store().get("roll", {})
    names = [""] + sorted(presets.keys())
    with st.expander("Preset งานประจำ", expanded=False):
        st.selectbox("เลือก Preset", names, key="roll_preset_selected", format_func=lambda value: "— เลือก —" if not value else value)
        preset_cols = st.columns(2)
        with preset_cols[0]:
            st.button("โหลด", key="load_roll_preset_button", on_click=load_roll_preset_from_state, use_container_width=True)
        with preset_cols[1]:
            st.button("ลบ", key="delete_roll_preset_button", on_click=request_delete_roll_preset_from_state, use_container_width=True)
        confirm_name = st.session_state.get("confirm_delete_roll_preset_name")
        if confirm_name:
            st.warning(f"ยืนยันลบ Preset งานม้วน: {confirm_name}")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                st.button("⚠️ ยืนยันลบ", key="confirm_delete_roll_preset_button", on_click=confirm_delete_roll_preset_from_state, use_container_width=True)
            with confirm_cols[1]:
                st.button("ยกเลิก", key="cancel_delete_roll_preset_button", on_click=cancel_preset_confirmation, use_container_width=True)
        st.text_input("ชื่อ Preset ใหม่/เขียนทับ", key="roll_preset_name", placeholder="เช่น 3M 120 gap 0.5")
        st.button("บันทึก Preset", key="save_roll_preset_button", on_click=save_roll_preset_from_state, use_container_width=True)
        st.caption(f"บันทึกในไฟล์ {APP_PRESET_PATH.name} สูงสุด {PRESET_LIMIT} รายการ")


# =========================================================
# Validation / Presets / State
# =========================================================
def validate_inputs(*values: float) -> list[str]:
    labels = [
        "กว้างสติกเกอร์",
        "ยาวสติกเกอร์",
        "กว้างวัสดุ",
        "ยาววัสดุ",
        "ระยะห่าง",
        "ระยะอนุโลม",
    ]
    errors = []
    for label, value in zip(labels, values):
        if value < 0:
            errors.append(f"{label} ต้องไม่ติดลบ")
    if values[0] <= 0 or values[1] <= 0:
        errors.append("ขนาดสติกเกอร์ต้องมากกว่า 0")
    if values[2] <= 0 or values[3] <= 0:
        errors.append("ขนาดวัสดุพิมพ์ต้องมากกว่า 0")
    return errors


def apply_sheet_preset_before_widgets() -> None:
    preset_name = st.session_state.get("sheet_size_preset", CUSTOM_PRESET)
    preset_value = SHEET_SIZE_PRESETS_CM.get(preset_name)
    if preset_value is None:
        return
    width_cm, height_cm = preset_value
    unit = st.session_state.get("sheet_unit", CM_UNIT)
    st.session_state["sheet_width"] = from_cm(width_cm, unit)
    st.session_state["sheet_height"] = from_cm(height_cm, unit)


def normalize_roll_width_preset_session() -> None:
    """บังคับ Preset หน้าพิมพ์ให้เป็นตัวเลือกที่เปิดใช้งานเท่านั้น

    ใช้กันค่าเก่าจาก Session/Preset ที่ไม่ได้เปิดใช้งานแล้ว
    ไม่ให้ค้างอยู่ใน Selectbox หลังจากตัดตัวเลือกออกแล้ว
    """
    preset_name = st.session_state.get("roll_width_preset", DEFAULT_ROLL_WIDTH_PRESET)
    if preset_name not in ROLL_WIDTH_PRESETS_CM:
        preset_name = DEFAULT_ROLL_WIDTH_PRESET
        st.session_state["roll_width_preset"] = preset_name

    unit = st.session_state.get("area_unit", CM_UNIT)
    st.session_state["roll_print_width"] = from_cm(ROLL_WIDTH_PRESETS_CM[preset_name], unit)


def apply_roll_width_preset_before_widgets() -> None:
    normalize_roll_width_preset_session()


def init_state() -> None:
    persistent_history = load_persistent_history()
    user_presets = load_user_presets()
    legacy_mixed_mark_gap_mm = st.session_state.get("mixed_mark_gap_mm", None)
    had_mixed_mark_gap_cm = "mixed_mark_gap_cm" in st.session_state
    defaults = {
        "selected_page": PAGE_QUANTITY,
        "quantity_mode": MODE_EASY,
        "area_mode": MODE_EASY,
        "sheet_size_preset": CUSTOM_PRESET,
        "roll_width_preset": DEFAULT_ROLL_WIDTH_PRESET,
        "sticker_shape": QUICK_SHAPE_RECTANGLE,
        "sticker_width": 10.0,
        "sticker_height": 10.0,
        "sheet_width": 57.0,
        "sheet_height": 41.0,
        "gap": DEFAULT_STICKER_GAP_CM,
        "quantity_gap_preset": DEFAULT_STICKER_GAP_PRESET,
        "tolerance": 2.0,
        "marks_count": DEFAULT_QUANTITY_MARK_COUNT,
        "quantity_mark_preset": DEFAULT_QUANTITY_MARK_PRESET,
        "sticker_unit": CM_UNIT,
        "sheet_unit": CM_UNIT,
        "option_unit": CM_UNIT,
        "previous_sticker_unit": CM_UNIT,
        "previous_sheet_unit": CM_UNIT,
        "previous_option_unit": CM_UNIT,
        "area_unit": CM_UNIT,
        "previous_area_unit": CM_UNIT,
        "roll_print_width": 120.0,
        "roll_gap": DEFAULT_STICKER_GAP_CM,
        "roll_gap_preset": DEFAULT_STICKER_GAP_PRESET,
        "fixed_quantity_mark_tolerance": DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM,
        "face_charge_threshold": 60.0,
        "waste_threshold_percent": 40.0,
        "roll_margin_left": 0.0,
        "roll_margin_right": 0.0,
        "roll_head_margin": 0.0,
        "roll_tail_margin": 0.0,
        "roll_auto_rotate": True,
        "roll_use_plotly_preview": True,
        "roll_layout_mode": ROLL_LAYOUT_MODE_SMART,
        "roll_area_calculation_mode": ROLL_AREA_CALC_MODE_FIXED_QUANTITY,
        "target_area_sqm": DEFAULT_TARGET_AREA_SQM,
        "target_min_mark_count": DEFAULT_TARGET_MIN_MARK_COUNT,
        "target_mark_step": DEFAULT_TARGET_MARK_STEP,
        "target_force_mark_pair": DEFAULT_TARGET_FORCE_MARK_PAIR,
        "fixed_mark_area_preset": DEFAULT_FIXED_MARK_AREA_PRESET,
        "fixed_mark_custom_count": DEFAULT_FIXED_MARK_COUNT,
        "mixed_mark_gap_cm": DEFAULT_MIXED_MARK_GAP_CM,
        "mixed_mark_gap_preset": DEFAULT_STICKER_GAP_PRESET,
        "mixed_mark_gap_mm": DEFAULT_MIXED_MARK_GAP_MM,
        "mixed_mark_layout_style": MIXED_MARK_LAYOUT_STYLE_BLOCK,
        "mixed_mark_preview_marks": DEFAULT_MIXED_MARK_PREVIEW_MARKS,
        "mixed_ratio_mode": MIXED_RATIO_MODE_EQUAL,
        "mixed_ratio_custom_text": "1:1",
        "mixed_fill_mode": MIXED_FILL_MODE_SMALLEST,
        "mixed_fill_selected_label": "",
        "mixed_manual_mode": False,
        "quantity_history": persistent_history.get("quantity_history", []),
        "last_quantity_history_signature": persistent_history.get("last_quantity_history_signature", ""),
        "roll_history": persistent_history.get("roll_history", []),
        "last_roll_history_signature": persistent_history.get("last_roll_history_signature", ""),
        "user_presets": user_presets,
        "quantity_preset_name": "",
        "quantity_preset_selected": "",
        "roll_preset_name": "",
        "roll_preset_selected": "",
        "quick_unit": CM_UNIT,
        "quick_mark_mode": QUICK_MARK_MODE_OFF,
        "quick_gap_preset": DEFAULT_STICKER_GAP_PRESET,
        "quick_auto_rotate": True,
        "quick_preview_marks": 4,
        "quick_item_ids": [1],
        "quick_next_id": 2,
        "area_item_ids": [1],
        "area_next_id": 2,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # บังคับล้างค่า Preset หน้ากว้างเก่าตั้งแต่เริ่ม app
    # กันกรณี Streamlit/ไฟล์ preset ยังจำค่าที่ถูกถอดออกไปแล้ว
    normalize_roll_width_preset_session()

    if legacy_mixed_mark_gap_mm is not None and not had_mixed_mark_gap_cm:
        st.session_state["mixed_mark_gap_cm"] = round2(float(legacy_mixed_mark_gap_mm) / 10.0)
    sync_mixed_mark_gap_legacy()
    st.session_state["mixed_ratio_mode"] = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))
    for item_id in st.session_state.get("area_item_ids", []):
        set_area_item_defaults(int(item_id))
        st.session_state.setdefault(f"mixed_ratio_weight_{int(item_id)}", 1)


# =========================================================
# CSS
# =========================================================
def inject_css() -> None:
    st.markdown(
        """
        <style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700;800;900&family=Inter:wght@400;500;600;700;800;900&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

:root {
    --bg: #070b12;
    --bg-2: #0c1120;
    --panel: rgba(16, 22, 36, 0.90);
    --panel-2: rgba(22, 30, 46, 0.88);
    --panel-3: rgba(255,255,255,0.04);
    --line: rgba(148, 163, 184, 0.14);
    --line-2: rgba(255,255,255,0.08);
    --text: #f1f5f9;
    --text-soft: #cbd5e1;
    --muted: #7d8fa3;
    --muted-2: #a8b8ca;
    --accent: #f59e0b;
    --accent-2: #fbbf24;
    --accent-3: #fb923c;
    --accent-glow: rgba(245,158,11,0.28);
    --good: #34d399;
    --good-2: #86efac;
    --danger: #fb7185;
    --danger-2: #ef4444;
    --info: #60a5fa;
    --warn: #fbbf24;
    --radius-xs: 10px;
    --radius: 18px;
    --radius-lg: 26px;
    --radius-xl: 34px;
    --shadow: 0 24px 80px rgba(0,0,0,0.48);
    --shadow-soft: 0 14px 40px rgba(0,0,0,0.30);
    --shadow-glow: 0 0 60px rgba(245,158,11,0.10);
}

@keyframes toastInOut {
    0% { opacity: 0; transform: translateY(-10px) scale(.98); }
    12% { opacity: 1; transform: translateY(0) scale(1); }
    84% { opacity: 1; transform: translateY(0) scale(1); }
    100% { opacity: 0; transform: translateY(-7px) scale(.99); }
}
@keyframes buttonSheen {
    0% { transform: translateX(-130%) skewX(-18deg); }
    100% { transform: translateX(230%) skewX(-18deg); }
}
@keyframes heroGlow {
    0%, 100% { opacity: 0.55; transform: translate3d(0,0,0) scale(1); filter: blur(0px); }
    33% { opacity: 0.80; transform: translate3d(-1.5rem, 0.8rem, 0) scale(1.06); filter: blur(1px); }
    66% { opacity: 0.70; transform: translate3d(0.8rem, -0.4rem, 0) scale(1.03); filter: blur(0.5px); }
}
@keyframes subtlePulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 0.9; }
}

html, body, .stApp,
.stApp p, .stApp div, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    font-family: "Noto Sans Thai", "Inter", sans-serif !important;
    letter-spacing: 0 !important;
}

.material-icons, .material-icons-outlined, .material-icons-round,
.material-symbols-rounded, .material-symbols-outlined, .material-symbols-sharp, [data-testid="stIconMaterial"] {
    font-family: "Material Symbols Rounded" !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 20px !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
    font-feature-settings: "liga" !important;
    font-variation-settings: "FILL" 0, "wght" 500, "GRAD" 0, "opsz" 24 !important;
}

.stApp {
    color: var(--text);
    background:
        radial-gradient(ellipse at 15% -5%, rgba(245, 158, 11, 0.18) 0%, transparent 35%),
        radial-gradient(ellipse at 92% 8%, rgba(96, 165, 250, 0.10) 0%, transparent 32%),
        radial-gradient(ellipse at 50% 95%, rgba(52, 211, 153, 0.07) 0%, transparent 28%),
        radial-gradient(ellipse at 78% 55%, rgba(167, 139, 250, 0.05) 0%, transparent 24%),
        linear-gradient(180deg, #060a11 0%, #090e18 40%, #060910 100%);
    background-attachment: fixed;
}
#MainMenu, footer { visibility: hidden; height: 0; }
div[data-testid="stMainBlockContainer"] {
    padding-top: 2.15rem;
    padding-bottom: 3.25rem;
    max-width: 1500px;
}
hr { border-color: var(--line); margin: 1.15rem 0; }

/* Header / Sidebar control */
[data-testid="stHeader"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    height: 3.35rem !important;
    background: rgba(5, 8, 14, 0.85) !important;
    backdrop-filter: blur(24px) saturate(160%) brightness(0.96);
    border-bottom: 1px solid rgba(245, 158, 11, 0.10);
    box-shadow: 0 1px 0 rgba(255,255,255,0.03), 0 8px 32px rgba(0,0,0,0.32);
    z-index: 999990 !important;
}
[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 0.66rem !important;
    left: 0.75rem !important;
    z-index: 999999 !important;
    pointer-events: auto !important;
}
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
    pointer-events: auto !important;
}
[data-testid="collapsedControl"] button,
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button {
    min-width: 46px !important;
    height: 37px !important;
    border-radius: 999px !important;
    padding: 0 .82rem !important;
    color: #1f1305 !important;
    border: 1px solid rgba(251, 191, 36, 0.76) !important;
    background: linear-gradient(135deg, #fde68a 0%, #f59e0b 58%, #ea580c 100%) !important;
    box-shadow: 0 10px 28px rgba(245, 158, 11, .2), 0 8px 22px rgba(0,0,0,.38) !important;
    transition: transform .16s ease, box-shadow .16s ease, filter .16s ease !important;
}
[data-testid="collapsedControl"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover,
[data-testid="stSidebarCollapseButton"] button:hover {
    transform: translateY(-1px) !important;
    filter: brightness(1.04) saturate(1.05) !important;
    box-shadow: 0 14px 34px rgba(245, 158, 11, .25), 0 10px 26px rgba(0,0,0,.46) !important;
}
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg {
    color: #1f1305 !important;
    fill: #1f1305 !important;
    stroke: #1f1305 !important;
}
[data-testid="collapsedControl"] button::after,
[data-testid="stSidebarCollapsedControl"] button::after {
    content: "เมนู";
    font-family: "Noto Sans Thai", "Inter", sans-serif !important;
    font-size: .82rem;
    font-weight: 900;
    margin-left: .34rem;
    color: #1f1305;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background:
        radial-gradient(ellipse at 8% 2%, rgba(245, 158, 11, 0.09) 0%, transparent 45%),
        radial-gradient(ellipse at 90% 95%, rgba(96,165,250,0.05) 0%, transparent 40%),
        linear-gradient(180deg, rgba(10, 14, 24, 0.99) 0%, rgba(7, 10, 18, 0.99) 100%);
    border-right: 1px solid rgba(245,158,11,0.08);
    box-shadow: 20px 0 80px rgba(0,0,0,0.48), inset -1px 0 0 rgba(255,255,255,0.03);
}
section[data-testid="stSidebar"] > div:first-child { padding-top: 1.15rem; }
.sidebar-brand {
    position: relative;
    overflow: hidden;
    padding: 1.1rem 1.05rem 1rem;
    border-radius: 24px;
    border: 1px solid rgba(251,191,36,0.22);
    background:
        radial-gradient(ellipse at 0% 0%, rgba(251,191,36,0.20) 0%, transparent 60%),
        radial-gradient(ellipse at 100% 100%, rgba(96,165,250,0.07) 0%, transparent 50%),
        linear-gradient(145deg, rgba(18,26,40,0.98), rgba(10,15,24,0.98));
    box-shadow: 0 20px 50px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.06);
    margin-bottom: 1rem;
}
.sidebar-brand::after {
    content: "";
    position: absolute;
    width: 9rem;
    height: 9rem;
    right: -4.5rem;
    top: -4.6rem;
    background: radial-gradient(circle, rgba(245,158,11,.28), transparent 64%);
    pointer-events: none;
}
.sidebar-brand .brand-top {
    color: var(--accent-2);
    font-weight: 900;
    font-size: .76rem;
    text-transform: uppercase;
    letter-spacing: .08em !important;
}
.sidebar-brand .brand-title {
    color: var(--text);
    font-weight: 900;
    font-size: 1.2rem;
    line-height: 1.2;
    margin-top: .25rem;
}
.sidebar-brand .brand-sub {
    color: var(--muted-2);
    font-size: .82rem;
    line-height: 1.5;
    margin-top: .42rem;
}
.sidebar-nav-label {
    color: var(--muted) !important;
    font-size: .72rem;
    font-weight: 900;
    letter-spacing: .06em !important;
    text-transform: uppercase;
    margin: .8rem 0 .42rem;
}
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] label { color: var(--text) !important; }
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 1.08rem;
    font-weight: 900;
    margin: .65rem 0 .15rem;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
    line-height: 1.55;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
    border-radius: 20px;
    border: 1px solid rgba(148,163,184,0.10);
    background: rgba(255,255,255,0.028);
    box-shadow: 0 10px 30px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.04);
    overflow: hidden;
    transition: border-color .20s ease, box-shadow .20s ease;
}
section[data-testid="stSidebar"] [data-testid="stExpander"]:hover {
    border-color: rgba(245,158,11,0.14);
    box-shadow: 0 12px 36px rgba(0,0,0,0.24), inset 0 1px 0 rgba(255,255,255,0.05);
}
section[data-testid="stSidebar"] [data-testid="stExpander"] details summary {
    font-weight: 900 !important;
}

/* Hero / page header */
.hero {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(245,158,11,0.14);
    border-radius: var(--radius-xl);
    padding: 1.55rem 1.65rem;
    margin: 0 0 1.25rem;
    background:
        radial-gradient(ellipse at 10% 5%, rgba(245,158,11,0.20) 0%, transparent 42%),
        radial-gradient(ellipse at 88% 10%, rgba(96,165,250,0.12) 0%, transparent 36%),
        radial-gradient(ellipse at 50% 110%, rgba(52,211,153,0.06) 0%, transparent 38%),
        linear-gradient(145deg, rgba(18,26,42,0.96) 0%, rgba(10,15,24,0.98) 100%);
    box-shadow: var(--shadow), var(--shadow-glow), inset 0 1px 0 rgba(255,255,255,0.05);
    backdrop-filter: blur(24px) saturate(140%);
}
.hero::before {
    content: "";
    position: absolute;
    inset: -38% -12% auto 50%;
    height: 26rem;
    background: radial-gradient(circle, rgba(251,191,36,.28), transparent 62%);
    animation: heroGlow 7s ease-in-out infinite;
    pointer-events: none;
}
.hero::after {
    content: "";
    position: absolute;
    inset: 0;
    background-image: linear-gradient(rgba(255,255,255,.055) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: radial-gradient(circle at 45% 35%, black, transparent 68%);
    opacity: .3;
    pointer-events: none;
}
.hero-content { position: relative; z-index: 2; max-width: 1060px; }
.kicker, .hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: .45rem;
    color: #1f1305;
    font-size: .78rem;
    font-weight: 900;
    margin-bottom: .62rem;
    padding: .32rem .68rem;
    border-radius: 999px;
    background: linear-gradient(135deg, #fde68a, #f59e0b);
    box-shadow: 0 8px 24px rgba(245,158,11,.22);
}
.hero h1 {
    color: var(--text);
    font-size: clamp(2rem, 4vw, 3.55rem);
    line-height: 1.06;
    margin: 0;
    font-weight: 900;
    letter-spacing: -.035em !important;
}
.hero p {
    color: var(--text-soft);
    font-size: 1.02rem;
    line-height: 1.7;
    margin: .78rem 0 0;
    max-width: 960px;
}
.hero-meta {
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
    margin-top: 1rem;
}
.hero-chip {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    color: #e7eef9;
    font-size: .82rem;
    font-weight: 800;
    padding: .42rem .72rem;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,.12);
    background: rgba(255,255,255,.06);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.05);
}
.hero-chip.good { color: #cbffdf; border-color: rgba(52,211,153,.30); background: rgba(52,211,153,.08); }
.hero-chip.info { color: #d9ecff; border-color: rgba(96,165,250,.30); background: rgba(96,165,250,.08); }
.hero-chip.warn { color: #fff0bd; border-color: rgba(251,191,36,.34); background: rgba(251,191,36,.08); }

.section-title {
    position: relative;
    color: var(--text);
    font-size: 1.18rem;
    font-weight: 900;
    margin: 1.55rem 0 .82rem;
    padding-left: .82rem;
    line-height: 1.25;
}
.section-title::before {
    content: "";
    position: absolute;
    left: 0;
    top: .08rem;
    bottom: .08rem;
    width: 4px;
    border-radius: 999px;
    background: linear-gradient(180deg, #fde68a, #f59e0b 50%, #ea580c);
    box-shadow: 0 0 14px rgba(245,158,11,0.55), 0 0 28px rgba(245,158,11,0.20);
}

/* Cards */
.summary-card, .detail-card {
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(ellipse at 85% 5%, rgba(255,255,255,0.05) 0%, transparent 40%),
        linear-gradient(160deg, rgba(22,30,46,0.94) 0%, rgba(12,18,30,0.98) 100%);
    border: 1px solid rgba(148,163,184,0.11);
    border-radius: var(--radius-lg);
    padding: 1.15rem 1.2rem;
    min-height: 124px;
    box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255,255,255,0.045);
    backdrop-filter: blur(16px) saturate(130%);
    transition: border-color .22s ease, transform .22s ease, box-shadow .22s ease !important;
    cursor: default !important;
}

/* KPI cards: บังคับให้กล่องตัวเลขด้านบนมีขนาดเท่ากันทุกใบ */
.summary-card.metric-card {
    width: 100%;
    height: 190px;
    min-height: 190px;
    max-height: 190px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
}
.summary-card.metric-card .metric-label {
    min-height: 2.65em;
    display: flex;
    align-items: flex-start;
}
.summary-card.metric-card .metric-value {
    min-height: 2.45em;
    display: flex;
    align-items: flex-start;
}
.summary-card.metric-card .metric-detail {
    margin-top: auto;
    min-height: 2.95em;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.summary-card::after, .detail-card::after {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 80% 0%, rgba(255,255,255,.08), transparent 36%);
    pointer-events: none;
}
.summary-card:hover, .detail-card:hover {
    transform: translateY(-2px) !important;
    border-color: rgba(245,158,11,0.22) !important;
    box-shadow: 0 24px 56px rgba(0,0,0,0.38), 0 0 0 1px rgba(245,158,11,0.08), inset 0 1px 0 rgba(255,255,255,0.06) !important;
}
.accent-card {
    background:
        radial-gradient(ellipse at 15% 10%, rgba(255,255,255,0.20) 0%, transparent 40%),
        linear-gradient(135deg, #fde68a 0%, #f59e0b 50%, #ea580c 100%) !important;
    border-color: rgba(253,230,138,0.65) !important;
    box-shadow: 0 20px 50px rgba(245,158,11,0.32), 0 0 80px rgba(245,158,11,0.12) !important;
}
.metric-label {
    position: relative;
    z-index: 2;
    color: var(--muted);
    font-size: .88rem;
    font-weight: 800;
    margin-bottom: .42rem;
}
.metric-value {
    position: relative;
    z-index: 2;
    color: var(--text);
    font-size: clamp(1.42rem, 2.45vw, 2.08rem);
    font-weight: 900;
    line-height: 1.08;
    letter-spacing: -.02em !important;
}
.metric-detail {
    position: relative;
    z-index: 2;
    color: var(--muted-2);
    font-size: .86rem;
    line-height: 1.55;
    margin-top: .64rem;
}
.accent-card .metric-label, .accent-card .metric-value, .accent-card .metric-detail { color: #211604 !important; }
.detail-card { min-height: auto; margin-bottom: .85rem; padding: 1rem 1.05rem; }
.detail-row {
    position: relative;
    z-index: 2;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    border-bottom: 1px solid rgba(148,163,184,.13);
    padding: .74rem 0;
    transition: background .16s ease, padding .16s ease;
}
.detail-row:first-child { padding-top: 0; }
.detail-row:last-child { border-bottom: 0; padding-bottom: 0; }
.detail-row:hover { background: rgba(245,158,11,0.04); margin-left: -.5rem; margin-right: -.5rem; padding-left: .5rem; padding-right: .5rem; border-radius: 14px; border-color: rgba(245,158,11,0.10); }
.detail-label { color: var(--muted); font-weight: 800; }
.detail-value { color: var(--text); font-weight: 900; text-align: right; }

/* Status pills */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: .38rem;
    border-radius: 999px;
    padding: .38rem .76rem;
    font-weight: 900;
    font-size: .85rem;
    margin: 0 .48rem .7rem 0;
    cursor: default;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.06);
}
.status-pill::before { content: "•"; font-size: 1.18rem; line-height: .5; }
.status-pill.good { color: #bbf7d0; border: 1px solid rgba(52,211,153,0.30); background: rgba(52,211,153,0.08); box-shadow: 0 0 20px rgba(52,211,153,0.06); }
.status-pill.warn { color: #fef08a; border: 1px solid rgba(251,191,36,0.34); background: rgba(251,191,36,0.08); box-shadow: 0 0 20px rgba(251,191,36,0.06); }
.status-pill.danger { color: #fecdd3; border: 1px solid rgba(251,113,133,0.34); background: rgba(251,113,133,0.08); box-shadow: 0 0 20px rgba(251,113,133,0.06); }
.status-pill.info { color: #bfdbfe; border: 1px solid rgba(96,165,250,0.34); background: rgba(96,165,250,0.08); box-shadow: 0 0 20px rgba(96,165,250,0.06); }

/* Inputs */
div[data-baseweb="input"],
div[data-baseweb="select"] > div,
textarea {
    background: rgba(10, 16, 30, 0.88) !important;
    border: 1px solid rgba(148,163,184,0.14) !important;
    border-radius: var(--radius) !important;
    transition: border-color .20s ease, box-shadow .20s ease, background .20s ease !important;
    box-shadow: inset 0 2px 6px rgba(0,0,0,0.20) !important;
}
div[data-baseweb="input"]:hover,
div[data-baseweb="select"] > div:hover,
textarea:hover {
    border-color: rgba(148,163,184,0.28) !important;
    background: rgba(14, 22, 38, 0.94) !important;
    box-shadow: inset 0 2px 6px rgba(0,0,0,0.22), 0 0 0 1px rgba(255,255,255,0.03) !important;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="select"] > div:focus-within,
textarea:focus {
    border-color: rgba(245,158,11,0.75) !important;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.12), inset 0 2px 6px rgba(0,0,0,0.22) !important;
    background: rgba(16, 25, 42, 0.96) !important;
}
.stTextInput input, .stNumberInput input, textarea {
    color: var(--text) !important;
    font-weight: 750 !important;
}
.stNumberInput button {
    border-radius: 11px !important;
    background: rgba(255,255,255,.055) !important;
    border: 1px solid rgba(148,163,184,.20) !important;
    transition: background .16s ease, border-color .16s ease !important;
}
.stNumberInput button:hover {
    background: rgba(245,158,11,.13) !important;
    border-color: rgba(245,158,11,.38) !important;
}

/* Main menu cards: apply only to selected_page radio in Sidebar */
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radiogroup"] {
    display: flex !important;
    flex-direction: column !important;
    gap: .72rem !important;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"] {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    gap: .78rem !important;
    min-height: 74px !important;
    padding: .86rem 1.1rem .86rem 4.55rem !important;
    border-radius: 24px !important;
    border: 1px solid rgba(148,163,184,.22) !important;
    background: linear-gradient(135deg, rgba(36,48,67,.98), rgba(23,32,47,.96)) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.055), 0 10px 28px rgba(0,0,0,.22) !important;
    transition: transform .16s ease, border-color .16s ease, background .16s ease, box-shadow .16s ease, filter .16s ease !important;
    cursor: pointer !important;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"]:hover {
    transform: translateY(-1px) !important;
    border-color: rgba(251,191,36,.38) !important;
    background: linear-gradient(135deg, rgba(45,58,79,.98), rgba(25,35,52,.96)) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.07), 0 14px 34px rgba(0,0,0,.28) !important;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"][aria-checked="true"] {
    border-color: rgba(251,191,36,.72) !important;
    background:
        radial-gradient(circle at 7% 50%, rgba(251,191,36,.38), transparent 5rem),
        linear-gradient(135deg, rgba(99,85,21,.96), rgba(74,59,17,.94)) !important;
    box-shadow: 0 0 0 1px rgba(245,158,11,.16), 0 16px 36px rgba(245,158,11,.12), 0 14px 32px rgba(0,0,0,.30) !important;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"] p {
    color: var(--text) !important;
    font-size: .98rem !important;
    font-weight: 900 !important;
    line-height: 1.38 !important;
    margin: 0 !important;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"]:nth-child(1) p::before {
    content: "🧮";
    margin-right: .5rem;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"]:nth-child(2) p::before {
    content: "📦";
    margin-right: .5rem;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"]:nth-child(3) p::before {
    content: "🧩";
    margin-right: .5rem;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"]::before {
    content: "";
    position: absolute;
    left: 1.02rem;
    top: 50%;
    width: 30px;
    height: 30px;
    border-radius: 999px;
    transform: translateY(-50%);
    border: 2px solid rgba(148,163,184,.32);
    background: #0e1624;
    box-shadow: inset 0 0 0 4px rgba(2,6,23,.60), 0 0 0 1px rgba(255,255,255,.04), 0 5px 12px rgba(0,0,0,.30);
    pointer-events: none;
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"][aria-checked="true"]::before {
    border-color: rgba(251,191,36,.94);
    background: radial-gradient(circle, #10100c 0 24%, #f59e0b 27% 100%);
    box-shadow: 0 0 0 6px rgba(245,158,11,.20), 0 8px 18px rgba(245,158,11,.24);
}
section[data-testid="stSidebar"] .st-key-selected_page .stRadio [role="radio"] > div:first-child {
    opacity: 0 !important;
    width: 0 !important;
    min-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Main menu cards rendered as buttons: robust across Streamlit versions */
section[data-testid="stSidebar"] .st-key-main_menu_quantity button,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    width: 100% !important;
    min-height: 74px !important;
    padding: .86rem 1.1rem .86rem 4.55rem !important;
    margin: 0 0 .72rem 0 !important;
    border-radius: 24px !important;
    border: 1px solid rgba(148,163,184,.22) !important;
    background: linear-gradient(135deg, rgba(36,48,67,.98), rgba(23,32,47,.96)) !important;
    color: var(--text) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.055), 0 10px 28px rgba(0,0,0,.22) !important;
    transition: border-color .16s ease, background .16s ease, box-shadow .16s ease, filter .16s ease !important;
    text-align: left !important;
    white-space: normal !important;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button:hover,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button:hover,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button:hover {
    transform: none !important;
    border-color: rgba(251,191,36,.38) !important;
    background: linear-gradient(135deg, rgba(45,58,79,.98), rgba(25,35,52,.96)) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.07), 0 14px 34px rgba(0,0,0,.28) !important;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button p,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button p,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button p {
    color: var(--text) !important;
    font-size: .98rem !important;
    font-weight: 900 !important;
    line-height: 1.38 !important;
    margin: 0 !important;
    text-align: left !important;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button::before {
    content: "";
    position: absolute;
    left: 1.02rem;
    top: 50%;
    width: 30px;
    height: 30px;
    border-radius: 999px;
    transform: translateY(-50%);
    border: 2px solid rgba(148,163,184,.32);
    background: #0e1624;
    box-shadow: inset 0 0 0 4px rgba(2,6,23,.60), 0 0 0 1px rgba(255,255,255,.04), 0 5px 12px rgba(0,0,0,.30);
    pointer-events: none;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button::after,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button::after,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 24px;
    pointer-events: none;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button:hover::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button:hover::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button:hover::before,
section[data-testid="stSidebar"] .st-key-main_menu_quantity button:active::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button:active::before,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button:active::before {
    animation: none !important;
    transform: translateY(-50%) !important;
}
section[data-testid="stSidebar"] .st-key-main_menu_quantity button:active,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_quantity button:active,
section[data-testid="stSidebar"] .st-key-main_menu_fixed_mark_mixed button:active {
    transform: none !important;
}

/* Buttons */
div.stButton > button,
[data-testid="stDownloadButton"] button {
    position: relative !important;
    overflow: hidden !important;
    min-height: 2.52rem !important;
    border-radius: 999px !important;
    font-weight: 900 !important;
    letter-spacing: 0 !important;
    color: var(--text-soft) !important;
    border: 1px solid rgba(148,163,184,0.16) !important;
    background: linear-gradient(160deg, rgba(38,52,72,0.98) 0%, rgba(20,30,48,0.98) 100%) !important;
    box-shadow: 0 10px 28px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.06) !important;
    transition: transform .20s cubic-bezier(.34,1.56,.64,1), box-shadow .20s ease, filter .20s ease, border-color .20s ease !important;
}
div.stButton > button::before,
[data-testid="stDownloadButton"] button::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent);
    transform: translateX(-130%) skewX(-18deg);
    pointer-events: none;
}
div.stButton > button:hover,
[data-testid="stDownloadButton"] button:hover {
    transform: translateY(-2px) !important;
    filter: brightness(1.06) !important;
    border-color: rgba(245,158,11,0.28) !important;
    box-shadow: 0 16px 36px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.08), 0 0 20px rgba(245,158,11,0.06) !important;
    color: var(--text) !important;
}
div.stButton > button:hover::before,
[data-testid="stDownloadButton"] button:hover::before { animation: buttonSheen .64s ease; }
div.stButton > button:active,
[data-testid="stDownloadButton"] button:active {
    transform: translateY(1px) scale(.99) !important;
    box-shadow: inset 0 3px 8px rgba(0,0,0,.25) !important;
}
div.stButton > button:disabled,
[data-testid="stDownloadButton"] button:disabled {
    opacity: .48 !important;
    cursor: not-allowed !important;
    transform: none !important;
    box-shadow: none !important;
}
.st-key-sidebar_add_area_item button,
.st-key-save_quantity_preset_button button,
.st-key-save_roll_preset_button button {
    color: #052e16 !important;
    border-color: rgba(134,239,172,.62) !important;
    background: linear-gradient(135deg, #bbf7d0 0%, #34d399 52%, #059669 100%) !important;
    box-shadow: 0 12px 28px rgba(52,211,153,.19) !important;
}
.st-key-sidebar_reset_area_items button,
.st-key-clear_quantity_history_button button,
.st-key-clear_roll_history_button button,
.st-key-delete_quantity_preset_button button,
.st-key-delete_roll_preset_button button,
.st-key-confirm_delete_quantity_preset_button button,
.st-key-confirm_delete_roll_preset_button button,
[class*="st-key-sidebar_remove_area_"] button,
[class*="st-key-confirm_remove_area_"] button,
.st-key-confirm_reset_area_items_button button {
    color: #fff1f2 !important;
    border-color: rgba(251,113,133,.50) !important;
    background: linear-gradient(135deg, #be123c 0%, #ef4444 100%) !important;
    box-shadow: 0 12px 28px rgba(239,68,68,.18) !important;
}
[class*="st-key-sidebar_duplicate_area_"] button,
[class*="st-key-sidebar_swap_area_"] button,
.st-key-cancel_reset_area_items_button button,
[class*="st-key-cancel_remove_area_"] button,
.st-key-cancel_delete_quantity_preset_button button,
.st-key-cancel_delete_roll_preset_button button,
.st-key-load_quantity_preset_button button,
.st-key-load_roll_preset_button button {
    color: #eef2ff !important;
    border-color: rgba(148,163,184,.22) !important;
    background: linear-gradient(135deg, rgba(71,85,105,.98), rgba(30,41,59,.98)) !important;
}
[class*="st-key-download_"] button {
    min-height: 1.75rem !important;
    padding: .06rem .54rem !important;
    font-size: .72rem !important;
    font-weight: 850 !important;
    color: rgba(248,250,252,.76) !important;
    border-color: rgba(148,163,184,.16) !important;
    background: rgba(255,255,255,.045) !important;
    box-shadow: none !important;
}
[class*="st-key-download_"] button:hover {
    transform: none !important;
    filter: none !important;
    color: rgba(248,250,252,.96) !important;
    border-color: rgba(251,191,36,.26) !important;
    background: rgba(245,158,11,.08) !important;
    box-shadow: none !important;
}
[class*="st-key-download_"] button::before,
[class*="st-key-download_"] button:hover::before {
    display: none !important;
    animation: none !important;
}
.st-key-download_quantity_preview_png button,
.st-key-download_roll_preview_png button {
    min-height: 2.35rem !important;
    padding: .22rem .86rem !important;
    font-size: .82rem !important;
    color: #f8fafc !important;
    border-color: rgba(251,191,36,.38) !important;
    background: linear-gradient(135deg, rgba(245,158,11,.18), rgba(71,85,105,.40)) !important;
    box-shadow: 0 10px 24px rgba(0,0,0,.18) !important;
}
div.stButton > button:focus-visible,
[data-testid="stDownloadButton"] button:focus-visible,
[data-testid="collapsedControl"] button:focus-visible,
[data-testid="stSidebarCollapsedControl"] button:focus-visible,
[data-testid="stSidebarCollapseButton"] button:focus-visible {
    outline: 2px solid rgba(251,191,36,.95) !important;
    outline-offset: 2px !important;
}

/* Tables / charts / alerts */
[data-testid="stDataFrame"], .stPyplot, .stAlert, [data-testid="stPlotlyChart"], .stPlotlyChart {
    border-radius: var(--radius-lg) !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid rgba(148,163,184,0.10);
    overflow: hidden;
    box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255,255,255,0.035);
    background: rgba(10,16,28,0.70);
}
.stPyplot {
    position: relative;
    border: 1px solid rgba(148,163,184,0.10);
    box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255,255,255,0.035);
    overflow: hidden;
    background: rgba(10,16,28,0.78);
}
[data-testid="stPlotlyChart"], .stPlotlyChart {
    border: 1px solid rgba(148,163,184,0.10);
    background: rgba(10,16,28,0.78);
    box-shadow: var(--shadow-soft), inset 0 1px 0 rgba(255,255,255,0.035);
    overflow: hidden;
}
.stAlert {
    border: 1px solid rgba(148,163,184,0.12) !important;
    border-radius: var(--radius) !important;
    box-shadow: 0 12px 32px rgba(0,0,0,0.20) !important;
    backdrop-filter: blur(12px) !important;
}

.action-toast {
    position: sticky;
    top: 3.7rem;
    z-index: 99998;
    display: inline-flex;
    align-items: center;
    gap: .62rem;
    margin: .15rem 0 .9rem 0;
    padding: .72rem 1rem;
    border-radius: 999px;
    border: 1px solid rgba(245,158,11,0.22);
    background: rgba(8,13,24,0.90);
    backdrop-filter: blur(24px) saturate(160%);
    box-shadow: 0 20px 50px rgba(0,0,0,0.44), 0 0 0 1px rgba(255,255,255,0.04), inset 0 1px 0 rgba(255,255,255,0.05);
    animation: toastInOut 2.7s ease both;
}
.action-toast-icon {
    width: 30px;
    height: 30px;
    border-radius: 999px;
    display: grid;
    place-items: center;
    color: #1f1305;
    font-weight: 900;
    background: linear-gradient(135deg, #fde68a, #f59e0b);
}
.action-toast-text { color: var(--text); font-weight: 900; font-size: .93rem; }
.action-toast.add .action-toast-icon { background: linear-gradient(135deg, #bbf7d0, #34d399); }
.action-toast.delete .action-toast-icon, .action-toast.reset .action-toast-icon { background: linear-gradient(135deg, #fecdd3, #fb7185); }
.action-toast.page .action-toast-icon, .action-toast.mode .action-toast-icon,
.action-toast.preset .action-toast-icon, .action-toast.rotate .action-toast-icon { background: linear-gradient(135deg, #cbd5e1, #64748b); }
.action-toast.warn .action-toast-icon { background: linear-gradient(135deg, #fde68a, #f59e0b); }

.preview-legend-card {
    padding: .95rem 1rem;
    border-radius: 18px;
    border: 1px solid rgba(148,163,184,.16);
    background: rgba(248,250,252,.96);
    box-shadow: 0 12px 28px rgba(0,0,0,.18);
    margin-top: .65rem;
}
.preview-legend-title {
    color: #475569;
    font-size: .86rem;
    font-weight: 950;
    margin-bottom: .56rem;
}
.preview-legend-row {
    display: flex;
    align-items: flex-start;
    gap: .52rem;
    padding: .34rem 0;
}
.preview-legend-dot {
    width: .58rem;
    height: .58rem;
    border-radius: 2px;
    flex: 0 0 .58rem;
    margin-top: .22rem;
    box-shadow: 0 0 0 1px rgba(15,23,42,.10);
}
.preview-legend-name {
    color: #6b7280;
    font-size: .82rem;
    line-height: 1.15;
    font-weight: 850;
}
.preview-legend-detail {
    color: #94a3b8;
    font-size: .70rem;
    line-height: 1.2;
    font-weight: 650;
    margin-top: .10rem;
}


.multi-result-head {
    background: linear-gradient(135deg, rgba(250, 204, 21, .16), rgba(56, 189, 248, .10));
    border: 1px solid rgba(250, 204, 21, .22);
    border-radius: 20px;
    padding: 18px 20px;
    margin: 16px 0 12px;
}
.multi-result-kicker {
    font-size: .78rem;
    letter-spacing: .08em;
    color: #facc15;
    font-weight: 800;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.multi-result-sentence {
    color: #f8fafc;
    font-size: 1.08rem;
    font-weight: 700;
    line-height: 1.65;
}
.multi-result-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px;
    margin: 12px 0 18px;
}
.multi-result-card {
    position: relative;
    background: rgba(15, 23, 42, .72);
    border: 1px solid rgba(148, 163, 184, .18);
    border-radius: 18px;
    padding: 14px 14px 14px 18px;
    overflow: hidden;
}
.multi-result-color { position: absolute; left: 0; top: 0; bottom: 0; width: 6px; }
.multi-result-size { color: #e2e8f0; font-weight: 900; font-size: 1rem; }
.multi-result-name { color: #94a3b8; font-size: .84rem; margin-top: 2px; }
.multi-result-qty { color: #facc15; font-size: 2rem; line-height: 1.1; font-weight: 950; margin-top: 8px; }
.multi-result-qty span { color: #cbd5e1; font-size: .9rem; font-weight: 700; }
.multi-result-meta, .multi-result-extra { color: #cbd5e1; font-size: .82rem; margin-top: 4px; }
.multi-result-extra { color: #7dd3fc; }
.compact-export-wrap {
    margin-top: .75rem;
    padding: .45rem .65rem;
    border: 1px dashed rgba(148,163,184,.16);
    border-radius: 16px;
    background: rgba(255,255,255,.025);
    display: flex;
    align-items: baseline;
    gap: .48rem;
    opacity: .82;
}
.compact-export-title {
    color: var(--accent-2);
    font-size: .68rem;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .055em !important;
}
.compact-export-note { color: var(--muted); font-size: .72rem; font-weight: 650; }
.fixed-sidebar-box {
    padding: .85rem .95rem;
    border-radius: 18px;
    border: 1px solid rgba(251,191,36,.24);
    background: linear-gradient(135deg, rgba(251,191,36,.12), rgba(15,23,42,.76));
    box-shadow: inset 0 1px 0 rgba(255,255,255,.08);
    margin: .55rem 0 .75rem 0;
}
.fixed-sidebar-title { color: #f8fafc; font-weight: 950; font-size: .98rem; }
.fixed-sidebar-line { color: #aeb5c1; font-weight: 750; font-size: .78rem; margin-top: .2rem; }
.fixed-mark-hero {
    padding: 1.2rem 1.35rem;
    border-radius: 24px;
    border: 1px solid rgba(251,191,36,.20);
    background: radial-gradient(circle at 20% 15%, rgba(251,191,36,.25), transparent 32%), linear-gradient(135deg, rgba(24,31,44,.95), rgba(10,15,24,.95));
    box-shadow: 0 18px 42px rgba(0,0,0,.28);
    margin: 0 0 1rem 0;
}
.fixed-mark-kicker { color: #f59e0b; font-weight: 950; letter-spacing: .08em !important; font-size: .72rem; }
.fixed-mark-title { color: #f8fafc; font-size: clamp(1.35rem, 2.4vw, 2.05rem); font-weight: 950; line-height: 1.2; margin-top: .18rem; }
.fixed-mark-subtitle { color: #cbd5e1; font-weight: 750; margin-top: .38rem; }
.fixed-mark-card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: .9rem;
    margin: .9rem 0 1rem 0;
}
.fixed-mark-card {
    border-radius: 22px;
    padding: 1rem;
    background: linear-gradient(145deg, rgba(30,41,59,.92), rgba(15,23,42,.96));
    border: 1px solid rgba(148,163,184,.18);
    box-shadow: 0 18px 36px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.06);
}
.fixed-card-topline { display: flex; align-items: center; justify-content: space-between; gap: .6rem; color: #f8fafc; font-weight: 950; }
.fixed-status { border-radius: 999px; padding: .22rem .5rem; font-size: .68rem; font-weight: 900; white-space: nowrap; }
.fixed-status.good { color: #bbf7d0; background: rgba(34,197,94,.12); border: 1px solid rgba(34,197,94,.25); }
.fixed-status.warn { color: #fde68a; background: rgba(245,158,11,.12); border: 1px solid rgba(245,158,11,.25); }
.fixed-card-qty { color: #fbbf24; font-size: 2.15rem; font-weight: 950; line-height: 1; margin-top: .7rem; }
.fixed-card-qty span { color: #cbd5e1; font-size: .9rem; font-weight: 850; }
.fixed-card-meta { color: #cbd5e1; font-size: .78rem; font-weight: 760; margin-top: .45rem; }
.fixed-card-gridline { color: #94a3b8; font-size: .72rem; font-weight: 650; margin-top: .38rem; }
div[data-testid="stHorizontalBlock"] { gap: .9rem; }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--muted) !important; }

@media (max-width: 900px) {
    div[data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
    .hero { padding: 1rem; border-radius: 22px; }
    .hero h1 { font-size: clamp(1.7rem, 8vw, 2.35rem); }
    .hero-meta { gap: .38rem; }
    .hero-chip { font-size: .75rem; padding: .34rem .58rem; }
    .summary-card, .detail-card { min-height: auto; padding: .92rem; border-radius: 18px; }
    .summary-card.metric-card { height: auto; min-height: 170px; max-height: none; }
    .detail-row { flex-direction: column; gap: .28rem; }
    .detail-value { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: .001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .001ms !important;
        scroll-behavior: auto !important;
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# Sidebar controls
# =========================================================
def render_quantity_sidebar_controls() -> None:
    st.markdown("## เมนูคำนวณจำนวน")
    st.caption("ตั้งค่าขนาดสติกเกอร์ วัสดุพิมพ์ ช่องไฟ และจำนวนมาร์ค")
    st.divider()

    st.radio("โหมดการใช้งาน", [MODE_EASY, MODE_DETAIL], key="quantity_mode", horizontal=True, on_change=notify_quantity_mode_change)
    is_detail = st.session_state.quantity_mode == MODE_DETAIL

    with st.expander("ขนาดสติกเกอร์", expanded=True):
        st.radio(
            "หน่วยสติกเกอร์",
            UNITS,
            key="sticker_unit",
            on_change=sync_unit_values,
            args=("sticker", ("sticker_width", "sticker_height"), "sticker_unit", "previous_sticker_unit"),
            horizontal=True,
        )
        st.selectbox("รูปทรง", QUICK_SHAPES, key="sticker_shape", help="วงกลมใช้เส้นผ่านศูนย์กลางค่าเดียว / รูปทรงอื่นใช้กว้าง×ยาว")
        sticker_shape = normalize_sticker_shape(st.session_state.get("sticker_shape", QUICK_SHAPE_RECTANGLE))
        sticker_unit_short = unit_label(st.session_state.sticker_unit)
        if sticker_shape == QUICK_SHAPE_CIRCLE:
            st.number_input(
                f"เส้นผ่านศูนย์กลาง ({sticker_unit_short})",
                min_value=0.0,
                step=0.1,
                format="%.2f",
                key="sticker_width",
                on_change=round_number_value,
                args=("sticker_width",),
            )
            st.session_state["sticker_height"] = round2(st.session_state.get("sticker_width", 0.0))
            st.caption("วงกลมใช้ค่าเดียว: กว้าง = สูง")
        else:
            sticker_cols = st.columns(2)
            with sticker_cols[0]:
                st.number_input(f"กว้าง ({sticker_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="sticker_width", on_change=round_number_value, args=("sticker_width",))
            with sticker_cols[1]:
                st.number_input(f"ยาว ({sticker_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="sticker_height", on_change=round_number_value, args=("sticker_height",))

    with st.expander("ขนาดวัสดุพิมพ์", expanded=True):
        st.radio(
            "หน่วยวัสดุพิมพ์",
            UNITS,
            key="sheet_unit",
            on_change=sync_unit_values,
            args=("sheet", ("sheet_width", "sheet_height"), "sheet_unit", "previous_sheet_unit"),
            horizontal=True,
        )
        st.selectbox("Preset วัสดุ", list(SHEET_SIZE_PRESETS_CM.keys()), key="sheet_size_preset", on_change=notify_sheet_preset_change)
        apply_sheet_preset_before_widgets()
        sheet_unit_short = unit_label(st.session_state.sheet_unit)
        sheet_cols = st.columns(2)
        with sheet_cols[0]:
            st.number_input(f"กว้าง ({sheet_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="sheet_width", on_change=round_number_value, args=("sheet_width",), disabled=st.session_state.sheet_size_preset != CUSTOM_PRESET)
        with sheet_cols[1]:
            st.number_input(f"ยาว ({sheet_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="sheet_height", on_change=round_number_value, args=("sheet_height",), disabled=st.session_state.sheet_size_preset != CUSTOM_PRESET)

    with st.expander("ระยะและจำนวนมาร์ค", expanded=is_detail):
        st.radio(
            "หน่วยระยะ",
            UNITS,
            key="option_unit",
            on_change=sync_unit_values,
            args=("option", ("gap", "tolerance"), "option_unit", "previous_option_unit"),
            horizontal=True,
        )
        option_unit_short = unit_label(st.session_state.option_unit)
        option_cols = st.columns(2)
        with option_cols[0]:
            render_gap_preset_selectbox(
                "ช่องไฟ",
                preset_key="quantity_gap_preset",
                value_key="gap",
                unit=st.session_state.option_unit,
                help_text="เลือกได้เฉพาะ 2 ระยะ: งานเล็ก 0.4 cm หรือ งานทั่วไป 0.6 cm",
            )
        with option_cols[1]:
            st.number_input(f"อนุโลม ({option_unit_short})", min_value=0.0, step=0.05, format="%.2f", key="tolerance", on_change=round_number_value, args=("tolerance",), help="ใช้เผื่อกรณีงานยอมให้ล้นขอบวัสดุได้เล็กน้อย")
        render_quantity_mark_preset_selectbox()


    render_quantity_preset_manager()

    st.info("โหมดง่ายยังคำนวณด้วยค่าช่องไฟ/อนุโลมเดิม แต่ซ่อนบางส่วนให้กรอกน้อยลง")


def render_area_sidebar_controls() -> None:
    sync_area_calc_mode_from_main_page()
    current_calc_mode = normalize_roll_area_calculation_mode(
        st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)
    )
    sidebar_title = current_calc_mode if get_area_calc_mode_from_main_page() else "เมนูคำนวณพื้นที่ม้วน"
    st.markdown(f"## {sidebar_title}")
    if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED:
        st.caption("คำนวณหลาย Size ในมาร์คมาตรฐาน 57×41 พร้อมอัตราส่วนและ Preview")
    elif current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
        st.caption("กรอกขนาดและจำนวนจริง ระบบจัดเข้ามาร์คคู่ 57cm และคำนวณพื้นที่ผลิต")
    else:
        st.caption("เลือกหน้าพิมพ์ 120/130 ตั้งค่าช่องไฟ Margin และรายการ Size สำหรับทำ Preview")
    st.divider()

    # กัน NameError: บาง session / preset เก่าอาจเรียกค่าช่องไฟก่อน radio หน่วยรายการสร้างค่าใน session_state
    st.session_state.setdefault("area_unit", CM_UNIT)
    area_unit = st.session_state.get("area_unit", CM_UNIT)
    area_unit_short = unit_label(area_unit)

    st.radio("โหมดการใช้งาน", [MODE_EASY, MODE_DETAIL], key="area_mode", horizontal=True, on_change=notify_area_mode_change)
    is_detail = st.session_state.area_mode == MODE_DETAIL

    with st.expander("ตั้งค่าพื้นที่คำนวณ", expanded=True):
        st.radio("หน่วยรายการ", UNITS, key="area_unit", on_change=sync_area_unit_values, horizontal=True)
        area_unit = st.session_state.get("area_unit", CM_UNIT)
        area_unit_short = unit_label(area_unit)

        # กันกรณี history/preset เก่ายังจำโหมดที่ถูกตัดออกไว้
        if st.session_state.get("roll_area_calculation_mode") not in ROLL_AREA_CALC_MODES:
            st.session_state["roll_area_calculation_mode"] = ROLL_AREA_CALC_MODE_FIXED_QUANTITY

        locked_calc_mode = get_area_calc_mode_from_main_page()
        if locked_calc_mode:
            st.session_state["roll_area_calculation_mode"] = locked_calc_mode
            st.markdown(
                f"""
                <div class="fixed-sidebar-box">
                    <div class="fixed-sidebar-title">เมนูหลักที่เลือก</div>
                    <div class="fixed-sidebar-line">{locked_calc_mode}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.radio(
                "วิธีคำนวณจำนวน",
                ROLL_AREA_CALC_MODES,
                key="roll_area_calculation_mode",
                help="เลือกโหมดคำนวณจากจำนวนจริง หรือฟังก์ชันคำนวนพื้นที่หลายขนาด",
                on_change=notify_roll_area_calculation_mode_change,
            )

        current_calc_mode = normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode"))
        enforce_single_area_item_for_fixed_quantity()
        if is_fixed_mark_calculation_mode(current_calc_mode):
            st.markdown(
                f"""
                <div class="fixed-sidebar-box">
                    <div class="fixed-sidebar-title">มาร์คมาตรฐาน 57×41 cm</div>
                    <div class="fixed-sidebar-line">ระยะอนุโลม +{FIXED_MARK_TOLERANCE_CM:.0f} cm · ช่องไฟปรับได้ {get_mixed_mark_gap_cm():.2f} cm</div>
                    <div class="fixed-sidebar-line">ครึ่ง ตรม. = 2 มาร์ค / 1 ตรม. = 4 มาร์ค</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.selectbox(
                "เลือกพื้นที่",
                list(FIXED_MARK_AREA_PRESETS.keys()),
                key="fixed_mark_area_preset",
                help="เลือกได้เฉพาะ ครึ่ง ตรม. (2 มาร์ค) หรือ 1 ตรม. (4 มาร์ค)",
            )
            st.session_state["fixed_mark_custom_count"] = get_fixed_mark_count()
            if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED:
                render_gap_preset_selectbox(
                    "ช่องไฟระหว่างชิ้นในมาร์ค",
                    preset_key="mixed_mark_gap_preset",
                    value_key="mixed_mark_gap_cm",
                    unit=CM_UNIT,
                    help_text="เลือกได้เฉพาะ 2 ระยะ: งานเล็ก 0.4 cm หรือ งานทั่วไป 0.6 cm",
                )
                sync_mixed_mark_gap_legacy()
                st.session_state["mixed_ratio_mode"] = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))
                st.selectbox(
                    "อัตราส่วนจำนวนเริ่มต้น",
                    MIXED_RATIO_MODES,
                    key="mixed_ratio_mode",
                    help="เลือกน้ำหนักตั้งต้นของแต่ละ Size ก่อนระบบเติมพื้นที่เหลือ",
                )
                st.caption(mixed_ratio_mode_help_text(st.session_state.get("mixed_ratio_mode")))
                if st.session_state.get("mixed_ratio_mode") == MIXED_RATIO_MODE_CUSTOM:
                    st.caption("กำหนดน้ำหนักของแต่ละ Size ได้ในกล่องรายการ Size ด้านล่าง ไม่ต้องพิมพ์ 3:1:1 เอง")
                st.selectbox(
                    "ถ้ามีพื้นที่เหลือให้ทำอย่างไร",
                    MIXED_FILL_MODES,
                    key="mixed_fill_mode",
                    help="แนะนำให้ใช้เติมชิ้นเล็กที่สุด เพื่อให้พื้นที่ที่เหลือกลายเป็นจำนวนชิ้นเพิ่ม ไม่บังคับให้ทุก Size ได้เท่ากัน",
                )
                if st.session_state.get("mixed_fill_mode") == MIXED_FILL_MODE_SELECTED:
                    fill_labels = _current_area_item_labels_for_select()
                    if fill_labels:
                        current_label = st.session_state.get("mixed_fill_selected_label")
                        index = fill_labels.index(current_label) if current_label in fill_labels else 0
                        st.selectbox(
                            "เลือก Size ที่ต้องการเติมเพิ่ม",
                            fill_labels,
                            index=index,
                            key="mixed_fill_selected_label",
                            help="เมื่อเหลือพื้นที่ ระบบจะพยายามเพิ่ม Size นี้ให้มากที่สุดก่อน",
                        )
                st.selectbox(
                    "รูปแบบการเรียงในมาร์ค",
                    MIXED_MARK_LAYOUT_STYLES,
                    key="mixed_mark_layout_style",
                    help="แบบบล็อกจะเป็นระเบียบและเร็วที่สุด / แบบประหยัดพื้นที่จะพยายามเติมช่องว่างมากขึ้นแต่ยังใช้ระบบเร็ว",
                )
                st.selectbox(
                    "จำนวนมาร์คที่แสดงใน Preview",
                    [1, 2, 4],
                    key="mixed_mark_preview_marks",
                    help="ทุกมาร์คเป็นสำเนากันอยู่แล้ว แสดง 2 มาร์คจะเร็วกว่าแสดง 4 มาร์ค",
                )
                st.caption("โหมดหลายขนาด: เลือกอัตราส่วนจากช่องด้านบน ระบบจะคำนวณจำนวนหลัก แล้วเติมพื้นที่เหลือให้ได้ชิ้นเพิ่มตามตัวเลือก")
            else:
                st.caption("โหมดแยก Size: ไม่ต้องกรอกจำนวนต่อมาร์ค — ใส่เฉพาะชื่อและขนาด แล้วระบบคำนวณจำนวนให้")
        else:
            # ต้อง normalize ก่อนสร้าง selectbox เพื่อเคลียร์ค่าเก่าที่เคยค้างใน Session/Preset
            normalize_roll_width_preset_session()
            st.selectbox(
                "Preset หน้ากว้างวัสดุ",
                list(ROLL_WIDTH_PRESETS_CM.keys()),
                key="roll_width_preset",
                on_change=notify_roll_preset_change,
            )
            apply_roll_width_preset_before_widgets()
            st.caption("เลือก Preset ตามหน้าพิมพ์จริงที่ใช้ผลิต เช่น 120 / 130 / 152 cm")

            st.markdown(
                f"""
                <div style="margin: .35rem 0 1rem; padding: .75rem .95rem; border: 1px solid rgba(148,163,184,.22); border-radius: 14px; background: rgba(15,23,42,.45);">
                    <div style="font-size: .82rem; color: #94a3b8; font-weight: 700; margin-bottom: .2rem;">หน้ากว้างที่ใช้คำนวณ ({area_unit_short})</div>
                    <div style="font-size: 1.18rem; color: #f8fafc; font-weight: 900;">{st.session_state.get('roll_print_width', 120.0):.2f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            render_gap_preset_selectbox(
                "ช่องไฟระหว่างชิ้น",
                preset_key="roll_gap_preset",
                value_key="roll_gap",
                unit=st.session_state.get("area_unit", CM_UNIT),
                help_text="เลือกได้เฉพาะ 2 ระยะ: งานเล็ก 0.4 cm หรือ งานทั่วไป 0.6 cm",
            )

            if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
                st.number_input(
                    "ขนาดอนุโลมมาร์ค 57cm (cm)",
                    min_value=0.0,
                    step=0.50,
                    format="%.2f",
                    key="fixed_quantity_mark_tolerance",
                    on_change=round_number_value,
                    args=("fixed_quantity_mark_tolerance",),
                    help="ค่าอนุโลมของมาร์ค 57cm จะเก็บเป็น cm ตลอด เช่น 57 + 2 cm = คำนวณเหมือนใช้พื้นที่วางได้ 59 cm",
                )
                fixed_quantity_tolerance_display = round2(st.session_state.get("fixed_quantity_mark_tolerance", DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM))
                st.info(
                    f"โหมดนี้แบ่งงานเป็นมาร์คคู่: กว้าง {FIXED_MARK_WIDTH_CM:.0f} cm + อนุโลม {fixed_quantity_tolerance_display:.2f} cm, "
                    f"คำนวณความยาวตามจุดจบสติกเกอร์จริง, ช่องไฟระหว่างมาร์ค {FIXED_QUANTITY_MARK_GAP_CM:.0f} cm"
                )

            if is_detail:
                st.number_input(f"เกณฑ์คิดตามหน้าเมื่อกว้างเกิน ({area_unit_short})", min_value=0.0, step=1.0, format="%.2f", key="face_charge_threshold", on_change=round_number_value, args=("face_charge_threshold",), help="ถ้ากว้างเกินค่านี้ ระบบจะแจ้งเตือนและคำนวณพื้นที่คิดตามหน้าพิมพ์")
                st.number_input("เกณฑ์พื้นที่ว่างเกิน (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.2f", key="waste_threshold_percent", on_change=round_number_value, args=("waste_threshold_percent",))
            else:
                st.caption(f"เกณฑ์คิดตามหน้า: >{st.session_state.face_charge_threshold:.2f} {area_unit_short} / พื้นที่ว่างเกิน {st.session_state.waste_threshold_percent:.2f}%")

            st.checkbox("ลองหมุนชิ้นงานอัตโนมัติ 90°", key="roll_auto_rotate", help="ระบบจะลองหมุนแต่ละชิ้นเพื่อให้ใช้มาร์ค 57 cm ได้คุ้มขึ้น", on_change=notify_auto_rotate_change)
            if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
                st.caption("รูปแบบจัดเรียงถูกล็อกเป็น: แบ่งเป็นมาร์คคู่ 57cm แล้วเรียง 2 คอลัมน์")
            else:
                st.radio(
                    "รูปแบบการจัดเรียง",
                    ROLL_LAYOUT_MODES,
                    key="roll_layout_mode",
                    help="เลือกโหมดเรียงตามงานจริง: ประหยัดพื้นที่ / ผลิตง่าย / ตามลำดับเดิม",
                    on_change=notify_roll_layout_mode_change,
                )

            if False:  # legacy target-area UI disabled
                st.number_input(
                    "พื้นที่ที่กำหนด (ตรม.)",
                    min_value=0.01,
                    step=0.01,
                    format="%.2f",
                    key="target_area_sqm",
                    on_change=round_number_value,
                    args=("target_area_sqm",),
                    help="เช่น 1.00 = ต้องการรู้ว่าภายในพื้นที่ 1 ตารางเมตร จะได้กี่ชิ้น โดยอิงจากขนาดและสัดส่วนต่อชุด/มาร์ค",
                )
                st.checkbox(
                    "บังคับเป็นมาร์คคู่ เช่น 2, 4, 6, 8...",
                    key="target_force_mark_pair",
                    help="เปิดไว้สำหรับงานผลิตที่ต้องจัดเป็นมาร์คคู่ขั้นต่ำ หากต้องการคำนวณจำนวนสูงสุดแบบ 1, 2, 3... ให้ปิดตัวเลือกนี้",
                )
                force_mark_pair = bool(st.session_state.get("target_force_mark_pair", DEFAULT_TARGET_FORCE_MARK_PAIR))
                mark_cols = st.columns(2)
                with mark_cols[0]:
                    st.number_input(
                        "จำนวนชุด/มาร์คขั้นต่ำ",
                        min_value=2 if force_mark_pair else 1,
                        step=2 if force_mark_pair else 1,
                        key="target_min_mark_count",
                        help="ระบบจะเริ่มคำนวณจากจำนวนชุด/มาร์คขั้นต่ำนี้",
                    )
                with mark_cols[1]:
                    st.number_input(
                        "เพิ่มทีละกี่ชุด/มาร์ค",
                        min_value=2 if force_mark_pair else 1,
                        step=2 if force_mark_pair else 1,
                        key="target_mark_step",
                        help="ถ้าบังคับมาร์คคู่ แนะนำ 2 เพื่อให้ผลลัพธ์เป็น 2, 4, 6, ...",
                    )
                st.caption("ในโหมดนี้ ช่องจำนวนของแต่ละ Size = จำนวนต่อ 1 ชุด/มาร์ค หรือสัดส่วนของ Size นั้น ไม่ใช่จำนวนรวม")

            st.checkbox(
                "ใช้ Preview แบบ Interactive",
                key="roll_use_plotly_preview",
                help="เปิด Plotly เพื่อซูม ลาก และ hover ดูรายละเอียดแต่ละชิ้น ถ้าเครื่องไม่มี Plotly ระบบจะกลับไปใช้ภาพนิ่งอัตโนมัติ",
                disabled=not PLOTLY_AVAILABLE,
            )
            if not PLOTLY_AVAILABLE:
                st.caption("ยังไม่พบ Plotly: ใช้ภาพนิ่ง Matplotlib แทนได้ตามเดิม")


    if not is_fixed_mark_calculation_mode():
        render_roll_preset_manager()

    if is_detail and not is_fixed_mark_calculation_mode():
        with st.expander("Margin งานม้วน / ระยะเสียหัวท้าย", expanded=True):
            area_unit_short = unit_label(st.session_state.get("area_unit", CM_UNIT))
            margin_cols = st.columns(2)
            with margin_cols[0]:
                st.number_input(f"ขอบซ้าย ({area_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="roll_margin_left", on_change=round_number_value, args=("roll_margin_left",))
                st.number_input(f"หัวม้วน ({area_unit_short})", min_value=0.0, step=0.5, format="%.2f", key="roll_head_margin", on_change=round_number_value, args=("roll_head_margin",))
            with margin_cols[1]:
                st.number_input(f"ขอบขวา ({area_unit_short})", min_value=0.0, step=0.1, format="%.2f", key="roll_margin_right", on_change=round_number_value, args=("roll_margin_right",))
                st.number_input(f"ท้ายม้วน ({area_unit_short})", min_value=0.0, step=0.5, format="%.2f", key="roll_tail_margin", on_change=round_number_value, args=("roll_tail_margin",))
    elif not is_fixed_mark_calculation_mode():
        # โหมดง่ายยังใช้ค่า margin เดิม หากเคยตั้งไว้ในโหมดละเอียด
        if any(st.session_state.get(key, 0.0) > 0 for key in ("roll_margin_left", "roll_margin_right", "roll_head_margin", "roll_tail_margin")):
            st.caption("มีค่า Margin เดิมอยู่ หากต้องการแก้ไขให้เปิดโหมดละเอียด")

    st.markdown("### รายการ Size")
    current_calc_mode = normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY))
    fixed_quantity_single_size = current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY
    if fixed_quantity_single_size:
        enforce_single_area_item_for_fixed_quantity()
        st.caption("โหมดคำนวณจากจำนวนที่กรอกใช้ Size เดียวเท่านั้น — ปุ่มเพิ่ม/คัดลอก/ลบถูกซ่อนเพื่อลดความสับสน")
        st.button("↺ ล้างค่า Size", on_click=request_reset_area_items, use_container_width=True, key="sidebar_reset_area_items")
    else:
        action_cols = st.columns(2)
        with action_cols[0]:
            st.button("➕ เพิ่ม", on_click=add_area_item, use_container_width=True, key="sidebar_add_area_item")
        with action_cols[1]:
            st.button("↺ ล้าง", on_click=request_reset_area_items, use_container_width=True, key="sidebar_reset_area_items")

    if st.session_state.get("confirm_reset_area_items"):
        st.warning("ยืนยันการล้างรายการ Size ทั้งหมด? ระบบจะลบทุก Size แล้วเริ่มใหม่เหลือ 1 รายการ")
        confirm_cols = st.columns(2)
        with confirm_cols[0]:
            st.button("⚠️ ยืนยันล้าง", on_click=confirm_reset_area_items, use_container_width=True, key="confirm_reset_area_items_button")
        with confirm_cols[1]:
            st.button("ยกเลิก", on_click=cancel_area_confirmation, use_container_width=True, key="cancel_reset_area_items_button")

    area_unit_short = unit_label(st.session_state.get("area_unit", CM_UNIT))
    for item_id in list(st.session_state.get("area_item_ids", [])):
        item_id = int(item_id)
        set_area_item_defaults(item_id)
        name_key, width_key, height_key, qty_key = area_item_keys(item_id)
        shape_key = area_shape_key(item_id)
        item_name = str(st.session_state.get(name_key, f"Size {item_id}")).strip() or f"Size {item_id}"
        st.session_state[name_key] = item_name

        with st.expander(f"Size #{item_id} — {item_name}", expanded=True):
            st.text_input("ชื่อ Size", key=name_key)
            selected_shape = st.selectbox(
                "รูปทรง",
                QUICK_SHAPES,
                key=shape_key,
                help="วงกลมใช้เส้นผ่านศูนย์กลางค่าเดียว / รูปทรงอื่นใช้กว้าง×ยาว",
            )
            selected_shape = normalize_sticker_shape(selected_shape)
            if selected_shape == QUICK_SHAPE_CIRCLE:
                st.number_input(
                    f"เส้นผ่านศูนย์กลาง ({area_unit_short})",
                    min_value=0.01,
                    step=0.1,
                    format="%.2f",
                    key=width_key,
                    on_change=round_number_value,
                    args=(width_key,),
                )
                st.session_state[height_key] = round2(st.session_state.get(width_key, 0.0))
                st.caption("วงกลมใช้ค่าเดียว: กว้าง = สูง")
            else:
                size_cols = st.columns(2)
                with size_cols[0]:
                    st.number_input(f"กว้าง ({area_unit_short})", min_value=0.01, step=0.1, format="%.2f", key=width_key, on_change=round_number_value, args=(width_key,))
                with size_cols[1]:
                    st.number_input(f"ยาว ({area_unit_short})", min_value=0.01, step=0.1, format="%.2f", key=height_key, on_change=round_number_value, args=(height_key,))
            current_calc_mode = normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode"))
            if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED:
                ratio_mode = normalize_mixed_ratio_mode(st.session_state.get("mixed_ratio_mode", MIXED_RATIO_MODE_EQUAL))
                if ratio_mode == MIXED_RATIO_MODE_CUSTOM:
                    weight_key = f"mixed_ratio_weight_{item_id}"
                    st.number_input(
                        "น้ำหนัก/สัดส่วนของ Size นี้",
                        min_value=1,
                        step=1,
                        key=weight_key,
                        help="ตัวเลขยิ่งมาก Size นี้ยิ่งถูกจัดให้ได้จำนวนตั้งต้นมากขึ้น เช่น 3 เทียบกับ 1",
                    )
                else:
                    st.caption(f"อัตราส่วนของ Size นี้จะคำนวณจากตัวเลือกกลาง: {ratio_mode}")
            else:
                st.number_input("จำนวน", min_value=1, step=1, key=qty_key)
            if fixed_quantity_single_size:
                st.button("↔ สลับกว้าง/ยาว", key=f"sidebar_swap_area_{item_id}", on_click=swap_area_item_dimensions, args=(item_id,), use_container_width=True, help="สลับค่ากว้าง/ยาวของ Size นี้")
            else:
                item_action_cols = st.columns(3)
                with item_action_cols[0]:
                    st.button("↔ สลับ", key=f"sidebar_swap_area_{item_id}", on_click=swap_area_item_dimensions, args=(item_id,), use_container_width=True, help="สลับค่ากว้าง/ยาวของ Size นี้")
                with item_action_cols[1]:
                    st.button("⧉ คัดลอก", key=f"sidebar_duplicate_area_{item_id}", on_click=duplicate_area_item, args=(item_id,), use_container_width=True, help="คัดลอก Size นี้ไปเป็นรายการใหม่")
                with item_action_cols[2]:
                    st.button("🗑️ ลบ", key=f"sidebar_remove_area_{item_id}", on_click=request_remove_area_item, args=(item_id,), disabled=len(st.session_state.get("area_item_ids", [])) <= 1, use_container_width=True)

            if (not fixed_quantity_single_size) and st.session_state.get("confirm_remove_area_item_id") == item_id:
                st.warning(f"ยืนยันการลบ Size #{item_id} — {item_name}? ข้อมูลขนาดและจำนวนของรายการนี้จะถูกลบ")
                confirm_item_cols = st.columns(2)
                with confirm_item_cols[0]:
                    st.button("⚠️ ยืนยันลบ", key=f"confirm_remove_area_{item_id}", on_click=confirm_remove_area_item, args=(item_id,), use_container_width=True)
                with confirm_item_cols[1]:
                    st.button("ยกเลิก", key=f"cancel_remove_area_{item_id}", on_click=cancel_area_confirmation, use_container_width=True)

    st.info("Preset จะบันทึกทั้งค่าหน้ากว้าง ช่องไฟ Margin โหมดจัดเรียง และรายการ Size ทั้งหมด")


# =========================================================
# Pages
# =========================================================
def render_quantity_calculator_page() -> None:
    render_action_feedback()
    st.markdown('<div class="page-motion-anchor"></div>', unsafe_allow_html=True)
    sticker_unit = st.session_state.sticker_unit
    sheet_unit = st.session_state.sheet_unit
    option_unit = st.session_state.option_unit
    sticker_unit_short = unit_label(sticker_unit)
    sheet_unit_short = unit_label(sheet_unit)
    option_unit_short = unit_label(option_unit)
    sticker_shape = normalize_sticker_shape(st.session_state.get("sticker_shape", QUICK_SHAPE_RECTANGLE))

    sticker_width = round2(st.session_state.sticker_width)
    sticker_height = round2(st.session_state.sticker_height)
    if sticker_shape == QUICK_SHAPE_CIRCLE:
        sticker_height = sticker_width
        st.session_state["sticker_height"] = sticker_width
    sheet_width = round2(st.session_state.sheet_width)
    sheet_height = round2(st.session_state.sheet_height)
    gap = round2(st.session_state.gap)
    tolerance = round2(st.session_state.tolerance)
    marks_count = int(st.session_state.marks_count)

    st.markdown(
        """
        <div class="hero hero-quantity">
            <div class="hero-content">
                <div class="hero-eyebrow">📐 Sticker Layout Pro</div>
                <h1>คำนวณจำนวนสติกเกอร์ต่อวัสดุพิมพ์</h1>
                <p>ระบบเลือกทิศทางที่วางได้มากที่สุด พร้อมลองวางแบบผสมแนวนอน/แนวตั้ง มีประวัติ 5 ครั้งล่าสุด และส่งออก Preview สำหรับส่งต่องานผลิต</p>
                <div class="hero-meta">
                    <span class="hero-chip good">✓ Best Fit Layout</span>
                    <span class="hero-chip info">↔ Normal / Rotate / Mixed</span>
                    <span class="hero-chip warn">↺ History 5 ล่าสุด</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sticker_width_cm = to_cm(sticker_width, sticker_unit)
    sticker_height_cm = to_cm(sticker_height, sticker_unit)
    sheet_width_cm = to_cm(sheet_width, sheet_unit)
    sheet_height_cm = to_cm(sheet_height, sheet_unit)
    gap_cm = to_cm(gap, option_unit)
    tolerance_cm = to_cm(tolerance, option_unit)

    errors = validate_inputs(sticker_width, sticker_height, sheet_width, sheet_height, gap, tolerance)
    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    layout = best_layout(sheet_width_cm, sheet_height_cm, sticker_width_cm, sticker_height_cm, gap_cm, tolerance_cm)
    total_all_marks = layout.total_per_mark * marks_count
    quantity_material_area_sqm = round2(sheet_width_cm * sheet_height_cm * marks_count / 10000)
    quantity_piece_area_sqcm = quick_piece_area_sqcm(sticker_shape, sticker_width_cm, sticker_height_cm)
    quantity_material_usage_percent = round2((quantity_piece_area_sqcm * layout.total_per_mark / (sheet_width_cm * sheet_height_cm) * 100) if sheet_width_cm * sheet_height_cm else 0.0)

    status_is_clean = layout.overflow_width_cm == 0 and layout.overflow_height_cm == 0
    status_badge("อยู่ในขอบวัสดุทั้งหมด" if status_is_clean else "มีบางชิ้นอยู่ในระยะอนุโลม", "good" if status_is_clean else "warn")
    if layout.layout_mode == "mixed":
        status_badge("ระบบเลือกวางแบบผสมเพื่อเพิ่มจำนวนชิ้น", "info")

    summary_cols = st.columns(4)
    with summary_cols[0]:
        metric_card("จำนวนรวมทั้งหมด", f"{total_all_marks:,} ชิ้น", f"{marks_count:,} มาร์ค", accent=True)
    with summary_cols[1]:
        metric_card("จำนวนต่อชุด/มาร์ค", f"{layout.total_per_mark:,} ชิ้น", layout.grid_summary)
    with summary_cols[2]:
        metric_card("ทิศทางที่เหมาะสุด", layout.orientation, "ระบบเทียบแบบปกติ/หมุน/ผสม")
    with summary_cols[3]:
        metric_card("การใช้พื้นที่", f"{quantity_material_usage_percent:.2f}%", f"รูปทรง: {sticker_shape}")

    st.markdown('<div class="section-title">ภาพจำลองการจัดวาง</div>', unsafe_allow_html=True)
    main_left, main_right = st.columns([2.15, 1])
    with main_left:
        fig = build_layout_figure(sheet_width_cm, sheet_height_cm, layout, gap_cm, tolerance_cm, sticker_shape=sticker_shape)
        preview_png = fig_to_png_bytes(fig)
        st.pyplot(fig, use_container_width=True)
        st.download_button(
            "ดาวน์โหลด Preview PNG",
            data=preview_png,
            file_name="quantity_layout_preview.png",
            mime="image/png",
            key="download_quantity_preview_png",
            use_container_width=True,
        )
        plt.close(fig)

    with main_right:
        display_sticker_w = from_cm(layout.sticker_width_cm, sticker_unit)
        display_sticker_h = from_cm(layout.sticker_height_cm, sticker_unit)
        display_used_w = from_cm(layout.used_width_cm, sheet_unit)
        display_used_h = from_cm(layout.used_height_cm, sheet_unit)
        display_overflow_w = from_cm(layout.overflow_width_cm, sheet_unit)
        display_overflow_h = from_cm(layout.overflow_height_cm, sheet_unit)
        st.markdown(
            f"""
            <div class="detail-card">
                <div class="detail-row"><div class="detail-label">รูปทรง</div><div class="detail-value">{sticker_shape}</div></div>
                <div class="detail-row"><div class="detail-label">ขนาดสติกเกอร์ชุดหลัก</div><div class="detail-value">{sticker_shape_dimension_text(sticker_shape, layout.sticker_width_cm, layout.sticker_height_cm, sticker_unit)}</div></div>
                <div class="detail-row"><div class="detail-label">วางแบบปกติ</div><div class="detail-value">{layout.normal_count:,} ชิ้น</div></div>
                <div class="detail-row"><div class="detail-label">วางแบบหมุน 90°</div><div class="detail-value">{layout.rotated_count:,} ชิ้น</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่ที่ใช้จริง</div><div class="detail-value">{display_used_w:.2f} x {display_used_h:.2f} {sheet_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">ระยะห่างช่องไฟ</div><div class="detail-value">{gap:.2f} {option_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">ระยะอนุโลม</div><div class="detail-value">{tolerance:.2f} {option_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">ล้นแนวกว้าง</div><div class="detail-value">{display_overflow_w:.2f} {sheet_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">ล้นแนวยาว</div><div class="detail-value">{display_overflow_h:.2f} {sheet_unit_short}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if layout.total_per_mark == 0:
            st.warning("ขนาดสติกเกอร์ใหญ่กว่าวัสดุพิมพ์และระยะอนุโลมที่ตั้งไว้")
        elif not status_is_clean:
            st.info("พื้นที่สีน้ำตาลเส้นประคือระยะอนุโลม ส่วนชิ้นสีส้มเข้มคือชิ้นที่เกินขอบวัสดุจริง")
        else:
            st.success("รูปแบบนี้ไม่เกินขอบวัสดุพิมพ์")

    add_quantity_history_entry(
        layout=layout,
        sticker_width_cm=sticker_width_cm,
        sticker_height_cm=sticker_height_cm,
        sheet_width_cm=sheet_width_cm,
        sheet_height_cm=sheet_height_cm,
        gap_cm=gap_cm,
        tolerance_cm=tolerance_cm,
        marks_count=marks_count,
        status_is_clean=status_is_clean,
    )

    quantity_summary_rows = [
        {"รายการ": "จำนวนรวมทั้งหมด", "ค่า": f"{total_all_marks:,} ชิ้น"},
        {"รายการ": "จำนวนต่อมาร์ค", "ค่า": f"{layout.total_per_mark:,} ชิ้น"},
        {"รายการ": "จำนวนมาร์ค", "ค่า": f"{marks_count:,} มาร์ค"},
        {"รายการ": "ทิศทางที่เหมาะสุด", "ค่า": layout.orientation},
        {"รายการ": "รูปแบบการวาง", "ค่า": layout.grid_summary.replace('<br>', ' / ').replace("<span style='font-size:0.78rem;font-weight:600;color:#aeb5c1'>", '').replace('</span>', '')},
        {"รายการ": "รูปทรง", "ค่า": sticker_shape},
        {"รายการ": "การใช้พื้นที่", "ค่า": f"{quantity_material_usage_percent:.2f}%"},
        {"รายการ": "พื้นที่วัสดุรวม", "ค่า": f"{quantity_material_area_sqm:.2f} ตรม."},
        {"รายการ": "ขนาดสติกเกอร์ชุดหลัก", "ค่า": sticker_shape_dimension_text(sticker_shape, layout.sticker_width_cm, layout.sticker_height_cm, sticker_unit)},
        {"รายการ": "พื้นที่ที่ใช้จริง", "ค่า": f"{display_used_w:.2f} x {display_used_h:.2f} {sheet_unit_short}"},
        {"รายการ": "ระยะห่างช่องไฟ", "ค่า": f"{gap:.2f} {option_unit_short}"},
        {"รายการ": "ระยะอนุโลม", "ค่า": f"{tolerance:.2f} {option_unit_short}"},
        {"รายการ": "สถานะ", "ค่า": "อยู่ในขอบวัสดุทั้งหมด" if status_is_clean else "มีบางชิ้นอยู่ในระยะอนุโลม"},
    ]

    st.markdown('<div class="section-title">สรุปสำหรับส่งต่องาน</div>', unsafe_allow_html=True)
    st.dataframe(quantity_summary_rows, use_container_width=True, hide_index=True)
    render_compact_export_bar(
        title="สรุปคำนวณจำนวนสติกเกอร์ต่อวัสดุพิมพ์",
        rows=quantity_summary_rows,
        file_prefix="sticker_quantity_summary",
    )

    render_quantity_history()


def render_area_calculator_page() -> None:
    render_action_feedback()
    st.markdown('<div class="page-motion-anchor"></div>', unsafe_allow_html=True)
    area_unit = st.session_state.get("area_unit", CM_UNIT)
    area_unit_short = unit_label(area_unit)

    print_width_cm = to_cm(st.session_state.get("roll_print_width", 120.0), area_unit)
    margin_left_cm = to_cm(st.session_state.get("roll_margin_left", 0.0), area_unit)
    margin_right_cm = to_cm(st.session_state.get("roll_margin_right", 0.0), area_unit)
    head_margin_cm = to_cm(st.session_state.get("roll_head_margin", 0.0), area_unit)
    tail_margin_cm = to_cm(st.session_state.get("roll_tail_margin", 0.0), area_unit)
    usable_width_cm = round2(max(0.0, print_width_cm - margin_left_cm - margin_right_cm))
    roll_gap_cm = to_cm(st.session_state.get("roll_gap", DEFAULT_STICKER_GAP_CM), area_unit)
    # ค่าอนุโลมมาร์ค 57cm เก็บเป็น cm ตลอด ไม่แปลงตาม area_unit
    fixed_quantity_mark_tolerance_cm = round2(
        st.session_state.get("fixed_quantity_mark_tolerance", DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM)
    )
    face_charge_threshold_cm = to_cm(st.session_state.get("face_charge_threshold", 60.0), area_unit)
    waste_threshold_percent = round2(st.session_state.get("waste_threshold_percent", 40.0))
    auto_rotate_enabled = bool(st.session_state.get("roll_auto_rotate", True))
    roll_layout_mode = st.session_state.get("roll_layout_mode", ROLL_LAYOUT_MODE_SMART)

    sync_area_calc_mode_from_main_page()
    current_calc_mode = normalize_roll_area_calculation_mode(st.session_state.get("roll_area_calculation_mode"))
    if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED:
        hero_title = ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED
        hero_desc = "คำนวณหลาย Size ในมาร์ค 57×41 เลือกครึ่ง ตรม./1 ตรม. ตั้งอัตราส่วน และเติมพื้นที่เหลืออัตโนมัติ"
    elif current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY:
        hero_title = ROLL_AREA_CALC_MODE_FIXED_QUANTITY
        hero_desc = "กรอกขนาดและจำนวนจริง ระบบจัดเข้ามาร์คคู่ 57cm คำนวณความยาวเข้าม้วน พื้นที่จริง และพื้นที่คิดเงิน"
    else:
        hero_title = "คำนวณพื้นที่ตามหน้ากว้างม้วน และแสดงตัวอย่างชิ้นงาน"
        hero_desc = "เพิ่ม Preset หน้ากว้าง, โหมดง่าย/ละเอียด, Margin งานม้วน, Auto Rotate, Smart Optimizer, เปอร์เซ็นต์ประหยัด และประวัติ 5 ครั้งล่าสุด"

    st.markdown(
        f"""
        <div class="hero">
            <div class="kicker">เครื่องคำนวณพื้นที่งานพิมพ์สติกเกอร์</div>
            <h1>{hero_title}</h1>
            <p>{hero_desc}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    fixed_quantity_mark_mode = current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_QUANTITY
    if fixed_quantity_mark_mode:
        roll_layout_mode = "แบ่งเป็นมาร์คคู่ 57cm"
    if current_calc_mode == ROLL_AREA_CALC_MODE_FIXED_MARK_MIXED:
        render_fixed_mark_mixed_calculator_content(area_unit)
        return

    if usable_width_cm <= 0:
        st.error("Margin ซ้าย+ขวา มากกว่าหรือเท่ากับหน้ากว้างพิมพ์ ทำให้ไม่มีพื้นที่วางชิ้นงาน")
        st.stop()

    base_area_items = collect_area_items(
        area_unit=area_unit,
        usable_print_width_cm=usable_width_cm,
        face_charge_threshold_cm=face_charge_threshold_cm,
        auto_rotate_enabled=auto_rotate_enabled,
    )

    roll_layout_kwargs = {
        "print_width_cm": print_width_cm,
        "gap_cm": roll_gap_cm,
        "margin_left_cm": margin_left_cm,
        "margin_right_cm": margin_right_cm,
        "head_margin_cm": head_margin_cm,
        "tail_margin_cm": tail_margin_cm,
        "waste_threshold_percent": waste_threshold_percent,
        "auto_rotate_enabled": auto_rotate_enabled,
        "layout_mode": roll_layout_mode,
    }

    # โหมดพื้นที่เป้าหมายถูกปิดออกจาก UI แล้ว จึงไม่ให้ logic เก่าหลุดเข้าการคำนวณหลัก
    target_mode_enabled = False
    target_result = None
    target_mark_count = None
    target_preview_mark_count = None
    target_result_is_valid = True
    area_items = base_area_items

    total_area_quantity = sum(item.quantity for item in area_items)
    if total_area_quantity > MAX_TOTAL_QUANTITY:
        st.error(f"จำนวนชิ้นรวม {total_area_quantity:,} ชิ้น เกินขีดจำกัด {MAX_TOTAL_QUANTITY:,} ชิ้นต่อครั้ง เพื่อป้องกันแอปค้าง กรุณาแบ่งงานออกเป็นหลายรอบ")
        st.stop()

    with st.spinner("กำลังคำนวณและจัดวางชิ้นงาน…"):
        if fixed_quantity_mark_mode:
            roll_layout = build_fixed_quantity_mark_pair_layout(
                area_items=area_items,
                print_width_cm=print_width_cm,
                gap_cm=roll_gap_cm,
                margin_left_cm=margin_left_cm,
                margin_right_cm=margin_right_cm,
                head_margin_cm=head_margin_cm,
                tail_margin_cm=tail_margin_cm,
                auto_rotate_enabled=auto_rotate_enabled,
                mark_tolerance_cm=fixed_quantity_mark_tolerance_cm,
            )
        else:
            roll_layout = build_roll_layout(
                area_items=area_items,
                **roll_layout_kwargs,
            )

    # โหมดมาร์คคู่ 57cm เป็นคนละหลักคิดกับ Roll Layout ปกติ
    # จึงไม่เทียบ "ประหยัดจากเรียงเดิม" เพื่อกันตัวเลขหลอกตา
    if fixed_quantity_mark_mode:
        baseline_layout = roll_layout
        savings_percent = 0.0
        savings_area_sqm = 0.0
    else:
        baseline_layout = build_roll_layout(
            area_items=area_items,
            print_width_cm=print_width_cm,
            gap_cm=roll_gap_cm,
            margin_left_cm=margin_left_cm,
            margin_right_cm=margin_right_cm,
            head_margin_cm=head_margin_cm,
            tail_margin_cm=tail_margin_cm,
            waste_threshold_percent=waste_threshold_percent,
            auto_rotate_enabled=auto_rotate_enabled,
            preview_limit=0,
            layout_mode=ROLL_LAYOUT_MODE_ORIGINAL,
        )
        savings_percent = 0.0
        savings_area_sqm = 0.0
        if baseline_layout.roll_face_area_sqm > 0:
            savings_area_sqm = round2(max(0.0, baseline_layout.roll_face_area_sqm - roll_layout.roll_face_area_sqm))
            savings_percent = round2(savings_area_sqm / baseline_layout.roll_face_area_sqm * 100)

    if not target_mode_enabled or target_result_is_valid:
        add_roll_history_entry(
            area_items=area_items,
            layout=roll_layout,
            baseline_layout=baseline_layout,
            savings_percent=savings_percent,
            layout_mode=roll_layout_mode,
            print_width_cm=print_width_cm,
            gap_cm=roll_gap_cm,
            margin_left_cm=margin_left_cm,
            margin_right_cm=margin_right_cm,
            head_margin_cm=head_margin_cm,
            tail_margin_cm=tail_margin_cm,
            auto_rotate_enabled=auto_rotate_enabled,
        )

    if roll_layout.face_charge_names:
        st.warning("มี Size ที่กว้างเกิน " f"{st.session_state.face_charge_threshold:.2f} {area_unit_short}: " f"{', '.join(roll_layout.face_charge_names)} — พื้นที่รายการนี้คิดตามหน้าพิมพ์")
    if roll_layout.charge_by_page_due_to_waste:
        st.warning(f"พื้นที่ว่างบนหน้าพิมพ์ {roll_layout.empty_area_percent:.2f}% มากกว่า {roll_layout.waste_threshold_percent:.2f}% — งานนี้คิดพื้นที่ตามหน้า")
    if roll_layout.overflow_count > 0:
        st.error(f"มี {roll_layout.overflow_count:,} ชิ้นที่กว้างเกินพื้นที่พิมพ์ที่ใช้ได้จริง {roll_layout.usable_width_cm:.2f} cm ควรแบ่งชิ้น ลด Margin หรือเพิ่มหน้ากว้างพิมพ์")
    if roll_layout.auto_rotate_enabled and roll_layout.rotated_count > 0:
        status_badge(f"Auto Rotate ทำงาน: หมุน {roll_layout.rotated_count:,} ชิ้น เพื่อประหยัดพื้นที่", "info")
    elif roll_layout.auto_rotate_enabled:
        status_badge("Auto Rotate เปิดอยู่ แต่ยังไม่จำเป็นต้องหมุนชิ้นงาน", "good")
    status_badge(f"โหมดจัดเรียง: {roll_layout_mode} / กลยุทธ์ที่เลือก: {roll_strategy_display_name(roll_layout.strategy_name)}", "info")
    fixed_mark_summary = getattr(roll_layout, "mark_summary", None) or {}
    if roll_layout.strategy_name == FIXED_QUANTITY_STRATEGY and fixed_mark_summary:
        status_badge(
            f"มาร์คคู่: {fixed_mark_summary.get('mark_count', 0):,} มาร์ค / {fixed_mark_summary.get('pair_count', 0):,} คู่ · ช่องไฟมาร์ค {fixed_mark_summary.get('mark_gap_cm', FIXED_QUANTITY_MARK_GAP_CM):.2f} cm · กว้างมาร์ค {fixed_mark_summary.get('mark_width_cm', FIXED_MARK_WIDTH_CM):.0f} cm + อนุโลม {fixed_mark_summary.get('mark_tolerance_cm', DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM):.2f} cm",
            "info",
        )
        st.caption("มาร์คทั้งหมดถูกปัดเป็นเลขคู่; 41 cm ใช้เป็นฐานนับจำนวนต่อมาร์ค แต่พื้นที่หน้าม้วน/ความยาวเข้าม้วนจะคิดถึงจุดสิ้นสุดของสติกเกอร์จริง")
    if target_mode_enabled and target_result:
        target_area_sqm = float(target_result.get("target_area_sqm", 0.0))
        if target_result_is_valid:
            status_badge(
                f"พื้นที่ที่กำหนด {target_area_sqm:.2f} ตรม. → ได้ {target_mark_count:,} ชุด/มาร์ค / จำนวนรวม {roll_layout.total_quantity:,} ชิ้น",
                "good",
            )
            remaining_area_sqm = float(target_result.get("remaining_area_sqm", 0.0))
            target_usage_percent = float(target_result.get("target_usage_percent", 0.0))
            st.caption(f"ใช้พื้นที่เป้าหมาย {target_usage_percent:.2f}% / เหลือพื้นที่ประมาณ {remaining_area_sqm:.2f} ตรม.")
        else:
            status_badge(
                f"พื้นที่ที่กำหนด {target_area_sqm:.2f} ตรม. → ยังใส่ขั้นต่ำ {target_preview_mark_count:,} ชุด/มาร์คไม่ได้",
                "danger",
            )
        failed_layout = target_result.get("failed_layout")
        failed_mark_count = target_result.get("failed_mark_count")
        if target_result_is_valid and failed_layout and failed_mark_count:
            st.caption(
                f"ชุด/มาร์คถัดไป {failed_mark_count:,} จะใช้พื้นที่ประมาณ {failed_layout.roll_face_area_sqm:.2f} ตรม. จึงเกินพื้นที่ที่กำหนด"
            )
    if savings_percent > 0:
        status_badge(f"ประหยัดกว่าการเรียงตามลำดับเดิม {savings_percent:.2f}%", "good")

    if roll_layout.total_quantity > roll_layout.preview_limit:
        st.info(
            f"จำนวนชิ้นรวม {roll_layout.total_quantity:,} ชิ้น — ระบบคำนวณครบทั้งหมด "
            f"แต่แสดง preview เฉพาะ {roll_layout.preview_limit:,} ชิ้นแรก เพื่อให้หน้า Preview ไม่หนักเกินไป"
        )

    cut_section_count, cut_last_length_cm = roll_cut_section_summary(roll_layout)
    if roll_layout.required_length_cm > ROLL_CUT_SECTION_LENGTH_CM:
        st.info(
            f"ความยาวรวม {roll_layout.required_length_cm:.2f} cm เกิน {ROLL_CUT_SECTION_LENGTH_CM:.0f} cm — "
            f"แนะนำแบ่งตัดเป็น {cut_section_count:,} ช่วง / ช่วงสุดท้ายประมาณ {cut_last_length_cm:.2f} cm"
        )

    area_summary_cols = st.columns([1, 1, 1, 1, 1, 1], gap="medium")
    with area_summary_cols[0]:
        metric_card("พื้นที่หน้าม้วนที่ต้องใช้", f"{roll_layout.roll_face_area_sqm:.2f} ตรม.", f"หน้ากว้าง {st.session_state.roll_print_width:.2f} {area_unit_short}", accent=True)
    with area_summary_cols[1]:
        metric_card("ความยาวเข้าม้วน", f"{roll_layout.required_length_cm / 100:.2f} ม.", f"{roll_layout.rows_count:,} ระดับวาง / ช่องไฟ {st.session_state.roll_gap:.2f} {area_unit_short}")
    with area_summary_cols[2]:
        if target_mode_enabled and target_result_is_valid:
            metric_card("จำนวนชุด/มาร์คที่ทำได้", f"{target_mark_count:,} ชุด", f"พื้นที่ {target_result['target_area_sqm']:.2f} ตรม.")
        elif target_mode_enabled:
            metric_card("จำนวนชุด/มาร์คที่ทำได้", "0 ชุด", f"ขั้นต่ำ {target_preview_mark_count:,} ชุดยังเกินพื้นที่")
        elif fixed_quantity_mark_mode:
            metric_card("เทียบเรียงเดิม", "ไม่ใช้", "โหมดมาร์คคู่ใช้ฐานคำนวณเฉพาะ")
        else:
            metric_card("ประหยัดจากเรียงเดิม", f"{savings_percent:.2f}%", f"ลดพื้นที่หน้าม้วน {savings_area_sqm:.2f} ตรม.")
    with area_summary_cols[3]:
        if target_mode_enabled and target_result_is_valid:
            metric_card("จำนวนรวม", f"{roll_layout.total_quantity:,} ชิ้น", "จำนวนต่อชุด/มาร์ค × จำนวนชุด/มาร์ค")
        elif target_mode_enabled:
            metric_card("จำนวนขั้นต่ำที่ลองวาง", f"{roll_layout.total_quantity:,} ชิ้น", "Preview ของขั้นต่ำที่เกินพื้นที่")
        else:
            metric_card("จำนวนรวม", f"{roll_layout.total_quantity:,} ชิ้น", f"{len(area_items):,} Size")
    with area_summary_cols[4]:
        metric_card("พื้นที่จริงของชิ้นงาน", f"{roll_layout.actual_area_sqm:.2f} ตรม.", "ไม่รวมพื้นที่ว่างบนหน้าม้วน")
    with area_summary_cols[5]:
        metric_card("พื้นที่คิดเงินสุดท้าย", f"{roll_layout.final_charge_area_sqm:.2f} ตรม.", "คิดตามหน้า" if roll_layout.charge_by_page_due_to_waste else "คิดตามกฎความกว้าง")

    rows = area_table_rows(
        area_items,
        base_items=base_area_items if target_mode_enabled else None,
        mark_count=target_preview_mark_count if target_mode_enabled else None,
    )

    target_preview_area_sqm = float(target_result.get("target_area_sqm")) if target_mode_enabled and target_result else None

    preview_left, preview_right = st.columns([2.1, 1])
    with preview_left:
        st.markdown('<div class="section-title">รูปตัวอย่างบนหน้าสติกเกอร์</div>', unsafe_allow_html=True)
        if area_items and roll_layout.required_length_cm > 0:
            render_premium_roll_preview_kpis(roll_layout)
            use_plotly_preview = bool(st.session_state.get("roll_use_plotly_preview", True)) and PLOTLY_AVAILABLE
            if use_plotly_preview:
                plotly_fig = build_roll_preview_plotly(roll_layout, area_items, area_unit, target_area_sqm=target_preview_area_sqm)
                if plotly_fig is not None:
                    st.plotly_chart(
                        plotly_fig,
                        use_container_width=True,
                        config={
                            "displaylogo": False,
                            "scrollZoom": True,
                            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                        },
                    )
                    st.caption("Interactive preview: ลากเพื่อเลื่อน, scroll เพื่อซูม, hover ที่ชิ้นงานเพื่อดูชื่อ ขนาด พื้นที่ และสถานะ")
                else:
                    st.warning("Plotly ไม่พร้อมใช้งาน ระบบเปลี่ยนเป็นภาพนิ่งให้อัตโนมัติ")
                    fig = build_roll_preview_figure(roll_layout, area_items, area_unit, target_area_sqm=target_preview_area_sqm)
                    st.pyplot(fig, use_container_width=True)
                    plt.close(fig)
            else:
                fig = build_roll_preview_figure(roll_layout, area_items, area_unit, target_area_sqm=target_preview_area_sqm)
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)

            export_fig = build_roll_preview_figure(roll_layout, area_items, area_unit, target_area_sqm=target_preview_area_sqm)
            export_png = fig_to_png_bytes(export_fig)
            st.download_button(
                "ดาวน์โหลด Preview PNG พร้อมสรุปสี",
                data=export_png,
                file_name="roll_layout_preview.png",
                mime="image/png",
                key="download_roll_preview_png",
                use_container_width=True,
            )
            st.caption(f"ไฟล์ PNG มีสรุปสี/ชื่อ Size ด้านขวา และมีเส้นไกด์ทุก {ROLL_CUT_SECTION_LENGTH_CM:.0f} cm; ถ้าม้วนยาวเกิน {ROLL_PREVIEW_MAX_LENGTH_CM:.0f} cm จะแสดงเฉพาะช่วง Preview ตามที่แจ้งไว้")
            plt.close(export_fig)
        else:
            st.warning("ยังไม่มีรายการที่คำนวณได้ กรุณาใส่กว้าง ยาว และจำนวนให้มากกว่า 0 ใน Sidebar")

    with preview_right:
        # ดัน detail card ลงมาให้อยู่ระนาบเดียวกับส่วน preview chart
        # (ชดเชย section-title ~2rem + KPI grid ~6rem + gap ~0.5rem)
        st.markdown('<div style="height: 9.5rem;"></div>', unsafe_allow_html=True)
        compare_original_detail_html = (
            '<div class="detail-row"><div class="detail-label">เทียบเรียงเดิม</div><div class="detail-value">ไม่ใช้ในโหมดมาร์คคู่ 57cm</div></div>'
            if fixed_quantity_mark_mode
            else f'<div class="detail-row"><div class="detail-label">เทียบเรียงเดิม</div><div class="detail-value">{savings_percent:.2f}% / {savings_area_sqm:.2f} ตรม.</div></div>'
        )
        st.markdown(
            f"""
            <div class="detail-card">
                <div class="detail-row"><div class="detail-label">หน้ากว้างพิมพ์</div><div class="detail-value">{st.session_state.roll_print_width:.2f} {area_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่ใช้ได้จริง</div><div class="detail-value">{roll_layout.usable_width_cm:.2f} cm</div></div>
                <div class="detail-row"><div class="detail-label">Margin ซ้าย/ขวา</div><div class="detail-value">{st.session_state.roll_margin_left:.2f} / {st.session_state.roll_margin_right:.2f} {area_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">หัว/ท้ายม้วน</div><div class="detail-value">{st.session_state.roll_head_margin:.2f} / {st.session_state.roll_tail_margin:.2f} {area_unit_short}</div></div>
                <div class="detail-row"><div class="detail-label">ความยาวเข้าม้วน</div><div class="detail-value">{roll_layout.required_length_cm:.2f} cm</div></div>
                <div class="detail-row"><div class="detail-label">แบ่งตัดไม่เกิน 260 cm</div><div class="detail-value">{cut_section_count:,} ช่วง / ท้าย {cut_last_length_cm:.2f} cm</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่หน้าม้วน</div><div class="detail-value">{roll_layout.roll_face_area_sqm:.2f} ตรม.</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่จริง</div><div class="detail-value">{roll_layout.actual_area_sqm:.2f} ตรม.</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่ว่าง</div><div class="detail-value">{roll_layout.empty_area_sqm:.2f} ตรม. ({roll_layout.empty_area_percent:.2f}%)</div></div>
                <div class="detail-row"><div class="detail-label">การใช้พื้นที่</div><div class="detail-value">{roll_layout.material_usage_percent:.2f}%</div></div>
                <div class="detail-row"><div class="detail-label">วิธีคำนวณ</div><div class="detail-value">{st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)}</div></div>
                {f'<div class="detail-row"><div class="detail-label">ฐานคำนวณความยาว</div><div class="detail-value">จุดสิ้นสุดของสติกเกอร์จริง ไม่ล็อกขั้นต่ำ 41 cm</div></div>' if fixed_mark_summary and fixed_mark_summary.get("calculation_height_mode") == "actual_sticker_end" else ''}
                {f'<div class="detail-row"><div class="detail-label">จำนวนมาร์ค/คู่</div><div class="detail-value">{fixed_mark_summary.get("mark_count", 0):,} มาร์ค / {fixed_mark_summary.get("pair_count", 0):,} คู่ · ช่องไฟมาร์ค {fixed_mark_summary.get("mark_gap_cm", FIXED_QUANTITY_MARK_GAP_CM):.2f} cm · อนุโลม {fixed_mark_summary.get("mark_tolerance_cm", DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM):.2f} cm</div></div>' if fixed_mark_summary else ''}
                {f'<div class="detail-row"><div class="detail-label">พื้นที่ที่กำหนด/ผลลัพธ์</div><div class="detail-value">{target_result["target_area_sqm"]:.2f} ตรม. / {"ผ่าน " + format(target_mark_count, ",") + " ชุด" if target_result_is_valid else "ไม่พอขั้นต่ำ " + format(target_preview_mark_count, ",") + " ชุด"}</div></div>' if target_mode_enabled and target_result else ''}
                <div class="detail-row"><div class="detail-label">โหมดจัดเรียง</div><div class="detail-value">{roll_layout_mode}</div></div>
                <div class="detail-row"><div class="detail-label">กลยุทธ์ที่เลือก</div><div class="detail-value">{roll_strategy_display_name(roll_layout.strategy_name)}</div></div>
                {compare_original_detail_html}
                <div class="detail-row"><div class="detail-label">Auto Rotate</div><div class="detail-value">{'เปิด' if roll_layout.auto_rotate_enabled else 'ปิด'} / {roll_layout.rotated_count:,} ชิ้น</div></div>
                <div class="detail-row"><div class="detail-label">พื้นที่คิดเงิน</div><div class="detail-value">{roll_layout.final_charge_area_sqm:.2f} ตรม.</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_roll_preview_legend(area_items, area_unit)
        st.info("สูตรหน้าม้วน: พื้นที่หน้าม้วน = หน้ากว้างพิมพ์ × ความยาวเข้าม้วน / 10,000")

    render_roll_history()

    if rows:
        st.markdown('<div class="section-title">สรุปรายการ Size</div>', unsafe_allow_html=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)

        area_summary_export_rows = [
            {"รายการ": "หน้ากว้างพิมพ์", "ค่า": f"{st.session_state.roll_print_width:.2f} {area_unit_short}"},
            {"รายการ": "พื้นที่ใช้ได้จริง", "ค่า": f"{roll_layout.usable_width_cm:.2f} cm"},
            {"รายการ": "จำนวน Size", "ค่า": f"{len(area_items):,} Size"},
            {"รายการ": "จำนวนชิ้นรวม", "ค่า": f"{roll_layout.total_quantity:,} ชิ้น"},
            {"รายการ": "วิธีคำนวณ", "ค่า": st.session_state.get("roll_area_calculation_mode", ROLL_AREA_CALC_MODE_FIXED_QUANTITY)},
            {"รายการ": "พื้นที่ที่กำหนด", "ค่า": f"{target_result['target_area_sqm']:.2f} ตรม." if target_mode_enabled and target_result else "-"},
            {"รายการ": "จำนวนชุด/มาร์คที่ทำได้", "ค่า": f"{target_mark_count:,} ชุด" if target_mode_enabled and target_result_is_valid else ("0 ชุด" if target_mode_enabled else "-")},
            {"รายการ": "ชุด/มาร์คขั้นต่ำ / Step", "ค่า": f"{target_result['min_mark_count']:,} / {target_result['mark_step']:,}" if target_mode_enabled and target_result else "-"},
            {"รายการ": "สถานะพื้นที่ที่กำหนด", "ค่า": "ผ่าน" if target_mode_enabled and target_result_is_valid else ("ไม่พอสำหรับขั้นต่ำ" if target_mode_enabled else "-")},
            {"รายการ": "จำนวนมาร์ค", "ค่า": f"{fixed_mark_summary.get('mark_count', 0):,} มาร์ค" if fixed_mark_summary else "-"},
            {"รายการ": "จำนวนคู่มาร์ค", "ค่า": f"{fixed_mark_summary.get('pair_count', 0):,} คู่" if fixed_mark_summary else "-"},
            {"รายการ": "ช่องไฟระหว่างมาร์ค", "ค่า": f"{fixed_mark_summary.get('mark_gap_cm', FIXED_QUANTITY_MARK_GAP_CM):.2f} cm" if fixed_mark_summary else "-"},
            {"รายการ": "ขนาดอนุโลมมาร์ค", "ค่า": f"{fixed_mark_summary.get('mark_tolerance_cm', DEFAULT_FIXED_QUANTITY_MARK_TOLERANCE_CM):.2f} cm" if fixed_mark_summary else "-"},
            {"รายการ": "โหมดจัดเรียง", "ค่า": roll_layout_mode},
            {"รายการ": "กลยุทธ์ที่เลือก", "ค่า": roll_strategy_display_name(roll_layout.strategy_name)},
            {"รายการ": "พื้นที่หน้าม้วนแบบเรียงเดิม", "ค่า": "-" if fixed_quantity_mark_mode else f"{baseline_layout.roll_face_area_sqm:.2f} ตรม."},
            {"รายการ": "ประหยัดจากเรียงเดิม", "ค่า": "ไม่ใช้ในโหมดมาร์คคู่ 57cm" if fixed_quantity_mark_mode else f"{savings_percent:.2f}% ({savings_area_sqm:.2f} ตรม.)"},
            {"รายการ": "ความยาวเข้าม้วน", "ค่า": f"{roll_layout.required_length_cm / 100:.2f} ม."},
            {"รายการ": "แบ่งตัดไม่เกิน 260 cm", "ค่า": f"{cut_section_count:,} ช่วง / ช่วงสุดท้าย {cut_last_length_cm:.2f} cm"},
            {"รายการ": "พื้นที่หน้าม้วนที่ต้องใช้", "ค่า": f"{roll_layout.roll_face_area_sqm:.2f} ตรม."},
            {"รายการ": "พื้นที่จริงของชิ้นงาน", "ค่า": f"{roll_layout.actual_area_sqm:.2f} ตรม."},
            {"รายการ": "พื้นที่ว่าง", "ค่า": f"{roll_layout.empty_area_sqm:.2f} ตรม. ({roll_layout.empty_area_percent:.2f}%)"},
            {"รายการ": "พื้นที่คิดเงินสุดท้าย", "ค่า": f"{roll_layout.final_charge_area_sqm:.2f} ตรม."},
            {"รายการ": "Auto Rotate", "ค่า": f"{'เปิด' if roll_layout.auto_rotate_enabled else 'ปิด'} / หมุน {roll_layout.rotated_count:,} ชิ้น"},
            {"รายการ": "สถานะ", "ค่า": "คิดตามหน้าเพราะพื้นที่ว่างเกินเกณฑ์" if roll_layout.charge_by_page_due_to_waste else "คิดตามกฎความกว้าง/ขนาดชิ้นงาน"},
        ]
        export_text = rows_to_plain_text("สรุปพื้นที่งานสติกเกอร์", area_summary_export_rows)
        export_text += "\nรายการ Size\n" + rows_to_plain_text("", rows)
        csv_export_rows = build_roll_area_export_rows(area_summary_export_rows, rows)
        render_compact_export_bar(
            title="สรุปรายการ Size และพื้นที่หน้าม้วน",
            rows=rows,
            file_prefix="sticker_roll_area_summary",
            extra_text=export_text,
            csv_rows=csv_export_rows,
        )


# =========================================================
# App entry
# =========================================================
st.set_page_config(
    page_title="HUGPRINT Sticker Layout Pro",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_state()
normalize_selected_main_page()
configure_matplotlib_fonts()
inject_css()
inject_startup_loading_overlay(force_show=False)  # แสดงวิดีโอครั้งแรกของ browser session เท่านั้น

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="brand-top">HUGPRINT WORK TOOL</div>
            <div class="brand-title">Sticker Layout Pro</div>
            <div class="brand-sub">คำนวณจำนวน พื้นที่ม้วน จัดเรียง Preview และ Preset งานประจำ · v124-3-main-menu-no-quick-20260620</div>
        </div>
        <div class="sidebar-nav-label">เลือกเมนูหลัก</div>
        """,
        unsafe_allow_html=True,
    )
    normalize_selected_main_page()
    current_main_page = st.session_state.get("selected_page", PAGE_QUANTITY)
    active_main_menu_key = {
        PAGE_QUANTITY: "main_menu_quantity",
        PAGE_AREA_FIXED_QUANTITY: "main_menu_fixed_quantity",
        PAGE_AREA_FIXED_MARK_MIXED: "main_menu_fixed_mark_mixed",
    }.get(current_main_page, "main_menu_quantity")
    st.markdown(
        f"""
        <style>
        section[data-testid="stSidebar"] .st-key-{active_main_menu_key} button {{
            border-color: rgba(251,191,36,.72) !important;
            background:
                radial-gradient(circle at 7% 50%, rgba(251,191,36,.38), transparent 5rem),
                linear-gradient(135deg, rgba(99,85,21,.96), rgba(74,59,17,.94)) !important;
            box-shadow: 0 0 0 1px rgba(245,158,11,.16), 0 16px 36px rgba(245,158,11,.12), 0 14px 32px rgba(0,0,0,.30) !important;
        }}
        section[data-testid="stSidebar"] .st-key-{active_main_menu_key} button::before {{
            border-color: rgba(251,191,36,.94) !important;
            background: radial-gradient(circle, #10100c 0 24%, #f59e0b 27% 100%) !important;
            box-shadow: 0 0 0 6px rgba(245,158,11,.20), 0 8px 18px rgba(245,158,11,.24) !important;
            transform: translateY(-50%) !important;
            animation: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.button(f"🧮 {PAGE_QUANTITY}", key="main_menu_quantity", on_click=set_main_page, args=(PAGE_QUANTITY,), use_container_width=True)
    st.button(f"📦 {PAGE_AREA_FIXED_QUANTITY}", key="main_menu_fixed_quantity", on_click=set_main_page, args=(PAGE_AREA_FIXED_QUANTITY,), use_container_width=True)
    st.button(f"🧩 {PAGE_AREA_FIXED_MARK_MIXED}", key="main_menu_fixed_mark_mixed", on_click=set_main_page, args=(PAGE_AREA_FIXED_MARK_MIXED,), use_container_width=True)
    selected_page = st.session_state.get("selected_page", PAGE_QUANTITY)
    st.divider()

    if selected_page == PAGE_QUANTITY:
        render_quantity_sidebar_controls()
    elif is_area_calculator_page(selected_page):
        render_area_sidebar_controls()

    st.divider()
    st.caption("กดปุ่มเมนูมุมซ้ายบนเพื่อเปิด/ปิด Sidebar")

selected_page = st.session_state.get("selected_page", PAGE_QUANTITY)
if selected_page == PAGE_QUANTITY:
    render_quantity_calculator_page()
elif is_area_calculator_page(selected_page):
    render_area_calculator_page()
else:
    st.session_state.selected_page = PAGE_QUANTITY
    render_quantity_calculator_page()
