import os
import json
import sqlite3
import qrcode
import time
import secrets
from collections import defaultdict
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from PIL import Image

import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_or_create_secret_key():
    env_key = os.environ.get("FLASK_SECRET_KEY")
    if env_key:
        return env_key
    key_file = os.path.join(BASE_DIR, ".secret_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if len(k) >= 32:
                    return k
        except Exception:
            pass
    new_key = secrets.token_hex(32)
    try:
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
    except Exception:
        pass
    return new_key

app = Flask(__name__)
app.secret_key = get_or_create_secret_key()

# Kiberxavfsizlik: Xavfsiz sessiya va Cookie sozlamalari
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # XSS orqali sessiyani o'g'irlashdan himoya
    SESSION_COOKIE_SAMESITE="Lax",      # CSRF hujumlaridan himoya
    SESSION_COOKIE_NAME="kafel_secure_session",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  # 8 soatdan so'ng sessiya avtomatik tugaydi
)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PRODUCT_UPLOADS = os.path.join(UPLOAD_FOLDER, "products")
QR_UPLOADS = os.path.join(UPLOAD_FOLDER, "qrcodes")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

os.makedirs(PRODUCT_UPLOADS, exist_ok=True)
os.makedirs(QR_UPLOADS, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_qr_image(sku_code):
    """Mahsulot SKU kodi uchun QR kod yaratadi va uploads/qrcodes/ papkasiga saqlaydi"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(sku_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    
    filename = f"qr_{sku_code}.png"
    filepath = os.path.join(QR_UPLOADS, filename)
    img.save(filepath)
    return f"/uploads/qrcodes/{filename}"

@app.route("/uploads/<path:subpath>")
def serve_uploads(subpath):
    return send_from_directory(UPLOAD_FOLDER, subpath)

# ----------------- AVTORIZATSIYA & DEKORATORLAR -----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login", next=request.url))
            user_role = session.get("role")
            if user_role not in allowed_roles:
                flash(f"Kechirasiz, sizning rolingiz ({user_role}) ushbu bo'limga kirishga ruxsat bermaydi!", "danger")
                if user_role == "sotuvchi":
                    return redirect(url_for("sotuv"))
                elif user_role == "omborchi":
                    return redirect(url_for("ombor_list"))
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_user():
    user_info = None
    pending_count = 0
    if "user_id" in session:
        user_info = {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name"),
            "role": session.get("role")
        }
        try:
            conn = database.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'tolandi'")
            row = cursor.fetchone()
            if row:
                pending_count = row["cnt"]
            conn.close()
        except Exception:
            pass
    return {"current_user": user_info, "pending_nakladnoy_count": pending_count}

# ----------------- KIBERXAVFSIZLIK: BRUTE-FORCE VA BUZIB KIRISHDAN HIMOYA -----------------
LOGIN_ATTEMPTS = defaultdict(list)
USER_ATTEMPTS = defaultdict(list)
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 daqiqa bloklash

def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

def is_ip_locked(client_ip):
    now = time.time()
    attempts = [t for t in LOGIN_ATTEMPTS[client_ip] if now - t < LOCKOUT_DURATION_SECONDS]
    LOGIN_ATTEMPTS[client_ip] = attempts
    return len(attempts) >= MAX_FAILED_ATTEMPTS

def is_user_locked(username):
    if not username:
        return False
    now = time.time()
    attempts = [t for t in USER_ATTEMPTS[username] if now - t < LOCKOUT_DURATION_SECONDS]
    USER_ATTEMPTS[username] = attempts
    return len(attempts) >= MAX_FAILED_ATTEMPTS

def record_failed_login(client_ip, username):
    now = time.time()
    LOGIN_ATTEMPTS[client_ip].append(now)
    if username:
        USER_ATTEMPTS[username].append(now)

def reset_failed_login(client_ip, username):
    LOGIN_ATTEMPTS.pop(client_ip, None)
    if username:
        USER_ATTEMPTS.pop(username, None)

def reset_all_rate_limits():
    """Testlar va favqulodda tozalash uchun yordamchi funksiya"""
    LOGIN_ATTEMPTS.clear()
    USER_ATTEMPTS.clear()

def is_safe_redirect_url(target):
    if not target:
        return False
    if target.startswith("//") or target.startswith("\\\\"):
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if "user_id" in session:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

def record_system_action(action_type, target_type, title, description=None, target_id=None):
    """Joriy foydalanuvchi va uning rolidan kelib chiqib qisqa audit log yozadi"""
    try:
        user_name = session.get("full_name") or session.get("username") or "Tizim"
        user_role = session.get("role") or "tizim"
        user_id = session.get("user_id")
        ip = get_client_ip()
        database.log_action(
            user_name=user_name,
            user_role=user_role,
            action_type=action_type,
            target_type=target_type,
            title=title,
            description=description,
            target_id=target_id,
            user_id=user_id,
            ip_address=ip
        )
    except Exception as e:
        print(f"record_system_action xatosi: {e}")

# ----------------- LOGIN / LOGOUT -----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        role = session.get("role")
        if role == "sotuvchi":
            return redirect(url_for("sotuv"))
        elif role == "omborchi":
            return redirect(url_for("ombor_list"))
        return redirect(url_for("dashboard"))

    show_demo = os.environ.get("SHOW_DEMO_CREDENTIALS", "").lower() in ("1", "true") or app.debug

    if request.method == "POST":
        client_ip = get_client_ip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()

        # Brute Force Tekshiruvi
        if is_ip_locked(client_ip) or is_user_locked(username):
            flash("Kiberxavfsizlik himoyasi: 5 marta ketma-ket noto'g'ri urinish tufayli tizim 15 daqiqaga vaqtincha bloklandi!", "danger")
            return render_template("login.html", is_locked=True, show_demo_credentials=show_demo), 429

        user = database.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            reset_failed_login(client_ip, username)
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]

            flash(f"Xush kelibsiz, {user['full_name']}!", "success")
            
            # Xavfsiz Yo'naltirish (Open Redirect Prevention)
            next_url = request.args.get("next")
            if next_url and is_safe_redirect_url(next_url):
                return redirect(next_url)
            
            if user["role"] == "sotuvchi":
                return redirect(url_for("sotuv"))
            elif user["role"] == "omborchi":
                return redirect(url_for("ombor_list"))
            return redirect(url_for("dashboard"))
        else:
            record_failed_login(client_ip, username)
            attempts_left = max(0, MAX_FAILED_ATTEMPTS - len(LOGIN_ATTEMPTS[client_ip]))
            if attempts_left > 0:
                flash(f"Login yoki parol noto'g'ri kiritildi! (Xavfsizlik: {attempts_left} ta urinish qoldi)", "danger")
            else:
                flash("Kiberxavfsizlik: 5 marta xato urinish tufayli hisob 15 daqiqaga bloklandi!", "danger")

    return render_template("login.html", show_demo_credentials=show_demo)

@app.route("/logout")
def logout():
    session.clear()
    flash("Tizimdan muvaffaqiyatli chiqdingiz.", "info")
    return redirect(url_for("login"))

# ----------------- XODIMLAR BOSHQARUVI (SUPER ADMIN) -----------------

@app.route("/admin/xodimlar", methods=["GET", "POST"])
@role_required(["admin"])
def admin_xodimlar():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "sotuvchi").strip()

        if not full_name or not username or not password:
            flash("Iltimos, barcha maydonlarni to'ldiring!", "danger")
        else:
            success, msg = database.create_user(username, password, full_name, role)
            if success:
                record_system_action('kiritdi', 'xodim', f"Yangi xodim qo'shildi: {full_name}", f"Login: {username}, Rol: {role}")
                flash(msg, "success")
            else:
                flash(msg, "danger")
        return redirect(url_for("admin_xodimlar"))

    users = database.get_all_users()
    return render_template("xodimlar.html", users=users)

@app.route("/admin/ustalar", methods=["GET"])
@role_required(["admin"])
def admin_ustalar():
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.full_name, c.phone, c.customer_type, c.notes, c.created_at,
               COUNT(DISTINCT o.customer_id) as clients_count,
               COUNT(DISTINCT o.id) as orders_count,
               COALESCE(SUM(o.total_amount), 0.0) as total_sales
        FROM customers c
        LEFT JOIN orders o ON o.usta_id = c.id
        WHERE c.customer_type IN ('usta', 'prorab')
        GROUP BY c.id
        ORDER BY c.id DESC
    """)
    ustalar = [dict(r) for r in cursor.fetchall()]
    total_ustalar = len(ustalar)
    total_clients_referred = sum(u["clients_count"] for u in ustalar)
    total_sales_generated = sum(u["total_sales"] for u in ustalar)
    conn.close()
    return render_template("ustalar.html",
                           ustalar=ustalar,
                           total_ustalar=total_ustalar,
                           total_clients_referred=total_clients_referred,
                           total_sales_generated=total_sales_generated)

