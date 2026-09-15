from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin"]))
):
    """
    Create a new product in inventory.
    Restricted to ADMIN role.
    """
    new_product = models.Product(
        name=product_in.name,
        price=product_in.price,
        stock=product_in.stock
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@router.get("/", response_model=List[schemas.ProductResponse])
def get_all_products(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Retrieve all products in the catalog.
    Accessible to authenticated users (admin, staff, customer).
    """
    return db.query(models.Product).all()


@router.get("/{product_id}", response_model=schemas.ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_caller: models.User = Depends(auth.verify_internal_or_user)
):
    """
    Retrieve details of a single product by ID.
    Secured: Requires valid Bearer JWT or internal service token.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )
    return product


@router.put("/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id: int,
    product_in: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin", "staff"]))
):
    """
    Update product details or stock.
    Restricted to ADMIN and STAFF roles.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    if product_in.name is not None:
        product.name = product_in.name
    if product_in.price is not None:
        product.price = product_in.price
    if product_in.stock is not None:
        product.stock = product_in.stock

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin"]))
):
    """
    Delete a product from the inventory.
    Restricted to ADMIN role.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    db.delete(product)
    db.commit()
    return {"message": f"Product with ID {product_id} successfully deleted", "product_id": product_id}


@router.post("/{product_id}/reserve", response_model=schemas.StockReserveResponse)
def reserve_stock(
    product_id: int,
    quantity: int = Query(..., gt=0, description="Quantity to reserve (must be > 0)"),
    db: Session = Depends(get_db),
    current_caller: models.User = Depends(auth.verify_internal_or_user)
):
    """
    Reserve/decrease product stock when an order is being placed.
    Secured: Requires valid Bearer JWT or internal service token.
    Rules:
    - quantity must be greater than 0
    - product must exist (404)
    - stock must be sufficient (409)
    - if successful, decreases stock and returns remaining stock
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    if product.stock < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Insufficient stock for product '{product.name}'. Available: {product.stock}, requested: {quantity}"
        )

    product.stock -= quantity
    db.commit()
    db.refresh(product)

    return {
        "message": "Stock reserved successfully",
        "product_id": product.id,
        "remaining_stock": product.stock
    }
