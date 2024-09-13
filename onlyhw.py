import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from openai import AsyncOpenAI
import openai
from openai.types.chat import ChatCompletion
import os
from dotenv import load_dotenv
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Проверка API ключа OpenAI
if not OPENAI_API_KEY:
    logger.error("OpenAI API key is not set. Please check your .env file.")
    raise ValueError("OpenAI API key is not set")

# Инициализация OpenAI API
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Словарь для хранения контекста пользователей
user_contexts = {}

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_command(message: Message):
    """Обработчик команды /start."""
    try:
        user_id = message.from_user.id
        logger.info(f"Start command from User ID ({user_id})")
        
        if user_id not in user_contexts:
            user_contexts[user_id] = {"context": [], "tokens": 1000}
            logger.info(f"User ID ({user_id}) not in DB, registered new user")
        else:
            logger.info(f"User ID ({user_id}) in DB, greeting existing user")
        
        await message.reply("Привет! Я бот-пират. Чем могу помочь?")
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}")

@dp.message(Command("tokens"))
async def tokens_command(message: Message):
    """Обработчик команды /tokens для пополнения токенов."""
    try:
        user_id = message.from_user.id
        logger.info(f"Tokens command from User ID ({user_id})")
        
        if user_id in user_contexts:
            user_contexts[user_id]["tokens"] = 1000
            logger.info(f"User ID ({user_id}) in DB, tokens reset")
            await message.reply("Ваши токены пополнены до 1000.")
        else:
            logger.warning(f"User ID ({user_id}) not in DB, can't reset tokens")
            await message.reply("Ошибка: пользователь не найден.")
    except Exception as e:
        logger.error(f"Error in tokens command: {str(e)}")

@dp.message(Command("clean"))
async def clean_command(message: Message):
    """Обработчик команды /clean для очистки контекста."""
    try:
        user_id = message.from_user.id
        logger.info(f"Clean command from User ID ({user_id})")
        
        if user_id in user_contexts:
            user_contexts[user_id]["context"] = []
            logger.info(f"User ID ({user_id}) context cleared")
            await message.reply("Контекст очищен.")
        else:
            logger.warning(f"User ID ({user_id}) not in DB, can't clear context")
            await message.reply("Ошибка: пользователь не найден.")
    except Exception as e:
        logger.error(f"Error in clean command: {str(e)}")

@dp.message()
async def handle_message(message: Message):
    """Обработчик входящих сообщений."""
    try:
        user_id = message.from_user.id
        user_message = message.text
        logger.info(f"New message from User ID ({user_id}) Message: {user_message}")

        if user_id not in user_contexts or user_contexts[user_id]["tokens"] <= 0:
            logger.warning(f"User ID ({user_id}) has no free tokens, can't respond")
            await message.reply("У вас закончились токены. Используйте /tokens для пополнения.")
            return

        response = await generate_response(user_id, user_message)
        logger.info(f"For User ID ({user_id}) replied to message ({user_message}). Response: {response}")
        
        await message.reply(response)
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")

async def generate_response(user_id: int, message: str) -> str:
    """Генерация ответа с использованием OpenAI API."""
    try:
        user_contexts[user_id]["context"].append({"role": "user", "content": message})
        
        response: ChatCompletion = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - бот-пират. Отвечай как пират."},
                *user_contexts[user_id]["context"]
            ]
        )

        assistant_response = response.choices[0].message.content
        user_contexts[user_id]["context"].append({"role": "assistant", "content": assistant_response})
        
        # Обновление статистики пользователя
        tokens_used = response.usage.total_tokens
        user_contexts[user_id]["tokens"] -= tokens_used
        
        logger.info(f"For User ID ({user_id}) new stats: tokens used: {tokens_used}, context length: {len(user_contexts[user_id]['context'])}")
        
        return assistant_response
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return "Извините, произошла ошибка при обращении к API. Попробуйте позже."
    except openai.RateLimitError as e:
        logger.error(f"OpenAI rate limit error: {str(e)}")
        return "Извините, достигнут лимит запросов. Попробуйте позже."
    except openai.AuthenticationError as e:
        logger.error(f"OpenAI authentication error: {str(e)}")
        return "Извините, произошла ошибка аутентификации. Обратитесь к администратору."
    except Exception as e:
        logger.error(f"Unexpected error in generate_response: {str(e)}")
        return "Извините, произошла неожиданная ошибка. Попробуйте позже."

async def main():
    """Основная функция для запуска бота."""
    try:
        logger.info("Bot started polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
    finally:
        logger.warning("Bot stopped.")

if __name__ == '__main__':
    asyncio.run(main())
