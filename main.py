import asyncio
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
import google.generativeai as genai
from twscrape import API, gather
from twscrape.logger import set_log_level

async def scrape_complaints():
    """Scrape X for civic complaints using browser cookies to bypass Cloudflare."""
    try:
        api = API()
        
        # Grab credentials and cookies from environment variables
        username = os.environ.get("X_USERNAME")
        password = os.environ.get("X_PASSWORD", "dummy_pass")
        email = os.environ.get("X_EMAIL", "dummy@email.com")
        email_password = os.environ.get("X_EMAIL_PASSWORD", "dummy_epass")
        auth_token = os.environ.get("X_AUTH_TOKEN")
        ct0 = os.environ.get("X_CT0")

        if not all([username, auth_token, ct0]):
            print("Missing X credentials or cookies. Set X_USERNAME, X_AUTH_TOKEN, X_CT0")
            return "No major complaints tracked today due to missing credentials."
        
        # Format cookies for twscrape to bypass Cloudflare
        cookies_str = f"auth_token={auth_token}; ct0={ct0}"
        
        # Add account using the extracted browser cookies
        await api.pool.add_account(username, password, email, email_password, cookies=cookies_str)
        await api.pool.login_all()

        print("Fetching last 24h civic complaints...")
        # Search query for Bengaluru civic issues
        today = datetime.now().strftime("%Y-%m-%d")
        tweets = await gather(api.search(f"Bengaluru BESCOM OR BBMP OR BMTC OR BWSSB since:{today}", limit=30))
        scraped_text = "\n".join([t.rawContent for t in tweets])
        
        if not scraped_text.strip():
            return "No major complaints tracked today."
        return scraped_text
        
    except Exception as e:
        print(f"Scraping failed: {e}")
        return "No major complaints tracked today due to data extraction error."

def load_taxonomy():
    with open('civic_taxonomy.json', 'r', encoding='utf-8') as f:
        return f.read()

def load_prompt():
    with open('system_prompt.txt', 'r', encoding='utf-8') as f:
        return f.read()

def clean_json(json_str):
    """Strip markdown fences and clean JSON string."""
    cleaned = re.sub(r'```\w*\n?', '', json_str).strip()
    return cleaned

def call_gemini(prompt, taxonomy, raw_data):
    """Call Gemini 1.5 Flash with retry logic to handle rate limits."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    
    # Switched to gemini-1.5-flash for higher Free Tier rate limits (15 RPM vs 5 RPM)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    full_prompt = f"{prompt}\n\n### CIVIC TAXONOMY:\n{taxonomy}\n\n### RAW DATA (Last 24h):\n{raw_data}"
    
    print("Calling Gemini 1.5 Flash...")
    
    # Added retry block to handle temporary rate limits
    try:
        response = model.generate_content(full_prompt)
    except Exception as e:
        print(f"Hit rate limit or error, retrying in 15 seconds... Error: {e}")
        time.sleep(15)
        response = model.generate_content(full_prompt)
    
    return response.text

def parse_response(response):
    """Parse Gemini response into 4 sections separated by ===SEPARATOR===."""
    sections = [s.strip() for s in response.split("===SEPARATOR===")]
    
    if len(sections) < 4:
        raise ValueError(f"Expected 4 sections, got {len(sections)}")
    
    thread_text = sections[0] if sections[0] else "Error generating thread"
    json_raw = sections[1] if sections[1] else "{}"
    audio_script = sections[2] if sections[2] else "Error generating script"
    
    # Clean and parse JSON
    json_str = clean_json(json_raw)
    try:
        data_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        data_json = {"error": str(e)}
    
    return thread_text, data_json, audio_script

def save_files(thread_text, data_json, audio_script):
    """Save the three output sections to files."""
    with open('daily_report.md', 'w', encoding='utf-8') as f:
        f.write(thread_text)
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data_json, f, indent=2, ensure_ascii=False)
    
    with open('audio_script.txt', 'w', encoding='utf-8') as f:
        f.write(audio_script)

def run_generate_scorecard():
    """Execute the scorecard generation script."""
    print("Generating report card image...")
    subprocess.run(['python', 'generate_scorecard.py'], check=True)

def archive_data(data_json):
    date_str = data_json['report_date']
    os.makedirs('history', exist_ok=True)
    with open(f'history/{date_str}.json', 'w') as f:
        json.dump(data_json, f, indent=2)

async def main():
    """Main orchestrator: scrape data, call Gemini, parse response, save outputs."""
    set_log_level("WARNING")

    # Scrape X for civic complaints
    scraped_data = await scrape_complaints()
    
    # Load system prompt and taxonomy
    taxonomy = load_taxonomy()
    prompt = load_prompt()
    
    # Call Gemini with retry logic
    response = call_gemini(prompt, taxonomy, scraped_data)
    
    # Parse the 4-part response
    thread_text, data_json, audio_script = parse_response(response)
    
    # Save the three output files
    save_files(thread_text, data_json, audio_script)
    
    # Generate report card
    run_generate_scorecard()
    
    # Archive JSON to history
    archive_data(data_json)
    
    print("Daily report generated successfully")

if __name__ == "__main__":
    asyncio.run(main())