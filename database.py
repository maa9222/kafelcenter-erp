import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_file():
    return os.environ.get("DB_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kafel_database.db')

DB_FILE = get_db_file()

def get_db():
    conn = sqlite3.connect(get_db_file(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Foydalanuvchilar (Users & Roles) jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL, -- 'admin', 'sotuvchi', 'omborchi'
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Mahsulotlar (Kafellar) jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        brand TEXT NOT NULL,
        model_name TEXT NOT NULL,
        size TEXT NOT NULL,
        unit TEXT DEFAULT 'm²',
        box_size_m2 REAL DEFAULT 1.44,
        pieces_per_box INTEGER DEFAULT 4,
        quantity_in_stock REAL NOT NULL DEFAULT 0.0,
        min_quantity REAL DEFAULT 10.0,
        price REAL NOT NULL,
        cost_price REAL DEFAULT 0.0,
        image_path TEXT,
        qr_code_path TEXT,
        location_rack TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Buyurtmalar (Savdo / Kassa) jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        total_amount REAL NOT NULL,
        paid_amount REAL NOT NULL,
        payment_method TEXT NOT NULL, -- 'naqd', 'karta', 'aralash'
        status TEXT NOT NULL DEFAULT 'tolandi', -- 'kutilmoqda', 'tolandi', 'yuk_berildi', 'bekor_qilindi'
        cashier_note TEXT,
        warehouse_note TEXT,
        dispatched_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Buyurtma tarkibidagi mahsulotlar jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        brand TEXT NOT NULL,
        model_name TEXT NOT NULL,
        size TEXT NOT NULL,
        unit TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        image_path TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)

    # Ombor harakati (Kirim, Chiqim tarixi)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        change_type TEXT NOT NULL, -- 'kirim', 'sotuv', 'tuzatish'
        quantity_change REAL NOT NULL,
        previous_quantity REAL NOT NULL,
        new_quantity REAL NOT NULL,
        reference_id TEXT, -- Order number or document number
        user_name TEXT,    -- Qaysi xodim bajardi
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)

    # Mijozlar (CRM & Nasiya Daftari) jadvali
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        phone TEXT,
        customer_type TEXT DEFAULT 'xaridor', -- 'usta', 'prorab', 'xaridor', 'doimiy'
        balance_debt REAL DEFAULT 0.0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Mijozlarning qarz to'lovlari (Nasiya to'lash tarixi)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        order_id INTEGER,
        amount REAL NOT NULL,
        payment_method TEXT DEFAULT 'naqd', -- 'naqd', 'karta'
        note TEXT,
        received_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
    )
    """)

    # Do'kon xarajatlari (Ijara, transport, oylik, brak, kommunal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL, -- 'ijara', 'transport', 'oylik', 'brak', 'kommunal', 'boshqa'
        amount REAL NOT NULL,
        description TEXT,
        user_name TEXT,
        expense_date DATE DEFAULT (DATE('now')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Siniqlar va brak kafellar (Broken and defective tiles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS broken_tiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT NOT NULL,
        reason TEXT NOT NULL,
        responsible_person TEXT,
        status TEXT DEFAULT 'omborda',
        loss_amount REAL DEFAULT 0.0,
        discounted_price REAL DEFAULT 0.0,
        sold_price REAL DEFAULT 0.0,
        order_id INTEGER,
        note TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
    """)

    # Zavodlar va Markalar (Tile Factories & Brands)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS factories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        country TEXT DEFAULT 'O''zbekiston',
        contact_person TEXT,
        phone TEXT,
        address TEXT,
        note TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Harakatlar / Qilingan ishlar tarixi (Action Audit Log)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS action_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT NOT NULL,
        user_role TEXT NOT NULL,
        action_type TEXT NOT NULL, -- 'kiritdi', 'ochirdi', 'tahrirladi', 'sotdi', 'topshirdi'
        target_type TEXT NOT NULL, -- 'kafel', 'kirim', 'savdo', 'usta', 'xodim', 'zavod', 'siniq', 'xarajat'
        target_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Audit va kengaytirilgan ustunlarni tekshirish va qo'shish (agar mavjud bo'lmasa)
    audit_alters = [
        ("orders", "seller_name", "TEXT"),
        ("orders", "seller_id", "INTEGER"),
        ("orders", "dispatched_by", "TEXT"),
        ("orders", "is_nasiya", "INTEGER DEFAULT 0"),
        ("orders", "debt_amount", "REAL DEFAULT 0.0"),
        ("orders", "customer_id", "INTEGER"),
        ("stock_history", "user_name", "TEXT"),
        ("products", "created_by", "TEXT"),
        ("broken_tiles", "discounted_price", "REAL DEFAULT 0.0"),
        ("broken_tiles", "sold_price", "REAL DEFAULT 0.0"),
        ("broken_tiles", "order_id", "INTEGER"),
        ("order_items", "is_defect", "INTEGER DEFAULT 0"),
        ("order_items", "defect_id", "INTEGER"),
        ("orders", "usta_id", "INTEGER"),
        ("customers", "referred_by_usta_id", "INTEGER")
    ]
    for tbl, col, col_type in audit_alters:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    conn.commit()
    conn.close()
    
    # Boshlang'ich foydalanuvchilar va zavodlarni yaratish
    create_default_users()
    create_default_factories()

