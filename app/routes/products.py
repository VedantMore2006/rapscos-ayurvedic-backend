import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..auth import get_current_admin
from ..database import get_db
from ..models import Category, Product, User
from ..schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(tags=["Products"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def parse_json_field(val: Optional[str]) -> list:
    if not val:
        return []
    try:
        data = json.loads(val)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def format_product(p: Product) -> dict:
    benefits_list = parse_json_field(p.benefits)
    images_list = parse_json_field(p.images)
    return {
        "id": p.id,
        "name": p.name,
        "category_key": p.category_key,
        "cat": p.category_key,  # Frontend alias
        "price": p.price,
        "size": p.size or "",
        "badge": p.badge,
        "desc": p.desc or "",
        "benefits": benefits_list,
        "howto": p.howto or "",
        "images": images_list,
        "is_featured": bool(p.is_featured),
        "display_order": p.display_order,
        "sales_count": p.sales_count or 0,
        "created_at": p.created_at,
    }


# --- Public Endpoints ---

@router.get("/api/products")
async def list_products(
    cat: Optional[str] = Query(None, description="Filter by category key"),
    featured: Optional[bool] = Query(None, description="Filter featured products"),
    db: Session = Depends(get_db),
):
    query = db.query(Product)

    if featured is not None:
        query = query.filter(Product.is_featured == featured)

    if cat:
        query = query.filter(Product.category_key == cat)
        category_obj = db.query(Category).filter(Category.key == cat).first()
        # If auto_sort_by_sales is enabled for this category, sort bestsellers to the top!
        if category_obj and category_obj.auto_sort_by_sales:
            query = query.order_by(Product.sales_count.desc(), Product.display_order.asc())
        else:
            query = query.order_by(Product.display_order.asc(), Product.created_at.asc())
    else:
        query = query.order_by(Product.display_order.asc(), Product.created_at.asc())

    products = query.all()
    return [format_product(p) for p in products]


@router.get("/api/products/{product_id}")
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return format_product(product)


@router.post("/api/products/{product_id}/click")
async def register_product_click(product_id: str, db: Session = Depends(get_db)):
    """
    Called when a user clicks 'Order on WhatsApp' or views the product.
    Increments sales_count for bestseller ranking.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    product.sales_count = (product.sales_count or 0) + 1
    db.commit()
    return {"ok": True, "id": product.id, "sales_count": product.sales_count}


# --- Admin Endpoints ---

@router.get("/api/admin/products")
async def admin_list_products(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    products = db.query(Product).order_by(Product.display_order.asc(), Product.created_at.asc()).all()
    return [format_product(p) for p in products]


@router.post("/api/admin/products", status_code=status.HTTP_201_CREATED)
async def admin_create_product(
    body: ProductCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    category_key = body.get_category_key()
    if not category_key:
        raise HTTPException(status_code=400, detail="Category key is required.")

    # Validate category exists
    cat_exists = db.query(Category).filter(Category.key == category_key).first()
    if not cat_exists:
        raise HTTPException(status_code=400, detail=f"Category '{category_key}' does not exist.")

    product_id = body.id or slugify(body.name)
    if not product_id:
        raise HTTPException(status_code=400, detail="Product id or valid name is required.")

    # Ensure unique slug
    base_id = product_id
    counter = 1
    while db.query(Product).filter(Product.id == product_id).first():
        counter += 1
        product_id = f"{base_id}-{counter}"

    product = Product(
        id=product_id,
        category_key=category_key,
        name=body.name.strip(),
        price=body.price,
        size=body.size.strip(),
        badge=body.badge.strip() if body.badge else None,
        desc=body.desc.strip(),
        benefits=json.dumps(body.benefits or []),
        howto=body.howto.strip(),
        images=json.dumps(body.images or []),
        is_featured=body.is_featured,
        display_order=body.display_order,
        sales_count=0,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return format_product(product)


@router.put("/api/admin/products/{product_id}")
async def admin_update_product(
    product_id: str,
    body: ProductUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    category_key = body.get_category_key()
    if category_key is not None:
        cat_exists = db.query(Category).filter(Category.key == category_key).first()
        if not cat_exists:
            raise HTTPException(status_code=400, detail=f"Category '{category_key}' does not exist.")
        product.category_key = category_key

    if body.name is not None:
        product.name = body.name.strip()
    if body.price is not None:
        product.price = body.price
    if body.size is not None:
        product.size = body.size.strip()
    if body.badge is not None:
        product.badge = body.badge.strip() if body.badge else None
    if body.desc is not None:
        product.desc = body.desc.strip()
    if body.benefits is not None:
        product.benefits = json.dumps(body.benefits)
    if body.howto is not None:
        product.howto = body.howto.strip()
    if body.images is not None:
        product.images = json.dumps(body.images)
    if body.is_featured is not None:
        product.is_featured = body.is_featured
    if body.display_order is not None:
        product.display_order = body.display_order

    db.commit()
    db.refresh(product)
    return format_product(product)


@router.delete("/api/admin/products/{product_id}")
async def admin_delete_product(
    product_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    db.delete(product)
    db.commit()
    return {"ok": True, "deleted_id": product_id}
