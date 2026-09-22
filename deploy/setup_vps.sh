#!/bin/bash
# ==========================================================
# KafelCenter ERP - Ubuntu 22.04/24.04 Avtomatik Deploy Skripti
# Ishga tushirish: sudo bash deploy/setup_vps.sh
# ==========================================================

set -e

echo "=========================================================="
echo "    KAFELCENTER ERP - SERVERGA O'RNATISH BOSHLANDI       "
echo "=========================================================="

if [ "$EUID" -ne 0 ]; then
  echo "Iltimos, ushbu skriptni 'sudo' huquqi bilan ishga tushiring!"
  exit 1
fi

read -p "Iltimos, domeningizni kiriting (masalan, kafelcenter.uz): " DOMAIN_NAME
if [ -z "$DOMAIN_NAME" ]; then
    echo "Xato: Domen nomi kiritilmadi!"
    exit 1
fi

APP_DIR="/var/www/kafel_magazin"
LOG_DIR="/var/log/kafel"

echo "1. Server paketlari yangilanmoqda va zaruriy dasturlar o'rnatilmoqda..."
apt update -y
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx sqlite3 tar ufw

echo "2. Papkalar va log yo'llari sozlanmoqda..."
mkdir -p "$LOG_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/uploads/products"
mkdir -p "$APP_DIR/uploads/qrcodes"

echo "3. Python Virtual Muhiti (venv) yaratilmoqda..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

echo "4. Kerakli Python kutubxonalari o'rnatilmoqda..."
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "5. Fayl huquqlari (permissions) sozlanmoqda..."
chown -R www-data:www-data "$APP_DIR"
chown -R www-data:www-data "$LOG_DIR"
chmod -R 775 "$APP_DIR/uploads"
chmod 664 "$APP_DIR/kafel_database.db"* 2>/dev/null || true

echo "6. Systemd xizmati o'rnatilmoqda..."
cp "$APP_DIR/deploy/kafel.service" /etc/systemd/system/kafel.service
systemctl daemon-reload
systemctl enable kafel
systemctl restart kafel

echo "7. Nginx konfiguratsiyasi sozlanmoqda..."
sed -i "s/SIZNING_DOMENINGIZ.UZ/$DOMAIN_NAME/g" "$APP_DIR/deploy/nginx_kafel.conf"
cp "$APP_DIR/deploy/nginx_kafel.conf" "/etc/nginx/sites-available/kafel"
ln -sf /etc/nginx/sites-available/kafel /etc/nginx/sites-enabled/kafel
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx

echo "8. Har kungi avtomatik zaxiralash (Backup) cron sozlanmoqda..."
chmod +x "$APP_DIR/deploy/backup_db.sh"
CRON_JOB="0 3 * * * /bin/bash $APP_DIR/deploy/backup_db.sh >> /var/log/kafel/backup.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "$APP_DIR/deploy/backup_db.sh" ; echo "$CRON_JOB") | crontab -

echo "9. Xavfsizlik devori (UFW Firewall) ochilmoqda..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable || true

echo "=========================================================="
echo "    O'RNATISH MUVAFFAQIYATLI YAKUNLANDI!                 "
echo "=========================================================="
echo "Dastur serverda ishga tushdi: http://$DOMAIN_NAME"
echo ""
echo "KEYINGI QADAM (SSL / HTTPS Bepul Sertifikat):"
echo "Domeningiz DNS sozlamasida serveringiz IP manziliga ulangach, quyidagi buyruqni bering:"
echo "    sudo certbot --nginx -d $DOMAIN_NAME -d www.$DOMAIN_NAME"
echo "=========================================================="
