import asyncio
import logging
from telethon.sync import TelegramClient
from telethon import functions
import os
import json
from datetime import datetime
import random
import string
import time

class TokenGenerator:
    def __init__(self):
        self.session_name = self._generate_random_name()
        self.config_path = '/Users/olegkizyma/Documents/more/config.json'  # Full path for better clarity

    def _generate_random_name(self, length=10):
        """Генерує випадкове ім'я сесії"""
        letters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(letters) for _ in range(length))

    async def create_bot_token(self, api_id: int, api_hash: str, phone: str):
        """Створює новий токен бота через BotFather"""
        client = None
        try:
            client = TelegramClient(self.session_name, api_id, api_hash)
            
            print("Підключення до Telegram...")
            await client.start(phone)
            
            if not await client.is_user_authorized():
                print("Помилка авторизації!")
                return None
                
            print("Пошук BotFather...")
            botfather = await client.get_entity("@BotFather")
            
            # Use more natural bot name
            display_name = f"TestBot {self._generate_random_name(4)}"
            username = f"test_{self._generate_random_name(6)}_bot"
            
            print("Створення нового бота...")
            await client.send_message(botfather, "/newbot")
            await asyncio.sleep(3)  # Increased delay
            
            # Check for response before continuing
            async for message in client.iter_messages(botfather, limit=1):
                if "Alright" not in message.text:
                    print("Помилка: неочікувана відповідь від BotFather")
                    return None
            
            print(f"Відправка імені бота: {display_name}")
            await client.send_message(botfather, display_name)
            await asyncio.sleep(3)  # Increased delay
            
            print(f"Відправка username бота: {username}")
            await client.send_message(botfather, username)
            await asyncio.sleep(3)  # Initial delay before checking
            
            print("Очікування токену...")
            start_time = time.time()
            while time.time() - start_time < 60:  # Increased timeout to 60 seconds
                async for message in client.iter_messages(botfather, limit=3):
                    if "Sorry" in message.text:
                        print("Помилка: ім'я бота вже зайняте")
                        return None
                        
                    if "Use this token to access the HTTP API:" in message.text:
                        lines = message.text.split('\n')
                        for line in lines:
                            if ':AAE' in line or ':AAF' in line or ':AAG' in line:  # Common bot token prefixes
                                token = line.strip()
                                print("Токен успішно отримано!")
                                self._save_token(token)
                                return token
                await asyncio.sleep(2)  # Check every 2 seconds
            
            print("Не вдалося отримати токен - таймаут!")
            return None
            
        except Exception as e:
            print(f"Помилка: {str(e)}")
            return None
        finally:
            if client:
                await client.disconnect()
            self._cleanup()

    def _save_token(self, token: str):
        """Зберігає токен в основний конфіг файл"""
        try:
            with open(self.config_path, 'r') as f:  # Using config_path from class
                config = json.load(f)
            
            # Додаємо або оновлюємо секцію з токеном
            if 'bot' not in config:
                config['bot'] = {}
            config['bot']['token'] = token
            config['bot']['created_at'] = datetime.now().isoformat()
            
            with open(self.config_path, 'w') as f:  # Using config_path from class
                json.dump(config, f, indent=4)
                
        except Exception as e:
            print(f"Помилка збереження токену в конфіг: {str(e)}")

    def _cleanup(self):
        """Очищує тільки файл сесії"""
        try:
            if os.path.exists(f"{self.session_name}.session"):
                os.remove(f"{self.session_name}.session")
        except Exception as e:
            print(f"Помилка під час очищення: {str(e)}")

async def main():
    config_path = '/Users/olegkizyma/Documents/more/config.json'  # Full path for better clarity
    
    if not os.path.exists(config_path):
        print(f"Файл конфігурації не знайдено: {os.path.abspath(config_path)}")
        return
    
    # Read configuration with better error handling
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Configuration file not found at: {os.path.abspath(config_path)}")
        return
    except json.JSONDecodeError:
        print("Invalid JSON format in config.json")
        return
    except Exception as e:
        print(f"Unexpected error reading configuration: {str(e)}")
        return

    generator = TokenGenerator()
    
    # Отримуємо дані з конфігурації
    api_id = config.get('telegram', {}).get('api_id')
    api_hash = config.get('telegram', {}).get('api_hash')
    phone = config.get('telegram', {}).get('phone_number')
    
    if not all([api_id, api_hash, phone]):
        print("Відсутні необхідні дані в конфігурації!")
        return
        
    # Створюємо токен
    token = await generator.create_bot_token(int(api_id), api_hash, phone)
    
    if token:
        print(f"\nВаш токен бота: {token}")
        print("\nЗбережіть його в надійному місці!")
    else:
        print("\nНе вдалося отримати токен!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    loop = asyncio.new_event_loop()  # Create new event loop instead of get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())