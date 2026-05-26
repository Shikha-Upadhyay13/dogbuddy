"""Pydantic v2 request/response schemas. Shapes locked by PRD Section 6."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Auth ---

class SignupRequest(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    phone: str
    password: str


class StaffOut(BaseModel):
    id: int
    name: str
    phone: str

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    staff: StaffOut


# --- Dogs / bookings / incidents (for Phase 2) ---

class DogOut(BaseModel):
    id: int
    name: str
    breed: str
    age_years: int
    weight_kg: float
    diet: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None
    vaccination_status: str
    vaccination_expires: Optional[date] = None
    owner_name: str
    owner_phone: str
    vet_contact: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class BookingOut(BaseModel):
    id: int
    dog_id: int
    start_date: date
    end_date: date
    status: str
    kennel_id: Optional[str] = None
    last_walked_at: Optional[datetime] = None
    last_fed_at: Optional[datetime] = None
    last_meds_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IncidentIn(BaseModel):
    dog_id: int
    type: str
    severity: str
    description: str


class IncidentOut(BaseModel):
    id: int
    dog_id: int
    staff_id: int
    type: str
    severity: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    status: str  # "checked_in" | "in_care" | "checked_out"


class ActivityUpdate(BaseModel):
    activity: str  # "walk" | "feed" | "meds"


class ChatRequest(BaseModel):
    message: str
    thread_id: str


# --- Dashboard / detail composites ---

class DogDetailOut(DogOut):
    current_booking: Optional[BookingOut] = None
    recent_incidents: list[IncidentOut] = []


class TodayBookingItem(BaseModel):
    booking_id: int
    dog: DogOut
    kennel_id: Optional[str] = None
    status: str
    last_walked_at: Optional[datetime] = None
    last_fed_at: Optional[datetime] = None
    last_meds_at: Optional[datetime] = None


class BookingsTodayOut(BaseModel):
    checking_in: list[TodayBookingItem]
    in_care: list[TodayBookingItem]
    checking_out: list[TodayBookingItem]
