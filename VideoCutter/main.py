import sys
import os
import subprocess
import xml.etree.ElementTree as ET
import imageio_ffmpeg

from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QFrame,
    QStyle, QSlider
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

SETTINGS_FILE = "settings.xml"

def time_to_seconds(t_str):
    """Convert HH:MM:SS string to float seconds."""
    try:
        parts = t_str.strip().split(':')
        if len(parts) == 3:
            return sum(x * float(t) for x, t in zip([3600, 60, 1], parts))
        elif len(parts) == 2: # MM:SS
            return sum(x * float(t) for x, t in zip([60, 1], parts))
        elif len(parts) == 1: # SS
            return float(parts[0])
        return 0
    except ValueError:
        return 0

class VideoProcessorThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, source, destination, start_time, end_time):
        super().__init__()
        self.source = source
        self.destination = destination
        self.start_time = start_time.strip()
        self.end_time = end_time.strip()

    def run(self):
        try:
            self.progress.emit("Initializing FFmpeg...")
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            temp_dir = os.path.dirname(self.destination)
            if not temp_dir:
                temp_dir = "."
                
            base_name = os.path.splitext(os.path.basename(self.source))[0]
            part1_file = os.path.join(temp_dir, f"{base_name}_part1_temp.mp4").replace(os.sep, '/')
            part2_file = os.path.join(temp_dir, f"{base_name}_part2_temp.mp4").replace(os.sep, '/')
            list_file = os.path.join(temp_dir, f"{base_name}_concat_temp.txt").replace(os.sep, '/')

            parts_to_concat = []

            # Command 1: Extract part 1 (if start_time is greater than 0)
            if time_to_seconds(self.start_time) > 0:
                self.progress.emit("Extracting first segment (before cut)...")
                cmd1 = [
                    ffmpeg_exe, "-y", 
                    "-i", self.source, 
                    "-to", self.start_time, 
                    "-c", "copy", part1_file
                ]
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                res1 = subprocess.run(cmd1, capture_output=True, text=True, creationflags=creationflags)
                if res1.returncode != 0:
                    raise Exception(f"FFmpeg error (Part 1):\n{res1.stderr}")
                parts_to_concat.append(part1_file)

            # Command 2: Extract part 2 (from end_time to end of video)
            self.progress.emit("Extracting second segment (after cut)...")
            cmd2 = [
                ffmpeg_exe, "-y", 
                "-i", self.source, 
                "-ss", self.end_time, 
                "-c", "copy", part2_file
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            res2 = subprocess.run(cmd2, capture_output=True, text=True, creationflags=creationflags)
            if res2.returncode != 0:
                raise Exception(f"FFmpeg error (Part 2):\n{res2.stderr}")
            parts_to_concat.append(part2_file)

            if len(parts_to_concat) > 1:
                # Merge segments
                self.progress.emit("Merging segments...")
                with open(list_file, "w", encoding='utf-8') as f:
                    for p in parts_to_concat:
                        f.write(f"file '{p}'\n")

                cmd3 = [
                    ffmpeg_exe, "-y", 
                    "-f", "concat", 
                    "-safe", "0", 
                    "-i", list_file, 
                    "-c", "copy", self.destination
                ]
                res3 = subprocess.run(cmd3, capture_output=True, text=True, creationflags=creationflags)
                if res3.returncode != 0:
                    raise Exception(f"FFmpeg error (Concat):\n{res3.stderr}")
            else:
                # Only part 2 exists, so just rename/move it to destination
                self.progress.emit("Only one segment present. Finishing up...")
                if os.path.exists(self.destination):
                    try:
                        os.remove(self.destination)
                    except:
                        pass
                os.rename(part2_file, self.destination)

            # Cleanup
            self.progress.emit("Cleaning up temporary files...")
            for f in [part1_file, part2_file, list_file]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass # Ignore cleanup errors

            self.finished.emit(True, "Processing completed successfully!")
        except Exception as e:
            self.finished.emit(False, str(e))

class VideoCutterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Segment Remover")
        self.resize(800, 600)
        
        # Setup media player components
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.initUI()
        self.loadSettings()
        
        # Connect media player signals
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Video Player Area
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(350)
        self.media_player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget, 1)

        # Playback Controls
        control_layout = QHBoxLayout()
        
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        control_layout.addWidget(self.play_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        control_layout.addWidget(self.slider)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        control_layout.addWidget(self.time_label)

        layout.addLayout(control_layout)

        # Spacer
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line1)

        # Source Selection
        src_layout = QHBoxLayout()
        self.src_label = QLabel("Source Video:")
        self.src_label.setFixedWidth(100)
        self.src_input = QLineEdit()
        self.src_btn = QPushButton("Browse...")
        self.src_btn.clicked.connect(self.select_source)
        src_layout.addWidget(self.src_label)
        src_layout.addWidget(self.src_input)
        src_layout.addWidget(self.src_btn)
        layout.addLayout(src_layout)

        # Destination Selection
        dst_layout = QHBoxLayout()
        self.dst_label = QLabel("Output Video:")
        self.dst_label.setFixedWidth(100)
        self.dst_input = QLineEdit()
        self.dst_btn = QPushButton("Browse...")
        self.dst_btn.clicked.connect(self.select_destination)
        dst_layout.addWidget(self.dst_label)
        dst_layout.addWidget(self.dst_input)
        dst_layout.addWidget(self.dst_btn)
        layout.addLayout(dst_layout)

        # Cut Times
        time_layout = QHBoxLayout()
        self.from_label = QLabel("Remove From:")
        self.from_input = QLineEdit()
        self.from_input.setPlaceholderText("HH:MM:SS.mmm or SS.mmm")
        self.from_scissor_btn = QPushButton("✂")
        self.from_scissor_btn.setToolTip("Capture Current Time")
        self.from_scissor_btn.clicked.connect(lambda: self.capture_time(self.from_input))

        self.to_label = QLabel("Remove To:")
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("HH:MM:SS.mmm or SS.mmm")
        self.to_scissor_btn = QPushButton("✂")
        self.to_scissor_btn.setToolTip("Capture Current Time")
        self.to_scissor_btn.clicked.connect(lambda: self.capture_time(self.to_input))
        
        time_layout.addWidget(self.from_label)
        time_layout.addWidget(self.from_input)
        time_layout.addWidget(self.from_scissor_btn)
        time_layout.addSpacing(20)
        time_layout.addWidget(self.to_label)
        time_layout.addWidget(self.to_input)
        time_layout.addWidget(self.to_scissor_btn)
        layout.addLayout(time_layout)

        # Spacer
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line2)

        # Process Button & Status
        bottom_layout = QHBoxLayout()
        self.process_btn = QPushButton("Remove Segment")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.clicked.connect(self.start_processing)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray;")
        
        bottom_layout.addWidget(self.process_btn)
        bottom_layout.addWidget(self.status_label, 1) # stretch factor 1
        
        layout.addLayout(bottom_layout)

    def load_video(self, file_path):
        if file_path and os.path.exists(file_path):
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.media_player.play()
            self.play_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

    def set_position(self, position):
        self.media_player.setPosition(position)

    def position_changed(self, position):
        self.slider.setValue(position)
        self.update_time_label()

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.update_time_label()

    def update_time_label(self):
        pos = self.media_player.position()
        dur = self.media_player.duration()
        self.time_label.setText(f"{self.format_ms(pos)} / {self.format_ms(dur)}")

    def format_ms(self, ms):
        seconds = ms // 1000
        rem_ms = ms % 1000
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}.{rem_ms:03d}"

    def capture_time(self, input_field):
        ms = self.media_player.position()
        input_field.setText(self.format_ms(ms))

    def select_source(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Source Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)")
        if file:
            self.src_input.setText(file)
            self.load_video(file)
            
            # If destination is empty, auto-fill it
            if not self.dst_input.text():
                base, ext = os.path.splitext(file)
                self.dst_input.setText(f"{base}_edited{ext}")

    def select_destination(self):
        file, _ = QFileDialog.getSaveFileName(self, "Select Destination Video", "", "MP4 Video (*.mp4)")
        if file:
            self.dst_input.setText(file)

    def start_processing(self):
        src = self.src_input.text().strip()
        dst = self.dst_input.text().strip()
        start = self.from_input.text().strip()
        end = self.to_input.text().strip()

        if not src or not dst or not start or not end:
            QMessageBox.warning(self, "Validation Error", "Please fill in all fields.")
            return

        if not os.path.exists(src):
            QMessageBox.warning(self, "Validation Error", "Source file does not exist.")
            return

        if time_to_seconds(start) >= time_to_seconds(end):
            QMessageBox.warning(self, "Validation Error", "'Remove To' time must be greater than 'Remove From' time.")
            return

        # Save settings continuously when processing
        self.saveSettings()

        self.process_btn.setEnabled(False)
        self.status_label.setStyleSheet("color: blue;")
        self.status_label.setText("Preparing...")

        self.thread = VideoProcessorThread(src, dst, start, end)
        self.thread.progress.connect(self.update_status)
        self.thread.finished.connect(self.process_finished)
        self.thread.start()

    def update_status(self, msg):
        self.status_label.setText(msg)

    def process_finished(self, success, msg):
        self.process_btn.setEnabled(True)
        if success:
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.status_label.setText("Success!")
            QMessageBox.information(self, "Success", msg)
        else:
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.status_label.setText("Error occurred")
            QMessageBox.critical(self, "Error", msg)

    def loadSettings(self):
        """Loads settings from XML file if it exists."""
        if os.path.exists(SETTINGS_FILE):
            try:
                tree = ET.parse(SETTINGS_FILE)
                root = tree.getroot()

                src = root.findtext("SourceVideo")
                if src: 
                    self.src_input.setText(src)
                    self.load_video(src)

                dst = root.findtext("DestinationVideo")
                if dst: self.dst_input.setText(dst)

                start = root.findtext("RemoveFrom")
                if start: self.from_input.setText(start)

                end = root.findtext("RemoveTo")
                if end: self.to_input.setText(end)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def saveSettings(self):
        """Saves current fields to XML file."""
        try:
            root = ET.Element("Settings")
            
            src = ET.SubElement(root, "SourceVideo")
            src.text = self.src_input.text().strip()

            dst = ET.SubElement(root, "DestinationVideo")
            dst.text = self.dst_input.text().strip()

            start = ET.SubElement(root, "RemoveFrom")
            start.text = self.from_input.text().strip()

            end = ET.SubElement(root, "RemoveTo")
            end.text = self.to_input.text().strip()

            tree = ET.ElementTree(root)
            tree.write(SETTINGS_FILE, encoding='utf-8', xml_declaration=True)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def closeEvent(self, event):
        """Save settings when the application closes."""
        self.saveSettings()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Optional styling
    app.setStyle("Fusion")
    
    window = VideoCutterApp()
    window.show()
    sys.exit(app.exec())
