import sys, os, json, requests, vlc, shutil, time, warnings
from collections import deque
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QRunnable, QThreadPool, QObject
from PyQt6.QtGui import QPixmap, QIcon, QMovie, QCursor, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QSlider, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QSplitter, QStyle,
    QMessageBox, QInputDialog, QMenu, QStackedWidget, QTextBrowser, QDialog,
    QFileDialog, QDialogButtonBox, QFormLayout, QComboBox, QCheckBox,
    QSplashScreen, QScrollArea
)
from tools.engine import MusicEngine
from tools.themes import get_theme, get_color_for_theme
from tools.flow_layout import FlowLayout
from colorthief import ColorThief
from io import BytesIO

warnings.filterwarnings("ignore", category=DeprecationWarning)

DB_FILE = "database.json"
DEFAULT_PLAYLIST_COVER = "icons/default_playlist.png"

def load_db():
    defaults = {
        'favorites': [],
        'playlists': {},
        'settings': {
            'theme': 'dark',
            'show_right_panel': True,
            'auto_download': True
        }
    }
    if not os.path.exists(DB_FILE): return defaults
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
        data.setdefault('playlists', {})
        data.setdefault('favorites', [])
        data.setdefault('settings', defaults['settings'])
        data['settings'].setdefault('theme', 'dark')
        data['settings'].setdefault('show_right_panel', True)
        data['settings'].setdefault('auto_download', True)
        return data
    except (json.JSONDecodeError, FileNotFoundError): return defaults

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

class ImageWorkerSignals(QObject):
    finished = pyqtSignal(dict)

class ImageWorker(QRunnable):
    def __init__(self, cache_key, target_size=None):
        super().__init__()
        self.cache_key = cache_key
        self.url = cache_key[0]
        self.target_size = target_size
        self.signals = ImageWorkerSignals()

    def run(self):
        result = {'cache_key': self.cache_key, 'pixmap': None, 'dominant_color': None, 'error': None}
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            image_data = response.content
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            if not pixmap.isNull() and self.target_size:
                pixmap = pixmap.scaled(
                    self.target_size[0], self.target_size[1],
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
            result['pixmap'] = pixmap
            try:
                color_thief = ColorThief(BytesIO(image_data))
                result['dominant_color'] = color_thief.get_color(quality=5)
            except Exception:
                result['dominant_color'] = (40, 40, 40)

        except Exception as e:
            result['error'] = str(e)
        finally:
            self.signals.finished.emit(result)

class ImageLoader:
    PRIORITY_HIGH = 0
    PRIORITY_NORMAL = 1
    def __init__(self, parent_player):
        self.parent_player = parent_player
        self.threadpool = QThreadPool()
        max_threads = min(QThreadPool.globalInstance().maxThreadCount(), 8)
        self.threadpool.setMaxThreadCount(max_threads)
        self.high_priority_queue = deque()
        self.normal_priority_queue = deque()
        self.pending_requests = {}
        self.processing_timer = QTimer()
        self.processing_timer.setInterval(50)
        self.processing_timer.timeout.connect(self._process_queues)
        self.processing_timer.start()

    def request_image(self, url, widget=None, priority=PRIORITY_NORMAL, callback=None, target_size=None):
        if not url: return
        cache_key = (url, tuple(target_size) if target_size else None)
        if cache_key in self.parent_player.pixmap_cache:
            pixmap = self.parent_player.pixmap_cache[cache_key]
            try:
                if hasattr(widget, 'set_image'): widget.set_image(pixmap)
                elif isinstance(widget, QLabel): widget.setPixmap(pixmap)
                if callback: pass
            except RuntimeError: pass
            return

        if cache_key in self.pending_requests:
            if widget and widget not in self.pending_requests[cache_key]['widgets']:
                self.pending_requests[cache_key]['widgets'].append(widget)
            if callback: self.pending_requests[cache_key]['callback'] = callback
            return

        request_details = {'widgets': [widget] if widget else [], 'callback': callback}
        self.pending_requests[cache_key] = request_details
        if priority == self.PRIORITY_HIGH: self.high_priority_queue.appendleft(cache_key)
        else: self.normal_priority_queue.append(cache_key)

    def _process_queues(self):
        while self.threadpool.activeThreadCount() < self.threadpool.maxThreadCount():
            if not self.high_priority_queue and not self.normal_priority_queue: break
            cache_key = self.high_priority_queue.popleft() if self.high_priority_queue else self.normal_priority_queue.popleft()
            if cache_key not in self.pending_requests: continue
            url, target_size_tuple = cache_key
            target_size = list(target_size_tuple) if target_size_tuple else None
            worker = ImageWorker(cache_key, target_size=target_size)
            worker.signals.finished.connect(self._on_worker_finished)
            self.threadpool.start(worker)

    def _on_worker_finished(self, result):
        cache_key = result['cache_key']
        pixmap = result['pixmap']
        error = result['error']
        if cache_key not in self.pending_requests: return
        request_info = self.pending_requests[cache_key]
        if error: print(f"Resim indirilemedi ({cache_key[0]}): {error}")
        elif pixmap and not pixmap.isNull():
            self.parent_player.pixmap_cache[cache_key] = pixmap
            for widget in request_info['widgets']:
                try:
                    if hasattr(widget, 'set_image'): widget.set_image(pixmap)
                    elif isinstance(widget, QLabel): widget.setPixmap(pixmap)
                except RuntimeError:
                    print(f"Widget (URL: {cache_key[0][:30]}...) resim yüklenmeden silindi, atlanıyor.")
                    continue

            if request_info['callback']:
                try: request_info['callback'](pixmap, result['dominant_color'])
                except RuntimeError: pass

        del self.pending_requests[cache_key]

    def cancel_normal_priority_jobs(self):
        print(f"İptal ediliyor: {len(self.normal_priority_queue)} normal öncelikli resim isteği.")
        for cache_key in list(self.normal_priority_queue):
            if cache_key in self.pending_requests:
                del self.pending_requests[cache_key]
        self.normal_priority_queue.clear()


class Worker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    def __init__(self, target, *args):
        super().__init__()
        self.target = target
        self.args = args
    def run(self):
        try:
            res = self.target(*self.args)
            self.result.emit(res)
        except Exception as e:
            self.error.emit(str(e))

class SongItemWidget(QWidget):
    def __init__(self, song_data, parent_player):
        super().__init__()
        self.setFixedHeight(60)
        self.parent_player = parent_player
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(44, 44); self.thumb.setStyleSheet("background-color: #282828; border-radius: 4px;")
        thumbnail_url = song_data.get('thumbnail')
        if thumbnail_url:
            target_size = (44, 44)
            self.parent_player.image_loader.request_image(thumbnail_url, self, ImageLoader.PRIORITY_NORMAL, target_size=target_size)
        else:
            self.thumb.setPixmap(QPixmap("icons/default_cover.png").scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio))
     
        info_layout = QVBoxLayout(); info_layout.setSpacing(2); info_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(song_data.get('title', 'Başlık Yok'))
        artist_label = QLabel(song_data.get('artist', 'Bilinmeyen Sanatçı'))
        info_layout.addWidget(title_label); info_layout.addWidget(artist_label)
        duration_str = self.parent_player.format_time(song_data.get('duration', 0) * 1000)
        duration_label = QLabel(duration_str)
        duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.thumb); layout.addLayout(info_layout); layout.addStretch(); layout.addWidget(duration_label)

    def set_image(self, pixmap):
        if not pixmap.isNull():
            self.thumb.setPixmap(pixmap)

