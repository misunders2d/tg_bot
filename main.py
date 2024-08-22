from dotenv import load_dotenv
load_dotenv('.env')

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import os, requests
from io import BytesIO
from typing import Final, Literal

from deta import Deta
from openai import OpenAI, NotFoundError
from openai.types.beta.thread import Thread

import modules

ASSISTANT_ID: Final = os.getenv('ASSISTANT_ID')
OPENAI_KEY: Final = os.getenv('AI_KEY')
TG_KEY: Final = os.getenv('TG_KEY')
BOT_HANDLE = os.getenv('BOT_HANDLE')
DETA_ID: Final = os.getenv('DETA_KEY')
ADMIN_CHAT: int = os.getenv('ADMIN_CHAT')

client: OpenAI = OpenAI(api_key = OPENAI_KEY)

deta_base: Deta = Deta(DETA_ID)

current_sessions: dict = {}

# Command to provide help information
async def assist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help function that shows available commands to the user"""
    if os.path.isfile('help.txt'):
        with open('help.txt', 'r') as file:
            reply_text: str = file.read()
    else:
        reply_text: str = "Sorry, no help yet"
    await update.message.reply_text(reply_text)

def retrieve_thread(chat_id: str) -> Thread:
    """
    function to retrieve tg chat's message thread from openai or create a new one if the chat is new to the bot
    Creates a thread if it didn't exist before or got expired
    """
    def create_thread():
        current_thread: Thread = client.beta.threads.create()
        return current_thread
    
    # first, get voice value from local or remote db and assign a default value:
    if not (voice:=current_sessions.get(chat_id,{}).get('voice')):
        if not (voice:=modules.check_thread(chat_id, deta_base)[1]):
            voice: str = 'onyx'
    
    if not (current_thread:= current_sessions.get(chat_id,{}).get('thread')):
        # thread not found in local "current_sessions dict", check in deta db:

        if not (chat_thread_id:=modules.check_thread(chat_id, deta_base)[0]):
            # thread_id not found in remote deta db either, create one
            current_thread: Thread = create_thread(chat_id)
            modules.push_to_deta(chat_id, current_thread.id, deta_base, voice = voice) #update thread id in remote db
            chat_thread_id = current_thread.id
        else:
            try:
                current_thread = client.beta.threads.retrieve(thread_id = chat_thread_id) # check if the stored thread still exists in OpenAI
            except NotFoundError:
                new_thread = create_thread() # create a new thread in OpenAI
                modules.push_to_deta(chat_id, new_thread.id, deta_base, voice = voice) # replace old thread id in remote db with newly created one
                current_thread = client.beta.threads.retrieve(thread_id = new_thread.id) # retrieve new thread from OpenAI
    else:
        try:
            current_thread = client.beta.threads.retrieve(thread_id = current_thread.id) # check if the stored thread still exists in OpenAI
        except NotFoundError:
            new_thread = create_thread() # create a new thread in OpenAI
            modules.push_to_deta(chat_id, new_thread.id, deta_base, voice = voice) # replace old thread id in remote db with newly created one
            current_thread = client.beta.threads.retrieve(thread_id = new_thread.id) # retrieve new thread from OpenAI


    #update local current_sessions dict with new thread and voice values
    current_sessions.update(
        {chat_id:{
            'thread':current_thread,
            'voice':voice
            }
        }
        )
    return current_thread

async def send_action(chat_id, context: ContextTypes.DEFAULT_TYPE, type:Literal['typing','recording'] = 'typing'):
    """Function to send 'typing...' action."""
    await context.bot.send_chat_action(chat_id, action=type, )

async def describe_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Separate function that is triggered by a photo in the message. The photo is processed
        using vision capabilities of OpenAI
    """
    if not update.message:
        return

    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print(chat_type, chat_id) # for test bot
    if not (text:= update.message.caption):
        text = 'What is in these images?'
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        current_thread = retrieve_thread(chat_id)
        media_file = update.message.photo[-1]
        caption = update.message.caption
        media_url = await context.bot.getFile(media_file.file_id)
        image_info_task = modules.image(
            media_url.file_path, caption, client,
            assistant_id = ASSISTANT_ID,
            thread_id=current_thread.id,
            voice_bool = False)
        await send_action(chat_id, context, type = 'typing')
        image_info = await image_info_task
        try:
            await update.message.reply_text(image_info, parse_mode='MarkdownV2')
        except:
            try:
                await update.message.reply_text(image_info, parse_mode='Markdown')
            except:
                await update.message.reply_text(image_info)

