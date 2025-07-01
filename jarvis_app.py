# J.A.R.V.I.S. - The Complete Application
# Version 3.2: Added Active Listening Mode with 60-second timeout

import sys
import os
import time
import webbrowser
from datetime import datetime

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient, QFont, QFontDatabase
from PyQt6.QtCore import Qt, QTimer, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty, QObject, QThread, pyqtSignal

# --- Core Engine Imports ---
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai


# ==============================================================================
#  1. CORE ENGINE (The "Brain")
# ==============================================================================

class JarvisCore(QObject):
    """
    The core engine that handles listening, processing, and speaking.
    It runs in a separate thread to not block the UI.
    """
    # --- Signals to communicate with the UI ---
    log_message = pyqtSignal(str, str)
    status_updated = pyqtSignal(str)
    orb_state_changed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        
        # --- Configuration & State ---
        self.WAKE_WORD = "jarvis"
        self.GEMINI_API_KEY = "AIzaSyCqB0EH8xfMqMHoCfuuqMR_g6z3fDHilQA" # <-- IMPORTANT: PASTE YOUR GEMINI API KEY HERE
        
        self._is_running = True
        self.is_active = False # Is J.A.R.V.I.S. in active command mode?
        self.last_interaction_time = 0
        self.inactivity_limit = 60 # seconds

        # --- Initialization ---
        self.engine = None
        self.recognizer = sr.Recognizer()
        self.genai_model = None

    def setup(self):
        """Initializes all components."""
        try:
            self.engine = pyttsx3.init()
        except Exception as e:
            self.log_message.emit("SYSTEM_ERROR", f"Failed to initialize TTS engine: {e}")

        try:
            if not self.GEMINI_API_KEY:
                self.log_message.emit("SYSTEM_ERROR", "Gemini API key not found. AI features disabled.")
            else:
                genai.configure(api_key=self.GEMINI_API_KEY)
                self.genai_model = genai.GenerativeModel('gemini-1.5-flash-latest')
                self.log_message.emit("SYSTEM", "AI Core successfully engaged.")
        except Exception as e:
            self.log_message.emit("SYSTEM_ERROR", f"Failed to initialize Gemini AI: {e}")

    def stop(self):
        self._is_running = False

    def speak(self, text):
        self.log_message.emit("JARVIS", text)
        self.orb_state_changed.emit('speaking')
        self.status_updated.emit("SPEAKING")
        if self.engine:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                self.log_message.emit("SYSTEM_ERROR", f"Speech error: {e}")
        self.orb_state_changed.emit('idle')
        self.status_updated.emit("IDLE")

    def listen_for_audio(self, prompt=""):
        if prompt:
             self.status_updated.emit(prompt)
        else:
             self.status_updated.emit("LISTENING")
             
        self.orb_state_changed.emit('listening')
        
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Listening...")
            
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio)
                if text:
                    self.log_message.emit("USER", text)
                return text.lower()
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                self.orb_state_changed.emit('idle')
                return None
            except sr.RequestError as e:
                self.speak(f"Connection error to speech service: {e}")
                return None
        return None

    def process_command(self, command):
        if 'open notepad' in command:
            self.speak("Certainly. Opening Notepad for you.")
            os.system('notepad.exe')
        elif 'what time is it' in command:
            time_string = datetime.now().strftime("%I:%M %p")
            self.speak(f"The current time is {time_string}.")
        elif 'search for' in command:
            query = command.replace('search for', '').strip()
            self.speak(f"Right away. Searching for {query}.")
            webbrowser.open(f"https://www.google.com/search?q={query}")
        elif 'stand down' in command or 'go to standby' in command:
            self.speak("Understood. Returning to standby mode.")
            self.is_active = False
        elif 'shut down' in command or 'go to sleep' in command:
             self.speak("Deactivating all systems. Goodbye, sir.")
             self.stop()
        else:
            if self.genai_model:
                self.status_updated.emit("THINKING")
                self.orb_state_changed.emit('speaking')
                try:
                    full_prompt = f"You are J.A.R.V.I.S., a witty and helpful AI assistant. A user said: '{command}'. Respond concisely."
                    response = self.genai_model.generate_content(full_prompt)
                    self.speak(response.text)
                except Exception as e:
                    self.speak(f"My apologies. I'm encountering an issue with my cognitive matrix: {e}")
            else:
                self.speak("I'm sorry, I don't recognize that command and my AI core is offline.")

    def run(self):
        """The main loop for the core engine with active/standby modes."""
        self.setup()
        self.speak("Systems online. Standing by for activation.")
        
        while self._is_running:
            if self.is_active:
                # --- ACTIVE MODE ---
                if time.time() - self.last_interaction_time > self.inactivity_limit:
                    self.speak("Inactivity detected. Returning to standby.")
                    self.is_active = False
                    continue

                command = self.listen_for_audio("Awaiting Command...")
                if command:
                    self.last_interaction_time = time.time() # Reset timer on interaction
                    self.process_command(command)
            else:
                # --- STANDBY MODE ---
                transcript = self.listen_for_audio("Awaiting Wake Word...")
                if transcript and self.WAKE_WORD in transcript:
                    self.is_active = True
                    self.last_interaction_time = time.time()
                    self.speak("Activated. How can I help you?")
            
            time.sleep(0.1)
        
        self.finished.emit()


