import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, db
import os
import google.generativeai as genai

import matplotlib.pyplot as plt
from collections import Counter
import datetime
import requests
import json
import re

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
    page = st.sidebar.radio("Go to", ["💬 Chatbot", "📊 Mood Tracker", "📘 Journal", "📂 My History", "📞 Emergency Setup", "🤝 My Friends"])

    model = genai.GenerativeModel('gemini-1.5-pro')
    chat = model.start_chat(history=[])

    if page == "💬 Chatbot":
        st.title("💬 MindMate Gemini Chatbot")
        user_input = st.text_area("What's on your mind?", height=100, key="input")
        submit = st.button("Ask")

        if submit and user_input:
            # === Emotion Detection using Gemini ===

            emotion_prompt = f"""
            You are an emotion classification AI.

            Classify the following sentence into one of the exact options from this list:
            ["happy", "sad", "angry", "anxious", "calm", "neutral", "excited", "bored", "frustrated"]

            Text: "{user_input}"

            Respond ONLY with valid JSON in this format:
            {{ "emotion": "<chosen_category_from_list>", "score": <confidence_between_0_and_1> }}

            Do not explain. Do not include anything else.
            """
            try:
                response = model.generate_content(emotion_prompt)

                # Check if response is empty or None
                if not response.text:
                    raise ValueError("Gemini returned empty response")

                raw_text = response.text.strip()
                # Remove markdown code fences if any (fix #1)
                clean_json = re.sub(r"^```(?:json)?|```$", "", raw_text).strip()
                parsed = json.loads(clean_json)
                predicted_emotion = parsed.get("emotion", "neutral").lower()
                emotion_score = parsed.get("score", 0.0)

                # Validate allowed emotions (fix #2)
                allowed_emotions = ["happy", "sad", "angry", "anxious", "calm", "neutral", "excited", "bored", "frustrated"]
                if predicted_emotion not in allowed_emotions:
                    predicted_emotion = "neutral"
                    emotion_score = 0.0

                # Optional debug logging (fix #5)
                # st.write("🔍 Raw Gemini output:", response.text)

            except Exception as e:
                st.error(f"Emotion classification failed: {e}")
                predicted_emotion = "neutral"
                emotion_score = 0.0

            st.info(f"🧠 Detected Emotion: **{predicted_emotion}**")
            reinforcement_prompt = f"Give a brief, supportive and motivational message for someone who is feeling {predicted_emotion.lower()}."

            try:
                reinforcement_response = model.generate_content(reinforcement_prompt)
                if not reinforcement_response.text:
                    raise ValueError("Gemini returned empty reinforcement message")
                reinforcement_message = reinforcement_response.text.strip()
            except Exception:
                reinforcement_message = "Keep going, you're doing your best. Take one step at a time."

            st.success(f"💡 **MindMate Tip:** {reinforcement_message}")

            st.session_state.mood_log.append(predicted_emotion)

            timestamp = datetime.datetime.now().isoformat()
            ref = db.reference(f"moods/{user_id}")
            ref.push({
                "mood": predicted_emotion,
                "score": emotion_score,
                "timestamp": timestamp
            })

            # === Emergency Mood Check: If user has 3+ consecutive negative moods
            low_moods = {"sad", "angry", "anxious", "frustrated", "depressed"}
            recent_moods = db.reference(f"moods/{user_id}").order_by_key().limit_to_last(5).get()

            if recent_moods:
                low_mood_count = sum(1 for m in recent_moods.values() if m.get("mood", "").lower() in low_moods)
                if low_mood_count >= 3:
                    st.warning("⚠️ Multiple low mood entries detected.")
                    emergency_contacts = db.reference(f"emergency_contacts/{user_id}").get()
                    if emergency_contacts:
                        for contact in emergency_contacts.values():
                            st.info(f"📨 Alert prepared for: {contact.get('name','')} ({contact.get('email','')})")
                            # Future scope: Send actual email alerts using a cloud function or SMTP
                    else:
                        st.info("No emergency contacts added.")

            prompt = f"The user is feeling {predicted_emotion.lower()}. Respond with empathy.\n\n{user_input}"
            response = chat.send_message(prompt, stream=True)

            st.session_state.chat_history.append(("You", user_input))
            st.subheader("🧠 Gemini Responds:")
            full_response = ""
            for chunk in response:
                full_response += chunk.text

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
                ax.set_ylabel("Count")  # fix #3: This is count of moods
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
    
    elif page == "📞 Emergency Setup":
        st.title("📞 Emergency Contact Settings")

        if "contact_name" not in st.session_state:
            st.session_state.contact_name = ""
        if "contact_email" not in st.session_state:
            st.session_state.contact_email = ""

        contact_name = st.text_input("Contact Name", value=st.session_state.contact_name, key="contact_name_input")
        contact_email = st.text_input("Contact Email", value=st.session_state.contact_email, key="contact_email_input")

        if st.button("Save Contact"):
            contacts_ref = db.reference(f"emergency_contacts/{user_id}")
            existing_contacts = contacts_ref.get() or {}

            duplicate = any(c.get("email", "").lower() == contact_email.lower() for c in existing_contacts.values())

            if duplicate:
                st.warning("⚠️ This contact is already saved.")
            elif contact_name.strip() == "" or contact_email.strip() == "":
                st.warning("❗ Both fields are required.")
            else:
                contacts_ref.push({
                    "name": contact_name.strip(),
                    "email": contact_email.strip()
                })
                st.success("✅ Emergency contact saved.")

                # Clear input fields
                st.session_state.contact_name = ""
                st.session_state.contact_email = ""
                st.rerun()

        st.subheader("📋 Your Emergency Contacts")
        contacts = db.reference(f"emergency_contacts/{user_id}").get()
        if contacts:
            for c in contacts.values():
                st.write(f"👤 {c.get('name', '')} — ✉️ {c.get('email', '')}")
        else:
            st.info("No contacts added yet.")

    elif page == "🤝 My Friends":
        st.title("🤝 Connect with Friends")

        if "friend_email" not in st.session_state:
            st.session_state.friend_email = ""
        if "active_chat_friend" not in st.session_state:
            st.session_state.active_chat_friend = None
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        friend_email = st.text_input("Add Friend by Email", value=st.session_state.friend_email, key="friend_email_input")

        if st.button("Add Friend"):
            try:
                friend_user = auth.get_user_by_email(friend_email)
                friend_uid = friend_user.uid

                friends_ref = db.reference(f"friends/{user_id}")
                existing_friends = friends_ref.get() or {}

                already_added = any(f.get("email", "").lower() == friend_email.lower() for f in existing_friends.values())

                if already_added:
                    st.warning("⚠️ This friend is already added.")
                elif friend_uid == user_id:
                    st.warning("❌ You cannot add yourself.")
                else:
                    friends_ref.push({
                        "friend_uid": friend_uid,
                        "email": friend_email.strip()
                    })
                    st.success(f"✅ {friend_email} added as a friend.")
                    st.session_state.friend_email = ""
                    st.rerun()
            except Exception:
                st.error("❌ User not found.")

        st.subheader("👥 Your Friends")
        friends = db.reference(f"friends/{user_id}").get()
        friend_list = []
        if friends:
            for fkey, f in friends.items():
                friend_list.append((fkey, f.get('email', ''), f.get('friend_uid', '')))

            # Select friend to chat with
            selected = st.selectbox("Select a friend to chat", options=[f[1] for f in friend_list])
            selected_friend = next((f for f in friend_list if f[1] == selected), None)
            if selected_friend:
                st.session_state.active_chat_friend = selected_friend

                # Reference for reading messages with ordering
                chat_query_ref = db.reference(f"chats/{user_id}/{selected_friend[2]}").order_by_child("timestamp")
                messages = chat_query_ref.get() or {}
                st.session_state.chat_messages = sorted(messages.values(), key=lambda x: x.get("timestamp", ""))

                st.subheader(f"💬 Chat with {selected_friend[1]}")

                for msg in st.session_state.chat_messages:
                    sender = "You" if msg.get("sender") == user_id else selected_friend[1]
                    st.write(f"**{sender}:** {msg.get('text')}")

                # Input box to send message
                new_msg = st.text_area("Type your message:", height=80, key="friend_msg_input")
                if st.button("Send Message"):
                    if new_msg.strip() == "":
                        st.warning("Please enter a message.")
                    else:
                        timestamp = datetime.datetime.now().isoformat()
                        message_data = {
                            "sender": user_id,
                            "text": new_msg.strip(),
                            "timestamp": timestamp
                        }
                        # Reference for writing message (without order_by_child)
                        chat_write_ref = db.reference(f"chats/{user_id}/{selected_friend[2]}")
                        chat_write_ref.push(message_data)

                        # Also save message under friend's chat so they can see it
                        friend_chat_write_ref = db.reference(f"chats/{selected_friend[2]}/{user_id}")
                        friend_chat_write_ref.push(message_data)

                        st.rerun()
        else:
            st.info("No friends added yet.")
