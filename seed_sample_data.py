import os
import sqlite3
from PIL import Image, ImageDraw, ImageFont
import qrcode
import database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
PRODUCTS_DIR = os.path.join(UPLOADS_DIR, "products")
QR_DIR = os.path.join(UPLOADS_DIR, "qrcodes")

os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)

def create_sample_tile_image(filename, brand, model_name, color_bg, color_accent):
    width, height = 600, 600
    img = Image.new("RGB", (width, height), color=color_bg)
    draw = ImageDraw.Draw(img)
    
    # Marbled or geometric tile pattern effect
    for i in range(20, 580, 80):
        draw.line([(i, 0), (i + 40, 600)], fill=color_accent, width=2)
        draw.line([(0, i), (600, i + 40)], fill=color_accent, width=2)
        
    draw.rectangle([15, 15, 585, 585], outline="#334155", width=4)
    
    # Text badge
    draw.rectangle([60, 240, 540, 360], fill="#0f172ae6")
    
    # Draw simple text
    text1 = f"{brand.upper()}"
    text2 = f"{model_name}"
    draw.text((80, 260), text1, fill="#f8fafc")
    draw.text((80, 300), text2, fill="#38bdf8")
    
    filepath = os.path.join(PRODUCTS_DIR, filename)
    img.save(filepath, quality=90)
    return f"/uploads/products/{filename}"

def seed():
    database.init_db()
    conn = database.get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    if count > 0:
        print("Bazada allaqachon kafellar mavjud.")
        conn.close()
        return

    sample_tiles = [
        {
            "sku": "KF-KER-ROY-1001",
            "brand": "Kerasys",
            "model_name": "Royal Calacatta Gold",
            "size": "60x120 sm",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 2,
            "quantity_in_stock": 180.0,
            "min_quantity": 25.0,
            "price": 185000.0,
            "cost_price": 140000.0,
            "bg": "#f8fafc",
            "accent": "#e2e8f0",
            "location_rack": "A-Qator, Tokcha 01",
            "description": "Yaltiroq (глянцевый), oq marmar naqshli premium kafel. Pol va devor uchun mos."
        },
        {
            "sku": "KF-MAR-BLA-1002",
            "brand": "Marazzi",
            "model_name": "Black Sahara Noir",
            "size": "60x60 sm",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 4,
            "quantity_in_stock": 95.0,
            "min_quantity": 20.0,
            "price": 165000.0,
            "cost_price": 125000.0,
            "bg": "#1e293b",
            "accent": "#475569",
            "location_rack": "A-Qator, Tokcha 03",
            "description": "Matviy (матовый), qora oltin tomirli chinni kafel. Zal va oshxonalar uchun."
        },
        {
            "sku": "KF-CER-TRA-1003",
            "brand": "Cersanit",
            "model_name": "Travertino Light Beige",
            "size": "30x60 sm",
            "unit": "m²",
            "box_size_m2": 1.08,
            "pieces_per_box": 6,
            "quantity_in_stock": 310.0,
            "min_quantity": 30.0,
            "price": 135000.0,
            "cost_price": 98000.0,
            "bg": "#fef3c7",
            "accent": "#fde68a",
            "location_rack": "B-Qator, Tokcha 02",
            "description": "Travertin tosh fakturali tabiiy rangli devor kafeli. Vanna va koridorlar uchun."
        },
        {
            "sku": "KF-AZO-CON-1004",
            "brand": "Azori",
            "model_name": "Concrete Grey Loft",
            "size": "60x60 sm",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 4,
            "quantity_in_stock": 8.0, # Kam qolgan ogohlantirishni ko'rsatish uchun
            "min_quantity": 15.0,
            "price": 145000.0,
            "cost_price": 110000.0,
            "bg": "#94a3b8",
            "accent": "#cbd5e1",
            "location_rack": "B-Qator, Tokcha 05",
            "description": "Zamonaviy loft stilidagi beton teksturali baquvvat kafel. Kam qolgan."
        }
    ]

    for tile in sample_tiles:
        img_filename = f"{tile['sku']}.jpg"
        img_url = create_sample_tile_image(img_filename, tile["brand"], tile["model_name"], tile["bg"], tile["accent"])
        
        # QR kod yaratish
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(tile["sku"])
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        qr_filename = f"qr_{tile['sku']}.png"
        qr_filepath = os.path.join(QR_DIR, qr_filename)
        qr_img.save(qr_filepath)
        qr_url = f"/uploads/qrcodes/{qr_filename}"
        
        cursor.execute("""
            INSERT INTO products (
                sku, brand, model_name, size, unit, box_size_m2, pieces_per_box,
                quantity_in_stock, min_quantity, price, cost_price, image_path, qr_code_path,
                location_rack, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tile["sku"], tile["brand"], tile["model_name"], tile["size"], tile["unit"],
            tile["box_size_m2"], tile["pieces_per_box"], tile["quantity_in_stock"],
            tile["min_quantity"], tile["price"], tile["cost_price"], img_url, qr_url,
            tile["location_rack"], tile["description"]
        ))
        
        p_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO stock_history (product_id, change_type, quantity_change, previous_quantity, new_quantity, reference_id, note)
            VALUES (?, 'kirim', ?, 0, ?, 'BOSHLANGICH', ?)
        """, (p_id, tile["quantity_in_stock"], tile["quantity_in_stock"], "Boshlang'ich ombor qoldig'i"))

    conn.commit()
    conn.close()
    print("Namuna kafellar va QR kodlar muvaffaqiyatli yuklandi!")

if __name__ == "__main__":
    seed()
