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

EMERGENCY_CONTACTS = os.getenv(
    "EMERGENCY_CONTACTS",
    os.getenv("EMERGENCY_CONTACT", "")
)

HOSPITAL_CONTACTS = os.getenv("HOSPITAL_CONTACTS", "")
DEMO_108 = os.getenv("DEMO_108", "")


# -------------------------------------------------
# CONTACT HANDLING
# -------------------------------------------------

def parse_contact_list(contact_string):
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
        f"AAROHI FAMILY ALERT: Accident detected for {name}. "
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
        f"AAROHI HOSPITAL ALERT: Possible road accident case incoming. "
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
        f"AAROHI 108 DEMO ALERT: Accident detected. "
        f"User: {name}. "
        f"Pickup location: {maps_link}. "
        f"Suggested hospital: {hospital}. "
        f"Ambulance dispatch required."
    )


def build_alert_message(data):
    return build_family_alert_message(data)


# -------------------------------------------------
# TWILIO MESSAGE SENDING
# -------------------------------------------------

def send_twilio_message_to_contacts(message, contacts, category):
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
    return send_twilio_message_to_contacts(
        message,
        get_emergency_contacts(),
        "emergency_contacts"
    )


def send_all_accident_alerts(data):
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
# CHATBOT FALLBACK RESPONSES
# -------------------------------------------------

