import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QListWidget,
    QProgressBar, QMessageBox, QGroupBox, QListWidgetItem, QStyle,
    QSplitter, QFrame, QLineEdit, QFormLayout, QCheckBox, QSlider,
    QSizePolicy, QStyledItemDelegate, QAbstractItemView, QSplashScreen,
    QScrollArea  # Added for improved resizing behavior
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QMimeData, QTimer
from PyQt6.QtGui import QIcon, QFont, QColor, QDragEnterEvent, QDropEvent, QPixmap, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import keyring
import qtawesome as qta
import mutagen
from mutagen.wave import WAVE
import time
from pydub import AudioSegment
import json  # Add json import at the top of the file with other imports

from elevenlabs_api import ElevenLabsAPI

# Application version
APP_VERSION = "1.2.1"

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchConverter")

# Constants for keyring
APP_NAME = "ElevenLabsBatchConverter"
KEY_NAME = "ElevenLabsAPIKey"
VOICE_KEY = "SelectedVoiceID"
MODEL_KEY = "SelectedModelID"
FORMAT_KEY = "SelectedOutputFormat"
VOICE_SETTINGS_KEY = "VoiceSettings"  # This will store a JSON with voice-specific settings

class ClickableProgressBar(QProgressBar):
    """A progress bar that can be clicked to seek to a position."""
    
    clicked = pyqtSignal(int)  # Signal emitted when clicked, with position percentage
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Calculate the percentage of the width where the click occurred
            position_percent = (event.position().x() / self.width()) * 100
            self.clicked.emit(int(position_percent))
        
        super().mousePressEvent(event)

