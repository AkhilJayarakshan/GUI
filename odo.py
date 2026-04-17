import serial, time

class ServiceClearer:
    def __init__(self, port, baud=2000000):
        self.port = port
        self.baud = baud
        self.ser = None

    def connect(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)

    def set_can_baudrate(self):
        frame = [
            0xaa, 0x55, 0x12, 0x03, 0x02,  # extended frame mode
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00,
        ]
        checksum = sum(frame[2:]) & 0xff
        frame.append(checksum)
        frame.append(0x55)
        self.ser.write(bytes(frame))

    def send_first_request(self):
        can_id = 0x18FF1010
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa,0xe8] + id_bytes)
        frame.extend([0xFF, 0x00, 0,0,0,0,0,0])  # main_version=255
        frame.append(0x55)
        self.ser.write(frame)

    def send_clear_frame(self):
        can_id = 0x00222224
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa,0xe0] + id_bytes)
        frame.append(0x55)
        self.ser.write(frame)

    def run_clear(self, progress_callback=None, done_callback=None):
        self.connect()
        self.set_can_baudrate()
        time.sleep(0.1)
        if progress_callback: progress_callback("Sending first request...")
        self.send_first_request()
        time.sleep(0.4)
        if progress_callback: progress_callback("Sending clear odometer frame...")
        self.send_clear_frame()

        if done_callback: done_callback("Clear command sent.")
        return True
