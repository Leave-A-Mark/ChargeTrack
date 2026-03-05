from main import SessionLocal, BotSubscriber, SensorData, Admin, Device
import os
import asyncio
import logging
import io
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytz
from datetime import datetime, timedelta, UTC
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
import html
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")

if not API_TOKEN or API_TOKEN == "YOUR_BOT_TOKEN_HERE":
    logger.error("BOT_TOKEN not found in .env file!")

MOCK_MODE = os.getenv("MOCK", "false").lower() == "true"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Keyboards
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Моніторинг")],
            [KeyboardButton(text="📈 Графік"), KeyboardButton(text="🔍 Деталі")],
            [KeyboardButton(text="➕ Додати пристрій")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_device_selection_kb(db: Session, user_id: int, action: str):
    subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == user_id).all()
    if not subs:
        return None
    
    keyboard = []
    for sub in subs:
        device_obj = db.query(Device).filter(Device.equipment_id == sub.equipment_id).first()
        name = device_obj.name if device_obj else sub.equipment_id
        keyboard.append([InlineKeyboardButton(text=name, callback_data=f"sel:{action}:{sub.equipment_id}")])
    
    if len(subs) > 1:
        keyboard.append([InlineKeyboardButton(text="✨ Всі пристрої разом", callback_data=f"sel:{action}:all")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Timezone helper
def to_local_time(dt):
    if not dt: return None
    # Если время наивное, считаем что оно в UTC (как сохраняет serv.py)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    # Конвертируем в системное локальное время
    return dt.astimezone()

# Graph generation
def create_voltage_graph(db: Session, device_id: str, data: list):
    if not data:
        return None
    
    plt.figure(figsize=(10, 6))
    times = [to_local_time(d.timestamp) for d in data]
    
    # Get device settings from DB
    device_obj = db.query(Device).filter(Device.equipment_id == device_id).first()
    active_sensors_str = device_obj.active_sensors if device_obj else "v1,v2,v3,v4,v5,v6,v7"
    active_sensors = active_sensors_str.split(",")
    device_name = device_obj.name if device_obj else device_id
    
    for s in ["v1", "v2", "v3", "v4", "v5", "v6"]:
        if s in active_sensors:
            vals = [getattr(d, s) for d in data]
            plt.plot(times, vals, label=s.upper())
            
    if "v7" in active_sensors:
        v7 = [d.v7 for d in data]
        plt.plot(times, v7, label='Загальна (V7)', linewidth=2, linestyle='--')

    plt.title(f"Напруга за 24г: {device_name}")
    plt.xlabel("Час")
    plt.ylabel("Вольтаж (V)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

def create_detailed_voltage_graph(db: Session, device_id: str, data: list):
    if not data:
        return None
        
    device_obj = db.query(Device).filter(Device.equipment_id == device_id).first()
    active_sensors_str = device_obj.active_sensors if device_obj else "v1,v2,v3,v4,v5,v6,v7"
    active_sensors = [s for s in active_sensors_str.split(",") if s != "v7" and s.startswith("v")]
    
    if not active_sensors:
        return None

    num_sensors = len(active_sensors)
    fig, axes = plt.subplots(num_sensors, 1, figsize=(12, 4 * num_sensors), sharex=True)
    if num_sensors == 1:
        axes = [axes]
    
    times = [to_local_time(d.timestamp) for d in data]
    device_name = device_obj.name if device_obj else device_id
    fig.suptitle(f"Графіки активних датчиків пристрою \"{device_name}\"", fontsize=16, fontweight='bold')

    for i, sensor in enumerate(active_sensors):
        ax = axes[i]
        vals = [getattr(d, sensor) for d in data]
        
        # Stats
        v_min, v_max = min(vals), max(vals)
        v_mean = sum(vals) / len(vals)
        v_last = vals[-1]
        
        ax.plot(times, vals, marker='.', markersize=4, linestyle='-', linewidth=1.5)
        ax.set_title(f"Акумулятор №{sensor[1:]}", fontweight='bold')
        ax.set_ylabel("Напруга (B)")
        ax.grid(True, alpha=0.2)
        
        # Stats box
        stats_text = (
            f"Останнє: {v_last:.3f}V\n"
            f"Мін: {v_min:.3f}V\n"
            f"Макс: {v_max:.3f}V\n"
            f"Середнє: {v_mean:.3f}V"
        )
        props = dict(boxstyle='round', facecolor='lightblue', alpha=0.5)
        ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=8,
                verticalalignment='top', bbox=props)

    plt.xticks(rotation=45)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    return buf

async def send_morning_reports():
    db = SessionLocal()
    # Получаем уникальных пользователей с телеграм-айди
    user_ids = [r[0] for r in db.query(BotSubscriber.telegram_id).filter(BotSubscriber.telegram_id != None).distinct().all()]
    
    for uid in user_ids:
        # Для каждого пользователя находим все его устройства
        subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == uid).all()
        for sub in subs:
            try:
                cutoff = datetime.now(UTC) - timedelta(hours=24)
                data = db.query(SensorData).filter(
                    SensorData.equipment_id == sub.equipment_id,
                    SensorData.timestamp >= cutoff
                ).order_by(SensorData.timestamp).all()
                
                if data:
                    photo_buf = create_voltage_graph(db, sub.equipment_id, data)
                    if photo_buf:
                        photo = BufferedInputFile(photo_buf.getvalue(), filename="graph.png")
                        device_obj = db.query(Device).filter(Device.equipment_id == sub.equipment_id).first()
                        device_name = device_obj.name if device_obj else sub.equipment_id
                        await bot.send_photo(uid, photo, caption=f"🌅 Доброго ранку! Графік за останні 24 години для {device_name}")
            except Exception as e:
                logger.error(f"Error sending report to {uid} for {sub.equipment_id}: {e}")
    db.close()

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот ChargeTrack.\n\n"
        "Чтобы получать данные, введите секретный код, выданный администратором.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_(["📊 Моніторинг", "📊 Мониторинг"]))
async def btn_monitoring(message: types.Message):
    db = SessionLocal()
    subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == message.from_user.id).all()
    if not subs:
        await message.answer("Ви не підписані на оновлення. Введіть секретний код.")
        db.close()
        return

    if len(subs) > 1:
        kb = get_device_selection_kb(db, message.from_user.id, "mon")
        await message.answer("Оберіть пристрій для моніторингу:", reply_markup=kb)
    else:
        await process_monitor(message, subs[0].equipment_id)
    db.close()

