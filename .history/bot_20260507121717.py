# ============================================================
#  SDU Event Bot — приглашение студентов на мероприятие 9 мая
#  Версия: python-telegram-bot 21.x (async)
# ============================================================

import csv
import os
import logging
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ──────────────────────────────────────────────
# НАСТРОЙКИ — вставь свои значения здесь
# ──────────────────────────────────────────────

# 1. Получи токен у @BotFather в Telegram и вставь сюда:
TOKEN = os.getenv("TOKEN")

# 2. Вставь сюда свой Telegram ID (число).
#    Как узнать свой ID: напиши боту @userinfobot в Telegram.
ADMIN_ID = os.getenv("ADMIN_ID")

# Имя файла для хранения данных гостей
CSV_FILE = "guests.csv"

# ──────────────────────────────────────────────
# СОСТОЯНИЯ для ConversationHandler
# ConversationHandler — это способ вести диалог по шагам.
# Каждое число — это "шаг" разговора.
# ──────────────────────────────────────────────
ASKING_NAME = 1      # Шаг 1: бот ждёт имя пользователя
ASKING_ANSWER = 2    # Шаг 2: бот ждёт ответ (приду / не приду)
CHANGING = 3         # Шаг 3: бот ждёт новый ответ при /change

# ──────────────────────────────────────────────
# ЛОГИРОВАНИЕ — помогает видеть ошибки в консоли
# ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С CSV
# ══════════════════════════════════════════════

def csv_exists() -> bool:
    """Проверяет, существует ли файл guests.csv."""
    return os.path.exists(CSV_FILE)


def init_csv():
    """
    Создаёт файл guests.csv с заголовками, если он ещё не существует.
    Это нужно при первом запуске бота.
    """
    if not csv_exists():
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Записываем строку-заголовок
            writer.writerow(["telegram_id", "username", "name", "answer", "datetime"])


def find_guest(telegram_id: int) -> dict | None:
    """
    Ищет гостя в CSV по его telegram_id.
    Возвращает словарь с данными гостя или None, если не найден.
    """
    if not csv_exists():
        return None
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["telegram_id"] == str(telegram_id):
                return row  # нашли — возвращаем
    return None  # не нашли


