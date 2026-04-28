from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id         = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(200), nullable=False)
    user_name  = Column(String(200), default="")
    action     = Column(String(100), nullable=False)
    details    = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Configuration(Base):
    __tablename__ = "configurations"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=False)
    description = Column(String(300), default="")
    category = Column(String(100), default="general")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class System(Base):
    __tablename__ = "systems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(300), default="")
    criticality = Column(String(10), default="media")   # alta | media | baixa
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incidents = relationship("Incident", back_populates="system")


class IncidentType(Base):
    __tablename__ = "incident_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(300), default="")
    active = Column(Boolean, default=True)

    incidents = relationship("Incident", back_populates="incident_type")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")

    system_id = Column(Integer, ForeignKey("systems.id"), nullable=False)
    incident_type_id = Column(Integer, ForeignKey("incident_types.id"), nullable=False)

    priority = Column(String(5), nullable=False)        # P1 | P2 | P3 | P4
    status = Column(String(20), default="Aberto")       # Aberto | Em Andamento | Resolvido

    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    # Calculated and stored on save/update
    duration_minutes = Column(Float, nullable=True)
    production_loss = Column(Float, nullable=True)
    financial_loss = Column(Float, nullable=True)

    root_cause = Column(Text, default="")
    resolution_notes = Column(Text, default="")
    affected_users = Column(Integer, default=0)

    created_by = Column(String(100), default="sistema")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    system = relationship("System", back_populates="incidents")
    incident_type = relationship("IncidentType", back_populates="incidents")