CHAT_RESPONSES = {
    "first_aid": {
        "en": "First aid: Do not move the injured person. Check breathing. Call 108. Apply pressure to bleeding wounds.",
        "hi": "प्राथमिक चिकित्सा: घायल व्यक्ति को न हिलाएं। सांस जांचें। 108 कॉल करें। खून बहने पर दबाव डालें।",
        "ta": "முதலுதவி: காயமடைந்த நபரை நகர்த்தாதீர்கள். சுவாசம் சரிபார்க்கவும். 108 அழைக்கவும். இரத்தப்போக்கை அழுத்தத்தால் நிறுத்தவும்.",
        "kn": "ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ: ಗಾಯಗೊಂಡ ವ್ಯಕ್ತಿಯನ್ನು ಕದಲಿಸಬೇಡಿ. ಉಸಿರಾಟ ಪರಿಶೀಲಿಸಿ. 108 ಗೆ ಕರೆ ಮಾಡಿ. ರಕ್ತಸ್ರಾವ ಇದ್ದರೆ ಒತ್ತಡ ಹಾಕಿ.",
        "te": "ప్రథమ చికిత్స: గాయపడిన వ్యక్తిని కదలించవద్దు. శ్వాసను పరీక్షించండి. 108 కి కాల్ చేయండి. రక్తస్రావం ఉంటే ఒత్తిడి పెట్టండి.",
        "ml": "പ്രഥമ ശുശ്രൂഷ: പരിക്കേറ്റ വ്യക്തിയെ നീക്കരുത്. ശ്വാസം പരിശോധിക്കുക. 108 വിളിക്കുക. രക്തസ്രാവം ഉണ്ടെങ്കിൽ സമ്മർദ്ദം നൽകുക.",
        "mr": "प्राथमिक उपचार: जखमी व्यक्तीला हलवू नका. श्वास तपासा. 108 वर कॉल करा. रक्तस्त्राव होत असल्यास दाब द्या.",
        "bn": "প্রাথমিক চিকিৎসা: আহত ব্যক্তিকে নড়াবেন না। শ্বাস পরীক্ষা করুন। 108-এ কল করুন। রক্তপাত হলে চাপ দিন।",
        "gu": "પ્રાથમિક સારવાર: ઇજાગ્રસ્ત વ્યક્તિને ખસેડશો નહીં. શ્વાસ તપાસો. 108 પર કોલ કરો. રક્તસ્ત્રાવ હોય તો દબાણ આપો.",
        "pa": "ਪਹਿਲੀ ਸਹਾਇਤਾ: ਜ਼ਖਮੀ ਵਿਅਕਤੀ ਨੂੰ ਨਾ ਹਿਲਾਓ। ਸਾਹ ਚੈੱਕ ਕਰੋ। 108 ਤੇ ਕਾਲ ਕਰੋ। ਖੂਨ ਵਗੇ ਤਾਂ ਦਬਾਅ ਦਿਓ."
    },
    "accident": {
        "en": "Accident detected. Help is on the way. Please stay calm.",
        "hi": "दुर्घटना का पता चला। मदद आ रही है। घबराएं नहीं।",
        "ta": "விபத்து கண்டறியப்பட்டது. உதவி வருகிறது. பயப்படாதீர்கள்.",
        "kn": "ಅಪಘಾತ ಪತ್ತೆಯಾಗಿದೆ. ಸಹಾಯ ಬರುತ್ತಿದೆ. ದಯವಿಟ್ಟು ಶಾಂತವಾಗಿರಿ.",
        "te": "ప్రమాదం గుర్తించబడింది. సహాయం వస్తోంది. దయచేసి ప్రశాంతంగా ఉండండి.",
        "ml": "അപകടം കണ്ടെത്തി. സഹായം വരുന്നു. ദയവായി ശാന്തരാകൂ.",
        "mr": "अपघात आढळला आहे. मदत येत आहे. कृपया शांत रहा.",
        "bn": "দুর্ঘটনা শনাক্ত হয়েছে। সাহায্য আসছে। অনুগ্রহ করে শান্ত থাকুন।",
        "gu": "અકસ્મીક ઘટના ઓળખાઈ છે. મદદ આવી રહી છે. કૃપા કરીને શાંત રહો.",
        "pa": "ਹਾਦਸਾ ਪਤਾ ਲੱਗ ਗਿਆ ਹੈ। ਮਦਦ ਆ ਰਹੀ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਸ਼ਾਂਤ ਰਹੋ।"
    },
    "hospital": {
        "en": "Nearest trauma hospital found. Ambulance support is being arranged.",
        "hi": "नजदीकी अस्पताल मिल गया। एम्बुलेंस सहायता की व्यवस्था की जा रही है।",
        "ta": "அருகிலுள்ள மருத்துவமனை கண்டறியப்பட்டது. ஆம்புலன்ஸ் உதவி ஏற்பாடு செய்யப்படுகிறது.",
        "kn": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಕಂಡುಬಂದಿದೆ. ಆಂಬ್ಯುಲೆನ್ಸ್ ಸಹಾಯವನ್ನು ವ್ಯವಸ್ಥೆ ಮಾಡಲಾಗುತ್ತಿದೆ.",
        "te": "సమీప ఆసుపత్రి కనుగొనబడింది. అంబులెన్స్ సహాయం ఏర్పాటు చేయబడుతోంది.",
        "ml": "അടുത്തുള്ള ആശുപത്രി കണ്ടെത്തി. ആംബുലൻസ് സഹായം ക്രമീകരിക്കുന്നു.",
        "mr": "जवळचे रुग्णालय सापडले आहे. रुग्णवाहिका मदत व्यवस्था केली जात आहे.",
        "bn": "নিকটতম হাসপাতাল পাওয়া গেছে। অ্যাম্বুলেন্স সহায়তা ব্যবস্থা করা হচ্ছে।",
        "gu": "નજીકની હોસ્પિટલ મળી ગઈ છે. એમ્બ્યુલન્સ મદદની વ્યવસ્થા થઈ રહી છે.",
        "pa": "ਨੇੜਲਾ ਹਸਪਤਾਲ ਮਿਲ ਗਿਆ ਹੈ। ਐਂਬੂਲੈਂਸ ਸਹਾਇਤਾ ਦਾ ਪ੍ਰਬੰਧ ਕੀਤਾ ਜਾ ਰਿਹਾ ਹੈ।"
    },
    "default": {
        "en": "I am AAROHI AI. I can help with accident alerts, nearby hospitals, and first aid.",
        "hi": "मैं AAROHI AI हूं। मैं दुर्घटना अलर्ट, नजदीकी अस्पताल और प्राथमिक चिकित्सा में मदद कर सकता हूं।",
        "ta": "நான் AAROHI AI. விபத்து எச்சரிக்கை, அருகிலுள்ள மருத்துவமனை மற்றும் முதலுதவியில் உதவ முடியும்.",
        "kn": "ನಾನು AAROHI AI. ಅಪಘಾತ ಎಚ್ಚರಿಕೆ, ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಮತ್ತು ಪ್ರಥಮ ಚಿಕಿತ್ಸೆಯಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಹುದು.",
        "te": "నేను AAROHI AI. ప్రమాద హెచ్చరికలు, సమీప ఆసుపత్రులు మరియు ప్రథమ చికిత్సలో సహాయం చేయగలను.",
        "ml": "ഞാൻ AAROHI AIആണ്. അപകട മുന്നറിയിപ്പുകൾ, അടുത്തുള്ള ആശുപത്രികൾ, പ്രഥമ ശുശ്രൂഷ എന്നിവയിൽ സഹായിക്കാം.",
        "mr": "मी AAROHI AI आहे. अपघात अलर्ट, जवळचे रुग्णालय आणि प्राथमिक उपचारात मदत करू शकतो.",
        "bn": "আমি AAROHI AI । দুর্ঘটনা সতর্কতা, নিকটতম হাসপাতাল এবং প্রাথমিক চিকিৎসায় সাহায্য করতে পারি।",
        "gu": "હું AAROHI AIછું. અકસ્માત એલર્ટ, નજીકની હોસ્પિટલ અને પ્રાથમિક સારવારમાં મદદ કરી શકું છું.",
        "pa": "ਮੈਂ AAROHI AIਹਾਂ। ਮੈਂ ਹਾਦਸਾ ਅਲਰਟ, ਨੇੜਲਾ ਹਸਪਤਾਲ ਅਤੇ ਪਹਿਲੀ ਸਹਾਇਤਾ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ।"
    }
}


def detect_language(message):
    ranges = {
        "ta": ("\u0B80", "\u0BFF"),
        "kn": ("\u0C80", "\u0CFF"),
        "te": ("\u0C00", "\u0C7F"),
        "ml": ("\u0D00", "\u0D7F"),
        "bn": ("\u0980", "\u09FF"),
        "gu": ("\u0A80", "\u0AFF"),
        "pa": ("\u0A00", "\u0A7F"),
        "hi": ("\u0900", "\u097F"),
    }

    for char in message:
        for lang, (start, end) in ranges.items():
            if start <= char <= end:
                if lang == "hi":
                    if any(word in message for word in ["आहे", "अपघात", "रुग्णालय"]):
                        return "mr"
                return lang

    return "en"