def create_default_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_users = [
            ("admin", generate_password_hash("admin123"), "Super Admin", "admin"),
            ("sotuvchi", generate_password_hash("sotuvchi123"), "Sotuvchi (Kassir)", "sotuvchi"),
            ("omborchi", generate_password_hash("omborchi123"), "Bosh Omborchi", "omborchi"),
        ]
        cursor.executemany("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, default_users)
        conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (username.strip().lower(),))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id ASC")
    users = cursor.fetchall()
    conn.close()
    return users

def create_user(username, password, full_name, role):
    conn = get_db()
    cursor = conn.cursor()
    try:
        pw_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
        """, (username.strip().lower(), pw_hash, full_name.strip(), role))
        conn.commit()
        conn.close()
        return True, "Foydalanuvchi muvaffaqiyatli qo'shildi!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"'{username}' logini allaqachon band!"
    except Exception as e:
        conn.close()
        return False, str(e)

def update_user_password(user_id, new_password):
    conn = get_db()
    cursor = conn.cursor()
    pw_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ? AND username != 'admin'", (user_id,))
    conn.commit()
    conn.close()

def generate_order_number():
    now = datetime.now()
    prefix = now.strftime("NK-%y%m%d-")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT order_number FROM orders WHERE order_number LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}%",))
    last = cursor.fetchone()
    conn.close()
    if last and last[0]:
        try:
            last_num = int(last[0].split("-")[-1])
            next_num = last_num + 1
        except Exception:
            next_num = 1
    else:
        next_num = 1
    return f"{prefix}{next_num:04d}"

def generate_product_sku(brand, model_name):
    clean_brand = "".join(filter(str.isalnum, brand))[:3].upper()
    clean_model = "".join(filter(str.isalnum, model_name))[:3].upper()
    import random
    rand_id = random.randint(1000, 9999)
    return f"KF-{clean_brand}-{clean_model}-{rand_id}"

# ================= ZAVODLAR & MARKALAR BOSHQARUVI =================

def create_default_factories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM factories")
    count = cursor.fetchone()[0]
    if count == 0:
        default_factories = [
            ("Kerama Marazzi", "Rossiya / Italiya", "Menejer Sergey", "+998 90 123 45 67", "Moskva viloyati", "Sifatli keramika va granit"),
            ("Modena Ceramica", "O'zbekiston", "Abror aka", "+998 97 765 43 21", "Toshkent viloyati", "Mahalliy kafel zavodi"),
            ("Cersanit", "Polsha / Rossiya", "Menejer Aleksey", "+998 91 111 22 33", "Kalyazin zavodi", "Hamyonbop ommabop kafellar"),
            ("Bien Seramik", "Turkiya", "Ahmad Bey", "+90 212 555 12 34", "Istanbul, Turkiya", "Turk elit kafellari"),
            ("Kerasys", "Xitoy", "Menejer Chen", "+998 93 333 44 55", "Foshan, Xitoy", "Katta formatli kafel va granit"),
            ("Samarqand Kafel", "O'zbekiston", "Jamshed aka", "+998 99 888 77 66", "Samarqand shahri", "O'zbekiston kafel ishlab chiqaruvchisi"),
            ("Eron Granit", "Eron", "Rizo afandi", "+998 90 999 88 77", "Isfahon, Eron", "Eron tabiiy tosh va kafellari"),
            ("Azori", "Rossiya", "Menejer Dmitriy", "+998 95 123 44 55", "Sankt-Peterburg", "Vanna va pol kafellari")
        ]
        cursor.executemany("""
            INSERT INTO factories (name, country, contact_person, phone, address, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, default_factories)
        conn.commit()
    conn.close()

