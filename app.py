import os
import sqlite3
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import plotly.express as px

from PIL import Image
from dotenv import load_dotenv

from google import genai
from google.genai import types


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Smart Farming Assistant",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")


# ============================================================
# GEMINI CLIENT
# ============================================================

if not API_KEY:

    st.error(
        "❌ GEMINI_API_KEY is missing.\n\n"
        "Create a .env file and add:\n"
        "GEMINI_API_KEY=your_api_key"
    )

    st.stop()


try:

    client = genai.Client(api_key=API_KEY)

except Exception as e:

    st.error(f"Gemini connection failed: {e}")
    st.stop()


# ============================================================
# FIND A USABLE MODEL
# ============================================================

@st.cache_resource
def find_model():

    preferred_models = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.0-flash"
    ]

    try:

        available_models = []

        for model in client.models.list():

            name = getattr(model, "name", "")

            if name:
                available_models.append(
                    name.replace("models/", "")
                )

        for preferred in preferred_models:

            if preferred in available_models:
                return preferred

        for model_name in available_models:

            if "flash" in model_name.lower():
                return model_name

        if available_models:

            return available_models[0]

        return None

    except Exception:

        return None


MODEL_NAME = find_model()


if not MODEL_NAME:

    st.warning(
        "⚠️ No Gemini model was detected. "
        "Run list_models.py to check your API access."
    )


# ============================================================
# DATABASE
# ============================================================

DATABASE = "smart_farming.db"


def init_database():

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farm_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_name TEXT,
            location TEXT,
            crop TEXT,
            soil_type TEXT,
            soil_ph REAL,
            nitrogen REAL,
            phosphorus REAL,
            potassium REAL,
            temperature REAL,
            humidity REAL,
            rainfall REAL,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            message TEXT,
            created_at TEXT
        )
    """)

    connection.commit()
    connection.close()


init_database()


# ============================================================
# SAVE FARM DATA
# ============================================================

def save_farm_data(data):

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO farm_profiles (
            farmer_name,
            location,
            crop,
            soil_type,
            soil_ph,
            nitrogen,
            phosphorus,
            potassium,
            temperature,
            humidity,
            rainfall,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        data["farmer_name"],
        data["location"],
        data["crop"],
        data["soil_type"],
        data["soil_ph"],
        data["nitrogen"],
        data["phosphorus"],
        data["potassium"],
        data["temperature"],
        data["humidity"],
        data["rainfall"],
        datetime.now().isoformat()

    ))

    connection.commit()
    connection.close()


# ============================================================
# SAVE CHAT
# ============================================================

def save_chat(role, message):

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO chat_history
        (role, message, created_at)
        VALUES (?, ?, ?)
    """, (
        role,
        message,
        datetime.now().isoformat()
    ))

    connection.commit()
    connection.close()


# ============================================================
# GEMINI TEXT FUNCTION
# ============================================================

def ask_ai(prompt):

    if not MODEL_NAME:

        return "No Gemini model is available."

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if response.text:

            return response.text

        return "AI returned an empty response."

    except Exception as e:

        return f"❌ Gemini Error: {str(e)}"


# ============================================================
# GEMINI IMAGE FUNCTION
# ============================================================

def analyze_image(uploaded_file, prompt):

    if not MODEL_NAME:

        return "No Gemini model is available."

    try:

        image_bytes = uploaded_file.getvalue()

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=uploaded_file.type
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                image_part,
                prompt
            ]
        )

        if response.text:

            return response.text

        return "AI could not analyze the image."

    except Exception as e:

        return f"❌ Image analysis error: {str(e)}"


# ============================================================
# WEATHER API
# ============================================================

def get_weather(latitude, longitude):

    try:

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            "&current=temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "wind_speed_10m"
            "&daily=temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum"
            "&timezone=auto"
        )

        response = requests.get(
            url,
            timeout=10
        )

        if response.status_code == 200:

            return response.json()

        return None

    except Exception:

        return None


# ============================================================
# CROP RECOMMENDATION
# ============================================================

