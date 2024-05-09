from deta import Deta
from openai import OpenAI
import time, os
import logging
from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

tg_token = os.getenv('TG_KEY')
ai_key = os.getenv('AI_KEY')
deta_key = os.getenv('DB_USERS')


GPT_MODEL = 'gpt-4-0125-preview'#'gpt-3.5-turbo'

deta = Deta(deta_key)
base = deta.Base('messages')
users = deta.Base('users')

client = OpenAI(api_key = ai_key)

# Define the error function
def error(update, context):
    logger.warning('\nUpdate "%s" caused error "%s"\n', update, context.error)

def check_chat_id(chat_id = None, result = 'chat'):
    user_chats = users.fetch().items
    if result == 'chat':
        if chat_id in [chat['chat_id'] for chat in user_chats]:
            return True
        else:
            return False
    elif result == 'push':
        return [x['chat_id'] for x in user_chats]
    elif result == 'users':
        return '\n'.join([x['username'] for x in user_chats if x['username'] is not None])


def get_messages(user_id, history):
    if history:
        messages = base.fetch({'username':user_id}).items
        messages = sorted(messages, key=lambda d: d['time'])
        messages = [x['message'] for x in messages]
        if len(messages) == 0:
            messages = [{'role':'user', 'content':'start'}]
    elif history == False:
        messages = [{'role':'user', 'content':'start'}]
    return messages

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.first_name}")

async def start(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    await context.bot.send_message(chat_id=chat_id,text =f"Hi, I'm your ChatGPT bot. How can I help you?\n{chat_id}\n{user_id}")

async def create(update,context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='upload_photo')
    if (chat_id>0 or bot_username in user_message) or ('/create' in user_message):
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
            
            # context.bot.send_message(chat_id=chat_id,text ="And give me a couple of seconds...")
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id,text =f"Oops, this didn't work out, here's the error message\n{e}")
        
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    if not check_chat_id(chat_id):
        users.insert({'username':user_id,'chat_id':chat_id},)
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()

    if (chat_id>0 or bot_username in user_message) and ('/create' not in user_message):
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing', )
    elif (chat_id>0 or bot_username in user_message) and '/create' in user_message:
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='upload_photo')


    if all([any([int(chat_id)>0,bot_username in user_message]),('/create' not in user_message)]):
        try:
            if f'messages_{user_id}' not in globals():
                globals()[f'messages_{user_id}'] = get_messages(user_id, history = True)
            globals()[f'messages_{user_id}'].append({'role':'user','content':user_message})
            globals()[f'messages_{user_id}'] = globals()[f'messages_{user_id}'][-10:]
            base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
            response = client.chat.completions.create(
                model = GPT_MODEL,
                messages =  globals()[f'messages_{user_id}'],
                temperature=0.9,
                max_tokens=3000 if r'\max_tokens' in user_message else 1000
            )
            message = response.choices[0].message.content.strip()
            globals()[f'messages_{user_id}'].append({'role':'assistant','content':message})
            base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
        except Exception as e:
            message = f'Sorry, the following error occurred:\n{e}'
        try:
            if len(message)>4000:
                split_message = ''
                words = message.split(' ')
                for word in words:
                    if len(split_message +' ' + word) <4000:
                        split_message = split_message +' ' + word
                    else:
                        time.sleep(1)
                        await update.message.reply_text(split_message)
                        split_message = word
                if len(split_message)>0:
                    time.sleep(1)
                    await update.message.reply_text(split_message)
            else:
                try:
                    await update.message.reply_text(message)
                except Exception as e:
                    await update.message.reply_text(f'Sorry, the following error occurred:\n{e}')
        except Exception as e:
            await update.message.reply_text(f'Sorry, the following error occurred:\n{e}')

async def push(update, context):
    chat_ids = check_chat_id(chat_id = None, result = 'push')
    for chat in chat_ids:
        await context.bot.send_message(chat_id = chat, text = update.message.text.replace('/push','').strip())
        
async def check_id(update, context):
    chat_id = update.effective_chat.id
    chat_ids = check_chat_id(chat_id = None, result = 'push')
    chat_ids = [str(x) for x in chat_ids]
    pre_text = f'Your chat_id is {chat_id}'
    text = '\n'.join(chat_ids)
    await context.bot.send_message(chat_id = chat_id, text = pre_text + '\n' + text)

async def usernames(update, context):
    chat_id = update.effective_chat.id
    usernames = check_chat_id(chat_id = None, result = 'users')
    await context.bot.send_message(chat_id = chat_id, text = usernames)


if __name__ == '__main__':
    print('The bot is running')
    logging.basicConfig(format='\n%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.WARNING)
    
    logger = logging.getLogger(__name__)
    
    
    app = ApplicationBuilder().token(tg_token).build()
    
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("push", push))
    app.add_handler(CommandHandler("check_id", check_id))
    app.add_handler(CommandHandler("users", usernames))
    
    
    app.add_error_handler(error)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

    
    app.run_polling()