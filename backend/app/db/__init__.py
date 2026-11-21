"""
Database package for HopTrace.
"""
from app.db.connection import get_db, get_db_connection
from app.db.init import DEMO_INCIDENTS, DEMO_SUBSCRIBERS, init_db
from app.db.repository import (
    create_incident,
    close_open_incidents,
    get_incident,
    get_latest_incident,
    get_latest_open_incident,
    get_reminders_for_subscriber,
    get_subscriber,
    get_subscribers_by_access_points,
    list_subscribers,
    record_payment_reminder,
)

__all__ = [
    "get_db",
    "get_db_connection",
    "init_db",
    "DEMO_SUBSCRIBERS",
    "DEMO_INCIDENTS",
    "list_subscribers",
    "get_subscriber",
    "get_subscribers_by_access_points",
    "record_payment_reminder",
    "get_reminders_for_subscriber",
    "get_latest_incident",
    "get_latest_open_incident",
    "get_incident",
    "create_incident",
    "close_open_incidents",
]
