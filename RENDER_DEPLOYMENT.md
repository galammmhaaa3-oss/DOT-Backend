# 🚀 دليل رفع DOT Backend على Render

## 📋 المتطلبات

- حساب على [Render.com](https://render.com) (مجاني)
- حساب GitHub (لرفع الكود)
- Google Maps API Key (موجود)

---

## 🔧 الخطوة 1: تحضير الكود

### ✅ تم بالفعل:
- ✅ `requirements.txt` - قائمة المكتبات
- ✅ `runtime.txt` - إصدار Python
- ✅ `render.yaml` - إعدادات Render
- ✅ `.env.example` - مثال للمتغيرات

### الملفات الجاهزة:
```
backend/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── config.py
│   └── ...
├── requirements.txt    ✅
├── runtime.txt         ✅ (جديد)
├── render.yaml         ✅ (جديد)
└── .env.example        ✅
```

---

## 📦 الخطوة 2: رفع الكود على GitHub

### افتح Terminal وشغّل:

```bash
# 1. انتقل لمجلد Backend
cd C:\Users\ABDULLAH\Desktop\DOT\backend

# 2. Initialize Git (إذا لم يكن موجود)
git init

# 3. أضف الملفات
git add .

# 4. Commit
git commit -m "Initial commit - DOT Backend for Render"

# 5. أنشئ repository على GitHub ثم اربطه
# اذهب إلى github.com → New Repository → اسمه "DOT-Backend"
# ثم:
git remote add origin https://github.com/YOUR_USERNAME/DOT-Backend.git
git branch -M main
git push -u origin main
```

**ملاحظة:** استبدل `YOUR_USERNAME` باسم المستخدم على GitHub

---

## 🌐 الخطوة 3: إنشاء PostgreSQL Database على Render

### 1. اذهب إلى [Render Dashboard](https://dashboard.render.com)

### 2. اضغط **New +** → **PostgreSQL**

### 3. املأ البيانات:
- **Name:** `dot-database`
- **Database:** `dot_db`
- **User:** `dot_user`
- **Region:** Frankfurt (أو الأقرب لسوريا)
- **Plan:** **Free**

### 4. اضغط **Create Database**

### 5. احفظ المعلومات:
بعد الإنشاء، ستجد:
- **Internal Database URL** (استخدمه للـ Backend)
- **External Database URL** (للاتصال من جهازك)

---

## 🚀 الخطوة 4: إنشاء Web Service للـ Backend

### 1. اضغط **New +** → **Web Service**

### 2. اختر **Connect a repository**
- صل حساب GitHub
- اختر `DOT-Backend` repository

### 3. املأ البيانات:
- **Name:** `dot-backend`
- **Region:** Frankfurt
- **Branch:** `main`
- **Root Directory:** (اتركه فارغ)
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Plan:** Free

### 4. أضف Environment Variables:
اضغط **Advanced** ثم **Add Environment Variable**:

```
DATABASE_URL = [اختر من القائمة: dot-database → Internal Database URL]
SECRET_KEY = [أي قيمة عشوائية طويلة، مثل: your-super-secret-key-123456789]
GOOGLE_MAPS_API_KEY = AIzaSyCSOCXV_5b8a7Om3F1UQY82ED-vjraBK0U
ALGORITHM = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 10080
DEFAULT_COMMISSION = 5000
```

### 5. اضغط **Create Web Service**

---

## ⏳ الخطوة 5: انتظر البناء

- Render سيبدأ ببناء المشروع (5-10 دقائق)
- راقب الـ Logs في الصفحة
- عند النجاح، ستظهر رسالة: **"Live"** بجانب الخدمة

---

## 🔗 الخطوة 6: احصل على الرابط

بعد النجاح:
- **Backend URL:** `https://dot-backend.onrender.com`
- هذا هو رابط الـ API الخاص بك!

---

## 📱 الخطوة 7: تحديث Flutter App

### افتح `lib/config/api_constants.dart`:

```dart
class ApiConstants {
  // قبل:
  // static const String baseUrl = 'http://localhost:8000';
  
  // بعد:
  static const String baseUrl = 'https://dot-backend.onrender.com';
  
  // باقي الكود...
}
```

**احفظ وشغّل التطبيق!**

---

## 🧪 الخطوة 8: اختبار الـ API

### 1. Test Health Check:
افتح المتصفح:
```
https://dot-backend.onrender.com/
```
يجب أن تشاهد: `{"message": "Welcome to DOT API"}`

### 2. Test Docs:
```
https://dot-backend.onrender.com/docs
```
ستفتح صفحة FastAPI التفاعلية!

### 3. إنشاء مستخدم Admin:
من Swagger UI (صفحة /docs):
1. اذهب إلى **POST /auth/register**
2. Try it out
3. Body:
```json
{
  "phone": "0999999999",
  "email": "admin@dot.com",
  "name": "Admin",
  "password": "admin123",
  "role": "admin"
}
```
4. Execute

---

## ✅ اختبار كامل من Flutter

### 1. شغّل التطبيق
```bash
flutter run
```

### 2. سجّل حساب جديد
- الاسم: Test User
- الهاتف: 0944123456
- الإيميل: test@example.com
- كلمة المرور: test123

### 3. اطلب تاكسي أو توصيل
- اختر المواقع
- أكد الطلب
- **سيُحفظ في قاعدة البيانات على Render!**

---

## 🔄 تحديث الكود لاحقاً

عندما تعدّل الكود وتريد رفعه:

```bash
cd backend
git add .
git commit -m "Update: [وصف التعديل]"
git push
```

**Render سيكتشف التحديث ويُعيد البناء تلقائياً!** ✨

---

## 🐛 حل المشاكل الشائعة

### 1. Build Failed:
- تحقق من `requirements.txt`
- تأكد من `runtime.txt` (python-3.11.0)

### 2. Database Connection Error:
- تأكد من `DATABASE_URL` في Environment Variables
- استخدم **Internal Database URL** وليس External

### 3. Service Not Responding:
- انتظر 5-10 دقائق (قد يكون النشر بطيئاً)
- تحقق من Logs في Render Dashboard

### 4. Free Plan Sleep:
- الخدمة المجانية تنام بعد 15 دقيقة من عدم الاستخدام
- أول طلب بعد النوم قد يأخذ 30-60 ثانية

---

## 💡 نصائح

### 1. Keep Alive (منع النوم):
استخدم خدمة مثل [UptimeRobot](https://uptimerobot.com) لإرسال ping كل 5 دقائق

### 2. View Logs:
من Render Dashboard → اختر الخدمة → Logs (لمراقبة الأخطاء)

### 3. Database Backup:
Render يحفظ 7 أيام من النسخ الاحتياطية تلقائياً (Free Plan)

---

## 📊 الخلاصة

✅ **ما تم:**
1. Backend جاهز للنشر
2. PostgreSQL Database جاهزة
3. Flutter App يتصل بالخادم الحقيقي

✅ **روابط مهمة:**
- Backend: `https://dot-backend.onrender.com`
- API Docs: `https://dot-backend.onrender.com/docs`
- Database: على Render Dashboard

✅ **الخطوة التالية:**
- رفع الكود على GitHub
- إنشاء Database على Render
- إنشاء Web Service
- تحديث Flutter App
- **استمتع بالتطبيق الحقيقي!** 🎉

---

## 🆘 المساعدة

إذا واجهت مشكلة:
1. تحقق من Logs على Render
2. تأكد من Environment Variables
3. اختبر الـ API من المتصفح أولاً
4. تحقق من `api_constants.dart` في Flutter

**التطبيق جاهز للعمل بشكل واقعي 100%!** ✨
