from flask import Flask, Response, request, url_for, jsonify
import cv2
import numpy as np
import json
import os
from datetime import datetime
from requests.auth import HTTPBasicAuth
import requests
import logging

app = Flask(__name__)

last_detected_qr = None

@app.route("/")
def hello_world():
    return """
    <h1 style='text-align: center'>QR Code Scanner</h1>
    <div style='text-align: center'>
        <video id="video" autoplay playsinline style="border: 1px solid black; width: 640px; height: 480px;"></video>
        <canvas id="canvas" style="display: none;"></canvas>
    </div>
    <p style='text-align: center'>Position the QR code within the frame.</p>
    <script>
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        
        // Access the webcam
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(stream => {
                video.srcObject = stream;
            })
            .catch(err => {
                console.error('Error accessing webcam:', err);
            });
        
        // Periodically capture frames and send them to the server
        setInterval(() => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('frame', blob);
                fetch('/process_frame', {
                    method: 'POST',
                    body: formData
                }).then(response => response.json())
                  .then(data => {
                      console.log('Server response:', data);
                  }).catch(err => console.error('Error:', err));
            }, 'image/jpeg');
        }, 500);
    </script>
    """

def decode_qr(frame):
    """Decodes QR code from a frame."""
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(frame)
    if points is not None and data:
        return data, points
    return None, None

@app.route('/process_frame', methods=['POST'])
def process_frame():
    """Handles frame processing and QR code detection."""
    global last_detected_qr  
    
    if 'frame' not in request.files:
        return jsonify({"error": "No frame uploaded"}), 400

    # Read the uploaded frame
    frame = request.files['frame'].read()
    np_frame = np.frombuffer(frame, np.uint8)
    image = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
    
    qr_data, points = decode_qr(image)
    if qr_data:
        if qr_data == last_detected_qr:
            # If it's the same QR code, skip processing
            return jsonify({"status": "duplicate_qr"}), 200
        
        last_detected_qr = qr_data
        
        try:
            qr_data_dict = json.loads(qr_data)
            name = qr_data_dict.get("name", "")
            roll = qr_data_dict.get("roll", "")
            position = qr_data_dict.get("position", "")
            date = datetime.now().strftime("%d/%m/%Y")
            time = datetime.now().strftime("%H:%M:%S")

            endpoint = os.environ.get("SHEET_ENDPOINT", "https://api.sheety.co/da59243defdbf5e567a27b8a3e86f53d/attendance/sheet1")
            parameters2 = {
                "sheet1": {
                    "date": date,
                    "time": time,
                    "name": name,
                    "roll no": roll,
                    "position": position
                }
            }

            basic = HTTPBasicAuth(
                os.environ.get("USERNAME", "username_not_found"),
                os.environ.get("PASSWORD", "password_not_found")
            )
            response2 = requests.post(url=endpoint, json=parameters2, auth=basic)
            print(response2.text)

            return jsonify({"qr_data": qr_data, "status": "success"})
        except json.JSONDecodeError:
            return jsonify({"qr_data": qr_data, "status": "unauthorized"})
    
    return jsonify({"status": "no_qr"})

# Logging filter to suppress unnecessary messages
class EndpointFilter(logging.Filter):
    """Filter out specific endpoint logs."""
    def filter(self, record):
        # Suppress logs for the /process_frame endpoint
        return "/process_frame" not in record.getMessage()

if __name__ == "__main__":
    # Get the Flask default logger (Werkzeug logger)
    log = logging.getLogger('werkzeug')
    
    # Add the custom filter to suppress specific logs
    log.addFilter(EndpointFilter())
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