def get_intent(message):
    msg = message.lower()

    accident_words = [
        "accident", "crash", "impact", "collision",
        "दुर्घटना", "अपघात", "விபத்து", "ಅಪಘಾತ", "ప్రమాదం",
        "അപകടം", "দুর্ঘটনা", "અકસ્માત", "ਹਾਦਸਾ"
    ]

    hospital_words = [
        "hospital", "ambulance", "doctor",
        "अस्पताल", "रुग्णालय", "மருத்துவமனை", "ಆಸ್ಪತ್ರೆ",
        "ఆసుపత్రి", "ആശുപത്രി", "হাসপাতাল", "હોસ્પિટલ", "ਹਸਪਤਾਲ"
    ]

    first_aid_words = [
        "first aid", "bleeding", "breath", "injured",
        "प्राथमिक", "प्रथमोपचार", "முதலுதவி", "ಪ್ರಥಮ",
        "ప్రథమ", "പ്രഥമ", "প্রাথমিক", "પ્રાથમિક", "ਪਹਿਲੀ"
    ]

    if any(word in msg or word in message for word in accident_words):
        return "accident"

    if any(word in msg or word in message for word in hospital_words):
        return "hospital"

    if any(word in msg or word in message for word in first_aid_words):
        return "first_aid"

    return "default"