class ArtistItemWidget(QWidget):
    """Arama sonuçlarında bir sanatçıyı temsil eden widget."""
    def __init__(self, artist_data, parent_player):
        super().__init__()
        self.setFixedHeight(80)
        self.parent_player = parent_player
        self.browse_id = artist_data.get('browseId')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(15)
        self.thumb = QLabel()
        self.thumb.setFixedSize(64, 64)
        self.thumb.setStyleSheet("background-color: #282828; border-radius: 32px;") # Yuvarlak resim
        thumbnail_url = artist_data.get('thumbnail')
        if thumbnail_url:
            self.parent_player.image_loader.request_image(thumbnail_url, self, ImageLoader.PRIORITY_NORMAL, target_size=(64, 64))
            
        title_label = QLabel(artist_data.get('artist', 'Bilinmeyen Sanatçı'))
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.thumb); layout.addWidget(title_label); layout.addStretch()

    def set_image(self, pixmap):
        if not pixmap.isNull(): self.thumb.setPixmap(pixmap)

class AlbumItemWidget(QWidget):
    def __init__(self, album_data, parent_player):
        super().__init__()
        self.setFixedHeight(80)
        self.parent_player = parent_player
        self.browse_id = album_data.get('browseId')
        self.album_title = album_data.get('title')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8); layout.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setFixedSize(64, 64); self.thumb.setStyleSheet("background-color: #282828; border-radius: 4px;")
        thumbnail_url = album_data.get('thumbnail')
        if thumbnail_url:
            self.parent_player.image_loader.request_image(thumbnail_url, self, ImageLoader.PRIORITY_NORMAL, target_size=(64, 64))
            
        info_layout = QVBoxLayout(); info_layout.setSpacing(2); info_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(self.album_title)
        title_label.setStyleSheet("font-weight: bold;")
        artist_text = f"{album_data.get('artist', '')} • {album_data.get('year', '')}"
        artist_label = QLabel(artist_text)
        info_layout.addWidget(title_label); info_layout.addWidget(artist_label)
        layout.addWidget(self.thumb); layout.addLayout(info_layout); layout.addStretch()

    def set_image(self, pixmap):
        if not pixmap.isNull(): self.thumb.setPixmap(pixmap)

class CategoryItemWidget(QPushButton):
    def __init__(self, title, image_url, browse_id, parent_player, parent=None):
        super().__init__(parent)
        self.browse_id = browse_id; self.image_url = image_url; self.parent_player = parent_player
        self.setFixedSize(160, 200); self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("QPushButton { border: none; background-color: #181818; border-radius: 10px; text-align: center;} QPushButton:hover { background-color: #282828; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(10, 10, 10, 10); layout.setSpacing(10)
        self.image_label = QLabel()
        self.image_label.setFixedSize(140, 140); self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #282828; border-radius: 8px;")
        if image_url:
            self.image_label.setPixmap(QPixmap("icons/default_cover.png").scaled(80, 80))
            target_size = (140, 140)
            self.parent_player.image_loader.request_image(self.image_url, self, ImageLoader.PRIORITY_NORMAL, target_size=target_size)
        else:
            self.image_label.setPixmap(QPixmap("icons/default_cover.png").scaled(80, 80))
        
        title_label = QLabel(self.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, 140))
        title_label.setToolTip(title); title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        title_label.setStyleSheet("font-weight: bold; background-color: transparent;")
        layout.addWidget(self.image_label); layout.addWidget(title_label)

    def set_image(self, pixmap):
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
            
            
class DraggableSongListWidget(QListWidget):
    def __init__(self, parent_player):
        super().__init__(); self.parent_player = parent_player
    def dropEvent(self, event):
        super().dropEvent(event); key = self.parent_player.current_playlist_key
        if key == "search_results": return
        source_list = []
        if key == "favorites": source_list = self.parent_player.db['favorites']
        elif key in self.parent_player.db['playlists']: source_list = self.parent_player.db['playlists'][key]['songs']
        else: return
        new_song_order = []
        for i in range(self.count()):
            item = self.item(i)
            original_index = item.data(Qt.ItemDataRole.UserRole)
            if original_index is not None and 0 <= original_index < len(source_list): new_song_order.append(source_list[original_index])
        if len(new_song_order) != len(source_list): self.parent_player.populate_center_list(source_list); return
        if key == "favorites": self.parent_player.db['favorites'] = new_song_order
        else: self.parent_player.db['playlists'][key]['songs'] = new_song_order
        save_db(self.parent_player.db); self.parent_player.populate_center_list(new_song_order)

class PlaylistItemWidget(QWidget):
    def __init__(self, name, cover_path):
        super().__init__(); self.setFixedHeight(60)
        layout = QHBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(12)
        self.cover_label = QLabel(); self.cover_label.setFixedSize(44, 44); self.cover_label.setStyleSheet("background-color: #282828; border-radius: 4px;")
        if cover_path and os.path.exists(cover_path):
            if cover_path.lower().endswith('.gif'):
                movie = QMovie(cover_path); movie.setScaledSize(QSize(44, 44)); self.cover_label.setMovie(movie); movie.start()
            else:
                pixmap = QPixmap(cover_path); self.cover_label.setPixmap(pixmap.scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        else: self.cover_label.setPixmap(QPixmap(DEFAULT_PLAYLIST_COVER).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        name_label = QLabel(name); name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.cover_label); layout.addWidget(name_label); layout.addStretch()

class CreatePlaylistDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Yeni Çalma Listesi Oluştur"); self.setFixedSize(400, 220); self.new_cover_path = None
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(20, 20, 20, 20); main_layout.setSpacing(15)
        self.name_input = QLineEdit(); self.name_input.setPlaceholderText("Çalma Listesi Adı..."); main_layout.addWidget(self.name_input)
        cover_layout = QHBoxLayout(); cover_layout.setSpacing(10)
        self.cover_preview = QLabel(); self.cover_preview.setFixedSize(80, 80); self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setStyleSheet("border: 2px dashed #535353; border-radius: 5px; background-color: #121212;"); self.cover_preview.setText("Kapak\nSeç")
        choose_btn = QPushButton("Resim / GIF Seç..."); choose_btn.clicked.connect(self.choose_image)
        cover_layout.addWidget(self.cover_preview); cover_layout.addWidget(choose_btn); cover_layout.addStretch(); main_layout.addLayout(cover_layout)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok); ok_btn.setText("Oluştur"); ok_btn.setObjectName("dialog_accept_btn")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); main_layout.addStretch(); main_layout.addWidget(button_box)
    def choose_image(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Kapak Resmi Seç", "", "Resim Dosyaları (*.png *.jpg *.jpeg *.gif)")
        if filepath:
            self.new_cover_path = filepath; self.cover_preview.setText("")
            if filepath.lower().endswith('.gif'):
                movie = QMovie(filepath); movie.setScaledSize(QSize(80, 80)); self.cover_preview.setMovie(movie); movie.start()
            else:
                pixmap = QPixmap(filepath); scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation); self.cover_preview.setPixmap(scaled_pixmap)
    def get_data(self): return self.name_input.text(), self.new_cover_path

