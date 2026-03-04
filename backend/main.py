import os
import uuid
import urllib.parse
from typing import List, Optional
from datetime import datetime, UTC
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
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
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

# Database initialization
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()

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

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

# FastAPI App
app = FastAPI(title="ChargeTrack API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Admin if not exists
@app.on_event("startup")
def startup_event():
    admin_username = os.getenv("ADMIN_USERNAME").strip()
    admin_password = os.getenv("ADMIN_PASSWORD").strip()
    db = SessionLocal()
    admin = db.query(Admin).filter(Admin.username == admin_username).first()
    if not admin:
        admin = Admin(username=admin_username, password=admin_password)
        db.add(admin)
        db.commit()
    db.close()

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
