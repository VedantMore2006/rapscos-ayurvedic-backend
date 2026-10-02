import json
import os
import sys

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Category, Product, User


def seed():
    print("🌱 Starting database seed...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Accounts from data/accounts.json if present
        accounts_path = os.path.join(BACKEND_DIR, "data", "accounts.json")
        if not os.path.exists(accounts_path):
            accounts_path = os.path.join(PROJECT_ROOT, "data", "accounts.json")
        if os.path.exists(accounts_path):
            try:
                with open(accounts_path, "r", encoding="utf-8-sig") as f:
                    acc_data = json.load(f)
                for u in acc_data.get("users", []):
                    u_email = u.get("email", "").strip().lower()
                    if not u_email:
                        continue
                    existing_u = db.query(User).filter(User.email == u_email).first()
                    if not existing_u:
                        salt = u.get("salt", "")
                        hsh = u.get("hash", "")
                        scrypt_pwd = f"scrypt${salt}${hsh}" if salt and hsh else hash_password("Password@1933")
                        new_u = User(
                            email=u_email,
                            hashed_password=scrypt_pwd,
                            name=u.get("name", "User"),
                            phone=u.get("phone", ""),
                            address=u.get("address", ""),
                            role=u.get("role", "customer"),
                        )
                        db.add(new_u)
                        db.commit()
                        print(f"✅ Imported user from accounts.json: {u_email} ({u.get('name')})")
            except Exception as e:
                print(f"Warning: could not seed accounts.json: {e}")

        # Ensure Admin User
        admin_email = os.getenv("ADMIN_EMAIL", "rapscos1933@gmail.com").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin@1933")

        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if not existing_admin:
            print(f"Creating default admin account: {admin_email}...")
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                name="Rapscos Admin",
                phone="+91 86689 84043",
                role="owner",
            )
            db.add(admin_user)
            db.commit()
            print(f"✅ Admin user created. (Default credentials: {admin_email} / {admin_password})")
        else:
            if existing_admin.role != "owner":
                existing_admin.role = "owner"
                db.commit()
            print(f"ℹ️ Admin user '{admin_email}' already exists.")

        # 2. Load content.json
        content_path = os.path.join(BACKEND_DIR, "data", "content.json")
        if not os.path.exists(content_path):
            content_path = os.path.join(PROJECT_ROOT, "src", "data", "content.json")
        if not os.path.exists(content_path):
            print(f"❌ Error: content.json not found in {BACKEND_DIR}/data or {PROJECT_ROOT}/src/data.")
            return

        with open(content_path, "r", encoding="utf-8-sig") as f:
            content = json.load(f)

        featured_ids = set(content.get("featured", []))

        # 3. Seed Categories
        categories_data = content.get("categories", [])
        print(f"Seeding {len(categories_data)} categories...")
        for order, cat_data in enumerate(categories_data):
            cat_key = cat_data["key"].strip().lower()
            cat = db.query(Category).filter(Category.key == cat_key).first()
            if not cat:
                cat = Category(
                    key=cat_key,
                    name=cat_data.get("name", cat_key),
                    img_url=cat_data.get("img", ""),
                    display_order=order,
                    auto_sort_by_sales=False,
                )
                db.add(cat)
            else:
                cat.name = cat_data.get("name", cat.name)
                cat.img_url = cat_data.get("img", cat.img_url)
                cat.display_order = order

        db.commit()
        print("✅ Categories seeded.")

        # 4. Seed Products
        products_data = content.get("products", [])
        print(f"Seeding {len(products_data)} products...")
        for order, p_data in enumerate(products_data):
            p_id = p_data["id"]
            p = db.query(Product).filter(Product.id == p_id).first()
            is_feat = p_id in featured_ids

            benefits_json = json.dumps(p_data.get("benefits", []))
            images_json = json.dumps(p_data.get("images", []))

            if not p:
                p = Product(
                    id=p_id,
                    category_key=p_data.get("cat", "wellness"),
                    name=p_data.get("name", ""),
                    price=float(p_data.get("price", 0)),
                    size=p_data.get("size", ""),
                    badge=p_data.get("badge"),
                    desc=p_data.get("desc", ""),
                    benefits=benefits_json,
                    howto=p_data.get("howto", ""),
                    images=images_json,
                    is_featured=is_feat,
                    display_order=order,
                    sales_count=0,
                )
                db.add(p)
            else:
                p.category_key = p_data.get("cat", p.category_key)
                p.name = p_data.get("name", p.name)
                p.price = float(p_data.get("price", p.price))
                p.size = p_data.get("size", p.size)
                p.badge = p_data.get("badge", p.badge)
                p.desc = p_data.get("desc", p.desc)
                p.benefits = benefits_json
                p.howto = p_data.get("howto", p.howto)
                p.images = images_json
                p.is_featured = is_feat
                p.display_order = order

        db.commit()
        print("✅ Products seeded.")

        total_cats = db.query(Category).count()
        total_prods = db.query(Product).count()
        print(f"🎉 Database ready! Total categories: {total_cats}, Total products: {total_prods}")

    except Exception as e:
        db.rollback()
        print(f"❌ Seeding error: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed()
