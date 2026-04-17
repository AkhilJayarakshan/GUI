import serial
import time
import re
import os

class HykonUpdater:
    def __init__(self, port, baud=2000000):
        self.port = port
        self.baud = baud
        self.ser = None
        self.main_version = 0
        self.sub_version = 0
        self._cancel = False

    def connect(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
    
    def disconnect(self):
        can_id = 0x18FF1010
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa, 0xe8] + id_bytes)
        frame.extend([self.main_version & 0xFF, self.sub_version & 0xFF, 0,0,0,0,0,0])
        frame.append(0x55)
        self.ser.write(frame)
        self.ser.close()

    def cancel(self):
        self._cancel = True
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
    
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

    def extract_version(self, bin_file):
        with open(bin_file, "rb") as f:
            data = f.read()
        text_data = data.decode(errors="ignore")
        match = re.search(r"Hykon_Cluster\s*v(\d+)\.(\d+)", text_data)
        if match:
            self.main_version, self.sub_version = int(match.group(1)), int(match.group(2))
        return self.main_version, self.sub_version

    def send_first_request(self):
        can_id = 0x18FF1010
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa, 0xe8] + id_bytes)
        frame.extend([self.main_version & 0xFF, self.sub_version & 0xFF, 0,0,0,0,0,0])
        frame.append(0x55)
        self.ser.write(frame)

    def send_request_frame(self):
        can_id = 0x00222222
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa, 0xe0] + id_bytes)
        frame.append(0x55)
        self.ser.write(frame)

    def send_request_frame2(self):
        can_id = 0x00444444
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa, 0xe0] + id_bytes)
        frame.append(0x55)
        self.ser.write(frame)

    def get_update_type(self, bin_file):
        """Determine update type based on filename: 'firmware' or 'assets'"""
        filename = os.path.basename(bin_file).lower()
        if 'assets' in filename:
            return 'assets'
        return 'firmware'

    def send_binary_file(self, bin_file, progress_callback=None, log_callback=None):
        base_id = 0x00333333
        chunk_index = 0
        file_size = os.path.getsize(bin_file)
        total_chunks = (file_size + 7) // 8  # round up

        with open(bin_file, "rb") as f:
            while True:
                if self._cancel:
                    return False
                data = f.read(8)
                if not data:
                    break
                can_id = base_id + chunk_index
                id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
                frame = bytearray([0xaa, 0xe8] + id_bytes)
                frame.extend(data)
                while len(frame) < 14:
                    frame.append(0x00)
                frame.append(0x55)
                try:
                    self.ser.write(frame)
                except Exception:
                    if self._cancel:
                        return False
                    raise
                if log_callback:
                    log_callback(f"Sent chunk {chunk_index} | CAN ID: {hex(can_id)}")
                chunk_index += 1
                if progress_callback:
                    percent = int((chunk_index / total_chunks) * 100)
                    progress_callback(percent)
                time.sleep(0.00008)
        
        # Ensure all data is transmitted before continuing
        if self._cancel:
            return False
        try:
            self.ser.flush()
        except Exception:
            if self._cancel:
                return False
            raise
        time.sleep(0.15)
        return True

    def send_end_frame(self):
        can_id = 0x00999999
        id_bytes = [(can_id >> (8*i)) & 0xFF for i in range(4)]
        frame = bytearray([0xaa, 0xe2] + id_bytes)
        frame.extend([self.main_version & 0xFF, self.sub_version & 0xFF])
        frame.append(0x55)
        self.ser.write(frame)
        self.ser.flush()
        time.sleep(0.1)

    def run_update(self, bin_file, progress_callback=None, done_callback=None, update_type=None):
        self._cancel = False
        self.connect()
        self.set_can_baudrate()
        time.sleep(0.1)  # give device time to switch baud
        main, sub = self.extract_version(bin_file)
        if progress_callback:
            progress_callback(f"Firmware version detected: {main}.{sub}")
        
        # Use provided update_type, or auto-detect from filename
        if update_type is None:
            update_type = self.get_update_type(bin_file)
        
        if self._cancel:
            self.close()
            return False

        self.send_first_request()

        start = time.time()
        while (time.time() - start) < 10.0:
            if self._cancel:
                self.close()
                return False
            if update_type == 'assets':
                self.send_request_frame2()
            else:
                self.send_request_frame()
            
            header = self.ser.read(2)
            if self._cancel:
                self.close()
                return False
            if not header:
                continue
            if (header[0] == 0xaa) and (header[1] & 0xc0 == 0xc0):
                length = header[1] & 0x0f
                extra_len = length + 5
                payload = self.ser.read(extra_len)
                if self._cancel:
                    self.close()
                    return False
                if payload and payload[-1] == 0x55:
                    can_id = (payload[3]<<24)|(payload[2]<<16)|(payload[1]<<8)|payload[0]
                    if can_id == 0x00111111:
                        if progress_callback:
                            progress_callback("Updating...")
                        if update_type == 'assets':
                            time.sleep(10)
                        else:
                            time.sleep(1)
                        if not self.send_binary_file(bin_file, progress_callback):
                            self.close()
                            return False
                        time.sleep(0.2)  # Additional delay to ensure all frames are processed
                        for _ in range(15):
                            if self._cancel:
                                self.close()
                                return False
                            self.send_end_frame()
                        wait_start = time.time()
                        while (time.time() - wait_start) < 2.0:
                            if self._cancel:
                                self.close()
                                return False
                            header = self.ser.read(2)
                            if not header:
                                continue
                            if (header[0] == 0xaa) and (header[1] & 0xc0 == 0xc0):
                                length = header[1] & 0x0f
                                extra_len = length + 5
                                payload = self.ser.read(extra_len)
                                if payload and payload[-1] == 0x55:
                                    can_id = (payload[3]<<24)|(payload[2]<<16)|(payload[1]<<8)|payload[0]
                                    if can_id == 0x00555555:
                                        if done_callback:
                                            done_callback("Update completed successfully!")
                                        self.close()
                                        return True
                        # If no response within 2s
                        if done_callback and not self._cancel:
                            done_callback("Update failed ! \nPlease try again")
                        self.close()
                        return False
        if done_callback and not self._cancel:
            done_callback("Update failed ! \nPlease use a newer version or Check the connection")
        self.close()
        return False

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
