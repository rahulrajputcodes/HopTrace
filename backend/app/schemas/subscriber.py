"""
Pydantic schemas for subscriber and payment reminder operations.

Follows docs/api-contract.md Section 8 and Section 9.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Subscriber Item & Listing ────────────────────────────────────────────────

class SubscriberItem(BaseModel):
    id: str = Field(..., description="Unique subscriber identifier (e.g. SUB101)")
    display_name: str = Field(..., description="Subscriber name / label")
    plan: str = Field(..., description="Subscription plan name")
    plan_price: float = Field(default=399.0, description="Monthly plan price in INR")
    phone: Optional[str] = Field("+919876543200", description="Subscriber phone number")
    preferred_language: Optional[str] = Field("hi", description="Preferred notification language")
    access_point_id: str = Field(..., description="ID of connected access point")
    status: str = Field(..., description="Subscriber status (e.g. active, suspended)")
    payment_status: str = Field(..., description="Payment status (e.g. paid, overdue, pending)")
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")


class SubscriberListResponse(BaseModel):
    subscribers: list[SubscriberItem] = Field(
        ...,
        description="List of subscribers. Empty list if no subscribers exist.",
    )


# ── Payment Reminder ─────────────────────────────────────────────────────────

# Supported languages policy:
# "hi" (Hindi) is the primary language demonstrated for hackFront India (Sarvam integration demo).
# "en" (English) is also supported as standard telecom language.
# Invalid language codes are rejected by Pydantic validation with HTTP 422.
SupportedLanguage = Literal["hi", "en"]


class ReminderRequest(BaseModel):
    language: SupportedLanguage = Field(
        ...,
        description="Language code for the reminder (supported: 'hi', 'en')",
        examples=["hi"],
    )


class ReminderResponse(BaseModel):
    subscriber_id: str = Field(..., description="Target subscriber ID")
    status: str = Field(
        default="recorded",
        description="Recording status of the reminder action",
    )
    delivery_status: str = Field(
        default="not_sent",
        description="Delivery status. Prototype defaults to 'not_sent' until messaging is integrated.",
    )
