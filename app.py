import streamlit as st
import pyrebase
from firebase_config import firebaseConfig
import os
import google.generativeai as genai

from transformers import pipeline
import matplotlib.pyplot as plt
from collections import Counter
import datetime  # for timestamp
import requests

st.set_page_config(page_title="🧠 MindMate")

# === Emotion Classifier ===
@st.cache_resource
def load_emotion_model():
    return pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=1)

emotion_classifier = load_emotion_model()

# === Gemini API Key ===
genai.configure(api_key=st.secrets["google_api_key"])

# === Firebase Setup ===
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
db = firebase.database()  # <-- Realtime DB initialized here


# === Session State Management ===
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "mood_log" not in st.session_state:
    st.session_state.mood_log = []

# === LOGIN / SIGNUP SECTION ===
if not st.session_state.user:
    st.title("🔐 Welcome to MindMate")
    mode = st.selectbox("Choose:", ["Login", "Signup"])
    email = st.text_input("Email", key="email")
    password = st.text_input("Password", type="password", key="password")


    if mode == "Signup":
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        if st.button("Create Account"):
            if password == confirm_password:
                try:
                    auth.create_user_with_email_and_password(email, password)
                    st.success("✅ Account created! Please login.")
                   

                except Exception as e:
                    st.error(f"Signup error. Enter your correct email id. ")
            else:
                st.error("❌ Passwords do not match.")
    else:
        if st.button("Login"):
            try:
                user = auth.sign_in_with_email_and_password(email, password)
                st.session_state.user = user
                st.success("✅ Login successful!")
                st.rerun()
            except Exception as e:
                import json
                try:
                    error_json = e.args[1] if len(e.args) > 1 else str(e)
                    error_data = json.loads(error_json)
                    error_message = error_data["error"]["message"]

                    # 🔍 Match known Firebase auth errors
                    if error_message == "EMAIL_NOT_FOUND":
                        st.error("❌ Email not registered. Please sign up first.")
                    elif error_message == "INVALID_PASSWORD":
                        st.error("❌ Incorrect password. Please try again.")
                    elif error_message == "INVALID_EMAIL":
                        st.error("❌ Invalid email format. Please enter a valid email.")
                    elif error_message == "TOO_MANY_ATTEMPTS_TRY_LATER":
                        st.error("⚠️ Too many failed attempts. Please try again later.")
                    else:
                        st.error(f"Login failed: {error_message}")

                except:
                    st.error("⚠️ An unexpected login error occurred.")

                



