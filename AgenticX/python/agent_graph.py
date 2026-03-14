from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from audit import WeilAuditLogger

try:
    from weilliptic_sdk.dropshipping import DropshippingStepAgentClient
except ImportError:
    class DropshippingStepAgentClient:  # type: ignore
        def __init__(self, contract_address: str) -> None:
            self.contract_address = contract_address

        async def run(
            self, namespace: str, flow_id: str, execution_context: Dict[str, Any]
        ):
            return "Done", execution_context

        async def resume(self, namespace: str, flow_id: str):
            return "Done", {}

        async def attach_context(
            self, namespace: str, flow_id: str, key: str, value: str
        ):
            return None


class AgentState(TypedDict, total=False):
    flow_id: str
    cart: List[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    step_agent_ctx: Dict[str, Any]
    status: str
    metadata: Dict[str, Any]
    tool_hint: str
    tool_detail: Dict[str, Any]
    human_prompt: str
    human_decision: str
    payment_intent: Dict[str, Any]
    audit_url: str
    last_event: str


FLOW_STATE_STORE: Dict[str, AgentState] = {}
HUMAN_DECISIONS: Dict[str, str] = {}

STEP_PROMPTS: Dict[str, str] = {
    "CartReview": "Summarize the cart and verify all items are available for dropshipping.",
    "RiskCheck": "Perform a fraud and risk check for this order based on cart and customer info.",
    "HumanApproval": "Summarize the order and ask a human operator for approval.",
    "PayWithWUSD": "Charge the customer in WUSD for the approved order.",
    "PlaceSupplierOrder": "Place supplier orders for all items in the cart.",
    "FulfillmentUpdate": "Record shipping and tracking information for the completed order.",
}

STEP_TO_TOOL: Dict[str, str] = {
    "CartReview": "catalog-mcp",
    "RiskCheck": "risk-mcp",
    "PayWithWUSD": "payment-mcp",
    "PlaceSupplierOrder": "supplier-mcp",
    "FulfillmentUpdate": "fulfillment-mcp",
}

STEP_ORDER: List[str] = [
    "CartReview",
    "RiskCheck",
    "HumanApproval",
    "PayWithWUSD",
    "PlaceSupplierOrder",
    "FulfillmentUpdate",
]

DEFAULT_MERCHANT_WALLET = os.getenv("MERCHANT_WALLET", "0xMERCHANT_WALLET")


def _get_planner_llm():
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        return ChatOllama(model=ollama_model, base_url=ollama_host)
    except Exception:
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1"))


llm = _get_planner_llm()

audit_logger = WeilAuditLogger(
    applet_id="dropshipping-step-agent",
    namespace="dropshipping",
)

step_agent_client = DropshippingStepAgentClient(
    contract_address="0xDROPSHIPPING_STEP_AGENT",
)


def _sum_cart(cart: List[Dict[str, Any]]) -> float:
    return sum(item.get("quantity", 1) * 10 for item in cart)


def persist_state(state: AgentState) -> None:
    state["audit_url"] = audit_logger.dashboard_url(state["flow_id"])
    FLOW_STATE_STORE[state["flow_id"]] = state


def get_flow_state(flow_id: str) -> Optional[AgentState]:
    return FLOW_STATE_STORE.get(flow_id)


def record_human_decision(flow_id: str, decision: str) -> None:
    HUMAN_DECISIONS[flow_id] = decision


def _next_step(step: str) -> str:
    try:
        idx = STEP_ORDER.index(step)
        return STEP_ORDER[idx + 1]
    except (ValueError, IndexError):
        return STEP_ORDER[-1]


def build_default_context(state: AgentState) -> Dict[str, Any]:
    metadata = state.get("metadata", {})
    return {
        "step": "CartReview",
        "flow_id": state["flow_id"],
        "answers": [],
        "prompt_plan": {"prompts": STEP_PROMPTS},
        "model": "GPT_5POINT1",
        "model_key": None,
        "context": {
            "cart_json": str(state["cart"]),
            "customer_wallet": metadata.get("customer_wallet"),
            "audit_trace": metadata.get("audit_trace", "dropshipping-llm"),
            "tool_hint": state.get("tool_hint"),
        },
        "context_metadata": {
            "merchant_wallet": DEFAULT_MERCHANT_WALLET,
        },
    }


async def plan_node(state: AgentState) -> AgentState:
    await audit_logger.log_event(
        flow_id=state["flow_id"],
        event_type="plan_start",
        payload={"cart": state["cart"]},
    )

    try:
        res = await llm.ainvoke(
            [
                {"role": "system", "content": "You are a dropshipping planner."},
                {
                    "role": "user",
                    "content": f"Plan fulfillment for this shopping cart: {state['cart']}",
                },
            ]
        )
        plan_text = res.content
        plan_source = llm.__class__.__name__
    except Exception as exc:
        plan_text = "Local fallback plan: validate SKUs, run risk checks, ask for human approval, collect WUSD, fulfill orders."
        plan_source = "fallback"
        await audit_logger.log_event(
            flow_id=state["flow_id"],
            event_type="plan_error",
            payload={"error": str(exc)},
        )

    await audit_logger.log_event(
        flow_id=state["flow_id"],
        event_type="plan_result",
        payload={"plan": plan_text, "source": plan_source},
    )

    state.setdefault("messages", []).append({"role": "assistant", "content": plan_text})
    metadata = state.setdefault("metadata", {})
    metadata.update({
        "planner": plan_source,
        "cart_size": len(state["cart"]),
        "audit_trace": "dropshipping-agent-plan",
    })
    state["human_prompt"] = STEP_PROMPTS["HumanApproval"]
    state["status"] = "planned"
    state["payment_intent"] = {
        "merchant_wallet": DEFAULT_MERCHANT_WALLET,
        "amount_wusd": _sum_cart(state["cart"]),
    }
    persist_state(state)
    return state


async def predict_tool_call_node(state: AgentState) -> AgentState:
    ctx = state.setdefault("step_agent_ctx", {})
    current_step = ctx.get("step", "CartReview")
    selected_tool = STEP_TO_TOOL.get(current_step, "catalog-mcp")
    tool_detail = {
        "step": current_step,
        "prompt": STEP_PROMPTS.get(current_step),
        "mcp": selected_tool,
    }
    state["tool_hint"] = selected_tool
    state["tool_detail"] = tool_detail
    await audit_logger.log_tool_event(
        flow_id=state["flow_id"],
        step=current_step,
        tool=selected_tool,
        detail={"phase": "pre-run", "tool_detail": tool_detail},
    )
    persist_state(state)
    return state


async def call_step_agent_node(state: AgentState) -> AgentState:
    ctx = state.get("step_agent_ctx") or build_default_context(state)
    ctx.setdefault("prompt_plan", {"prompts": STEP_PROMPTS})
    ctx["flow_id"] = state["flow_id"]
    ctx.setdefault("context", {})
    ctx["context"].update({
        "audit_url": audit_logger.dashboard_url(state["flow_id"]),
        "tool_hint": state.get("tool_hint"),
    })

    await audit_logger.log_event(
        flow_id=state["flow_id"],
        event_type="step_agent_run_start",
        payload={
            "ctx": ctx,
            "tool_hint": state.get("tool_hint"),
        },
    )

    run_status, new_ctx = await step_agent_client.run(
        namespace="dropshipping",
        flow_id=state["flow_id"],
        execution_context=ctx,
    )

    await audit_logger.log_event(
        flow_id=state["flow_id"],
        event_type="step_agent_run_result",
        payload={
            "run_status": run_status,
            "ctx": new_ctx,
        },
    )

    state["step_agent_ctx"] = new_ctx
    state["status"] = run_status
    state["last_event"] = "step_agent_run"
    persist_state(state)
    return state


async def human_in_loop_node(state: AgentState) -> AgentState:
    flow_id = state["flow_id"]
    await audit_logger.log_event(
        flow_id=flow_id,
        event_type="await_human",
        payload={"ctx": state.get("step_agent_ctx")},
    )

    decision = HUMAN_DECISIONS.get(flow_id) or state.get("human_decision")

    if not decision:
        await audit_logger.log_event(
            flow_id=flow_id,
            event_type="human_waiting",
            payload={"message": "Waiting for human approval."},
        )
        state["status"] = "waiting_for_human_approval"
        state["human_prompt"] = STEP_PROMPTS["HumanApproval"]
        persist_state(state)
        return state

    await audit_logger.log_event(
        flow_id=flow_id,
        event_type="human_decision",
        payload={"decision": decision},
    )

    state["human_decision"] = decision

    await step_agent_client.attach_context(
        namespace="dropshipping",
        flow_id=flow_id,
        key="approval",
        value=decision,
    )

    run_status, new_ctx = await step_agent_client.resume(
        namespace="dropshipping",
        flow_id=flow_id,
    )

    await audit_logger.log_event(
        flow_id=flow_id,
        event_type="step_agent_resume_result",
        payload={
            "run_status": run_status,
            "ctx": new_ctx,
        },
    )

    state["step_agent_ctx"] = new_ctx
    state["status"] = run_status
    state["last_event"] = "step_agent_resume"
    persist_state(state)
    return state


builder = StateGraph(AgentState)
builder.add_node("plan", plan_node)
builder.add_node("predict_tool", predict_tool_call_node)
builder.add_node("step_agent", call_step_agent_node)
builder.add_node("human", human_in_loop_node)

builder.set_entry_point("plan")
builder.add_edge("plan", "predict_tool")
builder.add_edge("predict_tool", "step_agent")

def route_step_agent(state: AgentState) -> str:
    status = state.get("status")
    if status == "Pending":
        return "human"
    if status in ("Done", "Failed"):
        return "END"
    return "step_agent"

builder.add_conditional_edges(
    "step_agent",
    route_step_agent,
    {
        "human": "human",
        "step_agent": "step_agent",
        "END": END,
    },
)

def route_human(state: AgentState) -> str:
    status = state.get("status")
    if status == "waiting_for_human_approval":
        return "END"
    return "step_agent"

builder.add_conditional_edges(
    "human",
    route_human,
    {
        "step_agent": "step_agent",
        "END": END,
    },
)

graph = builder.compile()

def schedule_flow(state: AgentState) -> None:
    persist_state(state)
    asyncio.create_task(graph.ainvoke(state))

def continue_flow_from_payment(
    flow_id: str,
    status: str,
    ctx: Optional[Dict[str, Any]] = None,
) -> None:
    state = get_flow_state(flow_id)
    if not state:
        return
    state["status"] = status
    if ctx:
        state["step_agent_ctx"] = ctx
    persist_state(state)
    schedule_flow(state)

def signal_human_approval(flow_id: str, decision: str) -> None:
    record_human_decision(flow_id, decision)
    state = get_flow_state(flow_id)
    if not state:
        return
    state["human_decision"] = decision
    state["human_prompt"] = STEP_PROMPTS["HumanApproval"]
    state["status"] = "approval_received"
    persist_state(state)
    schedule_flow(state)

def new_flow_id() -> str:
    return str(uuid.uuid4())
