import asyncio
import json
import logging
import os
import random
import string
import time
from datetime import datetime
from telethon import TelegramClient

class TokenGenerator:
    def __init__(self):
        self.session_name = self._generate_random_name()
        self.config_path = '/Users/olegkizyma/Documents/more/config.json'
    
    def _generate_random_name(self, length=10):
        """Генерує випадкове ім'я сесії."""
        letters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(letters) for _ in range(length))
    
    async def create_bot_token(self, api_id, api_hash, phone):
        """Створює новий токен бота через BotFather."""
        client = TelegramClient(self.session_name, api_id, api_hash)
        await client.start(phone)

        try:
            if not await client.is_user_authorized():
                print("Помилка авторизації!")
                return None

            print("Пошук BotFather...")
            botfather = await client.get_entity("@BotFather")
            
            print("Створення нового бота...")
            await client.send_message(botfather, "/newbot")
            await asyncio.sleep(5)  # Збільшення затримки

            async for message in client.iter_messages(botfather, limit=1):
                print(f"Відповідь BotFather: {message.text}")
                if "Alright" not in message.text:
                    print("Помилка: неочікувана відповідь від BotFather")
                    return None
            
            display_name = f"TestBot {self._generate_random_name(4)}"
            username = f"test_{self._generate_random_name(6)}_bot"
            
            print(f"Відправка імені бота: {display_name}")
            await client.send_message(botfather, display_name)
            await asyncio.sleep(5)  # Збільшення затримки

            print(f"Відправка username бота: {username}")
            await client.send_message(botfather, username)
            await asyncio.sleep(5)  # Збільшення затримки

            print("Очікування токену...")
            start_time = time.time()
            while time.time() - start_time < 60:  # Збільшення таймауту до 60 секунд
                async for message in client.iter_messages(botfather, limit=5):
                    print(f"Відповідь BotFather: {message.text}")
                    if "Sorry" in message.text:
                        print("Помилка: ім'я бота вже зайняте")
                        return None
                    if "Use this token to access the HTTP API:" in message.text:
                        lines = message.text.split('\n')
                        for line in lines:
                            if 'Use this token to access the HTTP API:' in line:
                                token = line.split(':')[1].strip()
                                print("Токен успішно отримано!")
                                self._save_token(token)
                                return token
                await asyncio.sleep(2)  # Перевірка кожні 2 секунди

            print("Не вдалося отримати токен - таймаут!")
            return None

        except Exception as e:
            print(f"Помилка: {e}")
            return None
        finally:
            await client.disconnect()
            self._cleanup()

    def _save_token(self, token):
        """Зберігає токен в конфігураційний файл."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            if 'bot' not in config:
                config['bot'] = {}
            config['bot']['token'] = token
            config['bot']['created_at'] = datetime.now().isoformat()
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)

        except Exception as e:
            print(f"Помилка збереження токену в конфіг: {e}")

    def _cleanup(self):
        """Очищує файл сесії."""
        if os.path.exists(f"{self.session_name}.session"):
            os.remove(f"{self.session_name}.session")

async def main():
    if not os.path.exists('/Users/olegkizyma/Documents/more/config.json'):
        print("Файл конфігурації не знайдено!")
        return
    
    with open('/Users/olegkizyma/Documents/more/config.json', 'r') as f:
        config = json.load(f)
    
    api_id = config['telegram']['api_id']
    api_hash = config['telegram']['api_hash']
    phone = config['telegram']['phone_number']
    
    generator = TokenGenerator()
    token = await generator.create_bot_token(api_id, api_hash, phone)
    
    if token:
        print(f"\nВаш токен бота: {token}")
        print("\nЗбережіть його в надійному місці!")
    else:
        print("\nНе вдалося отримати токен!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())