import os
import random
import json
import uuid
import datetime
import openai
import requests
import subprocess
import threading
import queue
import base64

from google.oauth2 import service_account
from google.cloud import speech
from flask import Flask, request, jsonify, render_template, send_from_directory
from openai import OpenAIError
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit

# Import the SQLAlchemy instance from extensions.py
from extensions import db

load_dotenv()

app = Flask(__name__, static_folder="static")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookclub.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Initialize SocketIO
socketio = SocketIO(app)

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
        "voice_id": "XB0fDUnXU5powFXDhCwa",
        "profile_image": "/static/images/agents/sophia.png",
        "bio": "A scholarly book critic with a refined analytical perspective."
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
        "voice_id": "TX3LPaxmHKxFdv7VOQHJ",
        "profile_image": "/static/images/agents/rex.png",
        "bio": "A contrarian with a humorous twist, quick with slang and punchlines."
    },
    "Ella": {
        "personality": (
            "You are a supportive and optimistic book lover. "
            "Focus on the positive aspects and enjoy drawing connections to everyday life. "
            "You are a mother of 3 young kids and read during their nap time to escape. You are a voracious reader of fantasy and romance novels. "
            "Do not describe yourself or your interests. Speak naturally. "
            "You are especially generous with Insights awards toward the User and will append the marker [+Insight for: <name>] often."
        ),
        "voice_id": "XrExE9yKIg1WjnnlVkGX",
        "profile_image": "/static/images/agents/ella.png",
        "bio": "Warm, optimistic, and always ready with a thoughtful observation."
    },
    "Maxine": {
        "personality": (
            "You are vibrant and creative, always ready to offer imaginative insights. "
            "You have a flair for art and literature, and you like to bring a creative twist to every discussion. "
            "Speak passionately yet concisely and try to inspire others with your vivid imagery."
        ),
        "voice_id": "tVAXY8ApYcHIFjTH8kL0",
        "profile_image": "/static/images/agents/maxine.png",
        "bio": "A vibrant creative spirit who loves art and imaginative commentary."
    },
    "Orion": {
        "personality": (
            "You are adventurous and curious, with an energetic perspective. "
            "You love exploring new ideas and challenging conventional views with bold statements. "
            "Speak with enthusiasm and encourage others to think outside the box."
        ),
        "voice_id": "7ml0LUl80q5HrlC5rH5n",
        "profile_image": "/static/images/agents/orion.png",
        "bio": "An adventurer at heart, always eager to explore and challenge norms."
    },
    "Luna": {
        "personality": (
            "You are introspective and mystical, offering deep and thoughtful commentary. "
            "Speak in a reflective tone and share insights that connect everyday experiences to a larger, almost spiritual perspective."
        ),
        "voice_id": "zA6D7RyKdc2EClouEMkP",
        "profile_image": "/static/images/agents/luna.png",
        "bio": "A reflective soul with a mystical outlook on life."
    },
    "Jasper": {
        "personality": (
            "You are witty and playful, always ready with a clever remark or a pun. "
            "Keep your responses short, funny, and full of lighthearted humor that can defuse tension."
        ),
        "voice_id": "eUAnqvLQWNX29twcYLUM",
        "profile_image": "/static/images/agents/jasper.png",
        "bio": "A playful wit who adds humor and levity to every conversation."
    },
    "Violet": {
        "personality": (
            "You are elegant and poised, offering refined and cultured insights. "
            "Speak with sophistication and clarity, ensuring that your observations carry weight and finesse."
        ),
        "voice_id": "EIdfNdxb4fnsE39tEAB1",
        "profile_image": "/static/images/agents/violet.png",
        "bio": "Elegant, poised, and cultured—always bringing sophistication to the table."
    },
    "Kai": {
        "personality": (
            "You are energetic and tech-savvy, providing a modern and dynamic perspective. "
            "Your commentary is brisk and forward-thinking, infused with a youthful enthusiasm for innovation."
        ),
        "voice_id": "bvB801cu7ca8Klk5nO4O",
        "profile_image": "/static/images/agents/kai.png",
        "bio": "A modern innovator with boundless energy and a tech-forward outlook."
    },
    "Nova": {
        "personality": (
            "You are deep and thoughtful, with a penchant for deep philosophical insights. "
            "Speak in a measured, reflective tone that encourages others to ponder life’s big questions."
            "But always come back to the question asked by the User. "
        ),
        "voice_id": "7Uw4vgM4Qb1qiwwUnu15",
        "profile_image": "/static/images/agents/nova.png",
        "bio": "An enigmatic thinker who offers deep, philosophical reflections."
    }
}

