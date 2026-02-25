"""
LangGraph workflow for Ernesto.

Graph topology:
  intake → listing → [HUMAN APPROVAL] → publisher → deal_manager → [HUMAN OFFER DECISION] → deal_manager (loop)

Human-in-the-loop is implemented via interrupt_before on the approval and offer nodes.
State is persisted in SQLite via LangGraph's SqliteSaver.
"""
from typing import Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ..agents.intake import run_intake
from ..agents.listing import run_listing
from ..agents.publisher import run_publisher
from ..agents.deal_manager import run_deal_manager


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

def route_after_listing(state: dict[str, Any]) -> Literal["awaiting_approval", "error"]:
    if state.get("errors") and not state.get("listing_copy"):
        return "error"
    return "awaiting_approval"


def route_after_approval(state: dict[str, Any]) -> Literal["publisher", "cancelled"]:
    human_input = state.get("human_input", {})
    if human_input.get("action") == "cancel":
        return "cancelled"
    return "publisher"


def route_after_deal_manager(state: dict[str, Any]) -> Literal["awaiting_offer_decision", "managing", "sold"]:
    if state.get("step") == "awaiting_offer_decision":
        return "awaiting_offer_decision"
    if state.get("step") == "sold":
        return "sold"
    return "managing"


def route_after_offer_decision(state: dict[str, Any]) -> Literal["deal_manager", "sold"]:
    human_input = state.get("human_input", {})
    if human_input.get("action") == "sold":
        return "sold"
    return "deal_manager"


# ---------------------------------------------------------------------------
# Passthrough nodes (for interrupt points)
# ---------------------------------------------------------------------------

async def awaiting_approval_node(state: dict[str, Any]) -> dict[str, Any]:
    """Interrupt point: human reviews listing copy and price before publishing."""
    return state


async def awaiting_offer_decision_node(state: dict[str, Any]) -> dict[str, Any]:
    """Interrupt point: human decides on pending offers."""
    return state


async def cancelled_node(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step": "cancelled"}


async def sold_node(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step": "sold"}


async def error_node(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "step": "error"}


async def managing_node(state: dict[str, Any]) -> dict[str, Any]:
    """Idle node — the graph pauses here between polling cycles."""
    return {**state, "step": "managing"}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("intake", run_intake)
    g.add_node("listing", run_listing)
    g.add_node("awaiting_approval", awaiting_approval_node)
    g.add_node("publisher", run_publisher)
    g.add_node("deal_manager", run_deal_manager)
    g.add_node("awaiting_offer_decision", awaiting_offer_decision_node)
    g.add_node("managing", managing_node)
    g.add_node("cancelled", cancelled_node)
    g.add_node("sold", sold_node)
    g.add_node("error", error_node)

    g.set_entry_point("intake")

    g.add_edge("intake", "listing")
    g.add_conditional_edges("listing", route_after_listing, {
        "awaiting_approval": "awaiting_approval",
        "error": "error",
    })
    g.add_conditional_edges("awaiting_approval", route_after_approval, {
        "publisher": "publisher",
        "cancelled": "cancelled",
    })
    g.add_edge("publisher", "deal_manager")
    g.add_conditional_edges("deal_manager", route_after_deal_manager, {
        "awaiting_offer_decision": "awaiting_offer_decision",
        "managing": "managing",
        "sold": "sold",
    })
    g.add_conditional_edges("awaiting_offer_decision", route_after_offer_decision, {
        "deal_manager": "deal_manager",
        "sold": "sold",
    })
    g.add_edge("managing", END)
    g.add_edge("cancelled", END)
    g.add_edge("sold", END)
    g.add_edge("error", END)

    return g


async def get_compiled_graph(db_path: str = "./ernesto_checkpoints.db"):
    """Return a compiled graph with SQLite checkpointing."""
    g = build_graph()
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        compiled = g.compile(
            checkpointer=saver,
            interrupt_before=["awaiting_approval", "awaiting_offer_decision"],
        )
        return compiled, saver
