import os
import pytz
from datetime import datetime, timedelta, UTC
from flask import Flask, request, jsonify
from sqlalchemy.orm import Session
from main import SessionLocal, SensorData, init_db

# Ensure DB tables are created
init_db()

app = Flask(__name__)

def apply_voltage_correction(device_id, sensor_id, voltage):
    """Применить коррекцию напряжения для указанного датчика устройства"""
    try:
        # Импортируем конфигурацию
        import config
        import importlib
        importlib.reload(config)
        
        # Проверяем наличие устройства и датчика в коррекциях
        if device_id in config.VOLTAGE_CORRECTIONS:
            corrections = config.VOLTAGE_CORRECTIONS[device_id]
            if sensor_id in corrections:
                correction = corrections[sensor_id]
                return voltage + correction
    except Exception as e:
        print(f"Ошибка при применении коррекции для {device_id} датчик {sensor_id}: {e}")
    
    return voltage

def ensure_device_in_config(device_id):
    """Проверяет наличие устройства в конфигурации и добавляет его при необходимости"""
    try:
        import config
        if device_id not in config.DEVICE_NAME_MAPPING:
            update_config_file(device_id)
    except Exception as e:
        print(f"Ошибка при проверке устройства {device_id}: {e}")

def update_config_file(device_id):
    """Обновляет конфигурационный файл, добавляя новое устройство"""
    try:
        config_path = "config.py"
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        mapping_added = False
        corrections_added = False
        active_sensors_added = False
        
        current_section = None
        for line in lines:
            new_lines.append(line)
            if "DEVICE_NAME_MAPPING = {" in line:
                current_section = "mapping"
            elif "VOLTAGE_CORRECTIONS = {" in line:
                current_section = "corrections"
            elif "ACTIVE_SENSORS = {" in line:
                current_section = "active"
            
            if current_section == "mapping" and line.strip() == "}":
                if not mapping_added:
                    new_lines.insert(-1, f'    "{device_id}": "{device_id}",\n')
                current_section = None
            elif current_section == "corrections" and line.strip() == "}":
                if not corrections_added:
                    new_lines.insert(-1, f'    "{device_id}": {{\n')
                    for v in ["v1", "v2", "v3", "v4", "v5", "v6", "v7"]:
                        new_lines.insert(-1, f'        "{v}": 0.00,\n')
                    new_lines.insert(-1, f'    }},\n')
                current_section = None
            elif current_section == "active" and line.strip() == "}":
                if not active_sensors_added:
                    new_lines.insert(-1, f'    "{device_id}": ["v1", "v2", "v3", "v4", "v5", "v6", "v7"],\n')
                current_section = None

            if f'"{device_id}":' in line:
                if current_section == "mapping": mapping_added = True
                elif current_section == "corrections": corrections_added = True
                elif current_section == "active": active_sensors_added = True

        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Ошибка при обновлении конфигурации: {e}")

@app.route('/push', methods=['POST'])
def push_data():
    data = request.form
    device = data.get("device")
    if not device:
        return "Missing device name", 400

    try:
        wifi_signal = int(data.get("wifi", 0))
        v2 = float(data.get("v2", -1.0))
        v4 = float(data.get("v4", -1.0))
        v6 = float(data.get("v6", -1.0))
        v7 = float(data.get("v7", -1.0))
        
        v2_c = apply_voltage_correction(device, "v2", v2)
        v4_c = apply_voltage_correction(device, "v4", v4)
        v6_c = apply_voltage_correction(device, "v6", v6)
        v7_c = apply_voltage_correction(device, "v7", v7)
        
        v1_c = apply_voltage_correction(device, "v1", v7_c - v2_c)
        v3_c = apply_voltage_correction(device, "v3", v7_c - v4_c)
        v5_c = apply_voltage_correction(device, "v5", v7_c - v6_c)
        
        ensure_device_in_config(device)

        db = SessionLocal()
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