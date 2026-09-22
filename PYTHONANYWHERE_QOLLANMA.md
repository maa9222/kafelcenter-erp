# 🐍 KafelCenter ERP — PythonAnywhere-ga Deploy Qilish Bo'yicha To'liq Qo'llanma

**PythonAnywhere** — Python/Flask loyihalarini server sozlamalari (Linux/Nginx buyruqlari)siz, to'g'ridan-to'g'ri brauzer orqali boshqarish imkonini beruvchi eng qulay platformadir.

---

## ⚠️ Muhim Eslatma (Shaxsiy Domen Uchun):
* PythonAnywhere-da **bepul hisob** faqat `username.pythonanywhere.com` manzilida ishlaydi.
* O'zingizning **shaxsiy domeningizni** (masalan, `kafelcenter.uz` yoki `www.kafelcenter.uz`) ulash uchun PythonAnywhere-ning **"Hacker Plan"** ($5/oy) tarifi kerak bo'ladi.
* Doimiy disk (Persistent storage) mavjud bo'lib, SQLite bazangiz va yuklangan kafel rasmlari hech qachon o'chib ketmaydi.

---

## 1-QADAM: PythonAnywhere-da Ro'yxatdan O'tish va Web App Yaratish

1. [pythonanywhere.com](https://www.pythonanywhere.com) saytiga kiring va ro'yxatdan o'ting (username tanlang, masalan: `akmal`).
2. Agar o'z domeningizni ulamoqchi bo'lsangiz, **Account** -> **Upgrade** bo'limidan **Hacker Plan** ($5/oy) ni faollashtiring.
3. Yuqori menyudan **Web** bo'limiga o'ting va **"Add a new web app"** tugmasini bosing:
   * **Domain name**: domeningizni yozing (masalan: `www.sizningdomeningiz.uz`).
   * **Framework**: **Manual configuration** (yoki Flask emas, aynan **Manual configuration** tanlang — bu to'liq nazorat beradi).
   * **Python version**: **Python 3.10** yoki **Python 3.11** ni tanlang.

---

## 2-QADAM: Loyiha Fayllarini Yuklash

### Usul 1: ZIP qilib yuklash (Eng oson)
1. Shaxsiy kompyuteringizdagi `kafel_magazin` papkasini arxivlab `kafel_magazin.zip` qiling.
2. PythonAnywhere boshqaruv panelida **Files** bo'limiga o'ting.
3. `/home/<username>/` sahifasida **"Upload a file"** tugmasi orqali `kafel_magazin.zip` faylini yuklang.
4. **Consoles** bo'limiga o'tib, **Bash** konsolini oching va arxivni oching:
   ```bash
   unzip kafel_magazin.zip -d kafel_magazin
   ```

### Usul 2: Git orqali klonlash (agar GitHub/GitLab bo'lsa)
PythonAnywhere **Bash** konsolida:
```bash
git clone <sizning_repo_url> kafel_magazin
```

---

## 3-QADAM: Virtual Muhit (Virtualenv) Yaratish va Kutubxonalarni O'rnatish

PythonAnywhere **Bash** konsolida quyidagi buyruqlarni navbat bilan bajaring:

```bash
# Loyiha papkasiga kirish
cd /home/<username>/kafel_magazin

# Virtual muhit yaratish (masalan: kafel_env)
python3.10 -m venv /home/<username>/kafel_env

# Virtual muhitni faollashtirish
source /home/<username>/kafel_env/bin/activate

# Kutubxonalarni o'rnatish
pip install --upgrade pip
pip install -r requirements.txt
```

*(Eslatma: `<username>` o'rniga o'zingizning PythonAnywhere foydalanuvchi nomingizni yozasiz, masalan: `akmal`)*.

---

## 4-QADAM: Web Bo'limini Sozlash

Yuqori menyudagi **Web** tabiga o'ting va quyidagi bo'limlarni to'ldiring:

### 1. Code bo'limi:
* **Source code**: `/home/<username>/kafel_magazin`
* **Working directory**: `/home/<username>/kafel_magazin`

### 2. Virtualenv bo'limi:
* **Virtualenv path**: `/home/<username>/kafel_env`

### 3. WSGI configuration file:
* Ko'k rangda yozilgan `/var/www/<username>_..._wsgi.py` fayl havolasini bosing.
* Ichidagi barcha yozuvlarni tozalab (o'chirib), quyidagi kodni qo'ying:

```python
import sys
import os

# Loyiha joylashgan papka
path = '/home/<username>/kafel_magazin'
if path not in sys.path:
    sys.path.insert(0, path)

# Xavfsizlik sozlamalari
os.environ["FLASK_DEBUG"] = "0"
os.environ["SHOW_DEMO_CREDENTIALS"] = "0"

# Flask ilovasini 'application' nomi bilan yuklaymiz
from app import app as application
```
*(Yuqoridagi `<username>` ni o'z profilingiz nomiga o'zgartiring va **Save** tugmasini bosing).*

---

## 5-QADAM: Statik va Yuklangan Rasmlar (Static Files) Sozlamasi

Kafel rasmlari va sahifa dizaynlari tez va muammosiz ochilishi uchun **Web** sahifasining pastki qismidagi **"Static files"** jadvaliga 2 ta qator qo'shing:

| URL | Directory |
| :--- | :--- |
| `/static/` | `/home/<username>/kafel_magazin/static/` |
| `/uploads/` | `/home/<username>/kafel_magazin/uploads/` |

---

## 6-QADAM: Domen va Bepul SSL (HTTPS) Sozlamasi

1. **Domen DNS sozlamasi**:
   * PythonAnywhere sizning Web tabingizda CNAME manzil beradi (masalan: `webapp-123456.pythonanywhere.com`).
   * Domeningiz boshqaruv paneliga kiring va quyidagicha **CNAME** yozuvini qo'shing:
     * **Host**: `www`
     * **Points to / Target**: `webapp-123456.pythonanywhere.com` (Web tabdagi aniq manzil)
2. **HTTPS (Yashil qulf) yoqish**:
   * **Web** sahifasining **"Security"** bo'limida:
     * **Force HTTPS**: `Enabled` (yoqilgan) qiling.
     * **SSL Certificate**: **"Let's Encrypt"** tugmasini bosing — bepul HTTPS avtomatik o'rnatiladi.

---

## 7-QADAM: Ishga Tushirish (Reload)

Barcha sozlamalar kiritilgach:
* **Web** tabining eng yuqorisidagi yashil **"Reload <domeningiz>"** tugmasini bosing!
* Brauzerda domeningizni oching: `https://www.sizningdomeningiz.uz`

---

## 💡 Foydali Maslahatlar

1. **Birinchi kirish**:
   * Login: `admin`, Parol: `admin123`.
   * Tizimga kirgach, darhol **Xodimlar** sahifasiga o'tib parolni o'zgartiring.
2. **Xatoliklar yuz bersa**:
   * **Web** tabining pastida **Log files** bo'limi bor:
     * **Error log**: Flask kodidagi barcha xatolarni ko'rsatadi.
     * **Server log**: PythonAnywhere server xabarlarini ko'rsatadi.