def crop_recommendation(
    temperature,
    rainfall,
    ph,
    nitrogen,
    phosphorus,
    potassium
):

    recommendations = []

    if (
        20 <= temperature <= 35
        and rainfall >= 80
        and 5.5 <= ph <= 7.5
    ):

        recommendations.append("🌾 Rice")

    if (
        18 <= temperature <= 32
        and 40 <= rainfall <= 120
        and 5.5 <= ph <= 7.5
    ):

        recommendations.append("🌽 Maize")

    if (
        15 <= temperature <= 30
        and 30 <= rainfall <= 100
        and 6.0 <= ph <= 7.5
    ):

        recommendations.append("🌾 Wheat")

    if (
        20 <= temperature <= 35
        and 30 <= rainfall <= 120
        and 5.5 <= ph <= 7.5
    ):

        recommendations.append("🥜 Groundnut")

    if (
        20 <= temperature <= 35
        and 40 <= rainfall <= 150
        and 5.5 <= ph <= 7.5
    ):

        recommendations.append("🌿 Cotton")

    if (
        18 <= temperature <= 32
        and 40 <= rainfall <= 120
        and 5.5 <= ph <= 7.5
    ):

        recommendations.append("🍅 Tomato")

    if not recommendations:

        recommendations = [
            "🌾 Rice",
            "🌽 Maize",
            "🥜 Groundnut"
        ]

    return recommendations


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: 800;
    text-align: center;
    padding: 15px;
}

.subtitle {
    text-align: center;
    font-size: 18px;
    margin-bottom: 25px;
}

.card {
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #ddd;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    '🌱 AI Smart Farming Assistant'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Intelligent AI-powered farming decision support system'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🌱 Smart Farming")

st.sidebar.success(
    f"AI Model: {MODEL_NAME or 'Unavailable'}"
)

language = st.sidebar.selectbox(
    "🌐 Language",
    [
        "English",
        "Kannada",
        "Hindi",
        "Tamil",
        "Telugu",
        "Marathi"
    ]
)


page = st.sidebar.radio(
    "📌 Select Feature",
    [
        "🏠 Dashboard",
        "🤖 AI Farming Chat",
        "🌾 Crop Recommendation",
        "🌱 Soil Analysis",
        "🦠 Disease Detection",
        "🐛 Pest Management",
        "💧 Irrigation Advisor",
        "🌦️ Weather Assistant",
        "🧪 Fertilizer Advisor",
        "📅 Crop Calendar",
        "💰 Market Information",
        "📊 Farm Report",
        "🔔 Smart Alerts"
    ]
)


# ============================================================
# FARM PROFILE
# ============================================================

st.sidebar.divider()

st.sidebar.subheader("👨‍🌾 Farm Profile")

farmer_name = st.sidebar.text_input(
    "Farmer Name",
    "Farmer"
)

location = st.sidebar.text_input(
    "Farm Location",
    "Dharwad"
)

crop = st.sidebar.selectbox(
    "Current Crop",
    [
        "Rice",
        "Maize",
        "Wheat",
        "Tomato",
        "Cotton",
        "Groundnut",
        "Sugarcane",
        "Other"
    ]
)

soil_type = st.sidebar.selectbox(
    "Soil Type",
    [
        "Black Soil",
        "Red Soil",
        "Alluvial Soil",
        "Sandy Soil",
        "Clay Soil",
        "Loamy Soil"
    ]
)


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.header("🏠 Farm Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "👨‍🌾 Farmer",
        farmer_name
    )

    col2.metric(
        "🌾 Crop",
        crop
    )

    col3.metric(
        "🌱 Soil",
        soil_type
    )

    col4.metric(
        "🤖 AI",
        "Online" if MODEL_NAME else "Offline"
    )

    st.divider()

    st.subheader("📊 Current Farm Conditions")

    col1, col2, col3 = st.columns(3)

    with col1:

        temperature = st.number_input(
            "🌡️ Temperature °C",
            0.0,
            60.0,
            28.0
        )

        humidity = st.number_input(
            "💧 Humidity %",
            0.0,
            100.0,
            65.0
        )

    with col2:

        rainfall = st.number_input(
            "🌧️ Rainfall mm",
            0.0,
            500.0,
            100.0
        )

        ph = st.number_input(
            "🧪 Soil pH",
            0.0,
            14.0,
            6.5
        )

    with col3:

        nitrogen = st.number_input(
            "N - Nitrogen",
            0.0,
            200.0,
            50.0
        )

        phosphorus = st.number_input(
            "P - Phosphorus",
            0.0,
            200.0,
            40.0
        )

        potassium = st.number_input(
            "K - Potassium",
            0.0,
            200.0,
            40.0
        )

    if st.button(
        "💾 Save Farm Information",
        use_container_width=True
    ):

        save_farm_data({

            "farmer_name": farmer_name,
            "location": location,
            "crop": crop,
            "soil_type": soil_type,
            "soil_ph": ph,
            "nitrogen": nitrogen,
            "phosphorus": phosphorus,
            "potassium": potassium,
            "temperature": temperature,
            "humidity": humidity,
            "rainfall": rainfall

        })

        st.success(
            "✅ Farm information saved successfully."
        )

    st.divider()

    st.subheader("🌱 Quick AI Recommendation")

    if st.button(
        "🤖 Generate Quick Recommendation"
    ):

        prompt = f"""
You are an agricultural AI assistant.

Farmer: {farmer_name}
Location: {location}
Crop: {crop}
Soil: {soil_type}

Temperature: {temperature} C
Humidity: {humidity} %
Rainfall: {rainfall} mm
Soil pH: {ph}

N: {nitrogen}
P: {phosphorus}
K: {potassium}

Preferred language:
{language}

Give a short farm health summary and
the most important actions the farmer
should consider next.

Use simple language.
"""

        with st.spinner("AI is analyzing the farm..."):

            result = ask_ai(prompt)

        st.write(result)


# ============================================================
# AI CHAT
# ============================================================

elif page == "🤖 AI Farming Chat":

    st.header("🤖 AI Farming Assistant")

    st.write(
        "Ask anything about farming, crops, soil, "
        "irrigation, pests, diseases and weather."
    )

    if "chat_messages" not in st.session_state:

        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:

        with st.chat_message(
            message["role"]
        ):

            st.write(
                message["content"]
            )

    question = st.chat_input(
        "Ask your farming question..."
    )

    if question:

        st.session_state.chat_messages.append({
            "role": "user",
            "content": question
        })

        save_chat(
            "user",
            question
        )

        prompt = f"""
You are an AI Smart Farming Assistant.

Farmer:
{farmer_name}

Location:
{location}

Crop:
{crop}

Soil:
{soil_type}

Preferred language:
{language}

Farmer question:
{question}

Provide:
1. Direct answer
2. Practical suggestions
3. Important precautions
4. When local agricultural expert advice is needed

Avoid claiming certainty when information is insufficient.
"""

        with st.spinner("AI is thinking..."):

            answer = ask_ai(prompt)

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer
        })

        save_chat(
            "assistant",
            answer
        )

        st.rerun()


