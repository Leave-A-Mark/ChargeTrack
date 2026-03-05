from flask import Flask, request, jsonify
from sqlalchemy.orm import Session
from datetime import datetime, UTC
import pytz
from main import SessionLocal, SensorData, init_db, Device

# Ensure DB tables are created
init_db()

app = Flask(__name__)

def apply_voltage_correction(db: Session, device_id: str, sensor_id: str, voltage: float):
    """Применить коррекцию напряжения для указанного датчика устройства из БД"""
    try:
        device = db.query(Device).filter(Device.equipment_id == device_id).first()
        if device:
            # Получаем коррекцию из соответствующего поля модели
            offset_field = f"{sensor_id}_offset"
            correction = getattr(device, offset_field, 0.0)
            return voltage + correction
    except Exception as e:
        print(f"Ошибка при применении коррекции для {device_id} датчик {sensor_id}: {e}")
    
    return voltage

def safe_float(value, default=-1.0):
    """Безопасно преобразует значение в float, обрабатывая запятые и списки"""
    if value is None:
        return default
    
    # Если пришел список (PowerShell может так отправлять), берем первый элемент
    if isinstance(value, (list, tuple)) and len(value) > 0:
        value = value[0]
    
    try:
        # Очищаем от пробелов и заменяем запятую на точку
        s_val = str(value).strip().replace(',', '.')
        return float(s_val)
    except (ValueError, TypeError):
        print(f"DEBUG: Failed to parse float from: {repr(value)}")
        return default

def ensure_device_exists(db: Session, device_id: str):
    """Проверяет наличие устройства в базе данных и добавляет его при необходимости з дефолтними значеннями"""
    try:
        device = db.query(Device).filter(Device.equipment_id == device_id).first()
        if not device:
            device = Device(
                equipment_id=device_id,
                name=device_id,
                v1_offset=0.0,
                v2_offset=0.0,
                v3_offset=0.0,
                v4_offset=0.0,
                v5_offset=0.0,
                v6_offset=0.0,
                v7_offset=0.0,
                active_sensors="v1,v2,v3,v4,v5,v6,v7"
            )
            db.add(device)
            db.commit()
    except Exception as e:
        print(f"Ошибка при проверке устройства {device_id}: {e}")

@app.route('/push', methods=['POST'])
def push_data():
    data = request.form
    print(f"DEBUG: Received data: {dict(data)}")
    
    # Пытаемся достать значения более надежно для мульти-велью полей
    def get_first_value(key):
        vals = data.getlist(key)
        if not vals: 
            return data.get(key) # fallback
        return vals[0]

    device = get_first_value("device")
    if not device:
        return "Missing device name", 400

    try:
        db = SessionLocal()
        ensure_device_exists(db, device)

        wifi_signal = int(safe_float(get_first_value("wifi"), 0))
        v2 = safe_float(get_first_value("v2"))
        v4 = safe_float(get_first_value("v4"))
        v6 = safe_float(get_first_value("v6"))
        v7 = safe_float(get_first_value("v7"))
        
        v2_c = apply_voltage_correction(db, device, "v2", v2)
        v4_c = apply_voltage_correction(db, device, "v4", v4)
        v6_c = apply_voltage_correction(db, device, "v6", v6)
        v7_c = apply_voltage_correction(db, device, "v7", v7)
        
        v1_c = apply_voltage_correction(db, device, "v1", v7_c - v2_c)
        v3_c = apply_voltage_correction(db, device, "v3", v7_c - v4_c)
        v5_c = apply_voltage_correction(db, device, "v5", v7_c - v6_c)
        entry = SensorData(
            equipment_id=device,
            v1=round(v1_c, 2), v2=round(v2_c, 2),
            v3=round(v3_c, 2), v4=round(v4_c, 2),
            v5=round(v5_c, 2), v6=round(v6_c, 2),
            v7=round(v7_c, 2),
            wifi=wifi_signal,
            timestamp=datetime.now(UTC)
        )
        db.add(entry)
        db.commit()
        db.close()

        # Log to console
        local_tz = pytz.timezone('Europe/Kiev')
        local_time = datetime.now(local_tz)
        print(f"[{local_time.strftime('%Y-%m-%d %H:%M:%S')}] Saved data for '{device}' to DB.")
        
    except Exception as e:
        print(f"Error processing push: {e}")
        return str(e), 400

    return jsonify({"status": "ok"}), 200

@app.route('/data', methods=['GET'])
def get_data():
    device_filter = request.args.get("device")
    db = SessionLocal()
    query = db.query(SensorData)
    if device_filter:
        query = query.filter(SensorData.equipment_id == device_filter)
    
    # Return last 100 entries
    results = query.order_by(SensorData.timestamp.desc()).limit(100).all()
    db.close()
    
    data = []
    for r in results:
        data.append({
            "time": r.timestamp.isoformat(),
            "v1": r.v1, "v2": r.v2, "v3": r.v3,
            "v4": r.v4, "v5": r.v5, "v6": r.v6, "v7": r.v7,
            "wifi": r.wifi
        })
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8089)