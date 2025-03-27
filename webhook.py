from fastapi import APIRouter, Request
from pydantic import BaseModel
import httpx
import re
from metaapi_cloud_sdk import MetaApi

router = APIRouter()

TELEGRAM_BOT_TOKEN = "7900613582:AAGCwv6HCow334iKB4xWcyzvWj_hQBtmN4a"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
RAILWAY_BACKEND_URL = "https://vessa-mt5-backend-production.up.railway.app"


from metaapi_cloud_sdk import MetaApi

# MetaAPI credentials
METAAPI_TOKEN = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiJlZTFiMzY5MWExMTQzMTYzMjg1ZjYwNDBkYWVkMjFjZCIsImFjY2Vzc1J1bGVzIjpbeyJpZCI6Im1ldGFhcGktcmVzdC1hcGkiLCJtZXRob2RzIjpbIm1ldGFhcGktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6ImNvcHlmYWN0b3J5LWFwaSIsIm1ldGhvZHMiOlsiY29weWZhY3RvcnktYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX1dLCJpZ25vcmVSYXRlTGltaXRzIjpmYWxzZSwidG9rZW5JZCI6IjIwMjEwMjEzIiwiaW1wZXJzb25hdGVkIjpmYWxzZSwicmVhbFVzZXJJZCI6ImVlMWIzNjkxYTExNDMxNjMyODVmNjA0MGRhZWQyMWNkIiwiaWF0IjoxNzQzMDg0ODcyfQ.jOsIFdN0w0IuCbgaLK4S3dG0vtyIn_dou9rul88pj05me4pnDSiPC4EjkIQyuwEHU9Sqy2BVnwDYaqRszi5UYMWpCro3IQxeIBe-tcDGP0QGKvsk7153OYKQbwQpyXxsQ_T6UMTBiwepaFbAjFViovxSjO0879zriIkZ21FOtxFGRtsejO1gWJ9GJ50o6EPc64Fu6h_IDuBeChUhQi-oOwg8n8ZPYBa2c1Q43X7oi_viKbFslvLwUPeKrSxu-NIdl5eGHg8lHnznuFxck28_NsXTgN4EY_vN-NXtrbtqhwzBGGpYCsqDlc-gPlpytLXsrx1C-WR_Di55CxDt8S5IPph53kPberd8NB3LVGjqj6UR5mFS1pDYl9eOl9hzm-WpIZxW5c0PDtWxvRdEjOlWblmw79yOu37djik_bUYssOVVpvPXqds65zctCe-6Bs4sUt02KKkJCLdrr0edAvu6OToaYJ4jdp3HLethhjTsd9QRuNeq0PFIeJuqt2F7JN9GqhZCG3lZxOv3vmwV1GbdKtpm3v6RCY9TbQG-H6UAMLCAV4kbKpG5qr5XJXiC_EI8wFrJLRGVRBgy6ic_9gKUua3o6E2DYKfC8nqLvzZa-4hwqGqpbpuRMtuYl7W1812Uiv38sP1Xc_i0KgiWJYm7vTr-dD3ESWxwRbaXMAuorYs"
METAAPI_USER_ID = "aafbb9da-c43d-4fba-a84c-6ca568311d34"



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

        # Loop through each user
        for user in users:
            chat_id = user["chat_id"]

            # 1. Send Telegram confirmation
            await send_telegram_message(chat_id, f"✅ Trade Executed!\n{direction} {symbol}\nEntry: {entry}\nTP1: {tps[0]}\nSL: {sl}")

            # 2. Execute real trade via MetaAPI
            await execute_trade(symbol, direction, entry, sl, tps[0])

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

async def execute_trade(symbol, direction, entry, sl, tp1):
    try:
        # Connect to MetaAPI
        api = MetaApi(METAAPI_TOKEN)
        account = await api.metatrader_account.get_account(METAAPI_USER_ID)
        api_connection = account.get_connection()

        # Wait until the connection is ready
        await api_connection.connect()
        
        # Place the trade
        if direction == 'BUY':
            order = await api_connection.execute_order(
                symbol=symbol,
                action='BUY',
                volume=0.1,  # Fixed volume or dynamic based on risk
                price=entry,
                sl=sl,
                tp=tp1,
                magic=123456
            )
        elif direction == 'SELL':
            order = await api_connection.execute_order(
                symbol=symbol,
                action='SELL',
                volume=0.1,  # Fixed volume or dynamic based on risk
                price=entry,
                sl=sl,
                tp=tp1,
                magic=123456
            )
        
        print(f"Trade executed: {order}")
        return order

    except Exception as e:
        print(f"Error executing trade: {e}")
        return None
