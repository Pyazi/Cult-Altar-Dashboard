import sys
import os
import shutil
import time
import json
import random
import asyncio
import websockets
import threading
import psutil
import socket
import io
import gc
import qrcode
import subprocess
import struct
import zlib

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes
    import winreg
else:
    ctypes = None
    winreg = None
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, 
                             QGraphicsView, QGraphicsRectItem, QGraphicsTextItem,
                             QGraphicsPixmapItem, QGraphicsEllipseItem,
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, 
                             QMessageBox, QLabel, QFileDialog, QInputDialog, 
                             QTabWidget, QCheckBox, QComboBox, QSpinBox, 
                             QGroupBox, QDialog, QMenu, QSystemTrayIcon)
from PyQt6.QtCore import Qt, QPointF, QTimer
from PyQt6.QtGui import QFont, QPen, QColor, QBrush, QPixmap, QMovie, QIcon, QAction

# Определяем пути для режима .exe (PyInstaller) и обычного .py
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

os.chdir(BASE_DIR)

def get_resource_path(relative_path):
    """Получение абсолютного пути к ресурсу для dev-режима и для PyInstaller (sys._MEIPASS)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path):
            return path
    local_path = os.path.join(BASE_DIR, relative_path)
    if os.path.exists(local_path):
        return local_path
    return os.path.join(RESOURCE_DIR, relative_path)

# Распаковываем index.html и ресурсы из .exe рядом с программой для HTTP-сервера и кастомизации
if getattr(sys, 'frozen', False):
    for fname in ["index.html", "cult_altar.ico", "languages.json", "cult_preset.json"]:
        bundled_f = os.path.join(RESOURCE_DIR, fname)
        local_f = os.path.join(BASE_DIR, fname)
        if os.path.exists(bundled_f) and not os.path.exists(local_f):
            try:
                shutil.copy2(bundled_f, local_f)
            except Exception:
                pass
    bundled_html = os.path.join(RESOURCE_DIR, "index.html")
    local_html = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(bundled_html):
        try:
            shutil.copy2(bundled_html, local_html)
        except Exception:
            pass

PRESET_FILE = "cult_preset.json"
CONFIG_FILE = "cult_config.json"
LANG_FILE = "languages.json"
MEDIA_DIR = "cult_media"
AUTOSTART_REG_NAME = "CultAltarDashboard"
os.makedirs(MEDIA_DIR, exist_ok=True)

DEFAULT_LANGUAGES = {
    "ru": {
        "name": "Русский",
        "pc": {
            "app_title": "Алтарь Управления",
            "tab_altar": "🕯️ Алтарь",
            "tab_omens": "🔔 Знамения",
            "tab_settings": "⚙️ Настройки",
            "btn_deploy": "🔥 Провести ритуал (На экран)",
            "btn_about": "📜 О проекте",
            "btn_save_preset": "💾 Сохранить пресет",
            "btn_load_preset": "📂 Загрузить",
            "btn_del_selected": "🗑️ Удалить выбранный",
            "btn_clear_canvas": "💀 Очистить холст",
            "w_clock": "👑 Время",
            "w_cpu": "🗡️ CPU",
            "w_ram": "👁️ RAM",
            "w_disk": "💎 Диск C:",
            "w_uptime": "⏳ Аптайм",
            "w_spotify": "🎵 Spotify",
            "w_volume": "🔊 Громкость",
            "w_launcher": "🔮 Призыв",
            "w_image": "🖼️ Декор",
            "sec_theme": "Тема оформления (Theme)",
            "sec_lang": "Язык интерфейса (Language)",
            "sec_canvas": "Размер холста под ваше устройство",
            "sec_net": "Сетевой адрес для подключения смартфона (IP)",
            "sec_autostart": "Автозапуск вместе с Windows",
            "sec_pin": "Безопасность подключения",
            "lbl_profile": "Готовый профиль:",
            "lbl_width": "Ширина (px):",
            "lbl_height": "Высота (px):",
            "btn_apply_res": "Применить размер",
            "lbl_adapter": "Сетевой адаптер:",
            "lbl_adapter_hint": "💡 Выберите адаптер той же Wi-Fi/Ethernet сети, к которой подключен смартфон.",
            "btn_refresh": "🔄 Обновить",
            "autostart_lbl": "Запускать сервер в фоне при включении ПК (через pythonw.exe):",
            "autostart_on": "✅ В автозапуске (Убрать)",
            "autostart_off": "➕ Добавить в автозапуск",
            "sec_autostart_linux": "Автозапуск в Linux / SteamOS (systemd)",
            "autostart_linux_lbl": "Запускать сервер в фоне при входе в систему (через systemd --user):",
            "autostart_linux_on": "✅ Служба systemd активна (Отключить)",
            "autostart_linux_off": "➕ Включить службу systemd",
            "sec_steam": "Игровой режим Steam (Steam Deck / Desktop)",
            "steam_lbl": "Добавить Алтарь в библиотеку сторонних игр Steam для запуска в Gaming Mode:",
            "btn_add_to_steam": "🎮 Добавить в игровой режим Steam",
            "steam_added_title": "Steam Deck / Steam",
            "steam_added_text": "Алтарь успешно добавлен в Steam (shortcuts.vdf)!\nПерезапустите Steam, чтобы увидеть его в библиотеке.",
            "steam_not_found_title": "Steam не найден",
            "steam_not_found_text": "Не удалось обнаружить папку userdata Steam.\nУбедитесь, что Steam хотя бы раз запускался на этом устройстве.",
            "omens_status_linux": "✅ Перехватчик уведомлений Linux (D-Bus) готов к работе.",
            "pin_current": "Текущий постоянный PIN-код:  ",
            "btn_regen_pin": "🔄 Сгенерировать новый PIN",
            "qr_title": "📱 Быстрое подключение",
            "qr_header": "♛ ВРАТА АЛТАРЯ ♛",
            "qr_sub": "Наведите камеру смартфона для автовхода:",
            "qr_manual": "Или для старых телефонов (Android 4-6):",
            "btn_copy_link": "📋 Скопировать ссылку",
            "btn_copied": "✅ Скопировано!",
            "btn_close": "Закрыть",
            "tray_open": "🕯️ Открыть редактор",
            "tray_close": "💀 Закрыть полностью",
            "tray_qr": "📱 Показать QR-код",
            "tray_bubble_title": "Алтарь свёрнут в трей",
            "tray_bubble_text": "Сервер и ритуал продолжают работать в фоне.\nКликните по иконке, чтобы снова открыть редактор.",
            "ritual_complete_title": "Ритуал завершен",
            "ritual_complete_text": "Панель обновлена на экране смартфона!",
            "canvas_updated_title": "Размер обновлен",
            "canvas_updated_text": "Холст изменен на {w}×{h}.\nНажмите «Провести ритуал», чтобы обновить телефон.",
            "preset_saved_title": "Сохранено",
            "preset_saved_text": "Раскладка сохранена в {file}!",
            "preset_loaded_title": "Загружено",
            "preset_loaded_text": "Пресет успешно восстановлен!",
            "preset_empty_title": "Пусто",
            "preset_empty_text": "Файл сохранения еще не создан.",
            "pin_copied": "📋 Скопировано!",
            "launcher_dialog_title": "Название ритуала",
            "launcher_dialog_text": "Текст на кнопке смартфона:",
            "about_title": "О проекте — Алтарь Управления",
            "about_heading": "♛ АЛТАРЬ УПРАВЛЕНИЯ ♛",
            "about_text": "Привет! Меня зовут <b>Семен</b>. Мне нравится игра <i>Cult of the Lamb</i> и обожаю мастерить что-то интересное своими руками.<br><br>Всё началось с того, что у меня без дела лежал старый смартфон — выкинуть жалко, а применить некуда. Готовые программы для вывода виджетов с ПК оказались либо платными, либо некрасивыми, либо вообще отказывались работать на старом Android.<br><br>Тогда я позвал в напарники нейросеть <b>Gemini</b>, и мы собрали этот проект как настоящая команда: с меня — задумка, тесты и сборка, с ИИ — код и технические идеи. Я не программист, но очень рад, что мы живём во время, когда можно с нуля создать что-то своё и поделиться этим с такими же энтузиастами.<br><br><span style='color: #e6b800;'>Нашли баг или есть идея, как улучшить алтарь?</span><br>Напишите мне на почту: <b>pyazi.game@gmail.com</b>",
            "about_close": "Закрыть свиток",
            "omens_info": "Выберите приложения, чьи уведомления будут вызывать всплывающий значок поверх виджетов.\nТекст сообщений НЕ читается и НЕ передается — отображается только пульсирующая иконка на 5 секунд.\nПоложение и размер значка настраиваются перетаскиванием золотой рамки «🔔» на вкладке «Алтарь».",
            "omens_status_ok": "✅ Системный перехватчик Windows готов к работе.",
            "omens_status_no_winrt": "⚠️ Пакеты winrt не установлены (установите через pip для перехвата из Windows).",
            "omens_group": "Активные знамения",
            "omen_tg": "✈️ Telegram (значок самолетика)",
            "omen_dc": "🎮 Discord (значок культа связи)",
            "omen_st": "⚙️ Steam (значок гильдии)",
            "btn_test_omen": "🧪 Тест на экране",
            "omen_no_connection": "Сначала подключите смартфон к серверу!",
            "delete_anchor_warning": "Якорь уведомлений нельзя удалить с холста — его можно скрыть, сняв галочки на вкладке «🔔 Знамения».",
            "delete_selected_prompt": "Кликните по нужному виджету на холсте, чтобы выделить его, а затем нажмите «Удалить выбранный» или клавишу Delete.",
            "image_dialog_filter": "Изображения (*.png *.jpg *.jpeg *.gif *.webp)",
            "image_copy_error": "Не удалось скопировать файл: {err}",
            "server_not_running": "Сервер еще не запущен.",
            "copy_tooltip": "Кликните, чтобы скопировать адрес ссылки",
            "qr_tooltip": "Показать QR-код для быстрого подключения смартфона",
            "refresh_ip_tooltip": "Пересканировать сетевые адаптеры",
            "ip_primary": "Основной",
            "ip_virtual": "Виртуальный",
            "profile_phone_h": "Смартфон Горизонтально (640 × 360)",
            "profile_phone_v": "Смартфон Вертикально (360 × 640)",
            "profile_phone_wide": "Широкий смартфон (800 × 360)",
            "profile_tablet_h": "Планшет Горизонтально (1024 × 600)",
            "profile_tablet_v": "Планшет Вертикально (600 × 1024)"
        },
        "web": {
            "setup_title": "♛ АЛТАРЬ СИСТЕМЫ ♛",
            "enter_pin": "Введите 4-значный PIN-код из окна программы:",
            "server_prefix": "Сервер: ",
            "btn_connect": "Призвать панель",
            "btn_fs": "На весь экран",
            "connecting": "Соединение с Алтарем...",
            "empty_pin": "Введите 4-значный PIN-код!",
            "bad_pin": "Неверный PIN-код! Доступ отвергнут.",
            "sleep_title": "Алтарь дремлет",
            "sleep_sub": "Ожидание пробуждения главного ПК..."
        },
        "theme_names": {
            "cult": "Cult Edition (Мрачный культ)",
            "stardew": "Stardew Valley (Уютная ферма)",
            "twilight": "Сумерки / Twilight (Modern Dark)"
        },
        "theme_titles": {
            "cult": {
                "clock": "♛ ВРЕМЯ РИТУАЛА",
                "cpu": "🗡 РВЕНИЕ CPU",
                "ram": "👁 ВЕРА RAM",
                "disk": "💎 КАЗНА DISK",
                "uptime": "⏳ ЭПОХА ПК",
                "spotify": "🎵 ПЕСНЬ SPOTIFY",
                "volume": "🔊 ГЛАС СИСТЕМЫ",
                "launcher": "🔮 ПРИЗВАТЬ"
            },
            "stardew": {
                "clock": "🌾 ВРЕМЯ В ДОЛИНЕ",
                "cpu": "⛏ ЭНЕРГИЯ CPU",
                "ram": "🥕 УРОЖАЙ RAM",
                "disk": "📦 СУНДУК DISK",
                "uptime": "🐓 ДЕНЬ НА ФЕРМЕ",
                "spotify": "🎶 МУЗЫКА ДЖУНИМО",
                "volume": "🍃 ЗВУКИ ПРИРОДЫ",
                "launcher": "📮 ПОСЫЛКА"
            },
            "twilight": {
                "clock": "⚡ ВРЕМЯ СИСТЕМЫ",
                "cpu": "⚙️ ПРОЦЕССОР CPU",
                "ram": "📊 ПАМЯТЬ RAM",
                "disk": "💾 НАКОПИТЕЛЬ DISK",
                "uptime": "⏱ ВРЕМЯ РАБОТЫ",
                "spotify": "🎧 ПЛЕЕР SPOTIFY",
                "volume": "🔊 ГРОМКОСТЬ",
                "launcher": "🚀 ЗАПУСК"
            }
        }
    },
    "en": {
        "name": "English",
        "pc": {
            "app_title": "Cult Altar Dashboard",
            "tab_altar": "🕯️ Altar",
            "tab_omens": "🔔 Omens",
            "tab_settings": "⚙️ Settings",
            "btn_deploy": "🔥 Cast Ritual (To Screen)",
            "btn_about": "📜 About",
            "btn_save_preset": "💾 Save Preset",
            "btn_load_preset": "📂 Load",
            "btn_del_selected": "🗑️ Delete Selected",
            "btn_clear_canvas": "💀 Clear Canvas",
            "w_clock": "👑 Time",
            "w_cpu": "🗡️ CPU",
            "w_ram": "👁️ RAM",
            "w_disk": "💎 Disk C:",
            "w_uptime": "⏳ Uptime",
            "w_spotify": "🎵 Spotify",
            "w_volume": "🔊 Volume",
            "w_launcher": "🔮 Launcher",
            "w_image": "🖼️ Decor",
            "sec_theme": "Appearance Theme",
            "sec_lang": "Interface Language",
            "sec_canvas": "Canvas size for your device",
            "sec_net": "Network connection for smartphone (IP)",
            "sec_autostart": "Autostart with Windows",
            "sec_pin": "Connection Security",
            "lbl_profile": "Preset Profile:",
            "lbl_width": "Width (px):",
            "lbl_height": "Height (px):",
            "btn_apply_res": "Apply Size",
            "lbl_adapter": "Network Adapter:",
            "lbl_adapter_hint": "💡 Choose adapter of the same Wi-Fi/Ethernet network your phone is connected to.",
            "btn_refresh": "🔄 Refresh",
            "autostart_lbl": "Launch server silently when Windows starts (via pythonw.exe):",
            "autostart_on": "✅ Autostart Enabled (Remove)",
            "autostart_off": "➕ Add to Autostart",
            "sec_autostart_linux": "Autostart in Linux / SteamOS (systemd)",
            "autostart_linux_lbl": "Launch server in background at session login (via systemd --user):",
            "autostart_linux_on": "✅ systemd service active (Disable)",
            "autostart_linux_off": "➕ Enable systemd service",
            "sec_steam": "Steam Gaming Mode (Steam Deck / Desktop)",
            "steam_lbl": "Add Altar to Steam non-Steam library to launch from Gaming Mode:",
            "btn_add_to_steam": "🎮 Add to Steam Gaming Mode",
            "steam_added_title": "Steam Deck / Steam",
            "steam_added_text": "Altar was successfully added to Steam (shortcuts.vdf)!\nRestart Steam to see it in your library.",
            "steam_not_found_title": "Steam Not Found",
            "steam_not_found_text": "Could not find Steam userdata directory.\nMake sure Steam has been launched at least once on this device.",
            "omens_status_linux": "✅ Linux notification listener (D-Bus) is ready.",
            "pin_current": "Current permanent PIN:  ",
            "btn_regen_pin": "🔄 Generate New PIN",
            "qr_title": "📱 Quick Connection",
            "qr_header": "♛ GATES OF THE ALTAR ♛",
            "qr_sub": "Point your smartphone camera for auto-login:",
            "qr_manual": "Or for older phones (Android 4-6):",
            "btn_copy_link": "📋 Copy Link",
            "btn_copied": "✅ Copied!",
            "btn_close": "Close",
            "tray_open": "🕯️ Open Editor",
            "tray_close": "💀 Exit Completely",
            "tray_qr": "📱 Show QR Code",
            "tray_bubble_title": "Altar Minimized to Tray",
            "tray_bubble_text": "Server and ritual continue working in background.\nClick icon to reopen editor.",
            "ritual_complete_title": "Ritual Complete",
            "ritual_complete_text": "Dashboard updated on phone screen!",
            "canvas_updated_title": "Canvas Resized",
            "canvas_updated_text": "Canvas resized to {w}×{h}.\nClick 'Cast Ritual' to update phone.",
            "preset_saved_title": "Saved",
            "preset_saved_text": "Layout saved to {file}!",
            "preset_loaded_title": "Loaded",
            "preset_loaded_text": "Preset restored successfully!",
            "preset_empty_title": "Empty",
            "preset_empty_text": "Save file has not been created yet.",
            "pin_copied": "📋 Copied!",
            "launcher_dialog_title": "Ritual Name",
            "launcher_dialog_text": "Button label on smartphone:",
            "about_title": "About — Cult Altar Dashboard",
            "about_heading": "♛ ALTAR OF CONTROL ♛",
            "about_text": "Hello! My name is <b>Semyon</b>. I love the game <i>Cult of the Lamb</i> and enjoy crafting interesting things with my own hands.<br><br>It all started with an old smartphone gathering dust — too good to throw away, but no real use for it. Existing PC widget apps were either paid, clunky, or simply refused to run on old Android.<br><br>So I invited the <b>Gemini</b> AI as my partner, and we built this project together like a true team: I handled the concept, testing, and assembly; the AI wrote the code and technical architecture. I'm not a professional programmer, but I'm thrilled to live in a time when anyone can create something cool from scratch and share it with fellow enthusiasts.<br><br><span style='color: #e6b800;'>Found a bug or have an idea to improve the altar?</span><br>Email me at: <b>pyazi.game@gmail.com</b>",
            "about_close": "Close Scroll",
            "omens_info": "Choose apps whose notifications will trigger a floating badge over widgets.\nMessage text is NEVER read or transmitted — only a pulsing icon displays for 5 seconds.\nBadge position and size are adjusted by moving the golden '🔔' box on the 'Altar' tab.",
            "omens_status_ok": "✅ Windows notification listener is ready.",
            "omens_status_no_winrt": "⚠️ winrt package is not installed (install via pip for Windows listener).",
            "omens_group": "Active Omens",
            "omen_tg": "✈️ Telegram (paper plane icon)",
            "omen_dc": "🎮 Discord (community icon)",
            "omen_st": "⚙️ Steam (gaming guild icon)",
            "btn_test_omen": "🧪 Test on screen",
            "omen_no_connection": "Connect your smartphone to the server first!",
            "delete_anchor_warning": "The notification anchor cannot be removed from canvas — hide it by unchecking omens in the '🔔 Omens' tab.",
            "delete_selected_prompt": "Click a widget on the canvas to select it, then click 'Delete Selected' or press Delete.",
            "image_dialog_filter": "Images (*.png *.jpg *.jpeg *.gif *.webp)",
            "image_copy_error": "Failed to copy file: {err}",
            "server_not_running": "Server is not running yet.",
            "copy_tooltip": "Click to copy link address",
            "qr_tooltip": "Show QR code for quick smartphone connection",
            "refresh_ip_tooltip": "Rescan network adapters",
            "ip_primary": "Primary",
            "ip_virtual": "Virtual",
            "profile_phone_h": "Smartphone Horizontal (640 × 360)",
            "profile_phone_v": "Smartphone Vertical (360 × 640)",
            "profile_phone_wide": "Wide Smartphone (800 × 360)",
            "profile_tablet_h": "Tablet Horizontal (1024 × 600)",
            "profile_tablet_v": "Tablet Vertical (600 × 1024)"
        },
        "web": {
            "setup_title": "♛ SYSTEM ALTAR ♛",
            "enter_pin": "Enter 4-digit PIN from the PC app:",
            "server_prefix": "Server: ",
            "btn_connect": "Summon Dashboard",
            "btn_fs": "Fullscreen",
            "connecting": "Connecting to Altar...",
            "empty_pin": "Please enter 4-digit PIN!",
            "bad_pin": "Invalid PIN! Access denied.",
            "sleep_title": "Altar is Asleep",
            "sleep_sub": "Waiting for main PC to awaken..."
        },
        "theme_names": {
            "cult": "Cult Edition (Grim Cult)",
            "stardew": "Stardew Valley (Cozy Farm)",
            "twilight": "Twilight (Modern Dark)"
        },
        "theme_titles": {
            "cult": {
                "clock": "♛ RITUAL TIME",
                "cpu": "🗡 CPU ZEAL",
                "ram": "👁 RAM FAITH",
                "disk": "💎 DISK TREASURY",
                "uptime": "⏳ PC EPOCH",
                "spotify": "🎵 SPOTIFY CHANT",
                "volume": "🔊 SYSTEM VOICE",
                "launcher": "🔮 SUMMON"
            },
            "stardew": {
                "clock": "🌾 VALLEY TIME",
                "cpu": "⛏ CPU ENERGY",
                "ram": "🥕 RAM HARVEST",
                "disk": "📦 DISK CHEST",
                "uptime": "🐓 FARM DAY",
                "spotify": "🎶 JUNIMO MUSIC",
                "volume": "🍃 NATURE SOUNDS",
                "launcher": "📮 SHIPPING BIN"
            },
            "twilight": {
                "clock": "⚡ SYSTEM CLOCK",
                "cpu": "⚙️ CPU LOAD",
                "ram": "📊 RAM USAGE",
                "disk": "💾 DISK SPACE",
                "uptime": "⏱ UPTIME",
                "spotify": "🎧 SPOTIFY PLAYER",
                "volume": "🔊 VOLUME",
                "launcher": "🚀 LAUNCH"
            }
        }
    }
}

def load_languages():
    if os.path.exists(LANG_FILE):
        try:
            with open(LANG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception as e:
            print(f"Ошибка загрузки languages.json: {e}")

    bundled_lang = get_resource_path("languages.json")
    if os.path.exists(bundled_lang) and bundled_lang != os.path.abspath(LANG_FILE):
        try:
            with open(bundled_lang, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    try:
                        with open(LANG_FILE, "w", encoding="utf-8") as out_f:
                            json.dump(data, out_f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    return data
        except Exception:
            pass

    try:
        with open(LANG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_LANGUAGES, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return DEFAULT_LANGUAGES.copy()

ALL_LANGUAGES = load_languages()

def tr(key, lang=None, **kwargs):
    l = lang or APP_CONFIG.get("language", "ru")
    lang_dict = ALL_LANGUAGES.get(l, ALL_LANGUAGES.get("ru", {}))
    pc_dict = lang_dict.get("pc", {})
    text = pc_dict.get(key)
    if text is None:
        text = ALL_LANGUAGES.get("ru", {}).get("pc", {}).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            pass
    return text

THEMES = {
    "cult": {
        "id": "cult",
        "name_key": "cult",
        "card_bg": "#1c171c",
        "card_text": "#f2ebd9",
        "canvas_bg": "#141014",
        "scene_bg": "#161216",
        "border": "#8a1c1c",
        "accents": {
            "clock": "#f2ebd9",
            "cpu": "#d92b2b",
            "ram": "#e6b800",
            "disk": "#b366ff",
            "uptime": "#66d9ff",
            "spotify": "#1db954",
            "volume": "#e6b800",
            "launcher": "#e6b800"
        },
        "style": """
            QMainWindow, QWidget { background-color: #120f12; color: #f2ebd9; font-family: Georgia; }
            QTabWidget::pane { border: 1px solid #8a1c1c; background-color: #120f12; }
            QTabBar::tab {
                background-color: #1c171c; color: #b8ad9e; padding: 8px 16px;
                border: 1px solid #4a151b; border-bottom: none; font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #2b1419; color: #e6b800; border-color: #8a1c1c;
            }
            QPushButton { 
                background-color: #241d24; color: #f2ebd9; border: 1px solid #8a1c1c; 
                padding: 6px 9px; font-weight: bold; border-radius: 3px; font-size: 12px;
            }
            QPushButton:hover { background-color: #38252b; border-color: #d92b2b; }
            QCheckBox { font-size: 14px; spacing: 8px; padding: 4px; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #8a1c1c; background-color: #1c171c; }
            QCheckBox::indicator:checked { background-color: #8a1c1c; border-color: #e6b800; }
            QComboBox, QSpinBox {
                background-color: #1c171c; color: #f2ebd9; border: 1px solid #8a1c1c;
                padding: 5px; font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #4a151b; margin-top: 12px; padding-top: 14px;
                font-weight: bold; color: #e6b800;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """
    },
    "stardew": {
        "id": "stardew",
        "name_key": "stardew",
        "card_bg": "#f3e5c2",
        "card_text": "#3e2410",
        "canvas_bg": "#2b1c12",
        "scene_bg": "#24180f",
        "border": "#8c5826",
        "accents": {
            "clock": "#7c4a1e",
            "cpu": "#c0392b",
            "ram": "#b8860b",
            "disk": "#8e44ad",
            "uptime": "#2980b9",
            "spotify": "#27ae60",
            "volume": "#b8860b",
            "launcher": "#b87333"
        },
        "style": """
            QMainWindow, QWidget { background-color: #201712; color: #f7ebd2; font-family: Georgia; }
            QTabWidget::pane { border: 1px solid #8c5826; background-color: #201712; }
            QTabBar::tab {
                background-color: #2c1f18; color: #dfc8a8; padding: 8px 16px;
                border: 1px solid #5a381b; border-bottom: none; font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #442a17; color: #ffd966; border-color: #b87333;
            }
            QPushButton { 
                background-color: #33231a; color: #f7ebd2; border: 1px solid #8c5826; 
                padding: 6px 9px; font-weight: bold; border-radius: 3px; font-size: 12px;
            }
            QPushButton:hover { background-color: #4a3426; border-color: #e69138; }
            QCheckBox { font-size: 14px; spacing: 8px; padding: 4px; color: #f7ebd2; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #8c5826; background-color: #2c1f18; }
            QCheckBox::indicator:checked { background-color: #8c5826; border-color: #ffd966; }
            QComboBox, QSpinBox {
                background-color: #2c1f18; color: #f7ebd2; border: 1px solid #8c5826;
                padding: 5px; font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #6e4420; margin-top: 12px; padding-top: 14px;
                font-weight: bold; color: #ffd966;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """
    },
    "twilight": {
        "id": "twilight",
        "name_key": "twilight",
        "card_bg": "#23202e",
        "card_text": "#e6e4f0",
        "canvas_bg": "#15131c",
        "scene_bg": "#131118",
        "border": "#3b354d",
        "accents": {
            "clock": "#e6e4f0",
            "cpu": "#f45b84",
            "ram": "#9b72f3",
            "disk": "#5299f0",
            "uptime": "#2dd4bf",
            "spotify": "#1db954",
            "volume": "#9b72f3",
            "launcher": "#f45b84"
        },
        "style": """
            QMainWindow, QWidget { background-color: #191722; color: #e6e4f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            QTabWidget::pane { border: 1px solid #3b354d; background-color: #191722; }
            QTabBar::tab {
                background-color: #23202e; color: #a5a1b8; padding: 8px 16px;
                border: 1px solid #322d42; border-bottom: none; font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #2e2a3d; color: #9b72f3; border-color: #9b72f3;
            }
            QPushButton { 
                background-color: #272333; color: #e6e4f0; border: 1px solid #3b354d; 
                padding: 6px 9px; font-weight: bold; border-radius: 4px; font-size: 12px;
            }
            QPushButton:hover { background-color: #363047; border-color: #9b72f3; }
            QCheckBox { font-size: 14px; spacing: 8px; padding: 4px; color: #e6e4f0; }
            QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #3b354d; background-color: #23202e; border-radius: 3px; }
            QCheckBox::indicator:checked { background-color: #9b72f3; border-color: #9b72f3; }
            QComboBox, QSpinBox {
                background-color: #23202e; color: #e6e4f0; border: 1px solid #3b354d;
                padding: 5px; font-size: 13px; border-radius: 3px;
            }
            QGroupBox {
                border: 1px solid #3b354d; margin-top: 12px; padding-top: 14px;
                font-weight: bold; color: #9b72f3;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """
    }
}

def get_theme_title(w_type, theme=None, lang=None):
    t = theme or APP_CONFIG.get("theme", "cult")
    l = lang or APP_CONFIG.get("language", "ru")
    lang_dict = ALL_LANGUAGES.get(l, ALL_LANGUAGES.get("ru", {}))
    theme_dict = lang_dict.get("theme_titles", {}).get(t, {})
    title = theme_dict.get(w_type)
    if title:
        return title
    return ALL_LANGUAGES.get("ru", {}).get("theme_titles", {}).get("cult", {}).get(w_type, w_type.upper())

WINRT_AVAILABLE = False
if IS_WINDOWS:
    try:
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus
        )
        from winrt.windows.ui.notifications import NotificationKinds
        WINRT_AVAILABLE = True
    except ImportError:
        WINRT_AVAILABLE = False

# --- КОНФИГУРАЦИЯ ---
DEFAULT_CONFIG = {
    "pin": str(random.randint(1000, 9999)),
    "screen_w": 640,
    "screen_h": 360,
    "notify_telegram": True,
    "notify_discord": True,
    "notify_steam": True,
    "selected_ip": None,
    "language": "ru",
    "theme": "cult"
}

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    else:
        save_config(cfg)
    return cfg

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")

APP_CONFIG = load_config()

# --- ОПРЕДЕЛЕНИЕ СЕТЕВЫХ АДАПТЕРОВ И IP ---
VIRTUAL_ADAPTER_KEYWORDS = [
    "virtual", "vmware", "vbox", "radmin", "hamachi", "vethernet",
    "tap", "tun", "wsl", "loopback", "pseudo", "bluetooth", "hyper-v", "pcap"
]

def is_virtual_adapter(name):
    name_low = name.lower()
    return any(kw in name_low for kw in VIRTUAL_ADAPTER_KEYWORDS)

def get_network_adapters():
    """
    Возвращает список адаптеров: [{'name': str, 'ip': str, 'is_virtual': bool, 'is_primary': bool}]
    Игнорирует loopback, APIPA (169.254.x.x) и неактивные интерфейсы.
    """
    adapters = []
    primary_ip = None

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        primary_ip = None

    try:
        stats_map = psutil.net_if_stats()
        addrs_map = psutil.net_if_addrs()

        for iface_name, addrs in addrs_map.items():
            stats = stats_map.get(iface_name)
            is_up = stats.isup if stats else True
            if not is_up:
                continue

            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if ip.startswith("127.") or ip.startswith("169.254."):
                        continue
                    is_virt = is_virtual_adapter(iface_name)
                    is_prim = (ip == primary_ip) if primary_ip else (not is_virt)
                    adapters.append({
                        "name": iface_name,
                        "ip": ip,
                        "is_virtual": is_virt,
                        "is_primary": is_prim
                    })
    except Exception as e:
        print(f"Ошибка получения сетевых адаптеров: {e}")

    adapters.sort(key=lambda a: (a["is_virtual"], not a["is_primary"]))

    if not adapters:
        adapters.append({
            "name": "Локальный (Loopback)",
            "ip": "127.0.0.1",
            "is_virtual": False,
            "is_primary": True
        })

    return adapters

def get_current_ip():
    adapters = get_network_adapters()
    selected_ip = APP_CONFIG.get("selected_ip")
    if selected_ip:
        for a in adapters:
            if a["ip"] == selected_ip:
                return a["ip"]
    for a in adapters:
        if a["is_primary"] and not a["is_virtual"]:
            return a["ip"]
    for a in adapters:
        if not a["is_virtual"]:
            return a["ip"]
    return adapters[0]["ip"]

# --- ДИАЛОГ С QR-КОДОМ ДЛЯ БЫСТРОГО ВХОДА ---
class QRCodeDialog(QDialog):
    def __init__(self, parent, ip, pin):
        super().__init__(parent)
        self.setWindowTitle(tr("qr_title"))
        self.setFixedSize(380, 520)
        cur_theme = APP_CONFIG.get("theme", "cult")
        theme_cfg = THEMES.get(cur_theme, THEMES["cult"])
        self.setStyleSheet(f"""
            QDialog {{ background-color: {theme_cfg['card_bg']}; color: {theme_cfg['card_text']}; font-family: Georgia; }}
            QLabel {{ color: {theme_cfg['card_text']}; }}
            QPushButton {{
                background-color: #241d24; color: #f2ebd9; border: 1px solid #8a1c1c;
                padding: 7px 14px; font-weight: bold; border-radius: 3px; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #38252b; border-color: #d92b2b; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(tr("qr_header"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; color: #e6b800; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(title)

        subtitle = QLabel(tr("qr_sub"))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #b8ad9e;")
        layout.addWidget(subtitle)

        qr_container = QLabel()
        qr_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_container.setFixedSize(220, 220)
        qr_container.setStyleSheet("background-color: #ffffff; border: 2px solid #e6b800; border-radius: 6px; padding: 6px;")

        full_url = f"http://{ip}:8080/?pin={pin}"
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=1
            )
            qr.add_data(full_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pix = QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
            qr_container.setPixmap(pix.scaled(208, 208, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            qr_container.setText(f"Ошибка QR: {e}")
            qr_container.setStyleSheet("background-color: #241d24; color: #ff5555;")

        layout.addWidget(qr_container, alignment=Qt.AlignmentFlag.AlignCenter)

        info_box = QGroupBox(tr("qr_manual"))
        info_box.setStyleSheet("QGroupBox { border: 1px solid #4a151b; margin-top: 8px; padding-top: 10px; font-size: 12px; color: #b8ad9e; }")
        ib_layout = QVBoxLayout(info_box)
        ib_layout.setSpacing(6)

        self.url_label = QLabel(f"http://{ip}:8080")
        self.url_label.setStyleSheet("font-size: 13px; color: #66d9ff; font-weight: bold;")
        ib_layout.addWidget(self.url_label)

        pin_row = QHBoxLayout()
        pin_lbl = QLabel(f"PIN: {pin}")
        pin_lbl.setStyleSheet("font-size: 16px; color: #e6b800; font-weight: bold;")
        pin_row.addWidget(pin_lbl)

        btn_copy_url = QPushButton(tr("btn_copy_link"))
        btn_copy_url.setStyleSheet("font-size: 11px; padding: 4px 8px;")
        btn_copy_url.clicked.connect(lambda: self.copy_link(full_url, btn_copy_url))
        pin_row.addStretch()
        pin_row.addWidget(btn_copy_url)
        ib_layout.addLayout(pin_row)

        layout.addWidget(info_box)

        btn_close = QPushButton(tr("btn_close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def copy_link(self, url, btn):
        QApplication.clipboard().setText(url)
        btn.setText(tr("btn_copied"))
        QTimer.singleShot(1500, lambda: btn.setText(tr("btn_copy_link")))

authenticated_phones = set()
ws_loop = None
current_layout_json = None
registered_apps = {}

# --- АВТОЗАПУСК: WINDOWS (РЕЕСТР) И LINUX (SYSTEMD --USER) ---
def get_autostart_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    python_exe = sys.executable
    if IS_WINDOWS and python_exe.lower().endswith("python.exe"):
        pythonw_exe = python_exe[:-10] + "pythonw.exe"
        if os.path.exists(pythonw_exe):
            python_exe = pythonw_exe
    script_path = os.path.abspath(__file__)
    return f'"{python_exe}" "{script_path}"'

def get_systemd_service_path():
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(config_home, "systemd", "user", "cult-altar.service")

def is_systemd_autostart_enabled():
    svc_path = get_systemd_service_path()
    if not os.path.exists(svc_path):
        return False
    try:
        res = subprocess.run(
            ["systemctl", "--user", "is-enabled", "cult-altar.service"],
            capture_output=True, text=True, timeout=2.0
        )
        return "enabled" in res.stdout
    except Exception:
        return os.path.exists(svc_path)

def set_systemd_autostart(enable):
    svc_path = get_systemd_service_path()
    svc_dir = os.path.dirname(svc_path)
    try:
        if enable:
            os.makedirs(svc_dir, exist_ok=True)
            if getattr(sys, 'frozen', False):
                exec_cmd = f'"{sys.executable}" --headless'
            else:
                exec_cmd = f'"{sys.executable}" "{os.path.abspath(__file__)}" --headless'
            work_dir = BASE_DIR
            content = f"""[Unit]
Description=Cult Altar Dashboard Server
After=network.target sound.target

[Service]
Type=simple
ExecStart={exec_cmd}
WorkingDirectory={work_dir}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
            with open(svc_path, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=3.0)
            subprocess.run(["systemctl", "--user", "enable", "--now", "cult-altar.service"], timeout=3.0)
            return True
        else:
            if os.path.exists(svc_path):
                subprocess.run(["systemctl", "--user", "disable", "--now", "cult-altar.service"], timeout=3.0)
                try:
                    os.remove(svc_path)
                except OSError:
                    pass
                subprocess.run(["systemctl", "--user", "daemon-reload"], timeout=3.0)
            return True
    except Exception as e:
        print(f"Ошибка управления службой systemd: {e}")
        return False

def is_autostart_enabled():
    if IS_WINDOWS:
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            val, _ = winreg.QueryValueEx(key, AUTOSTART_REG_NAME)
            winreg.CloseKey(key)
            return bool(val)
        except Exception:
            return False
    elif IS_LINUX:
        return is_systemd_autostart_enabled()
    return False

def set_autostart(enable):
    if IS_WINDOWS:
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if enable:
                winreg.SetValueEx(key, AUTOSTART_REG_NAME, 0, winreg.REG_SZ, get_autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_REG_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Ошибка автозапуска: {e}")
            return False
    elif IS_LINUX:
        return set_systemd_autostart(enable)
    return False

# --- ИНТЕГРАЦИЯ СО STEAM DECK И STEAM GAMING MODE (SHORTCUTS.VDF) ---
def parse_shortcuts_vdf(data: bytes):
    """Парсинг бинарного формата Steam KeyValues (shortcuts.vdf)."""
    offset = 0
    length = len(data)

    def read_string():
        nonlocal offset
        end = data.find(b'\x00', offset)
        if end == -1:
            res = data[offset:].decode("utf-8", errors="replace")
            offset = length
            return res
        res = data[offset:end].decode("utf-8", errors="replace")
        offset = end + 1
        return res

    def parse_map():
        nonlocal offset
        result = {}
        while offset < length:
            type_byte = data[offset]
            offset += 1
            if type_byte == 0x08:
                break
            key = read_string()
            if type_byte == 0x00:
                result[key] = parse_map()
            elif type_byte == 0x01:
                result[key] = read_string()
            elif type_byte == 0x02:
                val = struct.unpack_from('<i', data, offset)[0]
                offset += 4
                result[key] = val
        return result

    if not data or data[0] != 0x00:
        return {}
    offset += 1
    root_name = read_string()
    if root_name.lower() == "shortcuts":
        return parse_map()
    return {}

def serialize_shortcuts_vdf(shortcuts_dict: dict) -> bytes:
    """Сериализация словаря в бинарный формат Steam KeyValues (shortcuts.vdf)."""
    buf = bytearray()

    def write_string(s: str):
        buf.extend(s.encode("utf-8"))
        buf.append(0x00)

    def write_map(m: dict):
        for k, v in m.items():
            if isinstance(v, dict):
                buf.append(0x00)
                write_string(str(k))
                write_map(v)
            elif isinstance(v, str):
                buf.append(0x01)
                write_string(str(k))
                write_string(v)
            elif isinstance(v, int):
                buf.append(0x02)
                write_string(str(k))
                buf.extend(struct.pack('<i', v))
        buf.append(0x08)

    buf.append(0x00)
    write_string("shortcuts")
    write_map(shortcuts_dict)
    buf.append(0x08)
    return bytes(buf)

def find_steam_shortcuts_paths():
    """Поиск путей shortcuts.vdf для зарегистрированных пользователей Steam."""
    candidates = []
    if IS_LINUX:
        home = os.path.expanduser("~")
        search_roots = [
            os.path.join(home, ".steam", "steam", "userdata"),
            os.path.join(home, ".local", "share", "Steam", "userdata"),
            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".steam", "steam", "userdata")
        ]
        for root in search_roots:
            if os.path.exists(root):
                for user_id in os.listdir(root):
                    cfg_dir = os.path.join(root, user_id, "config")
                    vdf_file = os.path.join(cfg_dir, "shortcuts.vdf")
                    if os.path.exists(cfg_dir):
                        candidates.append(vdf_file)
    elif IS_WINDOWS:
        prog_roots = [
            r"C:\Program Files (x86)\Steam\userdata",
            r"C:\Program Files\Steam\userdata"
        ]
        for root in prog_roots:
            if os.path.exists(root):
                for user_id in os.listdir(root):
                    cfg_dir = os.path.join(root, user_id, "config")
                    vdf_file = os.path.join(cfg_dir, "shortcuts.vdf")
                    if os.path.exists(cfg_dir):
                        candidates.append(vdf_file)
    return candidates

def add_to_steam_gaming_mode():
    """Добавляет Cult Altar Dashboard в библиотеку сторонних игр Steam для Steam Deck / SteamOS."""
    vdf_paths = find_steam_shortcuts_paths()
    if not vdf_paths:
        return False, "steam_not_found"

    if getattr(sys, 'frozen', False):
        exe_path = f'"{sys.executable}"'
        start_dir = f'"{BASE_DIR}"'
    else:
        exe_path = f'"{sys.executable}"'
        start_dir = f'"{BASE_DIR}"'

    app_name = "Cult Altar Dashboard"
    crc = zlib.crc32((exe_path + app_name).encode('utf-8')) | 0x80000000
    app_id = struct.unpack('<i', struct.pack('<I', crc))[0]

    ico_path = os.path.join(BASE_DIR, "cult_altar.ico")
    if not os.path.exists(ico_path):
        ico_path = get_resource_path("cult_altar.ico")
    if not os.path.exists(ico_path):
        ico_path = ""

    launch_opts = f'"{os.path.abspath(__file__)}"' if not getattr(sys, 'frozen', False) else ""

    success_count = 0
    for vdf_file in vdf_paths:
        try:
            shortcuts = {}
            if os.path.exists(vdf_file):
                with open(vdf_file, "rb") as f:
                    shortcuts = parse_shortcuts_vdf(f.read())

            entry_idx = None
            for idx_str, entry in shortcuts.items():
                if isinstance(entry, dict) and entry.get("AppName") == app_name:
                    entry_idx = idx_str
                    break

            if entry_idx is None:
                existing_indices = [int(k) for k in shortcuts.keys() if k.isdigit()]
                entry_idx = str(max(existing_indices) + 1 if existing_indices else 0)

            shortcuts[entry_idx] = {
                "appid": app_id,
                "AppName": app_name,
                "Exe": exe_path,
                "StartDir": start_dir,
                "icon": ico_path,
                "ShortcutPath": "",
                "LaunchOptions": launch_opts,
                "IsHidden": 0,
                "AllowDesktopConfig": 1,
                "AllowOverlay": 1,
                "OpenVR": 0,
                "Devkit": 0,
                "DevkitGameID": "",
                "DevkitOverrideAppID": 0,
                "LastPlayTime": 0,
                "FlatpakAppID": "",
                "tags": {}
            }

            serialized = serialize_shortcuts_vdf(shortcuts)
            with open(vdf_file, "wb") as f:
                f.write(serialized)
            success_count += 1
        except Exception as e:
            print(f"Ошибка записи в {vdf_file}: {e}")

    return (success_count > 0), ("ok" if success_count > 0 else "steam_write_error")

# --- КРОССПЛАТФОРМЕННЫЙ ЗАПУСК ПРИЛОЖЕНИЙ И ФАЙЛОВ ---
def launch_application(app_path):
    """
    Кроссплатформенный запуск приложений, игр Steam и файлов.
    Windows: os.startfile
    Linux / SteamOS: xdg-open или subprocess.Popen (поддерживает steam://, .desktop, bin)
    """
    if not app_path:
        return
    try:
        if IS_WINDOWS:
            os.startfile(app_path)
        elif IS_LINUX:
            if app_path.startswith("steam://") or app_path.startswith("http://") or app_path.startswith("https://"):
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", app_path])
                elif shutil.which("steam"):
                    subprocess.Popen(["steam", app_path])
            elif os.path.exists(app_path):
                if os.access(app_path, os.X_OK) and not os.path.isdir(app_path) and not app_path.endswith(".desktop"):
                    subprocess.Popen([app_path])
                elif shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", app_path])
                else:
                    subprocess.Popen(["sh", app_path])
            else:
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", app_path])
                else:
                    subprocess.Popen(app_path.split())
    except Exception as e:
        print(f"Ошибка запуска приложения '{app_path}': {e}")

# --- ОПТИМИЗИРОВАННОЕ УПРАВЛЕНИЕ МЕДИА И SPOTIFY (WINDOWS И LINUX) ---
if IS_WINDOWS and ctypes:
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
else:
    user32 = None
    WNDENUMPROC = None

MEDIA_KEYS = {
    "vol_mute": 0xAD,
    "vol_down": 0xAE,
    "vol_up": 0xAF,
    "next": 0xB0,
    "prev": 0xB1,
    "play_pause": 0xB3
}

def linux_volume_control(cmd):
    """
    Управление громкостью на Linux (SteamOS / PipeWire / PulseAudio / ALSA).
    Поддерживает wpctl (Steam Deck WirePlumber), pactl (PulseAudio), amixer (ALSA).
    """
    # 1. wpctl (Steam Deck SteamOS 3.x / PipeWire default)
    if shutil.which("wpctl"):
        try:
            if cmd == "vol_up":
                subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%+"])
                return
            elif cmd == "vol_down":
                subprocess.Popen(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "5%-"])
                return
            elif cmd == "vol_mute":
                subprocess.Popen(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
                return
        except Exception:
            pass

    # 2. pactl (PulseAudio)
    if shutil.which("pactl"):
        try:
            if cmd == "vol_up":
                subprocess.Popen(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"])
                return
            elif cmd == "vol_down":
                subprocess.Popen(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])
                return
            elif cmd == "vol_mute":
                subprocess.Popen(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
                return
        except Exception:
            pass

    # 3. amixer (ALSA)
    if shutil.which("amixer"):
        try:
            if cmd == "vol_up":
                subprocess.Popen(["amixer", "-q", "sset", "Master", "5%+"])
            elif cmd == "vol_down":
                subprocess.Popen(["amixer", "-q", "sset", "Master", "5%-"])
            elif cmd == "vol_mute":
                subprocess.Popen(["amixer", "-q", "sset", "Master", "toggle"])
        except Exception:
            pass

def linux_media_control(cmd):
    """
    Управление воспроизведением медиа (Spotify / плееры) на Linux через playerctl или D-Bus.
    """
    action_map = {
        "play_pause": "play-pause",
        "next": "next",
        "prev": "previous"
    }
    action = action_map.get(cmd)
    if not action:
        return

    if shutil.which("playerctl"):
        try:
            subprocess.Popen(["playerctl", action])
            return
        except Exception:
            pass

    # Fallback на D-Bus через dbus-send
    dbus_method_map = {
        "play-pause": "PlayPause",
        "next": "Next",
        "previous": "Previous"
    }
    method = dbus_method_map.get(action)
    if method and shutil.which("dbus-send"):
        try:
            subprocess.Popen([
                "dbus-send", "--type=method_call",
                "--dest=org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2",
                f"org.mpris.MediaPlayer2.Player.{method}"
            ])
        except Exception:
            pass

def press_media_key(cmd):
    if IS_WINDOWS and user32:
        vk = MEDIA_KEYS.get(cmd)
        if vk:
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
    elif IS_LINUX:
        if cmd in ("vol_mute", "vol_down", "vol_up"):
            linux_volume_control(cmd)
        elif cmd in ("next", "prev", "play_pause"):
            linux_media_control(cmd)

def get_linux_media_track():
    """Чтение текущего трека в Linux через playerctl (Spotify / MPRIS)."""
    if shutil.which("playerctl"):
        try:
            result = subprocess.run(
                ["playerctl", "metadata", "--format", "{{ artist }} - {{ title }}"],
                capture_output=True, text=True, timeout=1.0
            )
            title = result.stdout.strip()
            if title and " - " in title:
                return title
            status_res = subprocess.run(["playerctl", "status"], capture_output=True, text=True, timeout=1.0)
            status = status_res.stdout.strip().lower()
            if status == "paused":
                return "На паузе"
            elif status == "playing":
                return "Воспроизведение"
        except Exception:
            pass
    return "Spotify не запущен"

_cached_spotify_pids = set()
_last_pid_scan_time = 0.0

def get_spotify_track():
    """Чтение трека Spotify (кроссплатформенно: Windows через WinAPI, Linux через playerctl)."""
    if IS_LINUX:
        return get_linux_media_track()
    elif not IS_WINDOWS or not user32:
        return "Spotify не запущен"

    global _cached_spotify_pids, _last_pid_scan_time
    now = time.time()

    alive_pids = {pid for pid in _cached_spotify_pids if psutil.pid_exists(pid)}
    if not alive_pids and (now - _last_pid_scan_time > 6.0):
        _last_pid_scan_time = now
        found = set()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == 'spotify.exe':
                    found.add(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _cached_spotify_pids = found
        alive_pids = found
    else:
        _cached_spotify_pids = alive_pids

    if not alive_pids:
        return "Spotify не запущен"

    found_title = None

    def enum_windows_proc(hwnd, lParam):
        nonlocal found_title
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in alive_pids:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title not in ("Spotify", "Spotify Free", "Spotify Premium") and " - " in title:
                        found_title = title
                        return False
        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    return found_title if found_title else "На паузе"

def collect_system_metrics():
    """Сбор всех метрик в фоновом потоке без блокировки интерфейса (кроссплатформенно)."""
    cpu_usage = round(psutil.cpu_percent(), 1)
    ram_usage = round(psutil.virtual_memory().percent, 1)
    disk_path = '/' if IS_LINUX else 'C:\\'
    disk_usage = round(psutil.disk_usage(disk_path).percent, 1)

    uptime_sec = int(time.time() - psutil.boot_time())
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    uptime_str = f"{hours}ч {minutes}м"

    spotify_now = get_spotify_track()
    return {
        "action": "telemetry",
        "cpu": cpu_usage,
        "ram": ram_usage,
        "disk": disk_usage,
        "uptime": uptime_str,
        "spotify": spotify_now
    }

# --- ПЕРЕХВАТ УВЕДОМЛЕНИЙ LINUX (D-BUS) ---
async def linux_notification_listener_loop():
    """
    Перехват уведомлений на Linux через dbus-monitor (org.freedesktop.Notifications).
    Безопасный: не читает текст сообщений, определяет только факт от Telegram, Discord, Steam.
    Не падает, если dbus-monitor отсутствует.
    """
    if not shutil.which("dbus-monitor"):
        return

    try:
        proc = await asyncio.create_subprocess_exec(
            "dbus-monitor",
            "interface='org.freedesktop.Notifications',member='Notify'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
    except Exception as e:
        print(f"⚠️ Не удалось запустить dbus-monitor: {e}")
        return

    last_trigger = {"telegram": 0.0, "discord": 0.0, "steam": 0.0}

    try:
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore").lower()

            now = time.time()
            detected_app = None
            if "telegram" in line:
                detected_app = "telegram"
            elif "discord" in line:
                detected_app = "discord"
            elif "steam" in line:
                detected_app = "steam"

            if detected_app and (now - last_trigger[detected_app] > 5.0):
                last_trigger[detected_app] = now
                msg = json.dumps({"action": "notification", "app": detected_app})
                if authenticated_phones:
                    await asyncio.gather(
                        *(phone.send(msg) for phone in list(authenticated_phones)),
                        return_exceptions=True
                    )
    except Exception:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass

# --- ОТСЛЕЖИВАНИЕ УВЕДОМЛЕНИЙ WINDOWS ---
async def notification_listener_loop():
    if not WINRT_AVAILABLE:
        return

    try:
        listener = UserNotificationListener.current
        access = await listener.request_access_async()
        if access != UserNotificationListenerAccessStatus.ALLOWED:
            print("⚠️ Доступ к уведомлениям Windows не разрешен в параметрах системы.")
            return
    except Exception as e:
        print(f"⚠️ Не удалось запустить слушатель уведомлений: {e}")
        return

    seen_ids = set()
    try:
        initial = await listener.get_notifications_async(NotificationKinds.TOAST)
        for n in initial:
            seen_ids.add(n.id)
    except Exception:
        pass

    print("🔔 Слушатель знамений (Telegram / Discord / Steam) активен.")

    while True:
        try:
            if authenticated_phones and (
                APP_CONFIG.get("notify_telegram") or
                APP_CONFIG.get("notify_discord") or
                APP_CONFIG.get("notify_steam")
            ):
                notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
                current_ids = set()

                for n in notifications:
                    current_ids.add(n.id)
                    if n.id not in seen_ids:
                        seen_ids.add(n.id)
                        app_name = ""
                        try:
                            app_name = n.app_info.display_info.display_name.lower()
                        except Exception:
                            pass

                        detected_app = None
                        if "telegram" in app_name and APP_CONFIG.get("notify_telegram"):
                            detected_app = "telegram"
                        elif "discord" in app_name and APP_CONFIG.get("notify_discord"):
                            detected_app = "discord"
                        elif "steam" in app_name and APP_CONFIG.get("notify_steam"):
                            detected_app = "steam"

                        if detected_app:
                            msg = json.dumps({"action": "notify", "app": detected_app})
                            await asyncio.gather(
                                *(phone.send(msg) for phone in list(authenticated_phones)),
                                return_exceptions=True
                            )

                seen_ids.intersection_update(current_ids)
        except Exception:
            pass

        await asyncio.sleep(1.5)

# --- АСИНХРОННАЯ ТЕЛЕМЕТРИЯ С ДЕЛЬТА-ОТПРАВКОЙ ---
async def telemetry_loop():
    last_sent_json = None
    last_force_send = 0.0

    while True:
        if authenticated_phones:
            metrics = await asyncio.to_thread(collect_system_metrics)
            payload = json.dumps(metrics, ensure_ascii=False)
            now = time.time()

            # Отправляем только если данные изменились или прошло 10 сек (heartbeat)
            if payload != last_sent_json or (now - last_force_send >= 10.0):
                last_sent_json = payload
                last_force_send = now
                await asyncio.gather(
                    *(phone.send(payload) for phone in list(authenticated_phones)),
                    return_exceptions=True
                )
        else:
            last_sent_json = None

        await asyncio.sleep(2.0)

# --- WEBSOCKET СЕРВЕР ---
async def ws_handler(websocket):
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")

            if action == "auth":
                if str(data.get("pin")) == str(APP_CONFIG["pin"]):
                    authenticated_phones.add(websocket)
                    print("📱 Последователь подключился!")
                    current_theme = APP_CONFIG.get("theme", "cult")
                    current_lang = APP_CONFIG.get("language", "ru")
                    lang_dict = ALL_LANGUAGES.get(current_lang, ALL_LANGUAGES.get("ru", {}))
                    auth_ok_msg = json.dumps({
                        "action": "auth_ok",
                        "theme": current_theme,
                        "lang": current_lang,
                        "translations": lang_dict.get("web", {}),
                        "theme_titles": lang_dict.get("theme_titles", {}).get(current_theme, {})
                    }, ensure_ascii=False)
                    await websocket.send(auth_ok_msg)
                    if current_layout_json:
                        await websocket.send(current_layout_json)
                    # Сразу отправляем свежую телеметрию новому клиенту
                    metrics = await asyncio.to_thread(collect_system_metrics)
                    await websocket.send(json.dumps(metrics, ensure_ascii=False))
                else:
                    await websocket.send(json.dumps({"action": "auth_fail"}))
                    await websocket.close()
                    return

            elif action == "launch" and websocket in authenticated_phones:
                app_id = data.get("id")
                app_path = registered_apps.get(app_id)
                if app_path:
                    launch_application(app_path)

            elif action == "media" and websocket in authenticated_phones:
                cmd = data.get("cmd")
                press_media_key(cmd)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in authenticated_phones:
            authenticated_phones.remove(websocket)

async def run_server():
    print(f"🚀 WebSocket сервер запущен на порту 8765. PIN-код: {APP_CONFIG['pin']}")
    asyncio.create_task(telemetry_loop())
    if IS_WINDOWS:
        asyncio.create_task(notification_listener_loop())
    elif IS_LINUX:
        asyncio.create_task(linux_notification_listener_loop())
    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        await asyncio.Future()

def start_ws_server():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    ws_loop.run_until_complete(run_server())

async def broadcast_message(message):
    if authenticated_phones:
        await asyncio.gather(*(phone.send(message) for phone in list(authenticated_phones)), return_exceptions=True)

# --- МНОГОПОТОЧНЫЙ HTTP СЕРВЕР БЕЗ КЭША ---
class NoCacheHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def translate_path(self, path):
        target = super().translate_path(path)
        if os.path.exists(target):
            return target
        try:
            rel = os.path.relpath(target, BASE_DIR)
            bundled = os.path.join(RESOURCE_DIR, rel)
            if os.path.exists(bundled):
                return bundled
        except Exception:
            pass
        return target

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass

def start_http_server():
    try:
        server_address = ('0.0.0.0', 8080)
        httpd = ThreadingHTTPServer(server_address, NoCacheHTTPRequestHandler)
        print("🌍 Веб-интерфейс доступен на порту 8080")
        httpd.serve_forever()
    except Exception as e:
        print(f"Ошибка веб-сервера: {e}")

# --- КАРТОЧКА ВИДЖЕТА С КЭШЕМ GIF И БЫСТРЫМ ВЫРАВНИВАНИЕМ ---
class CultWidgetCard(QGraphicsRectItem):
    SNAP_DIST = 8

    def __init__(self, w_type, title, value_text, accent_color, width=185, height=90,
                 app_id=None, app_path=None, media_file=None):
        super().__init__(0, 0, width, height)
        self.w_type = w_type
        self.card_title = title
        self.label_text = value_text
        self.accent_color = accent_color
        self.card_w = width
        self.card_h = height
        self.app_id = app_id
        self.app_path = app_path
        self.media_file = media_file
        self.is_resizing = False
        self.movie = None
        self.static_pixmap = None

        # Кэши для исключения лишних вычислений при отрисовке
        self._gif_frame_cache = {}
        self._cached_cache_size = (0, 0)
        self._drag_snap_x = None
        self._drag_snap_y = None
        self._drag_bounds = (640, 360)

        current_theme_id = APP_CONFIG.get("theme", "cult")
        theme_cfg = THEMES.get(current_theme_id, THEMES["cult"])
        accents = theme_cfg.get("accents", {})
        if w_type in accents:
            accent_color = accents[w_type]
            self.accent_color = accent_color

        if w_type == "notify_anchor":
            side = min(width, height)
            self.card_w = side
            self.card_h = side
            self.setBrush(QBrush(QColor(230, 184, 0, 35)))
            self.setPen(QPen(QColor("#e6b800"), 2, Qt.PenStyle.DashLine))
            self.setZValue(100)
        else:
            bg_color = theme_cfg["card_bg"]
            if current_theme_id == "cult":
                if w_type == "spotify": bg_color = "#152119"
                elif w_type == "launcher": bg_color = "#2b1419"
            elif current_theme_id == "stardew":
                if w_type == "launcher": bg_color = "#e6d3a5"
                elif w_type == "spotify": bg_color = "#e8dbb7"
            elif current_theme_id == "twilight":
                if w_type == "launcher": bg_color = "#2a2538"
            self.setBrush(QBrush(QColor(bg_color)))
            self.setPen(QPen(QColor(self.accent_color), 2))
            self.setZValue(1)
        
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        text_color = theme_cfg["card_text"]

        if w_type == "image" and media_file:
            self.pixmap_item = QGraphicsPixmapItem(self)
            self.pixmap_item.setPos(4, 4)
            full_media_path = os.path.join(MEDIA_DIR, media_file)
            if os.path.exists(full_media_path):
                if media_file.lower().endswith(".gif"):
                    self.movie = QMovie(full_media_path)
                    self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
                    self.movie.frameChanged.connect(self.update_gif_frame)
                    self.movie.start()
                else:
                    self.static_pixmap = QPixmap(full_media_path)
        elif w_type == "notify_anchor":
            self.circle_preview = QGraphicsEllipseItem(self)
            self.circle_preview.setPen(QPen(QColor("#e6b800"), 1, Qt.PenStyle.DotLine))
            self.circle_preview.setBrush(QBrush(QColor(230, 184, 0, 25)))
            self.title_item = QGraphicsTextItem("🔔", self)
            self.title_item.setDefaultTextColor(QColor("#e6b800"))
        elif w_type in ("spotify", "volume"):
            self.title_item = QGraphicsTextItem(f"✦ {title}", self)
            self.title_item.setDefaultTextColor(QColor(self.accent_color))
            if w_type == "spotify":
                self.track_item = QGraphicsTextItem("♪ Исполнитель - Трек", self)
                self.track_item.setDefaultTextColor(QColor(text_color))
            
            btn_labels = ["⏮", "⏯", "⏭"] if w_type == "spotify" else ["🔉-", "🔇", "🔊+"]
            self.mini_boxes = []
            self.mini_texts = []
            for lbl in btn_labels:
                box = QGraphicsRectItem(self)
                box_bg = "#d8c49d" if current_theme_id == "stardew" else "#241d24"
                box.setBrush(QBrush(QColor(box_bg)))
                box.setPen(QPen(QColor(self.accent_color), 1))
                txt = QGraphicsTextItem(lbl, box)
                txt.setDefaultTextColor(QColor("#3e2410" if current_theme_id == "stardew" else "#f2ebd9"))
                self.mini_boxes.append(box)
                self.mini_texts.append(txt)
        else:
            self.title_item = QGraphicsTextItem(f"✦ {title}", self)
            self.title_item.setDefaultTextColor(QColor(self.accent_color))
            
            self.val_item = QGraphicsTextItem(value_text, self)
            self.val_item.setDefaultTextColor(QColor(text_color))
            
            if w_type in ("cpu", "ram", "disk"):
                self.bar_bg = QGraphicsRectItem(self)
                bar_bg_color = "#d8c49d" if current_theme_id == "stardew" else "#2e262e"
                self.bar_bg.setBrush(QBrush(QColor(bar_bg_color)))
                self.bar_bg.setPen(QPen(Qt.PenStyle.NoPen))
                
                self.bar_fill = QGraphicsRectItem(self)
                self.bar_fill.setBrush(QBrush(QColor(self.accent_color)))
                self.bar_fill.setPen(QPen(Qt.PenStyle.NoPen))

        self.grip_item = QGraphicsTextItem("◢", self)
        self.grip_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.grip_item.setDefaultTextColor(QColor("#e6b800"))

        self.update_inner_layout()

    def update_theme_style(self, theme_name, lang_name=None):
        if self.w_type == "notify_anchor":
            return
        theme_cfg = THEMES.get(theme_name, THEMES["cult"])
        bg_color = theme_cfg["card_bg"]
        if theme_name == "cult":
            if self.w_type == "spotify": bg_color = "#152119"
            elif self.w_type == "launcher": bg_color = "#2b1419"
        elif theme_name == "stardew":
            if self.w_type == "launcher": bg_color = "#e6d3a5"
            elif self.w_type == "spotify": bg_color = "#e8dbb7"
        elif theme_name == "twilight":
            if self.w_type == "launcher": bg_color = "#2a2538"

        accents = theme_cfg.get("accents", {})
        if self.w_type in accents:
            self.accent_color = accents[self.w_type]

        self.setBrush(QBrush(QColor(bg_color)))
        self.setPen(QPen(QColor(self.accent_color), 2))

        new_title = get_theme_title(self.w_type, theme_name, lang_name)
        if hasattr(self, 'title_item') and self.title_item:
            self.title_item.setPlainText(f"✦ {new_title}")
            self.title_item.setDefaultTextColor(QColor(self.accent_color))

        text_color = theme_cfg["card_text"]
        if hasattr(self, 'val_item') and self.val_item:
            self.val_item.setDefaultTextColor(QColor(text_color))
        if hasattr(self, 'track_item') and self.track_item:
            self.track_item.setDefaultTextColor(QColor(text_color))
        if hasattr(self, 'bar_fill') and self.bar_fill:
            self.bar_fill.setBrush(QBrush(QColor(self.accent_color)))
        if hasattr(self, 'bar_bg') and self.bar_bg:
            self.bar_bg.setBrush(QBrush(QColor("#d8c49d" if theme_name == "stardew" else "#2e262e")))
        if hasattr(self, 'mini_boxes'):
            for box in self.mini_boxes:
                box.setPen(QPen(QColor(self.accent_color), 1))
                box.setBrush(QBrush(QColor("#d8c49d" if theme_name == "stardew" else "#241d24")))
        if hasattr(self, 'mini_texts'):
            for txt in self.mini_texts:
                txt.setDefaultTextColor(QColor("#3e2410" if theme_name == "stardew" else "#f2ebd9"))

    def get_scene_bounds(self):
        if self.scene():
            r = self.scene().sceneRect()
            return int(r.width()), int(r.height())
        return APP_CONFIG["screen_w"], APP_CONFIG["screen_h"]

    def get_other_cards(self):
        if not self.scene():
            return []
        return [
            item for item in self.scene().items()
            if isinstance(item, CultWidgetCard) and item is not self and item.isVisible()
        ]

    def _prepare_snap_cache(self):
        """Предрасчет координат притяжения один раз при захвате карточки."""
        scene_w, scene_h = self.get_scene_bounds()
        self._drag_bounds = (scene_w, scene_h)
        max_x = float(max(0, scene_w - self.card_w))
        max_y = float(max(0, scene_h - self.card_h))

        x_targets = [(0.0, 0.0), (max_x, float(scene_w))]
        y_targets = [(0.0, 0.0), (max_y, float(scene_h))]

        for other in self.get_other_cards():
            ox = float(other.x())
            oy = float(other.y())
            ow = float(other.card_w)
            oh = float(other.card_h)

            x_targets.extend([
                (ox, ox),
                (ox + ow, ox + ow),
                (ox - self.card_w, ox),
                (ox + ow - self.card_w, ox + ow)
            ])
            y_targets.extend([
                (oy, oy),
                (oy + oh, oy + oh),
                (oy - self.card_h, oy),
                (oy + oh - self.card_h, oy + oh)
            ])

        self._drag_snap_x = x_targets
        self._drag_snap_y = y_targets

    def update_gif_frame(self):
        if not (self.movie and hasattr(self, "pixmap_item")):
            return
        target_size = (max(10, self.card_w - 8), max(10, self.card_h - 8))
        if self._cached_cache_size != target_size:
            self._gif_frame_cache.clear()
            self._cached_cache_size = target_size

        frame_num = self.movie.currentFrameNumber()
        scaled = self._gif_frame_cache.get(frame_num)
        if scaled is None:
            pix = self.movie.currentPixmap()
            if pix.isNull():
                return
            scaled = pix.scaled(
                target_size[0], target_size[1],
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._gif_frame_cache[frame_num] = scaled

        self.pixmap_item.setPixmap(scaled)
        ox = (self.card_w - scaled.width()) / 2
        oy = (self.card_h - scaled.height()) / 2
        self.pixmap_item.setPos(ox, oy)

    def update_inner_layout(self):
        self.setRect(0, 0, self.card_w, self.card_h)

        if self.w_type == "image":
            if self.movie:
                self.update_gif_frame()
            elif self.static_pixmap and not self.static_pixmap.isNull():
                scaled = self.static_pixmap.scaled(
                    max(10, self.card_w - 8), max(10, self.card_h - 8),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.pixmap_item.setPixmap(scaled)
                ox = (self.card_w - scaled.width()) / 2
                oy = (self.card_h - scaled.height()) / 2
                self.pixmap_item.setPos(ox, oy)
        elif self.w_type == "notify_anchor":
            self.circle_preview.setRect(4, 4, self.card_w - 8, self.card_h - 8)
            pt = max(12, min(28, int(self.card_h * 0.28)))
            self.title_item.setFont(QFont("Georgia", pt))
            br = self.title_item.boundingRect()
            self.title_item.setPos((self.card_w - br.width()) / 2, (self.card_h - br.height()) / 2)
        elif self.w_type in ("spotify", "volume"):
            title_pt = max(8, min(13, int(self.card_h * 0.11)))
            self.title_item.setFont(QFont("Georgia", title_pt, QFont.Weight.Bold))
            self.title_item.setPos(8, 4)

            if self.w_type == "spotify":
                tr_pt = max(8, min(14, int(self.card_h * 0.12)))
                self.track_item.setFont(QFont("Georgia", tr_pt))
                self.track_item.setPos(8, int(self.card_h * 0.25))
                btn_y = int(self.card_h * 0.52)
            else:
                btn_y = int(self.card_h * 0.36)

            btn_h = max(20, self.card_h - btn_y - 10)
            total_inner_w = max(60, self.card_w - 16)
            gap = 5
            btn_w = max(18, (total_inner_w - gap * 2) / 3.0)
            btn_pt = max(9, min(18, int(btn_h * 0.38)))

            for i, (box, txt) in enumerate(zip(self.mini_boxes, self.mini_texts)):
                bx = 8 + i * (btn_w + gap)
                box.setRect(bx, btn_y, btn_w, btn_h)
                txt.setFont(QFont("Segoe UI Emoji", btn_pt, QFont.Weight.Bold))
                tbr = txt.boundingRect()
                txt.setPos(bx + (btn_w - tbr.width()) / 2, btn_y + (btn_h - tbr.height()) / 2)
        else:
            title_pt = max(8, min(13, int(self.card_h * 0.11)))
            self.title_item.setFont(QFont("Georgia", title_pt, QFont.Weight.Bold))
            self.title_item.setPos(8, 5)

            if self.w_type == "launcher":
                val_pt = max(11, min(24, int(self.card_h * 0.22)))
            else:
                val_pt = max(14, min(36, int(self.card_h * 0.24)))

            self.val_item.setFont(QFont("Georgia", val_pt, QFont.Weight.Bold))
            self.val_item.setPos(8, int(self.card_h * 0.28))

            if self.w_type in ("cpu", "ram", "disk"):
                bar_h = max(6, int(self.card_h * 0.09))
                bar_y = self.card_h - bar_h - 10
                bar_w = max(20, self.card_w - 20)
                self.bar_bg.setRect(10, bar_y, bar_w, bar_h)
                self.bar_fill.setRect(10, bar_y, bar_w * 0.45, bar_h)

        self.grip_item.setPos(self.card_w - 18, self.card_h - 20)

    def mousePressEvent(self, event):
        pos = event.pos()
        if pos.x() >= self.card_w - 20 and pos.y() >= self.card_h - 20:
            self.is_resizing = True
            event.accept()
            return
        self.is_resizing = False
        self._prepare_snap_cache()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_resizing:
            pos = event.pos()
            scene_w, scene_h = self.get_scene_bounds()
            max_w = scene_w - int(self.x())
            max_h = scene_h - int(self.y())

            if self.w_type == "notify_anchor":
                raw_side = max(int(pos.x()), int(pos.y()))
                side = max(45, min(raw_side, max_w, max_h))
                self.card_w = side
                self.card_h = side
            else:
                min_w = 50 if self.w_type == "image" else 110
                min_h = 50 if self.w_type == "image" else 55
                new_w = max(min_w, min(int(pos.x()), max_w))
                new_h = max(min_h, min(int(pos.y()), max_h))

                cur_x, cur_y = int(self.x()), int(self.y())
                for other in self.get_other_cards():
                    ox, oy = int(other.x()), int(other.y())
                    ow, oh = other.card_w, other.card_h
                    if abs((cur_x + new_w) - (ox + ow)) <= 6:
                        new_w = (ox + ow) - cur_x
                    elif abs((cur_x + new_w) - ox) <= 6:
                        new_w = ox - cur_x
                    if abs((cur_y + new_h) - (oy + oh)) <= 6:
                        new_h = (oy + oh) - cur_y
                    elif abs((cur_y + new_h) - oy) <= 6:
                        new_h = oy - cur_y

                self.card_w = max(min_w, min(new_w, max_w))
                self.card_h = max(min_h, min(new_h, max_h))

            self.update_inner_layout()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_snap_x = None
        self._drag_snap_y = None
        if self.is_resizing:
            self.is_resizing = False
            event.accept()
            return
        if self.scene() and hasattr(self.scene(), "clear_guides"):
            self.scene().clear_guides()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == self.GraphicsItemChange.ItemPositionChange:
            if self._drag_snap_x is None:
                self._prepare_snap_cache()

            scene_w, scene_h = self._drag_bounds
            max_x = float(max(0, scene_w - self.card_w))
            max_y = float(max(0, scene_h - self.card_h))

            new_x = max(0.0, min(value.x(), max_x))
            new_y = max(0.0, min(value.y(), max_y))

            snap_x_line = None
            snap_y_line = None

            best_dx = self.SNAP_DIST + 1
            for target_x, guide_x in self._drag_snap_x:
                if 0.0 <= target_x <= max_x:
                    dx = abs(new_x - target_x)
                    if dx < best_dx:
                        best_dx = dx
                        new_x = target_x
                        snap_x_line = guide_x

            best_dy = self.SNAP_DIST + 1
            for target_y, guide_y in self._drag_snap_y:
                if 0.0 <= target_y <= max_y:
                    dy = abs(new_y - target_y)
                    if dy < best_dy:
                        best_dy = dy
                        new_y = target_y
                        snap_y_line = guide_y

            if self.scene() and hasattr(self.scene(), "update_guides"):
                self.scene().update_guides(snap_x_line, snap_y_line)

            return QPointF(new_x, new_y)
        return super().itemChange(change, value)

# --- СЦЕНА С НАПРАВЛЯЮЩИМИ ЛИНИЯМИ ---
class AltarGraphicsScene(QGraphicsScene):
    def __init__(self, x, y, w, h):
        super().__init__(x, y, w, h)
        self.guide_v = None
        self.guide_h = None

    def update_guides(self, x_pos, y_pos):
        self.clear_guides()
        pen = QPen(QColor("#e6b800"), 1, Qt.PenStyle.DashLine)
        r = self.sceneRect()
        if x_pos is not None:
            self.guide_v = self.addLine(x_pos, 0, x_pos, r.height(), pen)
            self.guide_v.setZValue(500)
        if y_pos is not None:
            self.guide_h = self.addLine(0, y_pos, r.width(), y_pos, pen)
            self.guide_h.setZValue(500)

    def clear_guides(self):
        if self.guide_v:
            self.removeItem(self.guide_v)
            self.guide_v = None
        if self.guide_h:
            self.removeItem(self.guide_h)
            self.guide_h = None

# --- ОКНО "О ПРОЕКТЕ" ---
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("about_title"))
        self.setFixedSize(460, 420)
        cur_theme = APP_CONFIG.get("theme", "cult")
        theme_cfg = THEMES.get(cur_theme, THEMES["cult"])
        bg_col = "#120f12" if cur_theme == "cult" else ("#201712" if cur_theme == "stardew" else "#191722")
        border_col = theme_cfg.get("border", "#8a1c1c")
        btn_bg = "#8a1c1c" if cur_theme == "cult" else ("#8c5826" if cur_theme == "stardew" else "#9b72f3")
        text_col = theme_cfg.get("card_text", "#f2ebd9")
        header_col = "#d92b2b" if cur_theme == "cult" else ("#ffd966" if cur_theme == "stardew" else "#f45b84")
        btn_text = "#f2ebd9" if cur_theme != "twilight" else "#ffffff"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_col};
                color: {text_col};
                font-family: Georgia;
                border: 2px solid {border_col};
            }}
            QLabel {{
                color: {text_col};
                font-size: 13px;
                line-height: 1.4;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {header_col};
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(tr("about_heading"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {header_col}; font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        layout.addWidget(title)

        story = QLabel(tr("about_text"))
        story.setWordWrap(True)
        story.setTextFormat(Qt.TextFormat.RichText)
        story.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(story)

        layout.addStretch()

        btn_close = QPushButton(tr("about_close"))
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

# --- ГРАФИЧЕСКИЙ РЕДАКТОР ---
class DashboardEditor(QMainWindow):
    def __init__(self, app_manager=None):
        super().__init__()
        self.app_manager = app_manager
        self.current_ip = get_current_ip()
        
        cur_theme = APP_CONFIG.get("theme", "cult")
        cur_lang = APP_CONFIG.get("language", "ru")
        theme_names = ALL_LANGUAGES.get(cur_lang, {}).get("theme_names", {})
        display_name = theme_names.get(cur_theme, cur_theme.capitalize())
        self.setWindowTitle(f"{tr('app_title')} — {display_name} | PIN: {APP_CONFIG['pin']}")
        
        icon_path = get_resource_path("cult_altar.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet(THEMES.get(cur_theme, THEMES["cult"])["style"])
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        top_bar = QHBoxLayout()
        self.pin_label = QLabel(f"🔑 PIN: {APP_CONFIG['pin']}")
        self.pin_label.setStyleSheet("color: #e6b800; font-size: 14px; font-weight: bold; padding: 4px 8px; border: 1px dashed #8a1c1c;")
        
        self.ip_btn = QPushButton(f"🌐 {self.current_ip}:8080")
        self.ip_btn.setStyleSheet("""
            QPushButton {
                background-color: #12202b; color: #66d9ff; border: 1px solid #1c5270;
                padding: 4px 10px; font-weight: bold; border-radius: 3px; font-size: 13px;
            }
            QPushButton:hover { background-color: #1c3245; border-color: #38a3d6; }
        """)
        self.ip_btn.setToolTip(tr("copy_tooltip"))
        self.ip_btn.clicked.connect(self.copy_ip_link)

        self.btn_qr = QPushButton("📱 QR")
        self.btn_qr.setStyleSheet("""
            QPushButton {
                background-color: #2b1d3a; color: #e6b800; border: 1px solid #9b72f3;
                padding: 4px 10px; font-weight: bold; border-radius: 3px; font-size: 13px;
            }
            QPushButton:hover { background-color: #3b2950; border-color: #d1b3ff; }
        """)
        self.btn_qr.setToolTip(tr("qr_tooltip"))
        self.btn_qr.clicked.connect(self.show_qr_dialog)

        self.res_badge = QLabel(f"📐 {APP_CONFIG['screen_w']}×{APP_CONFIG['screen_h']}")
        self.res_badge.setStyleSheet("color: #b8ad9e; font-size: 13px; padding: 4px 8px;")

        self.btn_about = QPushButton(tr("btn_about"))
        self.btn_about.clicked.connect(self.show_about_dialog)

        self.btn_deploy = QPushButton(tr("btn_deploy"))
        self.btn_deploy.setStyleSheet("background-color: #8a1c1c; color: #f2ebd9; border: 1px solid #e6b800; padding: 7px 14px;")
        self.btn_deploy.clicked.connect(self.deploy_to_phone)
        
        top_bar.addWidget(self.pin_label)
        top_bar.addWidget(self.ip_btn)
        top_bar.addWidget(self.btn_qr)
        top_bar.addWidget(self.res_badge)
        top_bar.addStretch()
        top_bar.addWidget(self.btn_about)
        top_bar.addWidget(self.btn_deploy)
        main_layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_altar = QWidget()
        self.tab_omens = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_altar, tr("tab_altar"))
        self.tabs.addTab(self.tab_omens, tr("tab_omens"))
        self.tabs.addTab(self.tab_settings, tr("tab_settings"))

        self.added_widgets = []
        self.notify_anchor = None

        self.init_altar_tab()
        self.init_omens_tab()
        self.init_settings_tab()

        if os.path.exists(PRESET_FILE):
            self.load_preset(silent=True)
        else:
            self.ensure_notify_anchor()

    def init_altar_tab(self):
        layout = QVBoxLayout(self.tab_altar)

        preset_bar = QHBoxLayout()
        self.btn_save = QPushButton(tr("btn_save_preset"))
        self.btn_save.clicked.connect(self.save_preset)

        self.btn_load = QPushButton(tr("btn_load_preset"))
        self.btn_load.clicked.connect(self.load_preset)

        self.btn_del_sel = QPushButton(tr("btn_del_selected"))
        self.btn_del_sel.setStyleSheet("border-color: #ff6666; color: #ff9999;")
        self.btn_del_sel.clicked.connect(self.delete_selected_widgets)

        self.btn_clear = QPushButton(tr("btn_clear_canvas"))
        self.btn_clear.clicked.connect(self.clear_canvas)

        preset_bar.addWidget(self.btn_save)
        preset_bar.addWidget(self.btn_load)
        preset_bar.addStretch()
        preset_bar.addWidget(self.btn_del_sel)
        preset_bar.addWidget(self.btn_clear)
        layout.addLayout(preset_bar)

        tools_row1 = QHBoxLayout()
        self.btn_clock = QPushButton(tr("w_clock"))
        self.btn_clock.clicked.connect(lambda: self.add_themed_widget("clock", "12:00:00", 195, 75))
        
        self.btn_cpu = QPushButton(tr("w_cpu"))
        self.btn_cpu.clicked.connect(lambda: self.add_themed_widget("cpu", "45%", 175, 88))
        
        self.btn_ram = QPushButton(tr("w_ram"))
        self.btn_ram.clicked.connect(lambda: self.add_themed_widget("ram", "60%", 175, 88))

        self.btn_disk = QPushButton(tr("w_disk"))
        self.btn_disk.clicked.connect(lambda: self.add_themed_widget("disk", "72%", 175, 88))

        self.btn_uptime = QPushButton(tr("w_uptime"))
        self.btn_uptime.clicked.connect(lambda: self.add_themed_widget("uptime", "4ч 15м", 175, 75))

        tools_row1.addWidget(self.btn_clock)
        tools_row1.addWidget(self.btn_cpu)
        tools_row1.addWidget(self.btn_ram)
        tools_row1.addWidget(self.btn_disk)
        tools_row1.addWidget(self.btn_uptime)
        layout.addLayout(tools_row1)

        tools_row2 = QHBoxLayout()
        self.btn_spotify = QPushButton(tr("w_spotify"))
        self.btn_spotify.setStyleSheet("border-color: #1db954; color: #1db954;")
        self.btn_spotify.clicked.connect(lambda: self.add_themed_widget("spotify", "⏮   ⏯   ⏭", 240, 95))

        self.btn_volume = QPushButton(tr("w_volume"))
        self.btn_volume.setStyleSheet("border-color: #ff9933; color: #ff9933;")
        self.btn_volume.clicked.connect(lambda: self.add_themed_widget("volume", "🔉  🔇  🔊", 195, 80))

        self.btn_app = QPushButton(tr("w_launcher"))
        self.btn_app.setStyleSheet("border-color: #e6b800; color: #e6b800;")
        self.btn_app.clicked.connect(self.add_launcher_widget)

        self.btn_img = QPushButton(tr("w_image"))
        self.btn_img.setStyleSheet("border-color: #ff66b3; color: #ff66b3;")
        self.btn_img.clicked.connect(self.add_image_widget)

        tools_row2.addWidget(self.btn_spotify)
        tools_row2.addWidget(self.btn_volume)
        tools_row2.addWidget(self.btn_app)
        tools_row2.addWidget(self.btn_img)
        layout.addLayout(tools_row2)
        
        sw, sh = APP_CONFIG["screen_w"], APP_CONFIG["screen_h"]
        cur_t = APP_CONFIG.get("theme", "cult")
        theme_cfg = THEMES.get(cur_t, THEMES["cult"])
        self.scene = AltarGraphicsScene(0, 0, sw, sh)
        self.scene.setBackgroundBrush(QBrush(QColor(theme_cfg.get("scene_bg", "#161216"))))
        self.border_rect = self.scene.addRect(0, 0, sw, sh, QPen(QColor(theme_cfg.get("border", "#8a1c1c")), 2))
        
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(660, 380)
        layout.addWidget(self.view)

    def add_themed_widget(self, w_type, default_val, width, height):
        cur_t = APP_CONFIG.get("theme", "cult")
        title = get_theme_title(w_type)
        accent = THEMES.get(cur_t, THEMES["cult"]).get("accents", {}).get(w_type, "#e6b800")
        self.add_widget(w_type, title, default_val, accent, width, height)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.tabs.currentWidget() == self.tab_altar:
                self.delete_selected_widgets()
                return
        super().keyPressEvent(event)

    def delete_selected_widgets(self):
        selected = self.scene.selectedItems()
        removed_any = False
        for item in selected:
            if isinstance(item, CultWidgetCard):
                if item.w_type == "notify_anchor":
                    QMessageBox.information(
                        self, tr("tab_omens"),
                        tr("delete_anchor_warning")
                    )
                    continue
                if item.movie:
                    item.movie.stop()
                if item.w_type == "launcher" and item.app_id in registered_apps:
                    del registered_apps[item.app_id]
                self.scene.removeItem(item)
                if item in self.added_widgets:
                    self.added_widgets.remove(item)
                removed_any = True
        self.scene.clear_guides()
        if not removed_any and not selected:
            QMessageBox.information(self, tr("btn_del_selected"), tr("delete_selected_prompt"))

    def ensure_notify_anchor(self, x=None, y=None, w=90, h=90):
        if self.notify_anchor and self.notify_anchor.scene() == self.scene:
            return
        side = min(w, h)
        sw, sh = APP_CONFIG["screen_w"], APP_CONFIG["screen_h"]
        if x is None:
            x = max(0, sw - side - 15)
        if y is None:
            y = 15
        anchor = CultWidgetCard("notify_anchor", "ЗНАМЕНИЕ", "", "#e6b800", width=side, height=side)
        anchor.setPos(x, y)
        self.scene.addItem(anchor)
        self.notify_anchor = anchor
        self.update_anchor_visibility()

    def update_anchor_visibility(self):
        if self.notify_anchor:
            any_enabled = (
                APP_CONFIG.get("notify_telegram") or
                APP_CONFIG.get("notify_discord") or
                APP_CONFIG.get("notify_steam")
            )
            self.notify_anchor.setVisible(bool(any_enabled))

    def init_omens_tab(self):
        layout = QVBoxLayout(self.tab_omens)

        self.omens_info_lbl = QLabel(tr("omens_info"))
        self.omens_info_lbl.setWordWrap(True)
        self.omens_info_lbl.setStyleSheet("color: #b8ad9e; font-size: 13px; padding: 6px;")
        layout.addWidget(self.omens_info_lbl)

        if IS_WINDOWS:
            status_text = tr("omens_status_ok") if WINRT_AVAILABLE else tr("omens_status_no_winrt")
        elif IS_LINUX:
            status_text = tr("omens_status_linux") if shutil.which("dbus-monitor") else "⚠️ dbus-monitor не найден в PATH."
        else:
            status_text = "⚠️ Платформа не поддерживает перехват уведомлений."
        self.omens_status_lbl = QLabel(status_text)
        self.omens_status_lbl.setStyleSheet("color: #e6b800; font-size: 12px; padding: 4px 6px;")
        layout.addWidget(self.omens_status_lbl)

        self.omens_group = QGroupBox(tr("omens_group"))
        g_layout = QVBoxLayout(self.omens_group)

        row_tg = QHBoxLayout()
        self.chk_tg = QCheckBox(tr("omen_tg"))
        self.chk_tg.setChecked(APP_CONFIG.get("notify_telegram", True))
        self.chk_tg.stateChanged.connect(self.on_notify_toggle)
        self.btn_test_tg = QPushButton(tr("btn_test_omen"))
        self.btn_test_tg.clicked.connect(lambda: self.send_test_notification("telegram"))
        row_tg.addWidget(self.chk_tg)
        row_tg.addStretch()
        row_tg.addWidget(self.btn_test_tg)
        g_layout.addLayout(row_tg)

        row_dc = QHBoxLayout()
        self.chk_dc = QCheckBox(tr("omen_dc"))
        self.chk_dc.setChecked(APP_CONFIG.get("notify_discord", True))
        self.chk_dc.stateChanged.connect(self.on_notify_toggle)
        self.btn_test_dc = QPushButton(tr("btn_test_omen"))
        self.btn_test_dc.clicked.connect(lambda: self.send_test_notification("discord"))
        row_dc.addWidget(self.chk_dc)
        row_dc.addStretch()
        row_dc.addWidget(self.btn_test_dc)
        g_layout.addLayout(row_dc)

        row_st = QHBoxLayout()
        self.chk_st = QCheckBox(tr("omen_st"))
        self.chk_st.setChecked(APP_CONFIG.get("notify_steam", True))
        self.chk_st.stateChanged.connect(self.on_notify_toggle)
        self.btn_test_st = QPushButton(tr("btn_test_omen"))
        self.btn_test_st.clicked.connect(lambda: self.send_test_notification("steam"))
        row_st.addWidget(self.chk_st)
        row_st.addStretch()
        row_st.addWidget(self.btn_test_st)
        g_layout.addLayout(row_st)

        layout.addWidget(self.omens_group)
        layout.addStretch()

    def on_notify_toggle(self):
        APP_CONFIG["notify_telegram"] = self.chk_tg.isChecked()
        APP_CONFIG["notify_discord"] = self.chk_dc.isChecked()
        APP_CONFIG["notify_steam"] = self.chk_st.isChecked()
        save_config(APP_CONFIG)
        self.update_anchor_visibility()

    def send_test_notification(self, app_name):
        if not authenticated_phones:
            QMessageBox.warning(self, tr("tab_omens"), tr("omen_no_connection"))
            return
        msg = json.dumps({"action": "notify", "app": app_name})
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(msg), ws_loop)

    def init_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)

        # Язык
        self.lang_group = QGroupBox(tr("sec_lang"))
        lg_layout = QHBoxLayout(self.lang_group)
        self.lbl_lang = QLabel(tr("sec_lang") + ":")
        self.combo_lang = QComboBox()
        self.refresh_lang_combo()
        self.combo_lang.currentIndexChanged.connect(self.on_language_changed)
        lg_layout.addWidget(self.lbl_lang)
        lg_layout.addWidget(self.combo_lang, stretch=1)
        layout.addWidget(self.lang_group)

        # Тема
        self.theme_group = QGroupBox(tr("sec_theme"))
        tg_layout = QHBoxLayout(self.theme_group)
        self.lbl_theme = QLabel(tr("sec_theme") + ":")
        self.combo_theme = QComboBox()
        self.refresh_theme_combo()
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        tg_layout.addWidget(self.lbl_theme)
        tg_layout.addWidget(self.combo_theme, stretch=1)
        layout.addWidget(self.theme_group)

        # Размер экрана
        self.screen_group = QGroupBox(tr("sec_canvas"))
        sg_layout = QVBoxLayout(self.screen_group)

        preset_row = QHBoxLayout()
        self.lbl_preset = QLabel(tr("lbl_profile"))
        preset_row.addWidget(self.lbl_preset)
        self.combo_presets = QComboBox()
        self.refresh_presets_combo()
        self.combo_presets.currentIndexChanged.connect(self.on_preset_selected)
        preset_row.addWidget(self.combo_presets)
        sg_layout.addLayout(preset_row)

        custom_row = QHBoxLayout()
        self.lbl_w = QLabel(tr("lbl_width"))
        custom_row.addWidget(self.lbl_w)
        self.spin_w = QSpinBox()
        self.spin_w.setRange(240, 1920)
        self.spin_w.setValue(APP_CONFIG["screen_w"])
        custom_row.addWidget(self.spin_w)

        self.lbl_h = QLabel(tr("lbl_height"))
        custom_row.addWidget(self.lbl_h)
        self.spin_h = QSpinBox()
        self.spin_h.setRange(240, 1920)
        self.spin_h.setValue(APP_CONFIG["screen_h"])
        custom_row.addWidget(self.spin_h)

        self.btn_apply_res = QPushButton(tr("btn_apply_res"))
        self.btn_apply_res.setStyleSheet("border-color: #e6b800; color: #e6b800;")
        self.btn_apply_res.clicked.connect(self.apply_screen_size)
        custom_row.addWidget(self.btn_apply_res)
        sg_layout.addLayout(custom_row)

        layout.addWidget(self.screen_group)

        # Сетевой адаптер (IP)
        self.net_group = QGroupBox(tr("sec_net"))
        ng_layout = QVBoxLayout(self.net_group)
        
        net_row = QHBoxLayout()
        self.lbl_adapter = QLabel(tr("lbl_adapter"))
        net_row.addWidget(self.lbl_adapter)
        self.combo_ip = QComboBox()
        self.refresh_ip_combo()
        self.combo_ip.currentIndexChanged.connect(self.on_ip_selected)
        net_row.addWidget(self.combo_ip, stretch=1)

        self.btn_refresh_ips = QPushButton(tr("btn_refresh"))
        self.btn_refresh_ips.setToolTip(tr("refresh_ip_tooltip"))
        self.btn_refresh_ips.clicked.connect(self.refresh_ip_combo)
        net_row.addWidget(self.btn_refresh_ips)
        ng_layout.addLayout(net_row)

        self.lbl_ip_hint = QLabel(tr("lbl_adapter_hint"))
        self.lbl_ip_hint.setStyleSheet("color: #b8ad9e; font-size: 12px;")
        ng_layout.addWidget(self.lbl_ip_hint)
        layout.addWidget(self.net_group)

        # Автозапуск: Windows (реестр) / Linux (systemd --user)
        self.auto_group = QGroupBox(tr("sec_autostart_linux") if IS_LINUX else tr("sec_autostart"))
        ag_layout = QHBoxLayout(self.auto_group)
        self.ag_lbl = QLabel(tr("autostart_linux_lbl") if IS_LINUX else tr("autostart_lbl"))
        self.ag_lbl.setWordWrap(True)
        self.btn_autostart = QPushButton()
        self.btn_autostart.clicked.connect(self.toggle_autostart)
        self.refresh_autostart_button()
        ag_layout.addWidget(self.ag_lbl)
        ag_layout.addWidget(self.btn_autostart)
        layout.addWidget(self.auto_group)

        # Интеграция со Steam Deck / Steam Gaming Mode (shortcuts.vdf)
        self.steam_group = QGroupBox(tr("sec_steam"))
        sg_steam_layout = QVBoxLayout(self.steam_group)
        self.lbl_steam_hint = QLabel(tr("steam_lbl"))
        self.lbl_steam_hint.setStyleSheet("color: #b8ad9e; font-size: 12px;")
        self.lbl_steam_hint.setWordWrap(True)
        sg_steam_layout.addWidget(self.lbl_steam_hint)

        self.btn_steam = QPushButton(tr("btn_add_to_steam"))
        self.btn_steam.setStyleSheet("background-color: #171a21; border-color: #66c0f4; color: #66c0f4; font-weight: bold; padding: 8px 14px;")
        self.btn_steam.clicked.connect(self.on_add_to_steam_clicked)
        sg_steam_layout.addWidget(self.btn_steam)
        layout.addWidget(self.steam_group)

        self.pin_group = QGroupBox(tr("sec_pin"))
        pg_layout = QHBoxLayout(self.pin_group)
        self.settings_pin_lbl = QLabel(f"{tr('pin_current')} {APP_CONFIG['pin']}")
        self.settings_pin_lbl.setStyleSheet("font-size: 14px; color: #e6b800; font-weight: bold;")
        self.btn_regen_pin = QPushButton(tr("btn_regen_pin"))
        self.btn_regen_pin.clicked.connect(self.regenerate_pin)
        pg_layout.addWidget(self.settings_pin_lbl)
        pg_layout.addStretch()
        pg_layout.addWidget(self.btn_regen_pin)
        layout.addWidget(self.pin_group)

        layout.addStretch()

    def refresh_lang_combo(self):
        self.combo_lang.blockSignals(True)
        self.combo_lang.clear()
        cur_lang = APP_CONFIG.get("language", "ru")
        sel_idx = 0
        i = 0
        for code, info in ALL_LANGUAGES.items():
            name = info.get("name", code)
            self.combo_lang.addItem(f"{name} ({code})", code)
            if code == cur_lang:
                sel_idx = i
            i += 1
        self.combo_lang.setCurrentIndex(sel_idx)
        self.combo_lang.blockSignals(False)

    def refresh_theme_combo(self):
        self.combo_theme.blockSignals(True)
        self.combo_theme.clear()
        cur_theme = APP_CONFIG.get("theme", "cult")
        cur_lang = APP_CONFIG.get("language", "ru")
        theme_names = ALL_LANGUAGES.get(cur_lang, {}).get("theme_names", {})
        sel_idx = 0
        for i, t_key in enumerate(["cult", "stardew", "twilight"]):
            display_name = theme_names.get(t_key, THEMES.get(t_key, {}).get("id", t_key).capitalize())
            self.combo_theme.addItem(display_name, t_key)
            if t_key == cur_theme:
                sel_idx = i
        self.combo_theme.setCurrentIndex(sel_idx)
        self.combo_theme.blockSignals(False)

    def refresh_presets_combo(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        self.combo_presets.addItem(tr("profile_phone_h"), (640, 360))
        self.combo_presets.addItem(tr("profile_phone_v"), (360, 640))
        self.combo_presets.addItem(tr("profile_phone_wide"), (800, 360))
        self.combo_presets.addItem(tr("profile_tablet_h"), (1024, 600))
        self.combo_presets.addItem(tr("profile_tablet_v"), (600, 1024))
        self.combo_presets.blockSignals(False)

    def on_language_changed(self):
        new_lang = self.combo_lang.currentData()
        if not new_lang or new_lang == APP_CONFIG.get("language"):
            return
        APP_CONFIG["language"] = new_lang
        save_config(APP_CONFIG)
        self.retranslate_ui()
        lang_dict = ALL_LANGUAGES.get(new_lang, ALL_LANGUAGES.get("ru", {}))
        theme = APP_CONFIG.get("theme", "cult")
        theme_titles = lang_dict.get("theme_titles", {}).get(theme, {})
        web_trans = lang_dict.get("web", {})
        msg = json.dumps({
            "action": "set_language",
            "lang": new_lang,
            "translations": web_trans,
            "theme_titles": theme_titles
        }, ensure_ascii=False)
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(msg), ws_loop)

    def on_theme_changed(self):
        new_theme = self.combo_theme.currentData()
        if not new_theme or new_theme == APP_CONFIG.get("theme"):
            return
        APP_CONFIG["theme"] = new_theme
        save_config(APP_CONFIG)
        self.apply_theme(new_theme)
        lang_code = APP_CONFIG.get("language", "ru")
        lang_dict = ALL_LANGUAGES.get(lang_code, ALL_LANGUAGES.get("ru", {}))
        theme_titles = lang_dict.get("theme_titles", {}).get(new_theme, {})
        msg = json.dumps({
            "action": "set_theme",
            "theme": new_theme,
            "theme_titles": theme_titles
        }, ensure_ascii=False)
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(msg), ws_loop)

    def apply_theme(self, theme_code):
        theme_cfg = THEMES.get(theme_code, THEMES["cult"])
        self.setStyleSheet(theme_cfg["style"])
        if hasattr(self, 'scene') and self.scene:
            self.scene.setBackgroundBrush(QBrush(QColor(theme_cfg.get("scene_bg", "#161216"))))
        if hasattr(self, 'border_rect') and self.border_rect:
            self.border_rect.setPen(QPen(QColor(theme_cfg.get("border", "#8a1c1c")), 2))
        
        cur_lang = APP_CONFIG.get("language", "ru")
        theme_names = ALL_LANGUAGES.get(cur_lang, {}).get("theme_names", {})
        display_name = theme_names.get(theme_code, theme_code.capitalize())
        self.setWindowTitle(f"{tr('app_title')} — {display_name} | PIN: {APP_CONFIG['pin']}")

        for card in self.added_widgets:
            card.update_theme_style(theme_code, cur_lang)

    def retranslate_ui(self):
        cur_lang = APP_CONFIG.get("language", "ru")
        cur_theme = APP_CONFIG.get("theme", "cult")
        theme_names = ALL_LANGUAGES.get(cur_lang, {}).get("theme_names", {})
        display_name = theme_names.get(cur_theme, cur_theme.capitalize())
        self.setWindowTitle(f"{tr('app_title')} — {display_name} | PIN: {APP_CONFIG['pin']}")

        self.tabs.setTabText(0, tr("tab_altar"))
        self.tabs.setTabText(1, tr("tab_omens"))
        self.tabs.setTabText(2, tr("tab_settings"))

        self.ip_btn.setToolTip(tr("copy_tooltip"))
        self.btn_qr.setToolTip(tr("qr_tooltip"))
        self.btn_about.setText(tr("btn_about"))
        self.btn_deploy.setText(tr("btn_deploy"))

        self.btn_save.setText(tr("btn_save_preset"))
        self.btn_load.setText(tr("btn_load_preset"))
        self.btn_del_sel.setText(tr("btn_del_selected"))
        self.btn_clear.setText(tr("btn_clear_canvas"))
        self.btn_clock.setText(tr("w_clock"))
        self.btn_cpu.setText(tr("w_cpu"))
        self.btn_ram.setText(tr("w_ram"))
        self.btn_disk.setText(tr("w_disk"))
        self.btn_uptime.setText(tr("w_uptime"))
        self.btn_spotify.setText(tr("w_spotify"))
        self.btn_volume.setText(tr("w_volume"))
        self.btn_app.setText(tr("w_launcher"))
        self.btn_img.setText(tr("w_image"))

        self.omens_info_lbl.setText(tr("omens_info"))
        if IS_WINDOWS:
            self.omens_status_lbl.setText(tr("omens_status_ok") if WINRT_AVAILABLE else tr("omens_status_no_winrt"))
        elif IS_LINUX:
            self.omens_status_lbl.setText(tr("omens_status_linux") if shutil.which("dbus-monitor") else "⚠️ dbus-monitor не найден в PATH.")
        else:
            self.omens_status_lbl.setText("⚠️ Платформа не поддерживает перехват уведомлений.")
        self.omens_group.setTitle(tr("omens_group"))
        self.chk_tg.setText(tr("omen_tg"))
        self.chk_dc.setText(tr("omen_dc"))
        self.chk_st.setText(tr("omen_st"))
        self.btn_test_tg.setText(tr("btn_test_omen"))
        self.btn_test_dc.setText(tr("btn_test_omen"))
        self.btn_test_st.setText(tr("btn_test_omen"))

        self.lang_group.setTitle(tr("sec_lang"))
        self.lbl_lang.setText(tr("sec_lang") + ":")
        self.theme_group.setTitle(tr("sec_theme"))
        self.lbl_theme.setText(tr("sec_theme") + ":")
        self.refresh_theme_combo()

        self.screen_group.setTitle(tr("sec_canvas"))
        self.lbl_preset.setText(tr("lbl_profile"))
        self.refresh_presets_combo()
        self.lbl_w.setText(tr("lbl_width"))
        self.lbl_h.setText(tr("lbl_height"))
        self.btn_apply_res.setText(tr("btn_apply_res"))

        self.net_group.setTitle(tr("sec_net"))
        self.lbl_adapter.setText(tr("lbl_adapter"))
        self.btn_refresh_ips.setText(tr("btn_refresh"))
        self.btn_refresh_ips.setToolTip(tr("refresh_ip_tooltip"))
        self.lbl_ip_hint.setText(tr("lbl_adapter_hint"))
        self.refresh_ip_combo()

        self.auto_group.setTitle(tr("sec_autostart_linux") if IS_LINUX else tr("sec_autostart"))
        self.ag_lbl.setText(tr("autostart_linux_lbl") if IS_LINUX else tr("autostart_lbl"))
        self.refresh_autostart_button()

        if hasattr(self, 'steam_group'):
            self.steam_group.setTitle(tr("sec_steam"))
            self.lbl_steam_hint.setText(tr("steam_lbl"))
            self.btn_steam.setText(tr("btn_add_to_steam"))

        self.pin_group.setTitle(tr("sec_pin"))
        self.settings_pin_lbl.setText(f"{tr('pin_current')} {APP_CONFIG['pin']}")
        self.btn_regen_pin.setText(tr("btn_regen_pin"))

        for card in self.added_widgets:
            card.update_theme_style(cur_theme, cur_lang)

        if self.app_manager:
            self.app_manager.update_tray_texts()

    def refresh_ip_combo(self):
        self.combo_ip.blockSignals(True)
        self.combo_ip.clear()
        adapters = get_network_adapters()
        selected_ip = APP_CONFIG.get("selected_ip")
        
        idx_to_select = 0
        for i, a in enumerate(adapters):
            label = f"{a['name']} ({a['ip']})"
            if a['is_primary'] and not a['is_virtual']:
                label += f" [{tr('ip_primary')}]"
            elif a['is_virtual']:
                label += f" [{tr('ip_virtual')}]"
            self.combo_ip.addItem(label, a['ip'])
            if selected_ip and a['ip'] == selected_ip:
                idx_to_select = i
            elif not selected_ip and a['is_primary'] and not a['is_virtual']:
                idx_to_select = i

        if self.combo_ip.count() > 0:
            self.combo_ip.setCurrentIndex(idx_to_select)
        self.combo_ip.blockSignals(False)

    def on_ip_selected(self):
        chosen_ip = self.combo_ip.currentData()
        if chosen_ip:
            APP_CONFIG["selected_ip"] = chosen_ip
            save_config(APP_CONFIG)
            self.current_ip = chosen_ip
            self.update_ip_button()
            if self.app_manager:
                self.app_manager.update_tray_tooltip()
                self.app_manager.update_tray_info_action()

    def update_ip_button(self):
        if hasattr(self, 'ip_btn'):
            self.ip_btn.setText(f"🌐 {self.current_ip}:8080")

    def copy_ip_link(self):
        url = f"http://{self.current_ip}:8080"
        QApplication.clipboard().setText(url)
        self.ip_btn.setText(tr("btn_copied"))
        QTimer.singleShot(1500, self.update_ip_button)

    def show_qr_dialog(self):
        dlg = QRCodeDialog(self, self.current_ip, APP_CONFIG["pin"])
        dlg.exec()

    def closeEvent(self, event):
        if self.app_manager and self.app_manager.has_tray():
            event.ignore()
            self.app_manager.minimize_editor()
        else:
            event.accept()

    def save_preset_silent(self):
        data = self.build_layout_list()
        try:
            with open(PRESET_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка фонового сохранения пресета: {e}")

    def cleanup_for_tray(self):
        for card in self.added_widgets:
            if card.movie:
                try:
                    card.movie.stop()
                    card.movie.deleteLater()
                except Exception:
                    pass
                card.movie = None
        self.scene.clear()

    def on_preset_selected(self):
        dims = self.combo_presets.currentData()
        if dims:
            self.spin_w.setValue(dims[0])
            self.spin_h.setValue(dims[1])

    def apply_screen_size(self):
        new_w = self.spin_w.value()
        new_h = self.spin_h.value()
        APP_CONFIG["screen_w"] = new_w
        APP_CONFIG["screen_h"] = new_h
        save_config(APP_CONFIG)

        self.scene.setSceneRect(0, 0, new_w, new_h)
        self.border_rect.setRect(0, 0, new_w, new_h)
        self.res_badge.setText(f"📐 {new_w}×{new_h}")

        all_items = list(self.added_widgets)
        if self.notify_anchor:
            all_items.append(self.notify_anchor)
        for item in all_items:
            clamped_x = max(0.0, min(item.x(), float(max(0, new_w - item.card_w))))
            clamped_y = max(0.0, min(item.y(), float(max(0, new_h - item.card_h))))
            item.setPos(clamped_x, clamped_y)

        QMessageBox.information(self, tr("canvas_updated_title"), tr("canvas_updated_text", w=new_w, h=new_h))

    def refresh_autostart_button(self):
        if is_autostart_enabled():
            txt = tr("autostart_linux_on") if IS_LINUX else tr("autostart_on")
            self.btn_autostart.setText(txt)
            self.btn_autostart.setStyleSheet("background-color: #152b1b; border-color: #1db954; color: #1db954; padding: 8px 12px;")
        else:
            txt = tr("autostart_linux_off") if IS_LINUX else tr("autostart_off")
            self.btn_autostart.setText(txt)
            self.btn_autostart.setStyleSheet("background-color: #241d24; border-color: #e6b800; color: #e6b800; padding: 8px 12px;")

    def toggle_autostart(self):
        currently_on = is_autostart_enabled()
        success = set_autostart(not currently_on)
        title = tr("sec_autostart_linux") if IS_LINUX else tr("sec_autostart")
        if success:
            self.refresh_autostart_button()
            if IS_LINUX:
                msg = tr("autostart_linux_off") if currently_on else tr("autostart_linux_on")
            else:
                msg = tr("autostart_off") if currently_on else tr("autostart_on")
            QMessageBox.information(self, title, msg)
        else:
            err = "Не удалось изменить параметры службы systemd." if IS_LINUX else "Не удалось изменить параметры реестра Windows."
            QMessageBox.warning(self, title, err)

    def on_add_to_steam_clicked(self):
        ok, res = add_to_steam_gaming_mode()
        if ok:
            QMessageBox.information(self, tr("steam_added_title"), tr("steam_added_text"))
        else:
            if res == "steam_not_found":
                QMessageBox.warning(self, tr("steam_not_found_title"), tr("steam_not_found_text"))
            else:
                QMessageBox.warning(self, tr("steam_not_found_title"), f"Ошибка сохранения shortcuts.vdf: {res}")

    def regenerate_pin(self):
        new_pin = str(random.randint(1000, 9999))
        APP_CONFIG["pin"] = new_pin
        save_config(APP_CONFIG)
        self.pin_label.setText(f"🔑 PIN: {new_pin}")
        self.settings_pin_lbl.setText(f"{tr('pin_current')} {new_pin}")
        cur_t = APP_CONFIG.get("theme", "cult")
        cur_l = APP_CONFIG.get("language", "ru")
        display_name = ALL_LANGUAGES.get(cur_l, {}).get("theme_names", {}).get(cur_t, cur_t.capitalize())
        self.setWindowTitle(f"{tr('app_title')} — {display_name} | PIN: {new_pin}")
        if self.app_manager:
            self.app_manager.update_tray_tooltip()
            self.app_manager.update_tray_info_action()
        QMessageBox.information(self, tr("btn_regen_pin"), f"{tr('pin_current')} {new_pin}")

    def add_widget(self, w_type, title, default_text, color, width, height,
                   x=40, y=40, app_id=None, app_path=None, media_file=None):
        card = CultWidgetCard(w_type, title, default_text, color, width, height, app_id, app_path, media_file)
        card.setPos(x, y)
        self.scene.addItem(card)
        self.added_widgets.append(card)

    def add_launcher_widget(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("w_launcher"), "", "Все файлы (*.*)"
        )
        if not file_path:
            return
            
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        label, ok = QInputDialog.getText(
            self, tr("launcher_dialog_title"), tr("launcher_dialog_text"), text=default_name
        )
        if not ok or not label.strip():
            return

        app_id = f"app_{random.randint(10000, 99999)}"
        registered_apps[app_id] = file_path

        cur_t = APP_CONFIG.get("theme", "cult")
        accent = THEMES.get(cur_t, THEMES["cult"]).get("accents", {}).get("launcher", "#e6b800")
        title = get_theme_title("launcher")
        self.add_widget(
            "launcher", title, label.strip(), accent, 
            width=190, height=70, app_id=app_id, app_path=file_path
        )

    def add_image_widget(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("w_image"), "", tr("image_dialog_filter")
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        new_filename = f"art_{random.randint(10000, 99999)}{ext}"
        dest_path = os.path.join(MEDIA_DIR, new_filename)
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.warning(self, tr("w_image"), tr("image_copy_error", err=str(e)))
            return

        cur_t = APP_CONFIG.get("theme", "cult")
        accent = THEMES.get(cur_t, THEMES["cult"]).get("accents", {}).get("launcher", "#8a1c1c")
        self.add_widget(
            "image", "ИКОНА", "", accent,
            width=140, height=140, media_file=new_filename
        )

    def clear_canvas(self):
        for card in self.added_widgets:
            if card.movie:
                try:
                    card.movie.stop()
                    card.movie.deleteLater()
                except Exception:
                    pass
                card.movie = None
            self.scene.removeItem(card)
        self.added_widgets.clear()
        registered_apps.clear()
        self.scene.clear_guides()

    def build_layout_list(self):
        layout_data = []
        for card in self.added_widgets:
            item_info = {
                "type": card.w_type,
                "title": card.card_title,
                "label": card.label_text,
                "color": card.accent_color,
                "w": card.card_w,
                "h": card.card_h,
                "x": int(card.x()),
                "y": int(card.y())
            }
            if card.w_type == "launcher":
                item_info["id"] = card.app_id
                item_info["path"] = card.app_path
            elif card.w_type == "image":
                item_info["file"] = card.media_file
            layout_data.append(item_info)

        if self.notify_anchor:
            side = min(self.notify_anchor.card_w, self.notify_anchor.card_h)
            layout_data.append({
                "type": "notify_anchor",
                "w": side,
                "h": side,
                "x": int(self.notify_anchor.x()),
                "y": int(self.notify_anchor.y())
            })
        return layout_data

    def make_layout_packet(self, layout_data):
        current_theme = APP_CONFIG.get("theme", "cult")
        current_lang = APP_CONFIG.get("language", "ru")
        lang_dict = ALL_LANGUAGES.get(current_lang, ALL_LANGUAGES.get("ru", {}))
        return json.dumps({
            "action": "update_layout",
            "screen_w": APP_CONFIG["screen_w"],
            "screen_h": APP_CONFIG["screen_h"],
            "theme": current_theme,
            "theme_titles": lang_dict.get("theme_titles", {}).get(current_theme, {}),
            "widgets": layout_data
        }, ensure_ascii=False)

    def save_preset(self):
        data = self.build_layout_list()
        try:
            with open(PRESET_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, tr("preset_saved_title"), tr("preset_saved_text", file=PRESET_FILE))
        except Exception as e:
            QMessageBox.warning(self, tr("app_title"), f"Не удалось сохранить: {e}")

    def load_preset(self, silent=False):
        if not os.path.exists(PRESET_FILE):
            if not silent:
                QMessageBox.warning(self, tr("preset_empty_title"), tr("preset_empty_text"))
            return
        try:
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clear_canvas()
            anchor_found = False

            cur_t = APP_CONFIG.get("theme", "cult")
            cur_l = APP_CONFIG.get("language", "ru")

            for item in data:
                if item["type"] == "notify_anchor":
                    if self.notify_anchor:
                        self.scene.removeItem(self.notify_anchor)
                        self.notify_anchor = None
                    self.ensure_notify_anchor(item["x"], item["y"], item["w"], item["h"])
                    anchor_found = True
                    continue

                app_id = item.get("id")
                app_path = item.get("path")
                media_file = item.get("file")
                if item["type"] == "launcher" and app_id and app_path:
                    registered_apps[app_id] = app_path

                card_title = get_theme_title(item["type"], cur_t, cur_l) if item["type"] != "image" else item["title"]
                self.add_widget(
                    item["type"], card_title, item["label"], item["color"],
                    item["w"], item["h"], item["x"], item["y"], app_id, app_path, media_file
                )

            if not anchor_found:
                self.ensure_notify_anchor()

            global current_layout_json
            current_layout_json = self.make_layout_packet(data)
            if not silent:
                QMessageBox.information(self, tr("preset_loaded_title"), tr("preset_loaded_text"))
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, tr("app_title"), f"Сбой загрузки: {e}")

    def deploy_to_phone(self):
        global current_layout_json
        layout_data = self.build_layout_list()
        current_layout_json = self.make_layout_packet(layout_data)
        
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(current_layout_json), ws_loop)
            QMessageBox.information(self, tr("ritual_complete_title"), tr("ritual_complete_text"))
        else:
            QMessageBox.warning(self, tr("app_title"), tr("server_not_running"))

    def show_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

# --- СИСТЕМНЫЙ ТРЕЙ И УПРАВЛЕНИЕ ЖИЗНЕННЫМ ЦИКЛОМ (RAM ОПТИМИЗАЦИЯ) ---
class AppManager:
    def __init__(self, q_app):
        self.app = q_app
        self.editor = None
        self.tray_icon = None
        self.info_action = None
        self.action_qr = None
        self.action_open = None
        self.action_exit = None
        self.has_shown_tray_bubble = False
        self.init_tray()

    def has_tray(self):
        return self.tray_icon is not None and self.tray_icon.isVisible()

    def init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = get_resource_path("cult_altar.ico")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.tray_icon = QSystemTrayIcon(icon, self.app)
        self.update_tray_tooltip()

        self.tray_menu = QMenu()
        self.apply_tray_theme()

        self.info_action = QAction("", self.tray_menu)
        self.info_action.setEnabled(False)
        self.tray_menu.addAction(self.info_action)
        self.update_tray_info_action()

        self.action_qr = QAction(tr("tray_qr"), self.tray_menu)
        self.action_qr.triggered.connect(self.show_qr_from_tray)
        self.tray_menu.addAction(self.action_qr)

        self.tray_menu.addSeparator()

        self.action_open = QAction(tr("tray_open"), self.tray_menu)
        self.action_open.triggered.connect(self.show_editor)
        self.tray_menu.addAction(self.action_open)

        self.tray_menu.addSeparator()

        self.action_exit = QAction(tr("tray_close"), self.tray_menu)
        self.action_exit.triggered.connect(self.exit_app)
        self.tray_menu.addAction(self.action_exit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def apply_tray_theme(self):
        if not hasattr(self, 'tray_menu') or not self.tray_menu:
            return
        cur_t = APP_CONFIG.get("theme", "cult")
        if cur_t == "stardew":
            self.tray_menu.setStyleSheet("""
                QMenu { background-color: #201712; color: #f7ebd2; border: 1px solid #8c5826; font-family: Georgia; }
                QMenu::item { padding: 6px 20px 6px 12px; }
                QMenu::item:selected { background-color: #442a17; color: #ffd966; }
                QMenu::item:disabled { color: #8a7e72; }
                QMenu::separator { height: 1px; background-color: #5a381b; margin: 4px 0; }
            """)
        elif cur_t == "twilight":
            self.tray_menu.setStyleSheet("""
                QMenu { background-color: #191722; color: #e6e4f0; border: 1px solid #3b354d; font-family: sans-serif; }
                QMenu::item { padding: 6px 20px 6px 12px; }
                QMenu::item:selected { background-color: #2e2a3d; color: #9b72f3; }
                QMenu::item:disabled { color: #6a6480; }
                QMenu::separator { height: 1px; background-color: #322d42; margin: 4px 0; }
            """)
        else:
            self.tray_menu.setStyleSheet("""
                QMenu { background-color: #1c171c; color: #f2ebd9; border: 1px solid #8a1c1c; font-family: Georgia; }
                QMenu::item { padding: 6px 20px 6px 12px; }
                QMenu::item:selected { background-color: #38252b; color: #e6b800; }
                QMenu::item:disabled { color: #8a7e72; }
                QMenu::separator { height: 1px; background-color: #4a151b; margin: 4px 0; }
            """)

    def update_tray_texts(self):
        self.apply_tray_theme()
        if self.action_qr:
            self.action_qr.setText(tr("tray_qr"))
        if self.action_open:
            self.action_open.setText(tr("tray_open"))
        if self.action_exit:
            self.action_exit.setText(tr("tray_close"))
        self.update_tray_tooltip()
        self.update_tray_info_action()

    def update_tray_info_action(self):
        if self.info_action:
            ip = get_current_ip()
            pin = APP_CONFIG.get("pin", "")
            self.info_action.setText(f"🌐 {ip}:8080 | PIN: {pin}")

    def update_tray_tooltip(self):
        if self.tray_icon:
            ip = get_current_ip()
            pin = APP_CONFIG.get("pin", "")
            self.tray_icon.setToolTip(f"{tr('app_title')}\nhttp://{ip}:8080 | PIN: {pin}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Левый клик по иконке трея
            if self.editor and self.editor.isVisible():
                self.minimize_editor()
            else:
                self.show_editor()

    def show_editor(self):
        self.update_tray_info_action()
        self.update_tray_tooltip()
        if self.editor is None:
            self.editor = DashboardEditor(self)
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()

    def minimize_editor(self):
        if self.editor:
            self.editor.save_preset_silent()
            self.editor.cleanup_for_tray()
            self.editor.deleteLater()
            self.editor = None
            gc.collect()

        if self.tray_icon and not self.has_shown_tray_bubble:
            self.tray_icon.showMessage(
                tr("tray_bubble_title"),
                tr("tray_bubble_text"),
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
            self.has_shown_tray_bubble = True

    def show_qr_from_tray(self):
        ip = get_current_ip()
        pin = APP_CONFIG.get("pin", "")
        dlg = QRCodeDialog(None, ip, pin)
        dlg.exec()

    def exit_app(self):
        if self.editor:
            self.editor.cleanup_for_tray()
            self.editor.close()
            self.editor = None
        if self.tray_icon:
            self.tray_icon.hide()
        self.app.quit()

if __name__ == '__main__':
    # Поддержка фонового запуска без GUI (для systemd / Steam Deck Gaming Mode)
    if "--headless" in sys.argv or "--server-only" in sys.argv:
        print("🕯️ Запуск Cult Altar Dashboard в фоновом режиме (Headless Server)...")
        threading.Thread(target=start_http_server, daemon=True).start()
        start_ws_server()
        sys.exit(0)

    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=start_ws_server, daemon=True).start()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    app_manager = AppManager(app)
    app_manager.show_editor()
    
    sys.exit(app.exec())