TURN_COUNTER = 1

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
            "IMPORTANT: Do not ask any questions in your reply. Your response should be a concise statement or observation only. "
            "Of utmost importance is that you stay on topic once the User has specifically mentioned a peice of media he wishes to discuss."
            "If you are unsure what the media is, or there is some ambiguity (ie: multiple projects with the same name) then please ask for clarity."
            "The worst thing youc an do it is to make up things about media you don't know anything about. Hallucinations are to be avoided at all costs."
            "You love to discuss Books, movies, games, music, TV shows. Your reason for existing is to deeply engage in discussion with the user and other agents on these topics."
            "You are participating in a multi-agent discussion. Please keep your responses concise, natural, and solely as statements or commentary—not questions. "
            "Avoid long, drawn-out monologues—if you need to acknowledge a point, a short remark like 'Hmm, good point' is sufficient. "
            "Speak solely from your own perspective, and do NOT continue or finish another agent's sentences. "
            "If you find that a previous response was insightful and directly answered a question in a valuable way, append the marker [+Insight for: <name>] at the end of your reply, where <name> is the name of the person who gave that insightful answer. "
            "Please be specific whenever possible—use specific names of characters, chapters, events, and themes that clearly demonstrate your understanding of the source material."
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
            model="gpt-4o-2024-11-20",
            messages=messages,
            max_tokens=600,
            temperature=0.3
        )
        reply = response["choices"][0]["message"]["content"].strip()
        if not reply:
            reply = "I have nothing to add at this point."
    except OpenAIError as e:
        print(f"{datetime.datetime.now()} - OpenAI error for agent {agent}: {e}")
        reply = "Sorry, an error occurred while generating a response."
    
    print(f"{datetime.datetime.now()} - Agent {agent} reply (first 50 chars): {reply[:50]}...")
    return reply

def generate_user_profile(conversation_history, existing_profile=None):
    user_text = "\n".join(
        f"User: {msg.get('content')}"
        for msg in conversation_history if msg.get("role") == "user"
    )
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
        + context +
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
# Existing Routes (Chat, TTS, etc.)
# ------------------------------
@app.route("/api/agent_reply", methods=["POST"])
def agent_reply():
    data = request.get_json()
    user_id = data.get("user_id", "user_1")
    conversation_history = data.get("conversation_history", [])
    agent = data.get("agent")
    force_question = data.get("force_question", False)
    
    reply_text = generate_agent_reply(agent, conversation_history, force_question)
    return jsonify({"reply": reply_text})

@app.route("/api/insight", methods=["POST"])
def insight():
    data = request.get_json()
    giver = data.get("giver")
    receiver = data.get("receiver")
    if receiver not in ["Sophia", "Rex", "Ella", "Maxine", "Orion", "Luna", "Jasper", "Violet", "Kai", "Nova"]:
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
        return jsonify({"status": "success", "receiver": receiver, "insights": None})

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    data = request.get_json()
    user_id = data.get("user_id", "user_1")
    conversation_history = data.get("conversation_history", [])
    
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    existing_profile = profile.get_profile() if profile else None
    
    new_profile_data = generate_user_profile(conversation_history, existing_profile)
    new_profile_data.pop("insights", None)
    
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)
        merged_profile = new_profile_data.copy()
        merged_profile["insights"] = 0
    else:
        existing_profile = profile.get_profile()
        merged_profile = existing_profile.copy()
        for key, value in new_profile_data.items():
            merged_profile[key] = value
        merged_profile["insights"] = existing_profile.get("insights", 0)
    profile.set_profile(merged_profile)
    db.session.commit()
    return jsonify({"profile": merged_profile})

