from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class PagoResponse(BaseModel):
    id: int
    pedido_id: int
    mp_payment_id: Optional[int] = None
    mp_status: str
    mp_status_detail: Optional[str] = None
    external_reference: str
    transaction_amount: Decimal
    payment_method_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
