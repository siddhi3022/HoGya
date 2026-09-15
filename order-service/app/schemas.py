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
# Order Schemas
# ----------------------------------------------------
class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100, description="Customer name cannot be empty")
    product_id: int = Field(..., gt=0, description="Product ID must be greater than 0")
    quantity: int = Field(..., gt=0, description="Order quantity must be greater than 0")


class OrderUpdate(BaseModel):
    status: Optional[str] = Field(None, min_length=1, max_length=50, description="New order status (e.g. SHIPPED, DELIVERED, CANCELLED)")


class OrderResponse(BaseModel):
    id: int
    customer_name: str
    product_id: int
    quantity: int
    status: str
    user_id: int

    model_config = ConfigDict(from_attributes=True)
