import os
import re
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status

from ..auth import get_current_admin
from ..models import User

router = APIRouter(tags=["Images"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.getenv("MEDIA_DIR", os.path.join(BASE_DIR, "media"))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
PUBLIC_IMAGES_DIR = os.path.join(PROJECT_ROOT, "public", "images")
os.makedirs(MEDIA_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg", ".avif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def slugify_filename(name: str) -> str:
    base, ext = os.path.splitext(name)
    base = re.sub(r"[^\w\s-]", "", base.lower())
    base = re.sub(r"[\s_-]+", "-", base).strip("-") or "photo"
    return f"{base}{ext.lower()}"


# --- Compatibility Endpoints: /api/images ---

@router.get("/api/images")
async def get_images_list(
    path: Optional[str] = Query(None, description="Optional path to fetch specific image"),
    admin: User = Depends(get_current_admin),
):
    """
    Returns array of image paths for the admin photo picker:
    Includes all uploaded media and existing site images.
    """
    results = []

    # 1. Scanned media directory
    if os.path.exists(MEDIA_DIR):
        for f in os.listdir(MEDIA_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                results.append(f"/media/{f}")

    # 2. Existing static public images
    if os.path.exists(PUBLIC_IMAGES_DIR):
        for root, _, files in os.walk(PUBLIC_IMAGES_DIR):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    rel_path = os.path.relpath(os.path.join(root, f), os.path.join(PROJECT_ROOT, "public"))
                    results.append(f"/{rel_path}")

    return sorted(list(set(results)))


@router.post("/api/images")
async def upload_image_compat(
    request: Request,
    name: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
):
    """
    Accepts raw binary or multipart uploads from the admin UI.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    if len(body) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Image size exceeds 5MB limit.")

    raw_name = name or "photo.webp"
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid image extension.")

    unique_filename = f"{uuid.uuid4().hex[:12]}_{slugify_filename(raw_name)}"
    target_path = os.path.join(MEDIA_DIR, unique_filename)

    with open(target_path, "wb") as f:
        f.write(body)

    media_url = f"/media/{unique_filename}"
    return {"path": media_url, "url": media_url}


# --- RESTful Admin Image Endpoints: /api/admin/images ---

@router.post("/api/admin/images", status_code=status.HTTP_201_CREATED)
async def admin_upload_image(
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Image size exceeds 5MB limit.")

    unique_filename = f"{uuid.uuid4().hex[:12]}_{slugify_filename(file.filename or 'image.webp')}"
    target_path = os.path.join(MEDIA_DIR, unique_filename)

    with open(target_path, "wb") as f:
        f.write(contents)

    return {
        "url": f"/media/{unique_filename}",
        "path": f"/media/{unique_filename}",
        "name": file.filename,
        "size": len(contents),
    }


@router.get("/api/admin/images")
async def admin_list_images(
    admin: User = Depends(get_current_admin),
):
    items = []
    if os.path.exists(MEDIA_DIR):
        for entry in os.scandir(MEDIA_DIR):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    stat = entry.stat()
                    items.append({
                        "url": f"/media/{entry.name}",
                        "name": entry.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })
    items.sort(key=lambda x: x["modified"], reverse=True)
    return items


@router.delete("/api/admin/images")
async def admin_delete_image(
    path: str = Query(..., description="Image path e.g. /media/xyz.webp or filename"),
    admin: User = Depends(get_current_admin),
):
    filename = os.path.basename(path)
    safe_path = os.path.abspath(os.path.join(MEDIA_DIR, filename))

    if not safe_path.startswith(os.path.abspath(MEDIA_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not os.path.exists(safe_path):
        raise HTTPException(status_code=404, detail="Image not found.")

    os.remove(safe_path)
    return {"ok": True, "deleted": filename}
