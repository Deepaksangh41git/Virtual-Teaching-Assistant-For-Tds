# 🎓 Virtual Teaching Assistant for TDS 

This project is a **Virtual Teaching Assistant API** built to help answer student questions for the **Tools in Data Science (TDS)** course 
The assistant can automatically answer student queries using:  
- 📘 **Course content** (Jan 2025 batch, as of 15 Apr 2025)  
- 💬 **TDS Discourse posts** (1 Jan 2025 – 14 Apr 2025)  

By scraping and processing these sources, the API provides reliable, context-aware answers so that teaching assistants don’t have to respond to the same questions repeatedly.  

---

## 🚀 Features  

- ✅ Scrapes **TDS course content** and **Discourse forum posts**  
- ✅ Provides a simple **API endpoint** for querying  
- ✅ Accepts **student questions** and optional **file attachments (base64)**  
- ✅ Returns **JSON answers** with supporting links for transparency  
- ✅ Responds in **under 30 seconds**  

---

## 📡 API Usage  

The API is hosted at: Vercel

Send a POST request with a student’s question (and optional image/file attachment).  

### Example Request  

```bash
curl "https://app.example.com/api/" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"Should I use gpt-4o-mini which AI proxy supports, or gpt3.5 turbo?\", \"image\": \"$(base64 -w0 project-tds-virtual-ta-q1.webp)\"}"