@app.route("/admin/ustalar/qoshish", methods=["POST"])
@role_required(["admin"])
def admin_add_usta():
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    customer_type = request.form.get("customer_type", "usta").strip()
    notes = request.form.get("notes", "").strip()

    if not full_name:
        flash("Usta ismini kiritish majburiy!", "danger")
    else:
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (full_name, phone, customer_type, balance_debt, notes)
            VALUES (?, ?, ?, 0.0, ?)
        """, (full_name, phone, customer_type, notes or "Ustalar bo'limidan kiritilgan"))
        new_usta_id = cursor.lastrowid
        conn.commit()
        conn.close()
        record_system_action('kiritdi', 'usta', f"Yangi usta qo'shildi: {full_name}", f"Tel: {phone or 'Mavjud emas'}, Turi: {customer_type}", target_id=new_usta_id)
        flash(f"Usta '{full_name}' muvaffaqiyatli qo'shildi!", "success")
    return redirect(url_for("admin_ustalar"))

@app.route("/admin/ustalar/ochirish/<int:usta_id>", methods=["POST"])
@role_required(["admin"])
def admin_delete_usta(usta_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE usta_id = ?", (usta_id,))
    orders_cnt = cursor.fetchone()[0]
    if orders_cnt > 0:
        cursor.execute("UPDATE customers SET customer_type = 'oddiy', notes = notes || ' (Ustalikdan chiqarilgan)' WHERE id = ?", (usta_id,))
        flash("Usta avvalgi savdolarda qatnashgani sababli arxivlandi.", "info")
        action_msg = "Usta savdolarda qatnashgani sababli arxivlandi"
        action_title = f"Usta arxivlandi: ID #{usta_id}"
    else:
        cursor.execute("DELETE FROM customers WHERE id = ? AND customer_type IN ('usta', 'prorab')", (usta_id,))
        flash("Usta tizimdan o'chirildi.", "info")
        action_msg = "Usta bazadan to'liq o'chirildi"
        action_title = f"Usta o'chirildi: ID #{usta_id}"
    conn.commit()
    conn.close()
    record_system_action('ochirdi', 'usta', action_title, action_msg, target_id=usta_id)
    return redirect(url_for("admin_ustalar"))

@app.route("/admin/xodimlar/parol/<int:user_id>", methods=["POST"])
@role_required(["admin"])
def admin_change_password(user_id):
    new_password = request.form.get("new_password", "").strip()
    if new_password and len(new_password) >= 4:
        database.update_user_password(user_id, new_password)
        record_system_action('tahrirladi', 'xodim', f"Xodim paroli yangilandi: ID #{user_id}", "Admin tomonidan yangi parol o'rnatildi", target_id=user_id)
        flash("Xodim paroli muvaffaqiyatli o'zgartirildi!", "success")
    else:
        flash("Parol kamida 4 belgidan iborat bo'lishi kerak!", "danger")
    return redirect(url_for("admin_xodimlar"))

@app.route("/admin/xodimlar/ochirish/<int:user_id>", methods=["POST"])
@role_required(["admin"])
def admin_delete_user(user_id):
    database.delete_user(user_id)
    record_system_action('ochirdi', 'xodim', f"Xodim o'chirildi: ID #{user_id}", "Xodim akkaunti tizimdan o'chirildi", target_id=user_id)
    flash("Xodim tizimdan o'chirildi.", "info")
    return redirect(url_for("admin_xodimlar"))

# ----------------- ASOSIY SAHIFALAR -----------------

@app.route("/")
@role_required(["admin"])
def dashboard():
    conn = database.get_db()
    cursor = conn.cursor()
    
    # Statistik ma'lumotlar
    cursor.execute("SELECT COUNT(*) as total_types, COALESCE(SUM(quantity_in_stock), 0) as total_stock FROM products")
    prod_stats = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as low_stock_count FROM products WHERE quantity_in_stock <= min_quantity")
    low_stock = cursor.fetchone()["low_stock_count"]
    
    # Bugungi savdolar
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT COUNT(*) as orders_count, COALESCE(SUM(total_amount), 0) as total_sales
        FROM orders 
        WHERE DATE(created_at) = ? AND status != 'bekor_qilindi'
    """, (today,))
    today_stats = cursor.fetchone()
    
    # Yangi (kutayotgan) nakladnoylar soni
    cursor.execute("SELECT COUNT(*) as pending_nakladnoy FROM orders WHERE status = 'tolandi'")
    pending_nakladnoy = cursor.fetchone()["pending_nakladnoy"]
    
    # So'nggi 5 ta buyurtma
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5")
    recent_orders = cursor.fetchall()
    
    # Kam qolgan kafellar
    cursor.execute("SELECT * FROM products WHERE quantity_in_stock <= min_quantity ORDER BY quantity_in_stock ASC LIMIT 5")
    low_stock_items = cursor.fetchall()
    
    # Oxirgi 7 kunlik savdo dinamikasi
    sales_chart_labels = []
    sales_chart_data = []
    base_date = datetime.now()
    for i in range(6, -1, -1):
        day_date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
        day_label = (base_date - timedelta(days=i)).strftime("%d.%m")
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as daily_sum
            FROM orders
            WHERE DATE(created_at) = ? AND status != 'bekor_qilindi'
        """, (day_date,))
        row = cursor.fetchone()
        sales_chart_labels.append(day_label)
        sales_chart_data.append(float(row["daily_sum"] if row else 0))

    # To'lov usullari statistikasi
    cursor.execute("""
        SELECT payment_method, COALESCE(SUM(total_amount), 0) as total
        FROM orders
        WHERE status != 'bekor_qilindi'
        GROUP BY payment_method
    """)
    pm_rows = cursor.fetchall()
    payment_stats = {"naqd": 0.0, "karta": 0.0, "boshqa": 0.0}
    for pm in pm_rows:
        m = (pm["payment_method"] or "naqd").lower()
        if m in payment_stats:
            payment_stats[m] += float(pm["total"])
        else:
            payment_stats["boshqa"] += float(pm["total"])

    # Eng ko'p sotilgan kafellar (Top 5)
    cursor.execute("""
        SELECT oi.brand, oi.model_name, oi.size, SUM(oi.quantity) as total_qty, SUM(oi.total_price) as total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != 'bekor_qilindi'
        GROUP BY oi.product_id, oi.brand, oi.model_name, oi.size
        ORDER BY total_qty DESC
        LIMIT 5
    """)
    top_products = cursor.fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        prod_stats=prod_stats,
        low_stock=low_stock,
        today_stats=today_stats,
        pending_nakladnoy=pending_nakladnoy,
        recent_orders=recent_orders,
        low_stock_items=low_stock_items,
        sales_chart_labels=sales_chart_labels,
        sales_chart_data=sales_chart_data,
        payment_stats=payment_stats,
        top_products=top_products
    )

# --- OMBOR (INVENTORY) ---
@app.route("/ombor")
@role_required(["admin", "omborchi"])
def ombor_list():
    q = request.args.get("q", "").strip()
    brand_filter = request.args.get("brand", "").strip()
    stock_status = request.args.get("status", "").strip()
    
    conn = database.get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if q:
        query += " AND (brand LIKE ? OR model_name LIKE ? OR sku LIKE ? OR size LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern, pattern])
        
    if brand_filter:
        query += " AND brand = ?"
        params.append(brand_filter)
        
    if stock_status == "low":
        query += " AND quantity_in_stock <= min_quantity AND quantity_in_stock > 0"
    elif stock_status == "out":
        query += " AND quantity_in_stock <= 0"
        
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    products = cursor.fetchall()
    
    # Markalar ro'yxati (filtr uchun)
    cursor.execute("SELECT DISTINCT brand FROM products ORDER BY brand ASC")
    brands = [row["brand"] for row in cursor.fetchall()]
    
    conn.close()
    return render_template("ombor.html", products=products, brands=brands, q=q, brand_filter=brand_filter, stock_status=stock_status)

@app.route("/ombor/yangi", methods=["GET", "POST"])
@role_required(["admin", "omborchi"])
def ombor_yangi():
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model_name = request.form.get("model_name", "").strip()
        size = request.form.get("size", "").strip()
        unit = request.form.get("unit", "m²").strip()
        box_size_m2 = float(request.form.get("box_size_m2", 1.44) or 1.44)
        pieces_per_box = int(request.form.get("pieces_per_box", 4) or 4)
        quantity = float(request.form.get("quantity_in_stock", 0) or 0)
        min_quantity = float(request.form.get("min_quantity", 10) or 10)
        price = float(request.form.get("price", 0) or 0)
        cost_price = float(request.form.get("cost_price", 0) or 0)
        location_rack = request.form.get("location_rack", "").strip()
        description = request.form.get("description", "").strip()
        
        if not brand or not model_name or not size or price <= 0:
            flash("Iltimos, barcha asosiy maydonlarni (Marka, Nomi, O'lchami, Narxi) to'ldiring!", "danger")
            return redirect(url_for("ombor_yangi"))
            
        sku = database.generate_product_sku(brand, model_name)
        
        # Rasm yuklash
        image_path = None
        if "image" in request.files:
            file = request.files["image"]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{sku}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                filepath = os.path.join(PRODUCT_UPLOADS, filename)
                file.save(filepath)
                try:
                    with Image.open(filepath) as img:
                        img.thumbnail((1200, 1200))
                        img.save(filepath, quality=88, optimize=True)
                except Exception as e:
                    print("Rasm siqishda xatolik:", e)
                image_path = f"/uploads/products/{filename}"
                
        # QR kod yaratish
        qr_code_path = generate_qr_image(sku)
        
        worker_name = session.get("full_name") or session.get("username") or "Omborchi"
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (
                sku, brand, model_name, size, unit, box_size_m2, pieces_per_box,
                quantity_in_stock, min_quantity, price, cost_price, image_path, qr_code_path,
                location_rack, description, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sku, brand, model_name, size, unit, box_size_m2, pieces_per_box,
              quantity, min_quantity, price, cost_price, image_path, qr_code_path,
              location_rack, description, worker_name))
        
        new_prod_id = cursor.lastrowid
        
        # Kirim tarixini yozish
        if quantity > 0:
            cursor.execute("""
                INSERT INTO stock_history (product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, user_name, note)
                VALUES (?, 'kirim', ?, 0, ?, 'BOSHLANGICH', ?, 'Omborga birinchi marta kiritildi')
            """, (new_prod_id, quantity, quantity, worker_name))

        # Agar kiritilgan marka zavodlar ro'yxatida bo'lmasa, avtomatik qo'shish
        cursor.execute("SELECT id FROM factories WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))", (brand,))
        if not cursor.fetchone():
            try:
                cursor.execute("INSERT INTO factories (name, country) VALUES (?, ?)", (brand, "O'zbekiston"))
            except Exception:
                pass
            
        conn.commit()
        conn.close()
        
        record_system_action('kiritdi', 'kafel', f"Yangi kafel qo'shildi: {brand} {model_name}", f"SKU: {sku}, Miqdor: {quantity} {unit}, Narx: {price:,.0f} so'm", target_id=new_prod_id)
        flash(f"'{brand} - {model_name}' muvaffaqiyatli kiritildi! QR kod generatsiya qilindi.", "success")
        return redirect(url_for("ombor_qr_stiker", product_id=new_prod_id))
        
    factories = database.get_active_factories()
    return render_template("yangi_kafel.html", factories=factories)

@app.route("/ombor/tahrirlash/<int:product_id>", methods=["GET", "POST"])
@role_required(["admin", "omborchi"])
def ombor_tahrirlash(product_id):
    conn = database.get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        flash("Kafel topilmadi!", "danger")
        return redirect(url_for("ombor_list"))
        
    if request.method == "POST":
        brand = request.form.get("brand", "").strip()
        model_name = request.form.get("model_name", "").strip()
        size = request.form.get("size", "").strip()
        unit = request.form.get("unit", "m²").strip()
        box_size_m2 = float(request.form.get("box_size_m2", product["box_size_m2"]) or 1.44)
        pieces_per_box = int(request.form.get("pieces_per_box", product["pieces_per_box"]) or 4)
        min_quantity = float(request.form.get("min_quantity", product["min_quantity"]) or 10)
        price = float(request.form.get("price", product["price"]) or 0)
        cost_price = float(request.form.get("cost_price", product["cost_price"]) or 0)
        location_rack = request.form.get("location_rack", "").strip()
        description = request.form.get("description", "").strip()
        
        # Yangi kirim qo'shish (agar bo'lsa)
        add_stock = float(request.form.get("add_stock", 0) or 0)
        current_stock = product["quantity_in_stock"]
        new_stock = current_stock + add_stock
        
        image_path = product["image_path"]
        if "image" in request.files:
            file = request.files["image"]
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{product['sku']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                filepath = os.path.join(PRODUCT_UPLOADS, filename)
                file.save(filepath)
                try:
                    with Image.open(filepath) as img:
                        img.thumbnail((1200, 1200))
                        img.save(filepath, quality=88, optimize=True)
                except Exception as e:
                    print("Xato:", e)
                image_path = f"/uploads/products/{filename}"
                
        cursor.execute("""
            UPDATE products SET
                brand = ?, model_name = ?, size = ?, unit = ?, box_size_m2 = ?,
                pieces_per_box = ?, quantity_in_stock = ?, min_quantity = ?, price = ?,
                cost_price = ?, image_path = ?, location_rack = ?, description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (brand, model_name, size, unit, box_size_m2, pieces_per_box,
              new_stock, min_quantity, price, cost_price, image_path,
              location_rack, description, product_id))
        
        if add_stock > 0:
            worker_name = session.get("full_name") or session.get("username") or "Omborchi"
            cursor.execute("""
                INSERT INTO stock_history (product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, user_name, note)
                VALUES (?, 'kirim', ?, ?, ?, 'KIRIM_QOSHILDI', ?, ?)
            """, (product_id, add_stock, current_stock, new_stock, worker_name, "Omborga qo'shimcha yuk qabul qilindi"))
            
        conn.commit()
        conn.close()

        if add_stock > 0:
            record_system_action('kiritdi', 'kirim', f"Omborga yuk qabul qilindi: {brand} {model_name}", f"+{add_stock} {unit} qo'shildi. Yangi qoldiq: {new_stock} {unit}", target_id=product_id)
        record_system_action('tahrirladi', 'kafel', f"Kafel tahrirlandi: {brand} {model_name}", f"Narx: {price:,.0f} so'm, Zaxira: {new_stock} {unit}", target_id=product_id)

        flash("Kafel ma'lumotlari yangilandi!", "success")
        return redirect(url_for("ombor_list"))
        
    conn.close()
    factories = database.get_active_factories()
    return render_template("tahrirlash_kafel.html", product=product, factories=factories)

@app.route("/ombor/qr/<int:product_id>")
@role_required(["admin", "omborchi"])
def ombor_qr_stiker(product_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    if not product:
        flash("Mahsulot topilmadi!", "danger")
        return redirect(url_for("ombor_list"))
        
    count = int(request.args.get("count", 4))
    return render_template("qr_stiker.html", product=product, count=count)

# ================= ZAVODLAR & MARKALAR BOSHQARUVI =================
@app.route("/zavodlar")
@role_required(["admin", "omborchi"])
def zavodlar_page():
    q = request.args.get("q", "").strip()
    factories = database.get_all_factories(q)

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM factories")
    total_factories = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM factories WHERE is_active = 1")
    active_factories = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT country) FROM factories WHERE country IS NOT NULL AND country != ''")
    total_countries = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT id) FROM products")
    total_products_linked = cursor.fetchone()[0]
    conn.close()

    kpi = {
        "total_factories": total_factories,
        "active_factories": active_factories,
        "total_countries": total_countries,
        "total_products_linked": total_products_linked
    }
    return render_template("zavodlar.html", factories=factories, kpi=kpi, q=q)