def gemini_chat(message, lang):
    if not GEMINI_API_KEY:
        return None

    try:
        import requests

        language_name = {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "kn": "Kannada",
            "te": "Telugu",
            "ml": "Malayalam",
            "mr": "Marathi",
            "bn": "Bengali",
            "gu": "Gujarati",
            "pa": "Punjabi"
        }.get(lang, "English")

        system_prompt = f"""
You are AAROHI AI, an emergency road accident detection and rescue assistant.
Respond only in {language_name}.
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
        "project": "AAROHI AI",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/dashboard")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AAROHI AI Dashboard</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f8fafc;
            color: #111827;
        }

        header {
            background: #dc2626;
            color: white;
            padding: 26px;
            text-align: center;
        }

        header h1 {
            margin: 0;
            font-size: 34px;
        }

        header p {
            margin-top: 8px;
            font-size: 16px;
        }

        .container {
            max-width: 1080px;
            margin: auto;
            padding: 24px;
        }

        .language-box {
            text-align: center;
            margin-bottom: 24px;
        }

        .language-box button {
            background: white;
            color: #dc2626;
            border: 2px solid #dc2626;
            padding: 10px 14px;
            margin: 5px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
        }

        .language-box button.active {
            background: #dc2626;
            color: white;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
        }

        .card {
            background: white;
            padding: 22px;
            border-radius: 14px;
            box-shadow: 0 5px 16px rgba(0, 0, 0, 0.12);
            text-align: center;
        }

        .card h2 {
            color: #dc2626;
            margin-top: 0;
        }

        .icon {
            font-size: 42px;
            margin-bottom: 10px;
        }

        input {
            width: 100%;
            padding: 11px;
            margin: 7px 0;
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            box-sizing: border-box;
        }

        .main-btn {
            background: #dc2626;
            color: white;
            border: none;
            padding: 13px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 10px;
            width: 100%;
        }

        .main-btn:hover {
            background: #b91c1c;
        }

        .result {
            margin-top: 15px;
            padding: 14px;
            background: #ecfdf5;
            color: #166534;
            border-radius: 8px;
            display: none;
            font-weight: bold;
            line-height: 1.5;
        }

        .error {
            background: #fef2f2;
            color: #991b1b;
        }

        footer {
            text-align: center;
            padding: 20px;
            color: #64748b;
        }
    </style>
</head>

<body>

<header>
    <h1 id="title">AAROHI AI</h1>
    <p id="subtitle">Emergency Accident Detection and Rescue Alert System</p>
</header>

<div class="container">

    <div class="language-box">
        <button id="btn-en" class="active" onclick="setLanguage('en')">English</button>
        <button id="btn-hi" onclick="setLanguage('hi')">हिंदी</button>
        <button id="btn-ta" onclick="setLanguage('ta')">தமிழ்</button>
        <button id="btn-kn" onclick="setLanguage('kn')">ಕನ್ನಡ</button>
        <button id="btn-te" onclick="setLanguage('te')">తెలుగు</button>
        <button id="btn-ml" onclick="setLanguage('ml')">മലയാളം</button>
        <button id="btn-mr" onclick="setLanguage('mr')">मराठी</button>
        <button id="btn-bn" onclick="setLanguage('bn')">বাংলা</button>
        <button id="btn-gu" onclick="setLanguage('gu')">ગુજરાતી</button>
        <button id="btn-pa" onclick="setLanguage('pa')">ਪੰਜਾਬੀ</button>
    </div>

    <div class="grid">

        <div class="card">
            <div class="icon">🚨</div>
            <h2 id="accidentTitle">Accident Alert</h2>
            <p id="accidentText">
                Simulate accident detection and send alerts to family, hospital and 108 demo contact.
            </p>

            <input id="name" value="Demo User" placeholder="User name">
            <input id="latitude" value="12.8249" placeholder="Latitude">
            <input id="longitude" value="77.5159" placeholder="Longitude">
            <input id="hospital" value="Fortis Hospital Bangalore" placeholder="Nearest hospital">

            <button class="main-btn" id="triggerBtn" onclick="triggerAccident()">
                Trigger Accident Alert
            </button>

            <div id="accidentResult" class="result"></div>
        </div>

        <div class="card">
            <div class="icon">🏥</div>
            <h2 id="hospitalTitle">Nearest Hospital</h2>
            <p id="hospitalText">
                Find nearby trauma hospitals for emergency routing.
            </p>

            <button class="main-btn" id="hospitalBtn" onclick="findHospital()">
                Find Hospital
            </button>

            <div id="hospitalResult" class="result"></div>
        </div>

        <div class="card">
            <div class="icon">🩹</div>
            <h2 id="firstAidTitle">First Aid Help</h2>
            <p id="firstAidText">
                Get quick first-aid guidance in your selected language.
            </p>

            <button class="main-btn" id="firstAidBtn" onclick="firstAidHelp()">
                Show First Aid
            </button>

            <div id="firstAidResult" class="result"></div>
        </div>

    </div>

</div>

<footer id="footerText">
    AAROHI AI Hackathon Demo
</footer>

<script>
    let currentLang = "en";

    const text = {
        en: {
            title: "AAROHI AI",
            subtitle: "Emergency Accident Detection and Rescue Alert System",
            accidentTitle: "Accident Alert",
            accidentText: "Simulate accident detection and send alerts to family, hospital and 108 demo contact.",
            triggerBtn: "Trigger Accident Alert",
            hospitalTitle: "Nearest Hospital",
            hospitalText: "Find nearby trauma hospitals for emergency routing.",
            hospitalBtn: "Find Hospital",
            firstAidTitle: "First Aid Help",
            firstAidText: "Get quick first-aid guidance in your selected language.",
            firstAidBtn: "Show First Aid",
            footerText: "AAROHI AI Hackathon Demo",
            sending: "Sending emergency alerts...",
            alertSuccess: "Accident alert sent to emergency contacts, hospital and 108 demo contact.",
            alertFailed: "Alert could not be sent. Please check contact setup.",
            hospitalFound: "Nearest hospitals found: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "First aid: Do not move the injured person. Check breathing. Call 108. Apply pressure to bleeding wounds."
        },

        hi: {
            title: "AAROHI AI",
            subtitle: "आपातकालीन दुर्घटना पहचान और बचाव अलर्ट सिस्टम",
            accidentTitle: "दुर्घटना अलर्ट",
            accidentText: "दुर्घटना पहचान का डेमो करके परिवार, अस्पताल और 108 डेमो संपर्क को अलर्ट भेजता है।",
            triggerBtn: "दुर्घटना अलर्ट भेजें",
            hospitalTitle: "नजदीकी अस्पताल",
            hospitalText: "आपातकालीन इलाज के लिए नजदीकी अस्पताल खोजें।",
            hospitalBtn: "अस्पताल खोजें",
            firstAidTitle: "प्राथमिक चिकित्सा",
            firstAidText: "चुनी हुई भाषा में तुरंत प्राथमिक चिकित्सा सहायता पाएं।",
            firstAidBtn: "प्राथमिक चिकित्सा दिखाएं",
            footerText: "AAROHI AI हैकाथॉन डेमो",
            sending: "आपातकालीन अलर्ट भेजे जा रहे हैं...",
            alertSuccess: "दुर्घटना अलर्ट परिवार, अस्पताल और 108 डेमो संपर्क को भेज दिया गया।",
            alertFailed: "अलर्ट भेजा नहीं जा सका। संपर्क सेटअप जांचें।",
            hospitalFound: "नजदीकी अस्पताल: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "प्राथमिक चिकित्सा: घायल व्यक्ति को न हिलाएं। सांस जांचें। 108 कॉल करें। खून बहने पर दबाव डालें।"
        },

        ta: {
            title: "AAROHI AI",
            subtitle: "அவசர விபத்து கண்டறிதல் மற்றும் மீட்பு எச்சரிக்கை அமைப்பு",
            accidentTitle: "விபத்து எச்சரிக்கை",
            accidentText: "விபத்து கண்டறிதலை சோதித்து குடும்பம், மருத்துவமனை மற்றும் 108 டெமோ தொடர்புக்கு எச்சரிக்கை அனுப்பும்.",
            triggerBtn: "விபத்து எச்சரிக்கை அனுப்பு",
            hospitalTitle: "அருகிலுள்ள மருத்துவமனை",
            hospitalText: "அவசர சிகிச்சைக்கு அருகிலுள்ள மருத்துவமனைகளை கண்டறியும்.",
            hospitalBtn: "மருத்துவமனை கண்டறி",
            firstAidTitle: "முதலுதவி உதவி",
            firstAidText: "தேர்ந்தெடுத்த மொழியில் விரைவான முதலுதவி வழிகாட்டல்.",
            firstAidBtn: "முதலுதவி காட்டு",
            footerText: "AAROHI AI ஹாக்கத்தான் டெமோ",
            sending: "அவசர எச்சரிக்கைகள் அனுப்பப்படுகின்றன...",
            alertSuccess: "விபத்து எச்சரிக்கை குடும்பம், மருத்துவமனை மற்றும் 108 டெமோ தொடர்புக்கு அனுப்பப்பட்டது.",
            alertFailed: "எச்சரிக்கை அனுப்ப முடியவில்லை. தொடர்பு அமைப்பை சரிபார்க்கவும்.",
            hospitalFound: "அருகிலுள்ள மருத்துவமனைகள்: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "முதலுதவி: காயமடைந்த நபரை நகர்த்தாதீர்கள். சுவாசம் சரிபார்க்கவும். 108 அழைக்கவும். இரத்தப்போக்கை அழுத்தத்தால் நிறுத்தவும்."
        },

        kn: {
            title: "AAROHI AI ",
            subtitle: "ತುರ್ತು ಅಪಘಾತ ಪತ್ತೆ ಮತ್ತು ರಕ್ಷಣಾ ಎಚ್ಚರಿಕೆ ವ್ಯವಸ್ಥೆ",
            accidentTitle: "ಅಪಘಾತ ಎಚ್ಚರಿಕೆ",
            accidentText: "ಅಪಘಾತ ಪತ್ತೆಯನ್ನು ಪರೀಕ್ಷಿಸಿ ಕುಟುಂಬ, ಆಸ್ಪತ್ರೆ ಮತ್ತು 108 ಡೆಮೋ ಸಂಪರ್ಕಕ್ಕೆ ಎಚ್ಚರಿಕೆ ಕಳುಹಿಸುತ್ತದೆ.",
            triggerBtn: "ಅಪಘಾತ ಎಚ್ಚರಿಕೆ ಕಳುಹಿಸಿ",
            hospitalTitle: "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ",
            hospitalText: "ತುರ್ತು ಚಿಕಿತ್ಸೆಗೆ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗಳನ್ನು ಕಂಡುಹಿಡಿಯಿರಿ.",
            hospitalBtn: "ಆಸ್ಪತ್ರೆ ಹುಡುಕಿ",
            firstAidTitle: "ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ",
            firstAidText: "ಆಯ್ಕೆ ಮಾಡಿದ ಭಾಷೆಯಲ್ಲಿ ತ್ವರಿತ ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ ಮಾರ್ಗದರ್ಶನ ಪಡೆಯಿರಿ.",
            firstAidBtn: "ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ ತೋರಿಸಿ",
            footerText: "AAROHI AI ಹ್ಯಾಕಥಾನ್ ಡೆಮೋ",
            sending: "ತುರ್ತು ಎಚ್ಚರಿಕೆಗಳನ್ನು ಕಳುಹಿಸಲಾಗುತ್ತಿದೆ...",
            alertSuccess: "ಅಪಘಾತ ಎಚ್ಚರಿಕೆ ಕುಟುಂಬ, ಆಸ್ಪತ್ರೆ ಮತ್ತು 108 ಡೆಮೋ ಸಂಪರ್ಕಕ್ಕೆ ಕಳುಹಿಸಲಾಗಿದೆ.",
            alertFailed: "ಎಚ್ಚರಿಕೆ ಕಳುಹಿಸಲಾಗಲಿಲ್ಲ. ಸಂಪರ್ಕ ವ್ಯವಸ್ಥೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.",
            hospitalFound: "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗಳು: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ: ಗಾಯಗೊಂಡ ವ್ಯಕ್ತಿಯನ್ನು ಕದಲಿಸಬೇಡಿ. ಉಸಿರಾಟ ಪರಿಶೀಲಿಸಿ. 108 ಗೆ ಕರೆ ಮಾಡಿ. ರಕ್ತಸ್ರಾವ ಇದ್ದರೆ ಒತ್ತಡ ಹಾಕಿ."
        },

        te: {
            title: "AAROHI AI ",
            subtitle: "అత్యవసర ప్రమాద గుర్తింపు మరియు రక్షణ హెచ్చరిక వ్యవస్థ",
            accidentTitle: "ప్రమాద హెచ్చరిక",
            accidentText: "ప్రమాద గుర్తింపును పరీక్షించి కుటుంబం, ఆసుపత్రి మరియు 108 డెమో సంప్రదింపుకు హెచ్చరిక పంపుతుంది.",
            triggerBtn: "ప్రమాద హెచ్చరిక పంపండి",
            hospitalTitle: "సమీప ఆసుపత్రి",
            hospitalText: "అత్యవసర చికిత్స కోసం సమీప ఆసుపత్రులను కనుగొనండి.",
            hospitalBtn: "ఆసుపత్రి కనుగొనండి",
            firstAidTitle: "ప్రథమ చికిత్స",
            firstAidText: "ఎంచుకున్న భాషలో తక్షణ ప్రథమ చికిత్స సూచనలు పొందండి.",
            firstAidBtn: "ప్రథమ చికిత్స చూపించు",
            footerText: "AAROHI AI హ్యాకథాన్ డెమో",
            sending: "అత్యవసర హెచ్చరికలు పంపబడుతున్నాయి...",
            alertSuccess: "ప్రమాద హెచ్చరిక కుటుంబం, ఆసుపత్రి మరియు 108 డెమో సంప్రదింపుకు పంపబడింది.",
            alertFailed: "హెచ్చరిక పంపలేకపోయాం. సంప్రదింపు సెటప్ తనిఖీ చేయండి.",
            hospitalFound: "సమీప ఆసుపత్రులు: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "ప్రథమ చికిత్స: గాయపడిన వ్యక్తిని కదలించవద్దు. శ్వాసను పరీక్షించండి. 108 కి కాల్ చేయండి. రక్తస్రావం ఉంటే ఒత్తిడి పెట్టండి."
        },

        ml: {
            title: "AAROHI AI ",
            subtitle: "അടിയന്തര അപകട കണ്ടെത്തൽയും രക്ഷാ അലർട്ട് സംവിധാനവും",
            accidentTitle: "അപകട അലർട്ട്",
            accidentText: "അപകട കണ്ടെത്തൽ പരീക്ഷിച്ച് കുടുംബം, ആശുപത്രി, 108 ഡെമോ കോൺടാക്ട് എന്നിവർക്കു അലർട്ട് അയയ്ക്കുന്നു.",
            triggerBtn: "അപകട അലർട്ട് അയയ്ക്കുക",
            hospitalTitle: "അടുത്തുള്ള ആശുപത്രി",
            hospitalText: "അടിയന്തര ചികിത്സയ്ക്കായി അടുത്തുള്ള ആശുപത്രികൾ കണ്ടെത്തുക.",
            hospitalBtn: "ആശുപത്രി കണ്ടെത്തുക",
            firstAidTitle: "പ്രഥമ ശുശ്രൂഷ",
            firstAidText: "തിരഞ്ഞെടുത്ത ഭാഷയിൽ വേഗത്തിലുള്ള പ്രഥമ ശുശ്രൂഷ മാർഗ്ഗനിർദ്ദേശം നേടുക.",
            firstAidBtn: "പ്രഥമ ശുശ്രൂഷ കാണിക്കുക",
            footerText: "AAROHI AI ഹാക്കത്തോൺ ഡെമോ",
            sending: "അടിയന്തര അലർട്ടുകൾ അയയ്ക്കുന്നു...",
            alertSuccess: "അപകട അലർട്ട് കുടുംബം, ആശുപത്രി, 108 ഡെമോ കോൺടാക്ട് എന്നിവർക്കു അയച്ചു.",
            alertFailed: "അലർട്ട് അയയ്ക്കാൻ കഴിഞ്ഞില്ല. കോൺടാക്ട് സജ്ജീകരണം പരിശോധിക്കുക.",
            hospitalFound: "അടുത്തുള്ള ആശുപത്രികൾ: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "പ്രഥമ ശുശ്രൂഷ: പരിക്കേറ്റ വ്യക്തിയെ നീക്കരുത്. ശ്വാസം പരിശോധിക്കുക. 108 വിളിക്കുക. രക്തസ്രാവം ഉണ്ടെങ്കിൽ സമ്മർദ്ദം നൽകുക."
        },

        mr: {
            title: "AAROHI AI ",
            subtitle: "आपत्कालीन अपघात ओळख आणि बचाव अलर्ट प्रणाली",
            accidentTitle: "अपघात अलर्ट",
            accidentText: "अपघात ओळख डेमो करून कुटुंब, रुग्णालय आणि 108 डेमो संपर्काला अलर्ट पाठवते.",
            triggerBtn: "अपघात अलर्ट पाठवा",
            hospitalTitle: "जवळचे रुग्णालय",
            hospitalText: "आपत्कालीन उपचारासाठी जवळची रुग्णालये शोधा.",
            hospitalBtn: "रुग्णालय शोधा",
            firstAidTitle: "प्राथमिक उपचार",
            firstAidText: "निवडलेल्या भाषेत त्वरित प्राथमिक उपचार मार्गदर्शन मिळवा.",
            firstAidBtn: "प्राथमिक उपचार दाखवा",
            footerText: "AAROHI AI हॅकाथॉन डेमो",
            sending: "आपत्कालीन अलर्ट पाठवले जात आहेत...",
            alertSuccess: "अपघात अलर्ट कुटुंब, रुग्णालय आणि 108 डेमो संपर्काला पाठवला.",
            alertFailed: "अलर्ट पाठवता आला नाही. संपर्क सेटअप तपासा.",
            hospitalFound: "जवळची रुग्णालये: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "प्राथमिक उपचार: जखमी व्यक्तीला हलवू नका. श्वास तपासा. 108 वर कॉल करा. रक्तस्त्राव असल्यास दाब द्या."
        },

        bn: {
            title: "AAROHI AI ",
            subtitle: "জরুরি দুর্ঘটনা শনাক্তকরণ ও উদ্ধার সতর্কতা ব্যবস্থা",
            accidentTitle: "দুর্ঘটনা সতর্কতা",
            accidentText: "দুর্ঘটনা শনাক্তকরণের ডেমো করে পরিবার, হাসপাতাল এবং 108 ডেমো কন্ট্যাক্টে সতর্কতা পাঠায়।",
            triggerBtn: "দুর্ঘটনা সতর্কতা পাঠান",
            hospitalTitle: "নিকটতম হাসপাতাল",
            hospitalText: "জরুরি চিকিৎসার জন্য নিকটবর্তী হাসপাতাল খুঁজুন।",
            hospitalBtn: "হাসপাতাল খুঁজুন",
            firstAidTitle: "প্রাথমিক চিকিৎসা",
            firstAidText: "নির্বাচিত ভাষায় দ্রুত প্রাথমিক চিকিৎসার নির্দেশনা পান।",
            firstAidBtn: "প্রাথমিক চিকিৎসা দেখান",
            footerText: "AAROHI AI হ্যাকাথন ডেমো",
            sending: "জরুরি সতর্কতা পাঠানো হচ্ছে...",
            alertSuccess: "দুর্ঘটনা সতর্কতা পরিবার, হাসপাতাল এবং 108 ডেমো কন্ট্যাক্টে পাঠানো হয়েছে।",
            alertFailed: "সতর্কতা পাঠানো যায়নি। কন্ট্যাক্ট সেটআপ পরীক্ষা করুন।",
            hospitalFound: "নিকটতম হাসপাতাল: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "প্রাথমিক চিকিৎসা: আহত ব্যক্তিকে নড়াবেন না। শ্বাস পরীক্ষা করুন। 108-এ কল করুন। রক্তপাত হলে চাপ দিন।"
        },

        gu: {
            title: "AAROHI AI ",
            subtitle: "ઇમરજન્સી અકસ્માત ઓળખ અને બચાવ એલર્ટ સિસ્ટમ",
            accidentTitle: "અકસ્મિક એલર્ટ",
            accidentText: "અકસ્મિક ઓળખનો ડેમો કરીને પરિવાર, હોસ્પિટલ અને 108 ડેમો સંપર્કને એલર્ટ મોકલે છે.",
            triggerBtn: "અકસ્મિક એલર્ટ મોકલો",
            hospitalTitle: "નજીકની હોસ્પિટલ",
            hospitalText: "ઇમરજન્સી સારવાર માટે નજીકની હોસ્પિટલો શોધો.",
            hospitalBtn: "હોસ્પિટલ શોધો",
            firstAidTitle: "પ્રાથમિક સારવાર",
            firstAidText: "પસંદ કરેલી ભાષામાં ઝડપી પ્રાથમિક સારવાર માર્ગદર્શન મેળવો.",
            firstAidBtn: "પ્રાથમિક સારવાર બતાવો",
            footerText: "AAROHI AI હેકાથોન ડેમો",
            sending: "ઇમરજન્સી એલર્ટ મોકલાઈ રહ્યા છે...",
            alertSuccess: "અકસ્મિક એલર્ટ પરિવાર, હોસ્પિટલ અને 108 ડેમો સંપર્કને મોકલાયું.",
            alertFailed: "એલર્ટ મોકલી શકાયું નથી. સંપર્ક સેટઅપ તપાસો.",
            hospitalFound: "નજીકની હોસ્પિટલો: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "પ્રાથમિક સારવાર: ઇજાગ્રસ્ત વ્યક્તિને ખસેડશો નહીં. શ્વાસ તપાસો. 108 પર કોલ કરો. રક્તસ્ત્રાવ હોય તો દબાણ આપો."
        },

        pa: {
            title: "AAROHI AI ",
            subtitle: "ਐਮਰਜੈਂਸੀ ਹਾਦਸਾ ਪਛਾਣ ਅਤੇ ਬਚਾਅ ਅਲਰਟ ਸਿਸਟਮ",
            accidentTitle: "ਹਾਦਸਾ ਅਲਰਟ",
            accidentText: "ਹਾਦਸਾ ਪਛਾਣ ਦਾ ਡੈਮੋ ਕਰਕੇ ਪਰਿਵਾਰ, ਹਸਪਤਾਲ ਅਤੇ 108 ਡੈਮੋ ਸੰਪਰਕ ਨੂੰ ਅਲਰਟ ਭੇਜਦਾ ਹੈ।",
            triggerBtn: "ਹਾਦਸਾ ਅਲਰਟ ਭੇਜੋ",
            hospitalTitle: "ਨੇੜਲਾ ਹਸਪਤਾਲ",
            hospitalText: "ਐਮਰਜੈਂਸੀ ਇਲਾਜ ਲਈ ਨੇੜਲੇ ਹਸਪਤਾਲ ਲੱਭੋ।",
            hospitalBtn: "ਹਸਪਤਾਲ ਲੱਭੋ",
            firstAidTitle: "ਪਹਿਲੀ ਸਹਾਇਤਾ",
            firstAidText: "ਚੁਣੀ ਭਾਸ਼ਾ ਵਿੱਚ ਤੁਰੰਤ ਪਹਿਲੀ ਸਹਾਇਤਾ ਮਾਰਗਦਰਸ਼ਨ ਲਵੋ।",
            firstAidBtn: "ਪਹਿਲੀ ਸਹਾਇਤਾ ਦਿਖਾਓ",
            footerText: "AAROHI AIਹੈਕਾਥਾਨ ਡੈਮੋ",
            sending: "ਐਮਰਜੈਂਸੀ ਅਲਰਟ ਭੇਜੇ ਜਾ ਰਹੇ ਹਨ...",
            alertSuccess: "ਹਾਦਸਾ ਅਲਰਟ ਪਰਿਵਾਰ, ਹਸਪਤਾਲ ਅਤੇ 108 ਡੈਮੋ ਸੰਪਰਕ ਨੂੰ ਭੇਜਿਆ ਗਿਆ।",
            alertFailed: "ਅਲਰਟ ਨਹੀਂ ਭੇਜਿਆ ਜਾ ਸਕਿਆ। ਸੰਪਰਕ ਸੈਟਅਪ ਚੈੱਕ ਕਰੋ।",
            hospitalFound: "ਨੇੜਲੇ ਹਸਪਤਾਲ: Fortis Hospital, Manipal Hospital, St. Martha's Hospital.",
            firstAid: "ਪਹਿਲੀ ਸਹਾਇਤਾ: ਜ਼ਖਮੀ ਵਿਅਕਤੀ ਨੂੰ ਨਾ ਹਿਲਾਓ। ਸਾਹ ਚੈੱਕ ਕਰੋ। 108 ਤੇ ਕਾਲ ਕਰੋ। ਖੂਨ ਵਗੇ ਤਾਂ ਦਬਾਅ ਦਿਓ।"
        }
    };

    function setLanguage(lang) {
        currentLang = lang;

        const buttons = document.querySelectorAll(".language-box button");
        buttons.forEach(btn => btn.classList.remove("active"));

        document.getElementById("btn-" + lang).classList.add("active");

        const t = text[lang];

        document.getElementById("title").innerText = t.title;
        document.getElementById("subtitle").innerText = t.subtitle;
        document.getElementById("accidentTitle").innerText = t.accidentTitle;
        document.getElementById("accidentText").innerText = t.accidentText;
        document.getElementById("triggerBtn").innerText = t.triggerBtn;
        document.getElementById("hospitalTitle").innerText = t.hospitalTitle;
        document.getElementById("hospitalText").innerText = t.hospitalText;
        document.getElementById("hospitalBtn").innerText = t.hospitalBtn;
        document.getElementById("firstAidTitle").innerText = t.firstAidTitle;
        document.getElementById("firstAidText").innerText = t.firstAidText;
        document.getElementById("firstAidBtn").innerText = t.firstAidBtn;
        document.getElementById("footerText").innerText = t.footerText;

        document.getElementById("accidentResult").style.display = "none";
        document.getElementById("hospitalResult").style.display = "none";
        document.getElementById("firstAidResult").style.display = "none";
    }

    function showResult(id, message, isError = false) {
        const box = document.getElementById(id);
        box.style.display = "block";
        box.innerText = message;

        if (isError) {
            box.classList.add("error");
        } else {
            box.classList.remove("error");
        }
    }

    async function triggerAccident() {
        const t = text[currentLang];
        showResult("accidentResult", t.sending, false);

        const payload = {
            name: document.getElementById("name").value,
            latitude: document.getElementById("latitude").value,
            longitude: document.getElementById("longitude").value,
            hospital: document.getElementById("hospital").value,
            eta: "6 min",
            accelerometer_score: 90,
            sound_score: 85
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

            if (data.accident_confirmed === true) {
                showResult("accidentResult", t.alertSuccess, false);
            } else {
                showResult("accidentResult", t.alertFailed, true);
            }

        } catch (error) {
            showResult("accidentResult", t.alertFailed, true);
        }
    }

    async function findHospital() {
        const t = text[currentLang];

        try {
            const response = await fetch("/find-hospital", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    latitude: "12.8249",
                    longitude: "77.5159"
                })
            });

            if (response.ok) {
                showResult("hospitalResult", t.hospitalFound, false);
            } else {
                showResult("hospitalResult", t.alertFailed, true);
            }

        } catch (error) {
            showResult("hospitalResult", t.alertFailed, true);
        }
    }

    async function firstAidHelp() {
        const t = text[currentLang];

        const messages = {
            en: "first aid",
            hi: "प्राथमिक चिकित्सा",
            ta: "முதலுதவி",
            kn: "ಪ್ರಥಮ ಚಿಕಿತ್ಸೆ",
            te: "ప్రథమ చికిత్స",
            ml: "പ്രഥമ ശുശ്രൂഷ",
            mr: "प्राथमिक उपचार",
            bn: "প্রাথমিক চিকিৎসা",
            gu: "પ્રાથમિક સારવાર",
            pa: "ਪਹਿਲੀ ਸਹਾਇਤਾ"
        };

        try {
            await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: messages[currentLang]
                })
            });

            showResult("firstAidResult", t.firstAid, false);

        } catch (error) {
            showResult("firstAidResult", t.firstAid, false);
        }
    }
</script>

</body>
</html>
    """)


@app.route("/api/status")
def api_status():
    return jsonify({
        "message": "AAROHI AI backend running successfully",
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
# COMPATIBILITY ROUTES
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