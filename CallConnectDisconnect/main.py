import sys
import os
import xml.etree.ElementTree as ET
import apdu_builder
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QTabWidget, QLineEdit, QTextEdit, QGroupBox, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt

try:
    from smartcard.System import readers
    from smartcard.util import toHexString
    HAS_PYSCARD = True
except ImportError:
    HAS_PYSCARD = False

class ETSITester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ETSI TS 102 223 Event Tester")
        self.resize(600, 600)
        self.connection = None
        
        self.init_ui()
        self.load_settings()
        if HAS_PYSCARD:
            self.refresh_readers()
        else:
            self.log_message("Warning: pyscard is not installed. APDUs will only be generated, not sent.")
            self.btn_connect.setEnabled(False)
            self.btn_refresh.setEnabled(False)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Reader Section ---
        reader_group = QGroupBox("Smart Card Reader")
        reader_layout = QHBoxLayout()
        
        self.cb_readers = QComboBox()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        
        self.btn_refresh.clicked.connect(self.refresh_readers)
        self.btn_connect.clicked.connect(self.connect_card)
        self.btn_disconnect.clicked.connect(self.disconnect_card)

        reader_layout.addWidget(QLabel("Select Reader:"))
        reader_layout.addWidget(self.cb_readers, 1)
        reader_layout.addWidget(self.btn_refresh)
        reader_layout.addWidget(self.btn_connect)
        reader_layout.addWidget(self.btn_disconnect)
        reader_group.setLayout(reader_layout)
        main_layout.addWidget(reader_group)

        # --- Event Tabs ---
        self.tabs = QTabWidget()
        
        # Settings Tab
        self.tab_settings = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.tab_settings, "Settings")

        # MT Call Tab
        self.tab_mt_call = QWidget()
        self.setup_mt_call_tab()
        self.tabs.addTab(self.tab_mt_call, "MT Call")

        # Call Connected Tab
        self.tab_call_connected = QWidget()
        self.setup_call_connected_tab()
        self.tabs.addTab(self.tab_call_connected, "Call Connected")

        # Call Disconnected Tab
        self.tab_call_disconnected = QWidget()
        self.setup_call_disconnected_tab()
        self.tabs.addTab(self.tab_call_disconnected, "Call Disconnected")
        
        main_layout.addWidget(self.tabs)

        # --- Log Section ---
        log_group = QGroupBox("Logs / APDU Trace")
        log_layout = QVBoxLayout()
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("font-family: monospace; background-color: #1e1e1e; color: #00ff00;")
        
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self.text_log.clear)
        
        btn_export_log = QPushButton("Export Log")
        btn_export_log.clicked.connect(self.export_log)
        
        log_btn_layout = QHBoxLayout()
        log_btn_layout.addStretch()
        log_btn_layout.addWidget(btn_export_log)
        log_btn_layout.addWidget(btn_clear_log)
        
        log_layout.addWidget(self.text_log)
        log_layout.addLayout(log_btn_layout)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(log_group, 1)

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        
        profile_group = QGroupBox("Terminal Profile")
        profile_layout = QVBoxLayout()
        
        label = QLabel("Terminal Profile (Hex):")
        profile_layout.addWidget(label)
        
        self.in_profile = QLineEdit("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
        self.in_profile.setPlaceholderText("e.g. FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
        profile_layout.addWidget(self.in_profile)
        
        btn_layout = QHBoxLayout()
        self.btn_send_profile = QPushButton("Send Terminal Profile Now")
        self.btn_send_profile.clicked.connect(self.send_terminal_profile)
        btn_layout.addWidget(self.btn_send_profile)
        btn_layout.addStretch()
        profile_layout.addLayout(btn_layout)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        info = QLabel("<i>Note: The Terminal Profile is automatically sent after a successful connection.</i>")
        info.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(info)
        
        layout.addStretch()

    def setup_mt_call_tab(self):
        layout = QVBoxLayout(self.tab_mt_call)
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Transaction ID (Hex):"))
        self.in_mt_ti = QLineEdit("01")
        form_layout.addWidget(self.in_mt_ti)
        
        form_layout.addWidget(QLabel("Phone Number (+ International):"))
        self.in_mt_phone = QLineEdit("12345678")
        form_layout.addWidget(self.in_mt_phone)
        
        layout.addLayout(form_layout)
        
        btn_send = QPushButton("Generate & Send MT Call Event")
        btn_send.clicked.connect(self.send_mt_call)
        layout.addWidget(btn_send)
        
        btn_send_all = QPushButton("Send Full Sequence (MT Call -> Connect -> Disconnect)")
        btn_send_all.clicked.connect(self.send_full_call_sequence)
        layout.addWidget(btn_send_all)
        
        layout.addStretch()

    def setup_call_connected_tab(self):
        layout = QVBoxLayout(self.tab_call_connected)
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Transaction ID (Hex):"))
        self.in_conn_ti = QLineEdit("01")
        form_layout.addWidget(self.in_conn_ti)
        form_layout.addStretch()
        
        layout.addLayout(form_layout)
        
        btn_send = QPushButton("Generate & Send Call Connected Event")
        btn_send.clicked.connect(self.send_call_connected)
        layout.addWidget(btn_send)
        layout.addStretch()

    def setup_call_disconnected_tab(self):
        layout = QVBoxLayout(self.tab_call_disconnected)
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Transaction ID (Hex):"))
        self.in_disc_ti = QLineEdit("01")
        form_layout.addWidget(self.in_disc_ti)
        
        form_layout.addWidget(QLabel("Cause (Hex):"))
        self.in_disc_cause = QLineEdit("8090") # default normal clearing
        self.in_disc_cause.setToolTip("e.g. 8090 for normal clearing")
        form_layout.addWidget(self.in_disc_cause)
        
        layout.addLayout(form_layout)
        
        btn_send = QPushButton("Generate & Send Call Disconnected Event")
        btn_send.clicked.connect(self.send_call_disconnected)
        layout.addWidget(btn_send)
        layout.addStretch()

    def refresh_readers(self):
        if not HAS_PYSCARD: return
        self.cb_readers.clear()
        try:
            available_readers = readers()
            for r in available_readers:
                self.cb_readers.addItem(str(r))
            if not available_readers:
                self.log_message("No readers found.")
        except Exception as e:
            self.log_message(f"Error refreshing readers: {e}")

    def connect_card(self):
        if not HAS_PYSCARD: return
        selected_reader_str = self.cb_readers.currentText()
        if not selected_reader_str: return
        
        try:
            available_readers = readers()
            selected_reader = next(r for r in available_readers if str(r) == selected_reader_str)
            self.connection = selected_reader.createConnection()
            self.connection.connect()
            
            atr = toHexString(self.connection.getATR())
            self.log_message(f"Connected to card. ATR: {atr}")
            
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.cb_readers.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            
            # Send Terminal Profile automatically after connection
            self.send_terminal_profile()
        except Exception as e:
            self.log_message(f"Failed to connect: {e}")

    def disconnect_card(self):
        if self.connection:
            try:
                self.connection.disconnect()
                self.log_message("Disconnected.")
            except Exception as e:
                self.log_message(f"Error disconnecting: {e}")
            finally:
                self.connection = None
                
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.cb_readers.setEnabled(True)
        self.btn_refresh.setEnabled(True)

    def log_message(self, message):
        self.text_log.append(message)

    def transmit_apdu(self, apdu_bytes, event_name):
        apdu_hex = apdu_builder.to_hex(apdu_bytes)
        self.log_message(f"\n[{event_name}]")
        self.log_message(f"TX: {apdu_hex}")
        
        if self.connection:
            try:
                current_apdu = apdu_bytes
                while True:
                    data, sw1, sw2 = self.connection.transmit(current_apdu)
                    if data:
                        self.log_message(f"RX: {toHexString(data)}")
                    self.log_message(f"SW: {sw1:02X} {sw2:02X}")
                    
                    if sw1 == 0x61:
                        # ETSI TS 102 221 - GET RESPONSE
                        self.log_message(f"--> Auto-fetching GET RESPONSE ({sw2} bytes)")
                        current_apdu = [0x00, 0xC0, 0x00, 0x00, sw2]
                        self.log_message(f"TX: {apdu_builder.to_hex(current_apdu)}")
                    elif sw1 == 0x91:
                        # ETSI TS 102 223 - FETCH (Proactive Command)
                        self.log_message(f"--> Auto-fetching proactive command ({sw2} bytes)")
                        current_apdu = [0x80, 0x12, 0x00, 0x00, sw2]
                        self.log_message(f"TX: {apdu_builder.to_hex(current_apdu)}")
                    elif sw1 == 0x9F:
                        # Older SIMs - GET RESPONSE
                        self.log_message(f"--> Auto-fetching GET RESPONSE ({sw2} bytes)")
                        current_apdu = [0xA0, 0xC0, 0x00, 0x00, sw2]
                        self.log_message(f"TX: {apdu_builder.to_hex(current_apdu)}")
                    else:
                        # Standard final SW like 90 00, 6A 80, etc.
                        break
            except Exception as e:
                self.log_message(f"Transmission error: {e}")
        else:
            self.log_message("Card not connected. APDU not sent.")

    def send_terminal_profile(self):
        profile_hex = self.in_profile.text()
        try:
            apdu = apdu_builder.build_terminal_profile(profile_hex)
            self.transmit_apdu(apdu, "TERMINAL PROFILE")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid Terminal Profile: {e}")

    def send_mt_call(self):
        ti = self.in_mt_ti.text()
        phone = self.in_mt_phone.text()
        try:
            apdu = apdu_builder.build_mt_call_envelope(ti, phone)
            self.transmit_apdu(apdu, "EVENT DOWNLOAD - MT CALL")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid input: {e}")

    def send_full_call_sequence(self):
        ti = self.in_mt_ti.text()
        phone = self.in_mt_phone.text()
        cause = "8090" # Use default normal clearing cause for the sequence
        
        self.log_message("\n=== STARTING FULL CALL SEQUENCE ===")
        try:
            # 1. MT Call
            apdu_mt = apdu_builder.build_mt_call_envelope(ti, phone)
            self.transmit_apdu(apdu_mt, "EVENT DOWNLOAD - MT CALL (Sequence 1/3)")
            
            # 2. Call Connected
            apdu_conn = apdu_builder.build_call_connected_envelope(ti)
            self.transmit_apdu(apdu_conn, "EVENT DOWNLOAD - CALL CONNECTED (Sequence 2/3)")
            
            # 3. Call Disconnected
            apdu_disc = apdu_builder.build_call_disconnected_envelope(ti, cause)
            self.transmit_apdu(apdu_disc, "EVENT DOWNLOAD - CALL DISCONNECTED (Sequence 3/3)")
            
            self.log_message("\n=== FULL CALL SEQUENCE COMPLETED ===")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sequence error: {e}")

    def send_call_connected(self):
        ti = self.in_conn_ti.text()
        try:
            apdu = apdu_builder.build_call_connected_envelope(ti)
            self.transmit_apdu(apdu, "EVENT DOWNLOAD - CALL CONNECTED")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid input: {e}")

    def send_call_disconnected(self):
        ti = self.in_disc_ti.text()
        cause = self.in_disc_cause.text()
        try:
            apdu = apdu_builder.build_call_disconnected_envelope(ti, cause)
            self.transmit_apdu(apdu, "EVENT DOWNLOAD - CALL DISCONNECTED")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Invalid input: {e}")

    def export_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.text_log.toPlainText())
                self.log_message(f"Log exported to: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export log: {e}")

    def load_settings(self):
        settings_file = "settings.xml"
        if not os.path.exists(settings_file):
            return
        try:
            tree = ET.parse(settings_file)
            root = tree.getroot()
            
            val = root.findtext("TerminalProfile")
            if val is not None: self.in_profile.setText(val)
            
            val = root.findtext("MTCallTI")
            if val is not None: self.in_mt_ti.setText(val)
            
            val = root.findtext("MTCallPhone")
            if val is not None: self.in_mt_phone.setText(val)
            
            val = root.findtext("ConnTI")
            if val is not None: self.in_conn_ti.setText(val)
            
            val = root.findtext("DiscTI")
            if val is not None: self.in_disc_ti.setText(val)
            
            val = root.findtext("DiscCause")
            if val is not None: self.in_disc_cause.setText(val)
            
        except Exception as e:
            self.log_message(f"Error loading settings: {e}")

    def save_settings(self):
        settings_file = "settings.xml"
        try:
            root = ET.Element("Settings")
            
            ET.SubElement(root, "TerminalProfile").text = self.in_profile.text()
            ET.SubElement(root, "MTCallTI").text = self.in_mt_ti.text()
            ET.SubElement(root, "MTCallPhone").text = self.in_mt_phone.text()
            ET.SubElement(root, "ConnTI").text = self.in_conn_ti.text()
            ET.SubElement(root, "DiscTI").text = self.in_disc_ti.text()
            ET.SubElement(root, "DiscCause").text = self.in_disc_cause.text()
            
            tree = ET.ElementTree(root)
            if hasattr(ET, "indent"):
                ET.indent(tree, space="  ", level=0)
            tree.write(settings_file, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            self.log_message(f"Error saving settings: {e}")

    def closeEvent(self, event):
        self.save_settings()
        if self.connection:
            self.disconnect_card()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Good solid style across OS
    window = ETSITester()
    window.show()
    sys.exit(app.exec())
