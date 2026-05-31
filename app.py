import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect, render_template_string
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

# -------------------------------------------------
# ENVIRONMENT VARIABLES
# -------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Family / emergency contacts
EMERGENCY_CONTACTS = os.getenv(
    "EMERGENCY_CONTACTS",
    os.getenv("EMERGENCY_CONTACT", "")
)

# Hospital demo contact numbers
HOSPITAL_CONTACTS = os.getenv("HOSPITAL_CONTACTS", "")

# Demo 108 ambulance contact number
DEMO_108 = os.getenv("DEMO_108", "")


# -------------------------------------------------
# CONTACT HANDLING
# -------------------------------------------------

def parse_contact_list(contact_string):
    """
    Converts comma-separated numbers into a list.
    Example:
    +917483348177,+91XXXXXXXXXX
    """
    if not contact_string:
        return []

    return [
        num.strip()
        for num in contact_string.split(",")
        if num.strip()
    ]


def get_emergency_contacts():
    return parse_contact_list(EMERGENCY_CONTACTS)


def get_hospital_contacts():
    return parse_contact_list(HOSPITAL_CONTACTS)


def get_demo_108_contacts():
    return parse_contact_list(DEMO_108)


# -------------------------------------------------
# SEPARATE ALERT MESSAGES
# -------------------------------------------------

def build_family_alert_message(data):
    name = data.get("name", "Demo User")
    latitude = data.get("latitude", "12.8249")
    longitude = data.get("longitude", "77.5159")
    hospital = data.get("hospital", "Nearest Hospital")
    eta = data.get("eta", "6 min")

    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"

    return (
        f"RAKSHA FAMILY ALERT: Accident detected for {name}. "
        f"Location: {maps_link}. "
        f"Nearest hospital: {hospital}. "
        f"Estimated ambulance ETA: {eta}. "
        f"Please contact the user immediately."
    )


def build_hospital_alert_message(data):
    name = data.get("name", "Demo User")
    latitude = data.get("latitude", "12.8249")
    longitude = data.get("longitude", "77.5159")
    severity = data.get("severity", "High")
    eta = data.get("eta", "6 min")

    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"

    return (
        f"RAKSHA HOSPITAL ALERT: Possible road accident case incoming. "
        f"Patient/User: {name}. "
        f"Severity: {severity}. "
        f"Accident location: {maps_link}. "
        f"ETA: {eta}. "
        f"Please keep emergency/trauma support ready."
    )


def build_108_alert_message(data):
    name = data.get("name", "Demo User")
    latitude = data.get("latitude", "12.8249")
    longitude = data.get("longitude", "77.5159")
    hospital = data.get("hospital", "Nearest Hospital")

    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"

    return (
        f"RAKSHA 108 DEMO ALERT: Accident detected. "
        f"User: {name}. "
        f"Pickup location: {maps_link}. "
        f"Suggested hospital: {hospital}. "
        f"Ambulance dispatch required."
    )


# Backward-compatible old alert message
def build_alert_message(data):
    return build_family_alert_message(data)


# -------------------------------------------------
# TWILIO MESSAGE SENDING
# -------------------------------------------------