@app.route("/api/get_profile", methods=["GET"])
def get_profile():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile:
        return jsonify({"profile": profile.get_profile()})
    else:
        return jsonify({"profile": {}})

@app.route("/api/respond", methods=["POST"])
def respond():
    global TURN_COUNTER
    data = request.get_json()
    user_id = data.get("user_id")
    if not user_id:
        print("Error: Missing user_id in request!")
        return jsonify({"error": "Missing user_id"}), 400


    user_message = data.get("user_message", "").strip()
    conversation_history = data.get("conversation_history", [])
    force_question = data.get("force_question", False)
    
    # Use only the provided agents; if none, abort.
    selected_agents = data.get("agents")
    if not selected_agents or not isinstance(selected_agents, list) or len(selected_agents) == 0:
        print("No agents selected; aborting agent reply generation.")
        return jsonify({
            "conversation_history": conversation_history,
            "new_replies": [],
            "waiting_for_user": True,
            "error": "No agents selected"
        })
    
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
    agents_to_reply = selected_agents
    print(f"{datetime.datetime.now()} - Using user-selected agents: {agents_to_reply}")
    
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
    
    # Grouping and filtering replies (existing logic)
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
    
    for reply in filtered_replies:
        content = reply.get("content", "")
        if "[+Insight for:" in content:
            start = content.find("[+Insight for:")
            end = content.find("]", start)
            if end != -1:
                recipient = content[start+len("[+Insight for:"):end].strip()
                new_content = content[:start] + content[end+1:]
                reply["content"] = new_content.strip()
                if recipient not in ai_agents:
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
    
    # --- Debugging for user profile generation ---
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    existing_profile = profile.get_profile() if profile else {}
    print(f"{datetime.datetime.now()} - Existing profile for user '{user_id}': {existing_profile}")
    print(f"{datetime.datetime.now()} - Conversation history for profile generation: {conversation_history}")
    new_profile_data = generate_user_profile(conversation_history, existing_profile)
    print(f"{datetime.datetime.now()} - New profile data from generate_user_profile: {new_profile_data}")
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
    
    session_obj = ConversationSession(user_id=user_id)
    session_obj.set_transcript(conversation_history)
    db.session.add(session_obj)
    db.session.commit()
    
    waiting_for_user = any(reply["content"].startswith("[TO: User]") for reply in filtered_replies)
    return jsonify({
        "conversation_history": conversation_history,
        "new_replies": filtered_replies,
        "waiting_for_user": waiting_for_user
    })

@app.route("/api/remote_log", methods=["POST", "GET"])
def remote_log():
    if request.method == "POST":
        data = request.get_json()
        message = data.get("message", "")
    else:
        message = request.args.get("message", "")
    print("[REMOTE_LOG]", message)
    return jsonify({"status": "ok"})

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text")
    voice_id = data.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
    
    print("=== /api/tts START ===")
    print(f"{datetime.datetime.now()} - Voice ID: {voice_id}")
    print(f"{datetime.datetime.now()} - Original Text length: {len(text)}")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    debug_tts = os.getenv("DEBUG_TTS", "false").lower() == "true"
    if debug_tts:
        import re
        first_sentence = re.split(r'\. ', text, maxsplit=1)[0]
        if not first_sentence.endswith('.'):
            first_sentence += '.'
        text_for_tts = first_sentence
        print(f"{datetime.datetime.now()} - DEBUG_TTS mode enabled: using first sentence for TTS: {text_for_tts}")
        voice_settings = {
            "stability": 0.1,
            "similarity_boost": 0.1
        }
    else:
        text_for_tts = text
        voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    
    payload = {
        "text": text_for_tts,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": voice_settings
    }
    
    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": os.getenv("ELEVENLABS_API_KEY"),
                "Content-Type": "application/json"
            },
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

