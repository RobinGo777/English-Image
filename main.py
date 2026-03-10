"""
English A2 Telegram Bot
Генерує 8 навчальних карток щодня і публікує в Telegram.
Розклад: 09:00–16:00 за Києвом, одна картка на годину.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from io import BytesIO

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from playwright.async_api import async_playwright

# ──────────────────────────────────────────────
# НАЛАШТУВАННЯ ЛОГІВ
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# ЗМІННІ СЕРЕДОВИЩА
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]   # ID вашого Saved Messages або каналу
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY       = os.environ["GROQ_API_KEY"]

# ──────────────────────────────────────────────
# МОДЕЛІ — ЛАНЦЮЖОК FALLBACK
# ──────────────────────────────────────────────
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-pro",
]
GROQ_MODEL = "llama-3.3-70b-versatile"

# ──────────────────────────────────────────────
# РОЗКЛАД РУБРИК
# ──────────────────────────────────────────────
SCHEDULE = {
    9:  "daily_phrase",
    10: "word_pack",
    11: "fun_fact",
    12: "quote",
    13: "situation",
    14: "chat_expressions",
    15: "synonyms_battle",
    16: "motivation",
}

# ──────────────────────────────────────────────
# КОЛЬОРОВІ ГАМИ (одна на рубрику)
# ──────────────────────────────────────────────
COLOR_SCHEMES = {
    "daily_phrase": {
        "bg": "#EAF0F8",
        "block1": "#C8DCF0",
        "block2": "#B8CCE0",
        "accent": "#2A6EA6",
        "text1": "#1A2530",
        "text2": "#1A4A7A",
        "rubric": "#A4B5C8",
        "wave_color": "42,110,166",
    },
    "word_pack": {
        "bg": "#F0F5EA",
        "block1": "#C8E0B8",
        "block2": "#B4CCА4",
        "accent": "#3A6A28",
        "text1": "#1A2518",
        "text2": "#2A5A20",
        "rubric": "#AABBA0",
        "wave_color": "80,140,60",
    },
    "fun_fact": {
        "bg": "#EDE8F5",
        "block1": "#D8D0EE",
        "block2": "#C8C0E4",
        "accent": "#6A4FC4",
        "text1": "#1E1830",
        "text2": "#3A2870",
        "rubric": "#B5AAD0",
        "wave_color": "106,79,196",
    },
    "quote": {
        "bg": "#E8F3EE",
        "block1": "#C0DDD0",
        "block2": "#B0CEC0",
        "accent": "#3A8A58",
        "text1": "#1A2E24",
        "text2": "#2A5A40",
        "rubric": "#A0BDB0",
        "wave_color": "40,130,80",
    },
    "situation": {
        "bg": "#EAF0F8",
        "block1": "#C8DCF0",
        "block2": "#B8CCE0",
        "accent": "#2A6EA6",
        "text1": "#1A2530",
        "text2": "#1A4A7A",
        "rubric": "#A4B5C8",
        "wave_color": "42,110,166",
    },
    "chat_expressions": {
        "bg": "#F5EEE8",
        "block1": "#EDD8CC",
        "block2": "#DDC8BC",
        "accent": "#8A4A35",
        "text1": "#1E1410",
        "text2": "#6A3020",
        "rubric": "#C4AFA4",
        "wave_color": "180,90,50",
    },
    "synonyms_battle": {
        "bg": "#EDE8F5",
        "block1": "#D8D0EE",
        "block2": "#C8C0E4",
        "accent": "#6A4FC4",
        "text1": "#1E1830",
        "text2": "#3A2870",
        "rubric": "#B5AAD0",
        "wave_color": "106,79,196",
    },
    "motivation": {
        "bg": "#F0F5EA",
        "block1": "#C8E0B8",
        "block2": "#B8D0A8",
        "accent": "#3A8A28",
        "text1": "#1A2E18",
        "text2": "#2A5A20",
        "rubric": "#AABBA0",
        "wave_color": "80,140,60",
    },
}

# ──────────────────────────────────────────────
# ПРОМПТИ ДЛЯ GEMINI
# ──────────────────────────────────────────────
def get_prompt(rubric: str, used_history: list) -> str:
    history_note = f"\nDo NOT use these recent topics/phrases: {used_history[-20:]}\n" if used_history else ""

    prompts = {

        "daily_phrase": f"""
