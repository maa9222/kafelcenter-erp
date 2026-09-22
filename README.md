# 🏢 KafelCenter ERP — Kafel Do'koni Ombor va Kassa Tizimi

Kafel savdosi bilan shug'ullanuvchi korxonalar va do'konlar uchun mo'ljallangan zamonaviy, tezkor va xavfsiz boshqaruv tizimi (ERP / CRM / POS).

---

## 🌟 Asosiy Imkoniyatlar

* 📦 **Ombor Boshqaruvi**: Kafel qoldiqlari (m² va qutilarda), kirim/chiqim tarixi, qoldiq limiti ogohlantirishlari.
* 💳 **Kassa & Savdo (POS)**: Tezkor savdo, chek chiqarish, naqd/karta/aralash to'lovlar, smeta hisoblash.
* 👥 **Mijozlar & Nasiya Daftari (CRM)**: Mijozlar bazasi, qarzlar (nasiya) hisobi va to'lovlar tarixi.
* 🛠 **Ustalar & Referral**: Usta va prorablar bilan ishlash, mijoz olib kelgan ustalar uchun bonuslar hisobi.
* 📉 **Siniqlar va Brak Kafellar**: Do'kon yoki omborda singan, brak bo'lgan kafellar hisobi, ularni arzonlashtirilgan narxda sotish tizimi.
* 📊 **Hisobot va Tahlil (Analytics)**: Kunlik, oylik va davriy savdo hisobotlari, sof foyda tahlili, grafiklar.
* 🏆 **Xodimlar KPI**: Sotuvchilar va omborchilar natijalari, umumiy daromad va bonuslar hisob-kitobi.
* 🏷 **QR-kod Stikerlar**: Har bir kafel modeli uchun avtomatik QR-kod generatsiya qilish va stiker chop etish.
* 🔐 **Kiberxavfsizlik**: Rollarga asoslangan kirish (Admin, Sotuvchi, Omborchi), Brute-force hujumlaridan himoya (5 ta noto'g'ri urinishda bloklash), xavfsiz sessiyalar.

---

## 🛠 Texnologiyalar

* **Backend**: Python 3.12, Flask 3.0
* **Ma'lumotlar bazasi**: SQLite3 (WAL rejimida, yuqori tezlik)
* **Frontend**: HTML5, Jinja2, TailwindCSS, FontAwesome
* **Kutubxonalar**: Pillow, QRCode, Gunicorn

---

## 🚀 Ishga Tushirish (Lokal kompyuterda)

### Windows:
Faqatgina `ishga_tushirish.bat` faylini ikki marta bosing. Dastur kutubxonalarni o'rnatib, brauzerda avtomatik ochiladi:
👉 `http://localhost:5000`

### Linux / MacOS:
```bash
# 1. Virtual muhit yaratish va faollashtirish
python3 -m venv venv
source venv/bin/activate

# 2. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 3. Dasturni ishga tushirish
python app.py
```

---

## 🌐 Serverga Deploy Qilish

Loyihada deploy qilish uchun to'liq qo'llanmalar tayyorlangan:
* **VPS Server (Ubuntu + Nginx + SSL)**: [`DEPLOY_QOLLANMA.md`](DEPLOY_QOLLANMA.md)
* **PythonAnywhere**: [`PYTHONANYWHERE_QOLLANMA.md`](PYTHONANYWHERE_QOLLANMA.md)

---

## 🔑 Dastlabki Kirish Ma'lumotlari

| Rol | Login | Boshlang'ich Parol |
| :--- | :--- | :--- |
| **👑 Admin** | `admin` | `admin123` |
| **📱 Sotuvchi** | `sotuvchi` | `sotuvchi123` |
| **📦 Omborchi** | `omborchi` | `omborchi123` |

*(Serverga o'rnatgandan so'ng, xavfsizlik uchun parollarni darhol o'zgartirish tavsiya etiladi).*
