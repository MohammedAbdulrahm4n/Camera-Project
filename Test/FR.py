import requests
import cv2
import smtplib
import numpy as np
import face_recognition
import mysql.connector
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import datetime
from email.mime.base import MIMEBase
from email import encoders

# إعدادات Home Assistant
home_assistant_url = "http://192.168.1.116:8123"
camera_entity_id = "camera.ds_2de2c400mwg_e20240420aawrfd1963881_101"
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkNDYyZDI4NTFjY2E0NzJlODMxOGZhNGVhMmYwNmZiNCIsImlhdCI6MTczOTY5MjExOSwiZXhwIjoyMDU1MDUyMTE5fQ.FGqLEoWVzmV1qSLGwlggmOpRpdvNlmRvMaOfrmyDjGY"

# عنوان API للبث المباشر
url = f"{home_assistant_url}/api/camera_proxy/{camera_entity_id}"
headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

# إعدادات البريد الإلكتروني
sender_email = "your_email@example.com"
receiver_email = "receiver_email@example.com"
smtp_server = "localhost"
smtp_port = 25

# الاتصال بقاعدة البيانات
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Skarpt@2021",
        database="usersdb"
    )
    cursor = db.cursor()
    print("✅ تم الاتصال بقاعدة البيانات بنجاح")
except mysql.connector.Error as err:
    print(f"❌ فشل الاتصال بقاعدة البيانات: {err}")
    exit()

# تحميل الوجوه المخزنة
try:
    cursor.execute("SELECT UserID, ProfileImage FROM users")
    users = cursor.fetchall()
except mysql.connector.Error as err:
    print(f"❌ خطأ في جلب بيانات المستخدمين: {err}")
    users = []

known_faces = []
known_face_ids = []

for user in users:
    user_id, profile_image = user

    if profile_image:
        try:
            image_array = np.frombuffer(profile_image, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            if image is None or image.size == 0:
                print(f"⚠️ صورة المستخدم {user_id} غير صالحة أو فارغة، سيتم تخطيها.")
                continue

            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_faces.append(encodings[0])
                known_face_ids.append(user_id)
        except Exception as e:
            print(f"⚠️ خطأ في تحميل صورة المستخدم {user_id}: {e}")

# دالة لإرسال البريد الإلكتروني
def send_email(user_info):
    subject = "تم اكتشاف وجه!"
    body = f"تم اكتشاف وجه عبر الكاميرا.\n\nمعلومات الشخص:\n{user_info}"

    msg = MIMEText(body, 'plain')
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("📩 تم إرسال البريد الإلكتروني.")
    except Exception as e:
        print(f"❌ فشل في إرسال البريد الإلكتروني: {e}")

# تسجيل الوجه في قاعدة البيانات
def log_face(user_id, detected):
    timestamp = datetime.datetime.now()
    location = "Camera 1"

    query = "INSERT INTO face_logs (UserID, FaceDetected, Timestamp, Location, Confidence) VALUES (%s, %s, %s, %s, %s)"
    values = (user_id, detected, timestamp, location, 1.0)

    try:
        cursor.execute(query, values)
        db.commit()
        print(f"✅ تم تسجيل الوجه {'(معروف)' if detected else '(غير معروف)'} في قاعدة البيانات")
    except mysql.connector.Error as err:
        print(f"❌ فشل تسجيل الوجه في قاعدة البيانات: {err}")

# بدء تحليل البث المباشر
while True:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is not None and img.size != 0:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img)
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)

            for encoding in face_encodings:
                matches = face_recognition.compare_faces(known_faces, encoding)
                
                if True in matches:
                    match_index = matches.index(True)
                    user_id = known_face_ids[match_index]

                    cursor.execute("SELECT FirstName, LastName, Email FROM users WHERE UserID = %s", (user_id,))
                    user_info = cursor.fetchone()

                    if user_info:
                        send_email(f"الاسم: {user_info[0]} {user_info[1]}\nالبريد الإلكتروني: {user_info[2]}")
                        log_face(user_id, True)  # تسجيل الوجه كـ "معروف"

                else:
                    print("❌ الوجه غير معروف.")
                    log_face(None, False)  # تسجيل الوجه كـ "غير معروف"

            cv2.imshow("Face Detection", img)
        else:
            print("❌ فشل في تحميل الصورة من البث المباشر")

        if cv2.waitKey(1) & 0xFF == 27:
            break

    else:
        print(f"❌ فشل في الحصول على البث المباشر من الكاميرا: {response.status_code}")
        break

cv2.destroyAllWindows()
