import os
import json
import pytz
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from dash import Dash, html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.user_credential import UserCredential

load_dotenv()

# Credentials and URL for SharePoint
site_url = os.getenv('site_url')
username = os.getenv('sharepoint_username')
password = os.getenv('password')

# Create Dash application with a dark theme
app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# Define layout for the dashboard
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Service Health Dashboard - AIIB Prod", className="text-center text-light my-4"), width=12)
    ]),
    dcc.Interval(id="interval-component", interval=(600*1000)/10, n_intervals=0),  # Refresh every 5 minutes
    dbc.Row([
        dbc.Col(html.Div(id='service-health-container'), width=12)
    ])
], fluid=True, style={"backgroundColor": "#2c2f33"})

# Define the IST timezone
IST = pytz.timezone("Asia/Kolkata")

# Define callback to refresh data and update the dashboard
@app.callback(
    Output('service-health-container', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_dashboard(n):
    # Connect to SharePoint
    ctx = ClientContext(site_url).with_credentials(UserCredential(username, password))

    # Specify the folder path where JSON files are stored
    folder_url = "/sites/CSDataVault/Shared Documents/DB Data dump by AppSupport/Purbanchal- AIIB+Assam/ServiceHealth-Prod"

    # Get files from the specified folder
    files = ctx.web.get_folder_by_server_relative_url(folder_url).files
    ctx.load(files)
    ctx.execute_query()

    # Initialize a list to collect data and timestamps
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

            # Append file data with the file name
            for entry in file_data:
                entry['FileName'] = file.name  # Add FileName column for reference

            all_data.extend(file_data)  # Collect data from all JSON files

            # Record the last modified time of the file and convert to IST
            utc_time = file.time_last_modified  # This is already a datetime object
            last_updated_times[file.name] = utc_time.replace(tzinfo=pytz.utc).astimezone(IST).strftime("%Y-%m-%d %I:%M %p %Z")


    # If no data was gathered, return an alert
    if not all_data:
        return dbc.Alert("No JSON files found or no data available in the specified folder.", color="warning")

    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(all_data)

    # Generate dashboard content with service statuses and last updated times
    service_status_divs = [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H5(
                        service,
                        className="card-title text-light",
                        style={
                            "whiteSpace": "nowrap",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis"
                        }
                    ),
                    dbc.Badge(
                        "Running" if status.lower() == 'running' else "Stopped",
                        color="success" if status.lower() == 'running' else "danger",
                        className="p-2",
                    ),
                    html.P(
                        f"Last Updated: {last_updated_times[file_name]}",
                        className="text-light mt-2",
                        style={"fontSize": "0.85rem"}
                    )
                ]),
                className="shadow-sm mb-4 bg-dark",
                style={'width': '18rem'}
            ),
            width=4,
            className="mb-4"
        ) for service, status, file_name in zip(df['Name'], df['Status'], df['FileName'])
    ]

    # Arrange service statuses into rows
    rows = []
    for i in range(0, len(service_status_divs), 3):  # 3 cards per row
        rows.append(dbc.Row(service_status_divs[i:i+3], justify="center"))

    return rows

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
