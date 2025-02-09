import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import plotly.express as px
import time
import random
from PIL import Image
from fpdf import FPDF
from twilio.rest import Client
import googlemaps

import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv
import json
import streamlit as st
from firebase_admin import credentials, initialize_app
load_dotenv()
# Load Firebase Admin Key from Streamlit Secrets
import toml
import streamlit as st
import firebase_admin
from firebase_admin import credentials, db




# Manually load secrets from the renamed folder
with open("streamlit_config/secrets.toml", "r") as f:
    secrets = toml.load(f)

# Now, use secrets like this:
firebase_admin_key = json.loads(secrets["FIREBASE_ADMIN_KEY"])

st.write("Firebase Config Loaded Successfully")
# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_admin_key)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://iot-bin-ba8a5-default-rtdb.firebaseio.com/'  # Replace with your Firebase DB URL
    })

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
GMAPS_API_KEY = os.getenv("GMAPS_API_KEY")

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Google Maps API Key
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Load UI assets
logo = Image.open("dustbin_logo.jpg")
header_img = Image.open("header.jpg")

# Streamlit UI Config
st.title("Welcome to the AI-model of Dustbin")

st.image(header_img, use_container_width=True)
st.sidebar.image(logo, width=200)
st.sidebar.title("MCD Admin Panel")

user_role = st.sidebar.radio("Select Role", ["Admin", "Field Worker"])


# Generate real-time bin data
def fetch_bin_data():
    ref = db.reference("/Data/bins")
    bins_data = ref.get()
    bins = []

    for key, value in bins_data.items():
        bins.append(value)

    return pd.DataFrame(bins)

bin_data = fetch_bin_data()


# Compute priority for bin collection
def calculate_priority(df):
    df["Priority"] = (
            (df["Fill Level (%)"] / 100) * 2 +
            (df["Tilt"] * 3) +
            (df["Temperature (°C)"] / 50) +
            (df["Humidity (%)"] / 100)
    )
    df.sort_values(by="Priority", ascending=False, inplace=True)
    return df
bin_data = calculate_priority(bin_data)

# Fetch and process live bin data



# Generate real-time van locations
def fetch_van_data():
    ref = db.reference("/Data/vans")
    vans_data = ref.get()
    vans = []

    for key, value in vans_data.items():
        vans.append(value)

    return pd.DataFrame(vans)

vans = fetch_van_data()


# Assign bins dynamically to closest available vans
# Assign bins dynamically to closest available vans & send Twilio alerts
def assign_bins_to_vans(bin_data, vans):
    assignments = []

    for _, bin in bin_data.iterrows():
        min_distance = float('inf')
        assigned_van = None
        assigned_driver_number = None  # Store driver number for Twilio

        for _, van in vans.iterrows():
            distance = np.sqrt((bin["Latitude"] - van["Latitude"]) ** 2 + (bin["Longitude"] - van["Longitude"]) ** 2)
            if distance < min_distance:
                min_distance = distance
                assigned_van = van["Van ID"]
                assigned_driver_number = "+919810126223" # Replace with actual driver's number

        assignments.append(assigned_van)

        # 🚨 *Send SMS Notification via Twilio*


    bin_data["Assigned Van"] = assignments
    return bin_data


bin_data = assign_bins_to_vans(bin_data, vans)

# Display bin data in a table
st.subheader("\U0001F4CD Live Bin Status")
st.dataframe(
    bin_data.style.format({"Fill Level (%)": "{:.2f}", "Temperature (°C)": "{:.2f}", "Humidity (%)": "{:.2f}"}))

# Display bin locations on a map
st.subheader("\U0001F5FA Bin Locations & Routes")
map = folium.Map(location=[28.7, 77.2], zoom_start=12)
# Add dustbin markers
for _, bin in bin_data.iterrows():
    folium.Marker(
        location=[bin["Latitude"], bin["Longitude"]],
        popup=f"Bin ID: {bin['Bin ID']}<br>Fill Level: {bin['Fill Level (%)']}%",
        icon=folium.Icon(icon="trash", prefix="fa", color="black")
    ).add_to(map)



