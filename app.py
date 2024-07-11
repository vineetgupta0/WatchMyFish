
import io
import json
import logging
import socketserver
from threading import Condition, Thread
from http import server
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput
from libcamera import controls
import psutil
import time
from rpi_ws281x import *
import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)

# LED strip configuration
LED_COUNT = 30      # Number of LED pixels
LED_PIN = 18        # GPIO pin connected to the pixels
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10        # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0     # set to '1' for GPIOs 13, 19, 41, 45 or 53

# Create NeoPixel object with appropriate configuration
strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
# Initialize the library (must be called once before other functions)
strip.begin()

# Default settings
DEFAULT_SETTINGS = {
    "iso": 400,
    "framerate": 15,
    "resolution": "640,480",
    "quality": 70,
    "led_color": "#FFFFFF",
    "led_brightness": 255,
    "camera_on": True,
    "led_on": False,
    "led_on_time": "18:00",
    "led_off_time": "06:00",
    "schedule_enabled": False
}

# Load settings from file or use defaults
'''
try:
    with open('camera_settings.json', 'r') as f:
        SETTINGS = json.load(f)
except FileNotFoundError:
    SETTINGS = DEFAULT_SETTINGS
    with open('camera_settings.json', 'w') as f:
        json.dump(SETTINGS, f)

'''
SETTINGS = DEFAULT_SETTINGS

# HTML page for the stream
PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watch My Fish Camera and LED Control</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        h1 {
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .stream {
            width: 100%;
            height: auto;
            margin-bottom: 20px;
        }
        .controls {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        label {
            display: block;
            margin-bottom: 5px;
        }
        input, select {
            width: 100%;
            padding: 5px;
            margin-bottom: 10px;
        }
        #systemInfo, #scheduleStatus {
            margin-top: 20px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Raspberry Pi Camera and LED Control</h1>
        <img src="stream.mjpg" class="stream" alt="Camera Stream" />
        <div class="controls">
            <div>
                <label for="iso">ISO:</label>
                <input type="number" id="iso" min="100" max="1600">

                <label for="framerate">Framerate:</label>
                <input type="number" id="framerate" min="1" max="30">

                <label for="led_color">LED Color:</label>
                <input type="color" id="led_color">

                <label for="led_brightness">LED Brightness:</label>
                <input type="range" id="led_brightness" min="0" max="255">

                <label for="camera_on">Camera On:</label>
                <input type="checkbox" id="camera_on">
            </div>
            <div>
                <label for="resolution">Resolution:</label>
                <select id="resolution">
                    <option value="640,480">640x480</option>
                    <option value="1280,720">1280x720</option>
                    <option value="1920,1080">1920x1080</option>
                </select>

                <label for="quality">JPEG Quality:</label>
                <input type="number" id="quality" min="1" max="100">

                <label for="led_on">LED On:</label>
                <input type="checkbox" id="led_on">

                <label for="led_on_time">LED On Time:</label>
                <input type="time" id="led_on_time">

                <label for="led_off_time">LED Off Time:</label>
                <input type="time" id="led_off_time">

                <label for="schedule_enabled">Enable LED Schedule:</label>
                <input type="checkbox" id="schedule_enabled">
            </div>
        </div>
        <button onclick="updateSettings()">Apply Settings</button>
        <div id="systemInfo"></div>
        <div id="scheduleStatus"></div>
    </div>
    <script>
        function loadSettings() {
            const savedSettings = localStorage.getItem('cameraSettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                Object.keys(settings).forEach(key => {
                    const element = document.getElementById(key);
                    if (element) {
                        if (element.type === 'checkbox') {
                            element.checked = settings[key];
                        } else {
                            element.value = settings[key];
                        }
                    }
                });
            }
        }

        function saveSettings() {
            const settings = {
                iso: document.getElementById('iso').value,
                framerate: document.getElementById('framerate').value,
                resolution: document.getElementById('resolution').value,
                quality: document.getElementById('quality').value,
                led_color: document.getElementById('led_color').value,
                led_brightness: document.getElementById('led_brightness').value,
                camera_on: document.getElementById('camera_on').checked,
                led_on: document.getElementById('led_on').checked,
                led_on_time: document.getElementById('led_on_time').value,
                led_off_time: document.getElementById('led_off_time').value,
                schedule_enabled: document.getElementById('schedule_enabled').checked
            };
            localStorage.setItem('cameraSettings', JSON.stringify(settings));
        }

        function updateSettings() {
            saveSettings();

            fetch('/update_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: localStorage.getItem('cameraSettings'),
            })
            .then(response => response.json())
            .then(data => {
                console.log('Settings updated:', data);
                location.reload();
            })
            .catch((error) => {
                console.error('Error:', error);
            });
        }

        function updateSystemInfo() {
            fetch('/system_info')
            .then(response => response.json())
            .then(data => {
                document.getElementById('systemInfo').innerHTML = `CPU Load: ${data.cpu_load}% | RAM Usage: ${data.ram_usage}%`;
                document.getElementById('scheduleStatus').innerHTML = `Schedule Status: ${data.schedule_status}`;
            });
        }

        // Load settings when the page loads
        window.onload = loadSettings;

        // Save settings when any input changes
        document.querySelectorAll('input, select').forEach(element => {
            element.addEventListener('change', saveSettings);
        });

        setInterval(updateSystemInfo, 1000);
    </script>
