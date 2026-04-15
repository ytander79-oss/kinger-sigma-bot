import random
import os
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7089083244  # вставь сюда свой ID

# Состояние бота
state = {
    "active_chat": None,      # куда сейчас отправляем сообщения
    "chats": {},              # известные боту чаты {chat_id: название}
    "reply_to": None          # ID сообщения на которое отвечаем
}

# =================== УТИЛИТЫ ===================

def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

async def send_admin(context, text):
    await context.bot.send_message(chat_id=ADMIN_ID, text=text)

# =================== КОМАНДЫ АДМИНА ===================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "Привет! Команды:\n"
        "/chats — список чатов\n"
        "/switch <id> — переключиться на чат\n"
        "/current — текущий активный чат\n"
        "/read <кол-во> — последние сообщения\n\n"
        "Просто напиши текст — отправлю в активный чат\n"
        "Кинь аудио — отправлю голосовым\n"
        "Кинь видео — отправлю кружком"
    )

async def cmd_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not state["chats"]:
        await update.message.reply_text("Бот ещё не добавлен ни в один чат.")
        return
    text = "Известные чаты:\n"
    for chat_id, name in state["chats"].items():
        active = " ✅" if chat_id == state["active_chat"] else ""
        text += f"{name}{active}\nID: `{chat_id}`\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text("Укажи ID чата: /switch -100123456789")
        return
    try:
        chat_id = int(context.args[0])
        if chat_id not in state["chats"]:
            await update.message.reply_text("Такой чат не найден. Проверь /chats")
            return
        state["active_chat"] = chat_id
        name = state["chats"][chat_id]
        await update.message.reply_text(f"Переключился на: {name}")
    except ValueError:
        await update.message.reply_text("Неверный ID чата.")

async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not state["active_chat"]:
        await update.message.reply_text("Активный чат не выбран. Используй /switch")
        return
    name = state["chats"].get(state["active_chat"], "Неизвестно")
    await update.message.reply_text(f"Активный чат: {name}\nID: `{state['active_chat']}`", parse_mode="Markdown")

# =================== ОТПРАВКА СООБЩЕНИЙ ===================

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    reply_to = state.get("reply_to")
    state["reply_to"] = None

    await context.bot.send_message(
        chat_id=state["active_chat"],
        text=update.message.text,
        reply_to_message_id=reply_to
    )

async def handle_admin_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    file = update.message.audio or update.message.voice or update.message.document
    if not file:
        return

    file_obj = await context.bot.get_file(file.file_id)
    file_bytes = await file_obj.download_as_bytearray()

    await context.bot.send_voice(
        chat_id=state["active_chat"],
        voice=bytes(file_bytes)
    )
    await update.message.reply_text("Голосовое отправлено ✅")

async def handle_admin_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if update.effective_chat.type != "private": return
    if not state["active_chat"]:
        await update.message.reply_text("Сначала выбери чат через /switch")
        return

    file = update.message.video or update.message.video_note or update.message.document
    if not file:
        return

    file_obj = await context.bot.get_file(file.file_id)
    file_bytes = await file_obj.download_as_bytearray()

    await context.bot.send_video_note(
        chat_id=state["active_chat"],
        video_note=bytes(file_bytes)
    )
    await update.message.reply_text("Кружок отправлен ✅")

# =================== ВХОДЯЩИЕ СООБЩЕНИЯ В ГРУППАХ ===================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id

    # Запоминаем чат
    if chat_id not in state["chats"]:
        state["chats"][chat_id] = chat.title or chat.username or str(chat_id)
        await send_admin(context, f"Новый чат добавлен: {state['chats'][chat_id]}\nID: `{chat_id}`")

# =================== ВХОДЯЩИЕ СООБЩЕНИЯ В ЛС БОТУ ===================

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сообщения от других пользователей в лс боту — пересылаем админу
    if update.effective_user.id == ADMIN_ID:
        return  # это сам админ, не пересылаем

    user = update.effective_user
    name = user.full_name
    username = f"@{user.username}" if user.username else ""
    text = update.message.text or "[не текст]"

    forwarded = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💬 Сообщение в ЛС от {name} {username}:\n\n{text}\n\nОтветить: /reply_{update.message.message_id}_{user.id}"
    )

async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    # /reply_<message_id>_<user_id>
    try:
        parts = update.message.text.split("_")
        message_id = int(parts[1])
        user_id = int(parts[2])

        state["reply_to"] = message_id
        state["active_chat"] = user_id

        await update.message.reply_text(
            f"Следующее сообщение отправлю как ответ в ЛС этому пользователю.\nПиши:"
        )
    except Exception:
        await update.message.reply_text("Ошибка команды ответа.")

# =================== ЗАПУСК ===================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chats", cmd_chats))
    app.add_handler(CommandHandler("switch", cmd_switch))
    app.add_handler(CommandHandler("current", cmd_current))

    # Ответ в ЛС другому пользователю
    app.add_handler(MessageHandler(
        filters.Regex(r"^/reply_\d+_\d+$"), cmd_reply
    ))

    # Сообщения от админа в личке боту
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_text
    ))
    app.add_handler(MessageHandler(
        (filters.AUDIO | filters.VOICE | filters.Document.AUDIO) & filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_audio
    ))
    app.add_handler(MessageHandler(
        (filters.VIDEO | filters.VIDEO_NOTE) & filters.ChatType.PRIVATE & filters.User(ADMIN_ID),
        handle_admin_video
    ))

    # Сообщения в ЛС от других пользователей
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & ~filters.User(ADMIN_ID),
        handle_private_message
    ))

    # Сообщения в группах — просто запоминаем чат
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS,
        handle_group_message
    ))

    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()