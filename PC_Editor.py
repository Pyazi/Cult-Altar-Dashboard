import sys
import os
import shutil
import time
import json
import random
import ctypes
import winreg
import asyncio
import websockets
import threading
import psutil
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from PyQt6.QtWidgets import (QApplication, QMainWindow, QGraphicsScene, 
                             QGraphicsView, QGraphicsRectItem, QGraphicsTextItem,
                             QGraphicsPixmapItem, QGraphicsEllipseItem,
                             QPushButton, QVBoxLayout, QHBoxLayout, QWidget, 
                             QMessageBox, QLabel, QFileDialog, QInputDialog, 
                             QTabWidget, QCheckBox, QComboBox, QSpinBox, 
                             QGroupBox, QDialog)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QFont, QPen, QColor, QBrush, QPixmap, QMovie, QIcon

# Определяем пути для режима .exe (PyInstaller) и обычного .py
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR

os.chdir(BASE_DIR)

# Распаковываем index.html из .exe рядом с программой для HTTP-сервера
bundled_html = os.path.join(RESOURCE_DIR, "index.html")
local_html = os.path.join(BASE_DIR, "index.html")
if os.path.exists(bundled_html) and getattr(sys, 'frozen', False):
    shutil.copy2(bundled_html, local_html)

PRESET_FILE = "cult_preset.json"
CONFIG_FILE = "cult_config.json"
MEDIA_DIR = "cult_media"
AUTOSTART_REG_NAME = "CultAltarDashboard"
os.makedirs(MEDIA_DIR, exist_ok=True)

WINRT_AVAILABLE = False
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
    "notify_steam": True
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

authenticated_phones = set()
ws_loop = None
current_layout_json = None
registered_apps = {}

# --- АВТОЗАПУСК WINDOWS ---
def get_autostart_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    python_exe = sys.executable
    if python_exe.lower().endswith("python.exe"):
        pythonw_exe = python_exe[:-10] + "pythonw.exe"
        if os.path.exists(pythonw_exe):
            python_exe = pythonw_exe
    script_path = os.path.abspath(__file__)
    return f'"{python_exe}" "{script_path}"'

def is_autostart_enabled():
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

def set_autostart(enable):
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

# --- ОПТИМИЗИРОВАННОЕ УПРАВЛЕНИЕ МЕДИА И SPOTIFY ---
user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

MEDIA_KEYS = {
    "vol_mute": 0xAD,
    "vol_down": 0xAE,
    "vol_up": 0xAF,
    "next": 0xB0,
    "prev": 0xB1,
    "play_pause": 0xB3
}

def press_media_key(cmd):
    vk = MEDIA_KEYS.get(cmd)
    if vk:
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)

_cached_spotify_pids = set()
_last_pid_scan_time = 0.0

def get_spotify_track():
    """Быстрое чтение заголовка Spotify с кэшированием PID."""
    global _cached_spotify_pids, _last_pid_scan_time
    now = time.time()

    # Проверяем актуальность кэша PID
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
                        return False  # Останавливаем перебор окон сразу после находки
        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    return found_title if found_title else "На паузе"

