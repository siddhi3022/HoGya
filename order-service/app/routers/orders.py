import os
from typing import List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/orders", tags=["Orders"])

INVENTORY_URL = os.environ.get("INVENTORY_URL", "http://127.0.0.1:8002")


@router.post("/", response_model=schemas.OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
    authorization: Optional[str] = Header(None)
):
    """
    Create a new customer order with inventory verification and stock reservation.

    Execution Flow:
    1. Validate quantity > 0.
    2. Check product existence via Inventory Service GET /inventory/{product_id}.
    3. Reserve stock via Inventory Service POST /inventory/{product_id}/reserve?quantity=N.
       (Uses authenticated inter-service token and client bearer token).
    4. Upon successful reservation, commit new order to order.db with status 'CONFIRMED'.
    5. Associate order with current_user.id for ownership enforcement.
    """
    # Prepare inter-service headers (pass internal service token and forwarded JWT)
    headers = {
        "X-Internal-Service-Token": auth.INTERNAL_SERVICE_TOKEN
    }
    if authorization:
        headers["Authorization"] = authorization

    async with httpx.AsyncClient(timeout=5.0) as client:
        # STEP 2: Verify product exists in Inventory Service
        product_url = f"{INVENTORY_URL}/inventory/{order_in.product_id}"
        try:
            resp_check = await client.get(product_url, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RequestError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory Service unavailable. Please try again later."
            )

        if resp_check.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Internal authentication failure with Inventory Service."
            )
        elif resp_check.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {order_in.product_id} does not exist in Inventory."
            )
        elif resp_check.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected response from Inventory Service: HTTP {resp_check.status_code}"
            )

        # STEP 3: Reserve stock in Inventory Service
        reserve_url = f"{INVENTORY_URL}/inventory/{order_in.product_id}/reserve?quantity={order_in.quantity}"
        try:
            resp_reserve = await client.post(reserve_url, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RequestError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory Service unavailable during stock reservation."
            )

        if resp_reserve.status_code == 409:
            err_detail = resp_reserve.json().get("detail", "Insufficient stock for this product")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_detail
            )
        elif resp_reserve.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Internal authentication failure with Inventory Service during reservation."
            )
        elif resp_reserve.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stock reservation failed unexpectedly: HTTP {resp_reserve.status_code}"
            )

    # STEP 4 & 5: Stock reserved! Create order in order.db with status = 'CONFIRMED'
    new_order = models.Order(
        customer_name=order_in.customer_name,
        product_id=order_in.product_id,
        quantity=order_in.quantity,
        status="CONFIRMED",
        user_id=current_user.id
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


@router.get("/", response_model=List[schemas.OrderResponse])
def get_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Retrieve orders with RBAC & Ownership filtering:
    - Customer role: views only their own orders.
    - Admin and Staff roles: view all system orders.
    """
    if current_user.role == "customer":
        return db.query(models.Order).filter(models.Order.user_id == current_user.id).all()
    # Admin or Staff
    return db.query(models.Order).all()


@router.get("/{order_id}", response_model=schemas.OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Retrieve single order by ID with ownership check:
    - Customer: can only access their own order (403 if unauthorized).
    - Admin/Staff: can access any order.
    """
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found"
        )

    if current_user.role == "customer" and order.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view this order."
        )

    return order


@router.put("/{order_id}", response_model=schemas.OrderResponse)
def update_order(
    order_id: int,
    order_in: schemas.OrderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin", "staff"]))
):
    """
    Update order status (e.g. SHIPPED, DELIVERED, CANCELLED).
    Restricted to ADMIN and STAFF roles.
    """
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found"
        )

    if order_in.status is not None:
        order.status = order_in.status

    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=status.HTTP_200_OK)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin"]))
):
    """
    Delete an order from order.db.
    Restricted to ADMIN role.
    """
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found"
        )

    db.delete(order)
    db.commit()
    return {"message": f"Order with ID {order_id} successfully deleted", "order_id": order_id}
