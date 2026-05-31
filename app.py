import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Supports both old and new variable name
EMERGENCY_CONTACTS = os.getenv(
    "EMERGENCY_CONTACTS",
    os.getenv("EMERGENCY_CONTACT", "")
)


# -------------------------------------------------
# CONTACTS + ALERT MESSAGE
# -------------------------------------------------

def get_contact_list():
    """
    Reads emergency contacts from EMERGENCY_CONTACTS.
    Example:
    EMERGENCY_CONTACTS=+917483348177,+91XXXXXXXXXX
    """
    if not EMERGENCY_CONTACTS:
        return []

    return [
        num.strip()
        for num in EMERGENCY_CONTACTS.split(",")
        if num.strip()
    ]


def build_alert_message(data):
    name = data.get("name", "User")
    latitude = data.get("latitude", "12.9716")
    longitude = data.get("longitude", "77.5946")
    hospital = data.get("hospital", "City Hospital")
    eta = data.get("eta", "8 min")

    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"

    return (
        f"RAKSHA ALERT: Accident detected for {name}. "
        f"Location: {maps_link}. "
        f"Nearest hospital: {hospital}. "
        f"ETA: {eta}. Please call immediately."
    )


# -------------------------------------------------
# TWILIO MESSAGE SENDING
# -------------------------------------------------

