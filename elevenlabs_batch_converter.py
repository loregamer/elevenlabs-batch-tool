import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QListWidget,
    QProgressBar, QMessageBox, QGroupBox, QListWidgetItem, QStyle,
    QSplitter, QFrame, QLineEdit, QFormLayout, QCheckBox, QSlider
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QFont
from dotenv import load_dotenv, set_key

from elevenlabs_api import ElevenLabsAPI

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BatchConverter")

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
                output_path = output_dir / f"converted_{file_name}"
                
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
        # Load environment variables to get API key if it exists
        load_dotenv()
        self.api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.init_ui()
        
    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("ElevenLabs Batch Voice Converter")
        self.setMinimumSize(800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
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
        self.toggle_visibility_btn.clicked.connect(self.toggle_api_key_visibility)
        api_key_buttons.addWidget(self.toggle_visibility_btn)
        
        self.connect_api_btn = QPushButton("Connect")
        self.connect_api_btn.clicked.connect(self.connect_api)
        api_key_buttons.addWidget(self.connect_api_btn)
        
        self.save_key_btn = QPushButton("Save Key")
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
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)
        
        # File buttons
        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files")
        self.add_files_btn.clicked.connect(self.add_files)
        file_buttons.addWidget(self.add_files_btn)
        
        self.remove_file_btn = QPushButton("Remove Selected")
        self.remove_file_btn.clicked.connect(self.remove_selected_file)
        file_buttons.addWidget(self.remove_file_btn)
        
        self.clear_files_btn = QPushButton("Clear All")
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
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)  # Disabled until API connected
        control_buttons.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
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
        self.open_output_btn.clicked.connect(self.open_output_folder)
        main_layout.addWidget(self.open_output_btn)
        
        # If we already have an API key from .env, connect automatically
        if self.api_key:
            self.connect_api()
    
    def toggle_api_key_visibility(self):
        """Toggle between showing and hiding the API key."""
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def save_api_key(self):
        """Save the current API key to the .env file."""
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Empty API Key", "Please enter an API key to save.")
            return
        
        try:
            # Check if .env file exists, if not create it
            env_path = Path('.env')
            if not env_path.exists():
                env_path.touch()
            
            # Save the API key to the .env file
            with open(env_path, 'w') as f:
                f.write(f"ELEVENLABS_API_KEY={api_key}")
            
            QMessageBox.information(self, "Success", "API key saved to .env file successfully!")
            
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
            # Check if the file is already in the list
            existing_items = [self.file_list.item(i).data(Qt.ItemDataRole.UserRole) 
                             for i in range(self.file_list.count())]
            
            if file_path not in existing_items:
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                self.file_list.addItem(item)
    
    def remove_selected_file(self):
        """Remove the selected file from the list."""
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            self.file_list.takeItem(self.file_list.row(item))
    
    def clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()
    
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

def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Use Fusion style for a modern look
    window = ElevenLabsBatchConverter()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 