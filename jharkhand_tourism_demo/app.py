import os
import requests
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from supabase import create_client, Client

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

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("index.html", user=session.get("user"))

@app.route("/itinerary")
def itinerary():
    response = supabase.table('places').select("*").execute()
    places = response.data
    return render_template("itinerary.html", places=places, user=session.get("user"))

@app.route("/marketplace")
def marketplace():
    response = supabase.table('products').select("*").execute()
    products = response.data
    return render_template("marketplace.html", products=products, user=session.get("user"))

@app.route("/arvr")
def arvr():
    return render_template("arvr.html", user=session.get("user"))

# Generic route for other simple pages
@app.route('/<string:page_name>')
def page(page_name):
    return render_template(page_name, user=session.get("user"))

# ---------- Feedback ----------
@app.route('/feedback', methods=['POST'])
def handle_feedback():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']
    
    feedback_data = {'name': name, 'email': email, 'message': message}
    supabase.table('feedback').insert(feedback_data).execute()
    
    return redirect(url_for('home'))

# ---------- Authentication ----------
@app.route("/register", methods=["POST"])
def register():
    email = request.form["email"]
    password = request.form["password"]

    response = supabase.auth.sign_up({"email": email, "password": password})

    if response.user:
        session["user"] = {"email": email}
        return redirect(url_for("home"))
    else:
        return jsonify({"error": str(response)})

@app.route("/signin", methods=["POST"])
def signin():
    email = request.form["email"]
    password = request.form["password"]

    response = supabase.auth.sign_in_with_password({"email": email, "password": password})

    if response.user:
        session["user"] = {"email": email}
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

    system_prompt = "You are a helpful and friendly assistant providing concise and accurate information about Jharkhand tourism. Answer in a single paragraph unless asked for a list."
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

if __name__ == "__main__":
    app.run(debug=True)
