# 🧠 MindMate - Your Mental Wellness Companion

MindMate is an AI-powered emotional support and journaling assistant designed to promote mental wellness through conversation, mood tracking, and self-reflection. Built with **Google Gemini**, **Firebase**, and **Streamlit**, this app helps users express their thoughts, detect emotions, and track their mental health over time.

---

## 🌟 Features

### 🔐 Login & Signup
- Secure user authentication using Firebase.
- New users can sign up, and existing users can log in to access personalized features.

### 💬 Intelligent Chatbot (Powered by Gemini)
- Chat with an empathetic AI that understands your emotional state.
- Responds to your mood using natural language understanding.
- Detects emotion in your message and tailors responses accordingly.

### 🧠 Emotion Detection
- The chatbot detects the user's emotional tone from input and stores it for mood tracking and analysis.

### 📊 Mood Tracker
- Automatically logs your emotional state from each chat.
- Visualizes emotional trends over time with charts.
- Helps recognize mood patterns and changes.

### 📘 Daily Journal
- Write freely and reflect on your thoughts.
- Gemini summarizes your entries in a supportive tone.
- Stores your journal privately in the cloud.

### 📂 My History
- View past journal entries and summaries.
- Browse mood logs with timestamps and emotion scores.
- Download full chat history as a PDF for offline reflection.

### 📄 Export Chat as PDF
- Users can download their entire chat history with the AI in a clean PDF format for offline access.

### ☁️ Firebase Realtime Database
- All user data — including moods, journals, and profiles — is securely stored and synced in real-time.

---

## 🧠 Why MindMate?

Mental health is often overlooked. MindMate serves as a **non-judgmental space** where users can talk, reflect, and track their emotional journey. By combining **AI empathy** and **personal data logging**, it offers a unique tool for mindfulness, mental clarity, and emotional growth.

---

## 🛠️ Technologies Used

| Tech        | Purpose                                     |
|-------------|---------------------------------------------|
| **Streamlit** | Frontend framework for rapid UI development |
| **Firebase Realtime DB** | Store user mood logs and journals securely |
| **Firebase Authentication** | For secure user sign-up and login |
| **Google Gemini (generativeai)** | Generate chat and summaries using LLM |
| **Google Cloud Run** | Deploy the app securely and scalably |
| **Matplotlib** | Visualize emotional trends   |
| **ReportLab** | To generate downloadable PDFs of chat history  |
| **Python** | Backend logic, data handling, integration     |

---

## 🔐 Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/mindmate.git
cd mindmate
```


### 2. In the .secrets.toml file, place all your required keys and credentials from your firebase account.

### 3. Install Dependencies
Make sure you have Python 3.9+ installed. Then run:
```bash
pip install -r requirements.txt
```

## 🚀 Deployment (Google Cloud Run)

### Step 1: Docker Build & Push
```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/mindmate
```

### Step 2: Deploy to Cloud Run
```bash
gcloud run deploy mindmate \
  --image gcr.io/YOUR_PROJECT_ID/mindmate \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=your_key,FIREBASE_DB_URL=https://your_project.firebaseio.com/
```

## 📁 Folder Structure
```bash
mindmate/
├── app.py                   # Main Streamlit app
├── requirements.txt         # Python dependencies
├── mindmate-XXXX.json       # Firebase service account credentials
├── .env                     # Local environment secrets (not committed)
└── .streamlit/
    └── config.toml          # Optional Streamlit settings
```

## 🙋‍♀️ Use Cases
* Students managing academic stress
* Professionals needing a digital emotional outlet
* Anyone seeking a non-judgmental, AI-powered listener
* People interested in journaling and self-reflection tools

## 🛡️ Disclaimer
MindMate is intended as a supportive, educational tool.
It is not a replacement for therapy or professional mental health care.
If you're in distress, please seek help from a qualified mental health provider.

## 🤝 Contributing
We welcome contributions! To contribute:

1. Fork this repository
2. Create a new branch (git checkout -b feature-name)
3. Make your changes
4. Commit and push (git push origin feature-name)
5. Open a pull request

## 📬 Contact
Created with ❤️ by Priya Verma.

🔗 GitHub: github.com/Priyadeara2427











