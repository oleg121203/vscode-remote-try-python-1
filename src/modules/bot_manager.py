from typing import Optional, Dict, Any, List, Set
from telethon import TelegramClient, events, errors
from telethon.tl.types import User, Chat, Channel
from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
import logging
import asyncio
import os

class BotManager:
    def __init__(self, bot_token: str, api_id: int, api_hash: str,
                 session_name: Optional[str] = None, sessions_dir: Optional[str] = None):
        """Initialize the BotManager with unique session handling."""
        # Use provided sessions directory or default to 'sessions' in project root
        self.sessions_dir = sessions_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
        os.makedirs(self.sessions_dir, exist_ok=True)

        # Create unique session name using part of bot token
        if bot_token:
            token_part = bot_token.split(':')[0][-6:]  # Last 6 digits of token ID
            self.session_name = f"bot_{token_part}"
        else:
            self.session_name = session_name or "bot_session"

        # Full path to session file
        self.session_path = os.path.join(self.sessions_dir, f"{self.session_name}.session")

        # Initialize the bot client with the custom session path
        self.bot = TelegramClient(
            self.session_path,
            api_id,
            api_hash,
            device_model="Desktop",
            system_version="Windows 10",
            app_version="1.0",
            lang_code="en"
        )

        self.bot_token = bot_token
        self._connected = False
        self._tasks = set()
        self.status = "initialized"
        self.config_manager = None  # Will be set from outside

        logging.info(f"Bot session will be saved as: {self.session_path}")

    def set_config_manager(self, config_manager):
        """Set config manager for status updates."""
        self.config_manager = config_manager

    async def check_status(self) -> Dict[str, Any]:
        """Check bot status and connectivity."""
        try:
            if not self._connected or not self.bot:
                logging.warning("Bot is not connected")
                return {
                    'ok': False,
                    'status': 'disconnected',
                    'details': 'Bot is not connected'
                }

            try:
                # Проверяем реальное подключение
                if not self.bot.is_connected():
                    await self.bot.connect()
                
                me = await self.bot.get_me()
                if not me or not me.bot:
                    raise Exception("Invalid bot account")

                status = {
                    'ok': True,
                    'status': 'active',
                    'username': me.username,
                    'id': me.id,
                    'can_read_messages': True,
                    'is_bot': True
                }

                # Обновляем статус в конфиге только при успешной проверке
                if self.config_manager:
                    self.config_manager.update_bot_status('active')

                return status

            except Exception as e:
                logging.error(f"Bot connection check failed: {e}")
                if self.config_manager:
                    self.config_manager.update_bot_status('error', str(e))
                return {
                    'ok': False,
                    'status': 'error',
                    'details': str(e)
                }

        except Exception as e:
            error_msg = f"Bot status check failed: {str(e)}"
            logging.error(error_msg)
            if self.config_manager:
                self.config_manager.update_bot_status('error', error_msg)
            return {
                'ok': False,
                'status': 'error',
                'details': error_msg
            }

    async def start(self):
        """Start the bot client with proper session handling."""
        if self._connected:
            logging.warning("Bot is already connected")
            return

        try:
            # Connect first
            await self.bot.connect()
            
            # Start the bot with the token
            await self.bot.start(bot_token=self.bot_token)
            
            # Verify bot account
            me = await self.bot.get_me()
            if not me or not me.bot:
                raise Exception("This is not a bot account")

            self._connected = True
            logging.info(f"Bot @{me.username} (ID: {me.id}) started successfully")

            # Update status after successful start
            if self.config_manager:
                self.config_manager.update_bot_status('active')

        except Exception as e:
            self._connected = False
            logging.error(f"Failed to start bot: {str(e)}")
            if self.config_manager:
                self.config_manager.update_bot_status('error', error=str(e))
            raise

    async def _handle_first_auth(self):
        """Handle first time bot authentication."""
        try:
            # Start bot with token
            await self.bot.start(bot_token=self.bot_token)
            
            # Test authorization
            me = await self.bot.get_me()
            if not me:
                raise Exception("Bot authorization failed")
                
            logging.info(f"Bot @{me.username} authorized successfully")
            
        except errors.SessionPasswordNeededError:
            # For bots this should not happen, but handle just in case
            logging.error("Unexpected 2FA requirement for bot")
            raise
        except Exception as e:
            logging.error(f"Bot authentication failed: {e}")
            raise

    def _ensure_session_dir(self):
        """Ensure session directory exists."""
        session_dir = os.path.dirname(self.session_path)
        if session_dir and not os.path.exists(session_dir):
            os.makedirs(session_dir)

    async def stop(self):
        """Stop the bot client and cleanup resources."""
        try:
            if self._connected:
                for task in self._tasks:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                await self.bot.disconnect()
                await self.bot.disconnected
                self._connected = False
                logging.info("Bot stopped successfully")
        except Exception as e:
            logging.error(f"Error stopping bot: {e}")
            raise

    async def get_profile_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile data if bot has access."""
        try:
            user = await self.bot.get_entity(user_id)
            return {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'phone': getattr(user, 'phone', None),
                'bot_accessible': True
            }
        except Exception as e:
            logging.warning(f"Bot couldn't access profile data for user {user_id}: {e}")
            return None

    async def monitor_group(self, group_id: int, config: Dict[str, Any]):
        """Monitor group activity with configured limits."""
        try:
            max_members = config['bot_workload']['max_monitored_members_per_group']
            group = await self.bot.get_entity(group_id)
            participants = await self.bot.get_participants(group, limit=max_members)
            
            return {
                'group_id': group_id,
                'members_count': len(participants),
                'bot_accessible': True,
                'members': [p.id for p in participants]
            }
        except Exception as e:
            logging.warning(f"Bot couldn't monitor group {group_id}: {e}")
            return None

    def add_message_handler(self, callback):
        """Add message event handler."""
        @self.bot.on(events.NewMessage)
        async def handler(event):
            await callback(event)

    async def handle_account_updates(self):
        """Handle account update differences."""
        @self.bot.on(events.Raw)
        async def handle_raw_updates(event):
            try:
                if hasattr(event, 'difference'):
                    logging.info("Processing account updates...")
                    updates = event.difference.new_messages
                    for update in updates:
                        await self._process_update(update)
            except Exception as e:
                logging.error(f"Error handling account updates: {e}")

    async def _process_update(self, update):
        """Process individual account update."""
        try:
            # Handle different types of updates
            if hasattr(update, 'message'):
                await self._handle_message_update(update.message)
            elif hasattr(update, 'user_status'):
                await self._handle_status_update(update)
            # Add more update type handlers as needed
        except Exception as e:
            logging.error(f"Error processing update: {e}")

    async def _handle_message_update(self, message):
        """Handle message updates."""
        logging.info(f"New message update from {message.from_id}")
        # Add your message handling logic here

    async def _handle_status_update(self, status_update):
        """Handle user status updates."""
        logging.info(f"Status update for user {status_update.user_id}")
        # Add your status update handling logic here

# Remove test instance creation