@app.route("/api/factories/add", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_factories_add():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    country = data.get("country", "O'zbekiston").strip()
    contact_person = data.get("contact_person", "").strip()
    phone = data.get("phone", "").strip()
    address = data.get("address", "").strip()
    note = data.get("note", "").strip()

    if not name:
        return jsonify({"success": False, "message": "Zavod yoki marka nomini kiriting!"}), 400

    success, new_id, msg = database.create_factory(name, country, contact_person, phone, address, note)
    if not success:
        return jsonify({"success": False, "message": msg}), 400

    record_system_action('kiritdi', 'zavod', f"Yangi zavod/brend qo'shildi: {name}", f"Davlat: {country}, Tel: {phone or 'Mavjud emas'}", target_id=new_id)
    return jsonify({"success": True, "id": new_id, "message": msg})

@app.route("/api/factories/<int:factory_id>/edit", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_factories_edit(factory_id):
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    country = data.get("country", "O'zbekiston").strip()
    contact_person = data.get("contact_person", "").strip()
    phone = data.get("phone", "").strip()
    address = data.get("address", "").strip()
    note = data.get("note", "").strip()
    is_active = int(data.get("is_active", 1) or 1)

    if not name:
        return jsonify({"success": False, "message": "Zavod yoki marka nomini kiriting!"}), 400

    success, msg = database.update_factory(factory_id, name, country, contact_person, phone, address, note, is_active)
    if not success:
        return jsonify({"success": False, "message": msg}), 400

    record_system_action('tahrirladi', 'zavod', f"Zavod ma'lumotlari tahrirlandi: {name}", f"Davlat: {country}, Holati: {'Faol' if is_active else 'Nofaol'}", target_id=factory_id)
    return jsonify({"success": True, "message": msg})

@app.route("/api/factories/<int:factory_id>/delete", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_factories_delete(factory_id):
    success, msg = database.delete_factory(factory_id)
    if success:
        record_system_action('ochirdi', 'zavod', f"Zavod/brend o'chirildi: ID #{factory_id}", "Zavod yoki marka ro'yxatdan o'chirildi", target_id=factory_id)
    return jsonify({"success": success, "message": msg})

@app.route("/api/factories/list", methods=["GET"])
@login_required
def api_factories_list():
    factories = database.get_active_factories()
    result = [{"id": f["id"], "name": f["name"], "country": f["country"]} for f in factories]
    return jsonify({"success": True, "factories": result})

# --- SOTUV & QR SKANER (SALES SHOWROOM) ---
@app.route("/sotuv")
@role_required(["admin", "sotuvchi"])
def sotuv():
    return render_template("sotuv.html")

# --- KASSA (CASHIER & CHECKOUT) ---
@app.route("/kassa")
@role_required(["admin", "sotuvchi"])
def kassa():
    return render_template("kassa.html")

# --- NAKLADNOYLAR (WAREHOUSE DISPATCH) ---
@app.route("/nakladnoylar")
@role_required(["admin", "omborchi"])
def nakladnoy_list():
    status_filter = request.args.get("status", "").strip()
    conn = database.get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
        
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    orders = cursor.fetchall()
    
    # Har bir buyurtma uchun mahsulotlar soni va ro'yxatini yuklash
    order_data = []
    for ord in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (ord["id"],))
        items = cursor.fetchall()
        order_data.append({
            "order": ord,
            "items": items,
            "item_count": len(items)
        })
        
    conn.close()
    return render_template("nakladnoy_list.html", order_data=order_data, status_filter=status_filter)

@app.route("/nakladnoy/<int:order_id>")
@role_required(["admin", "omborchi"])
def nakladnoy_detail(order_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        flash("Nakladnoy topilmadi!", "danger")
        return redirect(url_for("nakladnoy_list"))
        
    cursor.execute("""
        SELECT oi.*, p.location_rack, p.quantity_in_stock, p.sku
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    """, (order_id,))
    items = cursor.fetchall()
    
    usta = None
    if order["usta_id"]:
        cursor.execute("SELECT * FROM customers WHERE id = ?", (order["usta_id"],))
        usta = cursor.fetchone()

    conn.close()
    
    return render_template("nakladnoy_detail.html", order=order, items=items, usta=usta)

@app.route("/nakladnoy/<int:order_id>/print")
@login_required
def nakladnoy_print(order_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return "Nakladnoy topilmadi", 404
        
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()
    
    usta = None
    if order["usta_id"]:
        cursor.execute("SELECT * FROM customers WHERE id = ?", (order["usta_id"],))
        usta = cursor.fetchone()

    conn.close()
    return render_template("nakladnoy_print.html", order=order, items=items, usta=usta)

@app.route("/nakladnoy/<int:order_id>/chek")
@login_required
def nakladnoy_chek(order_id):
    """80mm / 58mm termal kassa printerlari uchun ixcham kassa cheki"""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return "Nakladnoy topilmadi", 404
        
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = cursor.fetchall()
    
    usta = None
    if order["usta_id"]:
        cursor.execute("SELECT * FROM customers WHERE id = ?", (order["usta_id"],))
        usta = cursor.fetchone()

    conn.close()
    return render_template("chek_print.html", order=order, items=items, usta=usta)


# ----------------- API ENDPOINTS -----------------

@app.route("/api/product/by-code/<code>")
@login_required
def api_product_by_code(code):
    """QR skaner orqali o'qilgan kod bo'yicha mahsulotni topish"""
    code = code.strip()
    conn = database.get_db()
    cursor = conn.cursor()
    
    # SKU yoki ID bo'yicha qidirish
    cursor.execute("SELECT * FROM products WHERE sku = ? OR id = ?", (code, code if code.isdigit() else -1))
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return jsonify({"success": False, "message": "Ushbu QR kodli kafel topilmadi!"}), 404
        
    return jsonify({
        "success": True,
        "product": dict(product)
    })

@app.route("/api/products/search")
@login_required
def api_products_search():
    """Showroom vitrinasi va tezkor kafel qidiruvi"""
    q = request.args.get("q", "").strip()
    brand = request.args.get("brand", "").strip()
    size = request.args.get("size", "").strip()
    limit = int(request.args.get("limit", 24))

    conn = database.get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if q:
        pattern = f"%{q}%"
        query += " AND (brand LIKE ? OR model_name LIKE ? OR sku LIKE ? OR size LIKE ?)"
        params.extend([pattern, pattern, pattern, pattern])

    if brand:
        query += " AND brand = ?"
        params.append(brand)

    if size:
        query += " AND size LIKE ?"
        params.append(f"%{size}%")

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    products = cursor.fetchall()
    conn.close()
    return jsonify({"success": True, "products": [dict(p) for p in products]})

@app.route("/api/checkout", methods=["POST"])
@role_required(["admin", "sotuvchi"])
def api_checkout():
    """Kassa to'lovini qabul qilish va ombordan avtomatik ayirish"""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Ma'lumotlar yuborilmadi"}), 400
        
    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "message": "Savat bo'sh!"}), 400
        
    customer_name = data.get("customer_name", "Mijoz").strip()
    customer_phone = data.get("customer_phone", "").strip()
    payment_method = data.get("payment_method", "naqd") # naqd, karta, aralash
    cashier_note = data.get("cashier_note", "").strip()
    discount_amount = float(data.get("discount_amount", 0) or 0)
    
    conn = database.get_db()
    cursor = conn.cursor()
    
    try:
        # 1. Ombordagi qoldiqni tekshirish
        for item in items:
            qty = float(item["qty"])
            if item.get("is_defect") or item.get("defect_id"):
                def_id = int(item.get("defect_id") or item.get("id"))
                cursor.execute("""
                    SELECT bt.*, p.brand, p.model_name
                    FROM broken_tiles bt
                    JOIN products p ON bt.product_id = p.id
                    WHERE bt.id = ?
                """, (def_id,))
                d_row = cursor.fetchone()
                if not d_row:
                    conn.rollback()
                    conn.close()
                    return jsonify({"success": False, "message": f"Siniq kafel (ID {def_id}) topilmadi!"}), 400
                if d_row["status"] != 'omborda' or float(d_row["quantity"]) < qty:
                    conn.rollback()
                    conn.close()
                    return jsonify({
                        "success": False,
                        "message": f"'{d_row['brand']} {d_row['model_name']}' siniq kafeli omborda yetarli emas! Omborda: {d_row['quantity']} {d_row['unit']}, so'raldi: {qty}"
                    }), 400
            else:
                p_id = item["id"]
                cursor.execute("SELECT id, brand, model_name, quantity_in_stock FROM products WHERE id = ?", (p_id,))
                p = cursor.fetchone()
                if not p:
                    conn.rollback()
                    conn.close()
                    return jsonify({"success": False, "message": f"Mahsulot (ID {p_id}) topilmadi!"}), 400
                if p["quantity_in_stock"] < qty:
                    conn.rollback()
                    conn.close()
                    return jsonify({
                        "success": False, 
                        "message": f"'{p['brand']} {p['model_name']}' kafeli omborda yetarli emas! Omborda: {p['quantity_in_stock']} mavjud, so'raldi: {qty}"
                    }), 400
                
        # 2. Buyurtma yaratish
        subtotal = sum(float(i["qty"]) * float(i["price"]) for i in items)
        final_amount = max(0.0, subtotal - discount_amount)
        order_num = database.generate_order_number()
        
        full_note = cashier_note
        if discount_amount > 0:
            full_note = f"[Chegirma: {discount_amount:,.0f} so'm] {cashier_note}".strip()

        seller_name = session.get("full_name") or session.get("username") or "Sotuvchi"
        seller_id = session.get("user_id")

        is_nasiya = 1 if (data.get("is_nasiya") or payment_method == "nasiya") else 0
        raw_cust_id = data.get("customer_id")
        customer_id = int(raw_cust_id) if raw_cust_id else None

        if is_nasiya:
            raw_paid = data.get("paid_amount")
            try:
                paid_amount = float(raw_paid) if raw_paid is not None and str(raw_paid).strip() != "" else 0.0
            except (ValueError, TypeError):
                paid_amount = 0.0
            paid_amount = max(0.0, min(paid_amount, final_amount))
            debt_amount = max(0.0, final_amount - paid_amount)
        else:
            paid_amount = final_amount
            debt_amount = 0.0

        if is_nasiya and debt_amount > 0:
            if customer_id:
                cursor.execute("UPDATE customers SET balance_debt = balance_debt + ? WHERE id = ?", (debt_amount, customer_id))
            else:
                cust_full_name = customer_name.strip() if (customer_name and customer_name.strip() and customer_name.strip().lower() != "mijoz") else f"Nasiya Xaridor (#{order_num})"
                cursor.execute("""
                    INSERT INTO customers (full_name, phone, customer_type, balance_debt, notes)
                    VALUES (?, ?, 'xaridor', ?, ?)
                """, (cust_full_name, customer_phone, debt_amount, f"Kassa orqali #{order_num} nakladnoy bo'yicha nasiya"))
                customer_id = cursor.lastrowid

        raw_usta_id = data.get("usta_id")
        usta_id = int(raw_usta_id) if raw_usta_id and str(raw_usta_id).isdigit() else None

        cursor.execute("""
            INSERT INTO orders (
                order_number, customer_name, customer_phone, total_amount, paid_amount,
                payment_method, status, cashier_note, seller_name, seller_id, is_nasiya, debt_amount, customer_id, usta_id
            ) VALUES (?, ?, ?, ?, ?, ?, 'tolandi', ?, ?, ?, ?, ?, ?, ?)
        """, (order_num, customer_name, customer_phone, final_amount, paid_amount, payment_method, full_note, seller_name, seller_id, is_nasiya, debt_amount, customer_id, usta_id))
        
        order_id = cursor.lastrowid

        if customer_id and usta_id:
            try:
                cursor.execute("UPDATE customers SET referred_by_usta_id = ? WHERE id = ? AND (referred_by_usta_id IS NULL OR referred_by_usta_id = 0)", (usta_id, customer_id))
            except Exception:
                pass
        
        # 3. Buyurtma elementlarini kiritish va ombordan ayirish
        for item in items:
            qty = float(item["qty"])
            unit_price = float(item["price"])
            item_total = qty * unit_price
            
            if item.get("is_defect") or item.get("defect_id"):
                def_id = int(item.get("defect_id") or item.get("id"))
                cursor.execute("""
                    SELECT bt.*, p.brand, p.model_name, p.size, p.image_path, p.unit
                    FROM broken_tiles bt
                    JOIN products p ON bt.product_id = p.id
                    WHERE bt.id = ?
                """, (def_id,))
                d_row = cursor.fetchone()
                p_id = d_row["product_id"]

                defect_model_name = d_row["model_name"]
                if "[Siniq/Brak]" not in defect_model_name:
                    defect_model_name = f"{defect_model_name} [Siniq/Brak]"

                cursor.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, brand, model_name, size, unit, quantity,
                        unit_price, total_price, image_path, is_defect, defect_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (order_id, p_id, d_row["brand"], defect_model_name,
                      d_row["size"], d_row["unit"], qty, unit_price, item_total, d_row["image_path"], def_id))

                # Siniqlar jadvalini yangilash
                cur_def_qty = float(d_row["quantity"])
                new_def_qty = max(0.0, cur_def_qty - qty)
                new_def_status = 'arzonlashtirib_sotildi' if new_def_qty <= 0 else 'omborda'
                new_sold_price = float(d_row["sold_price"] or 0) + item_total
                new_loss = max(0.0, float(d_row["loss_amount"] or 0) - item_total)

                cursor.execute("""
                    UPDATE broken_tiles
                    SET quantity = ?, status = ?, sold_price = ?, loss_amount = ?, order_id = ?
                    WHERE id = ?
                """, (new_def_qty, new_def_status, new_sold_price, new_loss, order_id, def_id))

                # Tarixga yozish (asosiy ombor qoldig'i qayta kamaytirilmaydi, chunki sindirilganda 200->199 ayirilgan)
                cursor.execute("""
                    INSERT INTO stock_history (
                        product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, user_name, note
                    ) VALUES (?, 'sotuv_brak', ?, ?, ?, ?, ?, ?)
                """, (p_id, -qty, cur_def_qty, new_def_qty, order_num, seller_name,
                      f"Siniq/Brak sotuv #{order_num} ({qty} {d_row['unit']}, {item_total:,.0f} so'm, Sotuvchi: {seller_name})"))
            else:
                p_id = item["id"]
                cursor.execute("SELECT * FROM products WHERE id = ?", (p_id,))
                prod = cursor.fetchone()
                
                cursor.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, brand, model_name, size, unit, quantity,
                        unit_price, total_price, image_path, is_defect
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (order_id, p_id, prod["brand"], prod["model_name"], prod["size"], prod["unit"],
                      qty, unit_price, item_total, prod["image_path"]))
                
                # Asosiy ombordan ayirish
                prev_q = prod["quantity_in_stock"]
                new_q = prev_q - qty
                cursor.execute("""
                    UPDATE products SET quantity_in_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (new_q, p_id))
                
                # Tarixga yozish
                cursor.execute("""
                    INSERT INTO stock_history (
                        product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, user_name, note
                    ) VALUES (?, 'sotuv', ?, ?, ?, ?, ?, ?)
                """, (p_id, -qty, prev_q, new_q, order_num, seller_name, f"Sotuv #{order_num} ({payment_method.capitalize()}, Sotuvchi: {seller_name})"))
            
        conn.commit()
        conn.close()

        record_system_action(
            action_type='sotdi',
            target_type='savdo',
            title=f"Kassa savdosi: #{order_num}",
            description=f"Mijoz: {customer_name}, Jami: {final_amount:,.0f} so'm ({len(items)} xil mahsulot)",
            target_id=order_id
        )
        
        return jsonify({
            "success": True,
            "order_id": order_id,
            "order_number": order_num,
            "message": "To'lov muvaffaqiyatli qabul qilindi! Ombordan ayrildi va Nakladnoy yaratildi."
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": f"Server xatoligi: {str(e)}"}), 500

@app.route("/api/order/<int:order_id>/dispatch", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_order_dispatch(order_id):
    """Omborchi tomonidan 'Yuk berildi' deb tasdiqlash"""
    data = request.get_json() or {}
    warehouse_note = data.get("note", "").strip()
    omborchi_name = session.get("full_name") or session.get("username") or "Omborchi"
    
    note_to_save = warehouse_note if warehouse_note else "Yuk to'liq topshirildi"
    
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT order_number FROM orders WHERE id = ?", (order_id,))
    o_row = cursor.fetchone()
    order_num_str = o_row["order_number"] if o_row else f"ID {order_id}"

    cursor.execute("""
        UPDATE orders SET
            status = 'yuk_berildi',
            warehouse_note = ?,
            dispatched_by = ?,
            dispatched_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (note_to_save, omborchi_name, order_id))
    
    conn.commit()
    conn.close()

    record_system_action(
        action_type='topshirdi',
        target_type='savdo',
        title=f"Yuk topshirildi: #{order_num_str}",
        description=f"Ombordan xaridorga chiqarildi. Izoh: {note_to_save}",
        target_id=order_id
    )
    return jsonify({"success": True, "message": "Yuk muvaffaqiyatli xaridorga berildi deb belgilandi!"})

