from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_admin
from ..database import get_db
from ..models import Category, Product, User
from ..schemas import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter(tags=["Categories"])


def format_category(cat: Category, db: Session) -> dict:
    count = db.query(Product).filter(Product.category_key == cat.key).count()
    return {
        "id": cat.id,
        "key": cat.key,
        "name": cat.name,
        "img_url": cat.img_url or "",
        "img": cat.img_url or "",  # alias for frontend
        "display_order": cat.display_order,
        "auto_sort_by_sales": cat.auto_sort_by_sales,
        "count": count,
    }


# --- Public Endpoints ---

@router.get("/api/categories")
async def list_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).order_by(Category.display_order.asc(), Category.id.asc()).all()
    return [format_category(c, db) for c in cats]


# --- Admin Endpoints ---

@router.get("/api/admin/categories")
async def admin_list_categories(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    cats = db.query(Category).order_by(Category.display_order.asc(), Category.id.asc()).all()
    return [format_category(c, db) for c in cats]


@router.post("/api/admin/categories", status_code=status.HTTP_201_CREATED)
async def admin_create_category(
    body: CategoryCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    clean_key = body.key.strip().lower()
    existing = db.query(Category).filter(Category.key == clean_key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with key '{clean_key}' already exists.",
        )

    cat = Category(
        key=clean_key,
        name=body.name.strip(),
        img_url=body.img_url or "",
        display_order=body.display_order,
        auto_sort_by_sales=body.auto_sort_by_sales,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return format_category(cat, db)


@router.put("/api/admin/categories/{cat_id}")
async def admin_update_category(
    cat_id: str,
    body: CategoryUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    # Lookup by ID if numeric, or by key
    cat = None
    if cat_id.isdigit():
        cat = db.query(Category).filter(Category.id == int(cat_id)).first()
    if not cat:
        cat = db.query(Category).filter(Category.key == cat_id).first()

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")

    if body.name is not None:
        cat.name = body.name.strip()
    if body.img_url is not None:
        cat.img_url = body.img_url.strip()
    if body.display_order is not None:
        cat.display_order = body.display_order
    if body.auto_sort_by_sales is not None:
        cat.auto_sort_by_sales = body.auto_sort_by_sales

    db.commit()
    db.refresh(cat)
    return format_category(cat, db)


@router.delete("/api/admin/categories/{cat_id}")
async def admin_delete_category(
    cat_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    cat = None
    if cat_id.isdigit():
        cat = db.query(Category).filter(Category.id == int(cat_id)).first()
    if not cat:
        cat = db.query(Category).filter(Category.key == cat_id).first()

    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")

    db.delete(cat)
    db.commit()
    return {"ok": True, "deleted_id": cat_id}
