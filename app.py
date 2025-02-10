import os
import random
import json
import uuid
import datetime
import openai
import requests
from google.cloud import speech

from flask import Flask, request, jsonify, render_template
from openai import OpenAIError
from dotenv import load_dotenv

# Import the SQLAlchemy instance from extensions.py
from extensions import db

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookclub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the SQLAlchemy instance with the Flask app.
db.init_app(app)

# Import your models (they will import the same 'db' from extensions.py).
from models import ConversationSession, UserProfile

# ------------------------------
# OpenAI API setup and definitions
# ------------------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

ai_agents = {
    "Sophia": {
        "personality": (
            "You are a scholarly and analytical book critic. "
            "Speak in a formal tone, offering detailed analysis of the book's themes and literary techniques. "
            "Do not mention that you are a book critic. "
            "Do not refer to what other people think of the book. Frame all of your arguments from your own point of view and your own interpretation. "
            "Do not describe yourself or your interests. Speak naturally. "
            "Do not monologue. This is a conversation. Be smart and articulate, but do not dominate the conversation with long drawn-out responses unless asked to by the user. "
            "Never start your responses with 'As a Book Critic'."
        ),
        "voice_id": "XB0fDUnXU5powFXDhCwa"
    },
    "Rex": {
        "personality": (
            "You are contrarian and humorous. "
            "Challenge popular opinions and add a dash of humor in your commentary. "
            "You prefer graphic novels and sports magazines to long, complex books. "
            "Speak in short, simple sentences using slang. "
            "Do not have a large vocabulary. Do not describe yourself or your interests. Speak naturally. "
            "Never start your responses with 'Yo Rex here'."
        ),
        "voice_id": "TX3LPaxmHKxFdv7VOQHJ"
    },
    "Ella": {
        "personality": (
            "You are a supportive and optimistic book lover. "
            "Focus on the positive aspects and enjoy drawing connections to everyday life. "
            "You are a mother of 3 young kids and read during their nap time to escape. You are a voracious reader of fantasy and romance novels. "
            "Do not describe yourself or your interests. Speak naturally. "
            "You are especially generous with Insights awards toward the User and will append the marker `[+Insight for: <name>]` often."
        ),
        "voice_id": "XrExE9yKIg1WjnnlVkGX"
    }
}

# ------------------------------
# Global turn counter for debugging
# ------------------------------
TURN_COUNTER = 1

# ------------------------------
# Helper Functions
# ------------------------------
def parse_addressed_agents(user_message, possible_agents):
    lowered = user_message.lower()
    found = []
    for agent in possible_agents:
        index = lowered.find(agent.lower())
        if index != -1:
            found.append((agent, index))
    found.sort(key=lambda x: x[1])
    return [agent for agent, idx in found]

def conversation_manager(query, all_agents=["Sophia", "Rex", "Ella"]):
    addressed = parse_addressed_agents(query, all_agents) if query else []
    final_order = addressed + [agent for agent in all_agents if agent not in addressed]
    print(f"{datetime.datetime.now()} - conversation_manager: Final agent order: {final_order}")
    return final_order

