import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("USER")
password = os.getenv("PASSWORD")
host = os.getenv("HOST")
port = os.getenv("PORT")
db = os.getenv("DB")


BASE_URL = "http://91.199.149.128:18001"
PG_URL = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


HEADERS = {"X-Candidate-Id": "2"}