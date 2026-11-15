import os

from flask import Flask, jsonify, render_template

app = Flask(__name__, static_folder="templates/static")


@app.get("/")
def hospital_dashboard():
    return render_template('hospital.html')


@app.get("/api/v1/dashboard")
def dashboard_data():
    location = os.environ.get("HOSPITAL_LOCATION", "Bengaluru, India")
    return jsonify({
        "api_version": "1.0",
        "status": "demo",
        "location": {"name": location},
        "notice": (
            "Operational figures shown in the dashboard are illustrative demo data. "
            "Connect an authorized hospital system for live data."
        ),
    })


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() in {"1", "true", "yes"})