def generate_agent_reply(agent, conversation_history, force_question=False):
    personality_prompt = ai_agents.get(agent, {}).get("personality", "")
    if force_question:
        refined_instructions = (
            "Your response should be a brief, on-theme question to stimulate conversation. "
            "It should be concise and only ask a question without extra commentary."
        )
    else:
        refined_instructions = (
            "You are participating in a multi-agent discussion. Please keep your responses concise and natural. "
            "Avoid long, drawn-out monologues—if you need to acknowledge a point, a short remark like 'Hmm, good point' is sufficient. "
            "Ask questions very sparingly; if you do, keep them brief and direct. "
            "Speak solely from your own perspective, and do NOT continue or finish another agent's sentences. "
            "You did your homework. If the topic is a book - you read it. If it's a movie - you watched it. If it's a game, you played it. "
            "If you find that a previous response was insightful and directly answered a question in a valuable way, append the marker `[+Insight for: <name>]` at the end of your reply, where `<name>` is the name of the person who gave that insightful answer. Include this marker only when you are certain the response merits a +1. "
            "Please be specific whenever possible - use specific names of characters, chapters, events and themes that clearly demonstrate your understanding of the source material. "
            "Do not rephrase a question already asked by another Agent or User. "
        )
        if random.random() < 0.1:
            refined_instructions += "\nAdditionally, if appropriate, ask a brief follow-up question directed at another participant or the user."
    system_prompt = f"You are {agent}. {personality_prompt}\n\n" + refined_instructions
    system_message = {"role": "system", "content": system_prompt}
    
    conversation_text = "\n".join(
        f"{msg.get('role')}{(' (' + msg.get('name') + ')') if msg.get('name') else ''}: {msg.get('content')}"
        for msg in conversation_history
    )
    history_message = {
        "role": "system",
        "content": "Here is the conversation so far:\n\n" + conversation_text + "\n\nPlease respond as yourself only."
    }
    
    messages = [system_message, history_message]
    
    print(f"{datetime.datetime.now()} - Generating reply for agent {agent}. Conversation excerpt (last 2 messages): {conversation_history[-2:]}")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        reply = response["choices"][0]["message"]["content"].strip()
        if not reply:
            reply = "I have nothing to add at this point."
    except OpenAIError as e:
        print(f"{datetime.datetime.now()} - OpenAI error for agent {agent}: {e}")
        reply = "Sorry, an error occurred while generating a response."
    
    print(f"{datetime.datetime.now()} - Agent {agent} reply (first 50 chars): {reply[:50]}...")
    return reply

@app.route("/api/agent_reply", methods=["POST"])
def agent_reply():
    """
    Generate a reply for a single agent based on the current conversation history.
    This endpoint enables sequential agent responses so that each agent's reply
    is generated after the conversation history has been updated with previous replies.
    """
    data = request.get_json()
    user_id = data.get("user_id", "user_1")
    conversation_history = data.get("conversation_history", [])
    agent = data.get("agent")
    force_question = data.get("force_question", False)
    
    reply_text = generate_agent_reply(agent, conversation_history, force_question)
    return jsonify({"reply": reply_text})

def generate_user_profile(conversation_history, existing_profile=None):
    """
    Generate an updated user profile by considering both the new user messages
    from the conversation_history and any existing profile data (if provided).
    """
    # Extract only the user messages.
    user_text = "\n".join(
        f"User: {msg.get('content')}"
        for msg in conversation_history if msg.get("role") == "user"
    )
    
    # If an existing profile is provided, include it as context.
    context = ""
    if existing_profile:
        context = "Existing profile context: " + json.dumps(existing_profile) + "\n\n"
    
    prompt = (
        "You are an assistant that updates a user's profile. "
        "The user profile is a JSON object with exactly the following keys: "
        "'favorite_genres', 'discussion_style', 'notable_opinions', 'engagement_level', "
        "'favorite_characters', 'favorite_authors', 'approximate_age', "
        "'approximate_education_level', 'approximate_sex', "
        "'approximate_social_economic_status', and 'approximate_political_affiliation'. "
        "Use the following context from the existing profile (if any) and the new user messages to generate an updated profile. "
        "Return only valid JSON with these keys and no additional commentary.\n\n"
        f"{context}"
        "New user messages:\n" + user_text +
        "\n\nJSON:"
    )
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=300,
            temperature=0.5
        )
        profile_text = response["choices"][0]["message"]["content"].strip()
        profile_dict = json.loads(profile_text)
        return profile_dict
    except Exception as e:
        print("Error generating user profile:", e)
        return {}

