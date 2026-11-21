"""
Pydantic schemas for outage notification preview, dispatch, history, and voice endpoints (M3).
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

ChannelType = Literal["sms", "whatsapp"]
KindType = Literal["outage", "restored", "village_status"]


class NotificationPreviewItem(BaseModel):
    subscriber_id: str = Field(..., description="Unique subscriber ID (e.g. SUB101)")
    subscriber_name: str = Field(..., description="Subscriber display name")
    phone: str = Field(..., description="Destination phone number")
    preferred_language: str = Field(..., description="Subscriber preferred language code (e.g. 'hi', 'en')")
    channel: str = Field("sms", description="Delivery channel ('sms' or 'whatsapp')")
    message: str = Field(..., description="Personalized alert message in preferred language")
    message_source: str = Field("template", description="Source of message ('template' or 'sarvam')")
    village: Optional[str] = Field(None, description="Subscriber associated village")
    eligible: bool = Field(True, description="Whether subscriber is eligible for notifications")


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
    kind: KindType = Field("outage", description="Notification kind: 'outage' or 'restored'")
    translate: bool = Field(False, description="Whether to request Sarvam AI translation")


class NotificationDeliveryItem(BaseModel):
    subscriber_id: str = Field(..., description="Target subscriber ID")
    recipient: str = Field(..., description="Recipient phone number")
    status: str = Field(..., description="Delivery status ('queued', 'sent', 'delivered', 'failed')")
    message_id: Optional[str] = Field(None, description="External or internal message tracking ID")
    channel: str = Field("sms", description="Channel used ('sms' or 'whatsapp')")
    provider: str = Field("console", description="Provider used ('console', 'twilio')")
    message: str = Field(..., description="Message text delivered")
    message_source: str = Field("template", description="Source of message ('template' or 'sarvam')")
    error: Optional[str] = Field(None, description="Error detail if delivery failed")
    updated_at: Optional[str] = Field(None, description="Timestamp of delivery attempt")
    subscriber_name: Optional[str] = Field(None, description="Subscriber display name")
    language: Optional[str] = Field(None, description="Language used")


class NotificationSendResponse(BaseModel):
    incident_id: str = Field(..., description="Incident ID")
    provider: str = Field(..., description="Provider used ('console', 'twilio')")
    channel: str = Field(..., description="Delivery channel ('sms', 'whatsapp')")
    total_targeted: int = Field(..., description="Total target subscriber count")
    sent_count: int = Field(..., description="Successfully dispatched count")
    failed_count: int = Field(..., description="Failed dispatch count")
    deliveries: List[NotificationDeliveryItem] = Field(..., description="Detailed delivery results")
    deduplicated: bool = Field(False, description="True if request was deduplicated via Idempotency-Key")
    batch_id: Optional[str] = Field(None, description="Persisted batch identifier")
    kind: Optional[str] = Field("outage", description="Notification kind")


class NotificationBatchItem(BaseModel):
    id: str = Field(..., description="Batch identifier")
    incident_id: str = Field(..., description="Incident ID")
    kind: str = Field(..., description="Notification kind ('outage', 'restored')")
    channel: str = Field(..., description="Channel ('sms', 'whatsapp')")
    provider: str = Field(..., description="Provider used")
    created_at: str = Field(..., description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="Operator or creator identifier")
    deliveries: List[NotificationDeliveryItem] = Field(default_factory=list, description="Deliveries in batch")


class NotificationHistoryResponse(BaseModel):
    incident_id: str = Field(..., description="Incident ID")
    batches: List[NotificationBatchItem] = Field(default_factory=list, description="Batches newest first")


class NotificationStatusResponse(BaseModel):
    provider: str = Field(..., description="Configured notification provider")
    real_send_allowlist_count: int = Field(0, description="Count of allowlisted phone numbers")
    sarvam_configured: bool = Field(False, description="Whether Sarvam API key is configured")
    twilio_configured: bool = Field(False, description="Whether Twilio credentials are configured")


class VoiceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Text to synthesize")
    language: str = Field("hi", description="Language code ('hi', 'en', etc.)")
    speaker: Optional[str] = Field("meera", description="Speaker persona")


class VoiceResponse(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio bytes")
    mime: str = Field("audio/wav", description="Audio MIME type")
    provider: str = Field("sarvam", description="Speech provider identifier")
