from fastapi import FastAPI, Request
import requests
import base64
import os
import numpy as np
from google import genai
import time
import numpy as np
import logging
import mimetypes


app = FastAPI()
loaded_chunks = []
loaded_embeddings = np.array([])
# Load embeddings once at startup
try:
    print("🔄 Loading embeddings at startup...")
    data = np.load("all_embeddings_archive.npz", allow_pickle=True)
    raw_chunks = data["metadata"]
    raw_embeddings = data["embeddings"]

    filtered_chunks = []
    filtered_embeddings = []

    for emb, chunk in zip(raw_embeddings, raw_chunks):
        if emb is None:
            continue
        if not isinstance(emb, np.ndarray) or emb.ndim != 1:
            continue
        filtered_chunks.append(chunk)
        filtered_embeddings.append(emb)

    if not filtered_embeddings:
        raise ValueError("No valid embeddings found.")

    loaded_chunks = filtered_chunks
    loaded_embeddings = np.array(filtered_embeddings)

    print(f"✅ Loaded {len(loaded_embeddings)} embeddings.")

except Exception as e:
    print(f"❌ Error loading embeddings: {e}")
    loaded_chunks = []
    loaded_embeddings = np.array([])



logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
GPT4O_API_URL = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
AI_PIPE_TOKEN=os.getenv("AI_PIPE_TOKEN", "").strip()
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN", "").strip()


def get_img_desc(base64_image_str,question_one):
    image_data_url = f"data:image/jpeg;base64,{base64_image_str}"

    headers = {
        "Authorization": f"Bearer {AIPROXY_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",  # or "gpt-4o" if using full model
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Describe this image in one paragrpah related to Tools in Data Science and this question : {question_one}"},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]
    }

    try:
        response = requests.post(GPT4O_API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            desc = result["choices"][0]["message"]["content"]
            logger.info(desc.strip)
            return desc.strip()
        else:
            logger.error(f"Failed with status {response.status_code}: {response.text}")
            return "Image description failed."
    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return "Image description failed."

    except Exception as e:
        logger.error(f"Error in get_img_desc: {e}")
        return "Image description generation failed."



EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_URL = "http://aiproxy.sanand.workers.dev/openai/v1/embeddings"

def get_embedding(text: str, max_retries=3, delay=1.0):
    if not AIPROXY_TOKEN:
        raise ValueError("AIPROXY_TOKEN is not set in environment variables.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPROXY_TOKEN}"
    }

    payload = {
        "model": EMBEDDING_MODEL,
        "input": [text]
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(EMBEDDING_URL, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()["data"][0]["embedding"]
            elif response.status_code in [429, 503]:
                print(f"⏳ Retry {attempt} for rate limit or overload: {response.status_code}")
                time.sleep(delay * attempt)
            else:
                raise Exception(f"❌ HTTP {response.status_code}: {response.text}")
        except Exception as e:
            if attempt == max_retries:
                print(f"❌ Failed after {max_retries} attempts: {e}")
                return None
            time.sleep(delay * attempt)

def generate_llm_response(question: str, context: str) -> str:
    system_prompt = (
    "You are a helpful teaching assistant. Use the provided context to answer the question. "
    "Your response must be precise and factually accurate. "
    "Use markdown formatting with code blocks, lists, and headings where necessary. "
    "If the question is not answerable from the context, respond with 'I don't know'."
)
    if not AIPROXY_TOKEN:
        raise ValueError("AIPROXY_TOKEN is not set in environment variables.")
    
    URL = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPROXY_TOKEN}"
    }
    payload = {
        "model":"gpt-4o-mini",
        "messages":[
        {"role":"system","content":system_prompt},
         {"role": "user", "content": f"Context:\n{context}"},
          {"role": "user", "content": f"Question:\n{question}"}],
            "max_tokens": 512,
            "temperature": 0.2,
            "top_p": 0.95
    }

    try:
        response = requests.post(URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"❌ LLM generation failed: {e}")
        return "I don't know"

def answer(question: str, image: str = None):
    global loaded_chunks, loaded_embeddings
    if loaded_embeddings is None or len(loaded_embeddings) == 0:
        return {"error": "Embeddings not loaded. Please try again later."}

    if image:
        image_description = get_img_desc(image,question_one=question)
        question += " " + image_description

    question_embedding = get_embedding(question)
    if question_embedding is None:
        return {"error": "Failed to generate embedding for the question."}

    try:
        similarities = np.dot(loaded_embeddings, question_embedding) / (
        np.linalg.norm(loaded_embeddings, axis=1) * np.linalg.norm(question_embedding)
    )
    except Exception as e:
        return {"error": f"Similarity computation failed: {e}"}


    top_indices = np.argsort(similarities)[-10:][::-1]
    top_chunks = [loaded_chunks[i] for i in top_indices]
    urls = [chunk["url"] for chunk in top_chunks]

    context_text = "\n".join(chunk["content"] for chunk in top_chunks if "content" in chunk)
    response = generate_llm_response(question, context_text)

    return {
    "answer": response,
    "links": [{"url": chunk["url"], "text": chunk.get("title", "Source")} for chunk in top_chunks]
}

@app.post("/api/")
async def api_answer(request: Request):
    try:
        data = await request.json()
        return answer(data.get("question"), data.get("image"))
    except Exception as e:
        return {"error": str(e)}


if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8000)