# ----------------- MIJOZLAR & NASIYA DAFTARI (CRM & DEBTORS) -----------------

@app.route("/mijozlar", methods=["GET", "POST"])
@role_required(["admin"])
def mijozlar():
    conn = database.get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        customer_type = request.form.get("customer_type", "xaridor")
        balance_debt = float(request.form.get("balance_debt", 0) or 0)
        notes = request.form.get("notes", "").strip()

        if not full_name:
            flash("Iltimos, mijoz ismini kiriting!", "danger")
        else:
            cursor.execute("""
                INSERT INTO customers (full_name, phone, customer_type, balance_debt, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (full_name, phone, customer_type, balance_debt, notes))
            conn.commit()
            flash(f"Mijoz '{full_name}' muvaffaqiyatli saqlandi!", "success")
        conn.close()
        return redirect(url_for("mijozlar"))

    # Filters
    q = request.args.get("q", "").strip()
    c_type = request.args.get("type", "").strip()
    debt_only = request.args.get("debt_only", "").strip()

    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if q:
        query += " AND (full_name LIKE ? OR phone LIKE ? OR notes LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern])

    if c_type:
        query += " AND customer_type = ?"
        params.append(c_type)

    if debt_only == "1":
        query += " AND balance_debt > 0"

    # Oxirida ro'yxatga olingan mijoz har doim birinchi (boshida) chiqib tursin
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    customers = cursor.fetchall()

    # KPI stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_cnt, 
            COALESCE(SUM(balance_debt), 0) as total_debt, 
            COUNT(CASE WHEN balance_debt > 0 THEN 1 END) as debtors_cnt 
        FROM customers
    """)
    kpi = cursor.fetchone()

    # Recent debt payments history
    cursor.execute("""
        SELECT cp.*, c.full_name as customer_name
        FROM customer_payments cp
        JOIN customers c ON cp.customer_id = c.id
        ORDER BY cp.id DESC LIMIT 15
    """)
    recent_payments = cursor.fetchall()

    conn.close()
    return render_template(
        "mijozlar.html",
        customers=customers,
        kpi=kpi,
        recent_payments=recent_payments,
        q=q,
        c_type=c_type,
        debt_only=debt_only
    )

@app.route("/api/customer/<int:customer_id>/pay-debt", methods=["POST"])
@login_required
def api_customer_pay_debt(customer_id):
    data = request.get_json() or {}
    amount = float(data.get("amount", 0) or 0)
    method = data.get("payment_method", "naqd")
    note = data.get("note", "").strip()

    if amount <= 0:
        return jsonify({"success": False, "message": "To'lov summasi musbat bo'lishi kerak!"}), 400

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    if not customer:
        conn.close()
        return jsonify({"success": False, "message": "Mijoz topilmadi!"}), 404

    current_debt = float(customer["balance_debt"])
    new_debt = max(0.0, current_debt - amount)
    received_by = session.get("full_name") or session.get("username") or "Kassir"

    cursor.execute("""
        UPDATE customers SET balance_debt = ? WHERE id = ?
    """, (new_debt, customer_id))

    cursor.execute("""
        INSERT INTO customer_payments (customer_id, amount, payment_method, note, received_by)
        VALUES (?, ?, ?, ?, ?)
    """, (customer_id, amount, method, note if note else "Qarz to'lovi", received_by))

    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "new_debt": new_debt,
        "message": f"{amount:,.0f} so'm qarz to'lovi qabul qilindi. Qoldiq: {new_debt:,.0f} so'm"
    })

@app.route("/api/customers/search")
@login_required
def api_customers_search():
    q = request.args.get("q", "").strip()
    conn = database.get_db()
    cursor = conn.cursor()
    if q:
        pattern = f"%{q}%"
        cursor.execute("SELECT id, full_name, phone, customer_type, balance_debt FROM customers WHERE full_name LIKE ? OR phone LIKE ? ORDER BY id DESC LIMIT 15", (pattern, pattern))
    else:
        cursor.execute("SELECT id, full_name, phone, customer_type, balance_debt FROM customers ORDER BY id DESC LIMIT 15")
    rows = cursor.fetchall()
    conn.close()
    return jsonify({"success": True, "customers": [dict(r) for r in rows]})

# --- USTALAR VA PRORABLAR API ---

@app.route("/api/ustalar")
@login_required
def api_ustalar():
    q = request.args.get("q", "").strip()
    rows = database.get_active_ustalar(q=q)
    return jsonify({"success": True, "ustalar": [dict(r) for r in rows]})

@app.route("/api/ustalar/quick-add", methods=["POST"])
@role_required(["admin", "sotuvchi"])
def api_ustalar_quick_add():
    data = request.get_json() or {}
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    notes = data.get("notes", "").strip()
    
    if not full_name:
        return jsonify({"success": False, "message": "Usta ismini kiriting!"}), 400
        
    success, new_id, message = database.create_quick_usta(full_name, phone, notes)
    if success:
        record_system_action('kiritdi', 'usta', f"Yangi usta qo'shildi: {full_name}", f"Tel: {phone or 'Mavjud emas'}, Tezkor qo'shildi", target_id=new_id)
        return jsonify({
            "success": True,
            "message": message,
            "usta": {
                "id": new_id,
                "full_name": full_name,
                "phone": phone,
                "customer_type": "usta"
            }
        })
    else:
        return jsonify({"success": False, "message": message}), 400

