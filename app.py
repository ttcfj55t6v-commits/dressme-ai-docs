import os
import base64
import uuid
import requests
from flask import Flask, request
from openai import OpenAI

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://telegram-ai-bot-amzh.onrender.com")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN environment variable")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable")

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


SYSTEM_PROMPT = """
Ты — профессиональный AI-стилист в Telegram.

Твоя задача — анализировать фото образа человека и давать понятные, честные и деликатные рекомендации по стилю.

Отвечай по структуре:

1. Общее впечатление от образа
2. Что в образе удачно
3. Что можно улучшить
4. Цвета и сочетания
5. Посадка, пропорции и силуэт
6. Обувь, сумка и аксессуары
7. Как сделать образ современнее
8. Итоговая оценка от 1 до 10

Пиши простым женским языком, без грубости.
Не критикуй тело человека.
Не ставь медицинские диагнозы.
Если фото плохое — попроси прислать фото в полный рост при хорошем освещении.
""".strip()


TARIFFS = {
    "style_start": {
        "title": "DressMe Style Pack START",
        "price": "199.00",
        "label": "START — 199 ₽",
        "description": "До 3 образов: анализ, рекомендации, визуализация улучшенных образов, список изменений.",
    },
    "style_plus": {
        "title": "DressMe Style Pack PLUS",
        "price": "390.00",
        "label": "PLUS — 390 ₽",
        "description": "До 6 образов: анализ, визуализация, рекомендации по аксессуарам, дополнительные советы по стилю.",
    },
    "style_premium": {
        "title": "DressMe Style Pack PREMIUM",
        "price": "690.00",
        "label": "PREMIUM — 690 ₽",
        "description": "До 10 образов: анализ, визуализация, обувь, сумки, очки, украшения, подробная стилизация.",
    },
    "wardrobe_start": {
        "title": "AI Гардероб START",
        "price": "990.00",
        "label": "Гардероб START — 990 ₽",
        "description": "До 20 вещей: что оставить, что убрать, что ушить/укоротить, лучшие комплекты, список покупок.",
    },
    "wardrobe_smart": {
        "title": "AI Гардероб SMART",
        "price": "1990.00",
        "label": "Гардероб SMART — 1990 ₽",
        "description": "До 50 вещей: полный разбор, анализ посадки при фото на фигуре, капсула, приоритетный список покупок.",
    },
    "wardrobe_vip": {
        "title": "AI Гардероб VIP",
        "price": "3990.00",
        "label": "Гардероб VIP — 3990 ₽",
        "description": "До 100 вещей: полный аудит гардероба, обувь, сумки, украшения, очки, максимальное количество комплектов, стратегия стиля.",
    },
}


PRICES_TEXT = """
✨ Тарифы DressMe AI

Бесплатно:
📸 Разбор 1 образа
— что удачно
— что улучшить
— цвета, посадка, аксессуары
— итоговая оценка

DressMe Style Pack:

START — 199 ₽
✨ Улучшение до 3 образов
— визуализация каждого образа
— список изменений
— рекомендации стилиста

PLUS — 390 ₽
✨ Улучшение до 6 образов
— визуализация каждого образа
— рекомендации
— аксессуары
— список изменений

PREMIUM — 690 ₽
✨ Улучшение до 10 образов
— визуализация каждого образа
— обувь
— сумки
— очки
— украшения
— подробная стилизация

AI Гардероб:

START — 990 ₽
До 20 вещей
— что оставить
— что убрать
— что ушить/укоротить
— лучшие комплекты
— список покупок

SMART — 1990 ₽
До 50 вещей
— полный разбор
— анализ посадки, если вещи сфотографированы на фигуре
— капсула
— приоритетный список покупок

VIP — 3990 ₽
До 100 вещей
— полный аудит гардероба
— обувь, сумки, украшения, очки
— максимальное количество комплектов
— стратегия стиля
""".strip()


def send_message(chat_id: int, text: str, reply_markup=None) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text[:3900],
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json=payload,
        timeout=20,
    )