class AudioFileWidget(QWidget):
    """Custom widget to display audio file information with controls."""
    
    def __init__(self, file_path, parent=None, index=0):
        super().__init__(parent)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.is_playing = False
        self.index = index
        
        # Set up media player
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.sourceChanged.connect(self.handle_source_changed)
        self.player.playbackStateChanged.connect(self.handle_state_changed)
        self.player.errorOccurred.connect(self.handle_error)
        
        # Get audio duration
        self.duration = self.get_audio_duration()
        
        self.init_ui()
    
    def init_ui(self):
        """Set up the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # Index number
        self.index_label = QLabel(f"{self.index+1}.")
        self.index_label.setFixedWidth(15)
        self.index_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        font = QFont()
        font.setBold(True)
        self.index_label.setFont(font)
        layout.addWidget(self.index_label)
        
        # File info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # File name with ellipsis but preserving extension
        self.name_label = QLabel(self.ellipsify_filename(self.file_name, 40))
        self.name_label.setFont(font)
        self.name_label.setToolTip(self.file_name)
        info_layout.addWidget(self.name_label)
        
        # File details in a single line
        details_layout = QHBoxLayout()
        details_layout.setSpacing(10)
        
        # Duration
        duration_str = self.format_duration(self.duration)
        self.duration_label = QLabel(f"Duration: {duration_str}")
        details_layout.addWidget(self.duration_label)
        
        # Current position (only shown during playback)
        self.position_label = QLabel("")
        self.position_label.setVisible(False)
        details_layout.addWidget(self.position_label)
        
        # File size
        size_bytes = os.path.getsize(self.file_path)
        size_mb = size_bytes / (1024 * 1024)
        self.size_label = QLabel(f"Size: {size_mb:.2f} MB")
        details_layout.addWidget(self.size_label)
        
        # Add a spacer to push everything to the left
        details_layout.addStretch(1)
        
        info_layout.addLayout(details_layout)
        
        # Progress bar (only visible during playback)
        self.progress_bar = ClickableProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #ecf0f1;
                border-radius: 2px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_bar.clicked.connect(self.seek_to_position)
        self.progress_bar.setVisible(False)
        info_layout.addWidget(self.progress_bar)
        
        layout.addLayout(info_layout, 1)  # Give the info section more space
        
        # Play/Pause button
        self.play_button = QPushButton()
        self.play_button.setIcon(qta.icon('fa5s.play', color='white'))
        self.play_button.setFixedSize(36, 36)  # Slightly larger button
        self.play_button.setToolTip("Play/Pause")
        self.play_button.clicked.connect(self.toggle_playback)
        layout.addWidget(self.play_button)
        
        # Set the widget's size policy
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        # Set a fixed height for the widget
        self.setFixedHeight(50)
        
        # Add a subtle background
        self.setStyleSheet("""
            AudioFileWidget {
                background-color: rgba(52, 152, 219, 0.1);
                border-radius: 4px;
                margin: 2px;
            }
            AudioFileWidget:hover {
                background-color: rgba(52, 152, 219, 0.2);
            }
            QPushButton {
                background-color: #2c3e50;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        
        # Set initial volume
        self.audio_output.setVolume(1.0)
        
        # Connect position update signal
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
    
    def get_audio_duration(self):
        """Get the duration of the audio file in seconds."""
        try:
            if self.file_path.lower().endswith('.wav'):
                audio = WAVE(self.file_path)
                return audio.info.length
            else:
                audio = mutagen.File(self.file_path)
                if audio is not None:
                    return audio.info.length
            return 0
        except Exception as e:
            logging.error(f"Error getting audio duration: {str(e)}")
            return 0
    
    def format_duration(self, seconds):
        """Format seconds into a readable time string."""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def toggle_playback(self):
        """Toggle between play and pause."""
        if not self.is_playing:
            self.play()
        else:
            self.pause()
    
    def play(self):
        """Play the audio file."""
        parent_list = self.parent()
        while parent_list and not isinstance(parent_list, QListWidget):
            parent_list = parent_list.parent()
        if parent_list:
            for i in range(parent_list.count()):
                item = parent_list.item(i)
                widget = parent_list.itemWidget(item)
                if widget and isinstance(widget, AudioFileWidget) and widget != self:
                    widget.stop()
        if self.player.source() != QUrl.fromLocalFile(self.file_path):
            self.player.setSource(QUrl.fromLocalFile(self.file_path))
        self.player.play()
    
    def pause(self):
        """Pause playback."""
        self.player.pause()
    
    def stop(self):
        """Stop playback."""
        self.player.stop()
    
    def handle_source_changed(self, source):
        pass
    
    def handle_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing = True
            self.play_button.setIcon(qta.icon('fa5s.pause', color='white'))
            self.progress_bar.setVisible(True)
            self.position_label.setVisible(True)
        else:
            self.is_playing = False
            self.play_button.setIcon(qta.icon('fa5s.play', color='white'))
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self.progress_bar.setVisible(False)
                self.position_label.setVisible(False)
                self.progress_bar.setValue(0)
                
    def handle_error(self, error, error_string):
        logging.error(f"Media player error: {error_string}")
        QMessageBox.warning(self, "Playback Error", f"Error playing audio file: {error_string}")
    
    def update_position(self, position):
        if self.player.duration() > 0:
            progress = int((position / self.player.duration()) * 100)
            self.progress_bar.setValue(progress)
            position_str = self.format_duration(position / 1000)
            duration_str = self.format_duration(self.player.duration() / 1000)
            self.position_label.setText(f"{position_str} / {duration_str}")
    
    def update_duration(self, duration):
        if duration > 0:
            self.duration = duration / 1000
            duration_str = self.format_duration(self.duration)
            self.duration_label.setText(f"Duration: {duration_str}")
            self.position_label.setText(f"0:00 / {duration_str}")
            self.progress_bar.setValue(0)
    
    def seek_to_position(self, percent):
        if self.player.duration() > 0:
            position = int((percent / 100.0) * self.player.duration())
            self.player.setPosition(position)
            if not self.is_playing:
                self.play()
    
    def set_index(self, index):
        self.index = index
        self.index_label.setText(f"{index+1}.")
    
    def ellipsify_filename(self, filename, max_length=40):
        if len(filename) <= max_length:
            return filename
        name, ext = os.path.splitext(filename)
        chars_to_keep = max_length - 3 - len(ext)
        if chars_to_keep < 1:
            return filename[:max_length-3] + "..."
        return name[:chars_to_keep] + "..." + ext

class DragDropListWidget(QListWidget):
    """Custom QListWidget that supports drag and drop of audio files."""
    
    def __init__(self, parent=None, accepted_extensions=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.accepted_extensions = accepted_extensions or [".mp3", ".wav", ".ogg", ".flac", ".m4a"]
        self.setStyleSheet("""
            DragDropListWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
        """)
        self._default_stylesheet = self.styleSheet()
        self._drag_active = False
        self.setItemDelegate(QStyledItemDelegate())
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSpacing(2)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if self._is_accepted_file(url):
                    self._set_drag_active(True)
                    event.acceptProposedAction()
                    return
    
    def dragLeaveEvent(self, event):
        self._set_drag_active(False)
        
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        self._set_drag_active(False)
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            for url in event.mimeData().urls():
                if self._is_accepted_file(url):
                    self._add_file(url.toLocalFile())
            self.update_indices()
    
    def _set_drag_active(self, active):
        if self._drag_active != active:
            self._drag_active = active
            if active:
                self.setStyleSheet(self._default_stylesheet + """
                    DragDropListWidget {
                        border: 2px dashed #3498db;
                        background-color: rgba(52, 152, 219, 0.1);
                    }
                """)
            else:
                self.setStyleSheet(self._default_stylesheet)
    
    def _is_accepted_file(self, url: QUrl) -> bool:
        if not url.isLocalFile():
            return False
        file_path = url.toLocalFile()
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in self.accepted_extensions
    
    def _add_file(self, file_path: str):
        existing_items = [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        if file_path not in existing_items:
            audio_widget = AudioFileWidget(file_path, index=self.count())
            item = QListWidgetItem(self)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            item.setSizeHint(audio_widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, audio_widget)
    
    def update_indices(self):
        for i in range(self.count()):
            widget = self.itemWidget(self.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.set_index(i)

class ConversionWorker(QThread):
    """Worker thread to handle audio conversion without blocking the UI."""
    progress_updated = pyqtSignal(int, int)
    conversion_complete = pyqtSignal(str, bool, dict)
    conversion_finished = pyqtSignal()
    
    def __init__(self, api, voice_id, file_list, model_id, speaker_boost, remove_background_noise, 
                 stability, similarity_boost, style, output_format="mp3_44100_128"):
        super().__init__()
        self.api = api
        self.voice_id = voice_id
        self.file_list = file_list
        self.model_id = model_id
        self.speaker_boost = speaker_boost
        self.remove_background_noise = remove_background_noise
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.style = style
        self.output_format = output_format
        self.is_cancelled = False
    
    def _fix_wav_format(self, file_path, bit_depth=32):
        try:
            audio = AudioSegment.from_file(file_path)
            sample_width = 4
            if bit_depth == 16:
                sample_width = 2
            elif bit_depth == 24:
                sample_width = 3
            audio = audio.set_sample_width(sample_width)
            audio.export(file_path, format="wav")
            logger.info(f"Successfully fixed WAV format for {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error fixing WAV format: {str(e)}")
            return False
    
    def run(self):
        total_files = len(self.file_list)
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        for i, file_path in enumerate(self.file_list):
            if self.is_cancelled:
                break
            try:
                self.progress_updated.emit(i, total_files)
                file_name = os.path.basename(file_path)
                base_name, _ = os.path.splitext(file_name)
                if self.output_format.startswith("mp3"):
                    output_ext = ".mp3"
                    bit_depth = None
                elif self.output_format.startswith("flac"):
                    output_ext = ".flac"
                    bit_depth = 16
                    if "24" in self.output_format:
                        bit_depth = 24
                    elif "32" in self.output_format:
                        bit_depth = 32
                elif self.output_format.startswith("pcm"):
                    output_ext = ".wav"
                    if "16000" in self.output_format:
                        bit_depth = 16
                    elif "24000" in self.output_format:
                        bit_depth = 24
                    elif "32000" in self.output_format:
                        bit_depth = 32
                    else:
                        bit_depth = 32
                else:
                    output_ext = ".mp3"
                    bit_depth = None
                output_path = output_dir / f"{base_name}{output_ext}"
                audio_data, token_info = self.api.convert_speech_to_speech(
                    voice_id=self.voice_id,
                    audio_file_path=file_path,
                    model_id=self.model_id,
                    speaker_boost=self.speaker_boost,
                    remove_background_noise=self.remove_background_noise,
                    stability=self.stability,
                    similarity_boost=self.similarity_boost,
                    style=self.style,
                    output_format=self.output_format
                )
                if audio_data:
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    if output_ext.lower() == ".wav":
                        self._fix_wav_format(output_path, bit_depth)
                    elif output_ext.lower() == ".flac":
                        logger.info(f"FLAC format selected for {output_path}")
                    self.conversion_complete.emit(str(output_path), True, token_info or {})
                else:
                    self.conversion_complete.emit(file_path, False, {})
            except Exception as e:
                logger.error(f"Error converting {file_path}: {str(e)}")
                self.conversion_complete.emit(file_path, False, {})
        self.progress_updated.emit(total_files, total_files)
        self.conversion_finished.emit()
    
    def cancel(self):
        self.is_cancelled = True

class SplashScreen(QSplashScreen):
    """Custom splash screen with loading animation."""
    
    def __init__(self):
        splash_pixmap = QPixmap(400, 300)
        splash_pixmap.fill(QColor("#2c3e50"))
        super().__init__(splash_pixmap)
        self.container = QWidget()
        self.container.setFixedSize(400, 300)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "logo.png")
            if os.path.exists(logo_path):
                logo_label = QLabel()
                logo_pixmap = QPixmap(logo_path)
                scaled_pixmap = logo_pixmap.scaled(180, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
                logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout.addWidget(logo_label)
            else:
                icon_label = QLabel()
                icon_pixmap = QPixmap(128, 128)
                icon_pixmap.fill(Qt.GlobalColor.transparent)
                mic_icon = qta.icon('fa5s.microphone-alt', color='#3498db')
                mic_pixmap = mic_icon.pixmap(80, 80)
                wave_icon = qta.icon('fa5s.wave-square', color='#2ecc71')
                wave_pixmap = wave_icon.pixmap(60, 60)
                painter = QPainter(icon_pixmap)
                painter.drawPixmap(24, 10, mic_pixmap)
                painter.drawPixmap(34, 70, wave_pixmap)
                painter.end()
                icon_label.setPixmap(icon_pixmap)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout.addWidget(icon_label)
        except Exception as e:
            logger.error(f"Error loading splash screen image: {str(e)}")
        title_label = QLabel("ElevenLabs Batch Voice Changer")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white;")
        self.layout.addWidget(title_label)
        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #bdc3c7;")
        self.layout.addWidget(version_label)
        self.loading_label = QLabel("Loading...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: white;")
        self.layout.addWidget(self.loading_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #34495e;
                border-radius: 5px;
                text-align: center;
                height: 10px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        self.layout.addWidget(self.progress_bar)
        self.dot_count = 0
        self.dot_timer = QTimer()
        self.dot_timer.timeout.connect(self.update_loading_text)
        self.dot_timer.start(500)
        self.current_step = 0
        self.total_steps = 6
    
    def update_loading_text(self):
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.loading_label.setText(f"Loading{dots}")
        self.repaint()
    
    def drawContents(self, painter):
        self.container.render(painter)
        
    def showMessage(self, message, alignment=Qt.AlignmentFlag.AlignLeft, color=Qt.GlobalColor.white):
        self.loading_label.setText(message)
        self.current_step += 1
        progress = min(int((self.current_step / self.total_steps) * 100), 100)
        self.progress_bar.setValue(progress)
        self.repaint()
        QApplication.processEvents()

class ElevenLabsBatchConverter(QMainWindow):
    """Main application window for the ElevenLabs Batch Converter."""
    
    def __init__(self):
        super().__init__()
        self.api = None
        self.worker = None
        self.voices = []
        self.api_key = keyring.get_password(APP_NAME, KEY_NAME) or ""
        self.saved_voice_id = keyring.get_password(APP_NAME, VOICE_KEY) or ""
        self.saved_model_id = keyring.get_password(APP_NAME, MODEL_KEY) or ""
        self.saved_output_format = keyring.get_password(APP_NAME, FORMAT_KEY) or ""
        self.voice_settings = {}
        self.load_voice_settings()
        self.setAcceptDrops(True)
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f"ElevenLabs Batch Voice Changer v{APP_VERSION}")
        self.setMinimumSize(800, 600)
        self.resize(850, 1000)  # Set initial window size
        
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        # Set stretch factors: API settings and title remain fixed,
        # the splitter gets all extra vertical space.
        self.setCentralWidget(main_widget)

                # Set application style
        self.setStyleSheet("""
            QPushButton {
                padding: 5px;
                border-radius: 4px;
                background-color: #2c3e50;
                color: white;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        
        # Title
        title_label = QLabel("ElevenLabs Batch Voice Changer")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label, 0)
        
        # API Key settings
        api_key_group = QGroupBox("API Settings")
        api_key_layout = QFormLayout(api_key_group)
        self.api_key_input = QLineEdit(self.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your ElevenLabs API key here")
        api_key_layout.addRow("API Key:", self.api_key_input)
        api_key_buttons = QHBoxLayout()
        self.toggle_visibility_btn = QPushButton("Show/Hide Key")
        self.toggle_visibility_btn = self.style_button(self.toggle_visibility_btn, 'fa5s.eye', "Show/Hide Key")
        self.toggle_visibility_btn.clicked.connect(self.toggle_api_key_visibility)
        api_key_buttons.addWidget(self.toggle_visibility_btn)
        self.connect_api_btn = QPushButton("Connect")
        self.connect_api_btn = self.style_button(self.connect_api_btn, 'fa5s.plug', "Connect")
        self.connect_api_btn.clicked.connect(self.connect_api)
        api_key_buttons.addWidget(self.connect_api_btn)
        self.save_key_btn = QPushButton("Save Key")
        self.save_key_btn = self.style_button(self.save_key_btn, 'fa5s.save', "Save Key")
        self.save_key_btn.clicked.connect(self.save_api_key)
        api_key_buttons.addWidget(self.save_key_btn)
        api_key_layout.addRow("", api_key_buttons)
        self.credits_label = QLabel("Credits: Not connected")
        credits_font = QFont()
        credits_font.setBold(True)
        self.credits_label.setFont(credits_font)
        api_key_layout.addRow("", self.credits_label)
        main_layout.addWidget(api_key_group, 0)
        
        # Splitter for Audio Files and Voice Selection
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # Left panel - File selection
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        file_group = QGroupBox("Audio Files")
        file_layout = QVBoxLayout(file_group)
        self.file_list = DragDropListWidget(self)
        file_layout.addWidget(self.file_list)
        drag_drop_label = QLabel("Drag and drop audio files here")
        drag_drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_drop_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        file_layout.addWidget(drag_drop_label)
        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn = self.style_button(self.add_files_btn, 'fa5s.file-audio', "Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        file_buttons.addWidget(self.add_files_btn)
        self.remove_file_btn = QPushButton("Remove Selected")
        self.remove_file_btn = self.style_button(self.remove_file_btn, 'fa5s.trash-alt', "Remove Selected")
        self.remove_file_btn.clicked.connect(self.remove_selected_file)
        file_buttons.addWidget(self.remove_file_btn)
        self.clear_files_btn = QPushButton("Clear All")
        self.clear_files_btn = self.style_button(self.clear_files_btn, 'fa5s.times-circle', "Clear All")
        self.clear_files_btn.clicked.connect(self.clear_files)
        file_buttons.addWidget(self.clear_files_btn)
        file_layout.addLayout(file_buttons)
        left_layout.addWidget(file_group)
        
        # Right panel - Voice selection and conversion
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        voice_group = QGroupBox("Voice Selection")
        voice_layout = QVBoxLayout(voice_group)
        voice_layout.addWidget(QLabel("Select Voice:"))
        self.voice_combo = QComboBox()
        self.voice_combo.currentIndexChanged.connect(self.load_voice_specific_settings)
        self.voice_combo.currentIndexChanged.connect(self.auto_save_preferences)
        voice_layout.addWidget(self.voice_combo)
        voice_layout.addWidget(QLabel("Select Model:"))
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self.auto_save_preferences)
        voice_layout.addWidget(self.model_combo)
        voice_layout.addWidget(QLabel("Output Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("MP3 (44.1kHz, 128kbps)", "mp3_44100_128")
        self.format_combo.addItem("MP3 (44.1kHz, 192kbps)", "mp3_44100_192")
        self.format_combo.addItem("MP3 (44.1kHz, 256kbps)", "mp3_44100_256")
        self.format_combo.addItem("FLAC (16-bit, 44.1kHz)", "flac_16")
        self.format_combo.addItem("FLAC (24-bit, 44.1kHz)", "flac_24")
        self.format_combo.addItem("FLAC (32-bit, 44.1kHz)", "flac_32")
        self.format_combo.addItem("WAV (16-bit, 44.1kHz)", "pcm_16000")
        self.format_combo.addItem("WAV (24-bit, 44.1kHz)", "pcm_24000")
        self.format_combo.addItem("WAV (32-bit, 44.1kHz - Wwise Compatible)", "pcm_32000")
        self.format_combo.setCurrentIndex(0)
        self.format_combo.currentIndexChanged.connect(self.auto_save_preferences)
        self.format_combo.setToolTip("Select the output audio format and quality.\n"
                                     "MP3: Smaller file size, good for most uses.\n"
                                     "FLAC: Lossless compression, excellent quality with smaller file size than WAV.\n"
                                     "WAV: Uncompressed lossless quality, larger file size.\n"
                                     "32-bit WAV is recommended for Wwise compatibility.")
        voice_layout.addWidget(self.format_combo)
        settings_group = QGroupBox("Voice Model Settings")
        settings_layout = QFormLayout(settings_group)
        self.stability_label = QLabel("Stability: 0.5")
        self.stability_slider = QSlider(Qt.Orientation.Horizontal)
        self.stability_slider.setRange(0, 100)
        self.stability_slider.setValue(50)
        self.stability_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.stability_slider.setTickInterval(10)
        self.stability_slider.valueChanged.connect(self.update_stability_label)
        self.stability_slider.valueChanged.connect(self.auto_save_preferences)
        settings_layout.addRow(self.stability_label, self.stability_slider)
        self.similarity_label = QLabel("Similarity Boost: 0.75")
        self.similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_slider.setRange(0, 100)
        self.similarity_slider.setValue(75)
        self.similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        self.similarity_slider.valueChanged.connect(self.update_similarity_label)
        self.similarity_slider.valueChanged.connect(self.auto_save_preferences)
        settings_layout.addRow(self.similarity_label, self.similarity_slider)
        self.style_label = QLabel("Style Exaggeration: 0.0")
        self.style_slider = QSlider(Qt.Orientation.Horizontal)
        self.style_slider.setRange(0, 100)
        self.style_slider.setValue(0)
        self.style_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.style_slider.setTickInterval(10)
        self.style_slider.valueChanged.connect(self.update_style_label)
        self.style_slider.valueChanged.connect(self.auto_save_preferences)
        settings_layout.addRow(self.style_label, self.style_slider)
        voice_layout.addWidget(settings_group)
        self.speaker_boost_checkbox = QCheckBox("Speaker Boost")
        self.speaker_boost_checkbox.setChecked(True)
        self.speaker_boost_checkbox.setToolTip("Enhance the target speaker's voice")
        self.speaker_boost_checkbox.stateChanged.connect(self.auto_save_preferences)
        voice_layout.addWidget(self.speaker_boost_checkbox)
        self.remove_noise_checkbox = QCheckBox("Remove Silence")
        self.remove_noise_checkbox.setChecked(False)
        self.remove_noise_checkbox.setToolTip("Remove silence and background noise from the audio")
        self.remove_noise_checkbox.stateChanged.connect(self.auto_save_preferences)
        voice_layout.addWidget(self.remove_noise_checkbox)
        self.refresh_voices_btn = QPushButton("Refresh Voices")
        self.refresh_voices_btn = self.style_button(self.refresh_voices_btn, 'fa5s.sync', "Refresh Voices")
        self.refresh_voices_btn.clicked.connect(self.load_voices)
        voice_layout.addWidget(self.refresh_voices_btn)
        right_layout.addWidget(voice_group)
        conversion_group = QGroupBox("Conversion")
        conversion_layout = QVBoxLayout(conversion_group)
        conversion_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        conversion_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Enter your API key and click Connect to start")
        conversion_layout.addWidget(self.status_label)
        conversion_layout.addWidget(QLabel("Conversion Results:"))
        self.results_list = QListWidget()
        conversion_layout.addWidget(self.results_list)
        control_buttons = QHBoxLayout()
        self.start_btn = QPushButton("Start Conversion")
        self.start_btn = self.style_button(self.start_btn, 'fa5s.play', "Start Conversion", icon_color='#2ecc71')
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        control_buttons.addWidget(self.start_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn = self.style_button(self.cancel_btn, 'fa5s.stop', "Cancel", icon_color='#e74c3c')
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        self.cancel_btn.setEnabled(False)
        control_buttons.addWidget(self.cancel_btn)
        conversion_layout.addLayout(control_buttons)
        right_layout.addWidget(conversion_group)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_panel)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_scroll)
        splitter.setSizes([400, 400])
        main_layout.addWidget(splitter, 1)
        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn = self.style_button(self.open_output_btn, 'fa5s.folder-open', "Open Output Folder")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        main_layout.addWidget(self.open_output_btn, 0)
        
        if self.api_key:
            self.connect_api()
        
        self.voice_combo.currentIndexChanged.connect(self.load_voice_specific_settings)
    
    def style_button(self, button, icon_name, tooltip="", icon_color='white'):
        button.setIcon(qta.icon(icon_name, color=icon_color))
        button.setIconSize(QSize(16, 16))
        if tooltip:
            button.setToolTip(tooltip)
        return button
    
    def toggle_api_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_visibility_btn.setIcon(self.style_button(QPushButton(), 'fa5s.eye-slash').icon())
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_visibility_btn.setIcon(self.style_button(QPushButton(), 'fa5s.eye').icon())
    
    def save_api_key(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Empty API Key", "Please enter an API key to save.")
            return
        try:
            keyring.set_password(APP_NAME, KEY_NAME, api_key)
            QMessageBox.information(self, "Success", "API key saved securely to your system!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save API key: {str(e)}")
    
    def auto_save_preferences(self):
        if (self.voice_combo.count() > 0 and 
            self.model_combo.count() > 0 and 
            self.format_combo.count() > 0 and
            self.api is not None):
            self.save_preferences()
    
    def save_preferences(self):
        try:
            if self.voice_combo.currentData():
                keyring.set_password(APP_NAME, VOICE_KEY, self.voice_combo.currentData())
            if self.model_combo.currentData():
                keyring.set_password(APP_NAME, MODEL_KEY, self.model_combo.currentData())
            if self.format_combo.currentData():
                keyring.set_password(APP_NAME, FORMAT_KEY, self.format_combo.currentData())
            voice_id = self.voice_combo.currentData()
            if voice_id:
                if voice_id not in self.voice_settings:
                    self.voice_settings[voice_id] = {}
                self.voice_settings[voice_id] = {
                    'stability': self.stability_slider.value() / 100.0,
                    'similarity_boost': self.similarity_slider.value() / 100.0,
                    'style': self.style_slider.value() / 100.0,
                    'speaker_boost': self.speaker_boost_checkbox.isChecked(),
                    'remove_silence': self.remove_noise_checkbox.isChecked()
                }
                self.save_voice_settings()
            logger.info("Saved preferences to keyring")
        except Exception as e:
            logger.error(f"Error saving preferences: {str(e)}")
    
    def connect_api(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Empty API Key", "Please enter your ElevenLabs API key.")
            return
        self.status_label.setText("Connecting to ElevenLabs API...")
        QApplication.processEvents()
        try:
            self.api = ElevenLabsAPI(api_key=api_key)
            self.update_credits_display()
            self.load_voices()
            self.start_btn.setEnabled(True)
            self.voice_combo.setEnabled(True)
            self.refresh_voices_btn.setEnabled(True)
        except ValueError as e:
            QMessageBox.critical(self, "API Key Error", f"Error initializing ElevenLabs API: {str(e)}")
            self.status_label.setText("API connection failed. Check your key.")
    
    def update_credits_display(self):
        if not self.api:
            self.credits_label.setText("Credits: Not connected")
            return
        try:
            credits_info = self.api.get_remaining_credits()
            if credits_info:
                tier = credits_info.get("tier", "Unknown")
                used = credits_info.get("character_count", 0)
                limit = credits_info.get("character_limit", 0)
                remaining = credits_info.get("remaining_characters", 0)
                credits_text = f"Credits: {remaining:,} / {limit:,} characters remaining ({tier} tier)"
                self.credits_label.setText(credits_text)
                if remaining < limit * 0.1:
                    self.credits_label.setStyleSheet("color: red;")
                elif remaining < limit * 0.25:
                    self.credits_label.setStyleSheet("color: orange;")
                else:
                    self.credits_label.setStyleSheet("color: green;")
            else:
                self.credits_label.setText("Credits: Unable to retrieve")
                self.credits_label.setStyleSheet("")
        except Exception as e:
            logger.error(f"Error updating credits display: {str(e)}")
            self.credits_label.setText("Credits: Error retrieving")
            self.credits_label.setStyleSheet("")
    
    def load_voices(self):
        if not self.api:
            return
        self.status_label.setText("Loading voices...")
        QApplication.processEvents()
        try:
            try:
                self.voice_combo.currentIndexChanged.disconnect(self.load_voice_specific_settings)
            except TypeError:
                pass
            try:
                self.voice_combo.currentIndexChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.model_combo.currentIndexChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.format_combo.currentIndexChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            self.voices = self.api.get_voice_options()
            self.voice_combo.clear()
            if not self.voices:
                self.status_label.setText("No voices found. Check your API key and connection.")
                return
            found_saved_voice = False
            saved_voice_index = 0
            for i, voice in enumerate(self.voices):
                self.voice_combo.addItem(voice["name"], voice["id"])
                if voice["id"] == self.saved_voice_id:
                    found_saved_voice = True
                    saved_voice_index = i
            self.model_combo.clear()
            models = self.api.get_model_options()
            found_saved_model = False
            saved_model_index = 0
            for i, model in enumerate(models):
                self.model_combo.addItem(model["name"], model["id"])
                if model["id"] == self.saved_model_id:
                    found_saved_model = True
                    saved_model_index = i
            if self.saved_output_format:
                try:
                    self.format_combo.currentIndexChanged.disconnect(self.auto_save_preferences)
                except TypeError:
                    pass
                for i in range(self.format_combo.count()):
                    if self.format_combo.itemData(i) == self.saved_output_format:
                        self.format_combo.setCurrentIndex(i)
                        break
                self.format_combo.currentIndexChanged.connect(self.auto_save_preferences)
            self.update_credits_display()
            self.voice_combo.currentIndexChanged.connect(self.load_voice_specific_settings)
            self.voice_combo.currentIndexChanged.connect(self.auto_save_preferences)
            self.model_combo.currentIndexChanged.connect(self.auto_save_preferences)
            self.status_label.setText(f"Loaded {len(self.voices)} voices and {len(models)} models")
            if found_saved_model:
                self.model_combo.setCurrentIndex(saved_model_index)
            if found_saved_voice:
                self.voice_combo.setCurrentIndex(saved_voice_index)
            else:
                self.load_voice_specific_settings()
        except Exception as e:
            try:
                self.voice_combo.currentIndexChanged.connect(self.load_voice_specific_settings)
                self.voice_combo.currentIndexChanged.connect(self.auto_save_preferences)
                self.model_combo.currentIndexChanged.connect(self.auto_save_preferences)
                self.format_combo.currentIndexChanged.connect(self.auto_save_preferences)
            except:
                pass
            self.status_label.setText(f"Error loading voices: {str(e)}")
            logger.error(f"Error loading voices: {str(e)}")
    
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
        )
        for file_path in files:
            self.file_list._add_file(file_path)
        self.file_list.update_indices()
    
    def remove_selected_file(self):
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            widget = self.file_list.itemWidget(item)
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
            self.file_list.takeItem(self.file_list.row(item))
        self.file_list.update_indices()
    
    def clear_files(self):
        for i in range(self.file_list.count()):
            widget = self.file_list.itemWidget(self.file_list.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
        self.file_list.clear()
    
    def update_stability_label(self, value):
        stability_value = value / 100.0
        self.stability_label.setText(f"Stability: {stability_value:.2f}")
    
    def update_similarity_label(self, value):
        similarity_value = value / 100.0
        self.similarity_label.setText(f"Similarity Boost: {similarity_value:.2f}")
    
    def update_style_label(self, value):
        style_value = value / 100.0
        self.style_label.setText(f"Style Exaggeration: {style_value:.2f}")
    
    def start_conversion(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files", "Please add files to convert.")
            return
        if self.voice_combo.count() == 0:
            QMessageBox.warning(self, "No Voice Selected", "Please select a voice for conversion.")
            return
        voice_id = self.voice_combo.currentData()
        model_id = self.model_combo.currentData()
        speaker_boost = self.speaker_boost_checkbox.isChecked()
        remove_background_noise = self.remove_noise_checkbox.isChecked()
        stability = self.stability_slider.value() / 100.0
        similarity_boost = self.similarity_slider.value() / 100.0
        style = self.style_slider.value() / 100.0
        output_format = self.format_combo.currentData()
        file_paths = [self.file_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.file_list.count())]
        self.results_list.clear()
        self.status_label.setText("Converting...")
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.add_files_btn.setEnabled(False)
        self.remove_file_btn.setEnabled(False)
        self.clear_files_btn.setEnabled(False)
        self.voice_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.speaker_boost_checkbox.setEnabled(False)
        self.remove_noise_checkbox.setEnabled(False)
        self.stability_slider.setEnabled(False)
        self.similarity_slider.setEnabled(False)
        self.style_slider.setEnabled(False)
        self.refresh_voices_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.worker = ConversionWorker(
            self.api, 
            voice_id, 
            file_paths,
            model_id,
            speaker_boost,
            remove_background_noise,
            stability,
            similarity_boost,
            style,
            output_format
        )
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.conversion_complete.connect(self.add_conversion_result)
        self.worker.conversion_finished.connect(self.conversion_finished)
        self.worker.start()
    
    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
    
    def update_progress(self, current, total):
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.status_label.setText(f"Converting file {current+1} of {total}")
    
    def add_conversion_result(self, file_path, success, token_info):
        file_name = os.path.basename(file_path)
        item = QListWidgetItem()
        ellipsified_name = self.ellipsify_filename(file_name, 30)
        token_text = ""
        if success and token_info:
            if 'characters_used' in token_info:
                token_text = f" ({token_info['characters_used']} chars)"
            elif 'estimated_characters' in token_info:
                token_text = f" (~{token_info['estimated_characters']} chars)"
        if success:
            item.setText(f"✓ {ellipsified_name}{token_text}")
            item.setForeground(Qt.GlobalColor.darkGreen)
            self.update_credits_display()
            QApplication.processEvents()
        else:
            item.setText(f"✗ {ellipsified_name}")
            item.setForeground(Qt.GlobalColor.red)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.results_list.addItem(item)
        self.results_list.scrollToItem(item)
    
    def conversion_finished(self):
        self.progress_bar.setValue(100)
        self.start_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.remove_file_btn.setEnabled(True)
        self.clear_files_btn.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.format_combo.setEnabled(True)
        self.speaker_boost_checkbox.setEnabled(True)
        self.remove_noise_checkbox.setEnabled(True)
        self.stability_slider.setEnabled(True)
        self.similarity_slider.setEnabled(True)
        self.style_slider.setEnabled(True)
        self.refresh_voices_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        success_count = 0
        failed_count = 0
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            if "✓" in item.text():
                success_count += 1
            else:
                failed_count += 1
        if failed_count == 0:
            self.status_label.setText(f"Conversion complete! {success_count} files converted successfully.")
        else:
            self.status_label.setText(f"Conversion complete with issues. {success_count} succeeded, {failed_count} failed.")
        QMessageBox.information(
            self,
            "Conversion Complete",
            f"Conversion process finished.\n\nSuccessfully converted: {success_count} files\nFailed conversions: {failed_count} files\n\nOutput files are saved in the 'output' folder with their original filenames."
        )
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def open_output_folder(self):
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        os.startfile(output_dir)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if self.file_list:
            self.file_list.dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        if self.file_list:
            self.file_list.dragMoveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        if self.file_list:
            self.file_list.dropEvent(event)
    
    def closeEvent(self, event):
        for i in range(self.file_list.count()):
            widget = self.file_list.itemWidget(self.file_list.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
        event.accept()
    
    def ellipsify_filename(self, filename, max_length=30):
        if len(filename) <= max_length:
            return filename
        name, ext = os.path.splitext(filename)
        chars_to_keep = max_length - 3 - len(ext)
        if chars_to_keep < 1:
            return filename[:max_length-3] + "..."
        return name[:chars_to_keep] + "..." + ext
    
    def load_voice_settings(self):
        try:
            settings_json = keyring.get_password(APP_NAME, VOICE_SETTINGS_KEY)
            if settings_json:
                self.voice_settings = json.loads(settings_json)
            else:
                self.voice_settings = {}
            logger.info(f"Loaded settings for {len(self.voice_settings)} voices")
        except Exception as e:
            logger.error(f"Error loading voice settings: {str(e)}")
            self.voice_settings = {}
    
    def save_voice_settings(self):
        try:
            settings_json = json.dumps(self.voice_settings)
            keyring.set_password(APP_NAME, VOICE_SETTINGS_KEY, settings_json)
            logger.info(f"Saved settings for {len(self.voice_settings)} voices")
        except Exception as e:
            logger.error(f"Error saving voice settings: {str(e)}")
    
    def load_voice_specific_settings(self):
        voice_id = self.voice_combo.currentData()
        if not voice_id:
            return
        try:
            try:
                self.stability_slider.valueChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.similarity_slider.valueChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.style_slider.valueChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.speaker_boost_checkbox.stateChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            try:
                self.remove_noise_checkbox.stateChanged.disconnect(self.auto_save_preferences)
            except TypeError:
                pass
            if voice_id in self.voice_settings:
                settings = self.voice_settings[voice_id]
                if 'stability' in settings:
                    value = int(float(settings['stability']) * 100)
                    self.stability_slider.setValue(value)
                    self.update_stability_label(value)
                if 'similarity_boost' in settings:
                    value = int(float(settings['similarity_boost']) * 100)
                    self.similarity_slider.setValue(value)
                    self.update_similarity_label(value)
                if 'style' in settings:
                    value = int(float(settings['style']) * 100)
                    self.style_slider.setValue(value)
                    self.update_style_label(value)
                if 'speaker_boost' in settings:
                    self.speaker_boost_checkbox.setChecked(settings['speaker_boost'])
                if 'remove_silence' in settings:
                    self.remove_noise_checkbox.setChecked(settings['remove_silence'])
                logger.info(f"Loaded settings for voice {voice_id}")
            else:
                self.stability_slider.setValue(50)
                self.update_stability_label(50)
                self.similarity_slider.setValue(75)
                self.update_similarity_label(75)
                self.style_slider.setValue(0)
                self.update_style_label(0)
                self.speaker_boost_checkbox.setChecked(True)
                self.remove_noise_checkbox.setChecked(False)
                logger.info(f"Applied default settings for new voice {voice_id}")
                self.save_preferences()
            self.stability_slider.valueChanged.connect(self.auto_save_preferences)
            self.similarity_slider.valueChanged.connect(self.auto_save_preferences)
            self.style_slider.valueChanged.connect(self.auto_save_preferences)
            self.speaker_boost_checkbox.stateChanged.connect(self.auto_save_preferences)
            self.remove_noise_checkbox.stateChanged.connect(self.auto_save_preferences)
        except Exception as e:
            try:
                self.stability_slider.valueChanged.connect(self.auto_save_preferences)
                self.similarity_slider.valueChanged.connect(self.auto_save_preferences)
                self.style_slider.valueChanged.connect(self.auto_save_preferences)
                self.speaker_boost_checkbox.stateChanged.connect(self.auto_save_preferences)
                self.remove_noise_checkbox.stateChanged.connect(self.auto_save_preferences)
            except:
                pass
            logger.error(f"Error loading voice settings: {str(e)}")

def create_logo_file():
    logo_dir = Path("resources")
    logo_dir.mkdir(exist_ok=True)
    logo_path = logo_dir / "logo.png"
    if not logo_path.exists():
        try:
            logo_pixmap = QPixmap(200, 200)
            logo_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(logo_pixmap)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2c3e50"))
            painter.drawEllipse(25, 25, 150, 150)
            mic_icon = qta.icon('fa5s.microphone-alt', color='#3498db')
            mic_pixmap = mic_icon.pixmap(100, 100)
            wave_icon = qta.icon('fa5s.wave-square', color='#2ecc71')
            wave_pixmap = wave_icon.pixmap(80, 80)
            painter.drawPixmap(50, 30, mic_pixmap)
            painter.drawPixmap(60, 110, wave_pixmap)
            painter.setPen(QColor("white"))
            font = QFont()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(50, 180, "ElevenLabs")
            painter.end()
            logo_pixmap.save(str(logo_path))
            logger.info(f"Created logo file at {logo_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating logo file: {str(e)}")
            return False
    return True

def main():
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app_icon = qta.icon('fa5s.microphone-alt', color='#3498db')
    app.setWindowIcon(app_icon)
    window = ElevenLabsBatchConverter()
    splash = SplashScreen()
    splash.show()
    QTimer.singleShot(500, lambda: splash.showMessage("Initializing application...", Qt.AlignmentFlag.AlignCenter))
    def create_resources():
        splash.showMessage("Creating resources...", Qt.AlignmentFlag.AlignCenter)
        create_logo_file()
    QTimer.singleShot(1000, create_resources)
    QTimer.singleShot(1500, lambda: splash.showMessage("Creating user interface...", Qt.AlignmentFlag.AlignCenter))
    QTimer.singleShot(2000, lambda: splash.showMessage("Checking for saved credentials...", Qt.AlignmentFlag.AlignCenter))
    def setup_filesystem():
        splash.showMessage("Setting up file system...", Qt.AlignmentFlag.AlignCenter)
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
    QTimer.singleShot(2500, setup_filesystem)
    QTimer.singleShot(3000, lambda: splash.showMessage("Ready to launch!", Qt.AlignmentFlag.AlignCenter))
    def finish_splash():
        splash.finish(window)
        window.show()
    QTimer.singleShot(3500, finish_splash)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