# ==============================================================================
#  2. VISUAL INTERFACE (The "Body")
# ==============================================================================

class OrbWidget(QWidget):
    """A custom widget to display the animated J.A.R.V.I.S. orb."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._pulse_opacity = 0.9
        self.state = 'idle'
        
        self.pulse_animation = QPropertyAnimation(self, b'pulse_opacity')
        self.pulse_animation.setDuration(4000)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setStartValue(0.6)
        self.pulse_animation.setKeyValueAt(0.5, 0.9)
        self.pulse_animation.setEndValue(0.6)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.pulse_animation.start()

    @pyqtProperty(float)
    def pulse_opacity(self):
        return self._pulse_opacity

    @pulse_opacity.setter
    def pulse_opacity(self, value):
        self._pulse_opacity = value
        self.update()

    def set_state(self, new_state):
        self.state = new_state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width, height = self.width(), self.height()
        center, radius = QPointF(width / 2, height / 2), min(width, height) / 2.5
        
        glow_color = QColor(0, 0, 0, 0)
        if self.state == 'listening':
            glow_color = QColor(0, 240, 255, 150)
        elif self.state == 'speaking':
            glow_color = QColor(255, 255, 255, 180)

        if self.state != 'idle':
            glow_gradient = QRadialGradient(center, radius * 1.5)
            glow_gradient.setColorAt(0.6, glow_color)
            glow_gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(glow_gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, radius * 1.5, radius * 1.5)
        
        orb_gradient = QRadialGradient(center, radius)
        orb_gradient.setColorAt(0, QColor(0, 240, 255, 200))
        orb_gradient.setColorAt(0.7, QColor(0, 120, 255, 128))
        orb_gradient.setColorAt(1.0, QColor(10, 10, 26, 0))
        painter.setBrush(QBrush(orb_gradient))
        painter.setPen(QPen(QColor(150, 250, 255, 100), 1))
        painter.drawEllipse(center, radius, radius)

        core_radius = radius * 0.6
        core_gradient = QRadialGradient(center, core_radius)
        core_gradient.setColorAt(0, QColor(255, 255, 255, 255))
        core_gradient.setColorAt(0.8, QColor(0, 240, 255, int(200 * self._pulse_opacity)))
        core_gradient.setColorAt(1, QColor(0, 240, 255, 0))
        painter.setBrush(QBrush(core_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, core_radius, core_radius)

class JarvisWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.start_core_engine()

    def initUI(self):
        self.setWindowTitle("J.A.R.V.I.S.")
        self.setGeometry(100, 100, 800, 450)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.title_font = QFont("Orbitron", 24)
        self.mono_font = QFont("Roboto Mono", 10)

        self.orb_widget = OrbWidget(self)
        self.status_label = QLabel("INITIALIZING...", self)
        self.status_label.setFont(QFont("Orbitron", 16))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #00f0ff; padding: 5px;")

        self.log_display = QTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setFont(self.mono_font)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 25, 47, 0.7);
                border: 1px solid rgba(0, 240, 255, 0.3);
                color: #f0f0f0; border-radius: 5px;
            }""")

        vbox_left = QVBoxLayout()
        vbox_left.addWidget(self.orb_widget)
        vbox_left.addWidget(self.status_label)

        hbox_main = QHBoxLayout()
        hbox_main.addLayout(vbox_left)
        hbox_main.addWidget(self.log_display, 1)

        self.setLayout(hbox_main)

    def log_message_slot(self, sender, message):
        color = {"JARVIS": "#00f0ff", "USER": "#a0a0ff", "SYSTEM": "#909090", "SYSTEM_ERROR": "#ff5050"}.get(sender, "#f0f0f0")
        formatted = f'<span style="color: {color}; font-weight: bold;">{sender}:</span> {message}'
        self.log_display.append(formatted)

    def status_update_slot(self, status):
        self.status_label.setText(status)

    def orb_state_slot(self, state):
        self.orb_widget.set_state(state)

    def start_core_engine(self):
        self.thread = QThread()
        self.worker = JarvisCore()
        self.worker.moveToThread(self.thread)

        self.worker.log_message.connect(self.log_message_slot)
        self.worker.status_updated.connect(self.status_update_slot)
        self.worker.orb_state_changed.connect(self.orb_state_slot)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.close)

        self.thread.start()

    def closeEvent(self, event):
        if self.thread.isRunning():
            self.log_message_slot("SYSTEM", "Shutdown sequence initiated.")
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        brush = QBrush(QColor(10, 15, 30, 200))
        pen = QPen(QColor(0, 240, 255, 80), 1)
        painter.setBrush(brush)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect(), 10.0, 10.0)

    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition()

    def mouseMoveEvent(self, event):
        delta = QPointF(event.globalPosition() - self.oldPos)
        self.move(int(self.x() + delta.x()), int(self.y() + delta.y()))
        self.oldPos = event.globalPosition()

# --- Main Execution ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = JarvisWindow()
    window.show()
    sys.exit(app.exec())
