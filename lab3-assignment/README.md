# تقرير الواجب الثالث: خدمة جدولة الامتحانات (Exam Scheduler Service)

**اسم الطالب:** محمد وائل بصل  
**الرقم الجامعي:** 120230168  
**المساق:** BSWE 4123 - مختبر نظم البرمجة الموزعة (Distributed Software Systems Laboratory)  
**الجامعة:** جامعة فلسطين (University of Palestine)  

---

## 1. تعليمات الإعداد والتشغيل (Setup & Execution Instructions)

### أ. تثبيت المكتبات والاعتماديات (Dependencies)
قم بتثبيت المكتبات المطلوبة للتشغيل باستخدام الأمر التالي:
```bash
pip install -r requirements.txt
```

### ب. تشغيل الخدمات على منافذ مستقلة (Separate Ports)

1. **الموجه الأول (Terminal 1): تشغيل خدمة حجز القاعات (Room Booking Service) على المنفذ 8000**
   ```bash
   DELAY=0.0 uvicorn room_booking_service:app --port 8000
   ```

2. **الموجه الثاني (Terminal 2): تشغيل خدمة جدولة الامتحانات (Exam Scheduler Service) على المنفذ 8001**
   ```bash
   ROOM_SERVICE_URL="http://localhost:8000" TIMEOUT=2.0 MAX_RETRIES=3 uvicorn main:app --port 8001
   ```

3. **الموجه الثالث (Terminal 3): تشغيل سكريبت الاختبار الآلي (Automated Test Suite)**
   ```bash
   python test_scheduler.py
   ```

---

## 2. إعدادات متغيرات البيئة (Configuration Parameters)

تقوم خدمة جدولة الامتحانات (`Exam Scheduler Service`) بقراءة جميع إعداداتها المباشرة من متغيرات البيئة، ويمكن عرض الإعدادات الحالية من خلال نقطة النهاية `GET /config`:

* **`ROOM_SERVICE_URL`**: عنوان خدمة حجز القاعات المُراد الاتصال بها (القيمة الافتراضية: `http://localhost:8000`).
* **`TIMEOUT`**: مهلة انتظار استجابة الطلب بالثواني (القيمة الافتراضية: `2.0`).
* **`MAX_RETRIES`**: الحد الأقصى لعدد محاولات إعادة الاتصال عند الفشل (القيمة الافتراضية: `3`).

---

## 3. الخطوة 3: تحليل آلية إعادة المحاولة والموثوقية (Retry & Resilience Analysis)

### أ. سجل التشغيل عند إيقاف وإعادة تشغيل الخدمة (Execution Log)

عند تشغيل الاختبار وإيقاف خدمة حجز القاعات ثم إعادة تشغيلها أثناء المحاولات، تظهر السجلات التالية:

```text
==================================================
 Starting Automated Tests for Exam Scheduler (Lab 3)
==================================================

--- 1. Testing GET /config ---
Status Code: 200
Response: {'room_service_url': 'http://localhost:8000', 'timeout': 2.0, 'max_retries': 3}

--- 2. Testing Retry Mechanism (Service Restart Test) ---
[Attempt 1/3] Failed to connect to Room Booking Service. Retrying in 0.5s...
[Attempt 2/3] Failed to connect to Room Booking Service. Retrying in 1.0s...
[تم إعادة تشغيل خدمة حجز القاعات بنجاح]
[Attempt 3/3] Connected successfully! Room R101 booked.
Status Code: 201
Total Execution Time: 2314.50 ms
Response: {'message': 'Exam scheduled successfully', 'exam_id': 'EXAM-103', 'booked_room': {'id': 'R101', 'capacity': 30}}
```

### ب. شرح أمان إعادة المحاولة خاصية التكرار الآمن (Idempotency Safety)

تعتبر إعادة محاولة إرسال طلبات `PUT /bookings/{booking_id}` آمنة تماماً لأن نقطة النهاية الخاصة بالحجز تصمّم بخاصية **التكرار الآمن (Idempotence)**:
1. تقوم خدمة الجدولة بتوليد معرف حجز فريد للطلب مثل `booking-exam-EXAM-103`.
2. في حال حدوث انقطاع في الشبكة بعد أن قامت خدمة حجز القاعات بمعالجة الطلب بالفعل، فإن إعادة محاولة الطلب بنفس المعرف `booking_id` تُعيد النتيجة الناجحة `200 OK` دون تكرار الحجز أو إحداث تعارض في البيانات.

---

## 4. الخطوة 4: تحليل المفاضلة بين التأخير ومهلة الانتظار (Delay & Timeout Trade-off Analysis)

### أ. جدول نتائج الاختبارات (Test Results Matrix)

| السيناريو (Scenario) | تأخير الخدمة (`DELAY`) | مهلة الانتظار (`TIMEOUT`) | كود الاستجابة (Status Code) | زمن الاستجابة (Response Time) | النتيجة التشغيلية (Operational Result) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **الحالة الأولى (Case 1)** | `0.1s` | `2.0s` | `201 Created` | ~115 ms | نجاح سريع ومباشر في الظروف العادية low-latency. |
| **الحالة الثانية (Case 2)** | `2.5s` | `2.0s` | `503 Service Unavailable` | ~6050 ms | فشل الطلب بعد استنفاد المحاولات لأن تأخير السيرفر أكبر من المهلة المحددة. |
| **الحالة الثالثة (Case 3)** | `1.5s` | `3.0s` | `201 Created` | ~1510 ms | نجاح الطلب بعد رفع قيمة المهلة لتصبح أكبر من تأخير الخدمة. |

### ب. الشرح التحليلي للمفاضلة (Trade-off Explanation)

* **المهلة القصيرة (Short Timeout - e.g., 2.0s):**
  * **الميزة:** تُنهي الطلبات الفاشلة بسرعة (Fail Fast) وتمنع حجز موارد سيرفر الجدولة لفترات طويلة عند توقف الخدمة الأخرى.
  * **العيب:** قد تتسبب في إسقاط طلبات ناجحة لمجرد وجود بطء مؤقت في الشبكة أو السيرفر.
* **المهلة الطويلة (Long Timeout - e.g., 5.0s):**
  * **الميزة:** تزيد من نسبة نجاح الطلبات في ظروف الشبكة البطيئة أو عند وجود تأخير في الاستجابة.
  * **العيب:** تُبقي الاتصالات مفتوحة لفترة طويلة وتزيد من وقت انتظار المستخدم عند حدوث عطل حقيقي في الخدمة.
