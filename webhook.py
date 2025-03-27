from fastapi import APIRouter, Request
from pydantic import BaseModel
import httpx
import re

router = APIRouter()

TELEGRAM_BOT_TOKEN = "7900613582:AAGCwv6HCow334iKB4xWcyzvWj_hQBtmN4a"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
RAILWAY_BACKEND_URL = "https://vessa-mt5-backend-production.up.railway.app"


class TradingViewSignal(BaseModel):
    message: str


@router.post("/webhook")
async def receive_signal(signal: TradingViewSignal):
    try:
        text = signal.message.strip()
        parsed = parse_signal(text)
        if not parsed:
            return {"status": "error", "message": "Invalid signal format"}

        direction, symbol, entry, sl, tps = parsed

        # Fetch subscribed users
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{RAILWAY_BACKEND_URL}/get_users_by_symbol?symbol={symbol}")
            users = response.json().get("users", [])

        # Loop through each user (for now we just send a Telegram confirmation)
        for user in users:
            chat_id = user["chat_id"]
            await send_telegram_message(chat_id, f"✅ Trade Executed!\n{direction} {symbol}\nEntry: {entry}\nTP1: {tps[0]}\nSL: {sl}")

        return {"status": "ok", "executed_users": len(users)}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def parse_signal(text):
    try:
        lines = text.splitlines()
        direction_symbol = lines[0].strip().split()
        direction = direction_symbol[0].upper()
        symbol = direction_symbol[1].upper()

        entry = float(re.search(r"Entry:\s*(\d+\.\d+)", text).group(1))
        sl = float(re.search(r"SL:\s*(\d+\.\d+)", text).group(1))
        tps = re.findall(r"TP\d:\s*(\d+\.\d+)", text)

        return direction, symbol, entry, sl, list(map(float, tps))
    except:
        return None


async def send_telegram_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })
