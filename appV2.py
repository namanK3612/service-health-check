import os
import json
import pytz
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential

# Load environment variables from .env file
load_dotenv()

# Credentials for SharePoint
site_url = os.getenv('site_url')
username = os.getenv('sharepoint_username')
password = os.getenv('password')

# Teams webhook URL
TEAMS_WEBHOOK_URL = os.getenv('teams_webhook_url')

# Define the IST timezone
IST = pytz.timezone("Asia/Kolkata")

# Dictionary to track last alert times for each service
last_alert_times = {}

# Function to send an alert to Microsoft Teams
project_name = os.getenv('project_name')

def send_teams_alert(service_name, status, last_updated):
    """Sends an alert to the specified Teams channel using the webhook."""
    if status.lower() == "stopped":
        message = f"🚨 || {project_name} || **{service_name}** is **STOPPED** as of {last_updated}.🚨"
    elif status.lower() == "running":
        message = f"✅ || {project_name} || **{service_name}** is **RUNNING** as of {last_updated}.✅"

    payload = {
        "text": message
    }

    response = requests.post(TEAMS_WEBHOOK_URL, json=payload)
    if response.status_code == 200:
        print(f"Alert sent to Teams: {message}")
    else:
        print(f"Failed to send alert: {response.text}")

# Function to fetch data from SharePoint
def fetch_sharepoint_data():
    """Fetches service health data from SharePoint JSON files."""
    # Connect to SharePoint
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))

    # Specify the folder path where JSON files are stored
    folder_url = os.getenv('folder_url')
    files = ctx.web.get_folder_by_server_relative_url(folder_url).files
    ctx.load(files)
    ctx.execute_query()

    # Initialize a list to collect data
    all_data = []
    last_updated_times = {}

    # Loop through each JSON file and gather service data
    for file in files:
        if file.name.endswith('.json'):
            file_content = file.read()  # Get file content as bytes
            try:
                json_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                json_content = file_content.decode('utf-16')

            # Load the JSON content into a dictionary
            file_data = json.loads(json_content)

            # Add file name to each entry for reference
            for entry in file_data:
                entry['FileName'] = file.name

            all_data.extend(file_data)  # Collect data from all JSON files

            # Record the last modified time of the file and convert to IST
            last_updated_times[file.name] = file.time_last_modified.replace(tzinfo=pytz.utc).astimezone(IST).strftime("%Y-%m-%d %I:%M %p %Z")

    return all_data, last_updated_times

# Create Dash application with a dark theme
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# Define layout for the dashboard
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1(f"Service Health Dashboard - {project_name}", className="text-center text-light my-4"), width=12)
    ]),
    dcc.Interval(id="interval-component", interval=(600*1000)/10, n_intervals=0),  # Refresh every 1 minutes
    dbc.Row([dbc.Col(html.Div(id='service-health-container'), width=12)])
], fluid=True, style={"backgroundColor": "#2c2f33"})

# Updated Dash layout with a modern, minimalistic design
app.layout = dbc.Container([
    # Header with title
    dbc.Row([
        dbc.Col(html.H1(
            f"Service Health Dashboard - {project_name}",
            className="text-center text-light my-4",
            style={"fontSize": "2.5rem", "fontWeight": "bold", "color": "#17a2b8"}
        ), width=12)
    ]),

    # Auto-refresh interval
    dcc.Interval(id="interval-component", interval=(600 * 1000) / 10, n_intervals=0),

    # Service status cards container
    dbc.Row([
        dbc.Col(html.Div(id='service-health-container'), width=12)
    ], style={"justifyContent": "center"})
], fluid=True, style={"backgroundColor": "#1e1e2f", "padding": "2rem"})


@app.callback(
    Output('service-health-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_dashboard(n):
    global last_alert_times

    # Fetch service health data
    all_data, last_updated_times = fetch_sharepoint_data()

    if not all_data:
        return dbc.Alert("No JSON files found or no data available in the specified folder.", color="warning")

    df = pd.DataFrame(all_data)

    # Create cards for each service
    service_status_divs = [
        dbc.Card(
            dbc.CardBody([
                html.H5(
                    service,
                    className="card-title text-light",
                    style={
                        "whiteSpace": "nowrap",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "fontWeight": "600"
                    }
                ),
                html.Div(
                    [
                        dbc.Badge(
                            ["🟢 Running", "🔴 Stopped"][status.lower() == "stopped"],
                            color=["success", "danger"][status.lower() == "stopped"],
                            className="p-2 mx-1",
                            style={"fontSize": "1rem", "borderRadius": "5px"}
                        ),
                        html.I(
                            f"Last Updated: {last_updated_times[file_name]}",
                            className="text-light mt-2",
                            style={"fontSize": "0.85rem", "display": "block"}
                        )
                    ]
                )
            ]),
            className="shadow-sm mb-4 bg-dark",
            style={
                "width": "20rem",
                "borderRadius": "10px",
                "boxShadow": "0 4px 8px rgba(0, 0, 0, 0.1)"
            }
        ) for service, status, file_name in zip(df['Name'], df['Status'], df['FileName'])
    ]

    # Arrange the cards into rows
    rows = []
    for i in range(0, len(service_status_divs), 3):  # 3 cards per row
        rows.append(dbc.Row(service_status_divs[i:i + 3], justify="center", className="mb-4"))

    current_time = datetime.now()

    # Alert logic
    for index, row in df.iterrows():
        service_name = row['Name']
        status = row['Status']
        file_name = row['FileName']
        last_updated = last_updated_times[file_name]

        if status.lower() == "stopped":
            if service_name not in last_alert_times or (current_time - last_alert_times[service_name]).total_seconds() > 300:
                send_teams_alert(service_name, "stopped", last_updated)
                last_alert_times[service_name] = current_time
        else:
            if service_name in last_alert_times:
                send_teams_alert(service_name, "running", last_updated)
                del last_alert_times[service_name]

    return rows

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
