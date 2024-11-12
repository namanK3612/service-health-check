import os
import json
import pandas as pd
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

    # Initialize a list to collect data from each JSON file
    all_data = []

    # Loop through each JSON file and gather service data
    for file in files:
        if file.name.endswith('.json'):
            file_content = file.read()  # Get file content as bytes
            try:
                json_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                json_content = file_content.decode('utf-16')
            
            # Load the JSON content into a dictionary and append to all_data
            file_data = json.loads(json_content)
            all_data.extend(file_data)  # Collect data from all JSON files

    # If no data was gathered, return an alert
    if not all_data:
        return dbc.Alert("No JSON files found or no data available in the specified folder.", color="warning")

    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(all_data)
    
    # Generate dashboard content with service statuses
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
                ]),
                className="shadow-sm mb-4 bg-dark",
                style={'width': '18rem'}
            ),
            width=4,
            className="mb-4"
        ) for service, status in zip(df['Name'], df['Status'])
    ]

    # Arrange service statuses into rows
    rows = []
    for i in range(0, len(service_status_divs), 3):  # 3 cards per row
        rows.append(dbc.Row(service_status_divs[i:i+3], justify="center"))

    return rows

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
