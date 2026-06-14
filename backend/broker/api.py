"""
Per-user broker endpoints (authenticated, encrypted-at-rest).

Phase 2 — MeroShare connect + read-only portfolio for the self-audit feature.
Each call is scoped to the logged-in user; credentials are validated against the
live broker, then stored encrypted. TMS (Phase 3) and autonomous live execution
(Phase 4, gated/disabled by default) build on this same store.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..security import credential_encryption_available
from .credentials import (
    credential_status,
    delete_credentials,
    load_credentials,
    save_credentials,
)
from .mero_share import MeroShareClient, MeroSharePortfolio
from .tms_client import TMSClient

logger = logging.getLogger("nepse-alpha.broker")

router = APIRouter(prefix="/api/broker", tags=["broker"])


def _uid(user: dict[str, Any]) -> str:
    return str(user.get("_id") or user.get("id"))


def _portfolio_dict(portfolio: MeroSharePortfolio) -> dict[str, Any]:
    return asdict(portfolio)


class MeroShareConnectRequest(BaseModel):
    dp: str = Field(..., description="Depository Participant (DP) ID")
    username: str = Field(..., description="MeroShare username / client ID")
    password: str = Field(..., description="MeroShare password")


def _require_encryption() -> None:
    if not credential_encryption_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Credential encryption is not configured. Set CREDENTIAL_ENCRYPTION_KEY "
                "before connecting a broker account."
            ),
        )


@router.post("/meroshare/connect")
def meroshare_connect(req: MeroShareConnectRequest, user: dict = Depends(get_current_user)):
    """Validate MeroShare credentials, store them encrypted, return the portfolio."""
    _require_encryption()
    client = MeroShareClient(client_id=req.username, password=req.password, dp_id=req.dp)
    try:
        if not client.login():
            raise HTTPException(status_code=401, detail="MeroShare login failed. Check DP, username and password.")
        portfolio = client.get_portfolio()
    finally:
        client.close()

    save_credentials(_uid(user), "meroshare", {"dp": req.dp, "username": req.username, "password": req.password})
    logger.info("MeroShare connected for user %s", _uid(user))
    return {"connected": True, "provider": "meroshare", "portfolio": _portfolio_dict(portfolio)}


@router.get("/meroshare/status")
def meroshare_status(user: dict = Depends(get_current_user)):
    """Whether MeroShare is linked for this user (no secrets returned)."""
    return credential_status(_uid(user), "meroshare")


@router.get("/meroshare/portfolio")
def meroshare_portfolio(user: dict = Depends(get_current_user)):
    """Fetch the live MeroShare portfolio using the user's stored credentials."""
    creds = load_credentials(_uid(user), "meroshare")
    if not creds:
        raise HTTPException(status_code=404, detail="MeroShare is not connected for this account.")
    client = MeroShareClient(
        client_id=creds.get("username"),
        password=creds.get("password"),
        dp_id=creds.get("dp"),
    )
    try:
        if not client.login():
            raise HTTPException(status_code=502, detail="Could not establish a MeroShare session. Re-connect your account.")
        portfolio = client.get_portfolio()
    finally:
        client.close()
    return _portfolio_dict(portfolio)


@router.delete("/meroshare")
def meroshare_disconnect(user: dict = Depends(get_current_user)):
    """Remove the stored MeroShare credentials (disconnect)."""
    delete_credentials(_uid(user), "meroshare")
    return {"connected": False, "provider": "meroshare"}


# ─── TMS (Phase 3 — view stage; placement/management added incrementally) ──────

class TmsConnectRequest(BaseModel):
    tms_url: str = Field(..., description="Broker TMS portal URL, e.g. https://tms49.nepse.com.np")
    username: str = Field(..., description="TMS username")
    password: str = Field(..., description="TMS password")
    pin: str | None = Field(default=None, description="TMS transaction PIN (optional, for trading)")


