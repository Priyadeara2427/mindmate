import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, db
import os
import google.generativeai as genai

import matplotlib.pyplot as plt
from collections import Counter
import datetime
import requests

st.set_page_config(page_title="🧠 MindMate")

# === Gemini API Key ===
genai.configure(api_key=st.secrets["google_api_key"])

# === Firebase Admin Setup ===
if not firebase_admin._apps:
    cred = credentials.Certificate("mindmate-301d7-be0088c3286c.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://mindmate-301d7-default-rtdb.firebaseio.com/'
    })

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
                    user_record = auth.create_user(email=email, password=password)
                    st.success("✅ Account created! Please login.")
                except Exception as e:
                    st.error(f"Signup error: {e}")
            else:
                st.error("❌ Passwords do not match.")
    else:
        if st.button("Login"):
            try:
                user_record = auth.get_user_by_email(email)
                st.session_state.user = {"email": user_record.email, "uid": user_record.uid}
                st.success("✅ Login successful!")
                st.rerun()
            except auth.UserNotFoundError:
                st.error("❌ Email not registered. Please sign up first.")
            except Exception as e:
                st.error(f"Login failed: {e}")

# === MAIN CHAT INTERFACE ===
else:
    st.success(f"👋 Logged in as: {st.session_state.user['email']}")
    user_id = st.session_state.user['uid']

    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.chat_history = []
        st.session_state.mood_log = []
        st.rerun()

    st.sidebar.title("🧭 Navigate")
    page = st.sidebar.radio("Go to", ["💬 Chatbot", "📊 Mood Tracker", "📘 Journal", "📂 My History"])

    model = genai.GenerativeModel('gemini-1.5-pro')
    chat = model.start_chat(history=[])

    if page == "💬 Chatbot":
        st.title("💬 MindMate Gemini Chatbot")
        input = st.text_input("What's on your mind?", key="input")
        submit = st.button("Ask")

        if submit and input:
            # === Emotion Detection using Gemini ===
            emotion_prompt = f"What is the most likely emotion in this sentence: \"{input}\"? Reply only with the emotion name."
            try:
                response = model.generate_content(emotion_prompt)
                predicted_emotion = response.text.strip()
                emotion_score = 1.0  # dummy confidence for consistency
            except Exception as e:
                st.error(f"Emotion detection failed: {e}")
                predicted_emotion = "Unknown"
                emotion_score = 0.0

            st.info(f"🧠 Detected Emotion: **{predicted_emotion}** ({emotion_score:.2f})")
            st.session_state.mood_log.append(predicted_emotion)

            timestamp = datetime.datetime.now().isoformat()
            ref = db.reference(f"moods/{user_id}")
            ref.push({
                "mood": predicted_emotion,
                "score": round(emotion_score, 2),
                "timestamp": timestamp
            })

            prompt = f"The user is feeling {predicted_emotion.lower()}. Respond with empathy.\n\n{input}"
            response = chat.send_message(prompt, stream=True)

            st.session_state.chat_history.append(("You", input))
            st.subheader("🧠 Gemini Responds:")
            full_response = ""
            for chunk in response:
                full_response += chunk.text

            import re
            cleaned = " ".join(full_response.split()).strip()
            sentences = re.split(r'(?<=[.!?]) +', cleaned)
            st.write(" ".join(sentences))
            st.session_state.chat_history.append(("MindMate", " ".join(sentences)))

        st.subheader("🗒️ Chat History")
        for role, text in st.session_state.chat_history:
            st.write(f"**{role}:** {text}")

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

            st.download_button("📄 Download Chat PDF", buffer, "mindmate_chat_history.pdf", "application/pdf")

    elif page == "📊 Mood Tracker":
        st.title("📊 Your Mood Dashboard")
        try:
            moods = db.reference(f"moods/{user_id}").get()
            if not moods:
                st.info("🕵️ No mood data yet.")
            else:
                mood_log = [entry.get("mood", "") for entry in moods.values()]
                mood_counts = Counter(mood_log)
                labels = list(mood_counts.keys())
                values = list(mood_counts.values())

                fig, ax = plt.subplots()
                ax.bar(labels, values, color="orchid")
                ax.set_ylabel("Count")
                ax.set_title("Your Emotional Trends")
                st.pyplot(fig)
        except Exception as e:
            st.error(f"Error loading mood data: {e}")

    elif page == "📘 Journal":
        st.title("📘 Daily Journal")
        journal_input = st.text_area("Write your thoughts here...", height=200)
        if st.button("Summarize Journal"):
            if journal_input.strip() == "":
                st.warning("✍️ Please write something first.")
            else:
                summary_prompt = f"Summarize this journal entry in a supportive way:\n\n{journal_input}"
                summary = model.generate_content(summary_prompt).text
                st.subheader("🧠 Gemini Summary")
                st.write(summary)

                timestamp = datetime.datetime.now().isoformat()
                db.reference(f"journals/{user_id}").push({
                    "entry": journal_input,
                    "summary": summary,
                    "timestamp": timestamp
                })

    elif page == "📂 My History":
        st.title("📂 My Past Journal & Mood Logs")

        st.subheader("📘 Journal Entries")
        try:
            journals = db.reference(f"journals/{user_id}").get()
            if not journals:
                st.info("No journal entries found.")
            else:
                for data in journals.values():
                    st.markdown(f"🗓️ **Date:** {data.get('timestamp', 'N/A')}")
                    st.markdown(f"📝 **Entry:** {data.get('entry', '')}")
                    st.markdown(f"🔍 **Summary:** {data.get('summary', '')}")
                    st.markdown("---")
        except Exception as e:
            st.error(f"Error loading journals: {e}")

        st.subheader("📊 Mood Logs")
        try:
            moods = db.reference(f"moods/{user_id}").get()
            if not moods:
                st.info("No mood logs available.")
            else:
                for m in moods.values():
                    st.write(f"🗓️ {m.get('timestamp', 'N/A')} — {m.get('mood', '')} ({m.get('score', '')})")
        except Exception as e:
            st.error(f"Error loading mood logs: {e}")
