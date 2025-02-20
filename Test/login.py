from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Skarpt@2021'
app.config['MYSQL_DB'] = 'usersdb'

# إعدادات تحميل الصور
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

mysql = MySQL(app)

# وظيفة للتحقق من امتداد الملف
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# التأكد من وجود مجلد التحميل
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# صفحة التسجيل
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        
        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO users (FirstName, LastName, Email, PasswordHash) VALUES (%s, %s, %s, %s)', 
                       (first_name, last_name, email, password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# صفحة تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE Email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and user[4] == password:  # مقارنة كلمة المرور مباشرة
            session['user_id'] = user[0]
            return redirect(url_for('profile'))
        flash('Invalid credentials')
        return redirect(url_for('login'))
    return render_template('login.html')

# صفحة الملف التعريفي
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM users WHERE UserID = %s', (session['user_id'],))
    user = cursor.fetchone()

    # جلب بيانات السجلات من face_logs
    cursor.execute('SELECT Timestamp, Location, Confidence FROM face_logs WHERE UserID = %s ORDER BY Timestamp DESC', (session['user_id'],))
    logs = cursor.fetchall()
    cursor.close()

    # تحميل الصورة الجديدة إذا تم تحديدها
    if request.method == 'POST' and 'profile_picture' in request.files:
        file = request.files['profile_picture']
        if file and allowed_file(file.filename):
            # استخدام UserID لتسمية الصورة
            user_id = session['user_id']
            filename = f"{user_id}_{secure_filename(file.filename)}"  # اسم الصورة يكون UserID مع اسم الملف الأصلي
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            # تحديث الصورة في قاعدة البيانات
            cursor = mysql.connection.cursor()
            with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'rb') as img_file:
                file_data = img_file.read()
                cursor.execute('UPDATE users SET ProfileImage = %s WHERE UserID = %s', (file_data, session['user_id']))
                mysql.connection.commit()
            cursor.close()
            return redirect(url_for('profile'))

    # جلب اسم الصورة من قاعدة البيانات
    profile_picture = user[5] if user[5] else None
    profile_image_data = None

    if profile_picture:
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT ProfileImage FROM users WHERE UserID = %s', (session['user_id'],))
        image_data = cursor.fetchone()
        cursor.close()

        if image_data and image_data[0]:
            # تحويل الصورة إلى Base64 لكي يتم عرضها في HTML
            profile_image_data = base64.b64encode(image_data[0]).decode('utf-8')

    # استخدام صورة افتراضية في حال لم تكن موجودة
    if not profile_picture:
        profile_picture = 'default_profile_pic.jpeg'

    return render_template('profile.html', user=user, profile_picture=profile_picture, logs=logs, profile_image_data=profile_image_data)

# تسجيل الخروج
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