# ------------------------------
# Routes
# ------------------------------
@app.route("/api/insight", methods=["POST"])
def insight():
    data = request.get_json()
    giver = data.get("giver")
    receiver = data.get("receiver")
    # If the receiver is not an agent, update their insight count.
    if receiver not in ["Sophia", "Rex", "Ella"]:
        profile = UserProfile.query.filter_by(user_id=receiver).first()
        if profile:
            profile_data = profile.get_profile()
            insights = profile_data.get("insights", 0)
            insights += 1
            profile_data["insights"] = insights
            profile.set_profile(profile_data)
            db.session.commit()
            return jsonify({"status": "success", "receiver": receiver, "insights": insights})
        else:
            return jsonify({"status": "error", "message": "User not found"}), 404
    else:
        # For agents, just return success.
        return jsonify({"status": "success", "receiver": receiver, "insights": None})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    data = request.get_json()
    user_id = data.get("user_id", "user_1")
    conversation_history = data.get("conversation_history", [])
    
    # Get any existing profile for context.
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    existing_profile = profile.get_profile() if profile else None
    
    new_profile_data = generate_user_profile(conversation_history, existing_profile)
    # Remove insights from generated data (if any)
    new_profile_data.pop("insights", None)
    
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)
        merged_profile = new_profile_data.copy()
        merged_profile["insights"] = 0
    else:
        existing_profile = profile.get_profile()
        merged_profile = existing_profile.copy()
        # Update only keys from new_profile_data, leaving insights intact.
        for key, value in new_profile_data.items():
            merged_profile[key] = value
        # Ensure insights remains the same.
        merged_profile["insights"] = existing_profile.get("insights", 0)
    profile.set_profile(merged_profile)
    db.session.commit()
    return jsonify({"profile": merged_profile})

@app.route("/api/get_profile", methods=["GET"])
def get_profile():
    user_id = request.args.get("user_id", "user_1")
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile:
        return jsonify({"profile": profile.get_profile()})
    else:
        return jsonify({"profile": {}})

