from typing import Dict, List, Optional
from ai_supplier_agent import select_supplier
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# -----------------------------
# StepAgent configuration
# -----------------------------

STEP_AGENT_ADDRESS = "aaaaaat2t7jjfasit35tms4fduuvwn7ezbl36yu2fgkmlbtap75glrgq2y"
WEIL_RPC = "https://p-qa51m-0.asia-south1.main.weilliptic.net"


# -----------------------------
# In-memory order registry
# -----------------------------

FLOW_REGISTRY: Dict[str, Dict] = {}


# -----------------------------
# Models
# -----------------------------

class CartItem(BaseModel):
    sku: str
    quantity: int


class Product(BaseModel):
    sku: str
    name: str
    price: float
    image: Optional[str] = None
    description: Optional[str] = None


class CreateOrderRequest(BaseModel):
    cart: List[CartItem]
    customer_wallet: str


class PaymentConfirmedRequest(BaseModel):
    tx_hash: str
    amount_wusd: float


class HumanDecisionRequest(BaseModel):
    decision: str


# -----------------------------
# FastAPI setup
# -----------------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Product API
# -----------------------------

SUPPLIER_API = "https://fakestoreapi.com/products"


@app.get("/products", response_model=List[Product])
async def list_products():

    res = requests.get(SUPPLIER_API)
    data = res.json()

    products = []

    for p in data:
        products.append(
            Product(
                sku=f"sku-{p['id']}",
                name=p["title"],
                price=p["price"],
                image=p.get("image"),
                description=p.get("description"),
            )
        )

    return products


# -----------------------------
# Create Order
# -----------------------------

@app.post("/orders")
async def create_order(req: CreateOrderRequest):

    flow_id = str(len(FLOW_REGISTRY) + 1)

    cart = [item.dict() for item in req.cart]

    # AI supplier decision
    supplier = select_supplier(cart)

    state = {
        "flow_id": flow_id,
        "cart": cart,
        "supplier": supplier,
        "status": "waiting_for_human_approval",
        "human_prompt": "Approve supplier selection?",
        "payment_intent": None
    }

    FLOW_REGISTRY[flow_id] = state

    # Trigger Rust StepAgent
    try:
        requests.post(
            f"{WEIL_RPC}/step-agent/{STEP_AGENT_ADDRESS}/run",
            json={
                "flow_id": flow_id,
                "cart": cart,
                "supplier": supplier
            }
        )
    except:
        print("StepAgent not reachable (dev mode)")

    return state


# -----------------------------
# Order Status
# -----------------------------

@app.get("/orders/{flow_id}")
async def order_status(flow_id: str):

    if flow_id not in FLOW_REGISTRY:
        raise HTTPException(status_code=404)

    state = FLOW_REGISTRY[flow_id]

    return {
        "flow_id": state["flow_id"],
        "cart": state["cart"],
        "supplier": state["supplier"],
        "status": state["status"],
        "human_prompt": state.get("human_prompt"),
        "payment_intent": state.get("payment_intent")
    }


# -----------------------------
# Admin: List Orders
# -----------------------------

@app.get("/orders")
async def list_orders():

    return list(FLOW_REGISTRY.values())


# -----------------------------
# Human Approval
# -----------------------------

@app.post("/orders/{flow_id}/human-approval")
async def human_approval(flow_id: str, body: HumanDecisionRequest):

    if flow_id not in FLOW_REGISTRY:
        raise HTTPException(status_code=404)

    state = FLOW_REGISTRY[flow_id]

    # Move order to payment stage
    state["status"] = "payment_pending"

    # Create payment intent
    state["payment_intent"] = {
        "merchant_wallet": "0xMERCHANT_WALLET",
        "amount_wusd": 10
    }

    # Resume Rust StepAgent
    try:
        requests.post(
            f"{WEIL_RPC}/step-agent/{STEP_AGENT_ADDRESS}/resume",
            json={
                "flow_id": flow_id,
                "event": "human_approved",
                "decision": body.decision
            }
        )
    except:
        print("StepAgent resume failed (dev mode)")

    return {
        "flow_id": flow_id,
        "status": "payment_pending"
    }


# -----------------------------
# Payment Intent
# -----------------------------

@app.post("/orders/{flow_id}/payment-intent")
async def payment_intent(flow_id: str):

    if flow_id not in FLOW_REGISTRY:
        raise HTTPException(status_code=404)

    state = FLOW_REGISTRY[flow_id]

    if state["payment_intent"] is None:
        state["payment_intent"] = {
            "merchant_wallet": "0xMERCHANT_WALLET",
            "amount_wusd": 10
        }

    return state["payment_intent"]


# -----------------------------
# Payment Confirmed
# -----------------------------

@app.post("/orders/{flow_id}/payment-confirmed")
async def payment_confirmed(flow_id: str, body: PaymentConfirmedRequest):

    if flow_id not in FLOW_REGISTRY:
        raise HTTPException(status_code=404)

    state = FLOW_REGISTRY[flow_id]

    state["status"] = "payment_confirmed"

    try:
        requests.post(
            f"{WEIL_RPC}/step-agent/{STEP_AGENT_ADDRESS}/resume",
            json={
                "flow_id": flow_id,
                "event": "payment_confirmed"
            }
        )
    except:
        print("StepAgent resume failed")

    return {
        "flow_id": flow_id,
        "status": "payment_confirmed"
    }


# -----------------------------
# Health
# -----------------------------

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}