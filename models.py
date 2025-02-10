from extensions import db
from datetime import datetime
import json

class ConversationSession(db.Model):
    __tablename__ = "conversation_session"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100))  # optional if you plan to track different users
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    transcript = db.Column(db.Text)  # Store the conversation as JSON text

    def __repr__(self):
        return f"<Session {self.id}>"

    def set_transcript(self, conversation_history):
        self.transcript = json.dumps(conversation_history)

    def get_transcript(self):
        return json.loads(self.transcript) if self.transcript else []

class UserProfile(db.Model):
    __tablename__ = "user_profile"  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), unique=True)  # One profile per user
    profile_data = db.Column(db.Text)  # Store profile as JSON text
    insights = db.Column(db.Integer, default=0)  # New field for Insights

    def set_profile(self, profile_dict):
        self.profile_data = json.dumps(profile_dict)

    def get_profile(self):
        profile = json.loads(self.profile_data) if self.profile_data else {}
        if "insights" not in profile:
            profile["insights"] = self.insights
        return profile
