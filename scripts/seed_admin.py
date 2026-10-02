import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User


def seed_admin(email: str, password: str, name: str = "Rapscos Admin", role: str = "owner"):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    clean_email = email.strip().lower()
    clean_name = name.strip()

    try:
        user = db.query(User).filter(User.email == clean_email).first()
        hashed = hash_password(password)

        if user:
            print(f"🔄 Updating existing admin user: {clean_email}")
            user.name = clean_name
            user.hashed_password = hashed
            user.role = role
            db.commit()
            print(f"✅ Admin account updated successfully!")
        else:
            print(f"🌱 Creating new admin user: {clean_email}")
            user = User(
                email=clean_email,
                hashed_password=hashed,
                name=clean_name,
                role=role,
            )
            db.add(user)
            db.commit()
            print(f"✅ Admin account created successfully!")

        print(f"\n📋 Admin Account Details:")
        print(f"   Email:    {clean_email}")
        print(f"   Role:     {role}")
        print(f"   Name:     {clean_name}")
        print(f"   Password: [SET AS REQUESTED]\n")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding admin: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or update Rapscos admin account")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "rapscos1933@gmail.com"), help="Admin email")
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", "Admin@1933"), help="Admin password")
    parser.add_argument("--name", default="Rapscos Admin", help="Admin display name")
    parser.add_argument("--role", default="owner", choices=["owner", "admin", "editor"], help="Admin role")

    args = parser.parse_args()
    seed_admin(args.email, args.password, args.name, args.role)
