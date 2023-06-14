# -*- coding: utf-8 -*-
"""
Created on Mon Mar 27 14:10:04 2023

@author: Sergey
"""
import streamlit as st
from functools import wraps
from deta import Deta
# import logging
import requests
import time
from telegram import (ChatAction)
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import openai

tg_token = st.secrets['TG_KEY']
ai_key = st.secrets['AI_KEY']
deta_key = st.secrets['DETA_KEY']


openai.api_key = ai_key

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

# create a typing wrapper
def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        chat_id = update.effective_chat.id
        try:
            user_message = update.message.text
        except:
            user_message = ''
        bot_username = context.bot.username.lower()
        if (chat_id>0 or bot_username in user_message) and '/create' not in user_message:
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.TYPING)
        elif'/create' in user_message:
            context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=ChatAction.UPLOAD_PHOTO)
        return func(update, context,  *args, **kwargs)

    return command_func


# Define the start function
@send_typing_action
def start(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id,text =f"Hi, I'm your ChatGPT bot. How can I help you?\n{chat_id}")

@send_typing_action
def create(update,context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()
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
            context.bot.send_message(chat_id=chat_id,text ="Here's what DALL-E came up with")
            context.bot.send_photo(chat_id=update.effective_chat.id, photo = image_url_dall_e)
            
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

# Define the reply function
@send_typing_action
def reply(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_chat.username
    try:
        user_message = update.message.text
    except:
        user_message = ''
    bot_username = context.bot.username.lower()
    if all([any([chat_id>0,bot_username in user_message]),'/create' not in user_message]):
        if f'messages_{user_id}' not in globals():
            globals()[f'messages_{user_id}'] = get_messages(user_id, history = True)
        globals()[f'messages_{user_id}'].append({'role':'user','content':user_message})
        globals()[f'messages_{user_id}'] = globals()[f'messages_{user_id}'][-6:]
        base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
        response = openai.ChatCompletion.create(
          model = 'gpt-3.5-turbo',#'text-davinci-003',
          messages =  globals()[f'messages_{user_id}'],
          temperature=0.9,
          max_tokens=1000
        )
        message = response['choices'][0]['message']['content'].strip()
        globals()[f'messages_{user_id}'].append({'role':'assistant','content':message})
        base.insert({'username':user_id,'message':globals()[f'messages_{user_id}'][-1],'time':int(time.time())})
        context.bot.send_message(chat_id=update.effective_chat.id, text=message)

# Define the error function
# def error(update, context):
#     logger.warning('Update "%s" caused error "%s"', update, context.error)
def stop(update,context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id,text ='Bot stopped')


if 'running' not in st.session_state:
    deta = Deta(deta_key)
    base = deta.Base('messages')

    # logging.basicConfig(format='\n%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)

    # logger = logging.getLogger(__name__)
    
    updater = Updater(token=tg_token, use_context=True)
    dp = updater.dispatcher

    # Define the handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("create", create))
    dp.add_handler(MessageHandler(Filters.text, reply))
    # dp.add_error_handler(error)

    # # Start the bot
    updater.start_polling()
    updater.idle()
    
    st.session_state.running = True
    st.write(st.session_state)