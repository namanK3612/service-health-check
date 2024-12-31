import os
import json
import pytz
import pandas as pd
import requests
import webbrowser
from datetime import datetime
from dotenv import load_dotenv
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential
import socket

# Load environment variables from .env file
load_dotenv()

# Define the IST timezone
IST = pytz.timezone("Asia/Kolkata")

# Dictionary to track last alert times for each service
last_alert_times = {}

# Project configurations for SharePoints
PROJECTS = [
    {
        "project_name": os.getenv("project_1_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_1_folder_url"),
    },
    {
        "project_name": os.getenv("project_2_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_2_folder_url"),
    },
    {
        "project_name": os.getenv("project_3_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_3_folder_url"),
    },
]

username = os.getenv("sharepoint_username")
password = os.getenv("password")
TEAMS_WEBHOOK_URL = os.getenv("teams_webhook_url")


def find_open_port(start_port=8050, end_port=9000):
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No available ports found in the specified range.")


def send_teams_alert(alerts):
    """Sends cumulative alerts to Microsoft Teams."""
    message = "🚨 **Service Alert Summary** 🚨\n\n"

    if alerts.get("stopped"):
        stopped_services = "\n".join(
            f"- {entry['Name']} (Startup Type: {entry['StartupType']})" for entry in alerts["stopped"]
        )
        message += f"🛑 **Stopped Services:**\n{stopped_services}\n\n"

    if alerts.get("running"):
        running_services = "\n".join(
            f"- {entry['Name']} (Startup Type: {entry['StartupType']})" for entry in alerts["running"]
        )
        message += f"✅ **Recovered Services:**\n{running_services}\n\n"

    message += "🔍 Please investigate immediately!"

    payload = {"text": message}
    response = requests.post(TEAMS_WEBHOOK_URL, json=payload)
    if response.status_code == 200:
        print("Cumulative alert sent to Teams.")
    else:
        print(f"Failed to send alert: {response.text}")


def fetch_sharepoint_data(site_url, folder_url):
    """Fetches service health data from a single SharePoint."""
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))
    files = ctx.web.get_folder_by_server_relative_url(folder_url).files
    ctx.load(files)
    ctx.execute_query()

    all_data = []
    last_updated_times = {}

    for file in files:
        if file.name.endswith(".json"):
            file_content = file.read()
            try:
                json_content = file_content.decode("utf-8")
            except UnicodeDecodeError:
                json_content = file_content.decode("utf-16")

            file_data = json.loads(json_content)
            for entry in file_data:
                entry["FileName"] = file.name

            all_data.extend(file_data)
            last_updated_times[file.name] = file.time_last_modified.replace(
                tzinfo=pytz.utc
            ).astimezone(IST).strftime("%Y-%m-%d %I:%M %p %Z")

    return all_data, last_updated_times


# Create Dash application
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(
                html.H1(
                    "Service Health Dashboard",
                    className="text-center text-light my-4",
                ),
                width=12,
            )
        ),
        dcc.Interval(id="interval-component", interval=60000, n_intervals=0),
        dbc.Row(dbc.Col(html.Div(id="service-health-container"), width=12)),
    ],
    fluid=True,
    style={
        "backgroundColor": "#1e1e2f",
        "height": "100vh",  # Full viewport height
        "overflow": "auto",  # Allow scrolling for large dashboards
    },
)


@app.callback(
    Output("service-health-container", "children"),
    Input("interval-component", "n_intervals"),
)
def update_dashboard(n):
    global last_alert_times

    project_sections = []
    alerts = {"stopped": [], "running": []}

    for project in PROJECTS:
        project_data, last_updated_times = fetch_sharepoint_data(
            project["site_url"], project["folder_url"]
        )
        last_update_time = list(last_updated_times.values())[0]  # Assuming one update time per project

        # Track alerts
        for service in project_data:
            service_name = service["Name"]
            status = service["Status"]
            startup_type = service["StartupType"]

            if status.lower() == "stopped":
                if service_name not in last_alert_times or (
                    datetime.now() - last_alert_times[service_name]
                ).total_seconds() > 300:
                    alerts["stopped"].append(service)
                    last_alert_times[service_name] = datetime.now()
            elif status.lower() == "running" and service_name in last_alert_times:
                alerts["running"].append(service)
                del last_alert_times[service_name]

        # Generate service cards for the project
        service_cards = [
            dbc.Card(
                dbc.CardBody(
                    [
                        html.H5(service["Name"], className="card-title text-light"),
                        dbc.Badge(
                            service["Status"],
                            color=("success" if service["Status"].lower() == "running" else "danger"),
                            className="p-2",
                        ),
                        html.P(
                            f"Startup Type: {service['StartupType']}",
                            className="text-light",
                        ),
                        html.P(
                            f"Last Updated: {last_updated_times.get(service['FileName'], 'N/A')}",
                            className="text-light",
                        ),
                    ]
                ),
                className="bg-dark shadow-sm mb-4",
            )
            for service in project_data
        ]

        project_section = dbc.AccordionItem(
            [
                html.P(f"Last Updated: {last_update_time}", className="text-light"),
                dbc.Row(
                    [dbc.Col(card, width=4) for card in service_cards],
                    justify="start",
                ),
            ],
            title=project["project_name"],
        )
        project_sections.append(project_section)

    # Send cumulative Teams alerts if there are updates
    if alerts["stopped"] or alerts["running"]:
        send_teams_alert(alerts)

    # Wrap all project sections in an accordion
    return dbc.Accordion(project_sections, always_open=True)


if __name__ == "__main__":
    port = find_open_port()
    url = f"http://127.0.0.1:{port}"
    print(f"Starting app on {url}")
    webbrowser.open(url)
    app.run(debug=False, port=port)