# Assign optimized routes using Google Maps API
# Assign optimized routes using Google Maps API with unique colors
def get_routes(bin_data, vans, map_obj):
    colors = ["blue", "red", "green", "purple", "orange", "darkblue", "darkred", "darkgreen"]  # Expand if needed

    for i, van in vans.iterrows():
        assigned_bins = bin_data[bin_data["Assigned Van"] == van["Van ID"]]
        coordinates = [(row["Latitude"], row["Longitude"]) for _, row in assigned_bins.iterrows()]

        if coordinates:
            coordinates.insert(0, (van["Latitude"], van["Longitude"]))
            try:
                directions = gmaps.directions(
                    origin=coordinates[0],
                    destination=coordinates[-1],
                    waypoints=coordinates[1:-1],
                    mode="driving"
                )

                route_coords = [(step['start_location']['lat'], step['start_location']['lng']) for leg in
                                directions[0]['legs'] for step in leg['steps']]

                # Assign a unique color to each van
                path_color = colors[i % len(colors)]
                folium.PolyLine(route_coords, color=path_color, weight=5, opacity=0.8).add_to(map_obj)

                # Van Marker
                folium.Marker(
                    [van["Latitude"], van["Longitude"]],
                    popup=f"Van: {van['Van ID']}",
                    icon=folium.Icon(color=path_color, icon="truck", prefix="fa")
                ).add_to(map_obj)

            except Exception as e:
                st.error(f"Error generating route for {van['Van ID']}: {e}")
    return map_obj


map = get_routes(bin_data, vans, map)
folium_static(map)


# Function to send real-time updates via Twilio
def send_update_message(worker_phone, message):
    client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=worker_phone
    )


# Admin Panel for Managing Field Workers
if user_role == "Admin":
    st.sidebar.subheader("\U0001F477 Field Workers Management")
    workers = pd.DataFrame({
        "Worker ID": [101, 102, 103, 104],
        "Name": ["Rajesh", "Amit", "Pooja", "Suresh"],
        "Assigned Zone": ["North", "South", "East", "West"],
        "Phone": ["+918368164831", "+918368164831", "+917654321098", "+916543210987"]
    })
    st.sidebar.dataframe(workers)

    selected_worker = st.sidebar.selectbox("Assign Bin", bin_data["Bin ID"])
    selected_worker_id = st.sidebar.selectbox("Select Worker", workers["Worker ID"])
    worker_phone = workers.loc[workers["Worker ID"] == selected_worker_id, "Phone"].values[0]

    if st.sidebar.button("Assign Task"):
        st.sidebar.success(f"{selected_worker} assigned to Worker {selected_worker_id} with real-time update!")

# Analytics Report Page
if user_role == "Admin":
    st.sidebar.subheader("\U0001F4CA Analytics Report")
    if st.sidebar.button("View Report"):
        st.subheader("♻️ Waste & Environmental Analytics Report")

        # Fetch bin data again for latest updates
        bin_data = fetch_bin_data()

        # Waste Collection Trend
        fig_waste = px.line(bin_data, x="Bin ID", y="Fill Level (%)", title="Waste Collection Trend", markers=True)
        st.plotly_chart(fig_waste)

        # Carbon Footprint Analysis
        bin_data["Carbon Footprint (kg CO2)"] = bin_data["Fill Level (%)"] * 0.02  # Example Calculation
        fig_carbon = px.bar(bin_data, x="Bin ID", y="Carbon Footprint (kg CO2)", title="Carbon Footprint Analysis", color="Carbon Footprint (kg CO2)")
        st.plotly_chart(fig_carbon)

        # Environmental Impact Summary
        total_waste_collected = bin_data["Fill Level (%)"].sum()
        avg_carbon_footprint = bin_data["Carbon Footprint (kg CO2)"].mean()
        
        st.write(f"**Total Waste Collected:** {total_waste_collected:.2f} kg")
        st.write(f"**Average Carbon Footprint per Bin:** {avg_carbon_footprint:.2f} kg CO2")

        st.success("📊 Environmental Report Generated Successfully!")


st.success("✅ Dashboard Updated Successfully!")