def get_all_factories(q=""):
    conn = get_db()
    cursor = conn.cursor()
    if q:
        search_pattern = f"%{q.strip().lower()}%"
        cursor.execute("""
            SELECT f.*, COUNT(p.id) as product_count
            FROM factories f
            LEFT JOIN products p ON LOWER(TRIM(f.name)) = LOWER(TRIM(p.brand))
            WHERE LOWER(f.name) LIKE ? OR LOWER(f.country) LIKE ? OR LOWER(f.contact_person) LIKE ?
            GROUP BY f.id
            ORDER BY f.id DESC
        """, (search_pattern, search_pattern, search_pattern))
    else:
        cursor.execute("""
            SELECT f.*, COUNT(p.id) as product_count
            FROM factories f
            LEFT JOIN products p ON LOWER(TRIM(f.name)) = LOWER(TRIM(p.brand))
            GROUP BY f.id
            ORDER BY f.id DESC
        """)
    factories = cursor.fetchall()
    conn.close()
    return factories

def get_active_factories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM factories WHERE is_active = 1 ORDER BY id DESC")
    factories = cursor.fetchall()
    conn.close()
    return factories

def get_factory_by_id(factory_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM factories WHERE id = ?", (factory_id,))
    factory = cursor.fetchone()
    conn.close()
    return factory

def create_factory(name, country="O'zbekiston", contact_person="", phone="", address="", note=""):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO factories (name, country, contact_person, phone, address, note, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (name.strip(), country.strip() if country else "O'zbekiston", contact_person.strip(), phone.strip(), address.strip(), note.strip()))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return True, new_id, "Zavod muvaffaqiyatli qo'shildi!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, None, f"'{name}' nomli zavod yoki marka allaqachon mavjud!"
    except Exception as e:
        conn.close()
        return False, None, str(e)

def update_factory(factory_id, name, country, contact_person, phone, address, note, is_active=1):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE factories
            SET name = ?, country = ?, contact_person = ?, phone = ?, address = ?, note = ?, is_active = ?
            WHERE id = ?
        """, (name.strip(), country.strip(), contact_person.strip(), phone.strip(), address.strip(), note.strip(), is_active, factory_id))
        conn.commit()
        conn.close()
        return True, "Zavod ma'lumotlari yangilandi!"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"'{name}' nomli boshqa zavod allaqachon mavjud!"
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_factory(factory_id):
    conn = get_db()
    cursor = conn.cursor()
    # Check if products exist for this factory
    cursor.execute("SELECT name FROM factories WHERE id = ?", (factory_id,))
    f_row = cursor.fetchone()
    if not f_row:
        conn.close()
        return False, "Zavod topilmadi!"
    
    f_name = f_row["name"]
    cursor.execute("SELECT COUNT(*) FROM products WHERE LOWER(TRIM(brand)) = LOWER(TRIM(?))", (f_name,))
    prod_count = cursor.fetchone()[0]
    
    if prod_count > 0:
        # Don't hard delete, set inactive to preserve data integrity
        cursor.execute("UPDATE factories SET is_active = 0 WHERE id = ?", (factory_id,))
        conn.commit()
        conn.close()
        return True, f"Ushbu zavodga tegishli {prod_count} ta kafel mavjud bo'lgani uchun holati 'Nofaol' ga o'tkazildi."
    
    cursor.execute("DELETE FROM factories WHERE id = ?", (factory_id,))
    conn.commit()
    conn.close()
    return True, "Zavod o'chirildi!"

# --- USTALAR VA PRORABLAR (TILE MASTERS / CONTRACTORS) ---

def get_active_ustalar(q=None):
    """Barcha faol ustalar va prorablar ro'yxatini qaytaradi"""
    conn = get_db()
    cursor = conn.cursor()
    if q:
        pattern = f"%{q.strip()}%"
        cursor.execute("""
            SELECT id, full_name, phone, customer_type, balance_debt, notes, created_at
            FROM customers
            WHERE customer_type IN ('usta', 'prorab')
              AND (full_name LIKE ? OR phone LIKE ?)
            ORDER BY full_name ASC
        """, (pattern, pattern))
    else:
        cursor.execute("""
            SELECT id, full_name, phone, customer_type, balance_debt, notes, created_at
            FROM customers
            WHERE customer_type IN ('usta', 'prorab')
            ORDER BY full_name ASC
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_usta_by_id(usta_id):
    """Usta ma'lumotlarini ID bo'yicha olish"""
    if not usta_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, full_name, phone, customer_type, balance_debt, notes, created_at
        FROM customers
        WHERE id = ?
    """, (usta_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def create_quick_usta(full_name, phone, notes=None):
    """Kassadan yoki sahifadan tezda yangi usta qo'shish"""
    full_name = full_name.strip()
    phone = (phone or "").strip()
    notes = (notes or "").strip()
    if not full_name:
        return False, None, "Usta ismini kiritish majburiy!"
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO customers (full_name, phone, customer_type, balance_debt, notes)
            VALUES (?, ?, 'usta', 0.0, ?)
        """, (full_name, phone, notes or "Tezkor ro'yxatga olingan usta"))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return True, new_id, f"Usta '{full_name}' muvaffaqiyatli qo'shildi!"
    except Exception as e:
        conn.close()
        return False, None, str(e)

# ----------------- HARAKATLAR VA AMALLAR AUDIT LOGI (ACTION LOGS) -----------------

def log_action(user_name, user_role, action_type, target_type, title, description=None, target_id=None, user_id=None, ip_address=None):
    """
    Qilingan har bir ishni qisqa va lo'nda log sifatida bazaga yozadi.
    action_type: 'kiritdi', 'ochirdi', 'tahrirladi', 'sotdi', 'topshirdi'
    target_type: 'kafel', 'kirim', 'savdo', 'usta', 'xodim', 'zavod', 'siniq', 'xarajat'
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO action_logs (user_id, user_name, user_role, action_type, target_type, target_id, title, description, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_name, user_role, action_type, target_type, target_id, title, description, ip_address))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Log yozish xatoligi: {e}")
        return False

def get_action_logs(limit=200, action_type=None, user_name=None, target_type=None, q=None):
    """Audit loglarini filtrlar va qidiruv bo'yicha olish"""
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM action_logs WHERE 1=1"
    params = []

    if action_type and action_type != "all":
        query += " AND action_type = ?"
        params.append(action_type)

    if user_name and user_name != "all":
        query += " AND user_name = ?"
        params.append(user_name)

    if target_type and target_type != "all":
        query += " AND target_type = ?"
        params.append(target_type)

    if q:
        query += " AND (title LIKE ? OR description LIKE ? OR user_name LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