# ============================================================
# CROP RECOMMENDATION
# ============================================================

elif page == "🌾 Crop Recommendation":

    st.header("🌾 AI Crop Recommendation")

    st.write(
        "Enter soil and climate conditions to find suitable crops."
    )

    col1, col2 = st.columns(2)

    with col1:

        temperature = st.number_input(
            "Temperature °C",
            0.0,
            60.0,
            28.0
        )

        rainfall = st.number_input(
            "Rainfall mm",
            0.0,
            500.0,
            100.0
        )

        ph = st.number_input(
            "Soil pH",
            0.0,
            14.0,
            6.5
        )

    with col2:

        nitrogen = st.number_input(
            "Nitrogen",
            0.0,
            200.0,
            50.0
        )

        phosphorus = st.number_input(
            "Phosphorus",
            0.0,
            200.0,
            40.0
        )

        potassium = st.number_input(
            "Potassium",
            0.0,
            200.0,
            40.0
        )

    if st.button(
        "🌾 Recommend Crops",
        use_container_width=True
    ):

        recommendations = crop_recommendation(
            temperature,
            rainfall,
            ph,
            nitrogen,
            phosphorus,
            potassium
        )

        st.subheader("Recommended Crops")

        for item in recommendations:

            st.success(item)

        prompt = f"""
Recommend crops using these conditions:

Temperature: {temperature} C
Rainfall: {rainfall} mm
pH: {ph}
N: {nitrogen}
P: {phosphorus}
K: {potassium}
Location: {location}

Language: {language}

Explain why suitable crops may fit these conditions.
Mention that actual recommendations should be
validated with local agricultural conditions.
"""

        ai_result = ask_ai(prompt)

        st.subheader("🤖 AI Explanation")

        st.write(ai_result)


# ============================================================
# SOIL ANALYSIS
# ============================================================

