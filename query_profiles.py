# query_profiles.py

from app import app  # Import your Flask app instance
from models import UserProfile  # Import the UserProfile model
from dotenv import load_dotenv

load_dotenv()  # This loads variables from your .env file into this shell's environment
import os
print(os.getenv("OPENAI_API_KEY"))


# Push the application context so that Flask-SQLAlchemy knows which app to use.
with app.app_context():
    # Query all user profiles
    profiles = UserProfile.query.all()
    
    # Loop through each profile and print its details
    for profile in profiles:
        print(f"User ID: {profile.user_id}")
        print("Profile Data:", profile.get_profile())
        print("-" * 40)
