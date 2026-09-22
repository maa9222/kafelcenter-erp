import os
import sys
import shutil
import qrcode
import database

if sys.stdout:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    products_dir = os.path.join(uploads_dir, "products")
    qrcodes_dir = os.path.join(uploads_dir, "qrcodes")

    os.makedirs(products_dir, exist_ok=True)
    os.makedirs(qrcodes_dir, exist_ok=True)

    # 1. Copy generated images
    brain_dir = r"C:\Users\MAA9222\.gemini\antigravity\brain\4b1460b8-70d6-4665-8b01-0cad2e48370d"
    
    img_map = {
        "calacatta_gold.jpg": os.path.join(brain_dir, "tile_calacatta_gold_1789469021655.jpg"),
        "nero_marquina.jpg": os.path.join(brain_dir, "tile_nero_marquina_1789469089803.jpg"),
        "emerald_onyx.jpg": os.path.join(brain_dir, "tile_emerald_onyx_1789469153844.jpg"),
        "travertino_romano.jpg": os.path.join(brain_dir, "tile_travertino_beige_1789469200769.jpg"),
    }

    for target_name, src_path in img_map.items():
        if os.path.exists(src_path):
            dst = os.path.join(products_dir, target_name)
            shutil.copy2(src_path, dst)
            print(f"Copied {target_name}")
        else:
            print(f"Warning: {src_path} not found")

    # 2. Helper to generate QR image
    def make_qr(sku):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(sku)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        qr_file = os.path.join(qrcodes_dir, f"qr_{sku}.png")
        img.save(qr_file)
        return f"/uploads/qrcodes/qr_{sku}.png"

    # 3. Clean DB tables
    conn = database.get_db()
    c = conn.cursor()

    print("Cleaning nakladnoys, broken tiles, products and stock history...")
    c.execute("DELETE FROM order_items")
    c.execute("DELETE FROM orders")
    c.execute("DELETE FROM broken_tiles")
    c.execute("DELETE FROM stock_history")
    c.execute("DELETE FROM products")
    c.execute("UPDATE customers SET balance_debt = 0.0")

    # 4. Insert 4 new ceramic tile models
    tiles = [
        {
            "sku": "KF-KER-CAL-0101",
            "brand": "Kerama Marazzi",
            "model_name": "Calacatta Gold Royal",
            "size": "60x120",
            "quantity_in_stock": 250.0,
            "min_quantity": 25.0,
            "price": 240000.0,
            "cost_price": 170000.0,
            "image_path": "/uploads/products/calacatta_gold.jpg",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 2,
            "location_rack": "A-01",
            "description": "Premium oq marmar teksturali chinni kafel (Italiya/Rossiya). Oltin va kulrang tomirlar, yaltiroq silliq sirt. Showroom va xonadonlar uchun eng talabgir model."
        },
        {
            "sku": "KF-MOD-NER-0102",
            "brand": "Modena Ceramica",
            "model_name": "Nero Marquina Lux",
            "size": "60x60",
            "quantity_in_stock": 180.0,
            "min_quantity": 20.0,
            "price": 195000.0,
            "cost_price": 140000.0,
            "image_path": "/uploads/products/nero_marquina.jpg",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 4,
            "location_rack": "B-04",
            "description": "To'q qora marmar foni va nozik oq chaqmoqsimon tomirli kafel. Mehmonxona, zal va oshxona pollari uchun hashamatli dizayn."
        },
        {
            "sku": "KF-BIE-ONY-0103",
            "brand": "Bien Seramik",
            "model_name": "Emerald Jade Onyx",
            "size": "60x120",
            "quantity_in_stock": 120.0,
            "min_quantity": 15.0,
            "price": 290000.0,
            "cost_price": 210000.0,
            "image_path": "/uploads/products/emerald_onyx.jpg",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 2,
            "location_rack": "C-02",
            "description": "Noyob zumrad yashil oniks toshi ko'rinishi, kristall shaffof jiloli sirt va iliq asal tomirlari. Vanna va showroom vitrinalari uchun."
        },
        {
            "sku": "KF-VIT-TRA-0104",
            "brand": "Vitra Ceramic",
            "model_name": "Travertino Romano Beige",
            "size": "30x60",
            "quantity_in_stock": 320.0,
            "min_quantity": 30.0,
            "price": 165000.0,
            "cost_price": 115000.0,
            "image_path": "/uploads/products/travertino_romano.jpg",
            "unit": "m²",
            "box_size_m2": 1.44,
            "pieces_per_box": 8,
            "location_rack": "D-01",
            "description": "Klassik tabiiy bej travertin tosh teksturasi, sirpanmaydigan silliq mat sirt. Devorlar, yo'laklar va hovli terasasi uchun juda mos."
        }
    ]

    for t in tiles:
        qr_path = make_qr(t["sku"])
        c.execute("""
            INSERT INTO products (
                sku, brand, model_name, size,
                quantity_in_stock, min_quantity, price, cost_price,
                image_path, qr_code_path, unit, box_size_m2, pieces_per_box,
                location_rack, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t["sku"], t["brand"], t["model_name"], t["size"],
            t["quantity_in_stock"], t["min_quantity"], t["price"], t["cost_price"],
            t["image_path"], qr_path, t["unit"], t["box_size_m2"], t["pieces_per_box"],
            t["location_rack"], t["description"]
        ))
        prod_id = c.lastrowid
        
        # Kirim tarixi
        c.execute("""
            INSERT INTO stock_history (
                product_id, change_type, quantity_change, previous_quantity, new_quantity,
                reference_id, user_name, note
            ) VALUES (?, 'kirim', ?, 0, ?, 'YANGI-OMBOR-BOSH', 'Bosh Admin', ?)
        """, (
            prod_id, t["quantity_in_stock"], t["quantity_in_stock"],
            f"Birlamchi yangi ombor zaxirasini kiritish: {t['brand']} {t['model_name']} ({t['quantity_in_stock']} m²)"
        ))
        print(f"Added product: {t['brand']} - {t['model_name']} (Stock: {t['quantity_in_stock']} {t['unit']})")

    conn.commit()
    conn.close()
    print("Warehouse cleaned and 4 new tiles successfully seeded!")

if __name__ == "__main__":
    main()