class SettingsDialog(QDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__(parent); self.setWindowTitle("Ayarlar"); self.setMinimumWidth(400); self.settings = current_settings
        layout = QVBoxLayout(self); form_layout = QFormLayout()
        self.theme_combo = QComboBox()
        self.themes = {"Koyu": "dark", "Sade Açık": "light", "Okyanus Mavisi": "ocean", "Synthwave Moru": "synthwave"}
        self.theme_combo.addItems(self.themes.keys())
        current_theme_key = next((key for key, value in self.themes.items() if value == self.settings.get('theme')), "Koyu")
        self.theme_combo.setCurrentText(current_theme_key); form_layout.addRow("Uygulama Teması:", self.theme_combo)
        self.show_panel_check = QCheckBox(); self.show_panel_check.setChecked(self.settings.get('show_right_panel', True))
        form_layout.addRow("Başlangıçta sanatçı panelini göster:", self.show_panel_check)
        self.auto_download_check = QCheckBox()
        self.auto_download_check.setChecked(self.settings.get('auto_download', True))
        form_layout.addRow("Çalınan şarkıları otomatik önbelleğe al:", self.auto_download_check)
        layout.addLayout(form_layout); layout.addSpacing(20)
        self.clear_cache_btn = QPushButton("Önbelleği Temizle"); self.clear_cache_btn.setObjectName("clear_cache_btn")
        self.clear_cache_btn.clicked.connect(self.clear_cache); layout.addWidget(self.clear_cache_btn)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_btn = button_box.button(QDialogButtonBox.StandardButton.Save); save_btn.setText("Kaydet ve Uygula"); save_btn.setObjectName("dialog_accept_btn")
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
        button_box.accepted.connect(self.accept); button_box.rejected.connect(self.reject); layout.addWidget(button_box)
    def clear_cache(self):
        path = 'music_cache'
        if not os.path.exists(path) or not os.listdir(path):
            show_custom_messagebox(self, QMessageBox.Icon.Information, "Bilgi", "Önbellek zaten boş.", QMessageBox.StandardButton.Ok)
            return
        reply = show_custom_messagebox(self, QMessageBox.Icon.Question, "Onay", "Tüm önbelleğe alınmış şarkıları silmek istediğinize emin misiniz? Bu işlem geri alınamaz.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            total_size = 0; file_count = 0
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                try: total_size += os.path.getsize(file_path); os.remove(file_path); file_count += 1
                except Exception as e: print(f"Dosya silinemedi: {file_path}, Hata: {e}")
            size_mb = total_size / (1024 * 1024)
            if hasattr(self.parent(), 'pixmap_cache'):
                self.parent().pixmap_cache.clear()
                print("Resim önbelleği temizlendi.")
            show_custom_messagebox(self, QMessageBox.Icon.Information, "Başarılı", f"{file_count} dosya silindi. Toplam {size_mb:.2f} MB alan boşaltıldı.", QMessageBox.StandardButton.Ok)
    def get_settings(self):
        selected_theme_name = self.theme_combo.currentText()
        return {
            'theme': self.themes[selected_theme_name],
            'show_right_panel': self.show_panel_check.isChecked(),
            'auto_download': self.auto_download_check.isChecked()
        }

def show_custom_messagebox(parent, icon, title, text, buttons):
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(f"<b>{text}</b>")
    msg_box.setStandardButtons(buttons)
    if buttons & QMessageBox.StandardButton.Ok:
        ok_btn = msg_box.button(QMessageBox.StandardButton.Ok); ok_btn.setText("Tamam"); ok_btn.setObjectName("dialog_accept_btn")
    if buttons & QMessageBox.StandardButton.Yes:
        yes_btn = msg_box.button(QMessageBox.StandardButton.Yes); yes_btn.setText("Evet"); yes_btn.setObjectName("dialog_accept_btn")
    if buttons & QMessageBox.StandardButton.No:
        msg_box.button(QMessageBox.StandardButton.No).setText("Hayır")
    if buttons & QMessageBox.StandardButton.Cancel:
        msg_box.button(QMessageBox.StandardButton.Cancel).setText("İptal")
    return msg_box.exec()


class MusicPlayer(QWidget):
    song_finished_signal = pyqtSignal()
    SEARCH_PAGE_SIZE = 20

    def __init__(self):
        super().__init__()
        self.music_engine = MusicEngine()
        self.db = load_db()
        self.image_loader = ImageLoader(self)
        self.pixmap_cache = {}
        self.current_theme_name = self.db['settings']['theme']
        self.discover_category_widgets = []
        self.active_threads = []
        self.current_song_info = None
        self.current_playlist_key = None
        self.current_playlist = []
        self.current_song_index = -1
        self.loop_mode = 0
        self.last_search_query = ""
        self.last_search_filter = "songs"
        self.current_search_limit = self.SEARCH_PAGE_SIZE
        self.welcome_movie = None # welcome.gif için
        self._initialize_player()
        self._setup_ui()
        self._connect_signals()
        self._load_initial_state()

    def _initialize_player(self):
        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()
        self.media_player.event_manager().event_attach(vlc.EventType.MediaPlayerEndReached, self.handle_song_end)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(200)

    def _setup_ui(self):
        self.setWindowTitle("Lei-Music"); self.setWindowIcon(QIcon("icons/app_icon.png")); self.setGeometry(100, 100, 1400, 800)
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal); splitter.setHandleWidth(1); splitter.setStyleSheet("QSplitter::handle { background-color: #282828; }")
        self.left_panel = self._create_left_panel()
        self.center_panel = self._create_center_panel()
        self.right_panel = self._create_right_panel()
        splitter.addWidget(self.left_panel); splitter.addWidget(self.center_panel); splitter.addWidget(self.right_panel)
        splitter.setSizes([280, 770, 350]) 
        self.player_bar = self._create_player_bar()
        main_layout.addWidget(splitter); main_layout.addWidget(self.player_bar)
        
    def _connect_signals(self):
        self.progress_timer.timeout.connect(self.update_ui)
        self.song_finished_signal.connect(self.safe_play_next_song)
        self.home_button.clicked.connect(self.show_discover_page); self.settings_button.clicked.connect(self.open_settings)
        self.new_playlist_btn.clicked.connect(self.create_new_playlist)
        self.playlists_list.itemClicked.connect(lambda item: self.show_playlist(item.data(Qt.ItemDataRole.UserRole)))
        self.playlists_list.customContextMenuRequested.connect(self.show_playlist_context_menu)
        self.search_box.returnPressed.connect(self.search_songs); self.search_button.clicked.connect(self.search_songs)
        self.center_song_list.itemDoubleClicked.connect(self.play_from_center_list)
        self.center_song_list.customContextMenuRequested.connect(self.show_song_context_menu)
        self.load_more_btn.clicked.connect(self.load_more_songs)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause); self.next_btn.clicked.connect(self.safe_play_next_song)
        self.prev_btn.clicked.connect(self.play_prev_song); self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.volume_slider.valueChanged.connect(self.set_volume); self.loop_button.clicked.connect(self.toggle_loop_mode)
        self.fav_button.clicked.connect(self.toggle_favorite); self.info_button.clicked.connect(self.toggle_right_panel)

    def _load_initial_state(self):
        screen_geometry = self.screen().availableGeometry()
        self.move(int((screen_geometry.width() - self.width()) / 2), int((screen_geometry.height() - self.height()) / 2))
        self.apply_theme(self.db['settings']['theme'])
        self.update_playlists_list()
        show_panel = self.db['settings'].get('show_right_panel', True)
        self.right_panel.setVisible(show_panel); self.info_button.setChecked(show_panel)
        self.show_discover_page()
        if show_panel and not self.current_song_info:
            self.show_welcome_panel()

    def _create_left_panel(self):
        panel = QWidget(); panel.setObjectName("left_panel"); layout = QVBoxLayout(panel); layout.setContentsMargins(8, 8, 8, 8)
        top_layout = QHBoxLayout()
        self.home_button = QPushButton(icon=QIcon("icons/home.png")); self.home_button.setFixedSize(32, 32); self.home_button.setIconSize(QSize(20,20)); self.home_button.setObjectName("settings_button"); self.home_button.setToolTip("Ana Sayfa / Keşfet")
        self.settings_button = QPushButton(icon=QIcon("icons/settings.png")); self.settings_button.setFixedSize(32, 32); self.settings_button.setIconSize(QSize(20,20)); self.settings_button.setObjectName("settings_button"); self.settings_button.setToolTip("Ayarlar")
        top_layout.addWidget(self.home_button); top_layout.addWidget(self.settings_button); top_layout.addStretch(); layout.addLayout(top_layout)
        header_widget = QWidget(); header_layout = QHBoxLayout(header_widget); header_layout.setContentsMargins(0, 10, 0, 10)
        header_layout.addWidget(QLabel("Kütüphane")); header_layout.addStretch()
        self.new_playlist_btn = QPushButton("＋"); self.new_playlist_btn.setFixedSize(30, 30); self.new_playlist_btn.setObjectName("new_playlist_btn")
        header_layout.addWidget(self.new_playlist_btn); self.playlists_list = QListWidget(); self.playlists_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(header_widget); layout.addWidget(self.playlists_list); return panel

    def _create_center_panel(self):
        panel = QWidget(); panel.setObjectName("center_panel"); layout = QVBoxLayout(panel)
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Ne dinlemek istersin?")
        self.search_filter_combo = QComboBox()
        self.search_filter_combo.addItems(["Şarkılar", "Sanatçılar", "Albümler"])
        self.search_filter_combo.setFixedWidth(100)
        self.search_button = QPushButton("Ara")
        self.search_button.setObjectName("search_btn")
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.search_filter_combo)
        search_layout.addWidget(self.search_button)
        self.stacked_widget = QStackedWidget()
        self.center_song_list_page = QWidget(); song_list_layout = QVBoxLayout(self.center_song_list_page); song_list_layout.setContentsMargins(0,0,0,0)
        self.center_song_list = DraggableSongListWidget(self); self.center_song_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.center_song_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        song_list_layout.addWidget(self.center_song_list)
        self.load_more_btn = QPushButton("Daha Fazla Yükle"); self.load_more_btn.setObjectName("search_btn"); self.load_more_btn.setVisible(False); self.load_more_btn.setFixedHeight(40)
        song_list_layout.addWidget(self.load_more_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        loading_widget = QWidget(); loading_layout = QVBoxLayout(loading_widget); self.loading_animation = QLabel()
        self.loading_movie = QMovie("icons/loading.gif"); self.loading_animation.setMovie(self.loading_movie)
        self.loading_animation.setAlignment(Qt.AlignmentFlag.AlignCenter); loading_layout.addWidget(self.loading_animation)
        self.discover_page_scroll = QScrollArea(); self.discover_page_scroll.setWidgetResizable(True); self.discover_page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.discover_page = QWidget(); self.discover_page_layout = QVBoxLayout(self.discover_page)
        self.discover_page_layout.setAlignment(Qt.AlignmentFlag.AlignTop); self.discover_page_layout.setSpacing(25)
        self.discover_page_scroll.setWidget(self.discover_page)
        self.stacked_widget.addWidget(self.center_song_list_page); self.stacked_widget.addWidget(loading_widget); self.stacked_widget.addWidget(self.discover_page_scroll)
        layout.addWidget(search_widget); layout.addWidget(self.stacked_widget); return panel

    def _create_right_panel(self):
        panel = QWidget(); panel.setObjectName("right_panel"); layout = QVBoxLayout(panel); layout.setContentsMargins(15, 15, 15, 15); layout.setSpacing(10)
        self.artist_image_label = QLabel()
        self.artist_image_label.setObjectName("artist_image_label_main")
        self.artist_image_label.setFixedSize(350, 280)
        self.artist_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_image_label.setStyleSheet("border-radius: 8px; background-color: transparent;")
        self.artist_name_label = QLabel("Sanatçı Bilgisi"); self.artist_name_label.setObjectName("artist_name_label")
        self.artist_name_label.setWordWrap(False)
        self.header_label = QLabel("Sanatçı Hakkında", objectName="right_panel_header")
        self.artist_bio_browser = QTextBrowser(); self.artist_bio_browser.setReadOnly(True); self.artist_bio_browser.setOpenExternalLinks(True)
        layout.addWidget(self.artist_image_label); layout.addWidget(self.artist_name_label); layout.addWidget(self.header_label); layout.addWidget(self.artist_bio_browser); return panel

    def _create_player_bar(self):
        widget = QWidget()
        widget.setObjectName("player_bar")
        widget.setFixedHeight(100)
        layout = QHBoxLayout(widget)
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0); left_layout.setSpacing(12)
        self.player_cover = QLabel(); self.player_cover.setObjectName("player_cover_label"); self.player_cover.setFixedSize(60, 60); self.player_cover.setStyleSheet("border-radius: 5px;")
        self.player_cover.setPixmap(QPixmap("icons/default_cover.png").scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        player_song_info_layout = QVBoxLayout(); player_song_info_layout.setSpacing(2); player_song_info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.player_title = QLabel("Lei-Music"); self.player_title.setObjectName("now_playing_title")
        self.player_artist = QLabel("Keşfetmeye başla"); self.player_artist.setObjectName("now_playing_artist")
        player_song_info_layout.addWidget(self.player_title); player_song_info_layout.addWidget(self.player_artist)
        self.fav_button = QPushButton(icon=QIcon("icons/heart-outline.png")); self.fav_button.setFixedSize(32, 32); self.fav_button.setIconSize(QSize(24, 24)); self.fav_button.setEnabled(False)
        left_layout.addWidget(self.player_cover); left_layout.addLayout(player_song_info_layout); left_layout.addWidget(self.fav_button)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(5); center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); center_layout.setContentsMargins(0, 10, 0, 10)
        player_controls_layout = QHBoxLayout(); player_controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter); player_controls_layout.setSpacing(20)
        self.prev_btn = QPushButton(icon=self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward))
        self.play_pause_btn = QPushButton(); self.play_pause_btn.setObjectName("play_pause_btn"); self.play_pause_btn.setFixedSize(36, 36)
        self.next_btn = QPushButton(icon=self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward))
        player_controls_layout.addWidget(self.prev_btn); player_controls_layout.addWidget(self.play_pause_btn); player_controls_layout.addWidget(self.next_btn)
        progress_layout = QHBoxLayout(); progress_layout.setContentsMargins(0, 0, 0, 0); progress_layout.setSpacing(10)
        self.time_label = QLabel("00:00"); self.time_label.setFixedWidth(40); self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_slider = QSlider(Qt.Orientation.Horizontal); self.position_slider.setFixedHeight(20)
        self.duration_label = QLabel("00:00"); self.duration_label.setFixedWidth(40); self.duration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.time_label); progress_layout.addWidget(self.position_slider); progress_layout.addWidget(self.duration_label)
        center_layout.addLayout(player_controls_layout); center_layout.addLayout(progress_layout)
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter); right_layout.setSpacing(15)
        self.info_button = QPushButton(icon=QIcon("icons/info.png")); self.info_button.setCheckable(True); self.info_button.setFixedSize(32, 32)
        self.loop_button = QPushButton(); self.update_loop_button_style()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal); self.volume_slider.setRange(0, 100); self.volume_slider.setValue(100); self.volume_slider.setFixedWidth(120)
        right_layout.addWidget(self.info_button); right_layout.addWidget(self.loop_button); right_layout.addWidget(self.volume_slider)
        layout.addWidget(left_widget, 2); layout.addWidget(center_widget, 3); layout.addWidget(right_widget, 2)
        return widget

    def start_worker(self, worker_class, on_finish, on_error, target_func, *args):
        thread = worker_class(target_func, *args)
        thread.result.connect(on_finish); thread.error.connect(on_error)
        thread.finished.connect(lambda: self.active_threads.remove(thread) if thread in self.active_threads else None)
        self.active_threads.append(thread); thread.start()

    def apply_theme(self, theme_name):
        self.current_theme_name = theme_name; self.setStyleSheet(get_theme(theme_name))
        if hasattr(self, 'play_pause_btn'): self.update_play_pause_icons()
            
    def play_song_by_id(self, video_id):
        self.progress_timer.stop(); self.media_player.stop()
        self.update_player_bar_info()
        cached_path = self.music_engine.check_cache(video_id)
        if cached_path:
            print(f"'{video_id}' önbellekten oynatılıyor."); self.play_media(cached_path); return
        print(f"'{video_id}' stream ediliyor...")
        self.start_worker(Worker, self.on_stream_url_received, self.show_error_message, self.music_engine.get_stream_url, video_id)
        if self.db['settings'].get('auto_download', True):
            self.start_worker(Worker, lambda r: None, lambda e: print(f"Cache hatası: {e}"), self.music_engine.download_and_cache_song, video_id)

    def on_stream_url_received(self, stream_url):
        if stream_url: self.play_media(stream_url)
        else: self.show_error_message("Şarkı stream edilemedi.")

    def play_media(self, media_path_or_url):
        if hasattr(self, 'welcome_movie') and self.welcome_movie: self.welcome_movie.stop(); self.welcome_movie = None
        media = self.vlc_instance.media_new(media_path_or_url)
        self.media_player.set_media(media); self.media_player.play(); self.progress_timer.start()
        self.update_play_pause_icons(); self.update_fav_button_status()

    def update_ui(self):
        if not self.media_player.get_media() or self.position_slider.isSliderDown() or not self.media_player.is_playing(): return
        position = self.media_player.get_time()
        self.position_slider.setValue(position); self.time_label.setText(self.format_time(position))
    
    def format_time(self, ms):
        if ms < 0: ms = 0
        total_seconds = int(ms / 1000)
        return f"{(total_seconds // 60):02d}:{(total_seconds % 60):02d}"

    def handle_song_end(self, event): self.song_finished_signal.emit()

    def toggle_play_pause(self):
        if self.media_player.get_media(): self.media_player.pause(); self.update_play_pause_icons()
            
    def on_slider_released(self):
        if self.media_player.get_media(): self.media_player.set_time(self.position_slider.value())
            
    def set_volume(self, volume): self.media_player.audio_set_volume(volume)
    
    def toggle_loop_mode(self):
        self.loop_mode = (self.loop_mode + 1) % 3
        self.update_loop_button_style()

    def safe_play_next_song(self):
        if not self.current_playlist: return
        if self.loop_mode == 2: self.play_song_from_current_playlist(); return
        is_last_song = self.current_song_index >= len(self.current_playlist) - 1
        if self.loop_mode == 0 and is_last_song:
            self.progress_timer.stop(); self.media_player.stop(); self.update_play_pause_icons(); return
        self.current_song_index = (self.current_song_index + 1) % len(self.current_playlist)
        self.play_song_from_current_playlist()

    def play_prev_song(self):
        if not self.current_playlist: return
        if self.media_player.get_time() > 3000: self.play_song_from_current_playlist()
        else:
            self.current_song_index = (self.current_song_index - 1 + len(self.current_playlist)) % len(self.current_playlist)
            self.play_song_from_current_playlist()
            
    def play_from_center_list(self, item):
        index = self.center_song_list.row(item)
        if not (0 <= index < len(self.current_playlist)): return
        data = self.current_playlist[index]
        item_type = data.get('type')
        browse_id = data.get('browseId')

        if item_type == 'artist' and browse_id:
            self.on_category_clicked(browse_id, data.get('artist'))
        elif item_type == 'album' and browse_id:
            self.on_category_clicked(browse_id, data.get('title'))
        else:
            self.current_song_index = index
            self.play_song_from_current_playlist()

    def play_song_from_current_playlist(self):
        if self.current_playlist and 0 <= self.current_song_index < len(self.current_playlist):
            self.current_song_info = self.current_playlist[self.current_song_index]
            self.center_song_list.setCurrentRow(self.current_song_index)
            self.play_song_by_id(self.current_song_info['id'])
            
    def show_error_message(self, error_message):
        self.loading_movie.stop(); self.stacked_widget.setCurrentIndex(0)
        show_custom_messagebox(self, QMessageBox.Icon.Critical, "Hata", str(error_message), QMessageBox.StandardButton.Ok)
        self.player_title.setText("Bir hata oluştu"); self.player_artist.setText("Lütfen tekrar deneyin")

    def update_player_bar_info(self):
        if not self.current_song_info: return
        self.player_title.setText(self.current_song_info.get('title', 'Bilinmeyen Şarkı'))
        artist_name = self.current_song_info.get('artist', 'Bilinmeyen Sanatçı'); self.player_artist.setText(artist_name)
        duration_ms = self.current_song_info.get('duration', 0) * 1000
        self.position_slider.setRange(0, duration_ms); self.duration_label.setText(self.format_time(duration_ms)); self.time_label.setText("00:00")
        thumbnail_url = self.current_song_info.get('thumbnail')
        if thumbnail_url:
            self.image_loader.request_image(thumbnail_url, self.player_cover, ImageLoader.PRIORITY_HIGH, target_size=(60,60))
        else:
            self.player_cover.setPixmap(QPixmap("icons/default_cover.png").scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        self.fetch_artist_info(artist_name)

    def fetch_artist_info(self, artist_name):
        if hasattr(self, 'welcome_movie') and self.welcome_movie: self.welcome_movie.stop(); self.welcome_movie = None
        if not self.right_panel.isVisible() or not artist_name: return
        if hasattr(self, "_last_fetched_artist") and self._last_fetched_artist == artist_name and "yükleniyor" not in self.artist_bio_browser.toPlainText(): return
        self._last_fetched_artist = artist_name
        self.artist_name_label.setText(artist_name); self.artist_bio_browser.setText("Biyografi yükleniyor...")
        thumbnail_url = self.current_song_info.get('thumbnail') if self.current_song_info else None
        if thumbnail_url:
            self.image_loader.request_image(thumbnail_url, None, ImageLoader.PRIORITY_HIGH, 
                                            callback=self.set_artist_image)
        else:
            self.artist_image_label.setPixmap(QPixmap("icons/default_cover.png").scaled(250, 250))
         
        self.start_worker(Worker, self.on_artist_info_received, lambda e: self.update_right_panel(None), self.music_engine.get_artist_info, artist_name)


    def set_artist_image(self, pixmap, dominant_color):
        """Callback: Sanatçı resmini alır, doğru şekilde boyutlandırır ve panele yerleştirir."""
        if not pixmap or pixmap.isNull():
            return

        label_width = self.artist_image_label.width()
        scaled_pixmap = pixmap.scaledToWidth(label_width, Qt.TransformationMode.SmoothTransformation)
        self.artist_image_label.setPixmap(scaled_pixmap)
        self.set_right_panel_background(pixmap, dominant_color)

    def on_artist_info_received(self, artist_data):
        if artist_data:
            self.artist_name_label.setText(artist_data.get('name', 'İsim Yok'))
            self.artist_bio_browser.setText(artist_data.get('bio', 'Biyografi bulunamadı.'))
        else:
            artist_name = self.current_song_info.get('artist', 'Sanatçı Bilgisi') if self.current_song_info else "Sanatçı Bilgisi"
            self.artist_name_label.setText(artist_name)
            self.artist_bio_browser.setText("Bu sanatçı için bilgi bulunamadı.")
            
    def update_right_panel(self, artist_data):
        self.on_artist_info_received(artist_data)
        
    def set_right_panel_background(self, pixmap, color_rgb):
        if color_rgb:
            r, g, b = color_rgb
            brightness = (0.299 * r + 0.587 * g + 0.114 * b)
            text_color = "#000000" if brightness > 128 else "#FFFFFF"
            secondary_text_color = "#333333" if brightness > 128 else "#b3b3b3"
            darker_color = QColor(r, g, b).darker(150)
            dr, dg, db = darker_color.red(), darker_color.green(), darker_color.blue()
            gradient_style = f"""
                #right_panel {{ background: qlineargradient(x1:0.5, y1:0, x2:0.5, y2:1, stop:0 rgba({r}, {g}, {b}, 255), stop:1 rgba({dr}, {dg}, {db}, 255)); }}
            """
            self.right_panel.setStyleSheet(gradient_style)
            self.artist_name_label.setStyleSheet(f"color: {text_color}; background-color: transparent;")
            self.header_label.setStyleSheet(f"color: {secondary_text_color}; background-color: transparent;")
            self.artist_bio_browser.setStyleSheet(f"color: {text_color}; background-color: transparent;")
    
    def update_play_pause_icons(self):
        if self.media_player.is_playing():
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        else:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_pause_btn.setIconSize(QSize(24, 24))

    def update_loop_button_style(self):
        self.loop_button.setStyleSheet("")
        accent_color = get_color_for_theme(self.current_theme_name, 'accent_primary')
        if self.loop_mode == 0:
            self.loop_button.setIcon(QIcon("icons/loop-off.png")); self.loop_button.setToolTip("Tekrar Kapalı")
        elif self.loop_mode == 1:
            self.loop_button.setIcon(QIcon("icons/loop.png")); self.loop_button.setStyleSheet(f"color: {accent_color};"); self.loop_button.setToolTip("Listeyi Tekrarla")
        else:
            self.loop_button.setIcon(QIcon("icons/loop-one.png")); self.loop_button.setStyleSheet(f"color: {accent_color};"); self.loop_button.setToolTip("Şarkıyı Tekrarla")

    def toggle_favorite(self):
        if not self.current_song_info: return
        song_id = self.current_song_info['id']
        is_favorite = any(s['id'] == song_id for s in self.db['favorites'])
        if is_favorite:
            self.remove_song_from_favorites(self.current_song_info)
        else:
            self.add_song_to_favorites(self.current_song_info)

    def update_fav_button_status(self):
        if not self.current_song_info: self.fav_button.setEnabled(False); return
        self.fav_button.setEnabled(True)
        is_favorite = any(s['id'] == self.current_song_info['id'] for s in self.db['favorites'])
        self.fav_button.setIcon(QIcon("icons/heart-full.png") if is_favorite else QIcon("icons/heart-outline.png"))

    def open_settings(self):
        dialog = SettingsDialog(self.db['settings'], self)
        if dialog.exec():
            new_settings = dialog.get_settings()
            self.db['settings'] = new_settings; save_db(self.db)
            self.apply_theme(new_settings['theme'])
            self.toggle_right_panel(force_state=new_settings.get('show_right_panel', True))
            show_custom_messagebox(self, QMessageBox.Icon.Information, "Ayarlar Kaydedildi", "Ayarlar başarıyla uygulandı.", QMessageBox.StandardButton.Ok)

    def create_new_playlist(self):
        dialog = CreatePlaylistDialog(self)
        if dialog.exec():
            name, cover_path = dialog.get_data(); name = name.strip()
            if not name: show_custom_messagebox(self, QMessageBox.Icon.Warning, "Hata", "Çalma listesi adı boş olamaz.", QMessageBox.StandardButton.Ok); return
            if name in self.db['playlists'] or name == "favorites": show_custom_messagebox(self, QMessageBox.Icon.Warning, "Hata", f"'{name}' adında bir liste zaten var.", QMessageBox.StandardButton.Ok); return
            final_cover_path = DEFAULT_PLAYLIST_COVER
            if cover_path:
                if not os.path.exists("playlist_covers"): os.makedirs("playlist_covers")
                ext = os.path.splitext(cover_path)[1]; safe_name = "".join(x for x in name if x.isalnum())
                dest_path = os.path.join("playlist_covers", f"{safe_name}_{int(time.time())}{ext}")
                try: shutil.copy(cover_path, dest_path); final_cover_path = dest_path
                except Exception as e: print(f"Kapak kopyalanamadı: {e}")
            self.db['playlists'][name] = {'songs': [], 'cover': final_cover_path}; save_db(self.db); self.update_playlists_list()

    def show_playlist_context_menu(self, pos):
        item = self.playlists_list.itemAt(pos);
        if not item: return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key == "favorites": return
        menu = QMenu(); rename_action = menu.addAction("Adı Değiştir"); change_cover_action = menu.addAction("Kapak Resmini Değiştir"); delete_action = menu.addAction("Çalma Listesini Sil")
        action = menu.exec(QCursor.pos())
        if action == rename_action:
            dialog = QInputDialog(self); dialog.setWindowTitle("Adı Değiştir"); dialog.setLabelText(f"Yeni ad girin ({key}):")
            dialog.setOkButtonText("Kaydet"); dialog.setCancelButtonText("İptal")
            dialog.findChild(QDialogButtonBox).findChild(QPushButton).setObjectName("dialog_accept_btn")
            if dialog.exec():
                new_name = dialog.textValue().strip()
                if new_name and new_name != key:
                    if new_name in self.db['playlists']:
                        show_custom_messagebox(self, QMessageBox.Icon.Warning, "Hata", "Bu isimde başka bir liste zaten var.", QMessageBox.StandardButton.Ok)
                    else:
                        self.db['playlists'][new_name] = self.db['playlists'].pop(key); save_db(self.db); self.update_playlists_list()
                        if self.current_playlist_key == key: self.show_playlist(new_name)
        elif action == change_cover_action:
            filepath, _ = QFileDialog.getOpenFileName(self, "Yeni Kapak Resmi Seç", "", "Resim Dosyaları (*.png *.jpg *.jpeg *.gif)")
            if filepath:
                ext = os.path.splitext(filepath)[1]; safe_name = "".join(x for x in key if x.isalnum()); dest_path = os.path.join("playlist_covers", f"{safe_name}_{int(time.time())}{ext}")
                try: shutil.copy(filepath, dest_path); self.db['playlists'][key]['cover'] = dest_path; save_db(self.db); self.update_playlists_list()
                except Exception as e: print(f"Yeni kapak resmi kopyalanamadı: {e}")
        elif action == delete_action:
            reply = show_custom_messagebox(self, QMessageBox.Icon.Question, "Onay", f"'{key}' listesini silmek istediğinize emin misiniz?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                cover_to_delete = self.db['playlists'][key].get('cover')
                if cover_to_delete and cover_to_delete != DEFAULT_PLAYLIST_COVER and os.path.exists(cover_to_delete):
                    try: os.remove(cover_to_delete)
                    except OSError as e: print(f"Kapak resmi silinemedi: {e}")
                del self.db['playlists'][key]; save_db(self.db); self.update_playlists_list()
                if self.current_playlist_key == key: self.show_discover_page()

    def add_song_to_favorites(self, song_data):
        if not any(s['id'] == song_data['id'] for s in self.db['favorites']):
            self.db['favorites'].append(song_data)
            save_db(self.db)
            self.update_fav_button_status()
            if self.current_playlist_key == "favorites": self.show_playlist("favorites")
            print(f"'{song_data['title']}' beğenilenlere eklendi.")

    def remove_song_from_favorites(self, song_data):
        self.db['favorites'] = [s for s in self.db['favorites'] if s['id'] != song_data['id']]
        save_db(self.db)
        self.update_fav_button_status()
        if self.current_playlist_key == "favorites": self.show_playlist("favorites")
        print(f"'{song_data['title']}' beğenilenlerden kaldırıldı.")
        
    def download_song_from_menu(self, song_data):
        video_id = song_data['id']
        if self.music_engine.check_cache(video_id):
            print(f"'{song_data['title']}' zaten önbellekte.")
            return

        print(f"'{song_data['title']}' indirme isteği gönderildi...")
        self.start_worker(Worker, lambda r: print(f"'{song_data['title']}' başarıyla indirildi."), 
                          lambda e: print(f"'{song_data['title']}' indirilirken hata: {e}"), 
                          self.music_engine.download_and_cache_song, video_id)
        show_custom_messagebox(self, QMessageBox.Icon.Information, "İndirme Başladı", 
                               f"'{song_data['title']}' arka planda indiriliyor.", QMessageBox.StandardButton.Ok)

    def search_for_artist(self, artist_name):
        if not artist_name: return
        self.search_filter_combo.setCurrentText("Sanatçılar")
        self.search_box.setText(artist_name)
        self.search_songs()

    def show_song_context_menu(self, pos):
        item = self.center_song_list.itemAt(pos);
        if not item: return
        song_index = self.center_song_list.row(item)
        if not (0 <= song_index < len(self.current_playlist)): return
        data = self.current_playlist[song_index]
        item_type = data.get('type')
        if item_type != 'song' and item_type is not None: return

        song_data = data
        song_id = song_data.get('id')
        artist_name = song_data.get('artist')
        menu = QMenu()
        is_favorite = any(s['id'] == song_id for s in self.db['favorites'])
        if is_favorite:
            fav_action = menu.addAction(QIcon("icons/heart-full.png"), "Beğenilenlerden Kaldır")
            fav_action.triggered.connect(lambda: self.remove_song_from_favorites(song_data))
        else:
            fav_action = menu.addAction(QIcon("icons/heart-outline.png"), "Beğenilenlere Ekle")
            fav_action.triggered.connect(lambda: self.add_song_to_favorites(song_data))

        menu.addSeparator()
        add_to_playlist_menu = menu.addMenu("Çalma Listesine Ekle")
        if not self.db['playlists']: add_to_playlist_menu.setEnabled(False)
        else:
            for name in sorted(self.db['playlists'].keys()):
                playlist_songs = self.db['playlists'][name]['songs']
                if any(s['id'] == song_id for s in playlist_songs):
                    action = add_to_playlist_menu.addAction(f"{name} (Eklendi)"); action.setEnabled(False)
                else:
                    action = add_to_playlist_menu.addAction(name)
                    action.triggered.connect(lambda _, pl_name=name, s_data=song_data: self.add_song_to_playlist(pl_name, s_data))
        
        if self.current_playlist_key not in ["search_results", "discover", "favorites"]:
            remove_from_list_action = menu.addAction("Bu Listeden Kaldır")
            remove_from_list_action.triggered.connect(lambda: self.remove_song_from_current_playlist(song_index))

        menu.addSeparator()

        if artist_name and artist_name != "Bilinmeyen Sanatçı":
            go_to_artist_action = menu.addAction(f"'{artist_name}' Sanatçısına Git")
            go_to_artist_action.triggered.connect(lambda: self.search_for_artist(artist_name))

        download_action = menu.addAction(QIcon("icons/downloaded.png"), "Şarkıyı İndir (Önbelleğe Al)")
        if self.music_engine.check_cache(song_id):
            download_action.setText("Şarkı Zaten İndirilmiş"); download_action.setEnabled(False)
        else:
            download_action.triggered.connect(lambda: self.download_song_from_menu(song_data))
        
        menu.exec(QCursor.pos())

    def add_song_to_playlist(self, playlist_name, song_data):
        if not any(s['id'] == song_data['id'] for s in self.db['playlists'][playlist_name]['songs']):
            self.db['playlists'][playlist_name]['songs'].append(song_data)
            save_db(self.db)
            print(f"'{song_data['title']}' -> '{playlist_name}' listesine eklendi.")
            show_custom_messagebox(self, QMessageBox.Icon.Information, "Eklendi", f"'{song_data['title']}' şarkısı '{playlist_name}' listesine eklendi.", QMessageBox.StandardButton.Ok)

    def remove_song_from_current_playlist(self, song_index):
        list_key = self.current_playlist_key
        if list_key in self.db['playlists']:
            del self.db['playlists'][list_key]['songs'][song_index]
            save_db(self.db)
            self.show_playlist(list_key)
            print(f"Şarkı '{list_key}' listesinden kaldırıldı.")

    def show_playlist(self, key):
        self.image_loader.cancel_normal_priority_jobs()
        self.load_more_btn.setVisible(False)
        self.current_playlist_key = key
        if key == "favorites": song_list = self.db.get('favorites', [])
        else: song_list = self.db.get('playlists', {}).get(key, {}).get('songs', [])
        self.populate_center_list(song_list)
        self.stacked_widget.setCurrentWidget(self.center_song_list_page)

    def update_playlists_list(self):
        self.playlists_list.clear()
        fav_item_widget = PlaylistItemWidget("Beğenilen Şarkılar", "icons/heart-full.png"); fav_list_item = QListWidgetItem()
        fav_list_item.setSizeHint(fav_item_widget.sizeHint()); fav_list_item.setData(Qt.ItemDataRole.UserRole, "favorites")
        self.playlists_list.addItem(fav_list_item); self.playlists_list.setItemWidget(fav_list_item, fav_item_widget)
        playlists = self.db.get('playlists', {}) or {};
        for name, data in sorted(playlists.items()):
            cover_path = data.get('cover', DEFAULT_PLAYLIST_COVER); item_widget = PlaylistItemWidget(name, cover_path)
            list_item = QListWidgetItem(); list_item.setSizeHint(item_widget.sizeHint()); list_item.setData(Qt.ItemDataRole.UserRole, name)
            self.playlists_list.addItem(list_item); self.playlists_list.setItemWidget(list_item, item_widget)

    def populate_center_list(self, results_list):
        self.center_song_list.clear()
        self.current_playlist = list(results_list) 
        for i, data in enumerate(results_list):
            item_widget = None; item_type = data.get('type')
            if item_type == 'artist': item_widget = ArtistItemWidget(data, self)
            elif item_type == 'album': item_widget = AlbumItemWidget(data, self)
            else: item_widget = SongItemWidget(data, self)
            if item_widget:
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                list_item.setData(Qt.ItemDataRole.UserRole, i)
                self.center_song_list.addItem(list_item)
                self.center_song_list.setItemWidget(list_item, item_widget)

    def search_songs(self):
        query = self.search_box.text().strip()
        if not query: return
        selected_filter_text = self.search_filter_combo.currentText()
        filter_map = {"Şarkılar": "songs", "Sanatçılar": "artists", "Albümler": "albums"}
        api_filter = filter_map.get(selected_filter_text, "songs")
        self.image_loader.cancel_normal_priority_jobs()
        self.last_search_query = query
        self.last_search_filter = api_filter 
        self.current_search_limit = self.SEARCH_PAGE_SIZE
        self.load_more_btn.setText("Daha Fazla Yükle")
        self.stacked_widget.setCurrentIndex(1); self.loading_movie.start(); QApplication.processEvents() 
        self.start_worker(Worker, self.on_search_finished, self.show_error_message, 
                          self.music_engine.search_ytmusic, self.last_search_query, self.current_search_limit, api_filter)

    def load_more_songs(self):
        if not self.last_search_query: return
        self.current_search_limit += self.SEARCH_PAGE_SIZE
        self.load_more_btn.setText("Yükleniyor..."); self.load_more_btn.setEnabled(False)
        api_filter = getattr(self, 'last_search_filter', 'songs')
        self.start_worker(Worker, self.on_search_finished, self.show_error_message, 
                          self.music_engine.search_ytmusic, self.last_search_query, self.current_search_limit, api_filter)

    def on_search_finished(self, results):
        self.loading_movie.stop()
        self.current_playlist_key = "search_results"
        self.populate_center_list(results)
        self.stacked_widget.setCurrentWidget(self.center_song_list_page)
        self.load_more_btn.setEnabled(True); self.load_more_btn.setText("Daha Fazla Yükle")
        if len(results) < self.current_search_limit: self.load_more_btn.setVisible(False)
        else: self.load_more_btn.setVisible(True)

    def show_discover_page(self):
        self.stacked_widget.setCurrentWidget(self.discover_page_scroll)
        self.load_more_btn.setVisible(False)
        self.current_playlist_key = "discover"
        if not self.discover_category_widgets:
             self.load_discover_data()
        else:
            print("Keşfet sayfasına geri dönüldü, resimler kontrol ediliyor...")
            for widget in self.discover_category_widgets:
                if widget.image_url:
                    target_size = (140, 140) 
                    self.image_loader.request_image(widget.image_url, widget, ImageLoader.PRIORITY_NORMAL, target_size=target_size)

    def load_discover_data(self):
        self.stacked_widget.setCurrentIndex(1)
        self.loading_movie.start()
        self.start_worker(Worker, self.populate_discover_page, self.show_error_message, self.music_engine.get_ytmusic_discover_data)

    def populate_discover_page(self, data):
        self.loading_movie.stop()
        self.stacked_widget.setCurrentWidget(self.discover_page_scroll)
        self.discover_category_widgets.clear()
        while self.discover_page_layout.count():
            child = self.discover_page_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not data:
            self.discover_page_layout.addWidget(QLabel("Keşfedilecek içerik bulunamadı."))
            return
        self.discover_data_queue = list(data.items())
        self._process_discover_batch()

    def _process_discover_batch(self):
        if not hasattr(self, 'discover_data_queue') or not self.discover_data_queue:
            print("Tüm keşfet kategorileri arayüze eklendi.")
            return
        section_title, playlists = self.discover_data_queue.pop(0)
        if playlists:
            section_widget = self._create_discover_section(section_title, playlists)
            self.discover_page_layout.addWidget(section_widget)
        QTimer.singleShot(0, self._process_discover_batch)

    def _create_discover_section(self, title, items):
        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget); section_layout.setContentsMargins(10, 0, 10, 0); section_layout.setSpacing(10)
        title_label = QLabel(title); title_label.setObjectName("right_panel_header"); title_label.setStyleSheet("font-size: 22px; padding: 10px 0;")
        section_layout.addWidget(title_label)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFixedHeight(225)
        scroll_content = QWidget(); content_layout = QHBoxLayout(scroll_content)
        content_layout.setSpacing(15); content_layout.setContentsMargins(0, 0, 0, 0)
        for item in items:
            browse_id = item.get('browseId')
            thumbnail_url = item['thumbnails'][-1]['url'] if item.get('thumbnails') else None
            if browse_id:
                cat_widget = CategoryItemWidget(item['title'], thumbnail_url, browse_id, self)
                cat_widget.clicked.connect(lambda _, bid=browse_id, pl_title=item['title']: self.on_category_clicked(bid, pl_title))
                self.discover_category_widgets.append(cat_widget)
                content_layout.addWidget(cat_widget)
        content_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        section_layout.addWidget(scroll_area)
        return section_widget

    def on_category_clicked(self, browse_id, title):
        print(f"'{title}' kategorisine/albümüne tıklandı. ID: {browse_id}")
        self.image_loader.cancel_normal_priority_jobs()
        self.current_playlist_key = browse_id
        self.stacked_widget.setCurrentIndex(1); self.loading_movie.start()
        self.start_worker(Worker, self.on_discover_playlist_loaded, self.show_error_message, self.music_engine.get_ytmusic_browse_results, browse_id)

    def on_discover_playlist_loaded(self, song_list):
        self.loading_movie.stop()
        self.populate_center_list(song_list)
        self.stacked_widget.setCurrentWidget(self.center_song_list_page)
        self.load_more_btn.setVisible(False)

    def show_welcome_panel(self):
        self.artist_name_label.setText("Hoş Geldin !")
        self.artist_bio_browser.setText("Müzik keşfetmenin en keyifli yolu.\n\n" "İstediğin şarkıyı ara, çalma listeleri oluştur ve müziğin keyfini çıkar. " "Sağdaki panelde, çaldığın sanatçı hakkında ilginç bilgiler bulacaksın.")
        welcome_gif_path = "icons/welcome.gif"
        if os.path.exists(welcome_gif_path):
            if not hasattr(self, 'welcome_movie') or self.welcome_movie is None:
                 self.welcome_movie = QMovie(welcome_gif_path)
            self.artist_image_label.setMovie(self.welcome_movie)
            self.artist_image_label.setScaledContents(True) 
            self.welcome_movie.start()
        welcome_bg_color = get_color_for_theme(self.current_theme_name, 'bg_very_dark')
        self.right_panel.setStyleSheet(f"#right_panel {{ background-color: {welcome_bg_color}; }}")

    def toggle_right_panel(self, force_state=None):
        is_visible = self.right_panel.isVisible()
        new_state = not is_visible if force_state is None else force_state
        self.right_panel.setVisible(new_state)
        self.info_button.setChecked(new_state)
        if new_state and not self.current_song_info: self.show_welcome_panel()
        elif new_state and self.current_song_info: self.fetch_artist_info(self.current_song_info.get('artist'))
        
    def closeEvent(self, event):
        self.image_loader.processing_timer.stop()
        self.image_loader.threadpool.clear()
        self.image_loader.threadpool.waitForDone()
        for thread in self.active_threads:
            if thread.isRunning(): thread.quit(); thread.wait()
        event.accept()

def setup_initial_files():
    for folder in ["icons", "playlist_covers", "music_cache"]:
        if not os.path.exists(folder): os.makedirs(folder); print(f"Bilgi: '{folder}' klasörü oluşturuldu.")
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({'favorites': [], 'playlists': {}, 'settings': {'theme': 'dark', 'show_right_panel': True, 'auto_download': True}}, f)
    icon_urls = {
        "downloaded.png": "https://i.imgur.com/wXyYc5g.png", "home.png": "https://i.imgur.com/rJ2cM1t.png",
        "settings.png": "https://i.imgur.com/gB8v4m9.png", "app_icon.png": "https://i.imgur.com/Qz7a2F7.png",
        "default_cover.png": "https://i.imgur.com/d7ddx8w.png", "default_playlist.png": "https://i.imgur.com/GCRx3Jm.png",
        "heart-full.png": "https://i.imgur.com/5lILD0A.png", "heart-outline.png": "https://i.imgur.com/B3gL2tN.png",
        "info.png": "https://i.imgur.com/U4dFMRu.png", "loop.png": "https://i.imgur.com/gC5P7s1.png",
        "loop-one.png": "https://i.imgur.com/qg9bSj5.png", "welcome.gif": "https://i.imgur.com/3nI4b2s.gif",
        "loading.gif": "https://i.imgur.com/j2VjOq8.gif"
    }
    for name, url in icon_urls.items():
        path = os.path.join("icons", name)
        if not os.path.exists(path):
            try:
                print(f"İkon indiriliyor: {name}..."); r = requests.get(url, allow_redirects=True, timeout=10); r.raise_for_status()
                with open(path, 'wb') as f: f.write(r.content)
                print(f"İkon başarıyla indirildi: {name}")
            except Exception as e: print(f"İkon indirilemedi: {name}, Hata: {e}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    setup_initial_files()
    splash_pixmap_path = "icons/loading.gif"
    splash = None
    if os.path.exists(splash_pixmap_path):
        movie = QMovie(splash_pixmap_path)
        splash_label = QLabel(); splash_label.setMovie(movie); movie.start()
        splash = QSplashScreen(splash_label.movie().currentPixmap())
        splash.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        splash.setEnabled(False)
        screen_geometry = app.primaryScreen().geometry()
        splash.move(int((screen_geometry.width() - splash.width()) / 2), int((screen_geometry.height() - splash.height()) / 2))
        splash.show()
    player = MusicPlayer()
    if splash:
        splash.finish(player)
    player.show()
    sys.exit(app.exec())