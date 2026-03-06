from flask import Flask, request, jsonify
from sqlalchemy.orm import Session
from datetime import datetime
import pytz
import requests
from main import SessionLocal, SensorData, init_db, Device, BatteryEvent, BatterySession

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
                active_sensors="v1,v2,v3,v4,v5,v6,v7",
                battery_count=6
            )
            db.add(device)
            db.commit()
    except Exception as e:
        print(f"Ошибка при проверке устройства {device_id}: {e}")

def notify_telegram(equipment_id: str, message: str):
    """Отправить уведомление в Telegram через API бота (упрощенно)"""
    # В реальности бот имеет свой цикл, но мы можем отправить запрос 
    # или использовать общую очередь. Для простоты - прямой вызов если токен в env
    token = os.getenv("BOT_TOKEN")
    if not token: return
    
    db = SessionLocal()
    from main import BotSubscriber
    subs = db.query(BotSubscriber).filter(BotSubscriber.equipment_id == equipment_id).all()
    for sub in subs:
        if sub.telegram_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": sub.telegram_id, "text": message, "parse_mode": "HTML"}
            try:
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                print(f"Error sending telegram notification: {e}")
    db.close()

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
            timestamp=datetime.now()
        )
        db.add(entry)
        
        # --- State Analysis Logic ---
        device_obj = db.query(Device).filter(Device.equipment_id == device).first()
        if device_obj:
            v_prev = device_obj.last_v7
            v_curr = v7_c
            old_state = device_obj.last_state
            new_state = old_state
            
            # Constants for universal system (S=2)
            S = 2
            V_max = 12.4 * S
            V_min = 11.5 * S
            # THRESHOLD_OUTAGE: Above this value, we assume AC is present
            THRESHOLD_OUTAGE = 25.8 

            if v_curr >= THRESHOLD_OUTAGE:
                # Based on user feedback: Maintenance is 26.22-26.4V
                # Charging is higher (Absorption level)
                if v_curr > 26.6:
                    new_state = "CHARGING"
                else:
                    new_state = "MAINTENANCE"
            elif v_prev is not None:
                diff = v_curr - v_prev
                # Spike filter: only change if significant
                sens = 0.05 
                if diff < -sens: # Dropping
                    new_state = "DISCHARGING"
                elif diff > sens and v_curr < (V_max * 1.15): # Charging up to absorption
                    new_state = "CHARGING"
            
        # Manage Sessions
        active_session = db.query(BatterySession).filter(
            BatterySession.equipment_id == device,
            BatterySession.end_time == None
        ).first()
        
        # Start session if none exists OR if state changed
        state_changed = (new_state != old_state)
        
        if not active_session or state_changed:
            if active_session:
                # Close old session
                active_session.end_time = datetime.now()
                active_session.end_voltage = v_curr
                # Calculate energy for discharge sessions
                if active_session.type == "DISCHARGE":
                    v_max = 12.4 * 2
                    v_min = 11.5 * 2
                    v_range = v_max - v_min
                    # Constants: C_one=200, V_nom_one=12, S=2, DoD=0.3
                    e_safe = (device_obj.battery_count or 6) * 200.0 * 12.0 * 0.3
                    
                    v_start = min(active_session.start_voltage, v_max)
                    # Formula: Wh_used = ((V_start - V_end) / V_range) * E_safe
                    wh_used = ((v_start - v_curr) / v_range) * e_safe
                    active_session.energy_wh = round(max(0, wh_used), 2)
            
            # Start new session
            session_type = "MAINTENANCE"
            if new_state == "DISCHARGING": session_type = "DISCHARGE"
            elif new_state == "CHARGING": session_type = "CHARGE"
            
            db.add(BatterySession(
                equipment_id=device,
                type=session_type,
                start_time=datetime.now(),
                start_voltage=v_curr
            ))
            
            # Handle Notifications
            if state_changed:
                device_obj.last_state = new_state
                event_type = ""
                msg = ""
                if new_state == "DISCHARGING":
                    event_type = "POWER_OFF"
                    msg = f"⚠️ <b>ТРИВОГА: Світло вимкнено!</b>\nПристрій: {device_obj.name}\nНапруга: {v_curr:.2f}V\nІнвертор почав розряджати акумулятори."
                elif old_state == "DISCHARGING" and new_state in ["CHARGING", "MAINTENANCE"]:
                    event_type = "POWER_ON"
                    msg = f"🔌 <b>Світло з'явилося!</b>\nПристрій: {device_obj.name}\nНапруга: {v_curr:.2f}V\nПочався процес зарядки/підтримки."
                
                if event_type:
                    db.add(BatteryEvent(equipment_id=device, event_type=event_type, voltage=v_curr))
                    notify_telegram(device, msg)
            
        device_obj.last_v7 = v_curr

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