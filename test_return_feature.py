import os
import shutil
import json
import unittest
from datetime import datetime, timedelta

# Use isolated test DB
TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_kafel_return.db')
PROD_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kafel_database.db')
os.environ["DB_FILE"] = TEST_DB

if os.path.exists(PROD_DB):
    shutil.copy2(PROD_DB, TEST_DB)

import app
import database

class TestKafelReturnAndExchange(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        for ext in ['', '-wal', '-shm']:
            f = TEST_DB + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def setUp(self):
        self.client = app.app.test_client()
        app.app.config["TESTING"] = True
        app.reset_all_rate_limits()
        database.init_db()

    def test_return_reminder_on_sales_receipt_and_nakladnoy(self):
        # 1. Login as admin
        self.client.post("/login", data={"username": "admin", "password": "admin123"})

        # Get a product
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, brand, model_name, price, quantity_in_stock FROM products WHERE quantity_in_stock > 10 LIMIT 1")
        prod = cursor.fetchone()
        conn.close()

        # Checkout sale
        res = self.client.post("/api/checkout", json={
            "customer_name": "Test Xaridor Chek",
            "customer_phone": "+998 90 111 22 33",
            "payment_method": "naqd",
            "items": [{"id": prod["id"], "qty": 5.0, "price": prod["price"]}]
        })
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        order_id = data["order_id"]

        # View 80mm check
        r_chek = self.client.get(f"/nakladnoy/{order_id}/chek")
        self.assertEqual(r_chek.status_code, 200)
        self.assertIn("20 kun ichida", r_chek.data.decode("utf-8"))
        self.assertIn("qaytarishingiz", r_chek.data.decode("utf-8"))

        # View A4 Nakladnoy
        r_nak = self.client.get(f"/nakladnoy/{order_id}/print")
        self.assertEqual(r_nak.status_code, 200)
        self.assertIn("20 kun", r_nak.data.decode("utf-8"))
        self.assertIn("Qaytarish va Almashtirish", r_nak.data.decode("utf-8"))

    def test_return_tile_returns_to_warehouse_stock(self):
        # 1. Login as admin
        self.client.post("/login", data={"username": "admin", "password": "admin123"})

        # 2. Get product
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, brand, model_name, price, quantity_in_stock FROM products WHERE quantity_in_stock >= 20 LIMIT 1")
        prod = cursor.fetchone()
        p_id = prod["id"]
        initial_stock = float(prod["quantity_in_stock"])
        conn.close()

        # 3. Sell 10 m²
        res = self.client.post("/api/checkout", json={
            "customer_name": "Akmal Return Test",
            "customer_phone": "+998 90 999 88 77",
            "payment_method": "naqd",
            "items": [{"id": p_id, "qty": 10.0, "price": prod["price"]}]
        })
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        order_id = data["order_id"]

        # Stock should be initial_stock - 10
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity_in_stock FROM products WHERE id = ?", (p_id,))
        stock_after_sale = float(cursor.fetchone()[0])
        self.assertEqual(stock_after_sale, initial_stock - 10.0)

        # Get order item id
        cursor.execute("SELECT id FROM order_items WHERE order_id = ?", (order_id,))
        oi_id = cursor.fetchone()[0]
        conn.close()

        # 4. Check order API
        r_check = self.client.get(f"/api/return/check-order?order_id={order_id}")
        check_data = json.loads(r_check.data)
        self.assertTrue(check_data["success"])
        self.assertTrue(check_data["order"]["is_within_20_days"])
        self.assertEqual(check_data["order"]["days_passed"], 0)

        # 5. Return 4 m² of the tile to warehouse (no exchange items)
        r_proc = self.client.post("/api/return/process", json={
            "order_id": order_id,
            "returned_items": [{"order_item_id": oi_id, "qty": 4.0}],
            "exchange_items": [],
            "reason": "Usta 4 m2 kafel ortib qolganini aytdi, chek bilan qaytarildi",
            "payment_method": "naqd"
        })
        proc_data = json.loads(r_proc.data)
        self.assertTrue(proc_data["success"])
        return_id = proc_data["return_id"]

        # 6. VERIFY: Stock in warehouse increased by 4 m²!
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity_in_stock FROM products WHERE id = ?", (p_id,))
        stock_after_return = float(cursor.fetchone()[0])
        self.assertEqual(stock_after_return, stock_after_sale + 4.0)

        # Verify stock_history has 'qaytarish' record
        cursor.execute("""
            SELECT * FROM stock_history 
            WHERE product_id = ? AND change_type = 'qaytarish' 
            ORDER BY id DESC LIMIT 1
        """, (p_id,))
        sh = cursor.fetchone()
        self.assertIsNotNone(sh)
        self.assertEqual(float(sh["quantity_change"]), 4.0)
        self.assertIn("Kafel omborga qaytarildi", sh["note"])

        # Verify order_items returned_quantity
        cursor.execute("SELECT returned_quantity FROM order_items WHERE id = ?", (oi_id,))
        ret_q = float(cursor.fetchone()[0])
        self.assertEqual(ret_q, 4.0)

        # Verify returns table record
        cursor.execute("SELECT * FROM returns WHERE id = ?", (return_id,))
        ret_row = cursor.fetchone()
        self.assertIsNotNone(ret_row)
        self.assertEqual(float(ret_row["return_amount"]), 4.0 * float(prod["price"]))
        self.assertEqual(float(ret_row["exchange_amount"]), 0.0)
        self.assertEqual(float(ret_row["difference_amount"]), -(4.0 * float(prod["price"])))
        conn.close()

        # 7. Verify return receipt print
        r_rec = self.client.get(f"/qaytarish/{return_id}/chek")
        self.assertEqual(r_rec.status_code, 200)
        self.assertIn("QAYTARISH VA ALMASHTIRISH CHEKI", r_rec.data.decode("utf-8"))

    def test_return_and_exchange_for_other_tile(self):
        # 1. Login as admin
        self.client.post("/login", data={"username": "admin", "password": "admin123"})

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, brand, model_name, price, quantity_in_stock FROM products WHERE quantity_in_stock >= 10 ORDER BY id ASC LIMIT 2")
        products = cursor.fetchall()
        self.assertGreaterEqual(len(products), 2)
        p1 = products[0]
        p2 = products[1]
        p1_stock_initial = float(p1["quantity_in_stock"])
        p2_stock_initial = float(p2["quantity_in_stock"])
        conn.close()

        # Sell 6 m² of p1
        res = self.client.post("/api/checkout", json={
            "customer_name": "Exchange Test Customer",
            "customer_phone": "+998 90 777 66 55",
            "payment_method": "naqd",
            "items": [{"id": p1["id"], "qty": 6.0, "price": p1["price"]}]
        })
        order_id = json.loads(res.data)["order_id"]

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM order_items WHERE order_id = ?", (order_id,))
        oi_id = cursor.fetchone()[0]
        conn.close()

        # Return 6 m² of p1 and take 4 m² of p2 in exchange
        r_exch = self.client.post("/api/return/process", json={
            "order_id": order_id,
            "returned_items": [{"order_item_id": oi_id, "qty": 6.0}],
            "exchange_items": [{"product_id": p2["id"], "qty": 4.0, "price": p2["price"]}],
            "reason": "Boshqa dizayndagi kafelga almashtirdi",
            "payment_method": "naqd"
        })
        data = json.loads(r_exch.data)
        self.assertTrue(data["success"])
        return_id = data["return_id"]

        # VERIFY: p1 stock returned to warehouse! (Initial stock was decreased by 6 on sale, now increased back by 6)
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity_in_stock FROM products WHERE id = ?", (p1["id"],))
        p1_stock_final = float(cursor.fetchone()[0])
        self.assertEqual(p1_stock_final, p1_stock_initial)

        # VERIFY: p2 stock decreased by 4 (taken by customer)
        cursor.execute("SELECT quantity_in_stock FROM products WHERE id = ?", (p2["id"],))
        p2_stock_final = float(cursor.fetchone()[0])
        self.assertEqual(p2_stock_final, p2_stock_initial - 4.0)

        # Verify return items records
        cursor.execute("SELECT * FROM return_items WHERE return_id = ?", (return_id,))
        items = cursor.fetchall()
        self.assertEqual(len(items), 2)
        conn.close()

    def test_20_days_limit_enforcement(self):
        # 1. Login as sotuvchi (non-admin)
        self.client.post("/login", data={"username": "sotuvchi", "password": "sotuvchi123"})

        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, price FROM products LIMIT 1")
        prod = cursor.fetchone()
        conn.close()

        # Checkout sale
        res = self.client.post("/api/checkout", json={
            "customer_name": "Old Order Customer",
            "payment_method": "naqd",
            "items": [{"id": prod["id"], "qty": 2.0, "price": prod["price"]}]
        })
        order_id = json.loads(res.data)["order_id"]

        # Artificially set order date to 25 days ago (older than 20 days)
        old_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d %H:%M:%S")
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET created_at = ? WHERE id = ?", (old_date, order_id))
        cursor.execute("SELECT id FROM order_items WHERE order_id = ?", (order_id,))
        oi_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        # Check API response indicates > 20 days
        r_check = self.client.get(f"/api/return/check-order?order_id={order_id}")
        check_data = json.loads(r_check.data)
        self.assertFalse(check_data["order"]["is_within_20_days"])
        self.assertGreaterEqual(check_data["order"]["days_passed"], 25)

        # Sotuvchi tries to return after 20 days -> Should be blocked!
        r_proc = self.client.post("/api/return/process", json={
            "order_id": order_id,
            "returned_items": [{"order_item_id": oi_id, "qty": 1.0}],
            "exchange_items": [],
            "reason": "Eski chek"
        })
        proc_data = json.loads(r_proc.data)
        self.assertFalse(proc_data["success"])
        self.assertIn("20 kunlik qaytarish muddati tugagan", proc_data["message"])

if __name__ == "__main__":
    unittest.main()