def collect_system_metrics():
    """Сбор всех метрик в фоновом потоке без блокировки интерфейса."""
    cpu_usage = round(psutil.cpu_percent(), 1)
    ram_usage = round(psutil.virtual_memory().percent, 1)
    disk_usage = round(psutil.disk_usage('C:\\').percent, 1)

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
                    await websocket.send(json.dumps({"action": "auth_ok"}))
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
                if app_path and os.path.exists(app_path):
                    os.startfile(app_path)

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
    asyncio.create_task(notification_listener_loop())
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

        if w_type == "notify_anchor":
            side = min(width, height)
            self.card_w = side
            self.card_h = side
            self.setBrush(QBrush(QColor(230, 184, 0, 35)))
            self.setPen(QPen(QColor("#e6b800"), 2, Qt.PenStyle.DashLine))
            self.setZValue(100)
        else:
            bg_color = "#152119" if w_type == "spotify" else ("#2b1419" if w_type == "launcher" else "#1c171c")
            self.setBrush(QBrush(QColor(bg_color)))
            self.setPen(QPen(QColor(accent_color), 2))
            self.setZValue(1)
        
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        
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
            self.title_item.setDefaultTextColor(QColor(accent_color))
            if w_type == "spotify":
                self.track_item = QGraphicsTextItem("♪ Исполнитель - Трек", self)
                self.track_item.setDefaultTextColor(QColor("#f2ebd9"))
            
            btn_labels = ["⏮", "⏯", "⏭"] if w_type == "spotify" else ["🔉-", "🔇", "🔊+"]
            self.mini_boxes = []
            self.mini_texts = []
            for lbl in btn_labels:
                box = QGraphicsRectItem(self)
                box.setBrush(QBrush(QColor("#241d24")))
                box.setPen(QPen(QColor(accent_color), 1))
                txt = QGraphicsTextItem(lbl, box)
                txt.setDefaultTextColor(QColor("#f2ebd9"))
                self.mini_boxes.append(box)
                self.mini_texts.append(txt)
        else:
            self.title_item = QGraphicsTextItem(f"✦ {title}", self)
            self.title_item.setDefaultTextColor(QColor(accent_color))
            
            self.val_item = QGraphicsTextItem(value_text, self)
            self.val_item.setDefaultTextColor(QColor("#f2ebd9"))
            
            if w_type in ("cpu", "ram", "disk"):
                self.bar_bg = QGraphicsRectItem(self)
                self.bar_bg.setBrush(QBrush(QColor("#2e262e")))
                self.bar_bg.setPen(QPen(Qt.PenStyle.NoPen))
                
                self.bar_fill = QGraphicsRectItem(self)
                self.bar_fill.setBrush(QBrush(QColor(accent_color)))
                self.bar_fill.setPen(QPen(Qt.PenStyle.NoPen))

        self.grip_item = QGraphicsTextItem("◢", self)
        self.grip_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.grip_item.setDefaultTextColor(QColor("#e6b800"))

        self.update_inner_layout()

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
        self.setWindowTitle("О проекте — Алтарь Управления")
        self.setFixedSize(460, 410)
        self.setStyleSheet("""
            QDialog {
                background-color: #120f12;
                color: #f2ebd9;
                font-family: Georgia;
                border: 2px solid #8a1c1c;
            }
            QLabel {
                color: #f2ebd9;
                font-size: 13px;
                line-height: 1.4;
            }
            QPushButton {
                background-color: #8a1c1c;
                color: #f2ebd9;
                border: 1px solid #e6b800;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #a82424;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("♛ АЛТАРЬ УПРАВЛЕНИЯ ♛")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #d92b2b; font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        layout.addWidget(title)

        story = QLabel(
            "Привет! Меня зовут <b>Семен</b>. Мне нравится игра <i>Cult of the Lamb</i> и обожаю "
            "мастерить что-то интересное своими руками.<br><br>"
            "Всё началось с того, что у меня без дела лежал старый смартфон — выкинуть жалко, "
            "а применить некуда. Готовые программы для вывода виджетов с ПК оказались либо "
            "платными, либо некрасивыми, либо вообще отказывались работать на старом Android.<br><br>"
            "Тогда я позвал в напарники нейросеть <b>Gemini</b>, и мы собрали этот проект как "
            "настоящая команда: с меня — задумка, тесты и сборка, с ИИ — код и технические идеи. "
            "Я не программист, но очень рад, что мы живём во время, когда можно с нуля создать "
            "что-то своё и поделиться этим с такими же энтузиастами.<br><br>"
            "<span style='color: #e6b800;'>Нашли баг или есть идея, как улучшить алтарь?</span><br>"
            "Напишите мне на почту: <b>pyazi.game@gmail.com</b>"
        )
        story.setWordWrap(True)
        story.setTextFormat(Qt.TextFormat.RichText)
        story.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(story)

        layout.addStretch()

        btn_close = QPushButton("Закрыть свиток")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

# --- ГРАФИЧЕСКИЙ РЕДАКТОР ---
class DashboardEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Алтарь Управления — Cult Edition | PIN: {APP_CONFIG['pin']}")
        icon_path = os.path.join(RESOURCE_DIR, "cult_altar.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setStyleSheet("""
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
        """)
        
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        top_bar = QHBoxLayout()
        self.pin_label = QLabel(f"🔑 PIN: {APP_CONFIG['pin']}")
        self.pin_label.setStyleSheet("color: #e6b800; font-size: 15px; font-weight: bold; padding: 4px 8px; border: 1px dashed #8a1c1c;")
        
        self.res_badge = QLabel(f"📐 {APP_CONFIG['screen_w']}×{APP_CONFIG['screen_h']}")
        self.res_badge.setStyleSheet("color: #b8ad9e; font-size: 13px; padding: 4px 8px;")

        btn_about = QPushButton("📜 О проекте")
        btn_about.clicked.connect(self.show_about_dialog)

        btn_deploy = QPushButton("🔥 Провести ритуал (На экран)")
        btn_deploy.setStyleSheet("background-color: #8a1c1c; color: #f2ebd9; border: 1px solid #e6b800; padding: 7px 14px;")
        btn_deploy.clicked.connect(self.deploy_to_phone)
        
        top_bar.addWidget(self.pin_label)
        top_bar.addWidget(self.res_badge)
        top_bar.addStretch()
        top_bar.addWidget(btn_about)
        top_bar.addWidget(btn_deploy)
        main_layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_altar = QWidget()
        self.tab_omens = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_altar, "🕯️ Алтарь")
        self.tabs.addTab(self.tab_omens, "🔔 Знамения")
        self.tabs.addTab(self.tab_settings, "⚙️ Настройки")

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
        btn_save = QPushButton("💾 Сохранить пресет")
        btn_save.clicked.connect(self.save_preset)

        btn_load = QPushButton("📂 Загрузить")
        btn_load.clicked.connect(self.load_preset)

        btn_del_sel = QPushButton("🗑️ Удалить выбранный")
        btn_del_sel.setStyleSheet("border-color: #ff6666; color: #ff9999;")
        btn_del_sel.clicked.connect(self.delete_selected_widgets)

        btn_clear = QPushButton("💀 Очистить холст")
        btn_clear.clicked.connect(self.clear_canvas)

        preset_bar.addWidget(btn_save)
        preset_bar.addWidget(btn_load)
        preset_bar.addStretch()
        preset_bar.addWidget(btn_del_sel)
        preset_bar.addWidget(btn_clear)
        layout.addLayout(preset_bar)

        tools_row1 = QHBoxLayout()
        btn_clock = QPushButton("👑 Время")
        btn_clock.clicked.connect(lambda: self.add_widget("clock", "ВРЕМЯ РИТУАЛА", "12:00:00", "#f2ebd9", 195, 75))
        
        btn_cpu = QPushButton("🗡️ CPU")
        btn_cpu.clicked.connect(lambda: self.add_widget("cpu", "РВЕНИЕ CPU", "45%", "#d92b2b", 175, 88))
        
        btn_ram = QPushButton("👁️ RAM")
        btn_ram.clicked.connect(lambda: self.add_widget("ram", "ВЕРА RAM", "60%", "#e6b800", 175, 88))

        btn_disk = QPushButton("💎 Диск C:")
        btn_disk.clicked.connect(lambda: self.add_widget("disk", "КАЗНА DISK", "72%", "#b366ff", 175, 88))

        btn_uptime = QPushButton("⏳ Аптайм")
        btn_uptime.clicked.connect(lambda: self.add_widget("uptime", "ЭПОХА ПК", "4ч 15м", "#66d9ff", 175, 75))

        tools_row1.addWidget(btn_clock)
        tools_row1.addWidget(btn_cpu)
        tools_row1.addWidget(btn_ram)
        tools_row1.addWidget(btn_disk)
        tools_row1.addWidget(btn_uptime)
        layout.addLayout(tools_row1)

        tools_row2 = QHBoxLayout()
        btn_spotify = QPushButton("🎵 Spotify")
        btn_spotify.setStyleSheet("border-color: #1db954; color: #1db954;")
        btn_spotify.clicked.connect(lambda: self.add_widget("spotify", "ПЕСНЬ SPOTIFY", "⏮   ⏯   ⏭", "#1db954", 240, 95))

        btn_volume = QPushButton("🔊 Громкость")
        btn_volume.setStyleSheet("border-color: #ff9933; color: #ff9933;")
        btn_volume.clicked.connect(lambda: self.add_widget("volume", "ГЛАС СИСТЕМЫ", "🔉  🔇  🔊", "#ff9933", 195, 80))

        btn_app = QPushButton("🔮 Программа")
        btn_app.setStyleSheet("border-color: #e6b800; color: #e6b800;")
        btn_app.clicked.connect(self.add_launcher_widget)

        btn_img = QPushButton("🖼️ Картинка / GIF")
        btn_img.setStyleSheet("border-color: #ff66b3; color: #ff66b3;")
        btn_img.clicked.connect(self.add_image_widget)

        tools_row2.addWidget(btn_spotify)
        tools_row2.addWidget(btn_volume)
        tools_row2.addWidget(btn_app)
        tools_row2.addWidget(btn_img)
        layout.addLayout(tools_row2)
        
        sw, sh = APP_CONFIG["screen_w"], APP_CONFIG["screen_h"]
        self.scene = AltarGraphicsScene(0, 0, sw, sh)
        self.scene.setBackgroundBrush(QBrush(QColor("#161216")))
        self.border_rect = self.scene.addRect(0, 0, sw, sh, QPen(QColor("#8a1c1c"), 2))
        
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(660, 380)
        layout.addWidget(self.view)

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
                        self, "Зона знамений",
                        "Якорь уведомлений нельзя удалить с холста — его можно скрыть, сняв галочки на вкладке «🔔 Знамения»."
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
            QMessageBox.information(self, "Удаление", "Кликните по нужному виджету на холсте, чтобы выделить его, а затем нажмите «Удалить выбранный» или клавишу Delete.")

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

        info_lbl = QLabel(
            "Выберите приложения, чьи уведомления будут вызывать всплывающий значок поверх виджетов.\n"
            "Текст сообщений НЕ читается и НЕ передается — отображается только пульсирующая иконка на 5 секунд.\n"
            "Положение и размер значка настраиваются перетаскиванием золотой рамки «🔔» на вкладке «Алтарь»."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("color: #b8ad9e; font-size: 13px; padding: 6px;")
        layout.addWidget(info_lbl)

        status_text = (
            "✅ Системный перехватчик Windows готов к работе."
            if WINRT_AVAILABLE else
            "⚠️ Пакеты winrt не установлены (установите через pip для перехвата из Windows)."
        )
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet("color: #e6b800; font-size: 12px; padding: 4px 6px;")
        layout.addWidget(status_lbl)

        group = QGroupBox("Активные знамения")
        g_layout = QVBoxLayout(group)

        row_tg = QHBoxLayout()
        self.chk_tg = QCheckBox("✈️ Telegram (значок самолетика)")
        self.chk_tg.setChecked(APP_CONFIG.get("notify_telegram", True))
        self.chk_tg.stateChanged.connect(self.on_notify_toggle)
        btn_test_tg = QPushButton("🧪 Тест на экране")
        btn_test_tg.clicked.connect(lambda: self.send_test_notification("telegram"))
        row_tg.addWidget(self.chk_tg)
        row_tg.addStretch()
        row_tg.addWidget(btn_test_tg)
        g_layout.addLayout(row_tg)

        row_dc = QHBoxLayout()
        self.chk_dc = QCheckBox("🎮 Discord (значок культа связи)")
        self.chk_dc.setChecked(APP_CONFIG.get("notify_discord", True))
        self.chk_dc.stateChanged.connect(self.on_notify_toggle)
        btn_test_dc = QPushButton("🧪 Тест на экране")
        btn_test_dc.clicked.connect(lambda: self.send_test_notification("discord"))
        row_dc.addWidget(self.chk_dc)
        row_dc.addStretch()
        row_dc.addWidget(btn_test_dc)
        g_layout.addLayout(row_dc)

        row_st = QHBoxLayout()
        self.chk_st = QCheckBox("⚙️ Steam (значок гильдии)")
        self.chk_st.setChecked(APP_CONFIG.get("notify_steam", True))
        self.chk_st.stateChanged.connect(self.on_notify_toggle)
        btn_test_st = QPushButton("🧪 Тест на экране")
        btn_test_st.clicked.connect(lambda: self.send_test_notification("steam"))
        row_st.addWidget(self.chk_st)
        row_st.addStretch()
        row_st.addWidget(btn_test_st)
        g_layout.addLayout(row_st)

        layout.addWidget(group)
        layout.addStretch()

    def on_notify_toggle(self):
        APP_CONFIG["notify_telegram"] = self.chk_tg.isChecked()
        APP_CONFIG["notify_discord"] = self.chk_dc.isChecked()
        APP_CONFIG["notify_steam"] = self.chk_st.isChecked()
        save_config(APP_CONFIG)
        self.update_anchor_visibility()

    def send_test_notification(self, app_name):
        if not authenticated_phones:
            QMessageBox.warning(self, "Нет связи", "Сначала подключите смартфон к серверу!")
            return
        msg = json.dumps({"action": "notify", "app": app_name})
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(msg), ws_loop)

    def init_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)

        screen_group = QGroupBox("Размер холста под ваше устройство")
        sg_layout = QVBoxLayout(screen_group)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Готовый профиль:"))
        self.combo_presets = QComboBox()
        self.combo_presets.addItem("Смартфон Горизонтально (640 × 360)", (640, 360))
        self.combo_presets.addItem("Смартфон Вертикально (360 × 640)", (360, 640))
        self.combo_presets.addItem("Широкий смартфон (800 × 360)", (800, 360))
        self.combo_presets.addItem("Планшет Горизонтально (1024 × 600)", (1024, 600))
        self.combo_presets.addItem("Планшет Вертикально (600 × 1024)", (600, 1024))
        self.combo_presets.currentIndexChanged.connect(self.on_preset_selected)
        preset_row.addWidget(self.combo_presets)
        sg_layout.addLayout(preset_row)

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Ширина (px):"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(240, 1920)
        self.spin_w.setValue(APP_CONFIG["screen_w"])
        custom_row.addWidget(self.spin_w)

        custom_row.addWidget(QLabel("Высота (px):"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(240, 1920)
        self.spin_h.setValue(APP_CONFIG["screen_h"])
        custom_row.addWidget(self.spin_h)

        btn_apply_res = QPushButton("Применить размер")
        btn_apply_res.setStyleSheet("border-color: #e6b800; color: #e6b800;")
        btn_apply_res.clicked.connect(self.apply_screen_size)
        custom_row.addWidget(btn_apply_res)
        sg_layout.addLayout(custom_row)

        layout.addWidget(screen_group)

        auto_group = QGroupBox("Автозапуск вместе с Windows")
        ag_layout = QHBoxLayout(auto_group)
        ag_lbl = QLabel("Запускать сервер в фоне при включении ПК (через pythonw.exe):")
        ag_lbl.setWordWrap(True)
        self.btn_autostart = QPushButton()
        self.btn_autostart.clicked.connect(self.toggle_autostart)
        self.refresh_autostart_button()
        ag_layout.addWidget(ag_lbl)
        ag_layout.addWidget(self.btn_autostart)
        layout.addWidget(auto_group)

        pin_group = QGroupBox("Безопасность подключения")
        pg_layout = QHBoxLayout(pin_group)
        self.settings_pin_lbl = QLabel(f"Текущий постоянный PIN-код:  {APP_CONFIG['pin']}")
        self.settings_pin_lbl.setStyleSheet("font-size: 14px; color: #e6b800; font-weight: bold;")
        btn_regen_pin = QPushButton("🔄 Сгенерировать новый PIN")
        btn_regen_pin.clicked.connect(self.regenerate_pin)
        pg_layout.addWidget(self.settings_pin_lbl)
        pg_layout.addStretch()
        pg_layout.addWidget(btn_regen_pin)
        layout.addWidget(pin_group)

        layout.addStretch()

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

        QMessageBox.information(self, "Размер обновлен", f"Холст изменен на {new_w}×{new_h}.\nНажмите «Провести ритуал», чтобы обновить телефон.")

    def refresh_autostart_button(self):
        if is_autostart_enabled():
            self.btn_autostart.setText("✅ В автозапуске (Убрать)")
            self.btn_autostart.setStyleSheet("background-color: #152b1b; border-color: #1db954; color: #1db954; padding: 8px 12px;")
        else:
            self.btn_autostart.setText("➕ Добавить в автозапуск")
            self.btn_autostart.setStyleSheet("background-color: #241d24; border-color: #e6b800; color: #e6b800; padding: 8px 12px;")

    def toggle_autostart(self):
        currently_on = is_autostart_enabled()
        success = set_autostart(not currently_on)
        if success:
            self.refresh_autostart_button()
            msg = "Программа удалена из автозапуска." if currently_on else "Программа добавлена в автозапуск Windows!"
            QMessageBox.information(self, "Автозапуск", msg)
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось изменить параметры реестра Windows.")

    def regenerate_pin(self):
        new_pin = str(random.randint(1000, 9999))
        APP_CONFIG["pin"] = new_pin
        save_config(APP_CONFIG)
        self.pin_label.setText(f"🔑 PIN: {new_pin}")
        self.settings_pin_lbl.setText(f"Текущий постоянный PIN-код:  {new_pin}")
        self.setWindowTitle(f"Алтарь Управления — Cult Edition | PIN: {new_pin}")
        QMessageBox.information(self, "Новый PIN", f"Новый постоянный PIN-код: {new_pin}")

    def add_widget(self, w_type, title, default_text, color, width, height,
                   x=40, y=40, app_id=None, app_path=None, media_file=None):
        card = CultWidgetCard(w_type, title, default_text, color, width, height, app_id, app_path, media_file)
        card.setPos(x, y)
        self.scene.addItem(card)
        self.added_widgets.append(card)

    def add_launcher_widget(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите программу, ярлык или скрипт", "", "Все файлы (*.*)"
        )
        if not file_path:
            return
            
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        label, ok = QInputDialog.getText(
            self, "Название ритуала", "Текст на кнопке смартфона:", text=default_name
        )
        if not ok or not label.strip():
            return

        app_id = f"app_{random.randint(10000, 99999)}"
        registered_apps[app_id] = file_path

        self.add_widget(
            "launcher", "ПРИЗЫВ ПРОГРАММЫ", label.strip(), "#e6b800", 
            width=190, height=70, app_id=app_id, app_path=file_path
        )

    def add_image_widget(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение или GIF", "", "Изображения (*.png *.jpg *.jpeg *.gif *.webp)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        new_filename = f"art_{random.randint(10000, 99999)}{ext}"
        dest_path = os.path.join(MEDIA_DIR, new_filename)
        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось скопировать файл: {e}")
            return

        self.add_widget(
            "image", "ИКОНА", "", "#8a1c1c",
            width=140, height=140, media_file=new_filename
        )

    def clear_canvas(self):
        for card in self.added_widgets:
            if card.movie:
                card.movie.stop()
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
        return json.dumps({
            "action": "update_layout",
            "screen_w": APP_CONFIG["screen_w"],
            "screen_h": APP_CONFIG["screen_h"],
            "widgets": layout_data
        }, ensure_ascii=False)

    def save_preset(self):
        data = self.build_layout_list()
        try:
            with open(PRESET_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Сохранено", f"Раскладка сохранена в {PRESET_FILE}!")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить: {e}")

    def load_preset(self, silent=False):
        if not os.path.exists(PRESET_FILE):
            if not silent:
                QMessageBox.warning(self, "Пусто", "Файл сохранения еще не создан.")
            return
        try:
            with open(PRESET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clear_canvas()
            anchor_found = False

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
                self.add_widget(
                    item["type"], item["title"], item["label"], item["color"],
                    item["w"], item["h"], item["x"], item["y"], app_id, app_path, media_file
                )

            if not anchor_found:
                self.ensure_notify_anchor()

            global current_layout_json
            current_layout_json = self.make_layout_packet(data)
            if not silent:
                QMessageBox.information(self, "Загружено", "Пресет успешно восстановлен!")
        except Exception as e:
            if not silent:
                QMessageBox.warning(self, "Ошибка", f"Сбой загрузки: {e}")

    def deploy_to_phone(self):
        global current_layout_json
        layout_data = self.build_layout_list()
        current_layout_json = self.make_layout_packet(layout_data)
        
        if ws_loop and ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_message(current_layout_json), ws_loop)
            QMessageBox.information(self, "Ритуал завершен", "Панель обновлена на экране смартфона!")
        else:
            QMessageBox.warning(self, "Ошибка", "Сервер еще не запущен.")

    def show_about_dialog(self):
        dlg = AboutDialog(self)
        dlg.exec()

if __name__ == '__main__':
    threading.Thread(target=start_http_server, daemon=True).start()
    threading.Thread(target=start_ws_server, daemon=True).start()
    
    app = QApplication(sys.argv)
    window = DashboardEditor()
    window.show()
    sys.exit(app.exec())