@app.route("/api/usta/<int:usta_id>/orders")
@login_required
def api_usta_orders(usta_id):
    """Tanlangan ustaning barcha biriktirilgan buyurtmalari va mijozlari ro'yxati"""
    period = request.args.get("period", "all").strip().lower()
    now = datetime.now()
    
    date_cond = "1=1"
    params = [usta_id]
    
    if period == "today":
        date_cond = "o.created_at >= ?"
        params.append(now.strftime('%Y-%m-%d 00:00:00'))
    elif period == "week":
        date_cond = "o.created_at >= ?"
        params.append((now - timedelta(days=7)).strftime('%Y-%m-%d 00:00:00'))
    elif period in ["month", "1m", "1oy"]:
        date_cond = "o.created_at >= ?"
        params.append((now - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00'))
    elif period in ["3m", "3oy"]:
        date_cond = "o.created_at >= ?"
        params.append((now - timedelta(days=90)).strftime('%Y-%m-%d 00:00:00'))
    elif period in ["6m", "6oy"]:
        date_cond = "o.created_at >= ?"
        params.append((now - timedelta(days=180)).strftime('%Y-%m-%d 00:00:00'))
    elif period in ["1y", "1yil", "year"]:
        date_cond = "o.created_at >= ?"
        params.append((now - timedelta(days=365)).strftime('%Y-%m-%d 00:00:00'))
        
    conn = database.get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE id = ?", (usta_id,))
    usta = cursor.fetchone()
    if not usta:
        conn.close()
        return jsonify({"success": False, "message": "Usta topilmadi"}), 404
        
    query = f"""
        SELECT 
            o.id, o.order_number, o.customer_name, o.customer_phone,
            o.total_amount, o.paid_amount, o.status, o.created_at,
            COALESCE(SUM(oi.quantity), 0) as total_sqm,
            GROUP_CONCAT(oi.brand || ' ' || oi.model_name, ', ') as tiles_summary
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.usta_id = ? AND o.status != 'bekor_qilindi' AND {date_cond}
        GROUP BY o.id
        ORDER BY o.id DESC
    """
    cursor.execute(query, params)
    orders = cursor.fetchall()
    
    # Calculate summary
    total_rev = sum(float(r["total_amount"]) for r in orders)
    total_sqm = sum(float(r["total_sqm"]) for r in orders)
    unique_clients = len(set(r["customer_phone"] or r["customer_name"] for r in orders if (r["customer_phone"] or r["customer_name"])))
    
    conn.close()
    return jsonify({
        "success": True,
        "usta": dict(usta),
        "orders": [dict(r) for r in orders],
        "summary": {
            "orders_count": len(orders),
            "clients_count": unique_clients,
            "total_revenue": total_rev,
            "total_sqm": total_sqm
        }
    })

# ----------------- DO'KON XARAJATLARI (STORE EXPENSES) -----------------

@app.route("/xarajatlar", methods=["GET", "POST"])
@role_required(["admin"])
def xarajatlar():
    conn = database.get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        category = request.form.get("category", "boshqa")
        amount = float(request.form.get("amount", 0) or 0)
        description = request.form.get("description", "").strip()
        expense_date = request.form.get("expense_date") or datetime.now().strftime("%Y-%m-%d")
        user_name = session.get("full_name") or session.get("username") or "Admin"

        if amount <= 0 or not description:
            flash("Iltimos, xarajat summasi va izohini to'liq kiriting!", "danger")
        else:
            cursor.execute("""
                INSERT INTO expenses (category, amount, description, user_name, expense_date)
                VALUES (?, ?, ?, ?, ?)
            """, (category, amount, description, user_name, expense_date))
            new_exp_id = cursor.lastrowid
            conn.commit()
            record_system_action('kiritdi', 'xarajat', f"Xarajat kiritildi: {category.capitalize()}", f"Summa: {amount:,.0f} so'm, Izoh: {description}", target_id=new_exp_id)
            flash(f"Xarajat ({amount:,.0f} so'm) muvaffaqiyatli saqlandi!", "success")
        conn.close()
        return redirect(url_for("xarajatlar"))

    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    cat_filter = request.args.get("category", "").strip()

    query = "SELECT * FROM expenses WHERE expense_date LIKE ?"
    params = [f"{month}%"]

    if cat_filter:
        query += " AND category = ?"
        params.append(cat_filter)

    query += " ORDER BY expense_date DESC, id DESC"
    cursor.execute(query, params)
    expenses = cursor.fetchall()

    cursor.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE expense_date LIKE ?
        GROUP BY category
    """, (f"{month}%",))
    cat_rows = cursor.fetchall()
    cat_data = {r["category"]: float(r["total"]) for r in cat_rows}
    total_month_expense = sum(cat_data.values())

    conn.close()
    return render_template(
        "xarajatlar.html",
        expenses=expenses,
        total_month_expense=total_month_expense,
        cat_data=cat_data,
        month=month,
        cat_filter=cat_filter
    )

@app.route("/xarajatlar/ochirish/<int:expense_id>", methods=["POST"])
@role_required(["admin"])
def xarajat_delete(expense_id):
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    record_system_action('ochirdi', 'xarajat', f"Xarajat o'chirildi: ID #{expense_id}", "Xarajat hisobotdan olib tashlandi", target_id=expense_id)
    flash("Xarajat muvaffaqiyatli o'chirildi!", "info")
    return redirect(url_for("xarajatlar"))

# ----------------- SMETA / TIJORIY TAKLIF CHOP ETISH -----------------

@app.route("/sotuv/smeta")
@login_required
def sotuv_smeta():
    """Xaridor va usta uchun to'lovsiz chiqariladigan Smeta / Tijoriy Taklif"""
    return render_template("smeta_print.html")

# ----------------- SINIQLAR & BRAK KAFELLAR BOSHQARUVI -----------------

@app.route("/api/product/<int:product_id>/report-defect", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_report_product_defect(product_id):
    """Omborda yuklovchilar tomonidan sindirilgan yoki pachkada defekt chiqqan kafelni siniqlar bo'limiga o'tkazish"""
    data = request.get_json() or {}
    quantity = float(data.get("quantity", 0) or 0)
    reason = data.get("reason", "Yuk tushirishda sindi (yuklovchilar)").strip()
    responsible_person = data.get("responsible_person", "").strip() or "Noma'lum"
    note = data.get("note", "").strip()
    user_name = session.get("full_name") or session.get("username") or "Omborchi"

    if quantity <= 0:
        return jsonify({"success": False, "message": "Singan miqdor 0 dan katta bo'lishi kerak!"}), 400

    conn = database.get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        return jsonify({"success": False, "message": "Kafel topilmadi!"}), 404

    current_stock = float(product["quantity_in_stock"])
    if current_stock < quantity:
        conn.close()
        return jsonify({
            "success": False,
            "message": f"Omborda yetarli qoldiq yo'q! Mavjud: {current_stock} {product['unit']}, so'raldi: {quantity}"
        }), 400

    new_stock = round(current_stock - quantity, 2)
    unit_loss_rate = float(product["cost_price"]) if (product["cost_price"] and float(product["cost_price"]) > 0) else float(product["price"])
    loss_amount = round(quantity * unit_loss_rate, 2)
    
    # Siniq sotuv narxi (agar kiritilmagan bo'lsa, asl narxining 50% qilib tavsiya qilinadi)
    discounted_price = float(data.get("discounted_price", 0) or 0)
    if discounted_price <= 0:
        discounted_price = round(float(product["price"]) * 0.5, 0)

    # 1. Asosiy ombor qoldig'ini kamaytirish (masalan, 200 -> 199)
    cursor.execute("UPDATE products SET quantity_in_stock = ? WHERE id = ?", (new_stock, product_id))

    # 2. Siniqlar va brak jadvaliga qo'shish
    cursor.execute("""
        INSERT INTO broken_tiles (
            product_id, quantity, unit, reason, responsible_person,
            status, loss_amount, discounted_price, note, created_by
        ) VALUES (?, ?, ?, ?, ?, 'omborda', ?, ?, ?, ?)
    """, (product_id, quantity, product["unit"], reason, responsible_person, loss_amount, discounted_price, note, user_name))
    defect_id = cursor.lastrowid

    # 3. Ombor harakati (Audit jurnali)ga kiritish
    cursor.execute("""
        INSERT INTO stock_history (
            product_id, change_type, quantity_change, previous_quantity, new_quantity,
            reference_id, user_name, note
        ) VALUES (?, 'brak', ?, ?, ?, ?, ?, ?)
    """, (
        product_id, -quantity, current_stock, new_stock,
        f"BRAK-{defect_id:04d}", user_name,
        f"Siniq/Brak: {reason} [Mas'ul: {responsible_person}]. {note}".strip()
    ))

    # 4. Do'kon xarajatlariga avtomatik zarar sifatida kiritish
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT INTO expenses (category, amount, description, user_name, expense_date)
        VALUES ('brak', ?, ?, ?, ?)
    """, (
        loss_amount,
        f"Kafel braki: {product['brand']} {product['model_name']} ({quantity} {product['unit']}) - {reason} [Mas'ul: {responsible_person}]",
        user_name,
        today_str
    ))

    conn.commit()
    conn.close()

    record_system_action(
        action_type='kiritdi',
        target_type='siniq',
        title=f"Siniq/Brak qayd etildi: {product['brand']} {product['model_name']}",
        description=f"Miqdor: {quantity} {product['unit']}, Sabab: {reason}, Mas'ul: {responsible_person}, Zarar: {loss_amount:,.0f} so'm",
        target_id=defect_id
    )

    return jsonify({
        "success": True,
        "new_stock": new_stock,
        "defect_id": defect_id,
        "loss_amount": loss_amount,
        "message": f"'{product['brand']} {product['model_name']}' kafeli {quantity} {product['unit']} siniqlar bo'limiga o'tkazildi! Ombordagi qoldiq: {new_stock} {product['unit']}"
    })


@app.route("/ombor/siniqlar")
@login_required
def ombor_siniqlar():
    """Siniqlar va brak kafellar boshqaruvi bo'limi"""
    status_filter = request.args.get("status", "").strip()
    reason_filter = request.args.get("reason", "").strip()
    q = request.args.get("q", "").strip()

    conn = database.get_db()
    cursor = conn.cursor()

    query = """
        SELECT bt.*, p.brand, p.model_name, p.size, p.sku, p.price, p.location_rack, p.image_path
        FROM broken_tiles bt
        JOIN products p ON bt.product_id = p.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND bt.status = ?"
        params.append(status_filter)

    if reason_filter:
        query += " AND bt.reason LIKE ?"
        params.append(f"%{reason_filter}%")

    if q:
        query += " AND (p.brand LIKE ? OR p.model_name LIKE ? OR bt.responsible_person LIKE ? OR bt.note LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern, pattern])

    query += " ORDER BY bt.id DESC"
    cursor.execute(query, params)
    defects = cursor.fetchall()

    # KPI stats
    cursor.execute("""
        SELECT
            COALESCE(SUM(quantity), 0) as total_broken_qty,
            COALESCE(SUM(loss_amount), 0) as total_loss_sum,
            COALESCE(SUM(CASE WHEN status = 'omborda' THEN quantity ELSE 0 END), 0) as current_broken_qty,
            COUNT(CASE WHEN status != 'omborda' THEN 1 END) as resolved_count
        FROM broken_tiles
    """)
    kpi = cursor.fetchone()

    # Omborda mavjud kafellar ro'yxati (to'g'ridan-to'g'ri siniq qayd etish uchun)
    cursor.execute("""
        SELECT id, brand, model_name, size, unit, quantity_in_stock
        FROM products
        WHERE quantity_in_stock > 0
        ORDER BY brand, model_name
    """)
    products_list = cursor.fetchall()

    conn.close()
    return render_template(
        "siniqlar.html",
        defects=defects,
        kpi=kpi,
        products_list=products_list,
        status_filter=status_filter,
        reason_filter=reason_filter,
        q=q
    )


@app.route("/api/defect/<int:defect_id>/action", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_defect_action(defect_id):
    """Siniq kafelni tasarruf qilish: hisobdan chiqarish, arzon sotish yoki zavodga qaytarish"""
    data = request.get_json() or {}
    action_type = data.get("action_type", "hisobdan_chiqarildi").strip()
    action_note = (data.get("note") or data.get("action_note") or "").strip()
    sale_price = float(data.get("sale_price", 0) or 0)
    user_name = session.get("full_name") or session.get("username") or "Xodim"

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM broken_tiles WHERE id = ?", (defect_id,))
    defect = cursor.fetchone()
    if not defect:
        conn.close()
        return jsonify({"success": False, "message": "Brak yozuvi topilmadi!"}), 404

    note_addon = f"[{action_type.upper()} ({user_name})]: {action_note}"
    new_loss = float(defect['loss_amount'] or 0)
    if sale_price > 0:
        note_addon += f" [Sotildi: {sale_price:,.0f} so'm]"

    new_note = f"{defect['note'] or ''} | {note_addon}".strip(" |")

    order_id = None
    order_num = None

    if action_type == 'arzonlashtirib_sotildi':
        cursor.execute("SELECT * FROM products WHERE id = ?", (defect["product_id"],))
        prod = cursor.fetchone()
        
        effective_price = sale_price if sale_price > 0 else float(defect["discounted_price"] or 0)
        if effective_price <= 0 and prod:
            effective_price = round(float(prod["price"] or 0) * 0.5, 0)

        def_qty = float(defect["quantity"] or 1.0)
        unit_price = effective_price / def_qty if def_qty > 0 else effective_price

        order_num = database.generate_order_number()
        cursor.execute("""
            INSERT INTO orders (
                order_number, customer_name, customer_phone, total_amount, paid_amount,
                payment_method, status, cashier_note, warehouse_note, seller_name, dispatched_by,
                dispatched_at, is_nasiya, debt_amount
            ) VALUES (?, ?, ?, ?, ?, 'naqd', 'yuk_berildi', ?, ?, ?, ?, CURRENT_TIMESTAMP, 0, 0.0)
        """, (
            order_num,
            "Siniq Kafel Xaridori",
            "",
            effective_price,
            effective_price,
            f"[Siniq/Brak sotuv] {action_note}".strip(),
            "Ombordan chiqarildi",
            user_name,
            user_name
        ))
        order_id = cursor.lastrowid

        model_title = f"{prod['model_name']} [💔 Siniq/Brak]" if prod else "Siniq Kafel [💔 Brak]"
        brand_title = prod["brand"] if prod else "Kafel"
        size_title = prod["size"] if prod else ""
        img_path = prod["image_path"] if prod else None

        cursor.execute("""
            INSERT INTO order_items (
                order_id, product_id, brand, model_name, size, unit, quantity,
                unit_price, total_price, image_path, is_defect, defect_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            order_id,
            defect["product_id"],
            brand_title,
            model_title,
            size_title,
            defect["unit"],
            def_qty,
            unit_price,
            effective_price,
            img_path,
            defect_id
        ))

        cursor.execute("""
            INSERT INTO stock_history (
                product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, user_name, note
            ) VALUES (?, 'sotuv_brak', ?, ?, 0, ?, ?, ?)
        """, (
            defect["product_id"],
            -def_qty,
            def_qty,
            order_num,
            user_name,
            f"Siniq/Brak sotuv #{order_num} ({def_qty} {defect['unit']}, {effective_price:,.0f} so'm)"
        ))

        new_loss = max(0.0, float(defect['loss_amount'] or 0) - effective_price)
        cursor.execute("""
            UPDATE broken_tiles
            SET status = ?, note = ?, loss_amount = ?, sold_price = ?, order_id = ?, quantity = 0
            WHERE id = ?
        """, (action_type, new_note, new_loss, effective_price, order_id, defect_id))
    else:
        cursor.execute("""
            UPDATE broken_tiles SET status = ?, note = ?, loss_amount = ? WHERE id = ?
        """, (action_type, new_note, new_loss, defect_id))

    conn.commit()
    conn.close()

    if order_id:
        return jsonify({
            "success": True,
            "message": f"Siniq kafel sotildi! Nakladnoy chiqarildi: #{order_num}",
            "order_id": order_id,
            "order_number": order_num
        })

    return jsonify({
        "success": True,
        "message": f"Siniq kafel holati '{action_type}' ga muvaffaqiyatli o'zgartirildi!"
    })

@app.route("/api/defect/<int:defect_id>/set-price", methods=["POST"])
@role_required(["admin", "omborchi"])
def api_defect_set_price(defect_id):
    """Admin/omborchi tomonidan siniq kafelga arzonlashtirilgan sotuv narxini belgilash"""
    data = request.get_json() or {}
    price = float(data.get("discounted_price", 0) or 0)
    if price < 0:
        return jsonify({"success": False, "message": "Narx manfiy bo'lishi mumkin emas!"}), 400

    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, product_id, status FROM broken_tiles WHERE id = ?", (defect_id,))
    defect = cursor.fetchone()
    if not defect:
        conn.close()
        return jsonify({"success": False, "message": "Siniq kafel topilmadi!"}), 404

    cursor.execute("UPDATE broken_tiles SET discounted_price = ? WHERE id = ?", (price, defect_id))
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": f"Siniq kafel sotuv narxi {price:,.0f} so'm qilib belgilandi!",
        "new_price": price
    })

