"""Единая инициализация аутентифицированного ClobClient (V2) для auto-скриптов и executor."""
from __future__ import annotations

from config import Settings


def authenticated_clob_client(settings: Settings, signature_type: int | None = None):
    """CLOB с подписью и funder; время сервера — для корректного timestamp в ордерах (V2)."""
    from py_clob_client_v2 import ClobClient

    sig = (
        int(signature_type)
        if signature_type is not None
        else int(getattr(settings, "polymarket_signature_type", 0) or 0)
    )
    return ClobClient(
        settings.clob_api_url.rstrip("/"),
        chain_id=settings.chain_id,
        key=settings.polymarket_private_key,
        signature_type=sig,
        funder=settings.polymarket_funder_address,
        use_server_time=True,
        retry_on_error=True,
    )