You are an English teacher. Generate a useful conversational English phrase for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "phrase_en": "the English phrase (max 60 characters)",
  "example_en": "one example sentence using the phrase (max 120 characters)",
  "example_ua": "Ukrainian translation of the example sentence (max 120 characters)"
}}
Rules:
- Simple A2 vocabulary
- Natural, everyday conversation
- Short sentences
- Ukrainian must use only Ukrainian letters, no Russian
""",

        "word_pack": f"""
You are an English teacher. Choose a random everyday topic and generate 6 English words for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "topic": "topic name in English (1-2 words)",
  "words": [
    {{"en": "english word", "ua": "ukrainian translation"}},
    {{"en": "english word", "ua": "ukrainian translation"}},
    {{"en": "english word", "ua": "ukrainian translation"}},
    {{"en": "english word", "ua": "ukrainian translation"}},
    {{"en": "english word", "ua": "ukrainian translation"}},
    {{"en": "english word", "ua": "ukrainian translation"}}
  ]
}}
Rules:
- A2 level vocabulary only
- Common everyday words
- Ukrainian must use only Ukrainian letters, no Russian
- Each word max 20 characters
""",

        "fun_fact": f"""
You are an English teacher. Generate an interesting fun fact in simple English for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "fact_en": "interesting fact in English (max 160 characters, A2 level, simple words)",
  "fact_ua": "Ukrainian translation of the fact (max 180 characters)",
  "key_word": "one interesting word from the fact to highlight"
}}
Rules:
- Simple vocabulary, short sentences
- Surprising and interesting
- Ukrainian must use only Ukrainian letters, no Russian
""",

        "quote": f"""
You are an English teacher. Find a short motivational or wise quote for A2 level English students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "quote_en": "the quote in English (max 120 characters, simple words)",
  "author": "author name",
  "quote_ua": "Ukrainian translation of the quote (max 140 characters)"
}}
Rules:
- Simple A2 vocabulary
- Short and memorable
- Well-known author
- Ukrainian must use only Ukrainian letters, no Russian
""",

        "situation": f"""
You are an English teacher. Choose a random situation (hotel, airport, restaurant, shop, doctor, taxi) and generate 5 useful English phrases for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "situation": "situation name in English",
  "phrases": [
    {{"en": "english phrase (max 60 chars)", "ua": "ukrainian translation (max 70 chars)"}},
    {{"en": "english phrase (max 60 chars)", "ua": "ukrainian translation (max 70 chars)"}},
    {{"en": "english phrase (max 60 chars)", "ua": "ukrainian translation (max 70 chars)"}},
    {{"en": "english phrase (max 60 chars)", "ua": "ukrainian translation (max 70 chars)"}},
    {{"en": "english phrase (max 60 chars)", "ua": "ukrainian translation (max 70 chars)"}}
  ]
}}
Rules:
- Practical, everyday phrases
- A2 level vocabulary
- Ukrainian must use only Ukrainian letters, no Russian
""",

        "chat_expressions": f"""
You are an English teacher. Generate 5 common English internet/chat expressions or abbreviations for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "expressions": [
    {{"en": "ABBREVIATION — Full meaning", "ua": "Ukrainian explanation (max 50 chars)"}},
    {{"en": "ABBREVIATION — Full meaning", "ua": "Ukrainian explanation (max 50 chars)"}},
    {{"en": "ABBREVIATION — Full meaning", "ua": "Ukrainian explanation (max 50 chars)"}},
    {{"en": "ABBREVIATION — Full meaning", "ua": "Ukrainian explanation (max 50 chars)"}},
    {{"en": "ABBREVIATION — Full meaning", "ua": "Ukrainian explanation (max 50 chars)"}}
  ]
}}
Rules:
- Common online expressions (LOL, BRB, IMO, etc.)
- Simple explanations
- Ukrainian must use only Ukrainian letters, no Russian
- Max 60 characters per EN field
""",

        "synonyms_battle": f"""