def answer_callback_query(callback_query_id: str) -> None:
    requests.post(
        f"{TELEGRAM_API_URL}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id},
        timeout=20,
    )


def get_command(text: str) -> str:
    if not text:
        return ""

    first_word = text.strip().split()[0]
    command = first_word.split("@")[0]

    return command.lower()


def upsell_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "✨ START: 3 образа — 199 ₽", "callback_data": "buy_style_start"}],
            [{"text": "🔥 PLUS: 6 образов — 390 ₽", "callback_data": "buy_style_plus"}],
            [{"text": "💎 PREMIUM: 10 образов — 690 ₽", "callback_data": "buy_style_premium"}],
            [{"text": "👗 AI Гардероб", "callback_data": "show_wardrobe"}],
        ]
    }


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


def get_telegram_file_url(file_id: str) -> str:
    response = requests.get(
        f"{TELEGRAM_API_URL}/getFile",
        params={"file_id": file_id},
        timeout=20,
    )
    response.raise_for_status()

    result = response.json()
    file_path = result["result"]["file_path"]

    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"


def download_image_as_base64(file_url: str) -> str:
    response = requests.get(file_url, timeout=30)
    response.raise_for_status()

    image_base64 = base64.b64encode(response.content).decode("utf-8")
    return image_base64


def analyze_style_photo(image_base64: str, caption: str = "") -> str:
    user_text = caption.strip() or "Проанализируй мой образ по фото."

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )

    return response.output_text


def tariff_key_from_callback(callback_data: str) -> str | None:
    mapping = {
        "buy_style_start": "style_start",
        "buy_style_plus": "style_plus",
        "buy_style_premium": "style_premium",
        "buy_wardrobe_start": "wardrobe_start",
        "buy_wardrobe_smart": "wardrobe_smart",
        "buy_wardrobe_vip": "wardrobe_vip",
    }
    return mapping.get(callback_data)


def create_yookassa_payment(chat_id: int, tariff_key: str) -> str:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        raise RuntimeError("YooKassa environment variables are not configured")

    tariff = TARIFFS[tariff_key]
    idempotence_key = str(uuid.uuid4())

    payload = {
        "amount": {
            "value": tariff["price"],
            "currency": "RUB",
        },
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
        "receipt": {
            "customer": {
                "email": "customer@example.com"
            },
            "items": [
                {
                    "description": tariff["title"][:128],
                    "quantity": "1.00",
                    "amount": {
                        "value": tariff["price"],
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_subject": "service",
                    "payment_mode": "full_payment"
                }
            ]
        }
    }

    # Если чек в ЮKassa у самозанятой не подключен, блок receipt может вызвать ошибку.
    # Тогда ниже мы автоматически повторим создание платежа без receipt.
    url = "https://api.yookassa.ru/v3/payments"
    headers = {"Idempotence-Key": idempotence_key}

    response = requests.post(
        url,
        json=payload,
        auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        headers=headers,
        timeout=30,
    )

    if response.status_code >= 400:
        # Повтор без receipt на случай, если фискализация через ЮKassa не используется.
        payload.pop("receipt", None)
        response = requests.post(
            url,
            json=payload,
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers={"Idempotence-Key": str(uuid.uuid4())},
            timeout=30,
        )

    response.raise_for_status()
    data = response.json()
    return data["confirmation"]["confirmation_url"]


def get_yookassa_payment(payment_id: str) -> dict:
    response = requests.get(
        f"https://api.yookassa.ru/v3/payments/{payment_id}",
        auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def send_payment_link(chat_id: int, tariff_key: str) -> None:
    tariff = TARIFFS[tariff_key]
    payment_url = create_yookassa_payment(chat_id, tariff_key)

    text = (
        f"✨ {tariff['title']}\n\n"
        f"{tariff['description']}\n\n"
        f"Стоимость: {tariff['label']}\n\n"
        "Нажмите кнопку ниже, чтобы перейти к оплате через ЮKassa."
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "💳 Оплатить", "url": payment_url}],
            [{"text": "📄 Документы", "url": "https://ttcfj55t6v-commits.github.io/dressme-ai-docs/"}],
        ]
    }

    send_message(chat_id, text, reply_markup=keyboard)


