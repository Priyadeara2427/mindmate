# for running the streamit on local
# press ctrl + shift + P, choose venv
# streamlit run app.py

# for buiding and deploying
# gcloud builds submit --tag gcr.io/mindmate-301d7/mindmate
# gcloud run deploy mindmate --image gcr.io/mindmate-301d7/mindmate --platform managed --region asia-south1 --allow-unauthenticated


import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth, db
import os
import google.generativeai as genai
import matplotlib.pyplot as plt
from collections import Counter
import streamlit as st
import datetime
from streamlit_autorefresh import st_autorefresh
import datetime
import requests
import json
import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet

import base64
import hashlib
from cryptography.fernet import Fernet

def get_chat_key(uid1, uid2):
    # Combine UIDs in a consistent order
    sorted_uids = "".join(sorted([uid1, uid2]))
    # SHA256 hash to 32 bytes
    key_hash = hashlib.sha256(sorted_uids.encode()).digest()
    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(key_hash)


# === Email Sender ===
def send_alert_email(to_email, user_email, moods):
    from_email = "pv328360@gmail.com"  # your Gmail
    app_password = "zdak sobx bnrr pygk"   # generate from Google > Security > App passwords

    subject = "🚨 MindMate Emergency Alert"
    body = (
        f"Hello,\n\n"
        f"This is an automatic alert from MindMate.\n\n"
        f"User {user_email} has logged 4 consecutive low moods:\n{moods}\n\n"
        f"Please reach out to them immediately.\n\n"
        f"Stay safe,\nMindMate Team"
    )

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Email sending failed: {e}")
        return False


# ===== INITIALIZATION =====
if 'user' not in st.session_state:
    st.session_state.update({
        'user': None,
        'demo_mode': False,
        'chat_history': [],
        'mood_log': []
    })
    
    # Check for demo mode
    if st.query_params.get("demo") == "gdg2025":
        st.session_state.update({
            'user': {"email": "demo@mindmate.com", "uid": "demo_user"},
            'demo_mode': True
        })

st.set_page_config(page_title="🧠 MindMate")

# ===== FIREBASE SETUP =====
if not firebase_admin._apps:
    cred = credentials.Certificate("mindmate-301d7-be0088c3286c.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://mindmate-301d7-default-rtdb.firebaseio.com/'
    })

# ===== GEMINI SETUP =====
genai.configure(api_key=st.secrets["google_api_key"])
model = genai.GenerativeModel('gemini-1.5-pro')

# ===== AUTHENTICATION FLOW =====
if not st.session_state.user:
    # Login/Signup Page
    st.title("🔐 Welcome to MindMate")
    
    with st.container():
        mode = st.selectbox("Choose:", ["Login", "Signup"])
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        if mode == "Signup":
            confirm_password = st.text_input("Confirm Password", type="password")
            if st.button("Create Account"):
                if password == confirm_password:
                    try:
                        user_record = auth.create_user(email=email, password=password)
                        st.session_state.user = {
                            "email": user_record.email, 
                            "uid": user_record.uid
                        }
                        st.success("Account created! Please login.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Signup error: {e}")
                else:
                    st.error("Passwords don't match")
        else:
            if st.button("Login"):
                try:
                    user_record = auth.get_user_by_email(email)
                    st.session_state.user = {
                        "email": user_record.email, 
                        "uid": user_record.uid
                    }
                    st.success("Login successful!")
                    st.rerun()
                except auth.UserNotFoundError:
                    st.error("Email not registered")
                except Exception as e:
                    st.error(f"Login failed: {e}")

