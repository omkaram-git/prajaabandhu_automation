import json
import os
from PIL import Image, ImageDraw, ImageFont

def generate_scorecard():
    # Read data.json
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("data.json not found")
        return

    # Try to open base_template.png, else create fallback
    try:
        img = Image.open('base_template.png')
    except FileNotFoundError:
        img = Image.new('RGB', (1080, 1080), '#111827')

    draw = ImageDraw.Draw(img)

    # Try to load font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 40)
        small_font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Layout coordinates (example positions)
    positions = {
        'Date': (100, 100),
        'Critical Issue': (100, 200),
        'Frustration Score': (100, 300),
        'Main Complaint': (100, 400),
        'Minister to act': (100, 500)
    }

    # Draw text
    draw.text(positions['Date'], f"Date: {data.get('report_date', 'N/A')}", fill='white', font=font)
    draw.text(positions['Critical Issue'], f"Critical Issue: {data.get('worst_department', 'N/A')}", fill='white', font=font)
    draw.text(positions['Frustration Score'], f"Frustration Score: {data.get('frustration_score', 'N/A')}/10", fill='white', font=font)
    draw.text(positions['Main Complaint'], f"Main Complaint: {data.get('top_issue', 'N/A')}", fill='white', font=font)
    draw.text(positions['Minister to act'], f"Minister to act: {data.get('minister_in_charge', 'N/A')}", fill='white', font=font)

    # Save the image
    img.save('report_card.png')
    print("Scorecard generated: report_card.png")

if __name__ == "__main__":
    generate_scorecard()