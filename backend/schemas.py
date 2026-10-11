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
    facility_slug: str = Field(min_length=1)


class LoginRequest(BaseModel):
    phone: str
    password: str
    facility_slug: Optional[str] = None


class PasswordResetRequest(BaseModel):
    phone: str


class PasswordResetConfirm(BaseModel):
    phone: str
    code: str = Field(min_length=4)
    password: str = Field(min_length=6)


class InviteRequest(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    role: str = "attendant"


class AcceptInviteRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4)
    password: str = Field(min_length=6)
    facility_slug: str


class SessionUser(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str] = None
    role: str
    facility_id: int
    facility_name: str
    facility_slug: str


class FacilityChoice(BaseModel):
    facility_id: int
    facility_name: str
    facility_slug: str
    role: str


class AuthResponse(BaseModel):
    user: Optional[SessionUser] = None
    needs_facility: bool = False
    memberships: list[FacilityChoice] = []
    debug_code: Optional[str] = None


class InviteResponse(BaseModel):
    phone: str
    role: str
    facility_slug: str
    code: str


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
    parent_visible: bool = False


class IncidentOut(BaseModel):
    id: int
    dog_id: int
    staff_id: int
    type: str
    severity: str
    description: str
    parent_visible: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusUpdate(BaseModel):
    status: str  # "checked_in" | "checked_out"
    belongings: str = ""
    diet_confirmed: bool = False
    meds_confirmed: bool = False
    vet_confirmed: bool = False
    kennel_id: Optional[int] = None
    acknowledge_severe: bool = False


class ActivityUpdate(BaseModel):
    activity: str  # "walk" | "feed" | "meds"


class ChatRequest(BaseModel):
    message: str
    thread_id: str


# --- Owner-mode requests ---


class CreateDogRequest(BaseModel):
    name: str = Field(min_length=1)
    breed: str = Field(min_length=1)
    age_years: int = Field(ge=0, le=30)
    weight_kg: float = Field(gt=0, le=100)
    diet: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None
    vaccination_status: str = Field(default="up_to_date")
    vaccination_expires: Optional[date] = None
    vet_contact: Optional[str] = None
    notes: Optional[str] = None


class CreateBookingRequest(BaseModel):
    dog_id: int
    start_date: date
    end_date: date
    kennel_id: Optional[str] = None
    waiver_accepted: bool = False
    override: bool = False
    override_reason: Optional[str] = None


class DecisionIn(BaseModel):
    action: str


class KennelIn(BaseModel):
    name: str = Field(min_length=1)
    status: str = "available"


class KennelPatch(BaseModel):
    status: str


class KennelOut(BaseModel):
    id: int
    name: str
    status: str

    model_config = {"from_attributes": True}


class VaccinationIn(BaseModel):
    vaccine_type: str = Field(min_length=1)
    expires_on: date


class VaccinationOut(BaseModel):
    id: int
    dog_id: int
    vaccine_type: str
    expires_on: date

    model_config = {"from_attributes": True}


class QueueItem(BaseModel):
    booking: BookingOut
    dog_name: str
    owner_name: str


class OwnerOut(BaseModel):
    id: int
    name: str
    phone: str
    created_at: datetime
    dog_count: int


class AuditLogOut(BaseModel):
    id: int
    staff_id: int
    staff_name: Optional[str] = None
    action: str
    target_type: str
    target_id: int
    details: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


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
