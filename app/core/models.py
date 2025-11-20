import sys
sys.path.append("../..")

from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv()

model = init_chat_model(
    "gpt-4.1-mini",
    temperature=0
)