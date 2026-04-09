from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
from enum import Enum

app = FastAPI(
    title="Order Management API",
    description="""
## Order Management Microservice

A RESTful API exposing four core order operations:

- **Create Order** — POST /orders
- **Query Order** — GET /orders/{order_id}
- **Update Order** — PATCH /orders/{order_id}
- **Cancel Order** — DELETE /orders/{order_id}

> POC built to demonstrate API-first microservice design patterns.
    """,
    version="1.0.0"
)

# --- Enums ---

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    CANCELLED = "CANCELLED"

# --- Models ---

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItem]

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "CUST-001",
                "items": [
                    {"product_id": "SKY-RF-5G-001", "quantity": 2, "unit_price": 49.99}
                ]
            }
        }

class UpdateOrderRequest(BaseModel):
    status: Optional[OrderStatus] = None
    items: Optional[List[OrderItem]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "CONFIRMED"
            }
        }

class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    status: OrderStatus
    items: List[OrderItem]
    total_amount: float
    created_at: str
    updated_at: str

# --- In-memory store (replace with DB in production) ---
orders_db: dict = {}

# --- Helper ---
def calculate_total(items: List[OrderItem]) -> float:
    return round(sum(item.quantity * item.unit_price for item in items), 2)

# --- Routes ---

@app.post("/orders", response_model=OrderResponse, status_code=201, tags=["Orders"])
def create_order(request: CreateOrderRequest):
    """
    **Create a new order.**

    Accepts customer ID and list of items. Returns the created order with a generated order ID.
    """
    order_id = f"ORD-{str(uuid4())[:8].upper()}"
    now = datetime.utcnow().isoformat()
    order = {
        "order_id": order_id,
        "customer_id": request.customer_id,
        "status": OrderStatus.PENDING,
        "items": [item.dict() for item in request.items],
        "total_amount": calculate_total(request.items),
        "created_at": now,
        "updated_at": now
    }
    orders_db[order_id] = order
    return order


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def get_order(order_id: str):
    """
    **Query an order by ID.**

    Returns full order details including status, items, and timestamps.
    """
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order


@app.patch("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def update_order(order_id: str, request: UpdateOrderRequest):
    """
    **Update an existing order.**

    Supports partial updates — update status, items, or both.
    Cannot update a cancelled order.
    """
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    if order["status"] == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot update a cancelled order")

    if request.status:
        order["status"] = request.status
    if request.items:
        order["items"] = [item.dict() for item in request.items]
        order["total_amount"] = calculate_total(request.items)

    order["updated_at"] = datetime.utcnow().isoformat()
    orders_db[order_id] = order
    return order


@app.delete("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
def cancel_order(order_id: str):
    """
    **Cancel an order.**

    Sets order status to CANCELLED. Returns the updated order.
    Already cancelled orders return a 400 error.
    """
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    if order["status"] == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Order is already cancelled")

    order["status"] = OrderStatus.CANCELLED
    order["updated_at"] = datetime.utcnow().isoformat()
    orders_db[order_id] = order
    return order


@app.get("/orders", response_model=List[OrderResponse], tags=["Orders"])
def list_orders():
    """
    **List all orders.**

    Returns all orders in the system. Useful for testing the POC.
    """
    return list(orders_db.values())


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy", "service": "order-management-api", "version": "1.0.0"}
