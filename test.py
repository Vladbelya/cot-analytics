import os
from dotenv import load_dotenv

env_path = os.path.join(os.getcwd(), '.env')
print(f"Path: {env_path}")
print(f"Exists: {os.path.exists(env_path)}")
print(f"Loaded: {load_dotenv(env_path)}")
print(f"Key: {os.getenv('GEMINI_API_KEY')}")
