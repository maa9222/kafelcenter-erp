import sys
import database

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

conn = database.get_db()
cur = conn.cursor()

# 1. Mahsulotlar bo'yicha qoldiq
cur.execute("SELECT id, sku, brand, model_name, size, box_size_m2, quantity_in_stock, price FROM products")
prods = cur.fetchall()

# 2. Sotuvlar bo'yicha ma'lumot
cur.execute("""
    SELECT oi.product_id, SUM(oi.quantity) as sold_qty, SUM(oi.total_price) as sold_sum
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status != 'bekor_qilindi'
    GROUP BY oi.product_id
""")
sales = {r["product_id"]: (r["sold_qty"], r["sold_sum"]) for r in cur.fetchall()}

# 3. Jami umumiy ko'rsatkichlar
cur.execute("""
    SELECT COALESCE(SUM(oi.quantity), 0) as total_sold_qty, COALESCE(SUM(oi.total_price), 0) as total_sold_sum
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status != 'bekor_qilindi'
""")
total_sales = cur.fetchone()

cur.execute("SELECT COALESCE(SUM(quantity_in_stock), 0) as total_stock FROM products")
total_stock = cur.fetchone()["total_stock"]

print("="*65)
print("             KAFELCENTER: OMBOR VA SAVDO HISOBOTI")
print("="*65)

total_initial = 0.0
for p in prods:
    sold_qty, sold_sum = sales.get(p["id"], (0.0, 0.0))
    rem_qty = p["quantity_in_stock"]
    init_qty = rem_qty + sold_qty
    total_initial += init_qty
    box_size = p["box_size_m2"] or 1.44
    rem_boxes = rem_qty / box_size if box_size else 0

    print(f"\n[ID: {p['id']}] {p['brand']} - {p['model_name']} ({p['size']}):")
    print(f"  * Boshlang'ich kirim: {init_qty:.2f} m2")
    print(f"  * Sotildi (ombordan chiqdi): {sold_qty:.2f} m2  ({sold_sum:,.0f} so'm)")
    print(f"  * Omborda qoldi: {rem_qty:.2f} m2  (~{rem_boxes:.1f} quti)")

print("\n" + "="*65)
print("UMUMIY JAMI KO'RSATKICHLAR:")
print("="*65)
print(f"  * JAMI OMBORGA KIRGAN EDI:  {total_initial:.2f} m2")
print(f"  * JAMI SOTILDI VA CHIQARILDI: {total_sales['total_sold_qty']:.2f} m2  (Tushum: {total_sales['total_sold_sum']:,.0f} so'm)")
print(f"  * JAMI OMBORDA QOLDI:         {total_stock:.2f} m2")
print("="*65)

# Also check orders status
cur.execute("SELECT order_number, customer_name, total_amount, status, created_at FROM orders")
orders = cur.fetchall()
print("\nBUYURTMALAR VA NAKLADNOYLAR HOLATI:")
for o in orders:
    print(f"  - {o['order_number']}: {o['customer_name']} | {o['total_amount']:,.0f} so'm | Status: {o['status']} | Sana: {o['created_at']}")

conn.close()
