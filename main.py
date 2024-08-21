from dotenv import load_dotenv
load_dotenv('.env')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import os, requests, asyncio
from io import BytesIO
from typing import Final, Literal

from deta import Deta
from openai import OpenAI
from openai.types.beta.thread import Thread

import modules

ASSISTANT_ID: Final = os.getenv('ASSISTANT_ID')
OPENAI_KEY: Final = os.getenv('AI_KEY')
TG_KEY: Final = os.getenv('TG_KEY')
BOT_HANDLE = os.getenv('BOT_HANDLE')
DETA_ID: Final = os.getenv('DETA_KEY')
ADMIN_CHAT: int = os.getenv('ADMIN_CHAT')

client = OpenAI(api_key = OPENAI_KEY)

deta_base = Deta(DETA_ID)

current_sessions = {}

# Command to provide help information
async def assist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help function that shows available commands to the user"""
    if os.path.isfile('help.txt'):
        with open('help.txt', 'r') as file:
            reply_text = file.read()
    else:
        reply_text = "Sorry, no help yet"
    await update.message.reply_text(reply_text)

def retrieve_thread(chat_id: str) -> Thread:
    """function to retrieve tg chat's message thread from openai or create a new one if the chat is new to the bot"""
    if not (current_thread:= current_sessions.get(chat_id,{}).get('thread')):
        if not (chat_thread_id:=modules.check_thread(chat_id, deta_base)[0]):
            chat_thread = client.beta.threads.create()
            chat_thread_id = chat_thread.id
            modules.push_to_deta(chat_id, chat_thread_id, deta_base)
        current_thread = client.beta.threads.retrieve(thread_id = chat_thread_id)
        current_sessions.update(
            {chat_id:{
                'thread':current_thread,
                'voice':modules.check_thread(chat_id, deta_base)[1]
                }
            }
            )
    return current_thread

async def send_action(chat_id, context: ContextTypes.DEFAULT_TYPE, type:Literal['typing','recording'] = 'typing'):
    """Function to send 'typing...' action."""
    await context.bot.send_chat_action(chat_id, action=type, )

def generate_response(user_input: str, current_thread: Thread, voice_bool: bool = False, current_voice:str = 'onyx') -> str:
    """Helper function that uses the "modules.process text" function to actually pass texts to OpenAI and retrieve completions"""
    normalized_input: str = user_input.lower()

    return modules.process_text(
        text_input = normalized_input, 
        client = client,
        assistant_id=ASSISTANT_ID,
        thread_id = current_thread.id,
        voice_bool = voice_bool,
        voice = current_voice
    )

async def describe_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Separate function that is triggered by a photo in the message. The photo is processed
        using vision capabilities of OpenAI
    """
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if not (text:= update.message.caption):
        text = 'What is in these images?'
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        current_thread = retrieve_thread(chat_id)
        await send_action(chat_id, context, type = 'typing')
        media_file = update.message.photo[-1]
        caption = update.message.caption
        media_url = await context.bot.getFile(media_file.file_id)
        image_info = modules.image(
            media_url.file_path, caption, client,
            assistant_id = ASSISTANT_ID,
            thread_id=current_thread.id,
            voice_bool = False)
        await update.message.reply_text(image_info, parse_mode='Markdown')

async def accept_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, current_voice: str = 'onyx'):
    """Separate function to process voice conversations"""
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if not (current_voice:= current_sessions.get(str(chat_id),{}).get('voice')):
        pass
    if not (text:= update.message.caption):
        text = ''
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        voice_content = await context.bot.getFile(update.message.voice.file_id)
        await send_action(chat_id, context, type = 'record_audio')
        voice_file = requests.get(voice_content.file_path)
        voice_bytes = BytesIO(voice_file.content)
        voice_bytes.name = 'voice.ogg'
        voice_bytes.seek(0)
        text_version = modules.transcribe_audio(voice_bytes, client = client)
        current_thread = retrieve_thread(chat_id)
        bot_response = generate_response(text_version, current_thread, voice_bool = True, current_voice = current_voice)
        await update.message.reply_voice(voice = bot_response)

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main text processing function, that prepares data for the "generate_response" function"""
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if not (text:= update.message.text):
        text = 'What is in these images?'
    current_thread = retrieve_thread(chat_id)
    # Handle group messages only if bot is mentioned
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        await send_action(chat_id, context, type = 'typing')
        cleaned_text: str = text.replace(BOT_HANDLE, '').strip()
        response: str = generate_response(cleaned_text, current_thread)

        # Reply to the user
        await update.message.reply_text(response, parse_mode='Markdown')

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Separate function that is triggered by "/create" command and passes prompt to OpenAI to generate image
        using "modules.image" function
    """
    chat_id = update.message.chat.id
    chat_type: str = update.message.chat.type
    if not (text:= update.message.text):
        text = 'What is in these images?'
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action='upload_photo')
        prompt = text.replace('/create ','')
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
    """Pull existing chat IDs from Deta db"""
    result = deta_base.Base('chat_ids').fetch().items
    return [x['key'] for x in result]

async def push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin function used to push messages (updates and warnings) to all chats"""
    if update.message.chat.id == ADMIN_CHAT:
        if os.path.isfile('chat_ids.py'):
            from chat_ids import chat_ids
        else:
            chat_ids = get_chat_ids(deta_base=deta_base)
        if len(chat_ids) > 0:
            for chat in chat_ids:
                await context.bot.send_message(chat_id = chat, text = update.message.text.replace('/push','').strip())
        await context.bot.send_message(chat_id = 330959414, text = f'Message sent to {len(chat_ids)} chats')

async def voice_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper function that allows to change voice of the assistant for each user separately"""
    chat_id = update.message.chat.id
    if (current_voice:= current_sessions.get(str(chat_id),{}).get('voice')):
        await update.message.reply_text(f'Your current voice is {current_voice}')
    voices = ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
    voices_str = ', '.join(voices)
    current_thread = retrieve_thread(str(chat_id))
    text = update.message.text.strip().lower()
    voice = text.replace('/voice_change','').strip()
    if voice in voices:
        modules.push_to_deta(chat_id = str(chat_id), thread_id = current_thread.id, deta_base=deta_base, voice = voice)
        await update.message.reply_text(f'Changed the voice of the assistant to "{voice}"')
    else:
        await update.message.reply_text(f'Please send me a "/voice_change" command followed by one of the voices: {voices_str}')

async def log_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logging function. Also sends logs to ADMIN_CHAT in Telegram"""
    print(f'Update {update} caused error {context.error}\n')
    await context.bot.send_message(chat_id = ADMIN_CHAT, text = f'Update {update} caused error {context.error}\n')

def main():
    # build the app
    app = Application.builder().token(TG_KEY).build()

    # Register command handlers
    app.add_handler(CommandHandler('help', assist_command))
    app.add_handler(CommandHandler('create', create))
    app.add_handler(CommandHandler('push', push))
    app.add_handler(CommandHandler('voice_change', voice_change))

    # Register message handler
    app.add_handler(MessageHandler(filters.TEXT, process_message))
    app.add_handler(MessageHandler(filters.PHOTO, describe_photo))
    app.add_handler(MessageHandler(filters.VOICE, accept_voice))

    # Register error handler
    app.add_error_handler(log_error)

    print('Started polling...')
    # Run the bot
    app.run_polling(poll_interval=2)


# Start the bot
if __name__ == '__main__':
    main()
