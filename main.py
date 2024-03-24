import os

import httpx

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError

import exception_handlers as eh

from routers.leader.user_router import router as leader_user_router
from routers.leader.token_router import router as leader_token_router

from utils.api_clients.leader_api_client import LeaderAPIClient, UserNotFoundException, CaptchaNotSetException
from utils.api_clients.usedesk_api_client import UsedeskAPIClient
from utils.api_clients.telegram_api_client import TelegramAPIClient
from utils.logger import get_logger

from services.leader_service import LeaderServices
from services.usedesk_service import UsedeskService
from services.telegram_service import TelegramService

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.bot import router

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_WEBHOOK_URL = os.getenv('BOT_WEBHOOK_URL')
BOT_WEBHOOK_PATH = os.getenv('BOT_WEBHOOK_PATH')

USEDESK_API_TOKEN = os.getenv('USEDESK_API_TOKEN')

LEADER_ID_ADMIN_EMAIL = os.getenv('LEADER_ID_ADMIN_EMAIL')
LEADER_ID_ADMIN_PASSWORD = os.getenv('LEADER_ID_ADMIN_PASSWORD')

REDIS_URL = os.getenv('REDIS_URL')

logger = get_logger(__name__)

app = FastAPI()

app.add_exception_handler(HTTPException, eh.fastapi_http_exception_handler)
app.add_exception_handler(httpx.HTTPStatusError, eh.httpx_http_status_error_handler)
app.add_exception_handler(httpx.RequestError, eh.httpx_request_error_handler)
app.add_exception_handler(RequestValidationError, eh.generic_exception_handler)
app.add_exception_handler(Exception, eh.generic_exception_handler)
app.add_exception_handler(UserNotFoundException, eh.user_not_found_exception_handler)
app.add_exception_handler(CaptchaNotSetException, eh.captcha_not_set_exception_handler)

app.include_router(leader_user_router, prefix="/api/v1/leader", tags=["Leader-ID"])
app.include_router(leader_token_router, prefix="/api/v1/leader", tags=["Leader-ID"])

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = RedisStorage.from_url(REDIS_URL)
dp = Dispatcher(storage=storage)
dp.include_router(router)


@app.on_event("startup")
async def startup():
    """
    Webhook registration and API clients initialization.
    """
    webhook_url = f"{BOT_WEBHOOK_URL}{BOT_WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook URL: {webhook_url}")

    # Initialize and authenticate Leader-ID API client
    app.state.leader_api_client = LeaderAPIClient()  # Create API client
    app.state.leader_services = LeaderServices(app.state.leader_api_client)  # Create service for API operations
    await app.state.leader_services.authenticate(LEADER_ID_ADMIN_EMAIL, LEADER_ID_ADMIN_PASSWORD)  # Authenticate

    # Initialize and authenticate Usedesk API client
    app.state.usedesk_api_client = UsedeskAPIClient()  # Create API client
    app.state.usedesk_service = UsedeskService(app.state.usedesk_api_client)  # Create service for API operations
    await app.state.usedesk_service.authenticate(USEDESK_API_TOKEN)  # Authenticate

    # Initialize and authenticate Telegram API client
    app.state.telegram_api_client = TelegramAPIClient()  # Create API client
    app.state.telegram_service = TelegramService(app.state.telegram_api_client)  # Create service for API operations
    await app.state.telegram_service.authenticate(BOT_TOKEN)  # Authenticate


@app.on_event("shutdown")
async def shutdown():
    await app.state.leader_api_client.close()
    await app.state.usedesk_api_client.close()
    await app.state.telegram_api_client.close()


@app.get("/")
async def root():
    return {"message": "Hello World!"}


@app.post(BOT_WEBHOOK_PATH)
async def receive_update(request: Request):
    """
    Processing incoming updates from a webhook.
    """
    update = types.Update(**await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}