elif page == "🌱 Soil Analysis":

    st.header("🌱 AI Soil Health Analyzer")

    n = st.number_input(
        "Nitrogen (N)",
        0.0,
        200.0,
        50.0
    )

    p = st.number_input(
        "Phosphorus (P)",
        0.0,
        200.0,
        40.0
    )

    k = st.number_input(
        "Potassium (K)",
        0.0,
        200.0,
        40.0
    )

    ph = st.slider(
        "Soil pH",
        0.0,
        14.0,
        6.5
    )

    if st.button(
        "🔬 Analyze Soil",
        use_container_width=True
    ):

        prompt = f"""
Analyze agricultural soil.

Soil type:
{soil_type}

Crop:
{crop}

Nitrogen:
{n}

Phosphorus:
{p}

Potassium:
{k}

pH:
{ph}

Language:
{language}

Provide:

1. General soil health
2. Nutrient observations
3. Possible deficiencies
4. Suitable crop considerations
5. Soil improvement ideas
6. Organic matter suggestions
7. Importance of soil testing

Do not give falsely precise fertilizer dosages.
"""

        with st.spinner("Analyzing soil..."):

            result = ask_ai(prompt)

        st.write(result)


# ============================================================
# DISEASE DETECTION
# ============================================================

elif page == "🦠 Disease Detection":

    st.header("🦠 Plant Disease Detection")

    st.info(
        "Upload a clear image of a plant leaf."
    )

    uploaded_image = st.file_uploader(
        "📷 Upload plant image",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]
    )

    if uploaded_image:

        image = Image.open(
            uploaded_image
        )

        st.image(
            image,
            caption="Uploaded Plant",
            width=450
        )

        if st.button(
            "🔍 Analyze Plant",
            use_container_width=True
        ):

            prompt = f"""
Analyze this plant image as an agricultural
assistant.

Crop:
{crop}

Location:
{location}

Language:
{language}

Identify:

1. Whether it appears healthy
2. Possible disease or disorder
3. Visible symptoms
4. Possible causes
5. General management options
6. Prevention
7. When to consult an agricultural expert

Important:
An image alone cannot guarantee a diagnosis.
Clearly communicate uncertainty.
"""

            with st.spinner(
                "AI is analyzing the plant image..."
            ):

                result = analyze_image(
                    uploaded_image,
                    prompt
                )

            st.subheader(
                "🦠 AI Plant Analysis"
            )

            st.write(result)


# ============================================================
# PEST MANAGEMENT
# ============================================================

elif page == "🐛 Pest Management":

    st.header("🐛 AI Pest Management")

    pest = st.text_input(
        "Enter pest name or symptoms",
        placeholder="Example: Aphids on tomato leaves"
    )

    if st.button(
        "🐛 Analyze Pest Problem",
        use_container_width=True
    ):

        if pest:

            prompt = f"""
You are an agricultural pest-management assistant.

Crop:
{crop}

Location:
{location}

Problem:
{pest}

Language:
{language}

Explain:

1. Possible pest
2. Symptoms
3. Crop damage
4. Prevention
5. Integrated pest management
6. Non-chemical options
7. Safe management considerations
8. When expert advice is needed

Avoid unsafe chemical instructions.
"""

            result = ask_ai(prompt)

            st.write(result)

        else:

            st.warning(
                "Please enter a pest or symptom."
            )


# ============================================================
# IRRIGATION
# ============================================================

elif page == "💧 Irrigation Advisor":

    st.header("💧 Smart Irrigation Advisor")

    col1, col2 = st.columns(2)

    with col1:

        temperature = st.number_input(
            "Temperature °C",
            0.0,
            60.0,
            30.0
        )

        humidity = st.number_input(
            "Humidity %",
            0.0,
            100.0,
            60.0
        )

    with col2:

        rainfall = st.number_input(
            "Recent Rainfall mm",
            0.0,
            500.0,
            10.0
        )

        moisture = st.slider(
            "Estimated Soil Moisture %",
            0,
            100,
            50
        )

    if st.button(
        "💧 Generate Irrigation Advice",
        use_container_width=True
    ):

        prompt = f"""
Act as an agricultural irrigation advisor.

Crop:
{crop}

Soil:
{soil_type}

Temperature:
{temperature} C

Humidity:
{humidity} %

Recent rainfall:
{rainfall} mm

Estimated soil moisture:
{moisture} %

Language:
{language}

Explain:

1. Whether irrigation may be needed
2. Factors to check before watering
3. Water-saving methods
4. Signs of overwatering
5. Signs of underwatering
6. Weather considerations

Do not pretend that exact irrigation amounts
can be determined without field measurements.
"""

        result = ask_ai(prompt)

        st.write(result)


# ============================================================
# WEATHER
# ============================================================