async def process_monitor(message: types.Message, equipment_id: str):
    db = SessionLocal()
    data = db.query(SensorData).filter(SensorData.equipment_id == equipment_id).order_by(SensorData.timestamp.desc()).first()
    
    if not data and MOCK_MODE:
        data = SensorData(
            equipment_id=equipment_id,
            v1=round(random.uniform(26.0, 27.0), 2),
            v2=round(random.uniform(0.1, 0.4), 2),
            v3=round(random.uniform(26.0, 27.0), 2),
            v4=round(random.uniform(0.1, 0.4), 2),
            v5=round(random.uniform(26.0, 27.0), 2),
            v6=round(random.uniform(0.1, 0.4), 2),
            v7=round(random.uniform(26.0, 27.0), 2),
            wifi=random.randint(40, 95),
            timestamp=datetime.now(UTC)
        )

    if not data:
        device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
        device_name = device_obj.name if device_obj else equipment_id
        await message.answer(f"Дані для {device_name} поки не надійшли.")
    else:
        device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
        device_name = device_obj.name if device_obj else equipment_id
        active_sensors_str = device_obj.active_sensors if device_obj else "v1,v2,v3,v4,v5,v6,v7"
        active_sensors = active_sensors_str.split(",")
        
        is_mock = " (MOCK)" if not hasattr(data, 'id') else ""
        safe_name = html.escape(device_name)
        text = f"🔌 <b>{safe_name}</b>{is_mock}\n"
        text += f"🕒 Час: {to_local_time(data.timestamp).strftime('%H:%M:%S')}\n"
        
        for s in ["v1", "v2", "v3", "v4", "v5", "v6"]:
            if s in active_sensors:
                val = getattr(data, s)
                text += f"{s.upper()}: {val}V, "
        
        if text.endswith(", "): text = text[:-2] + "\n"
        else: text += "\n"

        if "v7" in active_sensors:
            text += f"⚡️ Загальна: {data.v7}V\n"
        
        text += f"📶 Wi-Fi: {data.wifi}%"
        await message.answer(text, parse_mode="HTML")
    db.close()

@dp.message(F.text.in_(["📈 Графік", "📈 График"]))
async def btn_graph(message: types.Message):
    db = SessionLocal()
    subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == message.from_user.id).all()
    if not subs:
        await message.answer("Ви не підписані на оновлення.")
        db.close()
        return

    if len(subs) > 1:
        kb = get_device_selection_kb(db, message.from_user.id, "gra")
        await message.answer("Оберіть пристрій для графіка:", reply_markup=kb)
    else:
        await process_graph(message, subs[0].equipment_id)
    db.close()