def send_twilio_sms(message):
    """
    First tries WhatsApp using Twilio Sandbox.
    If WhatsApp fails, tries normal SMS fallback.
    """

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "error": "Twilio credentials missing."
        }

    contacts = get_contact_list()

    if not contacts:
        return {
            "success": False,
            "error": "No emergency contacts found."
        }

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        sent_messages = []
        failed_messages = []

        for contact in contacts:
            try:
                # Try WhatsApp first
                whatsapp_to = (
                    contact if contact.startswith("whatsapp:")
                    else f"whatsapp:{contact}"
                )

                whatsapp_from = (
                    TWILIO_PHONE_NUMBER
                    if TWILIO_PHONE_NUMBER.startswith("whatsapp:")
                    else f"whatsapp:{TWILIO_PHONE_NUMBER}"
                )

                sms = client.messages.create(
                    body=message,
                    from_=whatsapp_from,
                    to=whatsapp_to
                )

                sent_messages.append({
                    "to": contact,
                    "sid": sms.sid,
                    "status": sms.status,
                    "via": "whatsapp"
                })

            except Exception as whatsapp_error:
                # If WhatsApp fails, try normal SMS
                try:
                    sms = client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=contact
                    )

                    sent_messages.append({
                        "to": contact,
                        "sid": sms.sid,
                        "status": sms.status,
                        "via": "sms"
                    })

                except Exception as sms_error:
                    failed_messages.append({
                        "to": contact,
                        "whatsapp_error": str(whatsapp_error),
                        "sms_error": str(sms_error)
                    })

        return {
            "success": len(sent_messages) > 0,
            "sent_count": len(sent_messages),
            "failed_count": len(failed_messages),
            "messages": sent_messages,
            "failed": failed_messages
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# -------------------------------------------------
# CHATBOT RESPONSES
# Gemini if available, fallback if not
# -------------------------------------------------

CHAT_RESPONSES = {
    "accident": {
        "ta": "விபத்து கண்டறியப்பட்டது. உதவி வருகிறது. பயப்படாதீர்கள்.",
        "hi": "दुर्घटना का पता चला। मदद आ रही है। घबराएं नहीं।",
        "en": "Accident detected. Help is on the way. Please stay calm."
    },
    "hospital": {
        "ta": "அருகிலுள்ள மருத்துவமனை கண்டறியப்பட்டது. ஆம்புலன்ஸ் அனுப்பப்படுகிறது.",
        "hi": "नजदीकी अस्पताल मिल गया। एम्बुलेंस भेजी जा रही है।",
        "en": "Nearest trauma hospital found. Ambulance is being dispatched."
    },
    "help": {
        "ta": "உதவி வேண்டுமா? நான் RAKSHA AI. விபத்து, மருத்துவமனை அல்லது முதலுதவி பற்றி கேளுங்கள்.",
        "hi": "मदद चाहिए? मैं RAKSHA AI हूं। दुर्घटना, अस्पताल या प्राथमिक चिकित्सा के बारे में पूछें।",
        "en": "Need help? I am RAKSHA AI. Ask me about accident status, hospitals, or first aid."
    },
    "first_aid": {
        "ta": "முதலுதவி: நபரை நகர்த்தாதீர்கள். சுவாசம் சரிபார்க்கவும். 108 அழைக்கவும். இரத்தப்போக்கை அழுத்தத்தால் நிறுத்தவும்.",
        "hi": "प्राथमिक चिकित्सा: व्यक्ति को हिलाएं नहीं। सांस जांचें। 108 कॉल करें। रक्तस्राव को दबाव से रोकें।",
        "en": "First aid: Do not move the person. Check breathing. Call 108. Apply pressure to stop bleeding."
    },
    "status": {
        "ta": "RAKSHA AI செயல்பாட்டில் உள்ளது. அனைத்து சென்சார்களும் சரியாக வேலை செய்கின்றன.",
        "hi": "RAKSHA AI चालू है। सभी सेंसर सही से काम कर रहे हैं।",
        "en": "RAKSHA AI is active. All sensors are functioning correctly."
    },
    "default": {
        "ta": "நான் RAKSHA AI. விபத்து கண்டறிதல் மற்றும் மீட்பு அமைப்பு. எப்படி உதவலாம்?",
        "hi": "मैं RAKSHA AI हूं। दुर्घटना पहचान और बचाव प्रणाली। कैसे मदद करूं?",
        "en": "I am RAKSHA AI — accident detection and rescue system. How can I help?"
    }
}


def detect_language(message):
    """
    Simple Tamil / Hindi / English detection.
    """

    tamil_chars = set(
        "அஆஇஈஉஊஎஏஐஒஓஔகஙசஞடணதநபமயரலவழளறன"
    )

    hindi_chars = set(
        "अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह"
    )

    msg_chars = set(message)

    if msg_chars & tamil_chars:
        return "ta"

    if msg_chars & hindi_chars:
        return "hi"

    return "en"


def get_intent(message):
    msg = message.lower()

    if any(word in msg for word in [
        "accident", "crash", "impact", "விபத்து", "दुर्घटना"
    ]):
        return "accident"

    if any(word in msg for word in [
        "hospital", "ambulance", "doctor", "மருத்துவமனை", "अस्पताल"
    ]):
        return "hospital"

    if any(word in msg for word in [
        "first aid", "bleeding", "breath", "injured",
        "முதலுதவி", "प्राथमिक"
    ]):
        return "first_aid"

    if any(word in msg for word in [
        "status", "active", "sensor", "system", "நிலை", "स्थिति"
    ]):
        return "status"

    if any(word in msg for word in [
        "help", "sos", "emergency", "உதவி", "मदद"
    ]):
        return "help"

    return "default"


def gemini_chat(message, lang):
    """
    Uses Gemini only if GEMINI_API_KEY is available.
    If not available or if API fails, returns None.
    """

    if not GEMINI_API_KEY:
        return None

    try:
        import requests

        lang_instruction = {
            "ta": "Respond only in Tamil.",
            "hi": "Respond only in Hindi.",
            "en": "Respond only in English."
        }.get(lang, "Respond only in English.")

        system_prompt = f"""
You are RAKSHA AI, an emergency road accident detection and rescue assistant.
{lang_instruction}
Keep the reply short, calm, and useful.
Focus only on accident detection, hospital routing, emergency contacts, and first aid.
"""

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"{system_prompt}\nUser: {message}"
                        }
                    ]
                }
            ]
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-pro:generateContent?key={GEMINI_API_KEY}"
        )

        response = requests.post(url, json=payload, timeout=5)
        data = response.json()

        return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception:
        return None


# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
def home():
    return redirect("/health")


