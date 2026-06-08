import os
import base64
import uuid
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request
from openai import OpenAI

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://telegram-ai-bot-amzh.onrender.com")
DOCS_URL = os.environ.get("DOCS_URL", "https://ttcfj55t6v-commits.github.io/dressme-ai-docs/")
DB_PATH = os.environ.get("DB_PATH", "dressme_ai.db")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable")

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


TARIFFS = {
    "style_start": {
        "title": "DressMe Style Pack START",
        "price": "199.00",
        "label": "START — 199 ₽",
        "units": 3,
        "unit_name": "образа",
        "description": "До 3 образов: анализ, рекомендации, визуализация улучшенных образов, список изменений.",
    },
    "style_plus": {
        "title": "DressMe Style Pack PLUS",
        "price": "390.00",
        "label": "PLUS — 390 ₽",
        "units": 6,
        "unit_name": "образов",
        "description": "До 6 образов: анализ, визуализация, рекомендации по аксессуарам, дополнительные советы по стилю.",
    },
    "style_premium": {
        "title": "DressMe Style Pack PREMIUM",
        "price": "690.00",
        "label": "PREMIUM — 690 ₽",
        "units": 10,
        "unit_name": "образов",
        "description": "До 10 образов: анализ, визуализация, обувь, сумки, очки, украшения, подробная стилизация.",
    },
    "wardrobe_start": {
        "title": "AI Гардероб START",
        "price": "990.00",
        "label": "Гардероб START — 990 ₽",
        "units": 20,
        "unit_name": "вещей",
        "description": "До 20 вещей: что оставить, что убрать, что ушить/укоротить, лучшие комплекты, список покупок.",
    },
    "wardrobe_smart": {
        "title": "AI Гардероб SMART",
        "price": "1990.00",
        "label": "Гардероб SMART — 1990 ₽",
        "units": 50,
        "unit_name": "вещей",
        "description": "До 50 вещей: полный разбор, анализ посадки при фото на фигуре, капсула, приоритетный список покупок.",
    },
    "wardrobe_vip": {
        "title": "AI Гардероб VIP",
        "price": "3990.00",
        "label": "Гардероб VIP — 3990 ₽",
        "units": 100,
        "unit_name": "вещей",
        "description": "До 100 вещей: полный аудит гардероба, обувь, сумки, украшения, очки, максимальное количество комплектов, стратегия стиля.",
    },
}

SYSTEM_PROMPT_FREE = """
Ты — профессиональный AI-стилист в Telegram.
Сделай бесплатный разбор одного образа по фото.
Структура ответа:
1. Общее впечатление
2. Что удачно
3. Что можно улучшить
4. Цвета, посадка, аксессуары
5. Итоговая оценка от 1 до 10
Пиши по-русски, мягко, конкретно, без критики тела.
""".strip()

SYSTEM_PROMPT_PAID_STYLE = """
Ты — профессиональный AI-стилист DressMe AI.
Пользователь оплатил платный Style Pack. Дай более подробный разбор образа и идею визуального улучшения.

Структура ответа:
1. Общее впечатление
2. Что в образе удачно
3. Что можно улучшить
4. Цвета и сочетания
5. Посадка, пропорции и силуэт
6. Обувь, сумка и аксессуары
7. Как сделать образ современнее
8. Визуализация улучшенного образа текстом: подробно опиши, как должен выглядеть обновленный вариант
9. Список конкретных изменений
10. Итоговая оценка от 1 до 10

Важно:
- не критикуй тело;
- не ставь диагнозы;
- не обещай невозможный результат;
- пиши как дорогой, но понятный стилист.
""".strip()

SYSTEM_PROMPT_WARDROBE = """
Ты — профессиональный AI-стилист DressMe AI.
Пользователь оплатил AI Гардероб и присылает фото вещи или образа.
Проанализируй вещь/образ как элемент гардероба.

Структура ответа:
1. Что это за вещь и какое у нее настроение
2. Стоит оставить / убрать / ушить / укоротить / заменить
3. С чем сочетать
4. Какие комплекты можно собрать
5. Чего не хватает рядом с этой вещью
6. Ошибки, которых лучше избегать
7. Итог: роль вещи в гардеробе

Если вещь сфотографирована на фигуре — оцени посадку. Если не на фигуре — честно скажи, что посадку оценить нельзя.
""".strip()

