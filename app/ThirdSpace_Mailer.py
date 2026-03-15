import os
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import time
import re
from google import genai
from google.genai import types
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("GMAIL_SENDER")
SENDER_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RAFFLE_LINK = "https://forms.gle/7BS8oXxDEEE4jYPP8"
FEEDBACK_LINK = "https://forms.gle/EazVGvRhaSWv5TZh8"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def generate_game_preview(league, team_a, team_b):
    """
    Generates a grounded, high-energy game preview using Gemini.
    Requires GEMINI_API_KEY set in your environment variables.
    """
    # 1. Initialize the client
    # The SDK automatically picks up the GEMINI_API_KEY environment variable.
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"⚠️ Failed to initialize Gemini Client (Check API Key): {e}")
        return f"A massive {league} showdown between {team_a} and {team_b}. Expect high energy tonight!"

    # 2. Define the System Instruction (Persona & Rules)
    system_instruction = (
        "You are an energetic sports writer for ThirdSpace, a community helping fans find "
        "local spots to watch big games together. Write every game preview in exactly this format:\n\n"
        "HOOK: [1-2 punchy sentences that hook the reader — highlight the stakes or a key narrative]\n"
        "BULLETS:\n"
        "- [key player matchup or individual storyline]\n"
        "- [standings context or recent form]\n"
        "- [injury news, X-factor, or something to watch]\n\n"
        "Be concise, energetic, and grounded in current facts. Do not add any other text."
    )

    # 3. Define the User Prompt Payload
    prompt = (
        f"Please write a preview for the following game:\n"
        f"Matchup: {team_a} vs. {team_b}\n"
        f"League/Tournament: {league}\n"
        f"Context: Look up the latest news, standings, or injury reports to make this relevant to today."
    )

    # 4. Enable Google Search Grounding
    search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # 5. Call the API
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", # Fast, cost-effective, perfect for batch text processing
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[search_tool],
                temperature=0.7 # Slight creativity, but grounded in the search facts
            )
        )
        
        hook = ''
        bullets = []
        in_bullets = False
        for line in response.text.strip().splitlines():
            line = line.strip()
            if line.startswith('HOOK:'):
                hook = line[5:].strip()
            elif line.startswith('BULLETS:'):
                in_bullets = True
            elif in_bullets and line.startswith('-'):
                bullets.append(line[1:].strip())
        return {'hook': hook, 'bullets': bullets}

    except Exception as e:
        print(f"⚠️ Error generating preview for {team_a} vs {team_b}: {e}")
        # Fallback if the API fails so the email loop doesn't crash
        return {
            'hook': f"A massive {league} showdown between {team_a} and {team_b}. Expect high energy and major implications tonight!",
            'bullets': []
        }
    
def process_csv_and_send_emails(csv_path):
    # Read the CSV
    df = pd.read_csv(csv_path)
    
    # Dictionary to cache LLM previews so we don't generate the same preview twice
    preview_cache = {}
    
    # List to hold the clean, formatted data for the email template
    subscribers = []

    today = pd.to_datetime("today").normalize()

    print("Step 1: Parsing CSV and Generating Previews...")
    for index, row in df.iterrows():
        name = str(row['fullname']).strip()
        email = str(row['email']).strip()
        signup_date = pd.to_datetime(row['timestamp'], errors='coerce')
        is_new = pd.notna(signup_date) and (today - signup_date.normalize()).days <= 7
        
        # Split the semicolon-separated columns into lists
        venues = [v.strip() for v in str(row['assigned_venues']).split(';')]
        games_raw = [g.strip() for g in str(row['todays_games']).split(';')]
        times = [t.strip() for t in str(row['game_times']).split(';')]
        
        user_games = []
        
        # Zip through the lists (assuming each user has matching counts of venues/games/times)
        for i in range(len(games_raw)):
            game_str = games_raw[i]
            # Safety checks in case of malformed data
            venue = venues[i] if i < len(venues) else "A local favorite"
            
            raw_game_time = times[i] if i < len(times) else "Check local listings"

            try:
                # This reads the military time (e.g., "20:30")
                time_obj = datetime.strptime(raw_game_time.strip(), "%H:%M")
                
                # This formats it to "08:30 PM" and lstrip("0") makes it "8:30 PM"
                game_time = time_obj.strftime("%I:%M %p").lstrip("0")
            except ValueError:
                # If the time is already "8:30 PM", "TBD", or malformed, just leave it as is
                game_time = raw_game_time
            
            # Use Regex to parse format like: "[NBA] Detroit Pistons,Memphis Grizzlies"
            # match.group(1) = League, match.group(2) = Team A, match.group(3) = Team B
            match = re.match(r'\[(.*?)\]\s*(.*?),([^;]+)', game_str)
            
            if match:
                league = match.group(1).strip()
                team_a = match.group(2).strip()
                team_b = match.group(3).strip()
            else:
                league, team_a, team_b = "Basketball", "Team A", "Team B"

            # Create a unique key for the cache (e.g., "NBA_Detroit Pistons_Memphis Grizzlies")
            game_key = f"{league}_{team_a}_{team_b}"
            
            # Check if we already generated a preview for this exact game
            if game_key not in preview_cache:
                preview_cache[game_key] = generate_game_preview(league, team_a, team_b)
            
            # Build the game dictionary for the template
            user_games.append({
                "team_a": team_a,
                "team_b": team_b,
                "time": game_time,
                "venue": venue,
                "preview": preview_cache[game_key]
            })
            
        # Add the fully compiled user profile to our subscribers list
        subscribers.append({
            "name": name,
            "email": email,
            "games": user_games,
            "is_new": is_new
        })

    print(f"✅ Generated {len(preview_cache)} unique game previews for {len(subscribers)} subscribers.")

    # 3. Setup Jinja2 Environment and Send Emails
    print("Step 2: Sending Batch Emails...")
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template('thirdspace_template.html')

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        
        for sub in subscribers:
            html_content = template.render(
                name=sub['name'],
                games=sub['games'],
                raffle_link=RAFFLE_LINK,
                feedback_link=FEEDBACK_LINK
            )
            
            msg = MIMEMultipart("alternative")
            msg['Subject'] = f"{sub['name']}, your ThirdSpace Watch Guide 🏀"
            msg['From'] = f"ThirdSpace Beta <{SENDER_EMAIL}>"
            msg['To'] = sub['email']
            
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            server.sendmail(SENDER_EMAIL, sub['email'], msg.as_string())
            print(f"📧 Sent successfully to {sub['name']} ({sub['email']})")
            
            time.sleep(1) # Prevent rate limiting
            
    except Exception as e:
        print(f"❌ Error sending batch: {e}")
    finally:
        server.quit()
        print("🎉 Batch complete.")

# 4. Execute the pipeline
if __name__ == "__main__":
    # Ensure you have your HTML template saved as 'thirdspace_template.html' in the same folder
    TODAY = pd.to_datetime("today").strftime("%Y-%m-%d")
    process_csv_and_send_emails(f"../data/User_Responses_With_Venues_{TODAY}.csv")