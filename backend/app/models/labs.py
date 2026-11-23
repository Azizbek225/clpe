import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin, SoftDeleteMixin, TimestampMixin


class MachineTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "machine_templates"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    operating_system: Mapped[str] = mapped_column(String(100))
    image_reference: Mapped[str] = mapped_column(String(300))
    image_version: Mapped[str] = mapped_column(String(50), default="latest")
    image_checksum: Mapped[str | None] = mapped_column(String(200))
    virtualization_provider: Mapped[str] = mapped_column(String(20))  # docker | virtualbox | libvirt
    role: Mapped[str] = mapped_column(String(20), default="target")  # attacker | target | defender
    default_cpu: Mapped[float] = mapped_column(default=1.0)
    default_ram: Mapped[int] = mapped_column(Integer, default=512)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)  # mock_ports, console shell va h.k.


class LabTemplate(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    """YAML manifestdan yaratilgan laboratoriya. configuration_json = to'liq tekshirilgan manifest."""
    __tablename__ = "lab_templates"
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    lab_type: Mapped[str] = mapped_column(String(30), default="offensive")
    category: Mapped[str] = mapped_column(String(50), default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    configuration_json: Mapped[dict] = mapped_column(JSON)
    manifest_yaml: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="published")
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))


class InfrastructureHost(IdMixin, TimestampMixin, Base):
    __tablename__ = "infrastructure_hosts"
    hostname: Mapped[str] = mapped_column(String(200), unique=True)
    operating_system: Mapped[str] = mapped_column(String(50))
    virtualization_provider: Mapped[str] = mapped_column(String(20))
    total_cpu: Mapped[int] = mapped_column(Integer, default=8)
    total_ram: Mapped[int] = mapped_column(Integer, default=16384)
    available_status: Mapped[str] = mapped_column(String(20), default="online")


class LabInstance(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_instances"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_templates.id"))
    host_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("infrastructure_hosts.id"))
    instance_name: Mapped[str] = mapped_column(String(100), unique=True)
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="CREATED")
    error: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    template: Mapped[LabTemplate] = relationship(lazy="selectin")
    machines: Mapped[list["LabMachine"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    networks: Mapped[list["LabNetwork"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class LabMachine(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_machines"
    lab_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_instances.id", ondelete="CASCADE"), index=True)
    machine_template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("machine_templates.id"))
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(20), default="target")
    vm_identifier: Mapped[str | None] = mapped_column(String(200))
    operating_system: Mapped[str] = mapped_column(String(100), default="")
    ip_addresses: Mapped[dict] = mapped_column(JSON, default=dict)  # {network_name: ip}
    cpu_limit: Mapped[float] = mapped_column(default=1.0)
    ram_limit: Mapped[int] = mapped_column(Integer, default=512)
    storage_limit: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="CREATED")
    snapshots: Mapped[list["LabSnapshot"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class LabSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_snapshots"
    lab_machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_machines.id", ondelete="CASCADE"), index=True)
    snapshot_name: Mapped[str] = mapped_column(String(100))
    snapshot_identifier: Mapped[str] = mapped_column(String(300))


class LabNetwork(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_networks"
    lab_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_instances.id", ondelete="CASCADE"), index=True)
    network_name: Mapped[str] = mapped_column(String(64))
    provider_identifier: Mapped[str | None] = mapped_column(String(200))
    network_type: Mapped[str] = mapped_column(String(20), default="isolated")
    cidr: Mapped[str] = mapped_column(String(32))
    isolation_policy: Mapped[str] = mapped_column(String(30), default="no-internet")


class LabTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_tasks"
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_templates.id", ondelete="CASCADE"), index=True)
    task_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    validation_type: Mapped[str] = mapped_column(String(50))
    validation_configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    max_score: Mapped[int] = mapped_column(Integer, default=10)


class LabSubmission(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_submissions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lab_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_instances.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_tasks.id", ondelete="CASCADE"))
    submitted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(default=False)
    feedback: Mapped[str] = mapped_column(Text, default="")


class LabEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "lab_events"
    lab_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_instances.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    event_details: Mapped[dict] = mapped_column(JSON, default=dict)


class LabScan(IdMixin, TimestampMixin, Base):
    """Skan natijasi (nmap XML'dan) — tarmoq topologiyasi grafigi shu yerdan quriladi."""
    __tablename__ = "lab_scans"
    lab_instance_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_instances.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    source: Mapped[str] = mapped_column(String(20), default="engine")  # engine | import
    target: Mapped[str] = mapped_column(String(64))
    profile: Mapped[str] = mapped_column(String(20), default="quick")
    hosts: Mapped[list] = mapped_column(JSON, default=list)
