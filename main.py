from dotenv import load_dotenv
load_dotenv('.env')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import os, requests, asyncio
from io import BytesIO
from typing import Final, Literal

from deta import Deta
from openai import OpenAI

import modules

ASSISTANT_ID: Final = os.getenv('ASSISTANT_ID')
OPENAI_KEY: Final = os.getenv('AI_KEY')
TG_KEY: Final = os.getenv('TG_KEY')
BOT_HANDLE = os.getenv('BOT_HANDLE')
DETA_ID: Final = os.getenv('DETA_KEY')

client = OpenAI(api_key = OPENAI_KEY)

deta_base = Deta(DETA_ID)

current_sessions = {}

# Command to provide help information
async def assist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Here comes the help', parse_mode='Markdown')

def retrieve_thread(chat_id):
    if chat_id not in current_sessions:
        if not (chat_thread_id:=modules.check_thread(chat_id, deta_base)):
            chat_thread = client.beta.threads.create()
            chat_thread_id = chat_thread.id
            modules.push_thread(chat_id, chat_thread_id, deta_base)
        current_thread = client.beta.threads.retrieve(thread_id = chat_thread_id)
        current_sessions.update({chat_id:current_thread})
    else:
        current_thread = current_sessions.get(chat_id)
    return current_thread

async def send_action(chat_id, context: ContextTypes.DEFAULT_TYPE, type:Literal['typing','recording'] = 'typing'):
    """Function to send 'typing...' action."""
    await context.bot.send_chat_action(chat_id, action=type)

def generate_response(user_input: str, current_thread: str, voice: bool = False) -> str:
    normalized_input: str = user_input.lower()

    return modules.process_text(
        text_input = normalized_input, 
        client = client,
        assistant_id=ASSISTANT_ID,
        thread_id = current_thread.id,
        voice = voice
    )

async def describe_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id: str = str(update.message.chat.id)
    current_thread = retrieve_thread(chat_id)
    await send_action(chat_id, context, type = 'typing')
    media_file = update.message.photo[-1]
    caption = update.message.caption
    media_url = await context.bot.getFile(media_file.file_id)
    image_info = modules.image(
        media_url.file_path, caption, client,
        assistant_id = ASSISTANT_ID,
        thread_id=current_thread.id,
        voice = False)
    await update.message.reply_text(image_info, parse_mode='Markdown')

async def accept_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id: str = str(update.message.chat.id)
    voice = await context.bot.getFile(update.message.voice.file_id)
    await send_action(chat_id, context, type = 'record_audio')
    voice_file = requests.get(voice.file_path)
    voice_bytes = BytesIO(voice_file.content)
    voice_bytes.name = 'voice.ogg'
    voice_bytes.seek(0)
    text_version = modules.transcribe_audio(voice_bytes, client = client)
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
            await send_action(chat_id, context, type = 'typing')
            cleaned_text: str = text.replace(BOT_HANDLE, '').strip()
            response: str = generate_response(cleaned_text, current_thread)
        else:
            return  # Ignore messages where bot is not mentioned in a group
    else:
        await send_action(chat_id, context, type = 'typing')
        response: str = generate_response(text, current_thread)

    # Reply to the user
    await update.message.reply_text(response, parse_mode='Markdown')

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    chat_type: str = update.message.chat.type

    try:
        user_message = update.message.text
    except:
        user_message = ''
    if (chat_type == 'group' and BOT_HANDLE in user_message) or True:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action='upload_photo')
        prompt = user_message.replace('/create ','')
        try:
            #DALL-E generation:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size="1024x1024"
                )
            image_url_dall_e = response.data[0].url
            await context.bot.send_message(chat_id=chat_id,text ="Here's what DALL-E came up with")
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo = image_url_dall_e)
            await context.bot.send_message(chat_id=chat_id,text =f"Revised prompt:\n{response.data[0].revised_prompt}")
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id,text =f"Oops, this didn't work out, here's the error message\n{e}")
        
def get_chat_ids(deta_base: Deta = deta_base):
    result = deta_base.Base('chat_ids').fetch().items
    return [x['key'] for x in result]

async def push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids = get_chat_ids(deta_base=deta_base)
    for chat in chat_ids:
        await context.bot.send_message(chat_id = chat, text = update.message.text.replace('/push','').strip())

# Log errors
async def log_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

def main():
    app = Application.builder().token(TG_KEY).build()

    # Register command handlers
    app.add_handler(CommandHandler('help', assist_command))
    app.add_handler(CommandHandler('create', create))
    app.add_handler(CommandHandler('push', push))

    # Register message handler
    app.add_handler(MessageHandler(filters.TEXT, process_message))

    app.add_handler(MessageHandler(filters.PHOTO, describe_photo))

    app.add_handler(MessageHandler(filters.VOICE, accept_voice))

    # Register error handler
    app.add_error_handler(log_error)

    print('Starting polling...')
    # Run the bot
    app.run_polling(poll_interval=2)


# Start the bot
if __name__ == '__main__':
    main()
