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
    <div style='display: flex; flex-direction: column; width: 100vw; height: 100vh; background-color:rgb(8, 8, 8);'>
    <h1 style='text-align: center; margin-top: 20px; color: #11a367''>QR Code Scanner</h1>

        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: calc(100vh - 100px); position: relative;">
            <video id="video" autoplay playsinline style="border: 1px solid black; width: 640px; height: 480px; box-sizing: border-box;"></video>
            <canvas id="overlayCanvas" 
                    style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 640px; height: 480px; pointer-events: none;"></canvas>
            <p style="font-size: 18px; color:rgb(230, 230, 230); margin: 10px 0; text-align: center;">Position the QR code within the frame.</p>
            <div id="messageOverlay" 
                style="position: absolute; pointer-events: none; font-size: 24px; font-weight: bold; 
                    text-shadow: 1px 1px 2px black; visibility: hidden;">
                Accessed!
            </div>
        </div>
    </div>

    <script>
        const video = document.getElementById('video');
        const overlayCanvas = document.getElementById('overlayCanvas');
        const overlayCtx = overlayCanvas.getContext('2d');

        let lastBoundingBox = null; // Store the last detected bounding box
        let lastVisibilityTimestamp = Date.now(); // Track when the box was last visible

        navigator.mediaDevices.getUserMedia({ video: true })
            .then(stream => {
                video.srcObject = stream;
            })
            .catch(err => {
                console.error('Error accessing webcam:', err);
            });

        video.addEventListener('loadedmetadata', () => {
            overlayCanvas.width = video.videoWidth;
            overlayCanvas.height = video.videoHeight;
        });

        setInterval(() => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            canvas.toBlob(blob => {
                const formData = new FormData();
                formData.append('frame', blob);

                fetch('/process_frame', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Server response:', data);

                    if (data.status === "success") {
                        overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

                        const points = data.qr_points || [];
                        drawBoundingBoxesAndLabel(points, overlayCtx);

                        // Show the "Access Granted" message
                        const accessMessage = document.getElementById('access-message');
                        accessMessage.textContent = "Access Granted!";
                        accessMessage.style.display = "block";

                        setTimeout(() => {
                            accessMessage.style.display = "none";
                        }, 2000);
                    } else {
                        console.warn('Processing failed:', data);
                    }
                })
                .catch(err => console.error('Error processing frame:', err));
            });
        }, 300);


        // Function to draw bounding boxes and labels
        function drawBoundingBoxesAndLabel(points, ctx) {
        // Extract bounding box dimensions
            const [topLeft, topRight, bottomRight, bottomLeft] = points;
            const width = topRight[0] - topLeft[0];
            const height = bottomLeft[1] - topLeft[1];

            ctx.fillStyle = 'red';
            ctx.font = '25px Arial';
            const label = 'Accessed';
            const textX = topLeft[0];
            const textY = topLeft[1] - 10;
            ctx.fillText(label, textX, textY);

            setTimeout(() => {
                // Clear the area where the text was drawn
                const textWidth = ctx.measureText(label).width;
                const textHeight = 25; // Approximate text height based on font size
                ctx.clearRect(textX, textY - textHeight, textWidth, textHeight);
            }, 1500);
        }
    </script>
    """

def decode_qr(frame):
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(frame)
    if points is not None and data:
        return data, points
    return None, None

@app.route('/process_frame', methods=['POST'])
def process_frame():
    global last_detected_qr

    if 'frame' not in request.files:
        app.logger.error("No frame uploaded")
        return jsonify({"error": "No frame uploaded"}), 400

    frame = request.files['frame'].read()
    np_frame = np.frombuffer(frame, np.uint8)
    image = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)

    qr_data, points = decode_qr(image)

    if qr_data:
        app.logger.info(f"Detected QR Data: {qr_data}")
        
        if qr_data == last_detected_qr:
            app.logger.info("Duplicate QR code detected; skipping.")
            return jsonify({"status": "duplicate_qr"}), 200

        last_detected_qr = qr_data

        try:
            qr_data_dict = json.loads(qr_data)
            name = qr_data_dict.get("name", "")
            roll = qr_data_dict.get("roll", "")
            position = qr_data_dict.get("position", "")
            date = datetime.now().strftime("%d/%m/%Y")
            time = datetime.now().strftime("%H:%M:%S")

            # Log extracted QR data
            app.logger.info(f"Extracted Data - Name: {name}, Roll: {roll}, Position: {position}")

            endpoint = os.environ.get("SHEET_ENDPOINT", "https://api.sheety.co/da59243defdbf5e567a27b8a3e86f53d/attendance/sheet1")
            parameters2 = {
                "sheet1": {
                    "date": date,
                    "time": time,
                    "name": name,
                    "roll": roll,
                    "position": position
                }
            }

            basic = HTTPBasicAuth(
                os.environ.get("USERNAME", "username_not_found"),
                os.environ.get("PASSWORD", "password_not_found")
            )

            # Send data to Google Sheets
            response2 = requests.post(url=endpoint, json=parameters2, auth=basic)
            app.logger.info(f"Google Sheets Response: {response2.text}")

            points_list = points[0].tolist() if points is not None else None
            return jsonify({"qr_data": qr_data, "qr_points": points_list, "status": "success"})
        except json.JSONDecodeError:
            app.logger.error("QR Data is not a valid JSON")
            return jsonify({"qr_data": qr_data, "status": "unauthorized"})
    
    app.logger.info("No QR code detected in the frame.")
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
