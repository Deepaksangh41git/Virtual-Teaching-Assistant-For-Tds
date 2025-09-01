import json
from markdownify import markdownify as md
from pathlib import Path 
import os
from PIL import Image 
import mimetypes
import io
import re
from google import genai
import requests
from io import BytesIO
import tempfile
from ratelimit import limits, sleep_and_retry
from tqdm import tqdm

REQUESTS_PER_MINUTE = 15
TIME_PERIOD = 60  # in seconds
pattern = r'!\[(.*?)\]\((.*?)\)'


# === Rate Limited Captioning Function ===
@sleep_and_retry
@limits(calls=REQUESTS_PER_MINUTE, period=TIME_PERIOD)
def get_img_desc(image_path):
    try:
        client=genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))    
        my_file=client.files.upload(file=image_path)

        resp=client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[my_file,"Caption this image related to Tools in Data Science in one paragraph not multiple options. "]
        )
        return resp.text.strip()
    except Exception as e:
        print(f"❌ Error processing {image_path}: {e}")
        return "Image description not available"
def get_image_description_course():
    def process_file_with_tqdm(md_path):
        print(f"\nProcessing: {md_path}")

        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        def replace_image(match):
            alt_text, img_url = match.groups()
            response = requests.get(img_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp_file:
                    tmp_file.write(response.content)
                    tmp_file_path = tmp_file.name
            description = get_img_desc(tmp_file_path)
            return f"**{description}**"

        new_content = re.sub(pattern, replace_image, content)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    # === Collect all .md files recursively ===
    def collect_md_files(root_dir):
        md_files = []
        for dirpath, _, filenames in os.walk(root_dir):
            for fname in filenames:
                if fname.endswith('.md'):
                    md_files.append(os.path.join(dirpath, fname))
        return md_files


    root_folder = "/home/deeps/Desktop/project_1/data/course" 
    md_files = collect_md_files(root_folder)
    for md_file in md_files:
        process_file_with_tqdm(md_file)

def get_image_description_discourse():
    root_folder = "/home/deeps/Desktop/project_1/data/discourse_data"

    # Traverse each subfolder
    for subdir_name in os.listdir(root_folder):
        subdir_path = os.path.join(root_folder, subdir_name)
        if os.path.isdir(subdir_path):
            target_json_file = os.path.join(subdir_path, f"{subdir_name}.json")
            if os.path.exists(target_json_file):
                print(f"\n🔍 Processing: {target_json_file}")

                # Load JSON
                with open(target_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                updated_data = []
                for item in tqdm(data, desc=f"⏳ Updating posts in {subdir_name}"):
                    text = item.get("text", "")
                    link = item.get("link", "")

                    # Replace image with description
                    def replace_image(match):
                        alt_text, img_url = match.groups()
                        try:
                            response = requests.get(img_url)
                            response.raise_for_status()
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp_file:
                                tmp_file.write(response.content)
                                tmp_file_path = tmp_file.name
                            description = get_img_desc(tmp_file_path)
                            return f"**{description}**"
                        except Exception as e:
                            print(f"⚠️ Failed to process {img_url}: {e}")
                            return match.group(0)

                    new_text = re.sub(pattern, replace_image, text)

                    updated_data.append({
                        "text": new_text,
                        "link": link
                    })

                # Save updated JSON back to same file
                with open(target_json_file, "w", encoding="utf-8") as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Updated: {target_json_file}")

get_image_description_discourse()