PRICES_TEXT = """
✨ Тарифы DressMe AI

Бесплатно:
📸 Разбор 1 образа

DressMe Style Pack:

START — 199 ₽
✨ Улучшение до 3 образов

PLUS — 390 ₽
✨ Улучшение до 6 образов

PREMIUM — 690 ₽
✨ Улучшение до 10 образов

AI Гардероб:

START — 990 ₽
До 20 вещей

SMART — 1990 ₽
До 50 вещей

VIP — 3990 ₽
До 100 вещей
""".strip()


# ---------- Database ----------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                free_used INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                tariff_key TEXT NOT NULL,
                payment_id TEXT UNIQUE,
                total_units INTEGER NOT NULL,
                used_units INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT
            )
        """)
        conn.commit()


init_db()


def ensure_user(chat_id: int):
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(chat_id, free_used, created_at) VALUES (?, 0, ?)",
            (chat_id, datetime.utcnow().isoformat()),
        )
        conn.commit()


def is_free_used(chat_id: int) -> bool:
    ensure_user(chat_id)
    with db() as conn:
        row = conn.execute("SELECT free_used FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        return bool(row["free_used"])


def mark_free_used(chat_id: int):
    ensure_user(chat_id)
    with db() as conn:
        conn.execute("UPDATE users SET free_used = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()


def activate_purchase(chat_id: int, tariff_key: str, payment_id: str):
    tariff = TARIFFS[tariff_key]
    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO purchases(chat_id, tariff_key, payment_id, total_units, used_units, status, created_at)
            VALUES (?, ?, ?, ?, 0, 'active', ?)
            """,
            (chat_id, tariff_key, payment_id, tariff["units"], datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_active_purchase(chat_id: int):
    with db() as conn:
        row = conn.execute(
            """
            SELECT * FROM purchases
            WHERE chat_id = ? AND status = 'active' AND used_units < total_units
            ORDER BY id ASC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        return row


def consume_unit(purchase_id: int):
    with db() as conn:
        conn.execute("UPDATE purchases SET used_units = used_units + 1 WHERE id = ?", (purchase_id,))
        row = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        if row["used_units"] >= row["total_units"]:
            conn.execute("UPDATE purchases SET status = 'completed' WHERE id = ?", (purchase_id,))
        conn.commit()
        return row


def get_balance_text(chat_id: int) -> str:
    purchase = get_active_purchase(chat_id)
    if not purchase:
        return "Активных оплаченных пакетов нет."
    tariff = TARIFFS[purchase["tariff_key"]]
    left = purchase["total_units"] - purchase["used_units"]
    return f"Активный тариф: {tariff['title']}\nОсталось: {left} из {purchase['total_units']} {tariff['unit_name']}."


# ---------- Telegram helpers ----------

def send_message(chat_id: int, text: str, reply_markup=None) -> None:
    payload = {"chat_id": chat_id, "text": text[:3900]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=20)


def answer_callback_query(callback_query_id: str) -> None:
    requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": callback_query_id}, timeout=20)


def get_command(text: str) -> str:
    if not text:
        return ""
    return text.strip().split()[0].split("@")[0].lower()


def prices_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "START: 3 образа — 199 ₽", "callback_data": "buy_style_start"}],
            [{"text": "PLUS: 6 образов — 390 ₽", "callback_data": "buy_style_plus"}],
            [{"text": "PREMIUM: 10 образов — 690 ₽", "callback_data": "buy_style_premium"}],
            [{"text": "Гардероб START — 990 ₽", "callback_data": "buy_wardrobe_start"}],
            [{"text": "Гардероб SMART — 1990 ₽", "callback_data": "buy_wardrobe_smart"}],
            [{"text": "Гардероб VIP — 3990 ₽", "callback_data": "buy_wardrobe_vip"}],
        ]
    }


def upsell_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ START: 3 образа — 199 ₽", "callback_data": "buy_style_start"}],
            [{"text": "🔥 PLUS: 6 образов — 390 ₽", "callback_data": "buy_style_plus"}],
            [{"text": "💎 PREMIUM: 10 образов — 690 ₽", "callback_data": "buy_style_premium"}],
            [{"text": "👗 AI Гардероб", "callback_data": "show_wardrobe"}],
        ]
    }


# ---------- AI ----------

def get_telegram_file_url(file_id: str) -> str:
    response = requests.get(f"{TELEGRAM_API_URL}/getFile", params={"file_id": file_id}, timeout=20)
    response.raise_for_status()
    file_path = response.json()["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"


def download_image_as_base64(file_url: str) -> str:
    response = requests.get(file_url, timeout=30)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


def analyze_photo(image_base64: str, caption: str, prompt: str) -> str:
    user_text = caption.strip() or "Проанализируй фото."
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_text},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_base64}"},
                ],
            },
        ],
    )
    return response.output_text


def ask_ai_text(user_text: str) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT_FREE},
            {"role": "user", "content": user_text},
        ],
    )
    return response.output_text


# ---------- YooKassa ----------

def tariff_key_from_callback(callback_data: str) -> str | None:
    return {
        "buy_style_start": "style_start",
        "buy_style_plus": "style_plus",
        "buy_style_premium": "style_premium",
        "buy_wardrobe_start": "wardrobe_start",
        "buy_wardrobe_smart": "wardrobe_smart",
        "buy_wardrobe_vip": "wardrobe_vip",
    }.get(callback_data)


def create_yookassa_payment(chat_id: int, tariff_key: str) -> str:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        raise RuntimeError("YooKassa environment variables are not configured")

    tariff = TARIFFS[tariff_key]
    payload = {
        "amount": {"value": tariff["price"], "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": f"{PUBLIC_BASE_URL}/payment-return",
        },
        "description": f"DressMe AI: {tariff['title']}",
        "metadata": {
            "chat_id": str(chat_id),
            "tariff_key": tariff_key,
            "tariff_title": tariff["title"],
        },
    }

    response = requests.post(
        "https://api.yookassa.ru/v3/payments",
        json=payload,
        auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        headers={"Idempotence-Key": str(uuid.uuid4())},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["confirmation"]["confirmation_url"]


def get_yookassa_payment(payment_id: str) -> dict:
    response = requests.get(
        f"https://api.yookassa.ru/v3/payments/{payment_id}",
        auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def send_payment_link(chat_id: int, tariff_key: str):
    tariff = TARIFFS[tariff_key]
    payment_url = create_yookassa_payment(chat_id, tariff_key)
    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 Оплатить через ЮKassa", "url": payment_url}],
            [{"text": "📄 Документы", "url": DOCS_URL}],
        ]
    }
    send_message(
        chat_id,
        f"✨ {tariff['title']}\n\n{tariff['description']}\n\nСтоимость: {tariff['label']}\n\nНажмите кнопку ниже для оплаты.",
        reply_markup=keyboard,
    )


def handle_tariff_click(chat_id: int, data: str):
    if data == "show_wardrobe":
        send_message(
            chat_id,
            "👗 AI Гардероб\n\n"
            "START — 990 ₽: до 20 вещей\n"
            "SMART — 1990 ₽: до 50 вещей\n"
            "VIP — 3990 ₽: до 100 вещей\n\n"
            "Напишите /prices, чтобы выбрать тариф.",
            reply_markup=prices_keyboard(),
        )
        return

    tariff_key = tariff_key_from_callback(data)
    if not tariff_key:
        send_message(chat_id, PRICES_TEXT, reply_markup=prices_keyboard())
        return

    try:
        send_payment_link(chat_id, tariff_key)
    except Exception as exc:
        print(f"YooKassa payment creation error: {exc}", flush=True)
        send_message(chat_id, "Не получилось создать ссылку на оплату. Проверь настройки ЮKassa в Render.")


# ---------- Routes ----------

@app.route("/", methods=["GET"])
def healthcheck():
    return "Bot is running", 200


@app.route("/payment-return", methods=["GET"])
def payment_return():
    return "Оплата обработана. Вернитесь в Telegram-бот DressMe AI.", 200


@app.route("/yookassa", methods=["POST"])
def yookassa_webhook():
    event = request.get_json(silent=True) or {}
    try:
        event_type = event.get("event")
        obj = event.get("object") or {}
        payment_id = obj.get("id")

        if event_type != "payment.succeeded" or not payment_id:
            return "ok", 200

        payment = get_yookassa_payment(payment_id)
        if payment.get("status") != "succeeded" or not payment.get("paid"):
            return "ok", 200

        metadata = payment.get("metadata") or {}
        chat_id = int(metadata.get("chat_id"))
        tariff_key = metadata.get("tariff_key")
        tariff = TARIFFS[tariff_key]

        activate_purchase(chat_id, tariff_key, payment_id)

        send_message(
            chat_id,
            "✅ Оплата прошла успешно!\n\n"
            f"Активирован тариф: {tariff['title']}.\n"
            f"Доступно: {tariff['units']} {tariff['unit_name']}.\n\n"
            "Теперь отправьте фотографии для работы по выбранному тарифу. "
            "Лучше присылать фото в хорошем освещении и по возможности в полный рост.",
        )
        return "ok", 200

    except Exception as exc:
        print(f"YooKassa webhook error: {exc}", flush=True)
        return "ok", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    callback_query = data.get("callback_query")
    if callback_query:
        callback_query_id = callback_query.get("id")
        callback_data = callback_query.get("data")
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        if callback_query_id:
            answer_callback_query(callback_query_id)
        if chat_id and callback_data:
            handle_tariff_click(chat_id, callback_data)
        return "ok", 200

    message = data.get("message") or data.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not chat_id:
        return "ok", 200

    ensure_user(chat_id)

    text = message.get("text") or ""
    caption = message.get("caption") or ""
    photos = message.get("photo") or []
    command = get_command(text)

    if command == "/start":
        send_message(
            chat_id,
            "Привет! Я DressMe AI — твой AI-стилист ✨\n\n"
            "Пришли фото образа в полный рост, и я сделаю бесплатный разбор.\n\n"
            "Команды:\n"
            "/prices — тарифы\n"
            "/balance — остаток по пакету\n"
            "/docs — документы",
        )
        return "ok", 200

    if command == "/prices":
        send_message(chat_id, PRICES_TEXT, reply_markup=prices_keyboard())
        return "ok", 200

    if command == "/balance":
        send_message(chat_id, get_balance_text(chat_id))
        return "ok", 200

    if command == "/docs":
        send_message(chat_id, f"Документы DressMe AI:\n{DOCS_URL}")
        return "ok", 200

    if photos:
        try:
            best_photo = photos[-1]
            file_url = get_telegram_file_url(best_photo["file_id"])
            image_base64 = download_image_as_base64(file_url)

            active = get_active_purchase(chat_id)

            if active:
                tariff_key = active["tariff_key"]
                is_wardrobe = tariff_key.startswith("wardrobe_")
                prompt = SYSTEM_PROMPT_WARDROBE if is_wardrobe else SYSTEM_PROMPT_PAID_STYLE

                tariff = TARIFFS[tariff_key]
                send_message(chat_id, f"Фото получила ✨ Работаю по тарифу {tariff['title']}...")

                answer = analyze_photo(image_base64, caption, prompt)
                send_message(chat_id, answer)

                updated = consume_unit(active["id"])
                left = updated["total_units"] - updated["used_units"]

                if left > 0:
                    send_message(chat_id, f"Готово ✨ Осталось: {left} из {updated['total_units']} {tariff['unit_name']}.")
                else:
                    send_message(
                        chat_id,
                        "Пакет полностью использован ✨\n\n"
                        "Можно выбрать новый тариф:",
                        reply_markup=prices_keyboard(),
                    )
                return "ok", 200

            if not is_free_used(chat_id):
                send_message(chat_id, "Фото получила ✨ Делаю бесплатный разбор образа...")
                answer = analyze_photo(image_base64, caption, SYSTEM_PROMPT_FREE)
                mark_free_used(chat_id)
                send_message(chat_id, answer)

                send_message(
                    chat_id,
                    "Бесплатный разбор использован ✨\n\n"
                    "Чтобы получить визуализации, подробные рекомендации и разбор нескольких образов, выберите пакет ниже:",
                    reply_markup=upsell_keyboard(),
                )
                return "ok", 200

            send_message(
                chat_id,
                "Бесплатный разбор уже использован ✨\n\n"
                "Чтобы продолжить, выберите платный тариф:",
                reply_markup=prices_keyboard(),
            )
            return "ok", 200

        except Exception as exc:
            print(f"Photo AI error: {exc}", flush=True)
            send_message(chat_id, "Ой, не получилось обработать фото. Попробуйте отправить фото еще раз в хорошем качестве.")
            return "ok", 200

    if text:
        try:
            answer = ask_ai_text(text)
        except Exception as exc:
            print(f"Text AI error: {exc}", flush=True)
            answer = "Ой, у меня временная ошибка. Попробуйте позже."
        send_message(chat_id, answer)
        return "ok", 200

    send_message(chat_id, "Пришлите фото образа в полный рост, и я сделаю стилистический разбор ✨")
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
