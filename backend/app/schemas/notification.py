"""
Pydantic schemas for outage notification preview and dispatch endpoints.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

ChannelType = Literal["sms", "whatsapp"]


class NotificationPreviewItem(BaseModel):
    subscriber_id: str = Field(..., description="Unique subscriber ID (e.g. SUB101)")
    subscriber_name: str = Field(..., description="Subscriber display name")
    phone: str = Field(..., description="Destination phone number")
    preferred_language: str = Field(..., description="Subscriber preferred language code (e.g. 'hi', 'en')")
    channel: str = Field("sms", description="Delivery channel ('sms' or 'whatsapp')")
    message: str = Field(..., description="Personalized alert message in preferred language")


class NotificationPreviewResponse(BaseModel):
    incident_id: str = Field(..., description="Incident ID")
    channel: str = Field("sms", description="Target delivery channel")
    affected_subscribers_count: int = Field(..., description="Count of affected subscribers")
    previews: List[NotificationPreviewItem] = Field(..., description="Preview items per subscriber")


class NotificationSendRequest(BaseModel):
    channel: ChannelType = Field("sms", description="Delivery channel: 'sms' or 'whatsapp'")
    subscriber_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of subscriber IDs to target. If omitted, sends to all affected subscribers.",
    )


class NotificationDeliveryItem(BaseModel):
    subscriber_id: str = Field(..., description="Target subscriber ID")
    recipient: str = Field(..., description="Recipient phone number")
    status: str = Field(..., description="Delivery status ('sent', 'delivered', 'failed')")
    message_id: Optional[str] = Field(None, description="External or internal message tracking ID")
    channel: str = Field(..., description="Channel used ('sms' or 'whatsapp')")
    provider: str = Field(..., description="Provider used ('console', 'twilio')")
    message: str = Field(..., description="Message text delivered")
    error: Optional[str] = Field(None, description="Error detail if delivery failed")


class NotificationSendResponse(BaseModel):
    incident_id: str = Field(..., description="Incident ID")
    provider: str = Field(..., description="Provider used ('console', 'twilio')")
    channel: str = Field(..., description="Delivery channel ('sms', 'whatsapp')")
    total_targeted: int = Field(..., description="Total target subscriber count")
    sent_count: int = Field(..., description="Successfully dispatched count")
    failed_count: int = Field(..., description="Failed dispatch count")
    deliveries: List[NotificationDeliveryItem] = Field(..., description="Detailed delivery results")