@router.post("/tms/connect")
def tms_connect(req: TmsConnectRequest, user: dict = Depends(get_current_user)):
    """Validate TMS credentials and store them encrypted."""
    _require_encryption()
    client = TMSClient(tms_url=req.tms_url, username=req.username, password=req.password, pin=req.pin or "")
    try:
        if not client.login():
            raise HTTPException(status_code=401, detail="TMS login failed. Check the portal URL, username and password.")
    finally:
        client.close()

    save_credentials(
        _uid(user), "tms",
        {"tms_url": req.tms_url.rstrip("/"), "username": req.username, "password": req.password, "pin": req.pin or ""},
    )
    logger.info("TMS connected for user %s", _uid(user))
    return {"connected": True, "provider": "tms"}


@router.get("/tms/status")
def tms_status(user: dict = Depends(get_current_user)):
    return credential_status(_uid(user), "tms")


@router.get("/tms/portfolio")
def tms_portfolio(user: dict = Depends(get_current_user)):
    """Fetch the live TMS portfolio + cash using the user's stored credentials."""
    creds = load_credentials(_uid(user), "tms")
    if not creds:
        raise HTTPException(status_code=404, detail="TMS is not connected for this account.")
    client = TMSClient(
        tms_url=creds.get("tms_url"),
        username=creds.get("username"),
        password=creds.get("password"),
        pin=creds.get("pin", ""),
    )
    try:
        if not client.login():
            raise HTTPException(status_code=502, detail="Could not establish a TMS session. Re-connect your account.")
        holdings = client.get_portfolio()
        cash = client.get_cash_balance()
    finally:
        client.close()
    return {"holdings": holdings, "cash_balance": cash}


@router.delete("/tms")
def tms_disconnect(user: dict = Depends(get_current_user)):
    """Remove the stored TMS credentials (disconnect)."""
    delete_credentials(_uid(user), "tms")
    return {"connected": False, "provider": "tms"}


# ─── Autonomous live-trading control (the safety gate, surfaced to the user) ────

class AutonomousOptInRequest(BaseModel):
    enabled: bool = Field(..., description="Opt in/out of autonomous LIVE trading for this account")


@router.get("/autonomous/status")
def autonomous_status(user: dict = Depends(get_current_user)):
    """Show the effective state of the autonomous live-trading safety gate."""
    from ..settings import get_settings
    from .broker_api import get_broker_api

    s = get_settings()
    broker = get_broker_api()
    broker._roll_day()
    will_trade_live = (
        (not s.broker_paper_mode)
        and s.autonomous_live_trading_enabled
        and (not s.autonomous_kill_switch)
        and broker.autonomous_opt_in
    )
    return {
        "paper_mode": s.broker_paper_mode,
        "live_trading_enabled": s.autonomous_live_trading_enabled,  # global arm switch
        "kill_switch": s.autonomous_kill_switch,
        "user_opted_in": broker.autonomous_opt_in,
        "will_execute_live": will_trade_live,
        "limits": {
            "max_order_npr": s.autonomous_max_order_npr,
            "max_trades_per_day": s.autonomous_max_trades_per_day,
            "daily_loss_limit_npr": s.autonomous_daily_loss_limit_npr,
        },
        "today": {"trades": broker._trades_today, "realized_loss_npr": broker._realized_loss_today},
    }


@router.post("/autonomous/opt-in")
def autonomous_opt_in(req: AutonomousOptInRequest, user: dict = Depends(get_current_user)):
    """Arm/disarm autonomous LIVE trading for this account (still requires the global
    arm switch + paper mode off + no kill-switch before any real order is placed)."""
    from .broker_api import get_broker_api

    broker = get_broker_api()
    broker.autonomous_opt_in = bool(req.enabled)
    logger.info("Autonomous opt-in set to %s by user %s", broker.autonomous_opt_in, _uid(user))
    return {"user_opted_in": broker.autonomous_opt_in}