def send_twilio_message_to_contacts(message, contacts, category):
    """
    Sends message to a specific contact group.
    First tries WhatsApp. If WhatsApp fails, tries SMS.
    """

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "category": category,
            "error": "Twilio credentials missing."
        }

    if not contacts:
        return {
            "success": False,
            "category": category,
            "error": f"No {category} contacts found."
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
                    contact
                    if contact.startswith("whatsapp:")
                    else f"whatsapp:{contact}"
                )

                whatsapp_from = (
                    TWILIO_PHONE_NUMBER
                    if TWILIO_PHONE_NUMBER.startswith("whatsapp:")
                    else f"whatsapp:{TWILIO_PHONE_NUMBER}"
                )

                msg = client.messages.create(
                    body=message,
                    from_=whatsapp_from,
                    to=whatsapp_to
                )

                sent_messages.append({
                    "to": contact,
                    "sid": msg.sid,
                    "status": msg.status,
                    "via": "whatsapp"
                })

            except Exception as whatsapp_error:
                # If WhatsApp fails, try normal SMS
                try:
                    msg = client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=contact
                    )

                    sent_messages.append({
                        "to": contact,
                        "sid": msg.sid,
                        "status": msg.status,
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
            "category": category,
            "sent_count": len(sent_messages),
            "failed_count": len(failed_messages),
            "messages": sent_messages,
            "failed": failed_messages
        }

    except Exception as e:
        return {
            "success": False,
            "category": category,
            "error": str(e)
        }


def send_twilio_sms(message):
    """
    Backward-compatible old function.
    Sends only to emergency contacts.
    """
    return send_twilio_message_to_contacts(
        message,
        get_emergency_contacts(),
        "emergency_contacts"
    )


def send_all_accident_alerts(data):
    """
    Sends three separate alert messages:
    1. Family / emergency contact
    2. Hospital contact
    3. Demo 108 contact
    """

    family_message = build_family_alert_message(data)
    hospital_message = build_hospital_alert_message(data)
    demo_108_message = build_108_alert_message(data)

    family_result = send_twilio_message_to_contacts(
        family_message,
        get_emergency_contacts(),
        "emergency_contacts"
    )

    hospital_result = send_twilio_message_to_contacts(
        hospital_message,
        get_hospital_contacts(),
        "hospital_contacts"
    )

    demo_108_result = send_twilio_message_to_contacts(
        demo_108_message,
        get_demo_108_contacts(),
        "demo_108"
    )

    return {
        "family_message": family_message,
        "hospital_message": hospital_message,
        "demo_108_message": demo_108_message,
        "family_result": family_result,
        "hospital_result": hospital_result,
        "demo_108_result": demo_108_result
    }


# -------------------------------------------------
# CHATBOT — Gemini if available, fallback if not
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
    return redirect("/dashboard")


@app.route("/health")
def health():
    return jsonify({
        "status": "running",
        "project": "RAKSHA AI",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/dashboard")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>RAKSHA AI Dashboard</title>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #ffffff;
        }

        header {
            background: linear-gradient(135deg, #dc2626, #7f1d1d);
            padding: 25px;
            text-align: center;
        }

        header h1 {
            margin: 0;
            font-size: 32px;
        }

        header p {
            margin-top: 8px;
            color: #fee2e2;
        }

        .container {
            max-width: 1100px;
            margin: auto;
            padding: 25px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
        }

        .card {
            background: #1e293b;
            border-radius: 14px;
            padding: 20px;
            box-shadow: 0 8px 18px rgba(0, 0, 0, 0.25);
        }

        .card h2 {
            margin-top: 0;
            color: #f87171;
        }

        input, textarea {
            width: 100%;
            padding: 11px;
            margin: 8px 0;
            border: none;
            border-radius: 8px;
            box-sizing: border-box;
        }

        button {
            background: #dc2626;
            color: white;
            border: none;
            padding: 12px 16px;
            margin-top: 10px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-weight: bold;
        }

        button:hover {
            background: #b91c1c;
        }

        pre {
            background: #020617;
            color: #22c55e;
            padding: 15px;
            border-radius: 10px;
            overflow-x: auto;
            white-space: pre-wrap;
            max-height: 350px;
        }

        .badge {
            display: inline-block;
            padding: 6px 10px;
            border-radius: 20px;
            background: #166534;
            color: white;
            font-size: 13px;
            margin-bottom: 10px;
        }

        .danger {
            background: #991b1b;
        }

        footer {
            text-align: center;
            padding: 20px;
            color: #94a3b8;
        }
    </style>
</head>

<body>

<header>
    <h1>RAKSHA AI Emergency Dashboard</h1>
    <p>Accident Detection | Hospital Alert | Emergency Contacts | Demo 108 Alert</p>
</header>

<div class="container">

    <div class="grid">

        <div class="card">
            <span class="badge">Backend</span>
            <h2>System Status</h2>
            <p>Check if Render environment variables and backend are active.</p>
            <button onclick="checkStatus()">Check Status</button>
            <pre id="statusOutput">Status result will appear here...</pre>
        </div>

        <div class="card">
            <span class="badge danger">Emergency</span>
            <h2>Accident Trigger</h2>
            <p>This simulates g-force accident detection and sends separate alerts.</p>

            <input id="name" value="Demo User" placeholder="User name">
            <input id="latitude" value="12.8249" placeholder="Latitude">
            <input id="longitude" value="77.5159" placeholder="Longitude">
            <input id="hospital" value="Fortis Hospital Bangalore" placeholder="Nearest hospital">
            <input id="eta" value="6 min" placeholder="ETA">

            <input id="accelerometer_score" value="90" placeholder="Accelerometer score">
            <input id="sound_score" value="85" placeholder="Sound score">

            <button onclick="triggerAccident()">Trigger Accident Alert</button>
            <pre id="accidentOutput">Accident result will appear here...</pre>
        </div>

        <div class="card">
            <span class="badge">Hospital</span>
            <h2>Find Nearby Hospital</h2>
            <p>Returns nearby demo hospitals for routing.</p>

            <input id="hospitalLat" value="12.8249" placeholder="Latitude">
            <input id="hospitalLng" value="77.5159" placeholder="Longitude">

            <button onclick="findHospital()">Find Hospital</button>
            <pre id="hospitalOutput">Hospital result will appear here...</pre>
        </div>

        <div class="card">
            <span class="badge">Chatbot</span>
            <h2>RAKSHA AI Chat</h2>
            <p>Test Tamil/Hindi/English first-aid chatbot.</p>

            <textarea id="chatMessage" rows="3" placeholder="Ask something...">first aid</textarea>

            <button onclick="sendChat()">Ask RAKSHA</button>
            <pre id="chatOutput">Chat response will appear here...</pre>
        </div>

    </div>

</div>

<footer>
    RAKSHA AI Hackathon Demo Dashboard
</footer>

<script>
    async function checkStatus() {
        const output = document.getElementById("statusOutput");
        output.textContent = "Checking backend status...";

        try {
            const response = await fetch("/api/status");
            const data = await response.json();
            output.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            output.textContent = "Error: " + error.message;
        }
    }

    async function triggerAccident() {
        const output = document.getElementById("accidentOutput");
        output.textContent = "Triggering accident alert...";

        const payload = {
            name: document.getElementById("name").value,
            latitude: document.getElementById("latitude").value,
            longitude: document.getElementById("longitude").value,
            hospital: document.getElementById("hospital").value,
            eta: document.getElementById("eta").value,
            accelerometer_score: document.getElementById("accelerometer_score").value,
            sound_score: document.getElementById("sound_score").value
        };

        try {
            const response = await fetch("/api/accident/trigger", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            output.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            output.textContent = "Error: " + error.message;
        }
    }

    async function findHospital() {
        const output = document.getElementById("hospitalOutput");
        output.textContent = "Finding nearby hospitals...";

        const payload = {
            latitude: document.getElementById("hospitalLat").value,
            longitude: document.getElementById("hospitalLng").value
        };

        try {
            const response = await fetch("/find-hospital", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            output.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            output.textContent = "Error: " + error.message;
        }
    }

    async function sendChat() {
        const output = document.getElementById("chatOutput");
        output.textContent = "RAKSHA AI is replying...";

        const payload = {
            message: document.getElementById("chatMessage").value
        };

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            output.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            output.textContent = "Error: " + error.message;
        }
    }
</script>

</body>
</html>
    """)


@app.route("/api/status")
def api_status():
    return jsonify({
        "message": "RAKSHA AI backend running successfully",
        "env_loaded": {
            "GEMINI_API_KEY": bool(GEMINI_API_KEY),
            "TWILIO_ACCOUNT_SID": bool(TWILIO_ACCOUNT_SID),
            "TWILIO_AUTH_TOKEN": bool(TWILIO_AUTH_TOKEN),
            "TWILIO_PHONE_NUMBER": bool(TWILIO_PHONE_NUMBER),
            "EMERGENCY_CONTACTS": bool(get_emergency_contacts()),
            "HOSPITAL_CONTACTS": bool(get_hospital_contacts()),
            "DEMO_108": bool(get_demo_108_contacts())
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
    Manual test endpoint.
    Sends separate messages to family, hospital, and demo 108.
    """

    data = request.get_json(silent=True) or {}

    alert_data = {
        "name": data.get("name", "Demo User"),
        "latitude": data.get("latitude", "12.8249"),
        "longitude": data.get("longitude", "77.5159"),
        "hospital": data.get("hospital", "Fortis Hospital Bangalore"),
        "eta": data.get("eta", "6 min"),
        "severity": data.get("severity", "High")
    }

    result = send_all_accident_alerts(alert_data)

    return jsonify({
        "status": "manual_alert_sent",
        "result": result
    })


@app.route("/api/accident/trigger", methods=["GET", "POST"])
def trigger_accident():
    """
    Main automatic accident trigger endpoint.

    If combined score > 70:
    - family alert goes to EMERGENCY_CONTACTS
    - hospital alert goes to HOSPITAL_CONTACTS
    - ambulance alert goes to DEMO_108
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

    try:
        accelerometer_score = float(data.get("accelerometer_score", 85))
        sound_score = float(data.get("sound_score", 78))
    except ValueError:
        return jsonify({
            "error": "accelerometer_score and sound_score must be numbers"
        }), 400

    combined_score = (accelerometer_score * 0.55) + (sound_score * 0.45)
    accident_confirmed = combined_score > 70

    if accident_confirmed:
        alert_data = {
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "hospital": hospital,
            "eta": eta,
            "severity": "High"
        }

        alert_result = send_all_accident_alerts(alert_data)

        alert_message = (
            "Accident confirmed. Separate alerts sent to emergency contacts, "
            "hospital contacts, and demo 108."
        )

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