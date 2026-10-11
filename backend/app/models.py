import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Boolean,
    Date,
    Time,
    DateTime,
    Enum,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ============================================================================
# Enums for Type Safety and Status Tracking
# ============================================================================

class HospitalStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class TicketSource(str, enum.Enum):
    ONLINE = "ONLINE"
    WALK_IN = "WALK_IN"


class TicketStatus(str, enum.Enum):
    WAITING = "WAITING"
    CALLING = "CALLING"
    IN_CONSULTATION = "IN_CONSULTATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


# ============================================================================
# Database Entities (ORM Models)
# ============================================================================

class Hospital(Base):
    """
    Healthcare facility entity. Must be approved by a system admin before
    it appears in patient search or accepts bookings.
    """
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    registration_number = Column(String(50), unique=True, nullable=False, index=True)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, default="Coimbatore")
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    status = Column(
        Enum(HospitalStatus),
        nullable=False,
        default=HospitalStatus.PENDING_APPROVAL,
        index=True,
    )
    is_accepting_bookings = Column(Boolean, nullable=False, default=False)
    avg_consultation_time_mins = Column(Integer, nullable=False, default=15)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    departments = relationship("Department", back_populates="hospital", cascade="all, delete-orphan")
    doctors = relationship("Doctor", back_populates="hospital", cascade="all, delete-orphan")
    sessions = relationship("ConsultationSession", back_populates="hospital", cascade="all, delete-orphan")
    tickets = relationship("QueueTicket", back_populates="hospital", cascade="all, delete-orphan")
    staff_members = relationship("User", back_populates="hospital")


class Department(Base):
    """
    Clinical department within a hospital (e.g. Cardiology, General Medicine, Pediatrics).
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    # Relationships
    hospital = relationship("Hospital", back_populates="departments")
    doctors = relationship("Doctor", back_populates="department", cascade="all, delete-orphan")


class Doctor(Base):
    """
    Doctor practicing within a hospital department.
    """
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    qualification = Column(String(100), nullable=True)
    specialization = Column(String(100), nullable=False)
    ticket_prefix = Column(String(10), nullable=False, default="DR")
    avg_consultation_time_mins = Column(Integer, nullable=False, default=15)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    hospital = relationship("Hospital", back_populates="doctors")
    department = relationship("Department", back_populates="doctors")
    sessions = relationship("ConsultationSession", back_populates="doctor", cascade="all, delete-orphan")
    tickets = relationship("QueueTicket", back_populates="doctor", cascade="all, delete-orphan")


class ConsultationSession(Base):
    """
    An active queue session for a doctor on a specific date (e.g., Morning OPD 09:00 - 13:00).
    The last_sequence_number field is atomically incremented via database row locks (FOR UPDATE)
    to safely generate sequential ticket numbers without race conditions.
    """
    __tablename__ = "consultation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    session_name = Column(String(100), nullable=False, default="OPD Session")
    session_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE, index=True)
    last_sequence_number = Column(Integer, nullable=False, default=0)
    max_capacity = Column(Integer, nullable=False, default=0)  # 0 indicates no artificial limit

    # Relationships
    hospital = relationship("Hospital", back_populates="sessions")
    doctor = relationship("Doctor", back_populates="sessions")
    tickets = relationship("QueueTicket", back_populates="session", cascade="all, delete-orphan")


class User(Base):
    """
    Application user account. Supports Role-Based Access Control (PATIENT, STAFF, ADMIN).
    Staff users are strictly bound to their hospital via hospital_id.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PATIENT, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    hospital = relationship("Hospital", back_populates="staff_members")
    tickets = relationship("QueueTicket", back_populates="user")


class QueueTicket(Base):
    """
    An authoritative queue ticket representing an online booking or staff-entered walk-in.
    Enforces strict sequence order within a session.
    """
    __tablename__ = "queue_tickets"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    ticket_number = Column(String(20), nullable=False)  # Formatted token: e.g. "DR1-014"
    sequence_number = Column(Integer, nullable=False)   # Numeric sequence: 1, 2, 3...
    patient_name = Column(String(100), nullable=False)
    patient_phone = Column(String(20), nullable=True)
    source = Column(Enum(TicketSource), nullable=False, default=TicketSource.ONLINE)
    status = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.WAITING, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    called_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("ConsultationSession", back_populates="tickets")
    hospital = relationship("Hospital", back_populates="tickets")
    doctor = relationship("Doctor", back_populates="tickets")
    user = relationship("User", back_populates="tickets")

    # Constraints and compound indexes for fast lookups and isolation
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_session_sequence"),
        Index("idx_hospital_status", "hospital_id", "status"),
        Index("idx_session_status", "session_id", "status"),
        Index("idx_user_status", "user_id", "status"),
    )