@app.route("/api/defects/for-sale", methods=["GET"])
@login_required
def api_defects_for_sale():
    """Sotuvchilar uchun vitrinada sotilishi mumkin bo'lgan siniq/brak kafellar ro'yxati"""
    conn = database.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT bt.id as defect_id, bt.product_id, bt.quantity, bt.unit, bt.reason,
               bt.responsible_person, bt.discounted_price, bt.loss_amount, bt.note,
               p.brand, p.model_name, p.size, p.price as original_price, p.image_path, p.box_size_m2
        FROM broken_tiles bt
        JOIN products p ON bt.product_id = p.id
        WHERE bt.status = 'omborda' AND bt.quantity > 0
        ORDER BY bt.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    defects = []
    for r in rows:
        d_price = float(r["discounted_price"] or 0)
        orig_price = float(r["original_price"] or 0)
        if d_price <= 0:
            d_price = round(orig_price * 0.5, 0)

        defects.append({
            "id": r["defect_id"],
            "product_id": r["product_id"],
            "brand": r["brand"],
            "model_name": r["model_name"],
            "size": r["size"],
            "unit": r["unit"],
            "quantity": float(r["quantity"]),
            "original_price": orig_price,
            "discounted_price": d_price,
            "reason": r["reason"],
            "note": r["note"] or "",
            "image_path": r["image_path"] or "",
            "box_size_m2": float(r["box_size_m2"] or 1.44)
        })

    return jsonify({"success": True, "defects": defects})