You are an English teacher. Choose 3 English synonyms and explain the difference between them for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "words": [
    {{
      "en": "english word",
      "meaning": "when to use it (max 50 chars, simple English)",
      "ua": "ukrainian translation"
    }},
    {{
      "en": "english word",
      "meaning": "when to use it (max 50 chars, simple English)",
      "ua": "ukrainian translation"
    }},
    {{
      "en": "english word",
      "meaning": "when to use it (max 50 chars, simple English)",
      "ua": "ukrainian translation"
    }}
  ]
}}
Rules:
- Common everyday synonyms
- Simple A2 explanations
- Ukrainian must use only Ukrainian letters, no Russian
""",

        "motivation": f"""
You are an English teacher. Find a short motivational quote in simple English for A2 level students.
{history_note}
Return ONLY valid JSON, no markdown, no extra text:
{{
  "quote_en": "motivational quote in English (max 120 characters, simple words)",
  "author": "author name",
  "quote_ua": "Ukrainian translation (max 140 characters)"
}}
Rules:
- Inspiring and positive
- Simple A2 vocabulary
- Different from typical quotes — surprising or unusual
- Ukrainian must use only Ukrainian letters, no Russian
""",
    }
    return prompts[rubric]


# ──────────────────────────────────────────────
# UPSTASH REDIS — ЧЕРЕЗ ЧИСТИЙ HTTP (без greenlet)
# ──────────────────────────────────────────────
class UpstashRedis:
    """Мінімальний Upstash Redis клієнт через httpx REST API."""

    def __init__(self):
        self.url   = os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/")
        self.token = os.environ["UPSTASH_REDIS_REST_TOKEN"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _cmd(self, *args):
        cmd_url = self.url + "/" + "/".join(str(a) for a in args)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(cmd_url, headers=self.headers)
            resp.raise_for_status()
            return resp.json().get("result")

    async def ping(self):
        return await self._cmd("ping")

    async def lrange(self, key: str, start: int, end: int) -> list:
        result = await self._cmd("lrange", key, start, end)
        return result or []

    async def lpush(self, key: str, value: str) -> int:
        return await self._cmd("lpush", key, value)

    async def ltrim(self, key: str, start: int, end: int):
        return await self._cmd("ltrim", key, start, end)

    async def set(self, key: str, value: str, nx: bool = False, ex: int = None):
        parts = ["set", key, value]
        if nx:
            parts.append("nx")
        if ex:
            parts += ["ex", ex]
        return await self._cmd(*parts)

    async def delete(self, key: str):
        return await self._cmd("del", key)


class HistoryManager:
    def __init__(self, redis_client: UpstashRedis):
        self.r = redis_client
        self.max_history = 90  # днів без повтору

    async def get_used(self, rubric: str) -> list:
        key = f"used:{rubric}"
        try:
            items = await self.r.lrange(key, 0, -1)
            return [item if isinstance(item, str) else str(item) for item in items]
        except Exception as e:
            log.error(f"❌ Redis get_used error for {rubric}: {e}")
            return []

    async def add_used(self, rubric: str, value: str):
        key = f"used:{rubric}"
        try:
            await self.r.lpush(key, value)
            await self.r.ltrim(key, 0, self.max_history - 1)
            log.info(f"📝 Added to history [{rubric}]: {value[:50]}")
        except Exception as e:
            log.error(f"❌ Redis add_used error for {rubric}: {e}")

    async def acquire_lock(self, rubric: str, ttl: int = 300) -> bool:
        """Захист від паралельних запусків — TTL 5 хвилин."""
        key = f"lock:{rubric}"
        try:
            result = await self.r.set(key, "1", nx=True, ex=ttl)
            return result == "OK"
        except Exception as e:
            log.error(f"❌ Redis lock error for {rubric}: {e}")
            return True

    async def release_lock(self, rubric: str):
        key = f"lock:{rubric}"
        try:
            await self.r.delete(key)
        except Exception as e:
            log.error(f"❌ Redis release_lock error for {rubric}: {e}")


# ──────────────────────────────────────────────
# GEMINI / GROQ — ГЕНЕРАЦІЯ КОНТЕНТУ
# ──────────────────────────────────────────────
async def call_gemini(model: str, prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 1000,
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=payload,
            params={"key": GEMINI_API_KEY},
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        # Прибираємо markdown якщо є
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


async def call_groq(prompt: str) -> dict:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 1000,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


async def generate_content(rubric: str, history: list) -> dict:
    """Пробує Gemini моделі по черзі, потім Groq."""
    prompt = get_prompt(rubric, history)

    for model in GEMINI_MODELS:
        try:
            log.info(f"🤖 Trying Gemini model: {model}")
            result = await call_gemini(model, prompt)
            log.info(f"✅ Success with Gemini {model}")
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503, 500):
                log.warning(f"⚠️ Gemini {model} rate limit / server error, trying next...")
                await asyncio.sleep(2)
                continue
            else:
                log.error(f"❌ Gemini {model} HTTP error {e.response.status_code}: {e}")
                continue
        except (json.JSONDecodeError, KeyError) as e:
            log.error(f"❌ Gemini {model} bad JSON response: {e}")
            continue
        except Exception as e:
            log.error(f"❌ Gemini {model} unexpected error: {e}")
            continue

    # Всі Gemini впали — пробуємо Groq
    log.warning("⚠️ All Gemini models failed, falling back to Groq...")
    try:
        result = await call_groq(prompt)
        log.info("✅ Success with Groq fallback")
        return result
    except Exception as e:
        log.error(f"❌ Groq also failed: {e}")
        raise RuntimeError(f"All AI models failed for rubric [{rubric}]: {e}")


# ──────────────────────────────────────────────
# HTML ШАБЛОНИ — ГЕНЕРАЦІЯ КАРТОК
# ──────────────────────────────────────────────
WAVES = """
<div class="wave-tr"></div>
<div class="wave-tr2"></div>
<div class="wave-tr3"></div>
<div class="wave-bl"></div>
<div class="wave-bl2"></div>
"""

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1080px; height:1350px; overflow:hidden; }}
.card {{
  width:1080px; height:1350px;
  background:{bg};
  display:flex; flex-direction:column;
  padding:72px 80px;
  font-family:'Nunito', sans-serif;
  position:relative; overflow:hidden;
}}
.wave-tr {{ position:absolute; top:-140px; right:-140px; width:420px; height:420px; border-radius:50%; border:28px solid rgba({wave},0.10); pointer-events:none; }}
.wave-tr2 {{ position:absolute; top:-80px; right:-80px; width:260px; height:260px; border-radius:50%; border:18px solid rgba({wave},0.07); pointer-events:none; }}
.wave-tr3 {{ position:absolute; top:-30px; right:-30px; width:140px; height:140px; border-radius:50%; border:12px solid rgba({wave},0.05); pointer-events:none; }}
.wave-bl {{ position:absolute; bottom:-140px; left:-140px; width:400px; height:400px; border-radius:50%; border:28px solid rgba({wave},0.08); pointer-events:none; }}
.wave-bl2 {{ position:absolute; bottom:-80px; left:-80px; width:250px; height:250px; border-radius:50%; border:18px solid rgba({wave},0.05); pointer-events:none; }}
.topbar {{ display:flex; justify-content:flex-end; align-items:center; margin-bottom:28px; position:relative; z-index:1; }}
.rubric {{ font-size:40px; font-weight:700; color:{rubric}; }}
"""