@app.route("/api/respond", methods=["POST"])
def respond():
    global TURN_COUNTER
    data = request.get_json()
    user_id = data.get("user_id", "user_1")
    user_message = data.get("user_message", "").strip()
    conversation_history = data.get("conversation_history", [])
    
    # Read force_question flag.
    force_question = data.get("force_question", False)
    
    print("=== /api/respond START ===")
    print(f"{datetime.datetime.now()} - User ID: {user_id}")
    print(f"{datetime.datetime.now()} - User Message: '{user_message}'")
    print(f"{datetime.datetime.now()} - Initial History Length: {len(conversation_history)}")
    
    if user_message:
        conversation_history.append({"role": "user", "content": user_message})
    else:
        if not force_question:
            print("Empty user message received; not generating new agent replies.")
            return jsonify({
                "conversation_history": conversation_history,
                "new_replies": [],
                "waiting_for_user": True
            })
    
    base_context = conversation_history.copy()
    
    if force_question:
        agents_to_reply = [random.choice(["Sophia", "Rex", "Ella"])]
        print("Force question enabled. Random agent selected:", agents_to_reply)
    else:
        agents_to_reply = conversation_manager(user_message)
    
    new_replies = []
    for agent in agents_to_reply:
        reply_text = generate_agent_reply(agent, base_context, force_question=force_question)
        reply_message = {
            "role": "assistant",
            "name": agent,
            "content": reply_text,
            "turn_id": TURN_COUNTER
        }
        TURN_COUNTER += 1
        new_replies.append(reply_message)
        print(f"{datetime.datetime.now()} - Generated {agent} reply (turn {reply_message['turn_id']}): {reply_text[:50]}...")
    
    conversation_history.extend(new_replies)
    
    print(f"{datetime.datetime.now()} - Raw Agent Replies:")
    for reply in new_replies:
        print(f"  Agent {reply.get('name')} (turn {reply.get('turn_id')}): {reply.get('content')[:50]}...")
    
    grouped_replies = {}
    for reply in new_replies:
        agent = reply.get("name")
        if agent in grouped_replies:
            current = grouped_replies[agent]
            if current["content"].startswith("[TO:") and not reply["content"].startswith("[TO:"):
                grouped_replies[agent] = reply
        else:
            grouped_replies[agent] = reply
    
    print(f"{datetime.datetime.now()} - Grouped Replies:", {k: v.get('content')[:50] for k, v in grouped_replies.items()})
    
    filtered_replies = []
    for reply in grouped_replies.values():
        content = reply["content"]
        if content.startswith("[TO:"):
            if content.startswith("[TO: User]"):
                filtered_replies.append(reply)
            else:
                end_marker = content.find("] ")
                if end_marker != -1:
                    new_content = content[end_marker+2:]
                    reply["content"] = new_content
                filtered_replies.append(reply)
        else:
            filtered_replies.append(reply)
    
    # Check for insight markers in each reply.
    for reply in filtered_replies:
        content = reply.get("content", "")
        if "[+Insight for:" in content:
            start = content.find("[+Insight for:")
            end = content.find("]", start)
            if end != -1:
                recipient = content[start+len("[+Insight for:"):end].strip()
                new_content = content[:start] + content[end+1:]
                reply["content"] = new_content.strip()
                if recipient not in ["Sophia", "Rex", "Ella"]:
                    profile = UserProfile.query.filter_by(user_id=recipient).first()
                    if profile:
                        profile_data = profile.get_profile()
                        insights = profile_data.get("insights", 0)
                        insights += 1
                        profile_data["insights"] = insights
                        profile.set_profile(profile_data)
                        db.session.commit()
    
    print(f"{datetime.datetime.now()} - Filtered Replies:", [f"{r.get('name')} (turn {r.get('turn_id')}): {r.get('content')[:50]}..." for r in filtered_replies])
    print(f"{datetime.datetime.now()} - Final History Length: {len(conversation_history)}")
    if conversation_history:
        print(f"{datetime.datetime.now()} - Last two messages: {conversation_history[-2:]}")
    print("=== /api/respond END ===")
    
    # Update the user's profile in real time without overwriting existing insights.
    from models import UserProfile
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    existing_profile = profile.get_profile() if profile else {}
    new_profile_data = generate_user_profile(conversation_history, existing_profile)
    new_profile_data.pop("insights", None)
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)
        merged_profile = new_profile_data.copy()
        merged_profile["insights"] = 0
    else:
        merged_profile = existing_profile.copy()
        for key, value in new_profile_data.items():
            merged_profile[key] = value
        merged_profile["insights"] = existing_profile.get("insights", 0)
    profile.set_profile(merged_profile)
    db.session.commit()
    
    session = ConversationSession(user_id=user_id)
    session.set_transcript(conversation_history)
    db.session.add(session)
    db.session.commit()
    
    waiting_for_user = any(reply["content"].startswith("[TO: User]") for reply in filtered_replies)
    return jsonify({
        "conversation_history": conversation_history,
        "new_replies": filtered_replies,
        "waiting_for_user": waiting_for_user
    })

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text")
    voice_id = data.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
    
    print("=== /api/tts START ===")
    print(f"{datetime.datetime.now()} - Voice ID: {voice_id}")
    print(f"{datetime.datetime.now()} - Text length: {len(text)}")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    headers = {
        "xi-api-key": os.getenv("ELEVENLABS_API_KEY"),
        "Content-Type": "application/json"
    }
    
    voice_settings = {
        "stability": 0.5,
        "similarity_boost": 0.75
    }
    
    if os.getenv("DEBUG_TTS", "false").lower() == "true":
        voice_settings = {
            "stability": 0.1,
            "similarity_boost": 0.1
        }
        print("DEBUG_TTS mode enabled: using lower quality voice parameters.")
    
    payload = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": voice_settings
    }
    
    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers=headers,
            json=payload
        )
        if response.status_code != 200:
            print(f"{datetime.datetime.now()} - TTS API error: {response.status_code} {response.text}")
            return jsonify({"error": "ElevenLabs TTS error", "details": response.text}), response.status_code
        print(f"{datetime.datetime.now()} - TTS API call succeeded, response size: {len(response.content)}")
        print("=== /api/tts END ===")
        return response.content, 200, {"Content-Type": "audio/mpeg"}
    except Exception as e:
        print(f"{datetime.datetime.now()} - TTS Exception: {e}")
        return jsonify({"error": str(e)}), 500

from google.cloud import speech

@app.route("/api/google_speech", methods=["POST"])
def google_speech():
    # Ensure an audio file was provided.
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files["audio"]
    audio_content = audio_file.read()

    # Instantiate a client.
    client = speech.SpeechClient()

    # Configure recognition parameters to match your audio file.
    # Here we assume the MediaRecorder produces WEBM_OPUS audio at 48000 Hz.
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-US",
        use_enhanced=True,
        model="phone_call"  # You can change this model as needed.
    )
    audio_data = speech.RecognitionAudio(content=audio_content)

    try:
        response = client.recognize(config=config, audio=audio_data)
        transcript = " ".join(result.alternatives[0].transcript for result in response.results)
        return jsonify({"transcript": transcript})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
