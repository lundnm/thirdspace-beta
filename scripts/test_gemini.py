from google import genai
from google.genai import types

# 1. Paste your exact API key inside the quotes below
MY_GEMINI_KEY = "AIzaSyBQM1URCcnbZ_orgJIllREjLZiEVFpKQGk"

print("🔄 Initializing Gemini Client...")

try:
    # 2. Connect to Google's AI servers
    client = genai.Client(api_key=MY_GEMINI_KEY)
    
    # 3. Enable the Google Search tool
    print("🔍 Equipping Google Search capability...")
    search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )
    
    # 4. Define a test prompt (using a classic rivalry since it's March Madness season!)
    test_prompt = (
        "You are an energetic sports writer for ThirdSpace, a community helping fans find "
        "local spots to watch big games together. Your job is to write a thrilling, 4-5 sentence "
        "preview for an upcoming basketball game between Kansas and Houston. Highlight the stakes, a key player "
        "matchup, or a fun narrative. Keep it punchy, engaging, and under 75 words."
    )
    
    print("🧠 Asking Gemini-2.5-Flash to write the preview (this takes a few seconds)...")
    
    # 5. Generate the response
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=test_prompt,
        config=types.GenerateContentConfig(
            tools=[search_tool],
            temperature=0.7
        )
    )
    
    # 6. Print the result!
    print("\n✅ SUCCESS! The API is working. Here is your preview:\n")
    print("=" * 50)
    print(response.text.strip())
    print("=" * 50)
    
except Exception as e:
    print("\n❌ ERROR: Something went wrong.")
    print("Check to make sure you pasted the API key correctly and have an internet connection.")
    print(f"Technical details: {e}")