# --- HISOBOT & AUDIT JURNALI ---
@app.route("/hisobot")
@app.route("/tarix")
@login_required
def hisobot():
    conn = database.get_db()
    cursor = conn.cursor()

    user_role = session.get("role")
    user_name = session.get("full_name") or session.get("username")
    user_id = session.get("user_id")
    selected_seller = request.args.get("seller", "all").strip()

    seller_sold_products = []
    all_sellers_breakdown = []
    sellers_list = []
    inbound_records = []
    tiles_balance = []
    brands_summary = []
    broken_records = []
    broken_reasons = []
    payment_stats = []
    seller_stats = []
    products_turnover = []
    orders_audit = []

    if user_role == "sotuvchi":
        # ==========================================
        # 1. SOTUVCHI REJIMI: Shaxsiy savdo hisoboti
        # ==========================================
        # Sotuvchi faqat o'zi sotgan tovarlar va nakladnoylarni ko'radi
        cursor.execute("""
            SELECT o.*,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count,
                   (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) as total_sqm
            FROM orders o
            WHERE (o.seller_id = ? OR o.seller_name = ? OR o.seller_name LIKE ?)
            ORDER BY o.id DESC
        """, (user_id, user_name, f"%{user_name}%"))
        orders_rows = cursor.fetchall()

        # Ushbu sotuvchi sotgan barcha tovarlar agregatsiyasi (Spiskasi)
        cursor.execute("""
            SELECT oi.brand, oi.model_name, oi.size, oi.unit,
                   COALESCE(SUM(oi.quantity), 0.0) as total_qty,
                   COALESCE(SUM(oi.total_price), 0.0) as total_sum,
                   COUNT(DISTINCT o.id) as orders_count,
                   MAX(o.created_at) as last_sold_at
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'bekor_qilindi'
              AND (o.seller_id = ? OR o.seller_name = ? OR o.seller_name LIKE ?)
            GROUP BY oi.brand, oi.model_name, oi.size, oi.unit
            ORDER BY total_sum DESC
        """, (user_id, user_name, f"%{user_name}%"))
        seller_sold_products = [dict(r) for r in cursor.fetchall()]

        for ord in orders_rows:
            cursor.execute("""
                SELECT oi.*, p.location_rack, p.sku
                FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (ord["id"],))
            items = cursor.fetchall()
            orders_audit.append({
                "order": ord,
                "items": items
            })

        total_sotuv_m2 = sum(p["total_qty"] for p in seller_sold_products)
        total_revenue = sum(ord["total_amount"] for ord in orders_rows if ord["status"] != 'bekor_qilindi')
        total_orders_count = len(orders_rows)

        summary_stats = {
            "total_kirim_m2": 0.0,
            "total_sotuv_m2": total_sotuv_m2,
            "current_stock_m2": 0.0,
            "total_revenue": total_revenue,
            "total_orders_count": total_orders_count,
            "pending_dispatch_count": 0,
            "dispatched_count": 0,
            "total_brands_count": 0,
            "total_broken_count": 0,
            "total_broken_m2": 0.0,
            "total_loss_sum": 0.0,
            "total_stock_value": 0.0
        }

        conn.close()
        action_logs = database.get_action_logs(limit=300, user_name=user_name)

    elif user_role == "omborchi":
        # ========================================================
        # 2. OMBORCHI REJIMI: Omborxona va Logistika Hisoboti
        #    (Moliyaviy pullar, tushumlar, narxlar ko'rsatilmaydi)
        # ========================================================
        # 1. Ombor KPI ko'rsatkichlari (Fizik hajm va sonlar)
        cursor.execute("SELECT COALESCE(SUM(quantity_change), 0) FROM stock_history WHERE change_type = 'kirim'")
        total_kirim_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(ABS(SUM(quantity_change)), 0) FROM stock_history WHERE change_type = 'sotuv'")
        total_sotuv_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(quantity_in_stock), 0) FROM products")
        current_stock_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'tolandi'")
        pending_dispatch_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'yuk_berildi'")
        dispatched_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders_count = cursor.fetchone()[0]

        # 2. Kirimlar jurnali (Narx ko'rsatilmaydi)
        cursor.execute("""
            SELECT sh.id, sh.product_id, sh.quantity_change, sh.previous_quantity, sh.new_quantity,
                   sh.reference_id, sh.user_name, sh.note, sh.created_at,
                   p.brand, p.model_name, p.size, p.unit, p.location_rack, p.image_path, p.sku
            FROM stock_history sh
            JOIN products p ON sh.product_id = p.id
            WHERE sh.change_type = 'kirim'
            ORDER BY sh.id DESC
        """)
        inbound_records = cursor.fetchall()

        # 3. Ombor qoldig'i va joylashuv (Polkalar, narxsiz)
        cursor.execute("""
            SELECT p.id, p.sku, p.brand, p.model_name, p.size, p.unit, p.quantity_in_stock, 0.0 as price, p.location_rack, p.created_by, p.created_at,
                   COALESCE((SELECT SUM(quantity_change) FROM stock_history WHERE product_id = p.id AND change_type = 'kirim'), 0) as total_in,
                   COALESCE((SELECT ABS(SUM(quantity_change)) FROM stock_history WHERE product_id = p.id AND change_type = 'sotuv'), 0) as total_out
            FROM products p
            ORDER BY p.brand ASC, p.model_name ASC
        """)
        tiles_balance = cursor.fetchall()

        # 4. Kafel markalari (faqat hajm va partiyalar soni)
        cursor.execute("""
            SELECT 
                p.brand,
                COUNT(DISTINCT p.id) as models_count,
                COALESCE(SUM(p.quantity_in_stock), 0.0) as stock_m2,
                0.0 as stock_value,
                COALESCE((
                    SELECT SUM(sh.quantity_change) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                ), 0.0) as total_kirim_m2,
                COALESCE((
                    SELECT COUNT(sh.id) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                ), 0) as inbound_batches_count,
                COALESCE((
                    SELECT ABS(SUM(sh.quantity_change)) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'sotuv'
                ), 0.0) as total_sotuv_m2,
                0.0 as total_revenue,
                COALESCE((
                    SELECT SUM(bt.quantity) 
                    FROM broken_tiles bt 
                    JOIN products p2 ON bt.product_id = p2.id 
                    WHERE p2.brand = p.brand
                ), 0.0) as broken_m2,
                0.0 as broken_loss_sum,
                (
                    SELECT sh.created_at 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                    ORDER BY sh.id DESC LIMIT 1
                ) as last_inbound_date
            FROM products p
            GROUP BY p.brand
            ORDER BY stock_m2 DESC, p.brand ASC
        """)
        brands_summary = [dict(r) for r in cursor.fetchall()]
        total_all_stock = current_stock_m2 if current_stock_m2 > 0 else 1.0
        for b in brands_summary:
            b["share_pct"] = round((b["stock_m2"] / total_all_stock) * 100, 1)

        # 5. Siniqlar va braklar (zarar so'mmasiz)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_broken_count,
                COALESCE(SUM(quantity), 0.0) as total_broken_m2,
                0.0 as total_loss_sum
            FROM broken_tiles
        """)
        broken_stats = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT bt.id, bt.product_id, bt.quantity, bt.unit, bt.reason, bt.responsible_person,
                   bt.status, bt.created_at, bt.created_by as user_name, bt.note, 0.0 as loss_amount,
                   p.brand, p.model_name, p.size, p.sku, p.location_rack, p.image_path
            FROM broken_tiles bt
            JOIN products p ON bt.product_id = p.id
            ORDER BY bt.id DESC
        """)
        broken_records = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT reason, COUNT(*) as count, COALESCE(SUM(quantity), 0.0) as sqm, 0.0 as loss
            FROM broken_tiles
            GROUP BY reason
            ORDER BY sqm DESC
        """)
        broken_reasons = [dict(r) for r in cursor.fetchall()]

        # 6. Buyurtmalarni yuklash nazorati (Topshirish jurnali, pullarsiz)
        cursor.execute("""
            SELECT o.id, o.order_number, o.customer_name, o.customer_phone, o.status,
                   o.dispatched_by, o.dispatched_at, o.warehouse_note, o.created_at, o.seller_name,
                   0.0 as total_amount, '' as payment_method,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count,
                   (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) as total_sqm
            FROM orders o
            ORDER BY CASE WHEN o.status = 'tolandi' THEN 0 ELSE 1 END, o.id DESC
        """)
        orders_rows = cursor.fetchall()

        for ord in orders_rows:
            cursor.execute("""
                SELECT oi.id, oi.brand, oi.model_name, oi.size, oi.unit, oi.quantity,
                       0.0 as unit_price, 0.0 as total_price,
                       p.location_rack, p.sku
                FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (ord["id"],))
            items = cursor.fetchall()
            orders_audit.append({
                "order": ord,
                "items": items
            })

        summary_stats = {
            "total_kirim_m2": total_kirim_m2,
            "total_sotuv_m2": total_sotuv_m2,
            "current_stock_m2": current_stock_m2,
            "total_revenue": 0.0,
            "total_orders_count": total_orders_count,
            "pending_dispatch_count": pending_dispatch_count,
            "dispatched_count": dispatched_count,
            "total_brands_count": len(brands_summary),
            "total_broken_count": broken_stats.get("total_broken_count", 0),
            "total_broken_m2": broken_stats.get("total_broken_m2", 0.0),
            "total_loss_sum": 0.0,
            "total_stock_value": 0.0
        }

        # 7. Ombor amallari tarixi
        cursor.execute("""
            SELECT * FROM action_logs
            WHERE target_type IN ('kafel', 'kirim', 'siniq', 'zavod', 'ombor')
               OR action_type = 'topshirdi'
               OR user_name = ?
            ORDER BY id DESC LIMIT 300
        """, (user_name,))
        action_logs = [dict(r) for r in cursor.fetchall()]
        conn.close()

    else:
        # ========================================================
        # 3. ADMIN REJIMI: Boshqaruv va To'liq Moliyaviy Nazorat
        # ========================================================
        cursor.execute("SELECT COALESCE(SUM(quantity_change), 0) FROM stock_history WHERE change_type = 'kirim'")
        total_kirim_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(ABS(SUM(quantity_change)), 0) FROM stock_history WHERE change_type = 'sotuv'")
        total_sotuv_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(quantity_in_stock), 0) FROM products")
        current_stock_m2 = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'bekor_qilindi'")
        total_revenue = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'tolandi'")
        pending_dispatch_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'yuk_berildi'")
        dispatched_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT sh.id, sh.product_id, sh.quantity_change, sh.previous_quantity, sh.new_quantity,
                   sh.reference_id, sh.user_name, sh.note, sh.created_at,
                   p.brand, p.model_name, p.size, p.unit, p.location_rack, p.image_path, p.sku, p.price
            FROM stock_history sh
            JOIN products p ON sh.product_id = p.id
            WHERE sh.change_type = 'kirim'
            ORDER BY sh.id DESC
        """)
        inbound_records = cursor.fetchall()

        cursor.execute("""
            SELECT DISTINCT COALESCE(seller_name, 'Sotuvchi (Kassir)') as seller_name
            FROM orders
            WHERE seller_name IS NOT NULL AND seller_name != ''
            UNION
            SELECT full_name as seller_name FROM users WHERE role = 'sotuvchi'
            ORDER BY seller_name ASC
        """)
        sellers_list = [r["seller_name"] for r in cursor.fetchall()]

        for s_name in sellers_list:
            cursor.execute("""
                SELECT oi.brand, oi.model_name, oi.size, oi.unit,
                       COALESCE(SUM(oi.quantity), 0.0) as total_qty,
                       COALESCE(SUM(oi.total_price), 0.0) as total_sum,
                       COUNT(DISTINCT o.id) as orders_count,
                       MAX(o.created_at) as last_sold_at
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.id
                WHERE o.status != 'bekor_qilindi'
                  AND (o.seller_name = ? OR (SELECT full_name FROM users WHERE id = o.seller_id) = ? OR o.seller_name LIKE ?)
                GROUP BY oi.brand, oi.model_name, oi.size, oi.unit
                ORDER BY total_sum DESC
            """, (s_name, s_name, f"%{s_name}%"))
            s_prods = [dict(r) for r in cursor.fetchall()]
            if s_prods:
                all_sellers_breakdown.append({
                    "seller_name": s_name,
                    "products": s_prods,
                    "total_qty": sum(p["total_qty"] for p in s_prods),
                    "total_sum": sum(p["total_sum"] for p in s_prods),
                    "orders_count": sum(p["orders_count"] for p in s_prods)
                })

        if selected_seller and selected_seller != "all":
            cursor.execute("""
                SELECT o.*,
                       (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count,
                       (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) as total_sqm
                FROM orders o
                WHERE (o.seller_name = ? OR (SELECT full_name FROM users WHERE id = o.seller_id) = ? OR o.seller_name LIKE ?)
                ORDER BY o.id DESC
            """, (selected_seller, selected_seller, f"%{selected_seller}%"))
            orders_rows = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT o.*,
                       (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count,
                       (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) as total_sqm
                FROM orders o
                ORDER BY o.id DESC
            """)
            orders_rows = cursor.fetchall()

        for ord in orders_rows:
            cursor.execute("""
                SELECT oi.*, p.location_rack, p.sku
                FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (ord["id"],))
            items = cursor.fetchall()
            orders_audit.append({
                "order": ord,
                "items": items
            })

        cursor.execute("""
            SELECT p.id, p.sku, p.brand, p.model_name, p.size, p.unit, p.quantity_in_stock, p.price, p.location_rack, p.created_by, p.created_at,
                   COALESCE((SELECT SUM(quantity_change) FROM stock_history WHERE product_id = p.id AND change_type = 'kirim'), 0) as total_in,
                   COALESCE((SELECT ABS(SUM(quantity_change)) FROM stock_history WHERE product_id = p.id AND change_type = 'sotuv'), 0) as total_out
            FROM products p
            ORDER BY p.brand ASC, p.model_name ASC
        """)
        tiles_balance = cursor.fetchall()

        cursor.execute("""
            SELECT 
                p.brand,
                COUNT(DISTINCT p.id) as models_count,
                COALESCE(SUM(p.quantity_in_stock), 0.0) as stock_m2,
                COALESCE(SUM(p.quantity_in_stock * p.price), 0.0) as stock_value,
                COALESCE((
                    SELECT SUM(sh.quantity_change) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                ), 0.0) as total_kirim_m2,
                COALESCE((
                    SELECT COUNT(sh.id) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                ), 0) as inbound_batches_count,
                COALESCE((
                    SELECT ABS(SUM(sh.quantity_change)) 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'sotuv'
                ), 0.0) as total_sotuv_m2,
                COALESCE((
                    SELECT SUM(oi.total_price) 
                    FROM order_items oi 
                    JOIN products p2 ON oi.product_id = p2.id 
                    JOIN orders o ON oi.order_id = o.id 
                    WHERE p2.brand = p.brand AND o.status != 'bekor_qilindi'
                ), 0.0) as total_revenue,
                COALESCE((
                    SELECT SUM(bt.quantity) 
                    FROM broken_tiles bt 
                    JOIN products p2 ON bt.product_id = p2.id 
                    WHERE p2.brand = p.brand
                ), 0.0) as broken_m2,
                COALESCE((
                    SELECT SUM(bt.loss_amount) 
                    FROM broken_tiles bt 
                    JOIN products p2 ON bt.product_id = p2.id 
                    WHERE p2.brand = p.brand
                ), 0.0) as broken_loss_sum,
                (
                    SELECT sh.created_at 
                    FROM stock_history sh 
                    JOIN products p2 ON sh.product_id = p2.id 
                    WHERE p2.brand = p.brand AND sh.change_type = 'kirim'
                    ORDER BY sh.id DESC LIMIT 1
                ) as last_inbound_date
            FROM products p
            GROUP BY p.brand
            ORDER BY stock_m2 DESC, p.brand ASC
        """)
        brands_summary = [dict(r) for r in cursor.fetchall()]
        total_all_stock = current_stock_m2 if current_stock_m2 > 0 else 1.0
        for b in brands_summary:
            b["share_pct"] = round((b["stock_m2"] / total_all_stock) * 100, 1)

        cursor.execute("""
            SELECT 
                COUNT(*) as total_broken_count,
                COALESCE(SUM(quantity), 0.0) as total_broken_m2,
                COALESCE(SUM(loss_amount), 0.0) as total_loss_sum
            FROM broken_tiles
        """)
        broken_stats = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT bt.*, p.brand, p.model_name, p.size, p.sku, p.price, p.location_rack, p.image_path
            FROM broken_tiles bt
            JOIN products p ON bt.product_id = p.id
            ORDER BY bt.id DESC
        """)
        broken_records = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT reason, COUNT(*) as count, COALESCE(SUM(quantity), 0.0) as sqm, COALESCE(SUM(loss_amount), 0.0) as loss
            FROM broken_tiles
            GROUP BY reason
            ORDER BY sqm DESC
        """)
        broken_reasons = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT COALESCE(SUM(quantity_in_stock * price), 0.0) FROM products")
        total_stock_value = cursor.fetchone()[0]

        cursor.execute("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0.0) as total_sum
            FROM orders
            WHERE status != 'bekor_qilindi'
            GROUP BY payment_method
            ORDER BY total_sum DESC
        """)
        payment_stats = [dict(r) for r in cursor.fetchall()]
        total_paid_sum = sum(p["total_sum"] for p in payment_stats) if payment_stats else 1.0
        for p in payment_stats:
            p["pct"] = round((p["total_sum"] / total_paid_sum) * 100, 1) if total_paid_sum > 0 else 0

        cursor.execute("""
            SELECT 
                COALESCE(seller_name, 'Sotuvchi (Kassir)') as seller_name,
                COUNT(*) as orders_count,
                COALESCE(SUM(total_amount), 0.0) as total_revenue
            FROM orders
            WHERE status != 'bekor_qilindi'
            GROUP BY seller_name
            ORDER BY total_revenue DESC
        """)
        seller_stats = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT p.brand, p.model_name, p.size, p.price, p.quantity_in_stock,
                   COALESCE(SUM(oi.quantity), 0.0) as sold_qty,
                   COALESCE(SUM(oi.total_price), 0.0) as sold_sum
            FROM products p
            LEFT JOIN order_items oi ON oi.product_id = p.id
            LEFT JOIN orders o ON oi.order_id = o.id AND o.status != 'bekor_qilindi'
            GROUP BY p.id
            ORDER BY sold_qty DESC, p.quantity_in_stock DESC
        """)
        products_turnover = [dict(r) for r in cursor.fetchall()]

        conn.close()

        summary_stats = {
            "total_kirim_m2": total_kirim_m2,
            "total_sotuv_m2": total_sotuv_m2,
            "current_stock_m2": current_stock_m2,
            "total_revenue": total_revenue,
            "total_orders_count": total_orders_count,
            "pending_dispatch_count": pending_dispatch_count,
            "dispatched_count": dispatched_count,
            "total_brands_count": len(brands_summary),
            "total_broken_count": broken_stats.get("total_broken_count", 0),
            "total_broken_m2": broken_stats.get("total_broken_m2", 0.0),
            "total_loss_sum": broken_stats.get("total_loss_sum", 0.0),
            "total_stock_value": total_stock_value
        }

        action_logs = database.get_action_logs(limit=300)

    return render_template(
        "hisobot.html",
        summary=summary_stats,
        inbound_records=inbound_records,
        orders_audit=orders_audit,
        tiles_balance=tiles_balance,
        brands_summary=brands_summary,
        broken_records=broken_records,
        broken_reasons=broken_reasons,
        payment_stats=payment_stats,
        seller_stats=seller_stats,
        products_turnover=products_turnover,
        action_logs=action_logs,
        seller_sold_products=seller_sold_products,
        all_sellers_breakdown=all_sellers_breakdown,
        sellers_list=sellers_list,
        selected_seller=selected_seller
    )

