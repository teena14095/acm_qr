from flask import Flask, Response, url_for
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import cv2
import json
import numpy as np
import os

app = Flask(__name__)

@app.route("/")
def hello_world():
    return f"<h1 style='text-align: center'>QR Code Scanner</h1>" \
           f"<div style='display: flex; align-items: center; justify-content: center; width: 100vw; height: 80vh;'>" \
           f"<img src='{url_for('video_feed')}' alt='QR Code Scanner Feed' align-self:center></div>" \
           f"<p style='text-align: center'>Position the QR code within the frame.</p>" 

def rescale(width, height):
    cap.set(3, width)
    cap.set(4, height)

cap = cv2.VideoCapture(0)
rescale(1111, 950)

def decode_qr(frame):
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(frame)
    if points is not None and data:
        return data, points
    return None, None

def generate_frames():
    last_scanned_data = None
    display_data = {}

    while True:
        success, frame = cap.read()

        if not success:
            break
        else:
            qr_data, points = decode_qr(frame)

            if qr_data and qr_data != last_scanned_data:
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

                    print(f"Scanned QR Code: {name} on {date} at {time}")
                    display_data[qr_data] = "Accessed"

                except json.JSONDecodeError:
                    print("Unauthorized/wrong QR data. Skipping.")
                    display_data[qr_data] = "Unauthorized"

                last_scanned_data = qr_data

            if points is not None:
                points = points.astype(int)
                for i in range(len(points)):
                    pt1 = tuple(points[i][0])
                    pt2 = tuple(points[(i + 1) % len(points)][0])
                    frame = cv2.line(frame, pt1, pt2, color=(0, 255, 0), thickness=2)

                if qr_data in display_data:
                    text_to_display = display_data[qr_data]
                    text_position = (points[0][0][0], points[0][0][1] - 10)
                    cv2.putText(frame, text_to_display, text_position, fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                                fontScale=0.8, color=(0, 0, 255), thickness=2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