def html_wrap(css: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>{css}</style>
</head>
<body>
<div class="card">
{WAVES}
{body}
</div>
</body>
</html>"""


def build_daily_phrase(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.blocks {{ display:flex; flex-direction:column; gap:20px; position:absolute;
  top:50%; left:80px; right:80px; transform:translateY(-50%); z-index:1; }}
.block {{ height:430px; border-radius:28px; padding:0 56px;
  display:flex; align-items:center; }}
.phrase-block {{ background:{cs["block1"]}; }}
.phrase-text {{ font-size:64px; font-weight:800; color:{cs["text1"]};
  letter-spacing:-1px; line-height:1.15; }}
.translation-block {{ background:{cs["block2"]}; flex-direction:column;
  justify-content:center; gap:14px; display:flex; }}
.example-en {{ font-size:46px; font-weight:700; color:{cs["text1"]}; line-height:1.3; }}
.example-ua {{ font-size:42px; font-weight:500; color:{cs["accent"]}; line-height:1.3; }}
"""
    phrase = data.get("phrase_en", "")
    ex_en  = data.get("example_en", "")
    ex_ua  = data.get("example_ua", "")
    body = f"""
<div class="topbar"><div class="rubric">💬 Daily Phrase</div></div>
<div class="blocks">
  <div class="block phrase-block">
    <div class="phrase-text">"{phrase}"</div>
  </div>
  <div class="block translation-block">
    <div class="example-en">{ex_en}</div>
    <div class="example-ua">{ex_ua}</div>
  </div>
</div>"""
    return html_wrap(css, body)


def build_word_pack(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.words-list {{ display:flex; flex-direction:column; gap:11px; flex:1; position:relative; z-index:1; }}
.word-row {{ border-radius:20px; overflow:hidden; display:flex; flex:1; }}
.word-en-block {{ background:{cs["block1"]}; flex:1; display:flex; align-items:center; padding:0 40px; }}
.word-en {{ font-size:52px; font-weight:800; color:{cs["text1"]}; letter-spacing:-0.5px; }}
.word-ua-block {{ background:{cs["block2"]}; width:340px; display:flex;
  align-items:center; justify-content:center; padding:0 28px; }}
.word-ua {{ font-size:42px; font-weight:600; color:{cs["accent"]}; text-align:center; line-height:1.2; }}
"""
    words = data.get("words", [])
    rows = ""
    for w in words[:6]:
        rows += f"""
  <div class="word-row">
    <div class="word-en-block"><div class="word-en">{w.get("en","")}</div></div>
    <div class="word-ua-block"><div class="word-ua">{w.get("ua","")}</div></div>
  </div>"""
    body = f"""
<div class="topbar"><div class="rubric">📦 Word Pack</div></div>
<div class="words-list">{rows}
</div>"""
    return html_wrap(css, body)


def build_fun_fact(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.blocks {{ display:flex; flex-direction:column; gap:20px; position:absolute;
  top:50%; left:80px; right:80px; transform:translateY(-50%); z-index:1; }}
.block {{ height:430px; border-radius:28px; padding:0 56px;
  display:flex; align-items:center; }}
.fact-block {{ background:{cs["block1"]}; }}
.fact-text {{ font-size:54px; font-weight:800; color:{cs["text1"]}; line-height:1.2; letter-spacing:-0.5px; }}
.fact-text span {{ color:{cs["accent"]}; }}
.translation-block {{ background:{cs["block2"]}; }}
.translation-text {{ font-size:48px; font-weight:500; color:{cs["text2"]}; line-height:1.4; }}
"""
    fact_en  = data.get("fact_en", "")
    fact_ua  = data.get("fact_ua", "")
    key_word = data.get("key_word", "")
    if key_word:
        fact_en = fact_en.replace(key_word, f"<span>{key_word}</span>", 1)
    body = f"""
<div class="topbar"><div class="rubric">💡 Fun Fact</div></div>
<div class="blocks">
  <div class="block fact-block">
    <div class="fact-text">{fact_en}</div>
  </div>
  <div class="block translation-block">
    <div class="translation-text">{fact_ua}</div>
  </div>
</div>"""
    return html_wrap(css, body)


def build_quote(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.blocks {{ display:flex; flex-direction:column; gap:20px; position:absolute;
  top:50%; left:80px; right:80px; transform:translateY(-50%); z-index:1; }}
.block {{ height:430px; border-radius:28px; padding:0 56px;
  display:flex; flex-direction:column; justify-content:center; gap:16px; }}
.quote-block {{ background:{cs["block1"]}; }}
.quote-text {{ font-size:52px; font-weight:800; color:{cs["text1"]}; line-height:1.2; letter-spacing:-0.5px; }}
.quote-author {{ font-size:40px; font-weight:700; color:{cs["accent"]}; }}
.translation-block {{ background:{cs["block2"]}; }}
.translation-text {{ font-size:48px; font-weight:500; color:{cs["text2"]}; line-height:1.4; }}
.translation-author {{ font-size:40px; font-weight:700; color:{cs["accent"]}; }}
"""
    body = f"""
<div class="topbar"><div class="rubric">📖 Quote</div></div>
<div class="blocks">
  <div class="block quote-block">
    <div class="quote-text">"{data.get("quote_en","")}"</div>
    <div class="quote-author">— {data.get("author","")}</div>
  </div>
  <div class="block translation-block">
    <div class="translation-text">"{data.get("quote_ua","")}"</div>
    <div class="translation-author">— {data.get("author","")}</div>
  </div>
</div>"""
    return html_wrap(css, body)


def build_situation(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.phrases-list {{ display:flex; flex-direction:column; gap:11px; flex:1; position:relative; z-index:1; }}
.phrase-row {{ background:{cs["block1"]}; border-radius:20px; padding:22px 40px;
  display:flex; flex-direction:column; justify-content:center; gap:8px; flex:1; }}
.phrase-en {{ font-size:42px; font-weight:800; color:{cs["text1"]}; line-height:1.2; letter-spacing:-0.3px; }}
.phrase-ua {{ font-size:40px; font-weight:500; color:{cs["accent"]}; line-height:1.2; }}
"""
    situation = data.get("situation", "")
    phrases   = data.get("phrases", [])
    rows = ""
    for p in phrases[:5]:
        rows += f"""
  <div class="phrase-row">
    <div class="phrase-en">{p.get("en","")}</div>
    <div class="phrase-ua">{p.get("ua","")}</div>
  </div>"""
    body = f"""
<div class="topbar"><div class="rubric">✈️ {situation}</div></div>
<div class="phrases-list">{rows}
</div>"""
    return html_wrap(css, body)


def build_chat_expressions(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.phrases-list {{ display:flex; flex-direction:column; gap:11px; flex:1; position:relative; z-index:1; }}
.phrase-row {{ background:{cs["block1"]}; border-radius:20px; padding:22px 40px;
  display:flex; flex-direction:column; justify-content:center; gap:8px; flex:1; }}
.phrase-en {{ font-size:42px; font-weight:800; color:{cs["text1"]}; line-height:1.2; }}
.phrase-ua {{ font-size:40px; font-weight:500; color:{cs["accent"]}; line-height:1.2; }}
"""
    expressions = data.get("expressions", [])
    rows = ""
    for e in expressions[:5]:
        rows += f"""
  <div class="phrase-row">
    <div class="phrase-en">{e.get("en","")}</div>
    <div class="phrase-ua">{e.get("ua","")}</div>
  </div>"""
    body = f"""
<div class="topbar"><div class="rubric">💬 Chat Expressions</div></div>
<div class="phrases-list">{rows}
</div>"""
    return html_wrap(css, body)


def build_synonyms_battle(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.words-list {{ display:flex; flex-direction:column; gap:14px; flex:1; position:relative; z-index:1; }}
.word-row {{ background:{cs["block1"]}; border-radius:24px; padding:28px 44px;
  display:flex; flex-direction:column; justify-content:center; gap:10px; flex:1; }}
.word-en {{ font-size:58px; font-weight:800; color:{cs["text1"]}; letter-spacing:-1px; line-height:1.1; }}
.word-meaning {{ font-size:40px; font-weight:500; color:{cs["accent"]}; line-height:1.3; }}
.word-ua {{ font-size:40px; font-weight:500; color:{cs["text2"]}; line-height:1.2; }}
"""
    words = data.get("words", [])
    rows = ""
    for w in words[:3]:
        rows += f"""
  <div class="word-row">
    <div class="word-en">{w.get("en","")}</div>
    <div class="word-meaning">{w.get("meaning","")}</div>
    <div class="word-ua">{w.get("ua","")}</div>
  </div>"""
    body = f"""
<div class="topbar"><div class="rubric">⚔️ Synonyms Battle</div></div>
<div class="words-list">{rows}
</div>"""
    return html_wrap(css, body)


def build_motivation(data: dict, cs: dict) -> str:
    css = BASE_CSS.format(bg=cs["bg"], wave=cs["wave_color"], rubric=cs["rubric"]) + f"""
.blocks {{ display:flex; flex-direction:column; gap:20px; position:absolute;
  top:50%; left:80px; right:80px; transform:translateY(-50%); z-index:1; }}
.block {{ height:430px; border-radius:28px; padding:0 56px;
  display:flex; flex-direction:column; justify-content:center; gap:16px; }}
.quote-block {{ background:{cs["block1"]}; }}
.quote-text {{ font-size:52px; font-weight:800; color:{cs["text1"]}; line-height:1.2; letter-spacing:-0.5px; }}
.quote-author {{ font-size:40px; font-weight:700; color:{cs["accent"]}; }}
.translation-block {{ background:{cs["block2"]}; }}
.translation-text {{ font-size:48px; font-weight:500; color:{cs["text2"]}; line-height:1.4; }}
.translation-author {{ font-size:40px; font-weight:700; color:{cs["accent"]}; }}
"""
    body = f"""
<div class="topbar"><div class="rubric">🚀 Motivation</div></div>
<div class="blocks">
  <div class="block quote-block">
    <div class="quote-text">"{data.get("quote_en","")}"</div>
    <div class="quote-author">— {data.get("author","")}</div>
  </div>
  <div class="block translation-block">
    <div class="translation-text">"{data.get("quote_ua","")}"</div>
    <div class="translation-author">— {data.get("author","")}</div>
  </div>
</div>"""
    return html_wrap(css, body)


BUILDERS = {
    "daily_phrase":     build_daily_phrase,
    "word_pack":        build_word_pack,
    "fun_fact":         build_fun_fact,
    "quote":            build_quote,
    "situation":        build_situation,
    "chat_expressions": build_chat_expressions,
    "synonyms_battle":  build_synonyms_battle,
    "motivation":       build_motivation,
}


# ──────────────────────────────────────────────
# PLAYWRIGHT — HTML → PNG
# ──────────────────────────────────────────────
async def render_card(html: str) -> bytes:
    """Рендерить HTML в PNG, повертає bytes (не зберігає на диск)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page    = await browser.new_page(viewport={"width": 1080, "height": 1350})
        await page.set_content(html, wait_until="networkidle")
        await asyncio.sleep(0.5)  # Чекаємо поки шрифт завантажиться
        png_bytes = await page.screenshot(type="png", full_page=False)
        await browser.close()

    # Перевіряємо розмір
    size_mb = len(png_bytes) / 1024 / 1024
    log.info(f"📸 PNG rendered: {size_mb:.2f} MB")
    if size_mb > 10:
        log.warning(f"⚠️ PNG too large ({size_mb:.2f} MB), Telegram may reject it")

    return png_bytes


# ──────────────────────────────────────────────
# TELEGRAM — ПУБЛІКАЦІЯ
# ──────────────────────────────────────────────
async def send_to_telegram(png_bytes: bytes, rubric: str) -> bool:
    """Надсилає PNG в Telegram з retry ×3."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    url,
                    data={"chat_id": TELEGRAM_CHAT_ID},
                    files={"photo": (f"{rubric}.png", png_bytes, "image/png")},
                )
                if resp.status_code == 200:
                    log.info(f"✅ Telegram: sent [{rubric}] successfully")
                    return True
                else:
                    log.error(f"❌ Telegram attempt {attempt}: status {resp.status_code} — {resp.text}")
        except Exception as e:
            log.error(f"❌ Telegram attempt {attempt} exception: {e}")

        if attempt < 3:
            await asyncio.sleep(5 * attempt)

    log.error(f"❌ Telegram: failed to send [{rubric}] after 3 attempts")
    return False


# ──────────────────────────────────────────────
# ГОЛОВНА ФУНКЦІЯ ПУБЛІКАЦІЇ
# ──────────────────────────────────────────────
async def publish_card(rubric: str, redis_client):
    history_mgr = HistoryManager(redis_client)
    start_time  = time.time()

    log.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info(f"🚀 Starting [{rubric}] at {datetime.now().strftime('%H:%M:%S')}")

    # Захист від паралельних запусків
    if not await history_mgr.acquire_lock(rubric):
        log.warning(f"⚠️ Lock exists for [{rubric}], skipping (already running)")
        return

    try:
        # 1. Отримуємо історію
        history = await history_mgr.get_used(rubric)
        log.info(f"📚 History for [{rubric}]: {len(history)} items")

        # 2. Генеруємо контент
        log.info(f"🤖 Generating content for [{rubric}]...")
        data = await generate_content(rubric, history)
        log.info(f"✅ Content generated: {json.dumps(data, ensure_ascii=False)[:200]}")

        # 3. Будуємо HTML
        cs      = COLOR_SCHEMES[rubric]
        builder = BUILDERS[rubric]
        html    = builder(data, cs)

        # 4. Рендеримо PNG
        log.info(f"🎨 Rendering PNG for [{rubric}]...")
        png_bytes = await render_card(html)

        # 5. Публікуємо в Telegram
        log.info(f"📤 Sending to Telegram [{rubric}]...")
        success = await send_to_telegram(png_bytes, rubric)

        # 6. Зберігаємо в історію тільки якщо успішно
        if success:
            # Зберігаємо ключове слово/тему для уникнення повторів
            history_key = json.dumps(data, ensure_ascii=False)[:100]
            await history_mgr.add_used(rubric, history_key)

        elapsed = time.time() - start_time
        log.info(f"⏱️ [{rubric}] completed in {elapsed:.1f}s | success={success}")

    except Exception as e:
        log.error(f"❌ CRITICAL ERROR in [{rubric}]: {e}", exc_info=True)
    finally:
        await history_mgr.release_lock(rubric)
        log.info(f"🔓 Lock released for [{rubric}]")


# ──────────────────────────────────────────────
# KEEP-ALIVE PING (Web Service)
# ──────────────────────────────────────────────
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Keep-alive ping sent OK")

    def log_message(self, format, *args):
        pass  # Вимикаємо стандартні логи HTTP сервера


def start_keep_alive_server():
    port   = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    log.info(f"🌐 HTTP server running on port {port}")
    server.serve_forever()


async def keep_alive_server():
    """Запускає keep-alive сервер в окремому треді щоб не блокувати asyncio."""
    thread = threading.Thread(target=start_keep_alive_server, daemon=True)
    thread.start()
    log.info("🌐 Keep-alive thread started")


async def self_ping():
    """Бот сам себе пінгує кожні 5 хвилин щоб Render не засинав."""
    # Зовнішній URL має більший пріоритет — Render не засинає від зовнішніх запитів
    external_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    port = int(os.environ.get("PORT", 10000))
    url = external_url if external_url else f"http://0.0.0.0:{port}/"
    await asyncio.sleep(30)  # Чекаємо поки сервер запуститься
    log.info(f"🔄 Self-ping will use URL: {url}")
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(url)
            log.info(f"🔄 Keep-alive ping sent → {url}")
        except Exception as e:
            log.warning(f"⚠️ Self-ping failed: {e}")
        await asyncio.sleep(300)  # Кожні 5 хвилин


# ──────────────────────────────────────────────
# ПЛАНУВАЛЬНИК
# ──────────────────────────────────────────────
async def scheduler(redis_client):
    """Перевіряє щохвилини — чи час публікувати картку."""
    log.info("⏰ Scheduler started")
    published_today = set()

    while True:
        now  = datetime.now()
        hour = now.hour

        # Скидаємо список опублікованих о 00:00
        if hour == 0 and now.minute == 0:
            published_today.clear()
            log.info("🔄 Reset published_today for new day")

        # Перевіряємо чи є рубрика для цієї години
        if hour in SCHEDULE and hour not in published_today:
            rubric = SCHEDULE[hour]
            published_today.add(hour)
            log.info(f"⏰ Time to publish [{rubric}] at {now.strftime('%H:%M')}")
            asyncio.create_task(publish_card(rubric, redis_client))

        await asyncio.sleep(60)


# ──────────────────────────────────────────────
# ТОЧКА ВХОДУ
# ──────────────────────────────────────────────
async def main():
    log.info("🤖 English A2 Bot starting...")

    # Upstash Redis через чистий HTTP — нуль C-залежностей
    redis_client = UpstashRedis()
    try:
        await redis_client.ping()
        log.info("✅ Upstash Redis connected")
    except Exception as e:
        log.error(f"❌ Upstash Redis connection failed: {e}")
        raise

    # Запускаємо keep-alive сервер і планувальник паралельно
    await asyncio.gather(
        keep_alive_server(),
        self_ping(),
        scheduler(redis_client),
    )


if __name__ == "__main__":
    asyncio.run(main())