</body>
</html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        elif self.path == '/system_info':
            cpu_load = psutil.cpu_percent()
            ram_usage = psutil.virtual_memory().percent
            schedule_status = "Active" if SETTINGS['schedule_enabled'] else "Inactive"
            content = json.dumps({
                'cpu_load': cpu_load,
                'ram_usage': ram_usage,
                'schedule_status': schedule_status
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/update_settings':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            new_settings = json.loads(post_data.decode('utf-8'))

            for key, value in new_settings.items():
                if key in SETTINGS:
                    if key in ['camera_on', 'led_on', 'schedule_enabled']:
                        SETTINGS[key] = value == 'true' if isinstance(value, str) else value
                    else:
                        SETTINGS[key] = value

            with open('camera_settings.json', 'w') as f:
                json.dump(SETTINGS, f)

            update_camera_settings()
            update_led_settings()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def update_camera_settings():
    global encoder

    if SETTINGS['camera_on']:
        picam2.stop_recording()

        iso = int(SETTINGS['iso'])
        framerate = int(SETTINGS['framerate'])
        width, height = map(int, SETTINGS['resolution'].split(','))
        quality = int(SETTINGS['quality'])

        video_config = picam2.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameDurationLimits": (1000000 // framerate, 1000000 // framerate)}
        )
        picam2.configure(video_config)
        picam2.set_controls({"AnalogueGain": iso / 100, "ExposureTime": 1000000 // framerate})

        encoder = JpegEncoder(q=quality)

        picam2.start_recording(encoder, FileOutput(output))
    else:
        picam2.stop_recording()

def update_led_settings():
    if SETTINGS['led_on']:
        color = tuple(int(SETTINGS['led_color'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        brightness = int(SETTINGS['led_brightness'])
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(*color))
        strip.setBrightness(brightness)
        strip.show()
    else:
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

def led_scheduler():
    while True:
        if SETTINGS['schedule_enabled']:
            now = datetime.datetime.now().time()
            on_time = datetime.datetime.strptime(SETTINGS['led_on_time'], "%H:%M").time()
            off_time = datetime.datetime.strptime(SETTINGS['led_off_time'], "%H:%M").time()

            if on_time <= now < off_time:
                if not SETTINGS['led_on']:
                    SETTINGS['led_on'] = True
                    update_led_settings()
            else:
                if SETTINGS['led_on']:
                    SETTINGS['led_on'] = False
                    update_led_settings()

        time.sleep(60)  # Check every minute

# Set up the camera
picam2 = Picamera2()
video_config = picam2.create_video_configuration(
    main={"size": tuple(map(int, SETTINGS['resolution'].split(','))), "format": "RGB888"},
    controls={"FrameDurationLimits": (1000000 // SETTINGS['framerate'], 1000000 // SETTINGS['framerate'])}
)
picam2.configure(video_config)
picam2.set_controls({"AnalogueGain": SETTINGS['iso'] / 100, "ExposureTime": 1000000 // SETTINGS['framerate']})
picam2.set_controls({"AeEnable": True, "AwbEnable": True})

output = StreamingOutput()
encoder = JpegEncoder(q=SETTINGS['quality'])
picam2.start_recording(encoder, FileOutput(output))

# Start LED scheduler in a separate thread
led_thread = Thread(target=led_scheduler)
led_thread.daemon = True
led_thread.start()

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    logging.info("Server started on port 8000")
    update_led_settings()  # Initialize LED strip
    server.serve_forever()
finally:
    picam2.stop_recording()
    # Turn off all LEDs when the server stops
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
