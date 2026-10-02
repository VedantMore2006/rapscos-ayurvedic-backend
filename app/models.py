import datetime
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=True, default="")
    address = Column(Text, nullable=True, default="")
    role = Column(String(20), nullable=False, default="customer")  # 'customer', 'admin', 'owner', 'editor'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def is_admin(self) -> bool:
        return self.role in ("admin", "owner", "editor")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    img_url = Column(String(255), nullable=True, default="")
    display_order = Column(Integer, default=0)
    auto_sort_by_sales = Column(Boolean, default=False)

    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(100), primary_key=True)  # slug identifier, e.g. "saunf-ark"
    category_key = Column(String(50), ForeignKey("categories.key", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    price = Column(Float, nullable=False, default=0.0)
    size = Column(String(100), nullable=False, default="")
    badge = Column(String(50), nullable=True)  # "Bestseller", "New", etc.
    desc = Column(Text, nullable=False, default="")
    benefits = Column(Text, nullable=False, default="[]")  # Stored as JSON array string
    howto = Column(Text, nullable=False, default="")
    images = Column(Text, nullable=False, default="[]")  # Stored as JSON array string
    is_featured = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    sales_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    category = relationship("Category", back_populates="products")
