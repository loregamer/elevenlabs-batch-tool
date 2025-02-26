import sys
import os
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QListWidget,
    QProgressBar, QMessageBox, QGroupBox, QListWidgetItem, QStyle,
    QSplitter, QFrame, QLineEdit, QFormLayout
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
    
    def __init__(self, api, voice_id, file_list):
        super().__init__()
        self.api = api
        self.voice_id = voice_id
        self.file_list = file_list
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
                    audio_file_path=file_path
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
            self.load_voices()
            
            # Enable controls that require the API
            self.start_btn.setEnabled(True)
            self.voice_combo.setEnabled(True)
            self.refresh_voices_btn.setEnabled(True)
            
        except ValueError as e:
            QMessageBox.critical(self, "API Key Error", 
                               f"Error initializing ElevenLabs API: {str(e)}")
            self.status_label.setText("API connection failed. Check your key.")
    
    def load_voices(self):
        """Load available voices from the API."""
        if not self.api:
            return
            
        self.status_label.setText("Loading voices...")
        QApplication.processEvents()
        
        try:
            self.voices = self.api.get_voice_options()
            self.voice_combo.clear()
            
            if not self.voices:
                self.status_label.setText("No voices found. Check your API key and connection.")
                return
                
            for voice in self.voices:
                self.voice_combo.addItem(voice["name"], voice["id"])
                
            self.status_label.setText(f"Loaded {len(self.voices)} voices")
            
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
        self.refresh_voices_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # Create and start worker thread
        self.worker = ConversionWorker(self.api, voice_id, file_paths)
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
        """Handle completion of the conversion process."""
        success_count = 0
        for i in range(self.results_list.count()):
            if "✓" in self.results_list.item(i).text():
                success_count += 1
        
        self.status_label.setText(f"Conversion complete. {success_count}/{self.results_list.count()} files succeeded.")
        
        # Re-enable controls
        self.start_btn.setEnabled(True)
        self.add_files_btn.setEnabled(True)
        self.remove_file_btn.setEnabled(True)
        self.clear_files_btn.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.refresh_voices_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # Show completion message
        QMessageBox.information(
            self, 
            "Conversion Complete", 
            f"Conversion process finished.\n\n"
            f"Successfully converted: {success_count}\n"
            f"Failed: {self.results_list.count() - success_count}\n\n"
            f"Converted files are saved in the 'output' folder."
        )
    
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