# 🚀 KafelCenter ERP — VPS Serverga Deploy Qilish Bo'yicha To'liq Qo'llanma

Ushbu qo'llanma orqali **KafelCenter** loyihasini shaxsiy domeningiz bilan **Ubuntu 22.04 / 24.04** VPS serveriga xavfsiz va professional tarzda joylashtirasiz.

---

## 🏗 Arxitektura

```text
Foydalanuvchi Brauzeri
       │ (HTTPS / SSL)
       ▼
   [ NGINX ] (Port 80 & 443)
   ├── /static/ va /uploads/  ──> To'g'ridan-to'g'ri diskdan tezkor uzatadi
   └── Boshqa barcha so'rovlar ──> [ Gunicorn: 127.0.0.1:5000 ]
                                         │
                                         ▼
                                   [ Flask App ]
                                         │
                                   [ SQLite DB (WAL) ]
```

---

## 1-QADAM: Domen DNS va Server Tayyorgarligi

### 1.1. Server talablari
* **OT**: Ubuntu 22.04 LTS yoki Ubuntu 24.04 LTS
* **Resurslar**: Minimal 1 CPU, 1-2 GB RAM, 20 GB SSD
* **Provayderlar**:
  * O'zbekiston ichida (TAS-IX): Eskiz.uz, Billur.com, Cloud.uz, VDS.uz
  * Xorijda: Hetzner Cloud, DigitalOcean

### 1.2. Domenni server IP siga yo'naltirish
Domen boshqaruv panelingizga (masalan: cPanel, Cloudflare, Reg.uz yoki provayder paneli) kiring va **DNS Records** bo'limida 2 ta **A-Record** qo'shing:

| Turi | Nomi (Host) | Qiymati (Points to) | TTL |
| :--- | :--- | :--- | :--- |
| **A** | `@` (yoki domeningiz) | `SERVER_IP_MANZILI` | Avto / 300 |
| **A** | `www` | `SERVER_IP_MANZILI` | Avto / 300 |

*(Eslatma: DNS yozuvlari tarqalishi uchun 5 daqiqadan 1-2 soatgacha vaqt ketishi mumkin).*

---

## 2-QADAM: Loyihani Serverga Yuklash

Serveringizga SSH orqali kiring (Terminal yoki PuTTY orqali):
```bash
ssh root@SERVER_IP_MANZILI
```

Serverda `/var/www/kafel_magazin` papkasini oching:
```bash
sudo mkdir -p /var/www/kafel_magazin
```

Lokal kompyuteringizdagi `kafel_magazin` papkasini serverga yuklash uchun quyidagi qulay usullardan birini tanlang:

### A) WinSCP dasturi orqali (Eng oson vizual usul):
1. **WinSCP** dasturini oching.
2. Host: `SERVER_IP`, Foydalanuvchi: `root`, Parolingizni kiriting.
3. Kompyuteringizdagi `kafel_magazin` ichidagi barcha fayllarni serverdagi `/var/www/kafel_magazin` papkasiga sudrab tashlang.

### B) SCP buyrug'i orqali (Windows PowerShell yoki Git Bash dan):
```bash
scp -r "C:\Users\MAA9222\Desktop\Новая папка (2)\kafel_magazin\*" root@SERVER_IP_MANZILI:/var/www/kafel_magazin/
```

---

## 3-QADAM: Avtomatik O'rnatish Skriptini Ishga Tushirish

Biz siz uchun barcha jarayonlarni (Python muhiti, Gunicorn, Nginx, Systemd, Firewall, Avto-zaxiralash) avtomatlashtiruvchi tayyor skript yaratdik.

Server terminalida quyidagi buyruqlarni bering:
```bash
cd /var/www/kafel_magazin
sudo chmod +x deploy/setup_vps.sh deploy/backup_db.sh
sudo bash deploy/setup_vps.sh
```

Skript sizdan domeningiz nomini so'raydi (masalan: `kafelcenter.uz`). Domenni kiritib **Enter** bosing.

Skript bir necha daqiqada quyidagilarni bajaradi:
1. Kerakli tizim paketlarini o'rnatadi (`nginx`, `certbot`, `python3-venv`, `sqlite3`).
2. Virtual muhit (`venv`) ochib kutubxonalarni o'rnatadi.
3. Fayl huquqlarini `www-data` foydalanuvchisiga xavfsiz sozlaydi.
4. `kafel.service` ni tizim xizmatiga qo'shadi va ishga tushiradi (server o'chib yonsa ham avtomatik ko'tariladi).
5. Nginx konfiguratsiyasini ulaydi.
6. Har kecha soat 03:00 da avtomatik zaxira (Backup) oladigan rejalashtiruvchini (cron) yoqadi.

---

## 4-QADAM: Bepul SSL (HTTPS) Sertifikatini Faollashtirish

Domen DNS yozuvlari ulanib bo'lgach, domeningizga bepul `https://` yashil qulf belgisini qo'yish uchun serverda quyidagi buyruqni bering:

```bash
sudo certbot --nginx -d SIZNING_DOMENINGIZ.UZ -d www.SIZNING_DOMENINGIZ.UZ
```

Certbot sizdan elektron pochtangizni va shartlarga rozilikni (`Y`) so'raydi. Sertifikat avtomatik o'rnatiladi va har 3 oyda o'zi yangilanib turadi.

Endi saytingizga kiring:
👉 `https://SIZNING_DOMENINGIZ.UZ`

---

## 5-QADAM: Xavfsizlik va Parollarni Yangilash

1. Saytga kiring (`/login`).
2. Dastlabki kirish ma'lumotlari:
   * **Login**: `admin`
   * **Parol**: `admin123`
3. Tizimga kirgach, darhol **Xodimlar** bo'limiga o'tib, admin parolini yangi va mustahkam parolga o'zgartiring!
4. Yangi sotuvchi va omborchi akkauntlarini oching.
5. Serverda `SHOW_DEMO_CREDENTIALS=0` va `FLASK_DEBUG=0` sozlanganligi sababli, login sahifasida demo sinov tugmalari (`admin123`) ko'rinmaydi.

---

## 6-QADAM: Serverni Boshqarish Buyruqlari (Cheat Sheet)

| Vazifa | Buyruq |
| :--- | :--- |
| **Dasturni qayta ishga tushirish** | `sudo systemctl restart kafel` |
| **Dastur holatini ko'rish** | `sudo systemctl status kafel` |
| **Xatoliklar va jonli loglarni ko'rish** | `sudo journalctl -u kafel -f` |
| **Nginx holatini ko'rish** | `sudo systemctl status nginx` |
| **Nginx ni qayta ishga tushirish** | `sudo systemctl restart nginx` |
| **Qo'lda zaxira (backup) olish** | `sudo /var/www/kafel_magazin/deploy/backup_db.sh` |

---

## 7-QADAM: Ma'lumotlar Bazasi Zaxiralari (Backups)

* Har kuni soat **03:00** da butun ma'lumotlar bazasi va yuklangan kafel suratlari avtomatik arxivlanadi.
* Zaxira fayllari serverdagi `/var/backups/kafel/` papkasida saqlanadi.
* Server diskini to'ldirib yubormaslik uchun 30 kundan oshgan arxivlar avtomatik tozalanadi.
* Xohlasangiz, WinSCP orqali haftada 1 marta `/var/backups/kafel/` papkasidagi fayllarni o'z shaxsiy kompyuteringizga ko'chirib saqlab qo'yishingiz mumkin.