else:
    # ===== MAIN APPLICATION =====
    st.success(f"👋 Logged in as: {st.session_state.user['email']}")
    if st.session_state.demo_mode:
        st.warning("🧪 Demo Mode Active")
    
    user_id = st.session_state.user['uid']
    
    if st.button("Logout"):
        st.session_state.user = None
        st.session_state.chat_history = []
        st.session_state.mood_log = []
        st.rerun()

    # ===== SIDEBAR NAVIGATION =====
    st.sidebar.title("🧭 Navigate")
    page = st.sidebar.radio("Go to", [
        "💬 Chatbot", 
        "📊 Mood Tracker", 
        "📘 Journal", 
        "📂 My History", 
        "📞 Emergency Setup", 
        "🤝 My Friends"
    ])


    # ===== CHATBOT PAGE =====
    if page == "💬 Chatbot":
        st.title("💬 MindMate Gemini Chatbot")

        # Clear input before creating widget if flagged
        if "chat_input_clear" not in st.session_state or st.session_state.get("chat_input_clear"):
            st.session_state.chat_input = ""
            st.session_state.chat_input_clear = False

        # Chat input
        user_input = st.text_area("What's on your mind?", height=100, key="chat_input")
        submit = st.button("Ask")

        if submit and user_input.strip():
            # Emotion Detection
            emotion_prompt = f"""Classify this text into one of: ["happy", "sad", "angry", "anxious", "calm", "neutral", "excited", "bored", "frustrated"]\n\nText: "{user_input}"\n\nRespond ONLY with valid JSON: {{ "emotion": "<category>", "score": <0-1> }}"""
            
            try:
                response = model.generate_content(emotion_prompt)
                clean_json = re.sub(r"^```(?:json)?|```$", "", response.text).strip()
                parsed = json.loads(clean_json)
                predicted_emotion = parsed.get("emotion", "neutral").lower()
                emotion_score = parsed.get("score", 0.0)
            except Exception as e:
                predicted_emotion = "neutral"
                emotion_score = 0.0

            st.info(f"🧠 Detected Emotion: {predicted_emotion}")

            # Get motivational message
            try:
                reinforcement = model.generate_content(
                    f"Give a brief supportive message for someone feeling {predicted_emotion}"
                ).text
                st.success(f"💡 MindMate Tip: {reinforcement}")
            except Exception:
                st.success("💡 MindMate Tip: You're doing great! Keep going.")

            # Store mood
            st.session_state.mood_log.append(predicted_emotion)
            if len(st.session_state.mood_log) > 10:
                st.session_state.mood_log.pop(0)

            # Check for 4 consecutive low moods
            low_moods = {"sad", "anxious", "frustrated", "angry", "bored"}
            if len(st.session_state.mood_log) >= 4:
                last_four = st.session_state.mood_log[-4:]
                if all(m in low_moods for m in last_four):
                    contacts = db.reference(f"emergency_contacts/{user_id}").get()
                    if contacts:
                        for c in contacts.values():
                            contact_email = c.get("email", "")
                            if contact_email:
                                if send_alert_email(contact_email, st.session_state.user["email"], last_four):
                                    st.warning(f"🚨 Alert sent to {contact_email}")

            # Save mood in Firebase (if not demo)
            if not st.session_state.demo_mode:
                db.reference(f"moods/{st.session_state.user['uid']}").push({
                    "mood": predicted_emotion,
                    "score": emotion_score,
                    "timestamp": datetime.datetime.now().isoformat()
                })

            # Generate chatbot response
            chat = model.start_chat(history=[])
            response = chat.send_message(
                f"The user is feeling {predicted_emotion}. Respond with empathy to: {user_input}",
                stream=True
            )
            full_response = "".join([chunk.text for chunk in response])

            # Update chat history
            st.session_state.chat_history.append(("You", user_input))
            st.session_state.chat_history.append(("MindMate", full_response))

            # Show chatbot response
            st.subheader("🧠 Gemini Responds:")
            st.write(full_response)

            # Clear input for next message
            st.session_state.chat_input_clear = True
            st.rerun()

        # Display chat history
        st.subheader("🗒️ Chat History")
        for role, text in st.session_state.chat_history:
            st.write(f"**{role}:** {text}")

        # PDF export
        if st.button("📥 Download Chat History as PDF"):
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            text_obj = c.beginText(40, 750)
            text_obj.setFont("Helvetica", 11)
            text_obj.textLine("MindMate Chat History")
            text_obj.textLine("-"*40)
            for role, message in st.session_state.chat_history:
                text_obj.textLine(f"{role}: {message}")
                text_obj.textLine("")
            c.drawText(text_obj)
            c.showPage()
            c.save()
            buffer.seek(0)
            st.download_button(
                "📄 Download PDF", 
                buffer, 
                "mindmate_chat.pdf", 
                "application/pdf"
            )


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

        # Add Friend
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
                    st.experimental_rerun()
            except Exception:
                st.error("❌ User not found.")

        # Encryption helpers
        def get_fernet(uid1, uid2):
            key = get_chat_key(uid1, uid2)
            return Fernet(key)

        def push_message(sender_id, receiver_id, text):
            fernet = get_fernet(sender_id, receiver_id)
            encrypted_text = fernet.encrypt(text.encode()).decode()
            timestamp = datetime.datetime.now().isoformat()
            msg_data = {"sender": sender_id, "text": encrypted_text, "timestamp": timestamp}

            # Push encrypted message for both users
            for ref in [f"chats/{sender_id}/{receiver_id}", f"chats/{receiver_id}/{sender_id}"]:
                db.reference(ref).push(msg_data)

                # Keep only last 10 messages
                messages = db.reference(ref).order_by_child("timestamp").get() or {}
                if len(messages) > 10:
                    keys_to_delete = list(messages.keys())[:-10]
                    for k in keys_to_delete:
                        db.reference(f"{ref}/{k}").delete()

        def fetch_messages(user_id, friend_id):
            fernet = get_fernet(user_id, friend_id)
            chat_ref = db.reference(f"chats/{user_id}/{friend_id}").order_by_child("timestamp")
            messages = chat_ref.get() or {}
            decrypted = []
            for m in messages.values():
                try:
                    text = fernet.decrypt(m.get("text").encode()).decode()
                except:
                    text = "[Decryption error]"
                decrypted.append({"sender": m.get("sender"), "text": text, "timestamp": m.get("timestamp")})
            return sorted(decrypted, key=lambda x: x["timestamp"])

        # Show Friends & Select
        st.subheader("👥 Your Friends")
        friends = db.reference(f"friends/{user_id}").get()
        friend_list = []
        if friends:
            for fkey, f in friends.items():
                friend_list.append((fkey, f.get('email', ''), f.get('friend_uid', '')))

            selected = st.selectbox("Select a friend to chat", options=[f[1] for f in friend_list])
            selected_friend = next((f for f in friend_list if f[1] == selected), None)
            if selected_friend:
                friend_uid = selected_friend[2]

                # Auto-refresh chat every 3 sec
                st_autorefresh(interval=3000, limit=None, key="chat_refresh")

                # Fetch decrypted messages
                st.session_state.chat_messages = fetch_messages(user_id, friend_uid)

                st.subheader(f"💬 Chat with {selected_friend[1]}")
                for msg in st.session_state.chat_messages:
                    sender = "You" if msg["sender"] == user_id else selected_friend[1]
                    st.write(f"**{sender}:** {msg['text']}")

                # Input box
                # Clear input before creating widget if flagged
                if "friend_msg_input" not in st.session_state or st.session_state.get("clear_input"):
                    st.session_state.friend_msg_input = ""
                    st.session_state.clear_input = False

                friend_msg_input = st.text_input("Message", key="friend_msg_input")

                if st.button("Send Message"):
                    if friend_msg_input.strip() == "":
                        st.warning("Please enter a message.")
                    else:
                        push_message(user_id, friend_uid, friend_msg_input.strip())
                        st.success("✅ Message Sent!")
                        st.session_state.clear_input = True  # triggers clearing on next rerun
                        st.rerun()


        else:
            st.info("No friends added yet.")
