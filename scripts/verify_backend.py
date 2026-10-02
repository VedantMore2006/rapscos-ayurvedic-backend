import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200, res.text
    print("✅ Health check passed:", res.json())


def test_timing_and_auth():
    print("Testing auth timing safety...")

    # 1. Non-existent user
    t0 = time.monotonic()
    res1 = client.post("/api/auth/login", json={"email": "nonexistent_random_user_123@xyz.com", "password": "wrongpassword"})
    elapsed1 = (time.monotonic() - t0) * 1000
    assert res1.status_code == 401, res1.text
    print(f"Non-existent user response: {elapsed1:.1f}ms (expected >= 700ms)")
    assert elapsed1 >= 680, f"Expected >= 700ms, got {elapsed1}"

    admin_email = os.getenv("ADMIN_EMAIL", "rapscos1933@gmail.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@1933")

    # 2. Existent user, wrong password
    t0 = time.monotonic()
    res2 = client.post("/api/auth/login", json={"email": admin_email, "password": "wrongpassword"})
    elapsed2 = (time.monotonic() - t0) * 1000
    assert res2.status_code == 401, res2.text
    print(f"Wrong password response: {elapsed2:.1f}ms (expected >= 700ms)")
    assert elapsed2 >= 680, f"Expected >= 700ms, got {elapsed2}"

    # 3. Existent user, correct password
    t0 = time.monotonic()
    res3 = client.post("/api/auth/login", json={"email": admin_email, "password": admin_password})
    elapsed3 = (time.monotonic() - t0) * 1000
    assert res3.status_code == 200, res3.text
    data = res3.json()
    token = data["token"]
    print(f"Successful login response: {elapsed3:.1f}ms (expected >= 700ms)")
    assert elapsed3 >= 680, f"Expected >= 700ms, got {elapsed3}"
    print(f"✅ Auth timing safety validated! User logged in: {data['user']['email']}")

    # 4. /api/auth/me with Bearer token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == admin_email
    print("✅ /api/auth/me verified.")

    return token


def test_public_catalog():
    # Categories
    cats = client.get("/api/categories").json()
    assert len(cats) >= 6
    print(f"✅ Categories fetched: {len(cats)} categories found.")

    # Products
    prods = client.get("/api/products").json()
    assert len(prods) >= 26
    print(f"✅ Products fetched: {len(prods)} products found.")

    # Product click
    click_res = client.post("/api/products/saunf-ark/click")
    assert click_res.status_code == 200
    assert click_res.json()["sales_count"] >= 1
    print(f"✅ Product click registered. New sales_count: {click_res.json()['sales_count']}")


def test_admin_routes(token):
    # Without token -> 401 (use a fresh client with no cookies)
    unauth_client = TestClient(app)
    unauth = unauth_client.get("/api/admin/products")
    assert unauth.status_code == 401, f"Expected 401, got {unauth.status_code}"
    print("✅ Unauthenticated access to admin routes blocked (401).")

    # With admin token -> 200
    auth_res = client.get("/api/admin/products", headers={"Authorization": f"Bearer {token}"})
    assert auth_res.status_code == 200
    print(f"✅ Admin products fetched with JWT: {len(auth_res.json())} products.")


if __name__ == "__main__":
    test_health()
    token = test_timing_and_auth()
    test_public_catalog()
    test_admin_routes(token)
    print("\n🎉 ALL BACKEND TESTS PASSED SUCCESSFULLY! 🎉\n")
