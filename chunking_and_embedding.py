import numpy as np
import os
import time
from pathlib import Path
from semantic_text_splitter import MarkdownSplitter
from tqdm import tqdm 
import json
from google import genai
import requests
COURSE_ROOT_FOLDER = "/home/deeps/Desktop/project_1/data/course_data"# Folder with nested subfolders of .md files
COURSE_CHUNKS_FOLDER = "/home/deeps/Desktop/project_1/data/course_data"# Output folder for chunks and embeddings
RATE_LIMIT = 15                         # Gemini requests per minute
SLEEP = 60 / RATE_LIMIT
ARCHIVE_PATH = "markdown_embeddings_archive.zip"
DISCOURSE_ROOT_FOLDER="/home/deeps/Desktop/project_1/data/discourse_data"
CHUNK_SIZE = 1500
OVERLAP = 100


# ------------------ INIT GEMINI ------------------
client=genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))    

# ------------------ INIT SPLITTER ------------------
splitter = MarkdownSplitter(1500)
# ------------------ CREATE OUTPUT FOLDER ------------------
Path(COURSE_CHUNKS_FOLDER).mkdir(parents=True, exist_ok=True)


all_chunks_metadata = []  # Stores chunk text + metadata
all_embeddings = []       # Stores all embedding vectors


""" def get_chunks(file_path:str,chunk_size:int =1500,chunk_overlap=100):
    with open(file_path,'r',encoding='utf-18') as f:
        content=f.read()
    splitter=MarkdownSplitter(chunk_size)
    chunks=splitter.chunks(content)
    chunk_metadata_list = []
    for i, chunk in enumerate(chunks):
        chunk_metadata = {
                    "content": chunk,
                    "source": "https://tds.s-anand.net/#/{f.name}",
                }
        chunk_metadata_list.append(chunk_metadata)
    with open(file_path,'r',encoding='utf-18') as f:
        content=f.write()    
    return chunks
 """
def create_course_chunks():
    def convert_to_source_url(md_file_path: str) -> str:
        path = Path(md_file_path).resolve()
        parts = path.parts
        try:
            idx = parts.index("course_data")
            subfolder = parts[idx + 1].lstrip("_")  # remove leading underscore
        except (ValueError, IndexError):
            subfolder = "unknown"

        return f"https://tds.s-anand.net/#/{subfolder}"

    # ----------------------------------------------------
    # STEP 1: Create chunks next to each markdown file
    # ----------------------------------------------------
    print("🔹 Step 1: Creating chunks...")

    for root, dirs, files in os.walk(COURSE_ROOT_FOLDER):
        for file in files:
            if file.endswith(".md"):
                md_path = os.path.join(root, file)
                with open(md_path, "r", encoding="utf-8") as f:
                    md_text = f.read()

                chunks = splitter.chunks(md_text)
                relative_path = os.path.relpath(md_path, COURSE_ROOT_FOLDER)
                chunk_list = []
                source=convert_to_source_url(f"https://tds.s-anand.net/#/{f.name}")
                for i, chunk in enumerate(chunks):
                    metadata = { 
                        "url":source ,
                        "content": chunk
                    }
                    chunk_list.append(metadata)
                    all_chunks_metadata.append(metadata)

                # Save chunk JSON next to the markdown file
                chunk_file_path = os.path.join(root, file.replace(".md", "_chunks.json"))
                with open(chunk_file_path, "w", encoding="utf-8") as out:
                    json.dump(chunk_list, out, indent=2)

                print(f"✅ Saved: {chunk_file_path}")

def create_discourse_chunks():
    def chunk_text(text, chunk_size=1500, overlap=100):
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i + chunk_size])
            i += chunk_size - overlap
        return chunks
    for root, dirs, files in os.walk(DISCOURSE_ROOT_FOLDER):
        for file in files:
            # Only process JSON files named same as their folder
            if file.endswith(".json") and os.path.basename(root) == file.replace(".json", ""):
                json_path = os.path.join(root, file)

                with open(json_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except Exception as e:
                        print(f"❌ Error reading {json_path}: {e}")
                        continue

                chunk_list = []
                for item in data:
                    text = item.get("text", "")
                    link = item.get("link", "")

                    if len(text.strip()) == 0:
                        continue

                    if len(text) > CHUNK_SIZE:
                        chunks = chunk_text(text, CHUNK_SIZE, OVERLAP)
                    else:
                        chunks = [text]

                    for chunk in chunks:
                        metadata = {
                            "url": link,
                            "content": chunk
                        }
                        chunk_list.append(metadata)
                        all_chunks_metadata.append(metadata)

                # Save the chunks next to the original JSON
                out_path = os.path.join(root, file.replace(".json", "_chunks.json"))
                with open(out_path, "w", encoding="utf-8") as f_out:
                    json.dump(chunk_list, f_out, indent=2)

                print(f"✅ Saved: {out_path}")

create_course_chunks()
create_discourse_chunks()

# ----------------------------------------------------
# STEP 2: Embed all chunks and save one combined .npy
# ----------------------------------------------------
print("\n🔹 Step 2: Embedding all chunks...")
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN", "").strip()
SAVE_INTERVAL = 100  # Save every N chunks
OUTPUT_FILE = "all_embeddings_archive.npz"
BACKUP_DIR = "embedding_checkpoints"
os.makedirs(BACKUP_DIR, exist_ok=True)

def embed_text_with_retry(text, max_retries=5, backoff=1):
    url = "http://aiproxy.sanand.workers.dev/openai/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPROXY_TOKEN}"
    }
    data = {
        "model": "text-embedding-3-small",
        "input": [text]
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                return response.json()["data"][0]["embedding"]
            elif response.status_code in [429, 503]:
                wait_time = backoff * (2 ** attempt)
                print(f"⏳ Retry {attempt+1}/{max_retries} after {wait_time}s (Error {response.status_code})")
                time.sleep(wait_time)
            else:
                print(f"❌ HTTP {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Exception on attempt {attempt+1}: {e}")
            time.sleep(backoff * (2 ** attempt))
    return None

# === Embed loop ===
for i, chunk in enumerate(tqdm(all_chunks_metadata, desc="Embedding chunks")):
    try:
        text = chunk["content"] if chunk["content"] else ""
        if not text.strip():
            all_embeddings.append(None)
            continue

        vec = embed_text_with_retry(text)
        all_embeddings.append(vec)
    except Exception as e:
        print(f"❌ Unexpected error for chunk {i}: {e}")
        all_embeddings.append(None)

    # Save partial backup every N chunks
    if i > 0 and i % SAVE_INTERVAL == 0:
        backup_path = os.path.join(BACKUP_DIR, f"checkpoint_{i}.npz")
        np.savez(backup_path, embeddings=all_embeddings, metadata=all_chunks_metadata)
        print(f"💾 Checkpoint saved at {backup_path}")
# ----------------------------------------------------
# STEP 3: Save global embedding + metadata archive
# ----------------------------------------------------

print("\n💾 Saving all_embeddings.npy and all_chunks_metadata.json...")

np.savez(
    "all_embeddings_archive.npz",
    embeddings=all_embeddings,
    metadata=all_chunks_metadata,
)

print("✅ Done. Archive complete.")




