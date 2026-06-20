import os
import sys
# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_google_genai import ChatGoogleGenerativeAI
from core.evaluation.evaluation_config import JUDGE_MODEL, GOOGLE_API_KEY

print("Model:", JUDGE_MODEL)
print("API Key:", GOOGLE_API_KEY)

llm = ChatGoogleGenerativeAI(
    model=JUDGE_MODEL,
    google_api_key=GOOGLE_API_KEY,
    temperature=0,
    timeout=30
)

try:
    print("Sending request to Gemini...")
    response = llm.invoke("Hello, answer in 5 words.")
    print("Response:", response.content)
except Exception as e:
    print("Error:", e)
