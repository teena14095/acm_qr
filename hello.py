from flask import Flask, Response, url_for
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import cv2
import json
from pyzbar.pyzbar import decode
import numpy as np

app = Flask(__name__)
print(__name__)

@app.route("/")
def hello_world():
    return f"<h1 style='text-align: center'>QR Code Scanner</h1>" \
           f"<div style='display: flex; align-items: center; justify-content: center; width: 100vw; height: 80vh;'><img src='{url_for('video_feed')}' alt='QR Code Scanner Feed' align-self:center></div>" \
           f"<p style='text-align: center'>Position the QR code within the frame.</p>" 

def rescale(width,height):
    cap.set(3,width)
    cap.set(4,height)

cap = cv2.VideoCapture(0)
import ctypes

rescale(1111,950)

def generate_frames():
    last_scanned_data = None
    display_data = {}

    while True:
        success, frame = cap.read()

        if not success:
            break
        else:
            qr_codes = decode(frame)

            if qr_codes:
                for barcode in qr_codes:
                    qr_data = barcode.data.decode('utf-8')

                    if qr_data != last_scanned_data:

                        try:
                            qr_data_dict = json.loads(qr_data)
                            name = qr_data_dict.get("name", "")
                            roll = qr_data_dict.get("roll", "")
                            position = qr_data_dict.get("position", "")
                            date = datetime.now().strftime("%d/%m/%Y")
                            time = datetime.now().strftime("%H:%M:%S")

                            endpoint = "https://api.sheety.co/da59243defdbf5e567a27b8a3e86f53d/attendance/sheet1" #SHEET_ENDPOINT = os.environ.get("SHEET_ENDPOINT", "endpoint doesnt exist")
                            parameters2 = {
                                "sheet1" : {
                                    "date" : date,
                                    "time" : time,
                                    "name" : name,
                                    "roll no" : roll,
                                    "position" : position
                                }
                            }

                            basic = HTTPBasicAuth(
                                "teena14", #USERNAME = os.environ.get("USERNAME", "username doesnt exist")
                                "p0o9i8u7", #PASSWORD = os.environ.get("PASSWORD", "password doesnt exist")
                            )
                            response2 = requests.post(url=endpoint,json=parameters2,auth=basic)
                            print(response2.text)

                            print(f"Scanned QR Code: {name} on {date} at {time}")

                            display_data[qr_data] = "Accessed"

                        except json.JSONDecodeError:
                            print("Unauthorized/wrong QR data. Skipping.")
                            display_data[qr_data] = "Unauthorized"

                        last_scanned_data = qr_data

                    frame = cv2.rectangle(frame, pt1=(barcode.rect.left, barcode.rect.top),
                                          pt2=(barcode.rect.left + barcode.rect.width,
                                           barcode.rect.top + barcode.rect.height),
                                          color=(0, 255, 0),thickness=2)

                    frame = cv2.polylines(frame, pts=[np.array(barcode.polygon)],isClosed= True, color=(255, 0, 0), thickness=2)

                    if qr_data in display_data:
                        text_to_display = display_data[qr_data]
                        text_position = (barcode.rect.left, barcode.rect.top - 10)
                        cv2.putText(frame, text_to_display, org=text_position,fontFace=
                                    cv2.FONT_HERSHEY_SIMPLEX,fontScale= 0.8, color=(0, 0, 0),thickness= 2)

            # Encode the frame as a JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield the frame in byte format for Flask to render
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(debug=True)