import time
from PyQt6.QtCore import QObject, pyqtSignal
import serial
import serial.tools.list_ports

class SerialWorker(QObject):
    data_received = pyqtSignal(float, float, float, float, float)  # t, P, F, Vp, Vf
    error = pyqtSignal(str)
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = False

    def connect(self, port, baud=115200):
        try:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baud
            self.ser.timeout = 0.1
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            self.running = True

            # Sequenza di reset hardware ESP32
            try:
                self.ser.setDTR(False)
                self.ser.setRTS(True)
                time.sleep(0.1)
                self.ser.setDTR(True)
                self.ser.setRTS(False)
                time.sleep(0.1)
                self.ser.setRTS(True)
                self.ser.setDTR(True)
                time.sleep(0.05)
                self.ser.setDTR(False)
                time.sleep(0.05)
                self.ser.setRTS(False)
                time.sleep(0.7)
                self.ser.reset_input_buffer()
            except Exception:
                pass
            return True
        except Exception as e:
            self.error.emit(str(e))
            return False

    def disconnect(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                if line.startswith("ESP32"):
                    self.status_msg.emit(line)
                    continue
                lower = line.lower()
                if any(k in lower for k in ("errore", "error", "fault", "non trovata", "failed")):
                    self.error.emit(line)
                    continue
                parts = line.split(',')
                if len(parts) >= 5:
                    try:
                        t = float(parts[0]) / 1000.0
                        p = float(parts[1])
                        f = float(parts[2])
                        vp = float(parts[3])
                        vf = float(parts[4])
                        self.data_received.emit(t, p, f, vp, vf)
                    except ValueError:
                        self.error.emit(f"Riga non valida: {line}")
            except Exception as e:
                self.error.emit(str(e))
                time.sleep(0.05)