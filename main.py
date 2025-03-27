from fastapi import FastAPI
from webhook import router as webhook_router  # import the webhook router

app = FastAPI()

# include the webhook router
app.include_router(webhook_router)
