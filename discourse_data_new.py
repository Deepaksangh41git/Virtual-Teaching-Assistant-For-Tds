import json
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
import time
import sys
from markdownify import markdownify as md
import os

cookies = []# paste your cookies value in dictionary format
cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

req_data=[]
base_url="https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34.json?page="

start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 4, 15)

def get_topics():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": cookie_str
    }
    print(cookie_str)
    for page in range(1,7):
        url=f"https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34.json?page={page}"
        response=requests.get(url,headers=headers)
        data=response.json()
       
        topics = data["topic_list"]["topics"]
        for topic in topics:
            post_time = datetime.strptime(topic["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
            if start_date < post_time < end_date:
                req_data.append(topic)
    with open("discourse_topics_data_final.json","w") as f:
        json.dump(req_data,f)
    print(req_data)

# get_topics()  call this to get all the topics(thread)

relevent_topics=req_data

posts=[]

def get_posts():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": cookie_str  
    }

    for topic in relevent_topics:
        topic_id = str(topic["id"])
        topic_slug= str(topic["slug"])
        page = 1
        posts = []
        json_content=[]
        # Create folder for this topic
        folder_path = os.path.join("/home/deeps/Desktop/project_1/data/discourse_data", topic_id)
        os.makedirs(folder_path, exist_ok=True)

        while True:
            url = f"https://discourse.onlinedegree.iitm.ac.in/t/{topic_id}.json?page={page}"
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                break

            data = response.json()
            content = data["post_stream"]["posts"]

            if not content:
                break

            for post in content:
                post_time = datetime.strptime(post["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
                if start_date < post_time < end_date:
                    markdown = md(post["cooked"])
                    posts.append(markdown + "\n\n---\n\n")  # separate posts with divider

            page += 1
            
            json_content.append(content)

        # Write to json file
        md_file_path = os.path.join(folder_path, f"{topic_slug}_json.json")
        with open(md_file_path, "w", encoding="utf-8") as fone:
            json.dump(json_content,fone)

        # Write to Markdown file
        md_file_path = os.path.join(folder_path, f"{topic_slug}.md")
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.writelines(posts)

        print(f"✅ Saved {len(posts)} posts to {md_file_path}")

# get_posts() call this to get all the post of all the topics

import os
import json
from markdownify import markdownify as md

def process_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            nested_data = json.load(f)

        output = []
        topic_id = None

        # Flatten the nested list structure
        for post_list in nested_data:
            for post in post_list:
                cooked = post.get("cooked")
                topic_slug = post.get("topic_slug")
                topic_id = post.get("topic_id")
                post_number = post.get("post_number")

                if cooked and topic_slug and topic_id and post_number:
                    markdown = md(cooked)
                    source = f"https://discourse.onlinedegree.iitm.ac.in/t/{topic_slug}/{topic_id}/{post_number}"
                    output.append({
                        "text": markdown,
                        "link": source
                    })

        if output and topic_id:
            out_file = os.path.join(os.path.dirname(file_path), f"{topic_id}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(output)} posts to {out_file}")
        else:
            print(f"⚠️ No valid posts or missing topic_id in {file_path}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

# === Root folder that contains .json files ===
input_root = "/home/deeps/Desktop/project_1/data/discourse_data"  # <-- CHANGE THIS

for root, dirs, files in os.walk(input_root):
    for file in files:
        if file.endswith(".json"):
            file_path = os.path.join(root, file)
            process_json_file(file_path)

