"""
Тест подключения к Groq API.
Запуск: python test_groq.py
"""

import os
import socket
import urllib.request
import httpx
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).parent / '.env')

api_key = os.environ.get('GROQ_API_KEY', '').strip()
model   = os.environ.get('GROQ_MODEL', '').strip()

print(f"API key : {'OK (' + api_key[:8] + '...)' if api_key else 'НЕ ЗАДАН'}")
print(f"Model   : {model or 'НЕ ЗАДАНА'}")

if not api_key:
    print("\n[ОШИБКА] GROQ_API_KEY не задан в .env")
    exit(1)

# ── Проверка сетевой доступности ──────────────────────────────────────────────
print("\nПроверяю доступность api.groq.com...")
socket.setdefaulttimeout(5)
try:
    urllib.request.urlopen("https://api.groq.com")
    print("  [OK] Хост доступен")
except urllib.error.HTTPError as e:
    # HTTP-ошибка (401/403/404) означает что сервер отвечает — доступ есть
    print(f"  [OK] Хост отвечает (HTTP {e.code}) — соединение работает")
except Exception as e:
    print(f"  [ОШИБКА] Хост недоступен: {e}")
    print("\n  Вывод: скорее всего региональная блокировка (РФ).")
    print("  Решения:")
    print("    1. Настройте VPN и запускайте сервер через него")
    print("    2. Используйте прокси — задайте переменную окружения HTTPS_PROXY=http://...")
    exit(1)

# ── Проверка моделей ──────────────────────────────────────────────────────────
MODELS_TO_TRY = [
    "openai/gpt-oss-120b",
    model,
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
if proxy:
    print(f"Прокси  : {proxy.split('@')[-1]}")  # показываем только хост без пароля
    client = Groq(api_key=api_key, http_client=httpx.Client(proxy=proxy))
else:
    print("Прокси  : не задан")
    client = Groq(api_key=api_key)

seen = set()
queue = [m for m in MODELS_TO_TRY if m and not (m in seen or seen.add(m))]

print()
for m in queue:
    print(f"  Пробую {m} ...")
    try:
        resp = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "Say: ok"}],
            max_tokens=5,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip()
        print(f"  [OK] Ответ: {answer}")
        print(f"\n>>> Рабочая модель: {m}")
        print(f"    Вставьте в .env: GROQ_MODEL={m}")
        break
    except Exception as e:
        print(f"  [ОШИБКА] {type(e).__name__}: {e}")
else:
    print("\n[!] Ни одна модель не ответила.")
    print("    Причина: 403 на все модели при доступном хосте =")
    print("    API ключ верный, но аккаунт заблокирован для вашего региона/IP.")
    print("    Решение: VPN + новый ключ, созданный через VPN.")