elif page == "🌦️ Weather Assistant":

    st.header("🌦️ Weather & Farming Assistant")

    col1, col2 = st.columns(2)

    with col1:

        latitude = st.number_input(
            "Latitude",
            -90.0,
            90.0,
            15.4589
        )

    with col2:

        longitude = st.number_input(
            "Longitude",
            -180.0,
            180.0,
            75.0078
        )

    if st.button(
        "🌦️ Get Weather",
        use_container_width=True
    ):

        weather = get_weather(
            latitude,
            longitude
        )

        if weather:

            current = weather["current"]

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Temperature",
                f"{current['temperature_2m']} °C"
            )

            col2.metric(
                "Humidity",
                f"{current['relative_humidity_2m']} %"
            )

            col3.metric(
                "Rain",
                f"{current['precipitation']} mm"
            )

            col4.metric(
                "Wind",
                f"{current['wind_speed_10m']} km/h"
            )

            daily = weather["daily"]

            dataframe = pd.DataFrame({

                "Date":
                    daily["time"],

                "Max Temperature":
                    daily["temperature_2m_max"],

                "Min Temperature":
                    daily["temperature_2m_min"],

                "Rainfall":
                    daily["precipitation_sum"]

            })

            st.subheader(
                "📈 Forecast"
            )

            figure = px.line(
                dataframe,
                x="Date",
                y=[
                    "Max Temperature",
                    "Min Temperature"
                ],
                markers=True
            )

            st.plotly_chart(
                figure,
                use_container_width=True
            )

            prompt = f"""
Analyze weather for farming.

Crop:
{crop}

Temperature:
{current['temperature_2m']} C

Humidity:
{current['relative_humidity_2m']} %

Rain:
{current['precipitation']} mm

Wind:
{current['wind_speed_10m']} km/h

Language:
{language}

Give advice about:

1. Irrigation
2. Crop protection
3. Disease risk
4. Pest risk
5. General weather precautions
"""

            result = ask_ai(prompt)

            st.subheader(
                "🤖 AI Weather Advice"
            )

            st.write(result)

        else:

            st.error(
                "Unable to retrieve weather data."
            )


# ============================================================
# FERTILIZER
# ============================================================

elif page == "🧪 Fertilizer Advisor":

    st.header("🧪 AI Fertilizer Advisor")

    n = st.number_input(
        "Nitrogen",
        0.0,
        200.0,
        50.0
    )

    p = st.number_input(
        "Phosphorus",
        0.0,
        200.0,
        40.0
    )

    k = st.number_input(
        "Potassium",
        0.0,
        200.0,
        40.0
    )

    ph = st.number_input(
        "Soil pH",
        0.0,
        14.0,
        6.5
    )

    if st.button(
        "🧪 Generate Fertilizer Advice",
        use_container_width=True
    ):

        prompt = f"""
You are an agricultural nutrient advisor.

Crop:
{crop}

Soil:
{soil_type}

N:
{n}

P:
{p}

K:
{k}

pH:
{ph}

Language:
{language}

Explain:

1. Nutrient observations
2. Possible deficiencies
3. General fertilizer categories
4. Organic alternatives
5. Soil testing importance
6. Application precautions

Do not provide falsely precise chemical dosages.
"""

        result = ask_ai(prompt)

        st.write(result)


# ============================================================
# CROP CALENDAR
# ============================================================

elif page == "📅 Crop Calendar":

    st.header("📅 AI Crop Calendar")

    if st.button(
        "📅 Generate Crop Calendar",
        use_container_width=True
    ):

        prompt = f"""
Create a farming calendar for:

Crop:
{crop}

Location:
{location}

Soil:
{soil_type}

Language:
{language}

Include:

1. Land preparation
2. Seed selection
3. Sowing
4. Irrigation
5. Nutrient management
6. Weed management
7. Pest monitoring
8. Disease monitoring
9. Harvest preparation
10. Harvesting

Use approximate stages rather than claiming
exact dates without local data.
"""

        with st.spinner(
            "Creating crop calendar..."
        ):

            result = ask_ai(prompt)

        st.write(result)

    st.divider()

    calendar = pd.DataFrame({

        "Activity": [
            "Land Preparation",
            "Seed Selection",
            "Sowing",
            "Irrigation",
            "Nutrient Management",
            "Pest Monitoring",
            "Disease Monitoring",
            "Harvest Preparation",
            "Harvesting"
        ],

        "Stage": [
            "Before sowing",
            "Before sowing",
            "Early stage",
            "Crop growth",
            "Crop growth",
            "Throughout cycle",
            "Throughout cycle",
            "Maturity",
            "Maturity"
        ]

    })

    st.dataframe(
        calendar,
        use_container_width=True
    )


# ============================================================
# MARKET INFORMATION
# ============================================================

