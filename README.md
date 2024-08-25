# tg_bot_gpt
TG bot with ChatGPT support, vision and voice capabilities.
Latest updates enable the bot to perform basic real-time web search and weather reporting.

Requires accounts with [OpenAI](https://openai.com/), [Google Custom Search API](https://developers.google.com/custom-search/v1/overview), [Deta](https://deta.space/), and [Weatherapi](https://www.weatherapi.com/)


Please make sure to include .env file with your api keys:

OpenAI:
ASSISTANT_ID = 'your openai assistant id'
AI_KEY = 'your openai project key'

Deta:
DETA_KEY = 'your Deta database ("Base") key'

Telegram:
TG_KEY = 'your telegram bot api key'
BOT_HANDLE = '@your_bot_handle (for group chats and debugging)'
ADMIN_CHAT = Telegram chat id (INT) of the admin for advanced functions, like "push" messages

Google:
GOOGLE_SEARCH_API = 'your google custom search json api'
GOOGLE_SEARCH_ENGINE_ID = 'the custom search engine ID with google'

WeatherAPI:
WEATHER_API = 'your weather api key'
