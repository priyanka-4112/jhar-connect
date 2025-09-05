import os
import requests
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from supabase import create_client, Client
from textblob import TextBlob

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change in production

# --- Load Environment Variables ---
load_dotenv()
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

# --- Initialize Services ---
api_endpoint = "https://openrouter.ai/api/v1/chat/completions"
supabase: Client = create_client(supabase_url, supabase_key)

# ---------- Core Routes ----------
@app.route("/")
def home():
    return render_template("index.html", user=session.get("user"))

@app.route("/itinerary")
def itinerary():
    return render_template("itinerary.html", user=session.get("user"))

@app.route("/marketplace")
def marketplace():
    response = supabase.table('products').select("*").execute()
    products = response.data
    return render_template("marketplace.html", products=products, user=session.get("user"))

@app.route("/arvr")
def arvr():
    return render_template("arvr.html", user=session.get("user"))

# ---------- Feedback ----------
@app.route('/feedback', methods=['GET'])
def feedback_page():
    return render_template('feedback.html')

@app.route('/handle-feedback', methods=['POST'])
def handle_feedback():
    name = request.form['name']
    email = request.form['email']
    message = request.form['user_feed']
    
    blob = TextBlob(message)
    sentiment_score = blob.sentiment.polarity
    
    feedback_data = {
        'user_name': name, 
        'email': email, 
        'user_feed': message, 
        'sentiment': sentiment_score 
    }
    supabase.table('feedback1').insert(feedback_data).execute()
    
    return redirect(url_for('home'))

# ---------- Authentication ----------
@app.route("/signin", methods=["POST"])
def signin():
    email = request.form["email"]
    password = request.form["password"]

    response = supabase.auth.sign_in_with_password({"email": email, "password": password})

    if response.user:
        user_id = response.user.id
        print("Signed in user_id:", user_id)

        try:
            profile_response = supabase.table("profiles").select("id, role").eq("id", user_id).single().execute()
            print("Profile Response raw:", profile_response)

            if profile_response.data:
                user_role = profile_response.data.get("role", "user")
            else:
                print("No profile row found for user_id:", user_id)
                user_role = "user"
        except Exception as e:
            print("Error fetching profile:", e)
            user_role = "user"

        print("Final resolved role:", user_role)
        session["user"] = {"email": email, "role": user_role}

        if user_role == "admin":
            return redirect(url_for("dashboard"))
        else:
            return redirect(url_for("home"))
    else:
        return jsonify({"error": "Invalid credentials"})

@app.route("/logout")
def logout():
    supabase.auth.sign_out()
    session.pop("user", None)
    return redirect(url_for("home"))

# ---------- AI Chatbot API ----------
@app.route("/chat", methods=["POST"])
def chat():
    user_query = request.json.get('message')

    if not user_query:
        return jsonify({"error": "Message cannot be empty"}), 400

    system_prompt = """
You are a tour guide chatbot for Jharkhand, India.
Your main rule is to always give short, simple, and direct answers. Be brief.
YOUR RULES:
1. IF the user says 'hi' or 'hello', ONLY reply with a short greeting and ask how you can help. NOTHING ELSE.
2. IF the user asks for 'places', 'attractions', or 'things to do', you MUST reply with a simple heading and a bulleted list. DO NOT use long paragraphs.
3. IF the user asks about anything unrelated to Jharkhand tourism (especially illegal or unethical topics), politely refuse.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": messages
    }
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(api_endpoint, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        
        response_data = response.json()
        model_reply = response_data['choices'][0]['message']['content']
        
        return jsonify({"response": model_reply})

    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return jsonify({"error": "Failed to connect to the chatbot service."}), 500

# ---------- Dashboard Route ----------

@app.route("/dashboard")
def dashboard():
    # fetch sentiments from Supabase
    response = supabase.table('feedback1').select('sentiment').execute()
    feedback_data = response.data

    sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
    for item in feedback_data:
        score = item.get('sentiment')
        if score is not None:
            if score > 0.1:
                sentiments['positive'] += 1
            elif score < -0.1:
                sentiments['negative'] += 1
            else:
                sentiments['neutral'] += 1

    return render_template("dashboard.html", user=session.get("user"), sentiment_data=sentiments)


# ---------- Catch-all Route (SAFE) ----------
@app.route('/<string:page_name>')
def page(page_name):
    # Only render valid html templates
    if not page_name.endswith(".html"):
        return redirect(url_for("home"))
    return render_template(page_name, user=session.get("user"))

if __name__ == "__main__":
    app.run(debug=True)
