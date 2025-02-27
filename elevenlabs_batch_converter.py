import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QListWidget,
    QProgressBar, QMessageBox, QGroupBox, QListWidgetItem, QStyle,
    QSplitter, QFrame, QLineEdit, QFormLayout, QCheckBox, QSlider,
    QSizePolicy, QStyledItemDelegate, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QMimeData
from PyQt6.QtGui import QIcon, QFont, QColor, QDragEnterEvent, QDropEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import keyring
import qtawesome as qta
import mutagen
from mutagen.wave import WAVE
import time

from elevenlabs_api import ElevenLabsAPI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchConverter")

# Constants for keyring
APP_NAME = "ElevenLabsBatchConverter"
KEY_NAME = "ElevenLabsAPIKey"

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
                border-radius: 18px;  /* Adjusted for larger button */
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
            # Try using mutagen for common audio formats
            if self.file_path.lower().endswith('.wav'):
                audio = WAVE(self.file_path)
                return audio.info.length
            else:
                # For other formats
                audio = mutagen.File(self.file_path)
                if audio is not None:
                    return audio.info.length
            
            # Fallback: estimate based on file size (very rough)
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
        # Stop all other audio files
        parent_list = self.parent()
        while parent_list and not isinstance(parent_list, QListWidget):
            parent_list = parent_list.parent()
        
        if parent_list:
            # Stop all other audio widgets
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
        """Handle when the media source changes."""
        pass
    
    def handle_state_changed(self, state):
        """Handle when the playback state changes."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.is_playing = True
            self.play_button.setIcon(qta.icon('fa5s.pause', color='white'))
            # Show progress bar and position label during playback
            self.progress_bar.setVisible(True)
            self.position_label.setVisible(True)
        else:
            self.is_playing = False
            self.play_button.setIcon(qta.icon('fa5s.play', color='white'))
            # Hide progress bar when not playing
            if state == QMediaPlayer.PlaybackState.StoppedState:
                self.progress_bar.setVisible(False)
                self.position_label.setVisible(False)
                self.progress_bar.setValue(0)
                
    def handle_error(self, error, error_string):
        """Handle media player errors."""
        logging.error(f"Media player error: {error_string}")
        QMessageBox.warning(self, "Playback Error", 
                          f"Error playing audio file: {error_string}")

    def update_position(self, position):
        """Update the position indicator."""
        if self.player.duration() > 0:
            progress = int((position / self.player.duration()) * 100)
            self.progress_bar.setValue(progress)
            
            # Update position label
            position_str = self.format_duration(position / 1000)  # Convert ms to seconds
            duration_str = self.format_duration(self.player.duration() / 1000)
            self.position_label.setText(f"{position_str} / {duration_str}")

    def update_duration(self, duration):
        """Update the duration display when media is loaded."""
        if duration > 0:
            self.duration = duration / 1000  # Convert ms to seconds
            duration_str = self.format_duration(self.duration)
            self.duration_label.setText(f"Duration: {duration_str}")
            
            # Reset position display
            self.position_label.setText(f"0:00 / {duration_str}")
            self.progress_bar.setValue(0)

    def seek_to_position(self, percent):
        """Seek to a position in the audio file."""
        if self.player.duration() > 0:
            # Calculate the position in milliseconds
            position = int((percent / 100.0) * self.player.duration())
            self.player.setPosition(position)
            
            # If not playing, start playback
            if not self.is_playing:
                self.play()

    def set_index(self, index):
        """Update the index number."""
        self.index = index
        self.index_label.setText(f"{index+1}.")

    def ellipsify_filename(self, filename, max_length=40):
        """Ellipsify a filename while preserving the extension."""
        if len(filename) <= max_length:
            return filename
        
        # Split the filename into name and extension
        name, ext = os.path.splitext(filename)
        
        # Calculate how many characters we can keep from the name
        # We need to account for the ellipsis "..." (3 chars) and the extension
        chars_to_keep = max_length - 3 - len(ext)
        
        # If we can't even fit a single character plus ellipsis plus extension,
        # just truncate the whole thing
        if chars_to_keep < 1:
            return filename[:max_length-3] + "..."
        
        # Otherwise, keep the start of the name, add ellipsis, and keep the extension
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
        
        # Set item delegate properties for custom widgets
        self.setItemDelegate(QStyledItemDelegate())
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        # Set spacing between items
        self.setSpacing(2)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter events for files."""
        if event.mimeData().hasUrls():
            # Check if at least one file has an accepted extension
            for url in event.mimeData().urls():
                if self._is_accepted_file(url):
                    self._set_drag_active(True)
                    event.acceptProposedAction()
                    return
    
    def dragLeaveEvent(self, event):
        """Handle drag leave events."""
        self._set_drag_active(False)
        
    def dragMoveEvent(self, event):
        """Handle drag move events."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        """Handle drop events for files."""
        self._set_drag_active(False)
        
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            
            # Process the dropped files
            for url in event.mimeData().urls():
                if self._is_accepted_file(url):
                    self._add_file(url.toLocalFile())
            
            # Update indices after adding files
            self.update_indices()
    
    def _set_drag_active(self, active):
        """Set the drag active state and update the visual style."""
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
        """Check if the file has an accepted extension."""
        if not url.isLocalFile():
            return False
            
        file_path = url.toLocalFile()
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in self.accepted_extensions
    
    def _add_file(self, file_path: str):
        """Add a file to the list if it's not already there."""
        # Check if the file is already in the list
        existing_items = [self.item(i).data(Qt.ItemDataRole.UserRole) 
                         for i in range(self.count())]
        
        if file_path not in existing_items:
            # Create a custom widget for the audio file with the correct index
            audio_widget = AudioFileWidget(file_path, index=self.count())
            
            # Create a list item to hold the widget
            item = QListWidgetItem(self)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            
            # Set the size of the item to match the widget
            item.setSizeHint(audio_widget.sizeHint())
            
            # Add the item to the list
            self.addItem(item)
            
            # Set the widget for the item
            self.setItemWidget(item, audio_widget)

    def update_indices(self):
        """Update the indices of all audio file widgets."""
        for i in range(self.count()):
            widget = self.itemWidget(self.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.set_index(i)

class ConversionWorker(QThread):
    """Worker thread to handle audio conversion without blocking the UI."""
    progress_updated = pyqtSignal(int, int)  # (current, total)
    conversion_complete = pyqtSignal(str, bool)  # (file_path, success)
    conversion_finished = pyqtSignal()  # All conversions complete
    
    def __init__(self, api, voice_id, file_list, model_id, speaker_boost, remove_background_noise, 
                 stability, similarity_boost, style):
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
        self.is_cancelled = False
    
    def run(self):
        """Execute the conversion process for each file."""
        total_files = len(self.file_list)
        
        # Create output directory if it doesn't exist
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        for i, file_path in enumerate(self.file_list):
            if self.is_cancelled:
                break
                
            try:
                # Update progress
                self.progress_updated.emit(i, total_files)
                
                # Get the filename and create the output path
                file_name = os.path.basename(file_path)
                output_path = output_dir / f"{file_name}"
                
                # Convert the file
                audio_data = self.api.convert_speech_to_speech(
                    voice_id=self.voice_id,
                    audio_file_path=file_path,
                    model_id=self.model_id,
                    speaker_boost=self.speaker_boost,
                    remove_background_noise=self.remove_background_noise,
                    stability=self.stability,
                    similarity_boost=self.similarity_boost,
                    style=self.style
                )
                
                if audio_data:
                    # Save the converted audio
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    
                    self.conversion_complete.emit(str(output_path), True)
                else:
                    self.conversion_complete.emit(file_path, False)
            
            except Exception as e:
                logger.error(f"Error converting {file_path}: {str(e)}")
                self.conversion_complete.emit(file_path, False)
        
        self.progress_updated.emit(total_files, total_files)
        self.conversion_finished.emit()
    
    def cancel(self):
        """Cancel the conversion process."""
        self.is_cancelled = True

class ElevenLabsBatchConverter(QMainWindow):
    """Main application window for the ElevenLabs Batch Converter."""
    
    def __init__(self):
        super().__init__()
        self.api = None
        self.worker = None
        self.voices = []
        
        # Try to get API key from keyring
        self.api_key = keyring.get_password(APP_NAME, KEY_NAME) or ""
        
        # Enable drag and drop for the main window
        self.setAcceptDrops(True)
        
        self.init_ui()
        
    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("ElevenLabs Batch Voice Converter")
        self.setMinimumSize(800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
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
        title_label = QLabel("ElevenLabs Batch Voice Converter")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # API Key settings
        api_key_group = QGroupBox("API Settings")
        api_key_layout = QFormLayout(api_key_group)
        
        self.api_key_input = QLineEdit(self.api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter your ElevenLabs API key here")
        api_key_layout.addRow("API Key:", self.api_key_input)
        
        # Toggle visibility button for API key
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
        
        # Add credits display
        self.credits_label = QLabel("Credits: Not connected")
        credits_font = QFont()
        credits_font.setBold(True)
        self.credits_label.setFont(credits_font)
        api_key_layout.addRow("", self.credits_label)
        
        main_layout.addWidget(api_key_group)
        
        # Split the UI into left and right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - File selection
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        
        file_group = QGroupBox("Audio Files")
        file_layout = QVBoxLayout(file_group)
        
        # File list
        self.file_list = DragDropListWidget(self)
        file_layout.addWidget(self.file_list)
        
        # Add a label to indicate drag and drop functionality
        drag_drop_label = QLabel("Drag and drop audio files here")
        drag_drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drag_drop_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        file_layout.addWidget(drag_drop_label)
        
        # File buttons
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
        
        # Voice selection
        voice_group = QGroupBox("Voice Selection")
        voice_layout = QVBoxLayout(voice_group)
        
        voice_layout.addWidget(QLabel("Select Voice:"))
        self.voice_combo = QComboBox()
        voice_layout.addWidget(self.voice_combo)
        
        # Add model selection
        voice_layout.addWidget(QLabel("Select Model:"))
        self.model_combo = QComboBox()
        voice_layout.addWidget(self.model_combo)
        
        # Add voice model settings group
        settings_group = QGroupBox("Voice Model Settings")
        settings_layout = QFormLayout(settings_group)
        
        # Stability slider (0.0 to 1.0)
        self.stability_label = QLabel("Stability: 0.5")
        self.stability_slider = QSlider(Qt.Orientation.Horizontal)
        self.stability_slider.setRange(0, 100)
        self.stability_slider.setValue(50)  # Default 0.5
        self.stability_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.stability_slider.setTickInterval(10)
        self.stability_slider.valueChanged.connect(self.update_stability_label)
        settings_layout.addRow(self.stability_label, self.stability_slider)
        
        # Similarity Boost slider (0.0 to 1.0)
        self.similarity_label = QLabel("Similarity Boost: 0.75")
        self.similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_slider.setRange(0, 100)
        self.similarity_slider.setValue(75)  # Default 0.75
        self.similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        self.similarity_slider.valueChanged.connect(self.update_similarity_label)
        settings_layout.addRow(self.similarity_label, self.similarity_slider)
        
        # Style Exaggeration slider (0.0 to 1.0)
        self.style_label = QLabel("Style Exaggeration: 0.0")
        self.style_slider = QSlider(Qt.Orientation.Horizontal)
        self.style_slider.setRange(0, 100)
        self.style_slider.setValue(0)  # Default 0.0
        self.style_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.style_slider.setTickInterval(10)
        self.style_slider.valueChanged.connect(self.update_style_label)
        settings_layout.addRow(self.style_label, self.style_slider)
        
        voice_layout.addWidget(settings_group)
        
        # Add speaker boost option
        self.speaker_boost_checkbox = QCheckBox("Speaker Boost")
        self.speaker_boost_checkbox.setChecked(True)  # Default to enabled
        self.speaker_boost_checkbox.setToolTip("Enhance the target speaker's voice")
        voice_layout.addWidget(self.speaker_boost_checkbox)
        
        # Add background noise removal option
        self.remove_noise_checkbox = QCheckBox("Remove Silence")
        self.remove_noise_checkbox.setChecked(False)  # Default to disabled
        self.remove_noise_checkbox.setToolTip("Remove silence and background noise from the audio")
        voice_layout.addWidget(self.remove_noise_checkbox)
        
        self.refresh_voices_btn = QPushButton("Refresh Voices")
        self.refresh_voices_btn = self.style_button(self.refresh_voices_btn, 'fa5s.sync', "Refresh Voices")
        self.refresh_voices_btn.clicked.connect(self.load_voices)
        voice_layout.addWidget(self.refresh_voices_btn)
        
        right_layout.addWidget(voice_group)
        
        # Conversion controls
        conversion_group = QGroupBox("Conversion")
        conversion_layout = QVBoxLayout(conversion_group)
        
        # Progress bar
        conversion_layout.addWidget(QLabel("Progress:"))
        self.progress_bar = QProgressBar()
        conversion_layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("Enter your API key and click Connect to start")
        conversion_layout.addWidget(self.status_label)
        
        # Conversion results
        conversion_layout.addWidget(QLabel("Conversion Results:"))
        self.results_list = QListWidget()
        conversion_layout.addWidget(self.results_list)
        
        # Control buttons
        control_buttons = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Conversion")
        self.start_btn = self.style_button(self.start_btn, 'fa5s.play', "Start Conversion")
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)  # Disabled until API connected
        control_buttons.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn = self.style_button(self.cancel_btn, 'fa5s.stop', "Cancel")
        self.cancel_btn.clicked.connect(self.cancel_conversion)
        self.cancel_btn.setEnabled(False)
        control_buttons.addWidget(self.cancel_btn)
        
        conversion_layout.addLayout(control_buttons)
        right_layout.addWidget(conversion_group)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400])  # Equal initial sizes
        
        # Open output folder button
        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn = self.style_button(self.open_output_btn, 'fa5s.folder-open', "Open Output Folder")
        self.open_output_btn.clicked.connect(self.open_output_folder)
        main_layout.addWidget(self.open_output_btn)
        
        # If we already have an API key from keyring, connect automatically
        if self.api_key:
            self.connect_api()
    
    def style_button(self, button, icon_name, tooltip=""):
        """Apply a consistent style to a button with an icon."""
        button.setIcon(qta.icon(icon_name, color='white'))
        button.setIconSize(QSize(16, 16))
        if tooltip:
            button.setToolTip(tooltip)
        return button
    
    def toggle_api_key_visibility(self):
        """Toggle between showing and hiding the API key."""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_visibility_btn.setIcon(self.style_button(QPushButton(), 'fa5s.eye-slash').icon())
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_visibility_btn.setIcon(self.style_button(QPushButton(), 'fa5s.eye').icon())
    
    def save_api_key(self):
        """Save the current API key securely to the system keyring."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Empty API Key", "Please enter an API key to save.")
            return
        
        try:
            # Save the API key to the system keyring
            keyring.set_password(APP_NAME, KEY_NAME, api_key)
            
            QMessageBox.information(self, "Success", "API key saved securely to your system!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save API key: {str(e)}")
    
    def connect_api(self):
        """Initialize the ElevenLabs API with the current key and load voices."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Empty API Key", "Please enter your ElevenLabs API key.")
            return
        
        self.status_label.setText("Connecting to ElevenLabs API...")
        QApplication.processEvents()
        
        try:
            # Initialize API with the provided key
            self.api = ElevenLabsAPI(api_key=api_key)
            
            # Update credits display
            self.update_credits_display()
            
            # Load voices
            self.load_voices()
            
            # Enable controls that require the API
            self.start_btn.setEnabled(True)
            self.voice_combo.setEnabled(True)
            self.refresh_voices_btn.setEnabled(True)
            
        except ValueError as e:
            QMessageBox.critical(self, "API Key Error", 
                               f"Error initializing ElevenLabs API: {str(e)}")
            self.status_label.setText("API connection failed. Check your key.")
    
    def update_credits_display(self):
        """Update the credits display with current information from the API."""
        if not self.api:
            self.credits_label.setText("Credits: Not connected")
            return
            
        try:
            credits_info = self.api.get_remaining_credits()
            if credits_info:
                # Format the credits display
                tier = credits_info.get("tier", "Unknown")
                used = credits_info.get("character_count", 0)
                limit = credits_info.get("character_limit", 0)
                remaining = credits_info.get("remaining_characters", 0)
                
                # Create a formatted string with the credits information
                credits_text = f"Credits: {remaining:,} / {limit:,} characters remaining ({tier} tier)"
                self.credits_label.setText(credits_text)
                
                # Change color based on remaining credits
                if remaining < limit * 0.1:  # Less than 10% remaining
                    self.credits_label.setStyleSheet("color: red;")
                elif remaining < limit * 0.25:  # Less than 25% remaining
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
        """Load available voices from the API."""
        if not self.api:
            return
            
        self.status_label.setText("Loading voices...")
        QApplication.processEvents()
        
        try:
            # Load voices
            self.voices = self.api.get_voice_options()
            self.voice_combo.clear()
            
            if not self.voices:
                self.status_label.setText("No voices found. Check your API key and connection.")
                return
                
            for voice in self.voices:
                self.voice_combo.addItem(voice["name"], voice["id"])
            
            # Load models
            self.model_combo.clear()
            models = self.api.get_model_options()
            for model in models:
                self.model_combo.addItem(model["name"], model["id"])
                
            self.status_label.setText(f"Loaded {len(self.voices)} voices and {len(models)} models")
            
            # Update credits display after loading voices
            self.update_credits_display()
            
        except Exception as e:
            self.status_label.setText(f"Error loading voices: {str(e)}")
            logger.error(f"Error loading voices: {str(e)}")
    
    def add_files(self):
        """Open file dialog to select audio files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
        )
        
        for file_path in files:
            self.file_list._add_file(file_path)
        
        # Update indices after adding files
        self.file_list.update_indices()
    
    def remove_selected_file(self):
        """Remove the selected file from the list."""
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            # Stop playback if the item has a widget
            widget = self.file_list.itemWidget(item)
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
            
            self.file_list.takeItem(self.file_list.row(item))
        
        # Update indices after removing files
        self.file_list.update_indices()
    
    def clear_files(self):
        """Clear all files from the list."""
        # Stop playback for all items
        for i in range(self.file_list.count()):
            widget = self.file_list.itemWidget(self.file_list.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
        
        self.file_list.clear()
        # No need to update indices after clearing as there are no items left
    
    def update_stability_label(self, value):
        """Update the stability label when the slider changes."""
        stability_value = value / 100.0
        self.stability_label.setText(f"Stability: {stability_value:.2f}")
    
    def update_similarity_label(self, value):
        """Update the similarity boost label when the slider changes."""
        similarity_value = value / 100.0
        self.similarity_label.setText(f"Similarity Boost: {similarity_value:.2f}")
    
    def update_style_label(self, value):
        """Update the style exaggeration label when the slider changes."""
        style_value = value / 100.0
        self.style_label.setText(f"Style Exaggeration: {style_value:.2f}")
    
    def start_conversion(self):
        """Start the batch conversion process."""
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Files", "Please add files to convert.")
            return
            
        if self.voice_combo.count() == 0:
            QMessageBox.warning(self, "No Voice Selected", "Please select a voice for conversion.")
            return
            
        # Get the selected voice ID
        voice_id = self.voice_combo.currentData()
        
        # Get the selected model ID
        model_id = self.model_combo.currentData()
        
        # Get the speaker boost and noise removal settings
        speaker_boost = self.speaker_boost_checkbox.isChecked()
        remove_background_noise = self.remove_noise_checkbox.isChecked()
        
        # Get the voice model settings
        stability = self.stability_slider.value() / 100.0
        similarity_boost = self.similarity_slider.value() / 100.0
        style = self.style_slider.value() / 100.0
        
        # Get all file paths from the list
        file_paths = [self.file_list.item(i).data(Qt.ItemDataRole.UserRole) 
                      for i in range(self.file_list.count())]
        
        # Clear previous results
        self.results_list.clear()
        
        # Update UI
        self.status_label.setText("Converting...")
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.add_files_btn.setEnabled(False)
        self.remove_file_btn.setEnabled(False)
        self.clear_files_btn.setEnabled(False)
        self.voice_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.speaker_boost_checkbox.setEnabled(False)
        self.remove_noise_checkbox.setEnabled(False)
        self.stability_slider.setEnabled(False)
        self.similarity_slider.setEnabled(False)
        self.style_slider.setEnabled(False)
        self.refresh_voices_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # Create and start worker thread
        self.worker = ConversionWorker(
            self.api, 
            voice_id, 
            file_paths,
            model_id,
            speaker_boost,
            remove_background_noise,
            stability,
            similarity_boost,
            style
        )
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.conversion_complete.connect(self.add_conversion_result)
        self.worker.conversion_finished.connect(self.conversion_finished)
        self.worker.start()
    
    def cancel_conversion(self):
        """Cancel the current conversion process."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
    
    def update_progress(self, current, total):
        """Update the progress bar."""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.status_label.setText(f"Converting file {current+1} of {total}")
    
    def add_conversion_result(self, file_path, success):
        """Add a conversion result to the results list."""
        file_name = os.path.basename(file_path)
        item = QListWidgetItem()
        
        if success:
            item.setText(f"✓ {file_name}")
            item.setForeground(Qt.GlobalColor.darkGreen)
        else:
            item.setText(f"✗ {file_name}")
            item.setForeground(Qt.GlobalColor.red)
        
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.results_list.addItem(item)
    
    def conversion_finished(self):
        """Handle the completion of all conversions."""
        # Set progress bar to 100%
        self.progress_bar.setValue(100)
        
        # Re-enable UI elements
        self.start_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.remove_file_btn.setEnabled(True)
        self.clear_files_btn.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.speaker_boost_checkbox.setEnabled(True)
        self.remove_noise_checkbox.setEnabled(True)
        self.stability_slider.setEnabled(True)
        self.similarity_slider.setEnabled(True)
        self.style_slider.setEnabled(True)
        self.refresh_voices_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # Update credits display after conversion
        self.update_credits_display()
        
        # Count successful and failed conversions
        success_count = 0
        failed_count = 0
        
        for i in range(self.results_list.count()):
            item = self.results_list.item(i)
            if "✓" in item.text():
                success_count += 1
            else:
                failed_count += 1
        
        # Update status
        if failed_count == 0:
            self.status_label.setText(f"Conversion complete! {success_count} files converted successfully.")
        else:
            self.status_label.setText(
                f"Conversion complete with issues. {success_count} succeeded, {failed_count} failed."
            )
            
        # Show a message box with the results
        QMessageBox.information(
            self,
            "Conversion Complete",
            f"Conversion process finished.\n\n"
            f"Successfully converted: {success_count} files\n"
            f"Failed conversions: {failed_count} files\n\n"
            f"Output files are saved in the 'output' folder."
        )
        
        # Clean up the worker
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
    
    def open_output_folder(self):
        """Open the output folder in file explorer."""
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        
        # Use OS-specific command to open folder
        os.startfile(output_dir)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Forward drag enter events to the file list widget."""
        if self.file_list:
            self.file_list.dragEnterEvent(event)
    
    def dragMoveEvent(self, event):
        """Forward drag move events to the file list widget."""
        if self.file_list:
            self.file_list.dragMoveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """Forward drop events to the file list widget."""
        if self.file_list:
            self.file_list.dropEvent(event)

    def closeEvent(self, event):
        """Handle the window close event."""
        # Stop all audio playback
        for i in range(self.file_list.count()):
            widget = self.file_list.itemWidget(self.file_list.item(i))
            if widget and isinstance(widget, AudioFileWidget):
                widget.stop()
        
        # Accept the close event
        event.accept()

def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    
    # Set application icon
    app_icon = qta.icon('fa5s.microphone-alt', color='#3498db')
    app.setWindowIcon(app_icon)
    
    window = ElevenLabsBatchConverter()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 