elif page == "💰 Market Information":

    st.header("💰 Market Information")

    st.info(
        "The values below are demonstration data. "
        "For a real deployment, connect this page "
        "to a verified live agricultural market-price API."
    )

    market_data = pd.DataFrame({

        "Crop": [
            "Rice",
            "Maize",
            "Wheat",
            "Tomato",
            "Cotton",
            "Groundnut"
        ],

        "Example Price": [
            2500,
            2200,
            2700,
            3000,
            7000,
            5500
        ]

    })

    st.dataframe(
        market_data,
        use_container_width=True
    )

    figure = px.bar(
        market_data,
        x="Crop",
        y="Example Price",
        title="Example Crop Prices"
    )

    st.plotly_chart(
        figure,
        use_container_width=True
    )

    selected_crop = st.selectbox(
        "Select crop",
        market_data["Crop"]
    )

    if st.button(
        "💰 Get Selling Guidance"
    ):

        prompt = f"""
Give general agricultural selling guidance for:

Crop:
{selected_crop}

Location:
{location}

Language:
{language}

Explain:

1. Factors affecting market price
2. Crop quality
3. Storage
4. Transportation
5. Comparing markets
6. Importance of checking current official prices
"""

        result = ask_ai(prompt)

        st.write(result)


# ============================================================
# FARM REPORT
# ============================================================

elif page == "📊 Farm Report":

    st.header("📊 AI Farm Report")

    temperature = st.number_input(
        "Temperature °C",
        0.0,
        60.0,
        28.0
    )

    humidity = st.number_input(
        "Humidity %",
        0.0,
        100.0,
        65.0
    )

    rainfall = st.number_input(
        "Rainfall mm",
        0.0,
        500.0,
        100.0
    )

    ph = st.number_input(
        "Soil pH",
        0.0,
        14.0,
        6.5
    )

    if st.button(
        "📄 Generate Farm Report",
        use_container_width=True
    ):

        prompt = f"""
Create a professional agricultural farm report.

Farmer:
{farmer_name}

Location:
{location}

Crop:
{crop}

Soil:
{soil_type}

Temperature:
{temperature} C

Humidity:
{humidity} %

Rainfall:
{rainfall} mm

pH:
{ph}

Language:
{language}

Sections:

1. Farm overview
2. Crop observations
3. Soil observations
4. Weather observations
5. Irrigation considerations
6. Pest risks
7. Disease risks
8. Nutrient considerations
9. Recommended next steps
10. Precautions

Keep the language simple.
"""

        with st.spinner(
            "Generating farm report..."
        ):

            result = ask_ai(prompt)

        st.markdown(
            "## 📄 AI Farm Report"
        )

        st.write(result)


# ============================================================
# SMART ALERTS
# ============================================================

elif page == "🔔 Smart Alerts":

    st.header("🔔 Smart Farm Alerts")

    temperature = st.number_input(
        "Temperature °C",
        0.0,
        60.0,
        32.0
    )

    humidity = st.number_input(
        "Humidity %",
        0.0,
        100.0,
        75.0
    )

    rainfall = st.number_input(
        "Expected Rainfall mm",
        0.0,
        500.0,
        20.0
    )

    if temperature >= 40:

        st.warning(
            "🔥 High temperature alert. "
            "Monitor crop water stress."
        )

    elif temperature >= 35:

        st.info(
            "🌡️ High temperature. "
            "Monitor crop conditions."
        )

    if humidity >= 85:

        st.warning(
            "💧 High humidity. "
            "Monitor crops for disease risk."
        )

    if rainfall >= 50:

        st.warning(
            "🌧️ Heavy rainfall possibility. "
            "Review drainage and irrigation plans."
        )

    if temperature < 15:

        st.info(
            "❄️ Low temperature alert."
        )

    if st.button(
        "🤖 Generate AI Risk Assessment",
        use_container_width=True
    ):

        prompt = f"""
Analyze farming risks.

Crop:
{crop}

Location:
{location}

Temperature:
{temperature} C

Humidity:
{humidity} %

Rainfall:
{rainfall} mm

Language:
{language}

Provide:

1. Weather risk
2. Disease risk
3. Pest risk
4. Irrigation risk
5. Crop protection considerations
6. Priority actions
"""

        result = ask_ai(prompt)

        st.subheader(
            "🤖 AI Risk Assessment"
        )

        st.write(result)


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🌱 AI Smart Farming Assistant"
)

st.sidebar.caption(
    "Python + Streamlit + Gemini + SQLite"
)