@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "project": "RAKSHA AI",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/status")
def api_status():
    return jsonify({
        "message": "RAKSHA AI backend running successfully",
        "env_loaded": {
            "GEMINI_API_KEY": bool(GEMINI_API_KEY),
            "TWILIO_ACCOUNT_SID": bool(TWILIO_ACCOUNT_SID),
            "TWILIO_AUTH_TOKEN": bool(TWILIO_AUTH_TOKEN),
            "TWILIO_PHONE_NUMBER": bool(TWILIO_PHONE_NUMBER),
            "EMERGENCY_CONTACTS": bool(get_contact_list())
        }
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "error": "No message provided"
        }), 400

    lang = detect_language(message)
    intent = get_intent(message)

    gemini_reply = gemini_chat(message, lang)

    if gemini_reply:
        return jsonify({
            "reply": gemini_reply,
            "language": lang,
            "intent": intent,
            "source": "gemini"
        })

    response_set = CHAT_RESPONSES.get(intent, CHAT_RESPONSES["default"])
    reply = response_set.get(lang, response_set["en"])

    return jsonify({
        "reply": reply,
        "language": lang,
        "intent": intent,
        "source": "fallback"
    })


@app.route("/api/alert/send", methods=["POST"])
def send_alert_api():
    """
    Manual alert test endpoint.
    Frontend can call this directly.
    """

    data = request.get_json(silent=True) or {}

    alert_message = build_alert_message(data)
    result = send_twilio_sms(alert_message)

    return jsonify({
        "alert_message": alert_message,
        "message_length": len(alert_message),
        "result": result
    })


@app.route("/api/accident/trigger", methods=["GET", "POST"])
def trigger_accident():
    """
    Main automatic accident trigger endpoint.

    If combined score > 70, alert is sent automatically.
    """

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = {}

    name = data.get("name", "Demo User")
    latitude = data.get("latitude", "12.8249")
    longitude = data.get("longitude", "77.5159")
    hospital = data.get("hospital", "Fortis Hospital Bangalore")
    eta = data.get("eta", "6 min")

    accelerometer_score = float(data.get("accelerometer_score", 85))
    sound_score = float(data.get("sound_score", 78))

    combined_score = (accelerometer_score * 0.55) + (sound_score * 0.45)
    accident_confirmed = combined_score > 70

    if accident_confirmed:
        alert_message = build_alert_message({
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "hospital": hospital,
            "eta": eta
        })

        alert_result = send_twilio_sms(alert_message)

    else:
        alert_message = "Accident not confirmed. Score below threshold."
        alert_result = {
            "success": False,
            "error": "Score below threshold."
        }

    return jsonify({
        "accident_confirmed": accident_confirmed,
        "combined_score": round(combined_score, 2),
        "threshold": 70,
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "map_link": f"https://maps.google.com/?q={latitude},{longitude}"
        },
        "nearest_hospital": hospital,
        "eta": eta,
        "alert_message": alert_message,
        "alert_result": alert_result
    })


# -------------------------------------------------
# COMPATIBILITY ROUTES FOR aarohi.html
# -------------------------------------------------

@app.route("/accident", methods=["POST"])
def accident_compat():
    return trigger_accident()


@app.route("/chat", methods=["POST"])
def chat_compat():
    return chat()


@app.route("/find-hospital", methods=["POST"])
def find_hospital_compat():
    data = request.get_json(silent=True) or {}

    return jsonify({
        "status": "success",
        "user_location": {
            "latitude": data.get("latitude", "12.8249"),
            "longitude": data.get("longitude", "77.5159")
        },
        "hospitals": [
            {
                "name": "Fortis Hospital Bangalore",
                "distance": "2.1 km",
                "eta": "6 min",
                "trauma": True
            },
            {
                "name": "Manipal Hospital",
                "distance": "3.4 km",
                "eta": "9 min",
                "trauma": True
            },
            {
                "name": "St. Martha's Hospital",
                "distance": "4.8 km",
                "eta": "12 min",
                "trauma": True
            }
        ]
    })


# -------------------------------------------------
# MAIN
# -------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug_mode
    )