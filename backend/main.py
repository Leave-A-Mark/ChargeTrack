import os
import uuid
import contextlib
import urllib.parse
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic import BaseModel, ConfigDict
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from pydantic import BaseModel

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database setup
DB_USER = os.getenv("DB_USER", "postgres").strip()
DB_PASSWORD = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", "postgres").strip())
DB_HOST = os.getenv("DB_HOST", "localhost").strip()
DB_PORT = os.getenv("DB_PORT", "5432").strip()
DB_NAME = os.getenv("DB_NAME", "chargetrack").strip()

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String) # For demo, storing as plain text as requested for specific credentials

class BotSubscriber(Base):
    __tablename__ = "subscribers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    equipment_id = Column(String, index=True)
    secret_code = Column(String, unique=True, index=True)
    telegram_id = Column(Integer, nullable=True)

class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, index=True)
    v1 = Column(Float)
    v2 = Column(Float)
    v3 = Column(Float)
    v4 = Column(Float)
    v5 = Column(Float)
    v6 = Column(Float)
    v7 = Column(Float)
    wifi = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.now)

class BatteryEvent(Base):
    __tablename__ = "battery_events"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, index=True)
    event_type = Column(String) # POWER_OFF, POWER_ON, CHARGE_START, DISCHARGE_START
    voltage = Column(Float)
    timestamp = Column(DateTime, default=datetime.now)

class BatterySession(Base):
    __tablename__ = "battery_sessions"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, index=True)
    type = Column(String) # CHARGE, DISCHARGE, MAINTENANCE
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    start_voltage = Column(Float)
    end_voltage = Column(Float, nullable=True)
    energy_wh = Column(Float, default=0.0)

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, unique=True, index=True)
    name = Column(String)
    v1_offset = Column(Float, default=0.0)
    v2_offset = Column(Float, default=0.0)
    v3_offset = Column(Float, default=0.0)
    v4_offset = Column(Float, default=0.0)
    v5_offset = Column(Float, default=0.0)
    v6_offset = Column(Float, default=0.0)
    v7_offset = Column(Float, default=0.0)
    active_sensors = Column(String, default="v1,v2,v3,v4,v5,v6,v7")
    battery_count = Column(Integer, default=6)
    min_voltage = Column(Float, default=22.0)
    last_v7 = Column(Float, nullable=True)
    last_state = Column(String, default="MAINTENANCE")

# Database initialization
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure existing rows have defaults for new columns
    db = SessionLocal()
    from sqlalchemy import update
    db.execute(update(Device).where(Device.min_voltage == None).values(min_voltage=22.0))
    db.execute(update(Device).where(Device.last_state == None).values(last_state="MAINTENANCE"))
    db.commit()
    db.close()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models (corrected)
class SubscriberCreate(BaseModel):
    name: str
    equipment_id: str

class SubscriberUpdate(BaseModel):
    name: Optional[str] = None
    equipment_id: Optional[str] = None

class SubscriberSchema(BaseModel):
    id: int
    name: str
    equipment_id: str
    secret_code: str
    telegram_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class LoginRequest(BaseModel):
    username: str
    password: str

# Device schemas
class DeviceSchema(BaseModel):
    id: int
    equipment_id: str
    name: str
    v1_offset: float
    v2_offset: float
    v3_offset: float
    v4_offset: float
    v5_offset: float
    v6_offset: float
    v7_offset: float
    active_sensors: str
    battery_count: Optional[int] = 6
    min_voltage: Optional[float] = 22.0
    last_v7: Optional[float] = None
    last_state: Optional[str] = "MAINTENANCE"

    model_config = ConfigDict(from_attributes=True)

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    v1_offset: Optional[float] = None
    v2_offset: Optional[float] = None
    v3_offset: Optional[float] = None
    v4_offset: Optional[float] = None
    v5_offset: Optional[float] = None
    v6_offset: Optional[float] = None
    v7_offset: Optional[float] = None
    active_sensors: Optional[str] = None
    battery_count: Optional[int] = None
    min_voltage: Optional[float] = None

class DeviceCreate(BaseModel):
    equipment_id: str
    name: str
    battery_count: int = 6

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Admin if not exists
    admin_username = os.getenv("ADMIN_USERNAME", "admin").strip()
    admin_password = os.getenv("ADMIN_PASSWORD", "admin").strip()
    db = SessionLocal()
    admin = db.query(Admin).filter(Admin.username == admin_username).first()
    if not admin:
        admin = Admin(username=admin_username, password=admin_password)
        db.add(admin)
        db.commit()
    db.close()
    yield

# FastAPI App
app = FastAPI(title="ChargeTrack API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints
@app.post("/api/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == request.username, Admin.password == request.password).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "success", "auth": True}

@app.get("/api/subscribers", response_model=List[SubscriberSchema])
def get_subscribers(db: Session = Depends(get_db)):
    return db.query(BotSubscriber).all()

# Device Endpoints
@app.get("/api/devices", response_model=List[DeviceSchema])
def get_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()

@app.post("/api/devices", response_model=DeviceSchema)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    db_device = db.query(Device).filter(Device.equipment_id == device.equipment_id).first()
    if db_device:
        raise HTTPException(status_code=400, detail="Device with this ID already exists")
    
    db_device = Device(
        equipment_id=device.equipment_id,
        name=device.name,
        battery_count=device.battery_count
    )
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@app.put("/api/devices/{device_id}", response_model=DeviceSchema)
def update_device(device_id: int, update: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    update_data = update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(device, key, value)
    
    db.commit()
    db.refresh(device)
    return device

@app.delete("/api/devices/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Видаляємо всі дані сенсорів для цього обладнання
    db.query(SensorData).filter(SensorData.equipment_id == device.equipment_id).delete()
    
    db.delete(device)
    db.commit()
    return {"status": "success"}

@app.post("/api/subscribers", response_model=SubscriberSchema)
def create_subscriber(sub: SubscriberCreate, db: Session = Depends(get_db)):
    secret_code = str(uuid.uuid4())[:8].upper()
    db_sub = BotSubscriber(
        name=sub.name,
        equipment_id=sub.equipment_id,
        secret_code=secret_code
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

@app.put("/api/subscribers/{sub_id}", response_model=SubscriberSchema)
def update_subscriber(sub_id: int, sub: SubscriberUpdate, db: Session = Depends(get_db)):
    db_sub = db.query(BotSubscriber).filter(BotSubscriber.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    if sub.name:
        db_sub.name = sub.name
    if sub.equipment_id:
        db_sub.equipment_id = sub.equipment_id
        
    db.commit()
    db.refresh(db_sub)
    return db_sub

@app.delete("/api/subscribers/{sub_id}")
def delete_subscriber(sub_id: int, db: Session = Depends(get_db)):
    db_sub = db.query(BotSubscriber).filter(BotSubscriber.id == sub_id).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    db.delete(db_sub)
    db.commit()
    return {"status": "success"}

# Mock Data Generation Helper
def generate_mock_data(equipment_id: str) -> dict:
    import random
    data = {
        "equipment_id": equipment_id,
        "v1": round(random.uniform(26.0, 27.0), 2),
        "v2": round(random.uniform(0.1, 0.4), 2),
        "v3": round(random.uniform(26.0, 27.0), 2),
        "v4": round(random.uniform(0.1, 0.4), 2),
        "v5": round(random.uniform(26.0, 27.0), 2),
        "v6": round(random.uniform(0.1, 0.4), 2),
        "v7": round(random.uniform(26.0, 27.0), 2)
    }
    return data

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