# === MAIN CHAT INTERFACE ===
else:
    st.success(f"👋 Logged in as: {st.session_state.user['email']}")

    user = st.session_state.user
    id_token = user['idToken']
    user_id = user['localId']

    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.chat_history = []
        st.session_state.mood_log = []
        st.rerun()

    # === Navigation ===
    st.sidebar.title("🧭 Navigate")
    page = st.sidebar.radio("Go to", ["💬 Chatbot", "📊 Mood Tracker", "📘 Journal", "📂 My History"])


    # === Gemini Model Setup ===
    model = genai.GenerativeModel('gemini-1.5-pro')
    chat = model.start_chat(history=[])

    # === 💬 Chatbot ===
    if page == "💬 Chatbot":
        st.title("💬 MindMate Gemini Chatbot")
        input = st.text_input("What's on your mind?", key="input")
        submit = st.button("Ask")

        if submit and input:
            # Emotion Detection
            emotion_result = emotion_classifier(input)[0][0]
            predicted_emotion = emotion_result['label']
            emotion_score = emotion_result['score']
            st.info(f"🧠 Detected Emotion: **{predicted_emotion}** ({emotion_score:.2f})")
            st.session_state.mood_log.append(predicted_emotion)

            # Save mood to Firebase
            timestamp = datetime.datetime.now().isoformat()
            db.child("moods").child(user_id).push({
                "mood": predicted_emotion,
                "score": round(emotion_score, 2),
                "timestamp": timestamp
            }, token=id_token)

            # Gemini Response
            prompt = f"The user is feeling {predicted_emotion.lower()}. Respond with empathy.\n\n{input}"
            response = chat.send_message(prompt, stream=True)

            st.session_state.chat_history.append(("You", input))
            st.subheader("🧠 Gemini Responds:")
            
            # Collect full response
            full_response = ""
            for chunk in response:
                full_response += chunk.text

            # Format the response: remove weird line breaks and extra spaces
            cleaned_response = " ".join(full_response.split()).strip()

            # Optionally: keep only the first 2 sentences (to keep it short)
            import re
            sentences = re.split(r'(?<=[.!?]) +', cleaned_response)
            short_response = " ".join(sentences[::])

            # Display it
            st.write(short_response)

            # Save to chat history
            st.session_state.chat_history.append(("MindMate", short_response))



        st.subheader("🗒️ Chat History")
        for role, text in st.session_state.chat_history:
            st.write(f"**{role}:** {text}")

        # === PDF Download Section ===
        from io import BytesIO
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        if st.button("📥 Download Chat History as PDF"):
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            text_obj = c.beginText(40, height - 40)
            text_obj.setFont("Helvetica", 11)
            text_obj.setLeading(18)

            text_obj.textLine("🧠 MindMate - Chat History")
            text_obj.textLine("----------------------------------------")

            for role, message in st.session_state.chat_history:
                formatted = f"{role}: {message}"
                for line in formatted.splitlines():
                    while len(line) > 90:
                        text_obj.textLine(line[:90])
                        line = line[90:]
                    text_obj.textLine(line)
                text_obj.textLine("")

            c.drawText(text_obj)
            c.showPage()
            c.save()
            buffer.seek(0)

            st.download_button(
                label="📄 Download Chat PDF",
                data=buffer,
                file_name="mindmate_chat_history.pdf",
                mime="application/pdf"
            )


    # === 📊 Mood Tracker ===
    elif page == "📊 Mood Tracker":
        st.title("📊 Your Mood Dashboard")

        try:
            user = st.session_state.user
            user_id = user['localId']
            id_token = user['idToken']

            # Fetch mood data from Firebase
            moods = db.child("moods").child(user_id).get(token=id_token)

            if moods.each() is None:
                st.info("🕵️ No mood data yet. Start chatting to track your emotions.")
            else:
                # Extract mood values from Firebase
                mood_log = [mood.val().get('mood', '') for mood in moods.each()]
                mood_counts = Counter(mood_log)
                labels = list(mood_counts.keys())
                values = list(mood_counts.values())

                # Plotting the bar chart
                fig, ax = plt.subplots()
                ax.bar(labels, values, color="orchid")
                ax.set_ylabel("Count")
                ax.set_title("Your Emotional Trends")
                st.pyplot(fig)
        except Exception as e:
            st.error(f"Error loading mood data: {e}")

    # === 📘 Journal Page ===
    elif page == "📘 Journal":
        st.title("📘 Daily Journal")
        journal_input = st.text_area("Write your thoughts here...", height=200)
        if st.button("Summarize Journal"):
            if journal_input.strip() == "":
                st.warning("✍️ Please write something in your journal before summarizing.")
            else:
                summary_prompt = f"Summarize this journal entry in a supportive and insightful way:\n\n{journal_input}"
                summary_response = model.generate_content(summary_prompt)
                summary = summary_response.text

                st.subheader("🧠 Gemini Summary")
                st.write(summary)

                # Save journal to Firebase
                timestamp = datetime.datetime.now().isoformat()
                user_id = st.session_state.user['localId']
                db.child("journals").child(user_id).push({
                    "entry": journal_input,
                    "summary": summary,
                    "timestamp": timestamp
                }, token= id_token)
    # === 📂 History Viewer Page ===
    elif page == "📂 My History":
        st.title("📂 My Past Journal & Mood Logs")

        user_id = st.session_state.user['localId']

        # ==== Journal History ====
        st.subheader("📘 Journal Entries")
        try:
            journals = db.child("journals").child(user_id).get(token=id_token)
            if journals.each() is None:
                st.info("No journal entries found.")
            else:
                for journal in journals.each():
                    data = journal.val()
                    st.markdown(f"🗓️ **Date:** {data.get('timestamp', 'N/A')}")
                    st.markdown(f"📝 **Entry:** {data.get('entry', '')}")
                    st.markdown(f"🔍 **Summary:** {data.get('summary', '')}")
                    st.markdown("---")
        except requests.exceptions.HTTPError as e:
            st.error(f"Error loading journals: {e}")
        except Exception as e:
            st.error(f"Unexpected error loading journals: {e}")

        # ==== Mood History ====
        st.subheader("📊 Mood Logs")
        try:
            moods = db.child("moods").child(user_id).get(token=id_token)
            if moods.each() is None:
                st.info("No mood logs available.")
            else:
                for mood in moods.each():
                    m = mood.val()
                    st.write(f"🗓️ {m.get('timestamp', 'N/A')} — {m.get('mood', '')} ({m.get('score', '')})")
        except requests.exceptions.HTTPError as e:
            st.error(f"Error loading mood logs: {e}")
        except Exception as e:
            st.error(f"Unexpected error loading mood logs: {e}")