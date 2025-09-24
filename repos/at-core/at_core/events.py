"""
Event utilities for creating and handling NATS events
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional


def generate_correlation_id(prefix: str = "req") -> str:
    """
    Generate a unique correlation ID

    Args:
        prefix: Prefix for the correlation ID

    Returns:
        Unique correlation ID
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def create_event_header(
    corr_id: Optional[str] = None,
    source: Optional[str] = None,
    instrument: Optional[str] = None,
    **kwargs
) -> Dict[str, str]:
    """
    Create standard NATS event headers

    Args:
        corr_id: Correlation ID (generated if not provided)
        source: Event source
        instrument: Trading instrument
        **kwargs: Additional headers

    Returns:
        Headers dictionary
    """
    headers = {}

    if corr_id:
        headers["Corr-ID"] = corr_id

    if source:
        headers["Source"] = source

    if instrument:
        headers["Instrument"] = instrument.upper()

    # Add any additional headers
    headers.update(kwargs)

    return headers


def create_signal_raw(
    payload: Dict[str, Any],
    source: str,
    corr_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a signals.raw event

    Args:
        payload: Raw signal payload
        source: Signal source
        corr_id: Correlation ID (generated if not provided)

    Returns:
        signals.raw event
    """
    if corr_id is None:
        corr_id = generate_correlation_id()

    return {
        "corr_id": corr_id,
        "source": source,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }


def create_signal_normalized(
    instrument: str,
    signal_type: str,
    strength: float,
    price: float,
    source: str,
    corr_id: str,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a signals.normalized event

    Args:
        instrument: Trading instrument
        signal_type: Type of signal
        strength: Signal strength (0-1)
        price: Current price
        source: Signal source
        corr_id: Correlation ID
        timestamp: Signal timestamp (current time if not provided)
        metadata: Additional metadata

    Returns:
        signals.normalized event
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "corr_id": corr_id,
        "timestamp": timestamp,
        "instrument": instrument.upper(),
        "signal_type": signal_type,
        "strength": strength,
        "price": price,
        "source": source,
        "metadata": metadata or {}
    }


def create_order_intent(
    strategy_id: str,
    agent_id: str,
    instrument: str,
    side: str,
    order_type: str,
    quantity: float,
    confidence: float,
    corr_id: str,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    reasoning: Optional[str] = None,
    risk_score: Optional[float] = None,
    signal_refs: Optional[list] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a decisions.order_intent event

    Args:
        strategy_id: Strategy identifier
        agent_id: Agent identifier
        instrument: Trading instrument
        side: buy or sell
        order_type: market, limit, stop, stop_limit
        quantity: Order quantity
        confidence: Confidence level (0-1)
        corr_id: Correlation ID
        price: Limit price (required for limit orders)
        stop_price: Stop price (required for stop orders)
        reasoning: Decision reasoning
        risk_score: Risk score (0-10)
        signal_refs: List of signal correlation IDs
        metadata: Additional metadata

    Returns:
        decisions.order_intent event
    """
    event = {
        "corr_id": corr_id,
        "strategy_id": strategy_id,
        "agent_id": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument.upper(),
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "confidence": confidence
    }

    # Add optional fields
    if price is not None:
        event["price"] = price
    if stop_price is not None:
        event["stop_price"] = stop_price
    if reasoning:
        event["reasoning"] = reasoning
    if risk_score is not None:
        event["risk_score"] = risk_score
    if signal_refs:
        event["signal_refs"] = signal_refs
    if metadata:
        event["metadata"] = metadata

    return event


def create_execution_fill(
    order_id: str,
    fill_id: str,
    instrument: str,
    side: str,
    fill_quantity: float,
    fill_price: float,
    fill_status: str,
    execution_venue: str,
    corr_id: str,
    strategy_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    commission: Optional[float] = None,
    slippage: Optional[float] = None,
    market_data: Optional[Dict[str, Any]] = None,
    execution_latency_ms: Optional[int] = None,
    reject_reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create an executions.fill event

    Returns:
        executions.fill event
    """
    event = {
        "corr_id": corr_id,
        "order_id": order_id,
        "fill_id": fill_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument.upper(),
        "side": side,
        "fill_quantity": fill_quantity,
        "fill_price": fill_price,
        "fill_status": fill_status,
        "execution_venue": execution_venue
    }

    # Add optional fields
    if strategy_id:
        event["strategy_id"] = strategy_id
    if agent_id:
        event["agent_id"] = agent_id
    if commission is not None:
        event["commission"] = commission
    if slippage is not None:
        event["slippage"] = slippage
    if market_data:
        event["market_data"] = market_data
    if execution_latency_ms is not None:
        event["execution_latency_ms"] = execution_latency_ms
    if reject_reason:
        event["reject_reason"] = reject_reason
    if metadata:
        event["metadata"] = metadata

    return event