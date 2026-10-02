import json
import os
import sys
import time
import uuid
import httpx

API_BASE = "http://127.0.0.1:8000"
FRONTEND_BASE = "http://localhost:5173"

report = []

def log(section, status, detail=""):
    symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "ℹ️"
    msg = f"{symbol} [{section}] {detail}"
    print(msg)
    report.append({"section": section, "status": status, "detail": detail})

def run_tests():
    print("=" * 60)
    print("🚀 STARTING FULL END-TO-END AUTOMATED VERIFICATION SUITE")
    print(f"Backend:  {API_BASE}")
    print(f"Frontend: {FRONTEND_BASE}")
    print("=" * 60)

    # 1. Health & Server connectivity
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5.0)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("status") == "healthy"
        log("Health Check", "PASS", f"FastAPI is healthy: {data}")
    except Exception as e:
        log("Health Check", "FAIL", str(e))

    # 2. Frontend Connectivity
    try:
        r = httpx.get(FRONTEND_BASE, timeout=5.0)
        assert r.status_code == 200
        assert "<title" in r.text.lower()
        log("Frontend Server", "PASS", "Vite dev server is serving 200 OK")
    except Exception as e:
        log("Frontend Server", "FAIL", str(e))

    # 3. Timing-Safe Response Floor (700ms constant time)
    try:
        durations = []
        for i, (email, pwd) in enumerate([
            ("random_nonexistent_123@domain.com", "pass12345"),
            ("rapscos1933@gmail.com", "WrongPassword123!"),
            ("rapscos1933@gmail.com", "Admin@1933"),
        ]):
            t0 = time.monotonic()
            resp = httpx.post(f"{API_BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=10.0)
            elapsed = (time.monotonic() - t0) * 1000
            durations.append(elapsed)
            assert elapsed >= 680, f"Call {i} took {elapsed:.1f}ms, expected >= 700ms"

        diff = max(durations) - min(durations)
        log("Timing Attack Defense", "PASS", 
            f"All login responses held to >=700ms floor: {durations[0]:.1f}ms, {durations[1]:.1f}ms, {durations[2]:.1f}ms (jitter: {diff:.1f}ms)")
    except Exception as e:
        log("Timing Attack Defense", "FAIL", str(e))

    # 4. CORS Whitelist Validation
    try:
        # Allowed origin
        r_allowed = httpx.options(
            f"{API_BASE}/api/products",
            headers={"Origin": "https://www.rapscosbio.com", "Access-Control-Request-Method": "GET"}
        )
        assert r_allowed.headers.get("access-control-allow-origin") == "https://www.rapscosbio.com"

        # Disallowed origin
        r_disallowed = httpx.options(
            f"{API_BASE}/api/products",
            headers={"Origin": "https://malicious-phishing-site.com", "Access-Control-Request-Method": "GET"}
        )
        assert r_disallowed.headers.get("access-control-allow-origin") != "https://malicious-phishing-site.com"
        log("CORS Security", "PASS", "Allowed origins accepted; external/unauthorized origins blocked")
    except Exception as e:
        log("CORS Security", "FAIL", str(e))

    # 5. Customer Lifecycle: Signup -> Get Me -> Update Account -> Change Password -> Login
    customer_email = f"customer_{uuid.uuid4().hex[:6]}@example.com"
    customer_pwd = "CustomerSecure@123"
    customer_token = ""
    try:
        # Signup
        r = httpx.post(f"{API_BASE}/api/auth/signup", json={
            "name": "E2E Test Customer",
            "email": customer_email,
            "phone": "+91 98765 43210",
            "password": customer_pwd
        }, timeout=10.0)
        assert r.status_code == 200, f"Signup failed: {r.text}"
        signup_data = r.json()
        customer_token = signup_data["token"]
        assert signup_data["user"]["role"] == "customer"
        log("Customer Signup", "PASS", f"Created customer account: {customer_email}")

        # Auth Me
        r_me = httpx.get(f"{API_BASE}/api/auth/me", headers={"Authorization": f"Bearer {customer_token}"})
        assert r_me.status_code == 200
        assert r_me.json()["user"]["email"] == customer_email
        log("Customer Auth Check", "PASS", "Decoded JWT via /api/auth/me")

        # Update Account (address for WhatsApp prefill)
        r_acc = httpx.put(f"{API_BASE}/api/account", headers={"Authorization": f"Bearer {customer_token}"}, json={
            "name": "E2E Test Customer Updated",
            "address": "123 Ayurvedic Way, Nashik, Maharashtra 422010"
        })
        assert r_acc.status_code == 200
        assert r_acc.json()["user"]["address"] == "123 Ayurvedic Way, Nashik, Maharashtra 422010"
        log("Customer Profile Update", "PASS", "Saved customer delivery address")

        # Change Password
        new_pwd = "NewSecurePassword456!"
        r_pwd = httpx.post(f"{API_BASE}/api/auth/password", headers={"Authorization": f"Bearer {customer_token}"}, json={
            "current_password": customer_pwd,
            "new_password": new_pwd
        })
        assert r_pwd.status_code == 200
        log("Password Change", "PASS", "Timing-safe password update successful")

        # Verify new password login
        r_login_new = httpx.post(f"{API_BASE}/api/auth/login", json={
            "email": customer_email,
            "password": new_pwd
        })
        assert r_login_new.status_code == 200
        log("Re-login with New Password", "PASS", "Successfully logged in with updated credentials")
    except Exception as e:
        log("Customer Lifecycle", "FAIL", str(e))

    # 6. Admin Authentication & Role Protection
    admin_token = ""
    try:
        r_admin_login = httpx.post(f"{API_BASE}/api/auth/login", json={
            "email": "rapscos1933@gmail.com",
            "password": "Admin@1933"
        })
        assert r_admin_login.status_code == 200
        admin_data = r_admin_login.json()
        admin_token = admin_data["token"]
        assert admin_data["user"]["role"] in ("owner", "admin")
        log("Admin Authentication", "PASS", f"Admin authenticated: role={admin_data['user']['role']}")

        # Customer trying to access admin endpoint -> 403 Forbidden
        r_forbidden = httpx.get(f"{API_BASE}/api/admin/products", headers={"Authorization": f"Bearer {customer_token}"})
        assert r_forbidden.status_code == 403, f"Expected 403, got {r_forbidden.status_code}"
        log("Admin Guard Protection", "PASS", "Customer token correctly blocked from admin endpoints (403 Forbidden)")
    except Exception as e:
        log("Admin Authentication", "FAIL", str(e))

    # 7. Products & Categories End-to-End Dynamic Sync Test
    test_prod_id = f"test-herb-{uuid.uuid4().hex[:4]}"
    try:
        # A. Public catalog read
        r_cats = httpx.get(f"{API_BASE}/api/categories")
        assert r_cats.status_code == 200
        cats = r_cats.json()
        assert len(cats) >= 6
        target_cat = cats[0]["key"]

        r_prods_before = httpx.get(f"{API_BASE}/api/products")
        initial_prod_count = len(r_prods_before.json())

        # B. Admin creates product
        new_prod_payload = {
            "id": test_prod_id,
            "cat": target_cat,
            "name": f"E2E Test Formulation ({test_prod_id})",
            "price": 249.0,
            "size": "100 ml",
            "badge": "New Arrival",
            "desc": "Fresh herbal extract created during automated end-to-end testing.",
            "benefits": ["Immunity support", "Quick digestion relief", "Clinically tested"],
            "howto": "Take 10ml with warm water twice daily.",
            "images": ["/images/saunf-ark.webp"],
            "is_featured": True,
            "display_order": 0
        }

        r_create = httpx.post(
            f"{API_BASE}/api/admin/products",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=new_prod_payload
        )
        assert r_create.status_code == 201, f"Create failed: {r_create.text}"
        log("Product Creation", "PASS", f"Admin created product: {test_prod_id}")

        # C. Verify product is immediately available in public API
        r_check = httpx.get(f"{API_BASE}/api/products/{test_prod_id}")
        assert r_check.status_code == 200
        check_data = r_check.json()
        assert check_data["name"] == new_prod_payload["name"]
        assert check_data["price"] == 249.0
        log("Immediate Public Availability", "PASS", f"Product {test_prod_id} is live and queryable on public API")

        # D. Click Tracking / Sales Increment Test
        r_click = httpx.post(f"{API_BASE}/api/products/{test_prod_id}/click")
        assert r_click.status_code == 200
        assert r_click.json()["sales_count"] == 1
        # Click again to simulate checkout
        httpx.post(f"{API_BASE}/api/products/{test_prod_id}/click")
        r_click2 = httpx.get(f"{API_BASE}/api/products/{test_prod_id}")
        assert r_click2.json()["sales_count"] == 2
        log("WhatsApp Click Tracker", "PASS", f"Sales counter incremented to 2 for {test_prod_id}")

        # E. Top-Selling Sorting Logic Test
        # Enable auto_sort_by_sales on the category
        r_cat_update = httpx.put(
            f"{API_BASE}/api/admin/categories/{target_cat}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"auto_sort_by_sales": True}
        )
        assert r_cat_update.status_code == 200
        assert r_cat_update.json()["auto_sort_by_sales"] is True

        # Query products in this category; test_prod_id should be top or prioritized by sales
        r_sorted = httpx.get(f"{API_BASE}/api/products?cat={target_cat}")
        cat_products = r_sorted.json()
        assert len(cat_products) > 0
        top_sales = cat_products[0]["sales_count"]
        for p in cat_products[1:]:
            assert p["sales_count"] <= top_sales
        log("Bestseller Auto-Sorting", "PASS", f"Category '{target_cat}' sorted by sales_count descending")

        # F. Image Upload Test
        image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("test_upload.png", image_bytes, "image/png")}
        r_img = httpx.post(
            f"{API_BASE}/api/admin/images",
            headers={"Authorization": f"Bearer {admin_token}"},
            files=files
        )
        assert r_img.status_code == 201
        uploaded_url = r_img.json()["url"]
        log("Admin Image Upload", "PASS", f"Uploaded image saved to: {uploaded_url}")

        # Verify image is publicly reachable
        r_img_check = httpx.get(f"{API_BASE}{uploaded_url}")
        assert r_img_check.status_code == 200
        log("Media Delivery", "PASS", "Uploaded image served with 200 OK from media storage")

        # G. Admin Clean-Up (Delete test product and test image)
        r_del_prod = httpx.delete(
            f"{API_BASE}/api/admin/products/{test_prod_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r_del_prod.status_code == 200

        r_del_img = httpx.delete(
            f"{API_BASE}/api/admin/images?path={uploaded_url}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r_del_img.status_code == 200
        log("Admin Clean-Up", "PASS", "Deleted temporary test product and test media file")

        # Reset category auto_sort_by_sales
        httpx.put(
            f"{API_BASE}/api/admin/categories/{target_cat}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"auto_sort_by_sales": False}
        )

    except Exception as e:
        log("Catalog Lifecycle", "FAIL", str(e))

    print("=" * 60)
    passed = sum(1 for r in report if r["status"] == "PASS")
    failed = sum(1 for r in report if r["status"] == "FAIL")
    print(f"📊 SUMMARY: {passed} PASSED, {failed} FAILED across {len(report)} tests")
    print("=" * 60)

    # Save artifact report
    report_path = "/home/vedant/.gemini/antigravity-ide/brain/7bac2077-6150-4d2e-a9b4-dad14680d1a7/e2e_test_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_tests()
