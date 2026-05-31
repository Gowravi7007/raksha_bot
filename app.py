import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request, redirect

# Load .env locally
load_dotenv()

app = Flask(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Add one or multiple emergency contacts separated by comma
# Example: EMERGENCY_CONTACTS=+919876543210,+919123456789
EMERGENCY_CONTACTS = os.getenv("EMERGENCY_CONTACTS", os.getenv("EMERGENCY_CONTACT", ""))

# Optional hospital / emergency numbers
HOSPITAL_CONTACT = os.getenv("HOSPITAL_CONTACT", "")
EMERGENCY_SERVICE_CONTACT = os.getenv("EMERGENCY_SERVICE_CONTACT", "")


def get_contact_list():
    contacts = []

    if EMERGENCY_CONTACTS:
        contacts.extend([num.strip() for num in EMERGENCY_CONTACTS.split(",") if num.strip()])

    if HOSPITAL_CONTACT:
        contacts.append(HOSPITAL_CONTACT.strip())

    if EMERGENCY_SERVICE_CONTACT:
        contacts.append(EMERGENCY_SERVICE_CONTACT.strip())

    return contacts


def send_twilio_sms(message):
    """
    Sends SMS alerts using Twilio.
    Works only if Twilio credentials and phone numbers are configured correctly.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "error": "Twilio credentials are missing. Add them in .env or Render Environment Variables."
        }

    contacts = get_contact_list()

    if not contacts:
        return {
            "success": False,
            "error": "No emergency contacts found. Add EMERGENCY_CONTACTS in .env or Render."
        }

    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        sent_messages = []

        for contact in contacts:
            sms = client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=contact
            )

            sent_messages.append({
                "to": contact,
                "sid": sms.sid,
                "status": sms.status
            })

        return {
            "success": True,
            "sent_count": len(sent_messages),
            "messages": sent_messages
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def build_alert_message(data):
    name = data.get("name", "RAKSHA AI User")
    latitude = data.get("latitude", "12.9716")
    longitude = data.get("longitude", "77.5946")
    hospital = data.get("hospital", "Nearest available hospital")
    eta = data.get("eta", "Not available")
    score = data.get("score", "Above 70%")

    maps_link = f"https://maps.google.com/?q={latitude},{longitude}"

    message = f"""
🚨 RAKSHA AI EMERGENCY ALERT 🚨

Accident detected for: {name}

Accident Score: {score}
Location: {maps_link}

Nearest Hospital: {hospital}
ETA: {eta}

Please respond immediately.
""".strip()

    return message


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


@app.route("/api/status")
def api_status():
    return jsonify({
        "message": "RAKSHA AI backend running successfully",
        "dashboard": "/dashboard",
        "env_loaded": {
            "GEMINI_API_KEY": bool(GEMINI_API_KEY),
            "TWILIO_ACCOUNT_SID": bool(TWILIO_ACCOUNT_SID),
            "TWILIO_AUTH_TOKEN": bool(TWILIO_AUTH_TOKEN),
            "TWILIO_PHONE_NUMBER": bool(TWILIO_PHONE_NUMBER),
            "EMERGENCY_CONTACTS": bool(get_contact_list())
        }
    })


@app.route("/api/accident/trigger", methods=["GET", "POST"])
def trigger_accident():
    """
    Demo accident trigger route.
    This simulates:
    STEP 1: Sense
    STEP 2: Score
    STEP 3: Confirm
    STEP 4: Locate
    STEP 5: Match
    STEP 6: Alert
    STEP 7: Dashboard update
    """

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = {}

    accident_data = {
        "name": data.get("name", "Demo User"),
        "latitude": data.get("latitude", "12.9716"),
        "longitude": data.get("longitude", "77.5946"),
        "hospital": data.get("hospital", "City Emergency Hospital"),
        "eta": data.get("eta", "8 minutes"),
        "accelerometer_score": data.get("accelerometer_score", 85),
        "sound_score": data.get("sound_score", 78)
    }

    combined_score = (
        accident_data["accelerometer_score"] * 0.55
        + accident_data["sound_score"] * 0.45
    )

    accident_confirmed = combined_score > 70

    if accident_confirmed:
        alert_message = build_alert_message({
            "name": accident_data["name"],
            "latitude": accident_data["latitude"],
            "longitude": accident_data["longitude"],
            "hospital": accident_data["hospital"],
            "eta": accident_data["eta"],
            "score": round(combined_score, 2)
        })

        alert_result = send_twilio_sms(alert_message)
    else:
        alert_message = "Accident not confirmed. Alert not sent."
        alert_result = {
            "success": False,
            "error": "Combined score below threshold."
        }

    return jsonify({
        "accident_confirmed": accident_confirmed,
        "combined_score": round(combined_score, 2),
        "threshold": 70,
        "sustained_time": "3 seconds",
        "location": {
            "latitude": accident_data["latitude"],
            "longitude": accident_data["longitude"],
            "map_link": f"https://maps.google.com/?q={accident_data['latitude']},{accident_data['longitude']}"
        },
        "nearest_hospital": accident_data["hospital"],
        "eta": accident_data["eta"],
        "alert_message": alert_message,
        "alert_result": alert_result
    })


@app.route("/api/alert/send", methods=["POST"])
def send_alert_api():
    data = request.get_json(silent=True) or {}

    alert_message = build_alert_message(data)
    result = send_twilio_sms(alert_message)

    return jsonify({
        "alert_message": alert_message,
        "result": result
    })


@app.route("/dashboard")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>RAKSHA AI Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: white;
        }

        header {
            padding: 20px;
            text-align: center;
            background: #991b1b;
        }

        header h1 {
            margin: 0;
            font-size: 34px;
        }

        header p {
            margin: 6px 0 0;
            font-size: 16px;
        }

        .container {
            padding: 25px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
        }

        .card {
            background: #1e293b;
            padding: 20px;
            border-radius: 14px;
            box-shadow: 0 0 15px rgba(0,0,0,0.4);
        }

        .card h2 {
            margin-top: 0;
            color: #fca5a5;
        }

        .status {
            font-size: 28px;
            font-weight: bold;
            color: #22c55e;
        }

        .danger {
            color: #ef4444;
        }

        button {
            background: #dc2626;
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            margin-top: 10px;
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
            max-height: 350px;
        }

        .full {
            grid-column: 1 / -1;
        }

        a {
            color: #38bdf8;
        }
    </style>
</head>

<body>
    <header>
        <h1>🚨 RAKSHA AI</h1>
        <p>Automated Accident Detection and Emergency Alert Dashboard</p>
    </header>

    <div class="container">
        <div class="card">
            <h2>Backend Status</h2>
            <p id="backendStatus" class="status">Checking...</p>
            <button onclick="checkStatus()">Check Backend</button>
        </div>

        <div class="card">
            <h2>Accident Detection</h2>
            <p>Accelerometer + Crash Sound AI</p>
            <button onclick="triggerAccident()">Simulate Accident Trigger</button>
        </div>

        <div class="card">
            <h2>Emergency Alert</h2>
            <p>Alert goes to saved emergency contacts using Twilio SMS.</p>
            <button onclick="sendTestAlert()">Send Test Alert</button>
        </div>

        <div class="card">
            <h2>System Flow</h2>
            <p>Sense → Score → Confirm → Locate → Match → Alert → Dashboard</p>
        </div>

        <div class="card full">
            <h2>Live Terminal Logs</h2>
            <pre id="logs">Dashboard loaded...</pre>
        </div>
    </div>

<script>
function log(message) {
    const logs = document.getElementById("logs");
    logs.textContent += "\\n" + message;
}

async function checkStatus() {
    try {
        const response = await fetch("/api/status");
        const data = await response.json();

        document.getElementById("backendStatus").textContent = "Running";
        document.getElementById("backendStatus").classList.remove("danger");

        log("Backend Status:");
        log(JSON.stringify(data, null, 2));
    } catch (error) {
        document.getElementById("backendStatus").textContent = "Error";
        document.getElementById("backendStatus").classList.add("danger");
        log("Error checking backend: " + error);
    }
}

async function triggerAccident() {
    log("STEP 1: Sensing phone accelerometer and microphone...");
    log("STEP 2: Calculating accident score...");
    log("STEP 3: Confirming accident for 3 seconds...");

    const payload = {
        name: "Demo User",
        latitude: "12.9716",
        longitude: "77.5946",
        hospital: "City Emergency Hospital",
        eta: "8 minutes",
        accelerometer_score: 85,
        sound_score: 78
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

        log("Accident Trigger Result:");
        log(JSON.stringify(data, null, 2));

        if (data.accident_confirmed) {
            alert("🚨 Accident Confirmed! Alert process triggered.");
        } else {
            alert("Accident not confirmed.");
        }

    } catch (error) {
        log("Error triggering accident: " + error);
    }
}

async function sendTestAlert() {
    const payload = {
        name: "RAKSHA AI Demo User",
        latitude: "12.9716",
        longitude: "77.5946",
        hospital: "City Emergency Hospital",
        eta: "8 minutes",
        score: "Demo Alert"
    };

    try {
        const response = await fetch("/api/alert/send", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        log("Test Alert Result:");
        log(JSON.stringify(data, null, 2));

        if (data.result.success) {
            alert("Emergency alert sent successfully.");
        } else {
            alert("Alert failed. Check Twilio credentials and contacts.");
        }

    } catch (error) {
        log("Error sending test alert: " + error);
    }
}

checkStatus();
</script>

</body>
</html>
""")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)