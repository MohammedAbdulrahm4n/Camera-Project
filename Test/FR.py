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
cursor.execute("SELECT UserID, ProfileImage FROM users")
users = cursor.fetchall()

known_faces = []
known_face_ids = []

for user in users:
    user_id, profile_image = user

    if profile_image:
        try:
            image_array = np.frombuffer(profile_image, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                known_faces.append(encodings[0])
                known_face_ids.append(user_id)
        except Exception as e:
            print(f"⚠️ خطأ في تحميل صورة المستخدم {user_id}: {e}")

# دالة لإرسال البريد الإلكتروني
def send_email(user_info, image_path):
    subject = "تم اكتشاف وجه!"
    body = f"تم اكتشاف وجه عبر الكاميرا.\n\nمعلومات الشخص:\n{user_info}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with open(image_path, "rb") as attachment:
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(image_path)}")
            msg.attach(part)

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("📩 تم إرسال البريد الإلكتروني مع الصورة.")
    except Exception as e:
        print(f"❌ فشل في إرسال البريد الإلكتروني: {e}")

# حفظ الوجه غير المعروف
def save_unknown_face(face_img, count):
    if not os.path.exists('static/snapshots'):
        os.makedirs('static/snapshots')
    
    filename = f"static/snapshots/unknown_face_{count}.jpg"
    cv2.imwrite(filename, face_img)
    print(f"📸 تم حفظ سناب شوت للوجه المجهول في: {filename}")
    return filename

# تسجيل الوجه في قاعدة البيانات
def log_face(user_id, face_img):
    _, img_encoded = cv2.imencode('.jpg', face_img)
    face_blob = img_encoded.tobytes()
    
    timestamp = datetime.datetime.now()
    location = "Camera 1"  # يمكنك تحديثها لاحقًا بالموقع الفعلي

    query = "INSERT INTO face_logs (UserID, FaceDetected, Timestamp, Location, Confidence) VALUES (%s, %s, %s, %s, %s)"
    values = (user_id, face_blob, timestamp, location, 1.0)

    try:
        cursor.execute(query, values)
        db.commit()
        print("✅ تم تسجيل الوجه في قاعدة البيانات")
    except mysql.connector.Error as err:
        print(f"❌ فشل تسجيل الوجه في قاعدة البيانات: {err}")

# بدء تحليل البث المباشر
unknown_face_count = 0
while True:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is not None and img.size != 0:
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img)
            face_encodings = face_recognition.face_encodings(rgb_img, face_locations)

            for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                matches = face_recognition.compare_faces(known_faces, encoding)
                face_img = img[top:bottom, left:right]

                if True in matches:
                    match_index = matches.index(True)
                    user_id = known_face_ids[match_index]

                    cursor.execute("SELECT FirstName, LastName, Email FROM users WHERE UserID = %s", (user_id,))
                    user_info = cursor.fetchone()

                    if user_info:
                        face_filename = f"static/snapshots/user_{user_id}.jpg"
                        cv2.imwrite(face_filename, face_img)

                        send_email(f"الاسم: {user_info[0]} {user_info[1]}\nالبريد الإلكتروني: {user_info[2]}", face_filename)
                        log_face(user_id, face_img)  # تسجيل الوجه في قاعدة البيانات

                else:
                    print("❌ الوجه غير معروف.")
                    unknown_face_count += 1
                    unknown_face_path = save_unknown_face(face_img, unknown_face_count)

            cv2.imshow("Face Detection", img)
        else:
            print("❌ فشل في تحميل الصورة من البث المباشر")

        if cv2.waitKey(1) & 0xFF == 27:
            break

    else:
        print(f"❌ فشل في الحصول على البث المباشر من الكاميرا: {response.status_code}")
        break

cv2.destroyAllWindows()
