from dotenv import load_dotenv
load_dotenv('.env')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import os, requests, pickle
from io import BytesIO
from typing import Final

from deta import Deta
from openai import OpenAI

import workers

ASSISTANT_ID: Final = os.getenv('ASSISTANT_ID')
OPENAI_KEY: Final = os.getenv('AI_KEY')
TG_KEY: Final = os.getenv('TG_KEY')
BOT_HANDLE = '@my_temp_bot_for_testing_bot'
DETA_ID: Final = os.getenv('DETA_KEY')

client = OpenAI(api_key = OPENAI_KEY)

deta_base = Deta(DETA_ID)
# client.beta.threads.delete('thread_fSravSQAjuQw0HwKQMjeKKmH')

current_sessions = {}

# Command to provide help information
async def assist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Here comes the help')

def retrieve_thread(chat_id):
    if chat_id not in current_sessions:
        if not (chat_thread_id:=workers.check_thread(chat_id, deta_base)):
            chat_thread = client.beta.threads.create()
            chat_thread_id = chat_thread.id
            workers.push_thread(chat_id, chat_thread_id, deta_base)
        current_thread = client.beta.threads.retrieve(thread_id = chat_thread_id)
        current_sessions.update({chat_id:current_thread})
    else:
        current_thread = current_sessions.get(chat_id)
    return current_thread

def generate_response(user_input: str, current_thread: str, voice: bool = False) -> str:
    normalized_input: str = user_input.lower()

    return workers.text(
        text_input = normalized_input, 
        client = client,
        assistant_id=ASSISTANT_ID,
        thread_id = current_thread.id,
        voice = voice
    )

async def describe_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = []
    chat_id: str = str(update.message.chat.id)
    current_thread = retrieve_thread(chat_id)

    media_files = update.message.photo
    images = [files.append(await context.bot.getFile(media.file_id)) for _,media in enumerate(media_files)]
    print(files)
    # image_paths = [x for x in [images[-1].file_path]]
    # files.append(image_paths)
    # print(files)
    # image_info = workers.image(
    #     image_paths, caption, client,
    #     assistant_id = ASSISTANT_ID,
    #     thread_id=current_thread.id,
    #     voice = False)
    # print(image_info)
    # await update.message.reply_text(image_info)

async def accept_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id: str = str(update.message.chat.id)
    voice = await context.bot.getFile(update.message.voice.file_id)
    voice_file = requests.get(voice.file_path)
    voice_bytes = BytesIO(voice_file.content)
    voice_bytes.name = 'voice.ogg'
    voice_bytes.seek(0)
    text_version = workers.transcribe_audio(voice_bytes, client = client)
    current_thread = retrieve_thread(chat_id)
    bot_response = generate_response(text_version, current_thread, voice = True)
    await update.message.reply_voice(voice = bot_response)

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    text: str = update.message.text

    current_thread = retrieve_thread(chat_id)

    # Handle group messages only if bot is mentioned
    if chat_type == 'group':
        if BOT_HANDLE in text:
            cleaned_text: str = text.replace(BOT_HANDLE, '').strip()
            response: str = generate_response(cleaned_text, current_thread)
        else:
            return  # Ignore messages where bot is not mentioned in a group
    else:
        response: str = generate_response(text, current_thread)

    # Reply to the user
    # print('Bot response:', response)
    await update.message.reply_text(response)


# Log errors
async def log_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')


# Start the bot
if __name__ == '__main__':
    app = Application.builder().token(TG_KEY).build()

    # Register command handlers
    app.add_handler(CommandHandler('help', assist_command))

    # Register message handler
    app.add_handler(MessageHandler(filters.TEXT, process_message))

    app.add_handler(MessageHandler(filters.PHOTO, describe_photo))

    app.add_handler(MessageHandler(filters.VOICE, accept_voice))

    # Register error handler
    app.add_error_handler(log_error)

    print('Starting polling...')
    # Run the bot
    app.run_polling(poll_interval=2)