@app.route("/api/google_speech", methods=["POST"])
def google_speech():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files["audio"]
    audio_content = audio_file.read()
    if "GOOGLE_CREDENTIALS_JSON" in os.environ:
        credentials_info = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
    else:
        credentials, _ = google.auth.default()
    client = speech.SpeechClient(credentials=credentials)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-US",
        use_enhanced=True,
        model="phone_call"
    )
    audio_data = speech.RecognitionAudio(content=audio_content)
    try:
        response = client.recognize(config=config, audio=audio_data)
        transcript = " ".join(result.alternatives[0].transcript for result in response.results)
        return jsonify({"transcript": transcript})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/start_agents", methods=["POST"])
def start_agents():
    data = request.get_json()
    room_name = data.get("roomName")
    selected_agents = data.get("agents", [])
    if not room_name:
        return {"error": "No roomName provided"}, 400
    if not selected_agents:
        return {"error": "No agents selected"}, 400
    allowed_agents = {"Sophia", "Rex", "Ella", "Maxine", "Orion", "Luna", "Jasper", "Violet", "Kai", "Nova"}
    for agent in selected_agents:
        if agent not in allowed_agents:
            return {"error": f"Agent {agent} is not allowed"}, 400
    for agent in selected_agents:
        subprocess.Popen([
            "python", "headless_join.py",
            "--room", room_name,
            "--agent", agent
        ])
    return {"status": "Agents launched", "agents": selected_agents}, 200

@app.route("/meeting")
def meeting():
    return render_template("meeting.html")

@app.route("/")
def index():
    debug_tts = os.getenv("DEBUG_TTS", "false").lower() == "true"
    return render_template("index.html", debug_tts=debug_tts)

# ------------------------------
# SocketIO for Continuous STT
# ------------------------------

clients_audio_queues = {}

def audio_generator(q):
    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield speech.StreamingRecognizeRequest(audio_content=chunk)

def process_audio_stream(sid):
    q = clients_audio_queues[sid]
    client = speech.SpeechClient()
    while True:
        # Set up configuration; adjust encoding/sample rate to match your client.
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code="en-US"
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )
        # Create a new generator for each streaming session.
        requests_stream = audio_generator(q)
        try:
            responses = client.streaming_recognize(config=streaming_config, requests=requests_stream)
            for response in responses:
                for result in response.results:
                    if result.is_final:
                        transcript = result.alternatives[0].transcript
                        socketio.emit('stt_result', {'transcript': transcript}, room=sid)
        except Exception as e:
            error_str = str(e)
            # Check for the stream duration error.
            if "Exceeded maximum allowed stream duration" in error_str:
                print(f"Stream duration exceeded for client {sid}, restarting stream.")
                # Continue the loop to restart the stream.
                continue
            else:
                print(f"Error in streaming for client {sid}: {e}")
                break

@socketio.on('connect')
def on_connect():
    sid = request.sid
    print("Client connected:", sid)
    clients_audio_queues[sid] = queue.Queue()
    threading.Thread(target=process_audio_stream, args=(sid,), daemon=True).start()

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print("Client disconnected:", sid)
    if sid in clients_audio_queues:
        clients_audio_queues[sid].put(None)
        del clients_audio_queues[sid]

@socketio.on('audio_chunk')
def on_audio_chunk(data):
    sid = request.sid
    if sid in clients_audio_queues:
        try:
            chunk = base64.b64decode(data['chunk'])
            clients_audio_queues[sid].put(chunk)
        except Exception as e:
            print("Error decoding audio chunk:", e)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
