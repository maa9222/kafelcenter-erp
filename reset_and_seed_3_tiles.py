import os
import sys
import sqlite3
import shutil
from PIL import Image, ImageDraw, ImageFont
import qrcode
import database

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
PRODUCTS_DIR = os.path.join(UPLOADS_DIR, "products")
QR_DIR = os.path.join(UPLOADS_DIR, "qrcodes")

os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)

def create_rich_tile_image(filename, brand, model_name, size, bg_color, vein_color, badge_accent):
    width, height = 800, 800
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # 1. Luxurious marble/stone/granite vein textures
    for offset in range(30, 780, 70):
        draw.line([(offset, 0), (offset + 120, height)], fill=vein_color, width=3)
        draw.line([(0, offset), (width, offset + 120)], fill=vein_color, width=2)
        # Secondary finer veins
        draw.line([(offset - 40, 0), (offset + 60, height)], fill=vein_color, width=1)
        draw.line([(0, offset - 40), (width, offset + 60)], fill=vein_color, width=1)

    # Outer border simulating bevel / edge
    draw.rectangle([10, 10, width - 10, height - 10], outline="#475569", width=6)
    draw.rectangle([20, 20, width - 20, height - 20], outline="#94a3b8", width=2)

    # Center floating label card with dark glassmorphic effect
    card_x0, card_y0 = 80, 280
    card_x1, card_y1 = 720, 520
    draw.rectangle([card_x0, card_y0, card_x1, card_y1], fill="#0f172af0", outline="#38bdf8", width=3)

    # Brand, Model and Size labels
    draw.text((120, 310), f"PREMIUM CERAMICS", fill=badge_accent)
    draw.text((120, 345), f"{brand.upper()}", fill="#ffffff")
    draw.text((120, 395), f"{model_name}", fill="#e2e8f0")
    draw.text((120, 445), f"O'lcham: {size}  |  1-Nav (Grade A)", fill="#94a3b8")

    filepath = os.path.join(PRODUCTS_DIR, filename)
    img.save(filepath, quality=92)
    return f"/uploads/products/{filename}"

def reset_and_seed():
    database.init_db()
    conn = database.get_db()
    cursor = conn.cursor()

    print("1. Ombordagi eski ma'lumotlar tozalanmoqda...")
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM stock_history")
    cursor.execute("DELETE FROM products")
    conn.commit()

    # Clear old uploaded files
    for folder in [PRODUCTS_DIR, QR_DIR]:
        for f in os.listdir(folder):
            fp = os.path.join(folder, f)
            if os.path.isfile(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass

    print("2. 3 ta har xil markadagi yangi kafellar kiritilmoqda...")

    tiles = [
        {
            "sku": "KF-KER-CAL-2001",
            "brand": "Kerama Marazzi",
            "model_name": "Pro Walk Calacatta Royal",
            "size": "60x120 sm",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 2,
            "quantity_in_stock": 240.0,
            "min_quantity": 30.0,
            "price": 195000.0,
            "cost_price": 145000.0,
            "location_rack": "A-Qator, Tokcha 01",
            "description": "Oliy toifali oq marmar teksturali yaltiroq (глянцевый) kafel. Pol va devor uchun.",
            "bg": "#f8fafc",
            "vein": "#e2e8f0",
            "accent": "#38bdf8"
        },
        {
            "sku": "KF-MOD-ANT-2002",
            "brand": "Modena Ceramica",
            "model_name": "Titanium Dark Anthracite",
            "size": "60x60 sm",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 4,
            "quantity_in_stock": 180.0,
            "min_quantity": 25.0,
            "price": 168000.0,
            "cost_price": 120000.0,
            "location_rack": "B-Qator, Tokcha 03",
            "description": "Matviy granit, zamonaviy quyuq kulrang (antratsit) fakturali, tirnalishga juda chidamli.",
            "bg": "#1e293b",
            "vein": "#334155",
            "accent": "#f59e0b"
        },
        {
            "sku": "KF-BIE-ONY-2003",
            "brand": "Bien Seramik",
            "model_name": "Onyx Amber Gold",
            "size": "80x80 sm",
            "unit": "m²",
            "box_size_m2": 1.92,
            "pieces_per_box": 3,
            "quantity_in_stock": 115.2,
            "min_quantity": 20.0,
            "price": 220000.0,
            "cost_price": 165000.0,
            "location_rack": "C-Qator, Tokcha 02",
            "description": "Tabiiy yarim-shaffof Oniks tosh effektli, oltin tomirli premium keramik plitka.",
            "bg": "#fef3c7",
            "vein": "#fde68a",
            "accent": "#10b981"
        }
    ]

    for t in tiles:
        # Create image
        img_fn = f"{t['sku']}.jpg"
        img_url = create_rich_tile_image(img_fn, t["brand"], t["model_name"], t["size"], t["bg"], t["vein"], t["accent"])

        # Create QR Code
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(t["sku"])
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        qr_fn = f"qr_{t['sku']}.png"
        qr_fp = os.path.join(QR_DIR, qr_fn)
        qr_img.save(qr_fp)
        qr_url = f"/uploads/qrcodes/{qr_fn}"

        cursor.execute("""
            INSERT INTO products (
                sku, brand, model_name, size, unit, box_size_m2, pieces_per_box,
                quantity_in_stock, min_quantity, price, cost_price, image_path, qr_code_path,
                location_rack, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t["sku"], t["brand"], t["model_name"], t["size"], t["unit"],
            t["box_size_m2"], t["pieces_per_box"], t["quantity_in_stock"],
            t["min_quantity"], t["price"], t["cost_price"], img_url, qr_url,
            t["location_rack"], t["description"]
        ))
        prod_id = cursor.lastrowid

        # Initial stock history entry
        cursor.execute("""
            INSERT INTO stock_history (product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, note)
            VALUES (?, 'kirim', ?, 0, ?, 'BOSHLANGICH', 'Omborga birinchi marta kiritildi')
        """, (prod_id, t["quantity_in_stock"], t["quantity_in_stock"]))

        print(f" -> Qo'shildi: [{t['brand']}] {t['model_name']} ({t['size']}) - Qoldiq: {t['quantity_in_stock']} m2")

    conn.commit()

    # Check products count
    cursor.execute("SELECT COUNT(*) FROM products")
    total_p = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_u = cursor.fetchone()[0]
    conn.close()

    print(f"\nTayyor! Omborda jami: {total_p} ta kafel. Foydalanuvchilar soni: {total_u} ta.")

if __name__ == "__main__":
    reset_and_seed()
