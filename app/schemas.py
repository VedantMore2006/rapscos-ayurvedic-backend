from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# --- Auth & User Schemas ---

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    role: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    # Accept either login or email
    login: Optional[str] = None
    email: Optional[str] = None
    password: str

    def get_email_or_login(self) -> str:
        val = self.email or self.login or ""
        return val.strip().lower()


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = ""
    password: str = Field(..., min_length=6)
    code: Optional[str] = None  # Invite code for admin/team role


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


class PasswordChangeRequest(BaseModel):
    current_password: Optional[str] = None
    current: Optional[str] = None
    new_password: Optional[str] = None
    next: Optional[str] = None

    def get_current(self) -> str:
        return self.current_password or self.current or ""

    def get_new(self) -> str:
        return self.new_password or self.next or ""


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


# --- Category Schemas ---

class CategoryBase(BaseModel):
    key: str
    name: str
    img_url: Optional[str] = ""
    display_order: int = 0
    auto_sort_by_sales: bool = False


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    img_url: Optional[str] = None
    display_order: Optional[int] = None
    auto_sort_by_sales: Optional[bool] = None


class CategoryResponse(CategoryBase):
    id: int
    count: int = 0  # number of products in category

    class Config:
        from_attributes = True


# --- Product Schemas ---

class ProductBase(BaseModel):
    id: str
    category_key: str
    name: str
    price: float = 0.0
    size: str = ""
    badge: Optional[str] = None
    desc: str = ""
    benefits: List[str] = []
    howto: str = ""
    images: List[str] = []
    is_featured: bool = False
    display_order: int = 0


class ProductCreate(BaseModel):
    id: Optional[str] = None  # Slug; if omitted, generated from name
    category_key: Optional[str] = None
    cat: Optional[str] = None  # Frontend compatibility alias
    name: str
    price: float = 0.0
    size: str = ""
    badge: Optional[str] = None
    desc: str = ""
    benefits: List[str] = []
    howto: str = ""
    images: List[str] = []
    is_featured: bool = False
    display_order: int = 0

    def get_category_key(self) -> str:
        return self.category_key or self.cat or ""


class ProductUpdate(BaseModel):
    category_key: Optional[str] = None
    cat: Optional[str] = None
    name: Optional[str] = None
    price: Optional[float] = None
    size: Optional[str] = None
    badge: Optional[str] = None
    desc: Optional[str] = None
    benefits: Optional[List[str]] = None
    howto: Optional[str] = None
    images: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None

    def get_category_key(self) -> Optional[str]:
        return self.category_key if self.category_key is not None else self.cat


class ProductResponse(ProductBase):
    cat: str  # Alias for category_key so existing frontend code works unmodified
    sales_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
