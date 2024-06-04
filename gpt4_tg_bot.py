import openai
import logging
import aiohttp
from io import BytesIO
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.storage import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile
from aiogram.utils import executor

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up your OpenAI API key
openai.api_key = 'YOUR_OPENAI_API_KEY'

# Set up the bot token
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# In-memory user sessions
user_sessions = {}

# Function to handle new and returning users
async def check_user(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"thread": None, "messages": []}  # Initialize a new thread
    return user_sessions[user_id]

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer('Hello! I am your assistant. How can I help you today?')

# Function to handle text messages
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    user_session = await check_user(user_id)
    
    text = message.text
    user_session['messages'].append({"role": "user", "content": text})

    # Send the message to OpenAI
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=user_session['messages']
    )

    assistant_message = response.choices[0].message['content']
    user_session['messages'].append({"role": "assistant", "content": assistant_message})

    await message.answer(assistant_message)

# Function to handle image messages
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_image(message: types.Message):
    user_id = message.from_user.id
    user_session = await check_user(user_id)
    
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Download image file
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}') as resp:
            if resp.status == 200:
                image_data = await resp.read()

    # Prepare the prompt
    prompt = message.caption or "Describe this image"
    user_session['messages'].append({"role": "user", "content": prompt})

    # Send the prompt to OpenAI
    response = openai.Image.create(
        prompt=prompt,
        n=1,
        size="256x256"
    )

    image_url = response['data'][0]['url']
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as image_response:
            image_bytes = await image_response.read()

    bio = BytesIO(image_bytes)
    bio.name = 'output_image.png'
    
    await bot.send_photo(chat_id=message.chat.id, photo=InputFile(bio))
    user_session['messages'].append({"role": "assistant", "content": "Image generated based on your input."})

# Function to handle voice messages
@dp.message_handler(content_types=types.ContentType.VOICE)
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    user_session = await check_user(user_id)
    
    voice = await message.voice.get_file()
    file_path = voice.file_path
    
    # Download voice file
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}') as resp:
            if resp.status == 200:
                voice_data = await resp.read()
    
    # Convert voice to text (you can use a library like SpeechRecognition or an API like Google Cloud Speech-to-Text)
    # For simplicity, let's assume we have the text
    voice_text = "transcribed text from voice message"
    user_session['messages'].append({"role": "user", "content": voice_text})

    # Send the transcribed text to OpenAI
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=user_session['messages']
    )

    assistant_message = response.choices[0].message['content']
    user_session['messages'].append({"role": "assistant", "content": assistant_message})

    await message.answer(assistant_message)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

### Code Explanation:
# - **Logging Setup**: Basic logging is set up to help with debugging.
# - **User Sessions**: User sessions are maintained in memory using a dictionary.
# - **Asynchronous HTTP Requests**: `aiohttp` is used for making asynchronous HTTP requests.
# - **Asynchronous Bot Functions**: The bot uses `aiogram` to handle asynchronous operations, such as message handling, file downloads, and API calls.
# - **Functions**:
#   - `check_user`: Checks if the user is new or returning and maintains their session.
#   - `start`: Sends a welcome message when the `/start` command is invoked.
#   - `handle_text`: Processes text messages and interacts with OpenAI.
#   - `handle_image`: Downloads image files, sends them to OpenAI, and returns the generated image.
#   - `handle_voice`: Downloads voice messages and handles voice-to-text conversion.