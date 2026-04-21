import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
import google.generativeai as genai
from twscrape import API, gather
from twscrape.logger import set_log_level

async def scrape_complaints():
    try:
        api = API()
        
        # Add account credentials from environment variables
        username = os.getenv('X_USERNAME')
        password = os.getenv('X_PASSWORD')
        email = os.getenv('X_EMAIL')
        email_password = os.getenv('X_EMAIL_PASSWORD')
        
        if not all([username, password, email, email_password]):
            print("Missing X credentials. Set X_USERNAME, X_PASSWORD, X_EMAIL, X_EMAIL_PASSWORD")
            return "No major complaints tracked today"
        
        # Add account to pool and login
        await api.pool.add_account(username, password, email, email_password)
        await api.pool.login_all()

        # Keywords for Bengaluru civic issues
        keywords = ["BMTC", "BBMP", "BESCOM", "BWSSB", "Bengaluru"]
        query = " OR ".join(keywords) + " since:" + (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        tweets = await gather(api.search(query, limit=100))  # Adjust limit as needed

        complaints = []
        for tweet in tweets:
            complaints.append({
                "text": tweet.rawContent,
                "date": tweet.date.isoformat(),
                "user": tweet.user.username
            })

        if not complaints:
            return "No major complaints tracked today"

        return "\n".join([f"{c['date']}: {c['text']} (@{c['user']})" for c in complaints])

    except Exception as e:
        print(f"Scraping failed: {e}")
        return "No major complaints tracked today"

def load_taxonomy():
    with open('civic_taxonomy.json', 'r') as f:
        return json.load(f)

def load_prompt():
    with open('system_prompt.txt', 'r') as f:
        return f.read()

def call_gemini(prompt, taxonomy, data):
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.5-flash')  # Assuming this model exists
    full_prompt = f"{prompt}\n\nCivic Taxonomy:\n{json.dumps(taxonomy)}\n\nScraped Data:\n{data}"
    response = model.generate_content(full_prompt)
    return response.text

def parse_response(response):
    sections = response.split("===SEPARATOR===")
    if len(sections) != 3:
        raise ValueError("Invalid response format")

    section1 = sections[0].strip()
    section2_raw = sections[1].strip()
    section3 = sections[2].strip()

    # Strip markdown fences from section2
    section2_clean = re.sub(r'```\w*\n?', '', section2_raw).strip()

    # Parse JSON
    try:
        data_json = json.loads(section2_clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in section 2: {e}")

    return section1, data_json, section3

def save_files(section1, data_json, section3):
    with open('daily_report.md', 'w') as f:
        f.write(section1)

    with open('data.json', 'w') as f:
        json.dump(data_json, f, indent=2)

    with open('audio_script.txt', 'w') as f:
        f.write(section3)

def run_generate_scorecard():
    subprocess.run(['python', 'generate_scorecard.py'], check=True)

def archive_data(data_json):
    date_str = data_json['report_date']
    os.makedirs('history', exist_ok=True)
    with open(f'history/{date_str}.json', 'w') as f:
        json.dump(data_json, f, indent=2)

async def main():
    set_log_level("WARNING")  # Reduce logs

    scraped_data = await scrape_complaints()
    taxonomy = load_taxonomy()
    prompt = load_prompt()

    response = call_gemini(prompt, taxonomy, scraped_data)

    section1, data_json, section3 = parse_response(response)

    save_files(section1, data_json, section3)

    run_generate_scorecard()

    archive_data(data_json)

    print("Daily report generated successfully")

if __name__ == "__main__":
    asyncio.run(main())