import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string, request, redirect

load_dotenv()

app = Flask(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Multiple contacts example:
# EMERGENCY_CONTACTS=+919876543210,+919123456789
EMERGENCY_CONTACTS = os.getenv("EMERGENCY_CONTACTS", os.getenv("EMERGENCY_CONTACT", ""))


def get_contact_list():
    if not EMERGENCY_CONTACTS:
        return []

    return [num.strip() for num in EMERGENCY_CONTACTS.split(",") if num.strip()]


def build_alert_message(data):
    name = data.get("name", "User")
    latitude = data.get("latitude", "12.9716")
    longitude = data.get("longitude", "77.5946")
    hospital = data.get("hospital", "City Hospital")
    eta = data.get("eta", "8 min")

    maps_link = f"maps.google.com/?q={latitude},{longitude}"

    # SHORT SMS for Twilio Trial account
    # No emoji, no long text, no many new lines
    message = (
        f"RAKSHA ALERT: Accident detected for {name}. "
        f"Loc: {maps_link}. "
        f"Hosp: {hospital}. "
        f"ETA: {eta}. Call now."
    )

    return message


def send_twilio_sms(message):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        return {
            "success": False,
            "error": "Twilio credentials missing in environment variables."
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

            except Exception as e:
                failed_messages.append({
                    "to": contact,
                    "error": str(e)
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


@app.route("/api/alert/send", methods=["POST"])
def send_alert_api():
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
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
    else:
        data = {}

    name = data.get("name", "Demo User")
    latitude = data.get("latitude", "12.9716")
    longitude = data.get("longitude", "77.5946")
    hospital = data.get("hospital", "City Hospital")
    eta = data.get("eta", "8 min")

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
            "latitude": latitude,
            "longitude": longitude,
            "map_link": f"https://maps.google.com/?q={latitude},{longitude}"
        },
        "nearest_hospital": hospital,
        "eta": eta,
        "alert_message": alert_message,
        "message_length": len(alert_message),
        "alert_result": alert_result
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

        .flow {
            line-height: 1.8;
            color: #e5e7eb;
        }
    </style>
</head>

<body>
    <header>
        <h1>RAKSHA AI</h1>
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
            <p>Short SMS alert to verified emergency contacts.</p>
            <button onclick="sendTestAlert()">Send Test Alert</button>
        </div>

        <div class="card">
            <h2>System Flow</h2>
            <p class="flow">
                Sense → Score → Confirm → Locate → Match → Alert → Dashboard
            </p>
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

async function sendTestAlert() {
    const payload = {
        name: "Demo User",
        latitude: "12.9716",
        longitude: "77.5946",
        hospital: "City Hospital",
        eta: "8 min"
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
            alert("Emergency alert sent successfully. Message length: " + data.message_length);
        } else {
            alert("Alert failed: " + (data.result.error || JSON.stringify(data.result.failed)));
        }

    } catch (error) {
        log("Error sending test alert: " + error);
        alert("Error sending alert: " + error);
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
        hospital: "City Hospital",
        eta: "8 min",
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
            alert("Accident confirmed. Alert triggered. Message length: " + data.message_length);
        } else {
            alert("Accident not confirmed.");
        }

    } catch (error) {
        log("Error triggering accident: " + error);
        alert("Error triggering accident: " + error);
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