import os
from dotenv import load_dotenv

def load_environment():
    load_dotenv()

    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        load_dotenv(".env.production", override=True)
    else:
        load_dotenv(".env.development", override=True)