async def accept_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, current_voice: str = 'onyx'):
    """Separate function to process voice conversations"""
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print(chat_type, chat_id) # for test bot
    if not (current_voice:= current_sessions.get(str(chat_id),{}).get('voice')):
        current_voice = 'onyx'
    if not (text:= update.message.caption):
        text = ''
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        voice_content = await context.bot.getFile(update.message.voice.file_id)
        voice_file = requests.get(voice_content.file_path)
        voice_bytes = BytesIO(voice_file.content)
        voice_bytes.name = 'voice.ogg'
        voice_bytes.seek(0)
        text_version = modules.transcribe_audio(voice_bytes, client = client)
        current_thread = retrieve_thread(chat_id)
        response_task: str = modules.process_text(
            text_input=text_version,
            client = client,
            assistant_id=ASSISTANT_ID,
            thread_id=current_thread.id,
            voice_bool = True,
            voice = current_voice)
        await send_action(chat_id, context, type = 'record_audio')
        response, text_response = await response_task
        await update.message.reply_voice(voice = response, caption = text_response)

async def process_replied_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    try:
        reply_text = update.message.reply_to_message.text
        re_from = update.message.reply_to_message.from_user.username
    except:
        return ''
    if not reply_text:
        return ''
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print('processing reply message')
        print(chat_type, chat_id, re_from, reply_text) # for test bot

    return f"""RE: from {re_from}\n{reply_text}\n\n"""

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main text processing function, that prepares data for the "process_text" function"""
    chat_type: str = update.message.chat.type
    chat_id: str = str(update.message.chat.id)
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print(chat_type, chat_id) # for test bot
    try:
        text = update.message.text
    except:
        text = 'What is in these images?'
    reply_text = await process_replied_message(update, context)
    text = reply_text + text
    current_thread = retrieve_thread(chat_id)
    # Handle group messages only if bot is mentioned
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private' or BOT_HANDLE.replace('@','') in reply_text:
        if update.message.photo:
            await describe_photo(update, context)
            return

        cleaned_text: str = text.replace(BOT_HANDLE, '').strip()
        response_task: str = modules.process_text(
            text_input=cleaned_text,
            client = client,
            assistant_id=ASSISTANT_ID,
            thread_id=current_thread.id,
        )
        # Reply to the user
        await send_action(chat_id, context, type = 'typing')
        response = await response_task
        try:
            await update.message.reply_text(response, parse_mode='MarkdownV2')
        except:
            try:
                await update.message.reply_text(response, parse_mode='Markdown')
            except:
                await update.message.reply_text(response)

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Separate function that is triggered by "/create" command and passes prompt to OpenAI to generate image
        using "modules.image" function
    """
    chat_id = update.message.chat.id
    chat_type: str = update.message.chat.type
    if BOT_HANDLE == '@my_temp_bot_for_testing_bot':
        print(chat_type, chat_id) # for test bot

    if not (text:= update.message.text):
        text = 'What is in these images?'
    if (chat_type in ('supergroup','group') and BOT_HANDLE in text) or chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action='upload_photo')
        prompt = text.replace('/create ','').replace(BOT_HANDLE,'')
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
    return [int(x['key']) for x in result]

async def push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin function used to push messages (updates and warnings) to all chats"""
    if update.message.chat.id == ADMIN_CHAT:
        chat_ids = get_chat_ids(deta_base=deta_base)
        if len(chat_ids) > 0:
            for chat in chat_ids:
                await context.bot.send_message(chat_id = chat, text = update.message.text.replace('/push','').strip())
        await context.bot.send_message(chat_id = ADMIN_CHAT, text = f'Message sent to {len(chat_ids)} chats')

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
        current_sessions[str(chat_id)]['voice'] = voice
        await update.message.reply_text(f'Changed the voice of the assistant to "{voice}"')
    else:
        await update.message.reply_text(f'Please send me a "/voice_change" command followed by one of the voices: {voices_str}')

async def delete_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    current_thread = retrieve_thread(str(chat_id))
    try:
        client.beta.threads.delete(thread_id = current_thread.id)
        await update.message.reply_text(f'Thread {current_thread.id} successfully deleted. You can start a new conversation')
    except NotFoundError:
        await update.message.reply_text(f'Thread {current_thread.id} does not exist, skipping')
    except Exception as e:
        await context.bot.send_message(chat_id = ADMIN_CHAT, text = f'Error while deleting thread {current_thread.id}:\n{e}')

async def log_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logging function. Also sends logs to ADMIN_CHAT in Telegram"""
    log_text = f'Update {update} caused error {context.error}\nChat ID = {update.message.chat}, text = {update.message.text}, chat type = {update.message.chat.type}'
    print(log_text)
    await context.bot.send_message(chat_id = ADMIN_CHAT, text = log_text)

def main():
    # build the app
    app = Application.builder().token(TG_KEY).build()

    # Register command handlers
    app.add_handler(CommandHandler('help', assist_command))
    app.add_handler(CommandHandler('create', create))
    app.add_handler(CommandHandler('push', push))
    app.add_handler(CommandHandler('delete', delete_history))
    app.add_handler(CommandHandler('voice_change', voice_change))

    # Register message handler
    app.add_handler(MessageHandler((filters.TEXT | filters.REPLY), process_message))
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
