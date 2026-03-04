import os
import asyncio
import logging
import io
import random
import matplotlib
matplotlib.use('Agg') # Fix TclError on Windows/Linux
import matplotlib.pyplot as plt
import pytz
from datetime import datetime, timedelta, UTC
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from sqlalchemy.orm import Session
from main import SessionLocal, BotSubscriber, SensorData, Admin
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

# Keyboard
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Мониторинг"), KeyboardButton(text="📈 График")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Timezone helper
def to_local_time(utc_dt):
    if not utc_dt: return None
    # Ensure timezone-aware if it's naive
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=UTC)
    local_tz = pytz.timezone('Europe/Kiev')
    return utc_dt.astimezone(local_tz)

# Graph generation
def create_voltage_graph(device_id, data):
    if not data:
        return None
    
    plt.figure(figsize=(10, 6))
    times = [to_local_time(d.timestamp) for d in data]
    v1 = [d.v1 for d in data]
    v2 = [d.v2 for d in data]
    v3 = [d.v3 for d in data]
    v4 = [d.v4 for d in data]
    v5 = [d.v5 for d in data]
    v6 = [d.v6 for d in data]
    v7 = [d.v7 for d in data]

    plt.plot(times, v1, label='V1')
    plt.plot(times, v2, label='V2')
    plt.plot(times, v3, label='V3')
    plt.plot(times, v4, label='V4')
    plt.plot(times, v5, label='V5')
    plt.plot(times, v6, label='V6')
    plt.plot(times, v7, label='Total (V7)', linewidth=2, linestyle='--')

    plt.title(f"Напряжение за 24ч: {device_id}")
    plt.xlabel("Время")
    plt.ylabel("Вольтаж (V)")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf

async def send_morning_reports():
    db = SessionLocal()
    subscribers = db.query(BotSubscriber).filter(BotSubscriber.telegram_id != None).all()
    for sub in subscribers:
        try:
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            data = db.query(SensorData).filter(
                SensorData.equipment_id == sub.equipment_id,
                SensorData.timestamp >= cutoff
            ).order_by(SensorData.timestamp).all()
            
            if data:
                photo_buf = create_voltage_graph(sub.equipment_id, data)
                if photo_buf:
                    photo = BufferedInputFile(photo_buf.getvalue(), filename="graph.png")
                    await bot.send_photo(sub.telegram_id, photo, caption=f"🌅 Доброе утро! График за последние 24 часа для {sub.equipment_id}")
        except Exception as e:
            logger.error(f"Error sending report to {sub.telegram_id}: {e}")
    db.close()

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот ChargeTrack.\n\n"
        "Чтобы получать данные, введите секретный код, выданный администратором.",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📊 Мониторинг")
async def btn_monitoring(message: types.Message):
    db = SessionLocal()
    sub = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == message.from_user.id).first()
    if not sub:
        await message.answer("Вы не подписаны на обновления. Введите секретный код.")
        db.close()
        return

    data = db.query(SensorData).filter(SensorData.equipment_id == sub.equipment_id).order_by(SensorData.timestamp.desc()).first()
    
    if not data and MOCK_MODE:
        # Generate mock data point
        data = SensorData(
            equipment_id=sub.equipment_id,
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
        await message.answer(f"Данные для {sub.equipment_id} пока не поступили.")
    else:
        text = (
            f"🔌 **{sub.equipment_id}** (MOCK)" if not hasattr(data, 'id') else f"🔌 **{sub.equipment_id}**"
        )
        text += (
            f"\n🕒 Время: {to_local_time(data.timestamp).strftime('%H:%M:%S')}\n"
            f"V1: {data.v1}V, V2: {data.v2}V\n"
            f"V3: {data.v3}V, V4: {data.v4}V\n"
            f"V5: {data.v5}V, V6: {data.v6}V\n"
            f"⚡️ Общее: {data.v7}V\n"
            f"📶 Wi-Fi: {data.wifi}%"
        )
        await message.answer(text, parse_mode="Markdown")
    db.close()

@dp.message(F.text == "📈 График")
async def btn_graph(message: types.Message):
    db = SessionLocal()
    sub = db.query(BotSubscriber).filter(BotSubscriber.telegram_id == message.from_user.id).first()
    if not sub:
        await message.answer("Вы не подписаны на обновления.")
        db.close()
        return

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    data = db.query(SensorData).filter(
        SensorData.equipment_id == sub.equipment_id,
        SensorData.timestamp >= cutoff
    ).order_by(SensorData.timestamp).all()

    if not data and MOCK_MODE:
        # Generate 24 points of mock data
        data = []
        for i in range(24):
            ts = datetime.now(UTC) - timedelta(hours=24-i)
            data.append(SensorData(
                equipment_id=sub.equipment_id,
                v1=round(random.uniform(26.0, 27.5), 2),
                v2=round(random.uniform(0.1, 0.5), 2),
                v3=round(random.uniform(26.1, 27.4), 2),
                v4=round(random.uniform(0.1, 0.5), 2),
                v5=round(random.uniform(26.2, 27.3), 2),
                v6=round(random.uniform(0.1, 0.5), 2),
                v7=round(random.uniform(26.5, 27.8), 2),
                wifi=random.randint(50, 90),
                timestamp=ts
            ))

    if not data:
        await message.answer("Нет данных за последние 24 часа.")
    else:
        photo_buf = create_voltage_graph(sub.equipment_id, data)
        if photo_buf:
            photo = BufferedInputFile(photo_buf.getvalue(), filename="graph.png")
            caption = f"История напряжений за 24ч для {sub.equipment_id} (MOCK)" if MOCK_MODE and len(data) > 0 and not hasattr(data[0], 'id') else f"История напряжений за 24ч для {sub.equipment_id}"
            await bot.send_photo(message.chat.id, photo, caption=caption)
    db.close()

@dp.message()
async def handle_secret_code(message: types.Message):
    code = message.text.strip().upper()
    if len(code) != 8: return

    db = SessionLocal()
    sub = db.query(BotSubscriber).filter(BotSubscriber.secret_code == code).first()
    if sub:
        sub.telegram_id = message.from_user.id
        db.commit()
        await message.answer(f"✅ Успешно! Вы привязаны к устройству: {sub.equipment_id}", reply_markup=get_main_keyboard())
    db.close()

async def main():
    # Schedule morning reports at 08:00
    scheduler.add_job(send_morning_reports, 'cron', hour=8, minute=0)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
