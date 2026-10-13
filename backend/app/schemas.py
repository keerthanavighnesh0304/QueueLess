from datetime import datetime, date, time
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models import UserRole, HospitalStatus, SessionStatus, TicketStatus, TicketSource


# ============================================================================
# Authentication Schemas
# ============================================================================

class LoginRequest(BaseModel):
    """Schema for user login credentials."""
    email: str
    password: str


class UserOut(BaseModel):
    """
    Public representation of a user profile.
    Explicitly excludes password_hash to prevent sensitive credential exposure.
    """
    id: int
    email: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    hospital_id: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Response returned upon successful authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut


# ============================================================================
# Hospital & Onboarding Schemas
# ============================================================================

class HospitalRegisterRequest(BaseModel):
    """Schema for public hospital onboarding application."""
    name: str = Field(..., min_length=2, max_length=150)
    registration_number: str = Field(..., min_length=2, max_length=50)
    address: str = Field(..., min_length=5, max_length=255)
    city: str = Field(default="Coimbatore", min_length=2, max_length=100)
    contact_person_name: Optional[str] = Field(default=None, max_length=100)
    contact_email: Optional[str] = Field(default=None, max_length=150)
    contact_phone: Optional[str] = Field(default=None, max_length=30)
    latitude: Optional[float] = Field(default=11.016844, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=76.955832, ge=-180.0, le=180.0)
    avg_consultation_time_mins: int = Field(default=15, ge=5, le=120)


class HospitalOut(BaseModel):
    """Sanitized public and administrative representation of a hospital entity."""
    id: int
    name: str
    registration_number: str
    address: str
    city: str
    latitude: float
    longitude: float
    status: HospitalStatus
    is_accepting_bookings: bool
    avg_consultation_time_mins: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HospitalActionResponse(BaseModel):
    """Response wrapper for administrative hospital approval or rejection."""
    message: str
    hospital: HospitalOut


class StaffProvisionRequest(BaseModel):
    """Admin request to provision the first or initial manager/staff account for an approved hospital."""
    email: str = Field(..., min_length=5, max_length=150)
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=30)
    initial_password: Optional[str] = Field(default=None, min_length=8, max_length=100)


class StaffProvisionResponse(BaseModel):
    """Response returned upon provisioning a staff account (includes one-time temporary password)."""
    message: str
    user: UserOut
    temporary_password: str


# ============================================================================
# Department, Doctor & Consultation Session Schemas (Milestone 3)
# ============================================================================

class DepartmentCreateRequest(BaseModel):
    """Staff request to add a new clinical department to their hospital."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(default=None, max_length=255)


class DepartmentOut(BaseModel):
    """Public representation of a clinical department."""
    id: int
    hospital_id: int
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorCreateRequest(BaseModel):
    """Staff request to register a new doctor under a department in their hospital."""
    department_id: int
    full_name: str = Field(..., min_length=2, max_length=100)
    qualification: Optional[str] = Field(default=None, max_length=100)
    specialization: str = Field(..., min_length=2, max_length=100)
    ticket_prefix: str = Field(default="DR", min_length=1, max_length=10)
    avg_consultation_time_mins: int = Field(default=15, ge=5, le=120)


class DoctorOut(BaseModel):
    """Public representation of an active doctor."""
    id: int
    hospital_id: int
    department_id: int
    full_name: str
    qualification: Optional[str] = None
    specialization: str
    ticket_prefix: str
    avg_consultation_time_mins: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class HospitalDetailOut(HospitalOut):
    """Extended public representation of a hospital including clinical departments."""
    departments: list[DepartmentOut] = []


class ConsultationSessionOut(BaseModel):
    """Public and administrative representation of an active or scheduled OPD session."""
    id: int
    hospital_id: int
    doctor_id: int
    session_name: str
    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    status: SessionStatus
    last_sequence_number: int
    max_capacity: int

    model_config = ConfigDict(from_attributes=True)


class ConsultationSessionCreateRequest(BaseModel):
    """Staff request payload to schedule a new consultation session for a doctor."""
    doctor_id: int
    session_name: str = Field(default="OPD Session", min_length=2, max_length=100)
    session_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    max_capacity: int = Field(default=0, ge=0)


class ConsultationSessionStatusUpdateRequest(BaseModel):
    """Staff request payload to update the operational status of an OPD session."""
    status: SessionStatus


class ConsultationSessionActionResponse(BaseModel):
    """Response wrapper for consultation session status modification."""
    message: str
    session: ConsultationSessionOut


# ============================================================================
# Queue & Token Management Schemas (Milestone 4)
# ============================================================================

class TicketJoinRequest(BaseModel):
    """Payload for patient online queue registration."""
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: Optional[str] = Field(None, max_length=20)


class WalkInTicketRequest(BaseModel):
    """Payload for desk staff walk-in token issuance."""
    patient_name: str = Field(..., min_length=2, max_length=100)
    patient_phone: Optional[str] = Field(None, max_length=20)


class QueueTicketPatientOut(BaseModel):
    """
    Patient-facing representation of a queue ticket.
    Protects privacy by exposing only the patient's own metadata, dynamic queue position,
    and approximate waiting time. Excludes internal audit details and other patients' info.
    """
    id: int
    ticket_number: str
    sequence_number: int
    patient_name: str
    patient_phone: Optional[str] = None
    status: TicketStatus
    source: TicketSource
    session_id: int
    session_name: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None
    queue_position: Optional[int] = None      # 1 = next; 0 = in consultation/calling; None = finalized
    patients_ahead: Optional[int] = None      # Count of active waiting tickets ahead in queue
    estimated_wait_mins: Optional[int] = None # Approximate clinical waiting time estimate
    created_at: datetime
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class QueueTicketStaffOut(BaseModel):
    """
    Staff-facing authoritative representation of a queue ticket.
    Includes full patient identity, phone, user account link, and operational timestamps.
    """
    id: int
    session_id: int
    hospital_id: int
    doctor_id: int
    user_id: Optional[int] = None
    ticket_number: str
    sequence_number: int
    patient_name: str
    patient_phone: Optional[str] = None
    source: TicketSource
    status: TicketStatus
    created_at: datetime
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LiveQueuePublicStatusOut(BaseModel):
    """
    Public, anonymized lobby display status for a consultation session queue.
    Strictly excludes any patient names, phone numbers, or user IDs.
    """
    session_id: int
    session_name: str
    session_status: SessionStatus
    doctor_id: int
    doctor_name: str
    currently_calling_token: Optional[str] = None
    currently_serving_token: Optional[str] = None
    waiting_count: int
    total_tokens_issued: int


class LiveQueueSummaryOut(BaseModel):
    """
    Staff operational live queue dashboard for a consultation session.
    """
    session_id: int
    session_name: str
    session_status: SessionStatus
    doctor_id: int
    doctor_name: str
    hospital_id: int
    total_tokens_issued: int
    waiting_count: int
    consumed_capacity: int
    max_capacity: int
    currently_calling: Optional[QueueTicketStaffOut] = None
    currently_serving: Optional[QueueTicketStaffOut] = None
    waiting_tickets: list[QueueTicketStaffOut] = []


class TicketActionResponse(BaseModel):
    """Generic action response for ticket lifecycle transitions."""
    message: str
    ticket: QueueTicketStaffOut


class PatientTicketActionResponse(BaseModel):
    """Patient-facing action response for ticket cancellation or creation."""
    message: str
    ticket: QueueTicketPatientOut


class CallNextResponse(BaseModel):
    """Response returned when hospital staff calls next patient in queue."""
    message: str
    session_id: int
    ticket: Optional[QueueTicketStaffOut] = None
