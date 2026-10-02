import json
import os
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import get_current_admin
from ..database import get_db
from ..models import Category, Product, User
from .categories import format_category
from .products import format_product, parse_json_field

router = APIRouter(tags=["Content"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
BACKEND_CONTENT_FILE = os.path.join(BASE_DIR, "data", "content.json")
ROOT_CONTENT_FILE = os.path.join(PROJECT_ROOT, "src", "data", "content.json")
CONTENT_FILE = BACKEND_CONTENT_FILE if os.path.exists(BACKEND_CONTENT_FILE) else ROOT_CONTENT_FILE


def load_static_content():
    if os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


@router.get("/api/content")
async def get_content(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    static_data = load_static_content()

    # Dynamic DB categories and products
    db_cats = db.query(Category).order_by(Category.display_order.asc(), Category.id.asc()).all()
    categories_list = []
    for c in db_cats:
        categories_list.append({
            "key": c.key,
            "name": c.name,
            "img": c.img_url or "",
            "img_url": c.img_url or "",
            "display_order": c.display_order,
            "auto_sort_by_sales": c.auto_sort_by_sales,
        })

    db_products = db.query(Product).order_by(Product.display_order.asc(), Product.created_at.asc()).all()
    products_list = []
    featured_list = []
    for p in db_products:
        prod_dict = {
            "id": p.id,
            "name": p.name,
            "cat": p.category_key,
            "price": p.price,
            "size": p.size or "",
            "badge": p.badge,
            "desc": p.desc or "",
            "benefits": parse_json_field(p.benefits),
            "howto": p.howto or "",
            "images": parse_json_field(p.images),
            "display_order": p.display_order,
            "sales_count": p.sales_count or 0,
        }
        products_list.append(prod_dict)
        if p.is_featured:
            featured_list.append(p.id)

    full_payload = {
        **static_data,
        "categories": categories_list,
        "products": products_list,
        "featured": featured_list,
    }

    return {
        "published": full_payload,
        "content": full_payload,
        "draft": None,
    }


@router.put("/api/content")
async def save_content(
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    body = await request.json()
    new_content = body.get("content", {})
    if not new_content:
        raise HTTPException(status_code=400, detail="Invalid content payload.")

    # 1. Update Categories
    categories_data = new_content.get("categories", [])
    for order, c_data in enumerate(categories_data):
        key = c_data.get("key", "").strip().lower()
        if not key:
            continue
        cat = db.query(Category).filter(Category.key == key).first()
        if not cat:
            cat = Category(
                key=key,
                name=c_data.get("name", key),
                img_url=c_data.get("img") or c_data.get("img_url") or "",
                display_order=order,
                auto_sort_by_sales=bool(c_data.get("auto_sort_by_sales", False)),
            )
            db.add(cat)
        else:
            cat.name = c_data.get("name", cat.name)
            cat.img_url = c_data.get("img") or c_data.get("img_url") or cat.img_url
            cat.display_order = order
            if "auto_sort_by_sales" in c_data:
                cat.auto_sort_by_sales = bool(c_data["auto_sort_by_sales"])

    # 2. Update Products
    featured_set = set(new_content.get("featured", []))
    products_data = new_content.get("products", [])
    seen_ids = set()

    for order, p_data in enumerate(products_data):
        pid = p_data.get("id", "").strip()
        if not pid:
            continue
        seen_ids.add(pid)
        p = db.query(Product).filter(Product.id == pid).first()
        benefits_json = json.dumps(p_data.get("benefits", []))
        images_json = json.dumps(p_data.get("images", []))
        is_feat = pid in featured_set

        if not p:
            p = Product(
                id=pid,
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

    # Remove any products that were deleted in the editor
    if seen_ids:
        db.query(Product).filter(Product.id.not_in(seen_ids)).delete(synchronize_session=False)

    db.commit()

    # Also keep content.json in sync on disk for Vite HMR, builds, and standalone backend
    for c_path in [BACKEND_CONTENT_FILE, ROOT_CONTENT_FILE]:
        if os.path.exists(c_path):
            try:
                with open(c_path, "r", encoding="utf-8-sig") as f:
                    disk_content = json.load(f)
                disk_content["categories"] = categories_data
                disk_content["products"] = products_data
                disk_content["featured"] = list(featured_set)
                with open(c_path, "w", encoding="utf-8") as f:
                    json.dump(disk_content, f, indent=2, ensure_ascii=False)
            except Exception as err:
                print(f"Warning: could not sync {c_path}: {err}")

    at_str = datetime.utcnow().isoformat()
    return {"ok": True, "at": at_str}


@router.get("/api/publish")
async def get_publish_status(admin: User = Depends(get_current_admin)):
    return {
        "deploy": {
            "status": "completed",
            "conclusion": "success",
            "created": datetime.utcnow().isoformat(),
        },
        "history": [],
    }


@router.post("/api/publish")
async def trigger_publish(admin: User = Depends(get_current_admin)):
    return {
        "ok": True,
        "deploy": {
            "status": "completed",
            "conclusion": "success",
            "created": datetime.utcnow().isoformat(),
        },
    }
