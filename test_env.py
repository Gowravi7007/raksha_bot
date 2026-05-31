import os
from dotenv import load_dotenv

load_dotenv()

keys = [
    "GEMINI_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "EMERGENCY_CONTACT"
]

print("Checking environment variables...\n")

all_ok = True

for key in keys:
    value = os.getenv(key)

    if value:
        print(f"{key}: Loaded")
    else:
        print(f"{key}: Missing")
        all_ok = False

if all_ok:
    print("\nAll environment variables loaded successfully.")
else:
    print("\nSome environment variables are missing.")