def save_guest(telegram_id: int, username: str, name: str, answer: str):
    """
    Сохраняет нового гостя в CSV.
    Если гость уже есть — обновляет его запись.
    """
    init_csv()  # убеждаемся, что файл существует

    rows = []  # сюда соберём все строки
    found = False  # флаг: нашли ли мы этого гостя

    # Читаем все существующие записи
    if csv_exists():
        with open(CSV_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["telegram_id"] == str(telegram_id):
                    # Обновляем данные этого гостя
                    row["username"] = username
                    row["name"] = name
                    row["answer"] = answer
                    row["datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    found = True
                rows.append(row)

    if not found:
        # Гость новый — добавляем его в список
        rows.append({
            "telegram_id": str(telegram_id),
            "username": username,
            "name": name,
            "answer": answer,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Записываем все строки обратно в файл
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["telegram_id", "username", "name", "answer", "datetime"]
        )
        writer.writeheader()
        writer.writerows(rows)


def get_all_guests() -> list[dict]:
    """Возвращает список всех гостей из CSV."""
    if not csv_exists():
        return []
    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ══════════════════════════════════════════════
# КЛАВИАТУРЫ (кнопки)
# ══════════════════════════════════════════════

def get_answer_keyboard() -> ReplyKeyboardMarkup:
    """
    Создаёт клавиатуру с двумя кнопками.
    resize_keyboard=True — кнопки будут компактного размера.
    one_time_keyboard=True — клавиатура скроется после нажатия.
    """
    keyboard = [["✅ Приду", "❌ Не приду"]]
    return ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=True
    )


# ══════════════════════════════════════════════
# ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /start.
    Отправляет приветственное сообщение и начинает диалог.
    Возвращает ASKING_NAME — переходим к шагу "спроси имя".
    """
    user = update.effective_user
    telegram_id = user.id

    # Проверяем, отвечал ли этот человек раньше
    existing = find_guest(telegram_id)
    if existing:
        await update.message.reply_text(
            "Ты уже отправил ответ 😊\n\n"
            f"Твой ответ: {existing['answer']}\n\n"
            "Если хочешь изменить ответ — напиши /change"
        )
        return ConversationHandler.END  # завершаем диалог

    # Новый пользователь — отправляем приветствие
    welcome_text = (
        "🎉 Happy 7 May! 🎉\n\n"
        "Желаем тебе:\n"
        "0 bugs 🐛\n"
        "100% luck 🍀\n"
        "high GPA 📚\n"
        "stable mental health 🧠\n\n"
        "В честь праздника приглашаем тебя на небольшое мероприятие, "
        "которое пройдет 9 мая в SDU University 💙\n\n"
        "Будем рады тебя видеть!\n"
        "Напиши, пожалуйста, придёшь ли ты 😊"
    )
    await update.message.reply_text(welcome_text)

    # Спрашиваем имя
    await update.message.reply_text(
        "Для начала, напиши своё имя 👇",
        reply_markup=ReplyKeyboardRemove(),  # убираем старые кнопки, если были
    )

    return ASKING_NAME  # переходим к следующему шагу


async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 1: получаем имя пользователя.
    Сохраняем его во временное хранилище context.user_data.
    Возвращает ASKING_ANSWER — переходим к шагу "спроси ответ".
    """
    name = update.message.text.strip()

    # Сохраняем имя временно (пока не получим ответ)
    context.user_data["name"] = name

    # Показываем кнопки
    await update.message.reply_text(
        f"Ты придёшь на мероприятие 9 мая?",
        reply_markup=get_answer_keyboard(),
    )

    return ASKING_ANSWER  # переходим к следующему шагу


async def received_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг 2: получаем ответ (приду / не приду).
    Сохраняем всё в CSV.
    Возвращает ConversationHandler.END — диалог завершён.
    """
    user = update.effective_user
    answer_text = update.message.text.strip()

    # Проверяем, что ответ корректный (нажата одна из кнопок)
    valid_answers = ["✅ Приду", "❌ Не приду"]
    if answer_text not in valid_answers:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки ниже 👇",
            reply_markup=get_answer_keyboard(),
        )
        return ASKING_ANSWER  # остаёмся на этом шаге

    name = context.user_data.get("name", "Неизвестно")
    username = f"@{user.username}" if user.username else "нет username"

    # Сохраняем в CSV
    save_guest(
        telegram_id=user.id,
        username=username,
        name=name,
        answer=answer_text,
    )

    # Отвечаем пользователю
    if answer_text == "✅ Приду":
        response = "Отлично! Ждём тебя 9 мая! 🎉\nДо встречи 💙"
    else:
        response = "Жаль 😔 Будем рады видеть тебя в следующий раз!"

    await update.message.reply_text(
        response,
        reply_markup=ReplyKeyboardRemove(),  # убираем кнопки
    )

    return ConversationHandler.END  # завершаем диалог


async def change_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработчик команды /change.
    Позволяет изменить ответ, если пользователь уже отвечал.
    """
    user = update.effective_user
    existing = find_guest(user.id)

    if not existing:
        await update.message.reply_text(
            "Ты ещё не отвечал на приглашение.\n"
            "Напиши /start чтобы начать."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Твой текущий ответ: {existing['answer']}\n\n"
        "Хочешь изменить? Выбери новый ответ:",
        reply_markup=get_answer_keyboard(),
    )

    return CHANGING  # переходим к шагу изменения ответа


async def received_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Шаг изменения ответа: получаем новый ответ и обновляем CSV.
    """
    user = update.effective_user
    new_answer = update.message.text.strip()

    valid_answers = ["✅ Приду", "❌ Не приду"]
    if new_answer not in valid_answers:
        await update.message.reply_text(
            "Пожалуйста, используй кнопки 👇",
            reply_markup=get_answer_keyboard(),
        )
        return CHANGING

    # Обновляем запись в CSV (save_guest сам найдёт и обновит)
    existing = find_guest(user.id)
    username = f"@{user.username}" if user.username else "нет username"
    save_guest(
        telegram_id=user.id,
        username=username,
        name=existing["name"],
        answer=new_answer,
    )

    await update.message.reply_text(
        f"Ответ обновлён: {new_answer} ✅",
        reply_markup=ReplyKeyboardRemove(),
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /cancel — отменяет текущий диалог."""
    await update.message.reply_text(
        "Диалог отменён. Напиши /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def list_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /list — показывает список гостей.
    ТОЛЬКО для администратора (проверяем по telegram_id).
    """
    user = update.effective_user

    # Проверка: только админ может смотреть список
    if user.id != ADMIN_ID:
        await update.message.reply_text("⛔ У тебя нет доступа к этой команде.")
        return

    guests = get_all_guests()

    if not guests:
        await update.message.reply_text("Пока никто не отвечал на приглашение.")
        return

    # Разделяем на "придут" и "не придут"
    coming = [g for g in guests if g["answer"] == "✅ Приду"]
    not_coming = [g for g in guests if g["answer"] == "❌ Не приду"]

    # Формируем текст для ответа
    lines = []
    lines.append(f"📋 Всего ответов: {len(guests)}\n")

    lines.append(f"✅ Придут ({len(coming)}):")
    if coming:
        for g in coming:
            lines.append(f"  • {g['name']} ({g['username']})")
    else:
        lines.append("  (никого)")

    lines.append(f"\n❌ Не придут ({len(not_coming)}):")
    if not_coming:
        for g in not_coming:
            lines.append(f"  • {g['name']} ({g['username']})")
    else:
        lines.append("  (никого)")

    await update.message.reply_text("\n".join(lines))


# ══════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ — запуск бота
# ══════════════════════════════════════════════

def main():
    """Запускает бота в режиме polling."""

    # Убеждаемся, что CSV файл создан
    init_csv()

    # Создаём приложение (главный объект бота)
    app = Application.builder().token(TOKEN).build()

    # ── Диалог для /start ──
    # ConversationHandler ведёт пользователя по шагам
    start_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASKING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)
            ],
            ASKING_ANSWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_answer)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # ── Диалог для /change ──
    change_conv = ConversationHandler(
        entry_points=[CommandHandler("change", change_answer)],
        states={
            CHANGING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_change)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрируем все обработчики в боте
    app.add_handler(start_conv)
    app.add_handler(change_conv)
    app.add_handler(CommandHandler("list", list_guests))

    # Запускаем бота (polling = постоянно проверяет новые сообщения)
    logger.info("Бот запущен! Нажми Ctrl+C чтобы остановить.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


# Точка входа: запускаем main() при старте скрипта
if __name__ == "__main__":
    main()