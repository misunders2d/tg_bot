from deta import Deta
import openai
import time
import logging
from google.cloud import secretmanager

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters


def access_secret_version(project_id, secret_id, version_id):
    client = secretmanager.SecretManagerServiceClient()
    secret_name = client.secret_version_path(project_id, secret_id, version_id)
    response = client.access_secret_version(request={"name": secret_name})
    return response.payload.data.decode('UTF-8')

project_id = 'tg-bot-392213'

tg_token = access_secret_version(project_id, 'TG_KEY', 'latest')
ai_key = access_secret_version(project_id, 'AI_KEY', 'latest')
deta_key = access_secret_version(project_id, 'DB_USERS', 'latest')

GPT_MODEL = 'gpt-4'#'gpt-3.5-turbo'

deta = Deta(deta_key)
base = deta.Base('messages')
users = deta.Base('users')

openai.api_key = ai_key

# Define the error function
def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)

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
        return '\n'.join([x['username'] for x in user_chats if x is not None])


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
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def start(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    await context.bot.send_message(chat_id=chat_id,text =f"Hi, I'm your ChatGPT bot. How can I help you?\n{chat_id}")

async def create(update,context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()
    await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='upload_photo')
    if (chat_id>0 or bot_username in user_message) or '/create' in user_message:
        prompt = user_message.replace('/create ','')
        try:
            #DALL-E generation:
            response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="1024x1024"
                )
            image_url_dall_e = response['data'][0]['url']
            await context.bot.send_message(chat_id=chat_id,text ="Here's what DALL-E came up with")
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo = image_url_dall_e)
            
            # context.bot.send_message(chat_id=chat_id,text ="And give me a couple of seconds...")
        except Exception as e:
            context.bot.send_message(chat_id=chat_id,text =f"Oops, this didn't work out, here's the error message\n{e}")
        
        # #Stable Diffution generation:
        # if 'photorealistic' in user_message:
        #     prompt += ', Canon EOS R3, nikon, f/1.4, ISO 200, 1/160s, 8K, RAW, unedited, symmetrical balance, in-frame, 8K'
        # url = 'https://stablediffusionapi.com/api/v3/text2img'
        # data = {
        #         "key": f"{sd_key}",
        #         "prompt": f"{prompt}",
        #         "negative_prompt": "((out of frame)), ((extra fingers)), mutated hands, ((poorly drawn hands)), ((poorly drawn face)), (((mutation))), (((deformed))), (((tiling))), ((naked)), ((tile)), ((fleshpile)), ((ugly)), (((abstract))), blurry, ((bad anatomy)), ((bad proportions)), ((extra limbs)), cloned face, (((skinny))), glitchy, ((extra breasts)), ((double torso)), ((extra arms)), ((extra hands)), ((mangled fingers)), ((missing breasts)), (missing lips), ((ugly face)), ((fat)), ((extra legs)), anime",
        #         "width": "512",
        #         "height": "512",
        #         "samples": "1",
        #         "num_inference_steps": "20",
        #         "seed": None,
        #         "guidance_scale": 7.5,
        #         "safety_checker":"yes",
        #         "webhook": None,
        #         "track_id": None
        #         }
        # try:
        #     response = requests.post(url, json=data)
        #     if response.status_code == 200:
        #         success = response.json()['status']
        #         if success == 'success':
        #             image_url = response.json()['output'][0]
        #             context.bot.send_message(chat_id=chat_id,text ="Here's a Stable Diffusion version")
        #             context.bot.send_photo(chat_id=update.effective_chat.id, photo = image_url)
        #         else:
        #             error_message = response.json()['message']
        #             context.bot.send_message(chat_id=chat_id,text =f"Sorry, got this error message:\n{error_message}")
        #     else:
        #         context.bot.send_message(chat_id=chat_id,text =f"Sorry, image generation failed. Status code {response.status_code}")
        # except Exception as e:
        #     context.bot.send_message(chat_id=chat_id,text =f"Sorry, image generation failed, please try again in 10-15 seconds\nError: {e}")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    if not check_chat_id(chat_id):
        users.insert({'username':user_id,'chat_id':chat_id},)
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()

    if (chat_id>0 or bot_username in user_message) and '/create' not in user_message:
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='typing')
    elif'/create' in user_message:
        await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action='upload_photo')


    if all([any([chat_id>0,bot_username in user_message]),'/create' not in user_message]):
        try:
            if f'messages_{user_id}' not in globals():
                globals()[f'messages_{user_id}'] = get_messages(user_id, history = True)
            globals()[f'messages_{user_id}'].append({'role':'user','content':user_message})
            globals()[f'messages_{user_id}'] = globals()[f'messages_{user_id}'][-10:]
            base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
            response = openai.ChatCompletion.create(
            model = GPT_MODEL,
            messages =  globals()[f'messages_{user_id}'],
            temperature=0.9,
            max_tokens=1000
            )
            message = response['choices'][0]['message']['content'].strip()
            globals()[f'messages_{user_id}'].append({'role':'assistant','content':message})
            base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
        except Exception as e:
            message = f'Sorry, the following error occurred:\n{e}'

    await update.message.reply_text(message)

async def push(update, context):
    chat_ids = check_chat_id(chat_id = None, result = 'push')
    for chat in chat_ids:
        await context.bot.send_message(chat_id = chat, text = update.message.text.replace('/push','').strip())

async def usernames(update, context):
    chat_id = update.effective_chat.id
    usernames = check_chat_id(chat_id = None, result = 'users')
    await context.bot.send_message(chat_id = chat_id, text = usernames)


logging.basicConfig(format='\n%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.WARNING)

logger = logging.getLogger(__name__)


app = ApplicationBuilder().token(tg_token).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("create", create))
app.add_handler(CommandHandler("push", push))
app.add_handler(CommandHandler("users", usernames))


app.add_error_handler(error)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))

app.run_polling()