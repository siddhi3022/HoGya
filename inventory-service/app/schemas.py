from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ----------------------------------------------------
# User Schemas
# ----------------------------------------------------
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=4, max_length=128, description="Plain text password")

    # Ignore any extra fields like 'role' sent in payload
    model_config = ConfigDict(extra="ignore")


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: int
    username: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ----------------------------------------------------
# Product Schemas
# ----------------------------------------------------
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Product name")
    price: float = Field(..., gt=0, description="Product price must be greater than 0")
    stock: int = Field(..., ge=0, description="Product stock must be 0 or greater")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)


class ProductResponse(ProductBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class StockReserveResponse(BaseModel):
    message: str
    product_id: int
    remaining_stock: int