# --- XODIMLAR VA USTALAR KPI REYTING TIZIMI ---
@app.route("/kpi")
@role_required(["admin", "sotuvchi"])
def kpi_dashboard():
    period = request.args.get("period", "1m").strip().lower()
    try:
        bonus_rate = float(request.args.get("rate", 2.0) or 2.0)
    except ValueError:
        bonus_rate = 2.0

    try:
        usta_rate = float(request.args.get("usta_rate", 2.0) or 2.0)
    except ValueError:
        usta_rate = 2.0

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    week_ago_str = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago_str = (now - timedelta(days=30)).strftime('%Y-%m-%d')
    three_months_ago_str = (now - timedelta(days=90)).strftime('%Y-%m-%d')
    six_months_ago_str = (now - timedelta(days=180)).strftime('%Y-%m-%d')
    one_year_ago_str = (now - timedelta(days=365)).strftime('%Y-%m-%d')

    orders_date_cond = "1=1"
    stock_date_cond = "1=1"
    date_params = []
    
    if period == "today":
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [today_str + " 00:00:00"]
        period_title = "Bugungi Kun"
    elif period == "week":
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [week_ago_str + " 00:00:00"]
        period_title = "Oxirgi 7 Kun"
    elif period in ["month", "1m", "1oy"]:
        period = "1m"
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [month_ago_str + " 00:00:00"]
        period_title = "Oxirgi 1 Oy (30 kun)"
    elif period in ["3m", "3oy"]:
        period = "3m"
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [three_months_ago_str + " 00:00:00"]
        period_title = "Oxirgi 3 Oy (90 kun)"
    elif period in ["6m", "6oy"]:
        period = "6m"
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [six_months_ago_str + " 00:00:00"]
        period_title = "Oxirgi 6 Oy (180 kun)"
    elif period in ["1y", "1yil", "year"]:
        period = "1y"
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [one_year_ago_str + " 00:00:00"]
        period_title = "Oxirgi 1 Yil (365 kun)"
    elif period == "all":
        period_title = "Barcha Vaqt"
    else:
        period = "1m"
        orders_date_cond = "o.created_at >= ?"
        stock_date_cond = "created_at >= ?"
        date_params = [month_ago_str + " 00:00:00"]
        period_title = "Oxirgi 1 Oy (30 kun)"

    conn = database.get_db()
    cursor = conn.cursor()

    # 1. Barcha aktiv do'kon xodimlari
    cursor.execute("SELECT id, username, full_name, role, created_at FROM users WHERE is_active = 1 ORDER BY role, id")
    all_users = cursor.fetchall()

    # 2. Tanlangan davrdagi umumiy jamoa savdosi
    team_query = f"""
        SELECT 
            COUNT(DISTINCT o.id) as team_orders,
            COALESCE(SUM(o.total_amount), 0.0) as team_revenue,
            COALESCE(SUM(oi.quantity), 0.0) as team_sqm
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.status != 'bekor_qilindi' AND {orders_date_cond}
    """
    cursor.execute(team_query, date_params)
    team_stats = cursor.fetchone()
    total_team_revenue = team_stats["team_revenue"] or 0.0
    total_team_sqm = team_stats["team_sqm"] or 0.0
    total_team_orders = team_stats["team_orders"] or 0

    # 3. Sotuvchilar KPI ro'yxati
    sales_users = [u for u in all_users if u["role"] in ["sotuvchi", "admin"]]
    seller_kpi_list = []

    for u in sales_users:
        u_name = u["full_name"]
        u_username = u["username"]

        seller_query = f"""
            SELECT 
                COUNT(DISTINCT o.id) as orders_count,
                COALESCE(SUM(o.total_amount), 0.0) as total_revenue,
                COALESCE(SUM(oi.quantity), 0.0) as total_sqm
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status != 'bekor_qilindi' 
              AND (o.seller_name = ? OR o.seller_name = ?)
              AND {orders_date_cond}
        """
        cursor.execute(seller_query, [u_name, u_username] + date_params)
        stats = cursor.fetchone()

        orders_count = stats["orders_count"] or 0
        total_revenue = stats["total_revenue"] or 0.0
        total_sqm = stats["total_sqm"] or 0.0
        avg_check = (total_revenue / orders_count) if orders_count > 0 else 0.0
        share_percent = (total_revenue / total_team_revenue * 100) if total_team_revenue > 0 else 0.0
        bonus_amount = total_revenue * (bonus_rate / 100.0)

        # Xodimning eng ko'p sotgan kafeli
        top_tile_query = f"""
            SELECT oi.brand, oi.model_name, SUM(oi.quantity) as sqm_sold
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'bekor_qilindi' 
              AND (o.seller_name = ? OR o.seller_name = ?)
              AND {orders_date_cond}
            GROUP BY oi.product_id, oi.brand, oi.model_name
            ORDER BY sqm_sold DESC
            LIMIT 1
        """
        cursor.execute(top_tile_query, [u_name, u_username] + date_params)
        top_tile_row = cursor.fetchone()
        top_tile_info = f"{top_tile_row['brand']} ({top_tile_row['sqm_sold']:.1f} m²)" if top_tile_row else "—"

        if total_revenue >= 10000000:
            performance_tier = "A'lo daraja"
            tier_color = "emerald"
        elif total_revenue >= 3000000:
            performance_tier = "Yaxshi natija"
            tier_color = "sky"
        elif total_revenue > 0:
            performance_tier = "O'rtacha faollik"
            tier_color = "amber"
        else:
            performance_tier = "Harakatda"
            tier_color = "slate"

        seller_kpi_list.append({
            "user": u,
            "orders_count": orders_count,
            "total_revenue": total_revenue,
            "total_sqm": total_sqm,
            "avg_check": avg_check,
            "share_percent": share_percent,
            "bonus_amount": bonus_amount,
            "top_tile": top_tile_info,
            "performance_tier": performance_tier,
            "tier_color": tier_color
        })

    # Saralash va reyting berish (Sotuvchilar)
    seller_kpi_list.sort(key=lambda x: x["total_revenue"], reverse=True)
    for idx, item in enumerate(seller_kpi_list):
        item["rank"] = idx + 1
        if idx == 0 and item["total_revenue"] > 0:
            item["medal"] = "🥇"
            item["medal_title"] = "1-o'rin (Lider)"
        elif idx == 1 and item["total_revenue"] > 0:
            item["medal"] = "🥈"
            item["medal_title"] = "2-o'rin"
        elif idx == 2 and item["total_revenue"] > 0:
            item["medal"] = "🥉"
            item["medal_title"] = "3-o'rin"
        else:
            item["medal"] = f"#{idx + 1}"
            item["medal_title"] = f"{idx + 1}-o'rin"

    top_performer = seller_kpi_list[0] if seller_kpi_list and seller_kpi_list[0]["total_revenue"] > 0 else None
    total_bonus_pool = sum(x["bonus_amount"] for x in seller_kpi_list)

    # 4. Omborchilar (Warehouse Logistics KPI)
    warehouse_users = [u for u in all_users if u["role"] in ["omborchi", "admin"]]
    warehouse_kpi_list = []

    for w in warehouse_users:
        w_name = w["full_name"]
        w_username = w["username"]

        disp_query = f"""
            SELECT 
                COUNT(DISTINCT o.id) as dispatched_orders,
                COALESCE(SUM(oi.quantity), 0.0) as dispatched_sqm
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'yuk_berildi' 
              AND (o.dispatched_by = ? OR o.dispatched_by = ?)
              AND {orders_date_cond}
        """
        cursor.execute(disp_query, [w_name, w_username] + date_params)
        disp_stats = cursor.fetchone()

        inb_query = f"""
            SELECT 
                COUNT(*) as inbound_operations,
                COALESCE(SUM(quantity_change), 0.0) as inbound_sqm
            FROM stock_history
            WHERE change_type = 'kirim'
              AND (user_name = ? OR user_name = ?)
              AND {stock_date_cond}
        """
        cursor.execute(inb_query, [w_name, w_username] + date_params)
        inb_stats = cursor.fetchone()

        warehouse_kpi_list.append({
            "user": w,
            "dispatched_orders": disp_stats["dispatched_orders"] or 0,
            "dispatched_sqm": disp_stats["dispatched_sqm"] or 0.0,
            "inbound_operations": inb_stats["inbound_operations"] or 0,
            "inbound_sqm": inb_stats["inbound_sqm"] or 0.0
        })

    warehouse_kpi_list.sort(key=lambda x: (x["dispatched_sqm"] + x["inbound_sqm"]), reverse=True)

    # 5. USTALAR VA PRORABLAR KPI REYTINGI
    cursor.execute("""
        SELECT DISTINCT c.id, c.full_name, c.phone, c.customer_type, c.notes, c.created_at
        FROM customers c
        WHERE c.customer_type IN ('usta', 'prorab')
           OR c.id IN (SELECT DISTINCT usta_id FROM orders WHERE usta_id IS NOT NULL)
        ORDER BY c.full_name ASC
    """)
    all_ustalar = cursor.fetchall()
    usta_kpi_list = []

    for u in all_ustalar:
        u_id = u["id"]
        u_query = f"""
            SELECT 
                COUNT(DISTINCT o.id) as orders_count,
                COUNT(DISTINCT CASE 
                    WHEN o.customer_phone IS NOT NULL AND TRIM(o.customer_phone) != '' THEN TRIM(o.customer_phone)
                    WHEN o.customer_name IS NOT NULL AND TRIM(o.customer_name) != '' AND LOWER(TRIM(o.customer_name)) != 'mijoz' THEN TRIM(o.customer_name)
                    ELSE CAST(o.id AS TEXT)
                END) as clients_count,
                COALESCE(SUM(o.total_amount), 0.0) as total_revenue,
                COALESCE(SUM(oi.quantity), 0.0) as total_sqm
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status != 'bekor_qilindi'
              AND o.usta_id = ?
              AND {orders_date_cond}
        """
        cursor.execute(u_query, [u_id] + date_params)
        u_stats = cursor.fetchone()

        orders_count = u_stats["orders_count"] or 0
        clients_count = u_stats["clients_count"] or 0
        total_revenue = u_stats["total_revenue"] or 0.0
        total_sqm = u_stats["total_sqm"] or 0.0
        avg_check = (total_revenue / orders_count) if orders_count > 0 else 0.0
        bonus_amount = total_revenue * (usta_rate / 100.0)

        # Ustaning mijozlari eng ko'p olgan kafel
        top_tile_u_query = f"""
            SELECT oi.brand, oi.model_name, SUM(oi.quantity) as sqm_sold
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status != 'bekor_qilindi'
              AND o.usta_id = ?
              AND {orders_date_cond}
            GROUP BY oi.product_id, oi.brand, oi.model_name
            ORDER BY sqm_sold DESC
            LIMIT 1
        """
        cursor.execute(top_tile_u_query, [u_id] + date_params)
        top_t_row = cursor.fetchone()
        top_tile_info = f"{top_t_row['brand']} ({top_t_row['sqm_sold']:.1f} m²)" if top_t_row else "—"

        usta_kpi_list.append({
            "usta": u,
            "orders_count": orders_count,
            "clients_count": clients_count,
            "total_revenue": total_revenue,
            "total_sqm": total_sqm,
            "avg_check": avg_check,
            "bonus_amount": bonus_amount,
            "top_tile": top_tile_info
        })

    # Ustalar reytingi: Birinchi navbatda kim ko'p klient olib kelsa (clients_count), so'ng savdosiga qarab (total_revenue)!
    usta_kpi_list.sort(key=lambda x: (x["clients_count"], x["total_revenue"], x["total_sqm"]), reverse=True)
    
    for idx, item in enumerate(usta_kpi_list):
        item["rank"] = idx + 1
        if idx == 0 and (item["clients_count"] > 0 or item["total_revenue"] > 0):
            item["medal"] = "🥇"
            item["medal_title"] = "1-o'rin (Oltin Kubok - Lider Usta)"
            item["tier_color"] = "amber"
        elif idx == 1 and (item["clients_count"] > 0 or item["total_revenue"] > 0):
            item["medal"] = "🥈"
            item["medal_title"] = "2-o'rin (Kumush Kubok)"
            item["tier_color"] = "slate"
        elif idx == 2 and (item["clients_count"] > 0 or item["total_revenue"] > 0):
            item["medal"] = "🥉"
            item["medal_title"] = "3-o'rin (Bronza Kubok)"
            item["tier_color"] = "amber"
        else:
            item["medal"] = f"#{idx + 1}"
            item["medal_title"] = f"{idx + 1}-o'rin"
            item["tier_color"] = "slate"

    top_usta = usta_kpi_list[0] if usta_kpi_list and (usta_kpi_list[0]["clients_count"] > 0 or usta_kpi_list[0]["total_revenue"] > 0) else None
    total_usta_clients = sum(x["clients_count"] for x in usta_kpi_list)
    total_usta_revenue = sum(x["total_revenue"] for x in usta_kpi_list)
    total_usta_sqm = sum(x["total_sqm"] for x in usta_kpi_list)
    total_usta_orders = sum(x["orders_count"] for x in usta_kpi_list)
    total_usta_bonus = sum(x["bonus_amount"] for x in usta_kpi_list)

    # 6. Diagrammalar uchun
    chart_labels = [x["user"]["full_name"] for x in seller_kpi_list]
    chart_revenues = [x["total_revenue"] for x in seller_kpi_list]
    chart_sqm = [round(x["total_sqm"], 2) for x in seller_kpi_list]

    usta_chart_labels = [x["usta"]["full_name"] for x in usta_kpi_list[:10]]
    usta_chart_clients = [x["clients_count"] for x in usta_kpi_list[:10]]
    usta_chart_revenues = [x["total_revenue"] for x in usta_kpi_list[:10]]
    usta_chart_sqm = [round(x["total_sqm"], 2) for x in usta_kpi_list[:10]]

    conn.close()

    return render_template(
        "kpi.html",
        period=period,
        period_title=period_title,
        bonus_rate=bonus_rate,
        usta_rate=usta_rate,
        seller_kpi_list=seller_kpi_list,
        warehouse_kpi_list=warehouse_kpi_list,
        top_performer=top_performer,
        total_team_revenue=total_team_revenue,
        total_team_sqm=total_team_sqm,
        total_team_orders=total_team_orders,
        total_bonus_pool=total_bonus_pool,
        usta_kpi_list=usta_kpi_list,
        top_usta=top_usta,
        total_usta_clients=total_usta_clients,
        total_usta_revenue=total_usta_revenue,
        total_usta_sqm=total_usta_sqm,
        total_usta_orders=total_usta_orders,
        total_usta_bonus=total_usta_bonus,
        chart_labels=json.dumps(chart_labels),
        chart_revenues=json.dumps(chart_revenues),
        chart_sqm=json.dumps(chart_sqm),
        usta_chart_labels=json.dumps(usta_chart_labels),
        usta_chart_clients=json.dumps(usta_chart_clients),
        usta_chart_revenues=json.dumps(usta_chart_revenues),
        usta_chart_sqm=json.dumps(usta_chart_sqm)
    )

# Dasturni ishga tushirishda bazani tekshirish
with app.app_context():
    database.init_db()

if __name__ == "__main__":
    is_debug = os.environ.get("FLASK_DEBUG", "1").lower() in ("1", "true")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=is_debug)
