# 🚀 KafelCenter ERP — Render.com va Cloudflare Domeni Bilan Deploy Qilish

Ushbu usul eng tezkor va qulay bo'lib, loyihangiz allaqachon **GitHub**-da turganligi sababli bor-yo'g'i **2-3 daqiqa** vaqtingizni oladi.

---

## 1-QADAM: Render.com Saytida Ro'yxatdan O'tish

1. Brauzerda **[dashboard.render.com](https://dashboard.render.com)** saytiga kiring.
2. **"Sign in with GitHub"** (GitHub orqali kirish) tugmasini bosing.
3. GitHub hisobingizga ruxsat bering.

---

## 2-QADAM: Yangi Web Service Yaratish

1. Render boshqaruv panelining yuqori o'ng burchagidagi ko'k **"New +"** tugmasini bosing.
2. Ro'yxatdan **"Web Service"** ni tanlang.
3. **"Connect a repository"** bo'limida **`maa9222/kafelcenter-erp`** repozitoriyangizni ko'rasiz. Yonidagi **"Connect"** tugmasini bosing.
   *(Agar ko'rinmasa, "Configure GitHub" tugmasini bosib, barcha repolarga ruxsat bering).*
4. Quyidagi sozlamalarni tekshiring:
   * **Name**: `kafelcenter-erp`
   * **Region**: `Frankfurt (EU Central)` *(O'zbekistonga eng yaqin va tezkor)*
   * **Branch**: `main`
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `gunicorn wsgi:app`
   * **Instance Type**: **Free** ($0/month)
5. Eng pastdagi **"Deploy Web Service"** tugmasini bosing!

---

## 3-QADAM: Ishga Tushishini Kuzatish

Render konsolida dastur yig'iladi:
* Python kutubxonalari o'rnatiladi.
* Gunicorn ishga tushadi.
* 1-2 daqiqada yashil rangda **"Live"** yozuvi chiqadi.
* Render sizga havola beradi (masalan: `https://kafelcenter-erp.onrender.com`).
* Havolani bosib, tizim to'liq ishlayotganiga ishonch hosil qiling!

---

## 4-QADAM: Cloudflare Domeningizni Bog'lash

Saytingiz o'z domeningizda ochilishi uchun:

1. Render-da loyihangiz sahifasida chap menyudan **"Settings"** bo'limiga kiring.
2. Pastroqqa tushib, **"Custom Domains"** bo'limini toping.
3. **"Add Custom Domain"** tugmasini bosing va o'z domeningizni yozing:
   * Masalan: `kafelcenter.uz` (yoki `www.kafelcenter.uz`).
4. **"Save"** tugmasini bosing. Render sizga Cloudflare uchun sozlamani ko'rsatadi:
   * **Type**: `CNAME`
   * **Name**: `www` (yoki `@`)
   * **Target / Value**: `kafelcenter-erp.onrender.com`

---

## 5-QADAM: Cloudflare DNS Paneliga Yozish

1. **[dash.cloudflare.com](https://dash.cloudflare.com)** saytiga kiring.
2. O'z domeningizni tanlang.
3. Chap menyudan **DNS** ➔ **Records** bo'limiga o'ting.
4. **"Add record"** tugmasini bosing:
   * **Type**: `CNAME`
   * **Name**: `@` (yoki domeningiz)
   * **Target**: `kafelcenter-erp.onrender.com` (Render ko'rsatgan havola)
   * **Proxy status**: **Proxied** (To'q sariq bulutcha yoqilgan tursin — bu bepul SSL va DDoS himoyasini beradi).
   * **Save** qiling.
5. Xuddi shunday `www` uchun ham CNAME qo'shing:
   * **Type**: `CNAME`
   * **Name**: `www`
   * **Target**: `kafelcenter-erp.onrender.com`
   * **Save** qiling.

---

## 🎉 Natija:
* 5-10 daqiqa ichida domeningiz (`https://sizningdomeningiz.uz`) to'liq ishga tushadi.
* Sayt Cloudflare orqali himoyalanadi va yashil qulf (SSL) avtomatik faol bo'ladi.
* Do'kon xodimlari istalgan joydan domeningiz orqali tizimga kira oladilar!