async def process_graph(message: types.Message, equipment_id: str):
    db = SessionLocal()
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    data = db.query(SensorData).filter(
        SensorData.equipment_id == equipment_id,
        SensorData.timestamp >= cutoff
    ).order_by(SensorData.timestamp).all()

    if not data and MOCK_MODE:
        data = generate_mock_history(equipment_id)

    if not data:
        device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
        device_name = device_obj.name if device_obj else equipment_id
        await message.answer(f"Немає даних за останні 24 години для {device_name}.")
    else:
        photo_buf = create_voltage_graph(db, equipment_id, data)
        if photo_buf:
            photo = BufferedInputFile(photo_buf.getvalue(), filename="graph.png")
            device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
            device_name = device_obj.name if device_obj else equipment_id
            is_mock = " (MOCK)" if MOCK_MODE and len(data) > 0 and not hasattr(data[0], 'id') else ""
            safe_name = html.escape(device_name)
            caption = f"Історія напруг за 24г для {safe_name}{is_mock}"
            await bot.send_photo(message.chat.id, photo, caption=caption, parse_mode="HTML")
    db.close()

@dp.message(F.text.in_(["🔍 Деталі", "🔍 Детали"]))
async def btn_details(message: types.Message):
    db = SessionLocal()
    subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == message.from_user.id).all()
    if not subs:
        await message.answer("Ви не підписані на оновлення.")
        db.close()
        return

    if len(subs) > 1:
        kb = get_device_selection_kb(db, message.from_user.id, "det")
        await message.answer("Оберіть пристрій для деталей:", reply_markup=kb)
    else:
        await process_details(message, subs[0].equipment_id)
    db.close()

async def process_details(message: types.Message, equipment_id: str):
    db = SessionLocal()
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    data = db.query(SensorData).filter(
        SensorData.equipment_id == equipment_id,
        SensorData.timestamp >= cutoff
    ).order_by(SensorData.timestamp).all()

    if not data and MOCK_MODE:
        data = generate_mock_history(equipment_id)

    if not data:
        device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
        device_name = device_obj.name if device_obj else equipment_id
        await message.answer(f"Немає даних за останні 24 години для {device_name}.")
    else:
        photo_buf = create_detailed_voltage_graph(db, equipment_id, data)
        if photo_buf:
            photo = BufferedInputFile(photo_buf.getvalue(), filename="details.png")
            device_obj = db.query(Device).filter(Device.equipment_id == equipment_id).first()
            device_name = device_obj.name if device_obj else equipment_id
            is_mock = " (MOCK)" if MOCK_MODE and len(data) > 0 and not hasattr(data[0], 'id') else ""
            safe_name = html.escape(device_name)
            caption = f"Детальні графіки датчиків для {safe_name}{is_mock}"
            await bot.send_photo(message.chat.id, photo, caption=caption, parse_mode="HTML")
        else:
            await message.answer(f"Немає активних датчиків для пристрою {equipment_id}.")
    db.close()

@dp.callback_query(F.data.startswith("sel:"))
async def callback_select_device(callback: types.CallbackQuery):
    try:
        _, action, eq_id = callback.data.split(":")
        db = SessionLocal()
        
        if eq_id == "all":
            subs = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == callback.from_user.id).all()
            ids = [s.equipment_id for s in subs]
        else:
            ids = [eq_id]
            
        await callback.answer()
        for eid in ids:
            if action == "mon": await process_monitor(callback.message, eid)
            elif action == "gra": await process_graph(callback.message, eid)
            elif action == "det": await process_details(callback.message, eid)
        
        db.close()
    except Exception as e:
        logger.error(f"Error in callback_select_device: {e}")

@dp.message(F.text == "➕ Додати пристрій")
async def btn_add_device(message: types.Message):
    await message.answer("Надішліть секретний код нового пристрою.")

def generate_mock_history(equipment_id):
    # Helper to avoid code duplication
    data = []
    for i in range(48): # more points for smoother graph
        ts = datetime.now(UTC) - timedelta(hours=24) + timedelta(minutes=30*i)
        data.append(SensorData(
            equipment_id=equipment_id,
            v1=round(random.uniform(26.4, 26.55), 2),
            v2=round(random.uniform(0.08, 0.15), 2),
            v3=round(random.uniform(26.45, 26.55), 2),
            v4=round(random.uniform(0.06, 0.16), 2),
            v5=round(random.uniform(26.2, 27.3), 2),
            v6=round(random.uniform(0.1, 0.5), 2),
            v7=round(random.uniform(52.5, 53.5), 2),
            wifi=random.randint(50, 90),
            timestamp=ts
        ))
    return data

@dp.message()
async def handle_secret_code(message: types.Message):
    code = message.text.strip().upper()
    if len(code) != 8: return

    db = SessionLocal()
    sub = db.query(BotSubscriber).filter(BotSubscriber.secret_code == code).first()
    if sub:
        sub.telegram_id = message.from_user.id
        db.commit()
        device_obj = db.query(Device).filter(Device.equipment_id == sub.equipment_id).first()
        device_name = device_obj.name if device_obj else sub.equipment_id
        await message.answer(f"✅ Успішно! Ви приєднані до пристрою: {device_name}", reply_markup=get_main_keyboard())
    db.close()

async def main():
    # Schedule morning reports at 08:00
    scheduler.add_job(send_morning_reports, 'cron', hour=8, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
