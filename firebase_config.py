import streamlit as st

firebaseConfig = {
    "apiKey": st.secrets["apiKey"],
    "authDomain": st.secrets["authDomain"],
    "projectId": st.secrets["projectId"],
    "storageBucket": st.secrets["storageBucket"],
    "messagingSenderId": st.secrets["messagingSenderId"],
    "appId": st.secrets["appId"],
    "databaseURL": st.secrets["databaseURL"]
}