def handle_tariff_click(chat_id: int, data: str) -> None:
    if data == "show_wardrobe":
        send_message(
            chat_id,
            "👗 AI Гардероб\n\n"
            "START — 990 ₽: до 20 вещей\n"
            "SMART — 1990 ₽: до 50 вещей\n"
            "VIP — 3990 ₽: до 100 вещей\n\n"
            "Важно: анализ посадки возможен только если вещь сфотографирована на фигуре.\n\n"
            "Напишите /prices, чтобы увидеть все тарифы.",
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
        send_message(
            chat_id,
            "Не получилось создать ссылку на оплату. Проверьте настройки ЮKassa в Render: "
            "YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY и PUBLIC_BASE_URL.",
        )


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

        # Дополнительно проверяем платеж напрямую в ЮKassa, а не доверяем только webhook.
        payment = get_yookassa_payment(payment_id)

        if payment.get("status") != "succeeded" or not payment.get("paid"):
            return "ok", 200

        metadata = payment.get("metadata") or {}
        chat_id = metadata.get("chat_id")
        tariff_key = metadata.get("tariff_key")
        tariff = TARIFFS.get(tariff_key)

        if chat_id and tariff:
            send_message(
                int(chat_id),
                "✅ Оплата прошла успешно!\n\n"
                f"Активирован тариф: {tariff['title']}.\n\n"
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

    text = message.get("text") or ""
    caption = message.get("caption") or ""
    photos = message.get("photo") or []
    command = get_command(text)

    if command == "/start":
        send_message(
            chat_id,
            "Привет! Я твой AI-стилист DressMe AI ✨\n\n"
            "Пришли мне фото своего образа в полный рост, и я разберу:\n"
            "— что удачно\n"
            "— что улучшить\n"
            "— какие аксессуары добавить\n"
            "— как сделать образ современнее.\n\n"
            "Чтобы посмотреть тарифы, напиши /prices.",
        )
        return "ok", 200

    if command == "/prices":
        send_message(chat_id, PRICES_TEXT, reply_markup=prices_keyboard())
        return "ok", 200

    if photos:
        try:
            send_message(chat_id, "Фото получила ✨ Анализирую образ...")

            best_photo = photos[-1]
            file_id = best_photo["file_id"]

            file_url = get_telegram_file_url(file_id)
            image_base64 = download_image_as_base64(file_url)

            answer = analyze_style_photo(image_base64, caption)
            send_message(chat_id, answer)

            send_message(
                chat_id,
                "✨ Хотите увидеть, как этот и другие ваши образы можно улучшить визуально?\n\n"
                "Я могу переработать ваши реальные комплекты и показать новые версии:\n\n"
                "START — до 3 образов за 199 ₽\n"
                "PLUS — до 6 образов за 390 ₽\n"
                "PREMIUM — до 10 образов за 690 ₽\n\n"
                "Выберите пакет ниже 👇",
                reply_markup=upsell_keyboard(),
            )

        except Exception as exc:
            print(f"Photo AI error: {exc}", flush=True)
            send_message(
                chat_id,
                "Ой, не получилось разобрать фото. Проверь логи Render или пришли фото еще раз в хорошем качестве.",
            )

        return "ok", 200

    if text:
        try:
            answer = ask_ai_text(text)
        except Exception as exc:
            print(f"Text AI error: {exc}", flush=True)
            answer = "Ой, у меня временная ошибка. Проверь ключ OpenAI, баланс и логи сервера."

        send_message(chat_id, answer)
        return "ok", 200

    send_message(
        chat_id,
        "Пришли мне фото образа в полный рост, и я сделаю стилистический разбор ✨",
    )
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
