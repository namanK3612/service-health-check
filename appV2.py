import os
import json
import pytz
import logging
# import pandas as pd
import requests
# import webbrowser
from datetime import datetime
from dotenv import load_dotenv
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential
# import socket

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "dashboard.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger()

# Log to both console and file
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Load environment variables from .env file
load_dotenv()

# Define the IST timezone
IST = pytz.timezone("Asia/Kolkata")

# Dictionary to track last alert times for each service
last_alert_times = {}

# Projects Mapping to Channels
projects_map = {
    "Anvil": ["jk_anvil_prod","jk_techno_prod","arunachal_prod","sikkim_prod","ups_prod","ami_prod_new"],
    "Apraava": ["apraava_prod","hp_prod","hp_prod_ha","wb_apraava_prod"],
    "GVPR": ["gvpr_prod"],
    "Intelli": ["intelli_prod","intelli_dgvcl_prod","intelli_mgvcl_prod","intelli_pvvnl_prod","pkg7_prod"],
    "MCL": ["mcl_prod"],
    "NCC": ["ncc_awb_prod", "ncc_nashik_prod"],
    "Purbanchal": ["aiib_prod"],
}
# Helper function to get the alert channel webhook for a project
def get_alert_webhook(project_name):
    for key, values in projects_map.items():
        if project_name in values:
            return os.getenv(f"{key}")  
    return None

# Project configurations for SharePoints
PROJECTS = [
    {
        "project_name": os.getenv("project_1_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_1_folder_url"),
        "alert_channel_webhook": get_alert_webhook(os.getenv("project_1_name")),
    },
    {
        "project_name": os.getenv("project_2_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_2_folder_url"),
        "alert_channel_webhook": get_alert_webhook(os.getenv("project_2_name")),
    },
    {
        "project_name": os.getenv("project_3_name"),
        "site_url": os.getenv("base_site_url"),
        "folder_url": os.getenv("project_3_folder_url"),
        "alert_channel_webhook": get_alert_webhook(os.getenv("project_3_name")),
    },
]

# Track alert counts for services
alert_counts = {}

# Function to send Teams alert for individual service status
def send_teams_service_alert(service, message, webhook_url):
    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        logger.info(f"Alert sent for {service['Name']} to Teams.")
    else:
        logger.error(f"Failed to send alert for {service['Name']}: {response.text}")

# Function to handle alerts for automatic startup services
def handle_automatic_alert(service, service_name, alert_counts, webhook_url, last_updated_time):
    if service_name not in alert_counts:
        alert_counts[service_name] = 0

    alert_counts[service_name] += 1

    if alert_counts[service_name] == 3:  # Send alert on the 3rd consecutive stop
        message = (
            f"🚨 **Critical Alert:** Service '{service_name}' of Automatic Startup Type has been stopped for 3 consecutive intervals.\n"
            f"Last Updated: {last_updated_time}\n\n"
            f"🔍 Please investigate immediately!"
        )
        send_teams_service_alert(service, message, webhook_url)

# Function to handle alerts for manual startup services
def handle_manual_alert(service, service_name, webhook_url, last_updated_time):
    message = (
        f"🚨 **Notice:** Service '{service_name}' of Manual Startup Type is detected as stopped.\n"
        f"Last Updated: {last_updated_time}\n\n"
        f"🔍 Please investigate as needed."
    )
    send_teams_service_alert(service, message, webhook_url)

# Function to reset alert counts when a service is running
def reset_alert_counts(service_name):
    if service_name in alert_counts:
        del alert_counts[service_name]

# Function to send recovery notification
def send_recovery_notification(service_name, webhook_url, last_updated_time):
    message = (
        f"✅ **Recovery Notice:** Service '{service_name}' has resumed running.\n"
        f"Timestamp: {last_updated_time}\n\n"
        f"🔄 No further action required."
    )
    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        logger.info(f"Recovery notification sent for {service_name} to Teams.")
    else:
        logger.error(f"Failed to send recovery notification for {service_name}: {response.text}")


username = os.getenv("sharepoint_username")
password = os.getenv("password")

def fetch_sharepoint_data(site_url, folder_url):
    """Fetches service health data from a single SharePoint."""
    try:
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
    except Exception as e:
        logger.error(f"Error fetching data from SharePoint: {e}")
        return [], {}

# Create Dash application
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
server = app.server

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
        dcc.Interval(id="interval-component", interval=int(os.getenv("dashboard_refresh_interval", 1)) *10000, n_intervals=0),
        dbc.Row(dbc.Col(html.Div(id="service-health-container"), width=12)),
    ],
    fluid=True,
    style={
        "backgroundColor": "#1e1e2f",
        "height": "100vh",  # Full viewport height
        "overflow": "auto",  # Allow scrolling for large dashboards
    },
)


# Updated update_dashboard callback
@app.callback(
    Output("service-health-container", "children"),
    Input("interval-component", "n_intervals"),
)
def update_dashboard(n):
    global last_alert_times

    project_sections = []

    for project in PROJECTS:
        project_data, last_updated_times = fetch_sharepoint_data(
            project["site_url"], project["folder_url"]
        )

        min_last_update_time = min(
            datetime.strptime(ts[:-4], "%Y-%m-%d %I:%M %p").replace(tzinfo=IST)
            for ts in last_updated_times.values()
        )
        formatted_min_update_time = min_last_update_time.strftime("%Y-%m-%d %I:%M %p %Z")

        all_services_running = all(
            service["Status"].lower() == "running" for service in project_data
        )

        for service in project_data:
            service_name = service["Name"]
            status = service["Status"].lower()
            startup_type = service["StartupType"].lower()
            last_updated_time = last_updated_times.get(service["FileName"], "N/A")

            if status == "stopped":
                if startup_type == "automatic":
                    handle_automatic_alert(service, service_name, alert_counts, project["alert_channel_webhook"], last_updated_time)
                elif startup_type == "manual":
                    handle_manual_alert(service, service_name, project["alert_channel_webhook"], last_updated_time)

                last_alert_times[service_name] = datetime.now()
            elif status == "running":
                if service_name in alert_counts or service_name in last_alert_times:
                    send_recovery_notification(service_name, project["alert_channel_webhook"], last_updated_time)
                reset_alert_counts(service_name)


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
                dbc.Row(
                    [dbc.Col(card, width=4) for card in service_cards],
                    justify="start",
                ),
            ],
            title=f"{project['project_name']} (Last Updated: {formatted_min_update_time})",
            id=f"accordion-{project['project_name']}",
            style={
                "backgroundColor": ("#198754" if all_services_running else "#dc3545"),
                "color": "white",
                "padding": "10px",
                "borderRadius": "5px",
                "fontWeight": "bold",
            },
        )
        project_sections.append(project_section)

    return dbc.Accordion(project_sections, always_open=True)

if __name__ == "__main__":
    try:
        app.run()
    except Exception as e:
        logger.error(f"Failed to start the app: {e}")
