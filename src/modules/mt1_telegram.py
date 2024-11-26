import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from telethon import TelegramClient, errors, functions, types
from telethon.tl.functions.channels import (
    GetFullChannelRequest,
    JoinChannelRequest,
    LeaveChannelRequest,
)
from telethon.tl.types import (
    Channel,
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
    UserStatusOnline,
    UserStatusRecently,
)

from modules.bot_manager import BotManager


class TelegramModule:
    def __init__(self, api_id: int, api_hash: str, phone_number: str, 
                 bot_token: Optional[str] = None):
        """Initialize Telegram module with API credentials."""
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('account_session', self.api_id, self.api_hash)
        self.bot_manager = None  # Initialize bot_manager as None first
        self._is_connected = False
        self._is_authorized = False
        self.rate_limit_delay = 2
        self.bot_token = bot_token  # Store bot token for later initialization
        logging.debug("TelegramModule initialized with provided credentials.")

    async def connect(self) -> bool:
        """Connect account first, then bot if configured."""
        try:
            if not self._is_connected:
                await self.client.connect()
                self._is_connected = True
                self._is_authorized = await self.client.is_user_authorized()
                
                # Only initialize bot after account is connected
                if self._is_connected and self.bot_token:
                    try:
                        self.bot_manager = BotManager(
                            bot_token=self.bot_token,
                            api_id=self.api_id,
                            api_hash=self.api_hash,
                            session_name='bot_session'
                        )
                        await self.bot_manager.start()
                    except Exception as e:
                        logging.error(f"Failed to initialize bot manager: {e}")
                        self.bot_manager = None
                    
            await asyncio.sleep(self.rate_limit_delay)
            return True
                
        except Exception as e:
            self._is_connected = False
            self._is_authorized = False
            logging.error(f"Connection error: {e}")
            return False

    async def sign_in(self, code: Optional[str] = None, password: Optional[str] = None) -> None:
        """
        Асинхронно выполняет вход в Telegram с использованием предоставленного кода и/или пароля.

        :param code: Код подтверждения, полученный от Telegram.
        :param password: Пароль для Telegram (если включена двухэтапная аутентификация).
        """
        if not self.client.is_connected():
            await self.client.connect()
            
        try:
            if code and not password:
                await self.client.sign_in(self.phone_number, code)
            elif password and not code:
                await self.client.sign_in(password=password)
            elif code and password:
                await self.client.sign_in(self.phone_number, code, password=password)
            else:
                raise ValueError("Either code or password must be provided")
                
            logging.info("Successfully signed in")
            
        except errors.SessionPasswordNeededError:
            logging.warning("Two-factor authentication required")
            raise
        except errors.RPCError as e:
            logging.error(f"RPC Error during Telegram sign-in: {e}")
            raise e
        except Exception as e:
            logging.error(f"Unknown error during Telegram sign-in: {e}")
            raise e

    async def sign_in_via_sms(self) -> None:
        """Initiate sign-in process via SMS."""
        try:
            await self.client.send_code_request(self.phone_number)
            # ...existing code...
        except Exception as e:
            logging.error(f"Error sending SMS code: {e}")
            raise

    async def sign_in_with_code(self, code: str) -> None:
        """Sign in using the received SMS code."""
        try:
            await self.client.sign_in(self.phone_number, code)
            # ...existing code...
        except errors.SessionPasswordNeededError:
            logging.warning("Two-factor authentication required")
            raise
        except Exception as e:
            logging.error(f"Error signing in with code: {e}")
            raise

    async def restart_session(self) -> None:
        """Restart the Telegram client session."""
        await self.disconnect()
        await self.connect()
        # ...existing code...

    async def disconnect(self) -> None:
        """Safely disconnect from Telegram and cleanup resources."""
        try:
            if self._is_connected:
                if self.bot_manager:
                    await self.bot_manager.stop()
                await self.client.disconnect()
                self._is_connected = False
                self._is_authorized = False
                logging.info("Disconnected from Telegram")
        except Exception as e:
            logging.error(f"Disconnect error: {e}")
            raise

    async def ensure_connected(self) -> bool:
        """
        Ensure client is connected and authorized before operations.

        Returns:
            bool: True if connected and authorized, False otherwise
        """
        if not self._is_connected or not await self.is_connected():
            return await self.connect()

        if not self._is_authorized:
            self._is_authorized = await self.client.is_user_authorized()

        return self._is_connected and self._is_authorized

    async def get_entity(self, identifier: Any) -> Union[types.User, types.Chat, types.Channel]:
        """
        Асинхронно получает сущность Telegram по её идентификатору.

        :param identifier: Username, user ID или приглашение на сущность.
        :return: Объект сущности Telegram (User, Chat или Channel).
        """
        if not await self.ensure_connected():
            raise Exception("Failed to ensure connection")
            
        try:
            entity = await self.client.get_entity(identifier)
            logging.debug(f"Retrieved entity for identifier: {identifier}")
            return entity
        except errors.UsernameNotOccupiedError:
            logging.error(f"No user has \"{identifier}\" as username")
            return None
        except errors.RPCError as e:
            logging.error(f"RPC Error while getting entity: {e}")
            raise e
        except Exception as e:
            logging.error(f"Unknown error while getting entity: {e}")
            raise e

    async def get_participants(self, group_link: str, limit: int = 100) -> List[User]:
        """Gets participants from a group with proper error handling and rate limiting."""
        try:
            entity = await self.client.get_entity(group_link)
            participants = await self.client.get_participants(entity, limit=limit)
            await asyncio.sleep(self.rate_limit_delay)
            return participants
            
        except errors.ChatAdminRequiredError:
            logging.error(f"Insufficient permissions to access participants of {group_link}")
        except errors.FloodWaitError as e:
            logging.warning(f"Rate limit hit. Waiting {e.seconds} seconds for {group_link}")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logging.error(f"Failed to get participants of {group_link}: {e}")
        return []

    async def join_group(self, group_link: str) -> Optional[Channel]:
        """Joins a Telegram group with proper error handling and rate limiting."""
        try:
            entity = await self.client.get_entity(group_link)
            if isinstance(entity, Channel):
                if not entity.left:
                    logging.info(f"Already a member of group {group_link}")
                    return entity
                
                logging.info(f"Joining group {group_link}")
                await self.client(JoinChannelRequest(entity))
                await asyncio.sleep(self.rate_limit_delay)
                return entity
                
        except errors.FloodWaitError as e:
            logging.warning(f"Rate limit hit. Waiting {e.seconds} seconds for {group_link}")
            await asyncio.sleep(e.seconds)
        except errors.ChannelPrivateError:
            logging.error(f"Group {group_link} is private")
        except Exception as e:
            logging.error(f"Failed to join group {group_link}: {e}")
        return None

    async def get_dialogs(self, user: Union[types.User, types.Chat, types.Channel]) -> List[types.Dialog]:
        """
        Асинхронно получает диалоги пользователя Telegram.

        :param user: Сущность пользователя Telegram (User, Chat или Channel).
        :return: Список диалогов Telegram.
        """
        try:
            dialogs = await self.client.get_dialogs(user)
            logging.debug(f"Retrieved {len(dialogs)} dialogs for user: {user.id}")
            return dialogs
        except errors.RPCError as e:
            logging.error(f"RPC Error while getting dialogs: {e}")
            raise e
        except Exception as e:
            logging.error(f"Unknown error while getting dialogs: {e}")
            raise e

    async def is_connected(self) -> bool:
        """Safely checks if client is connected."""
        try:
            if not self._is_connected:
                await self.connect()
            return self._is_connected and self.client.is_connected()
        except Exception as e:
            logging.error(f"Connection check failed: {e}")
            return False

    async def is_user_authorized(self) -> bool:
        """Safely checks if user is authorized."""
        try:
            if not await self.is_connected():
                return False
            self._is_authorized = await self.client.is_user_authorized()
            return self._is_authorized
        except Exception as e:
            logging.error(f"Authorization check failed: {e}")
            return False

    async def send_code_request(self) -> None:
        """Sends verification code with proper error handling and backoff."""
        max_retries = 3
        base_delay = 5  # Initial delay in seconds
        
        for attempt in range(max_retries):
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                
                # Add small delay before sending code request
                if attempt > 0:
                    delay = base_delay * (2 ** attempt)
                    logging.info(f"Waiting {delay} seconds before retry {attempt + 1}")
                    await asyncio.sleep(delay)
                
                # Fixed: Use the correct parameters for SendCodeRequest
                result = await self.client.send_code_request(self.phone_number)
                return result
                
            except SendCodeUnavailableError:
                if attempt < max_retries - 1:
                    logging.warning(f"Code sending attempt {attempt + 1} failed, retrying...")
                    continue
                logging.error("All code sending methods exhausted")
                raise
            except Exception as e:
                logging.error(f"Error sending code request: {e}")
                raise

    async def reset_group(self, group_id: int):
        try:
            # Logic to reset the group data
            # For example: clear members, remove specific fields, etc.
            logging.info(f"Group {group_id} reset successfully.")
        except Exception as e:
            logging.error(f"Error resetting group {group_id}: {e}")

    async def search_groups(self, keywords: List[str], match_all: bool = False, min_participants: int = 0,
                            max_participants: Optional[int] = None, group_type: str = 'all',
                            stop_flag: Optional[Callable[[], bool]] = None,
                            pause_flag: Optional[Callable[[], bool]] = None):
        """Searches for public groups based on keywords and filters."""
        if not await self.ensure_connected():
            raise Exception("Failed to ensure connection")

        try:
            results = []
            search_queries = []
            
            # Генеруємо різні варіанти пошукових запитів
            for keyword in keywords:
                # Базовий запит
                search_queries.append(keyword)
                
                # Додаємо варіант з "@" якщо його немає
                if not keyword.startswith('@'):
                    search_queries.append(f"@{keyword}")
                    
                # Додаємо варіант з "t.me/" якщо це посилання
                if not keyword.startswith('t.me/'):
                    search_queries.append(f"t.me/{keyword}")

            for query in search_queries:
                if stop_flag and stop_flag():
                    break

                while pause_flag and pause_flag():
                    await asyncio.sleep(0.1)
                    if stop_flag and stop_flag():
                        break

                try:
                    # Виконуємо пошук через різні методи API
                    search_methods = [
                        lambda: self.client(functions.contacts.SearchRequest(
                            q=query,
                            limit=100
                        )),
                        lambda: self.client(functions.messages.SearchGlobalRequest(
                            q=query,
                            filter=types.InputMessagesFilterEmpty(),
                            min_date=-1,
                            max_date=-1,
                            offset_rate=0,
                            offset_peer=types.InputPeerEmpty(),
                            offset_id=0,
                            limit=100
                        ))
                    ]

                    for search_method in search_methods:
                        try:
                            search_results = await search_method()
                            
                            # Обробляємо результати пошуку
                            chats = getattr(search_results, 'chats', []) or []
                            for chat in chats:
                                if not isinstance(chat, types.Channel):
                                    continue

                                # Перевіряємо чи група вже є в результатах
                                if any(existing.id == chat.id for existing in results):
                                    continue

                                try:
                                    # Отримуємо повну інформацію про групу
                                    full_chat = await self.client(GetFullChannelRequest(channel=chat))
                                    participants_count = getattr(full_chat.full_chat, 'participants_count', 0)

                                    # Застосовуємо фільтри
                                    if participants_count < min_participants:
                                        continue
                                        
                                    if max_participants and participants_count > max_participants:
                                        continue

                                    # Перевіряємо тип групи
                                    if group_type.lower() != 'all':
                                        if group_type.lower() == 'megagroup' and not chat.megagroup:
                                            continue
                                        if group_type.lower() == 'broadcast' and not chat.broadcast:
                                            continue

                                    # Додаємо групу до результатів
                                    chat.participants_count = participants_count
                                    results.append(chat)

                                except Exception as e:
                                    logging.error(f"Error getting full chat info: {e}")
                                    continue

                            # Додаємо затримку між запитами
                            await asyncio.sleep(2)

                        except errors.FloodWaitError as e:
                            logging.warning(f"Hit rate limit, waiting {e.seconds} seconds")
                            await asyncio.sleep(e.seconds)
                        except Exception as e:
                            logging.error(f"Search method error: {e}")
                            continue

                except Exception as e:
                    logging.error(f"Error during search: {e}")
                    continue

            # Видаляємо дублікати та сортуємо за кількістю учасників
            unique_results = list({group.id: group for group in results}.values())
            sorted_results = sorted(unique_results, 
                                  key=lambda x: getattr(x, 'participants_count', 0) or 0,
                                  reverse=True)
            
            return sorted_results

        except Exception as e:
            logging.error(f"Error searching groups: {e}")
            raise

    def extract_user_info(self, user: User) -> Dict[str, Any]:
        """Extracts relevant user information safely."""
        return {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': getattr(user, 'phone', None)  # Safely get phone if available
        }

    async def can_access_participants(self, group: Channel) -> bool:
        """Check if we have permission to access group participants."""
        try:
            await self.client.get_participants(group, limit=1)
            return True
        except errors.ChatAdminRequiredError:
            logging.warning(f"No admin rights to access participants in {group.title}")
            return False
        except Exception as e:
            logging.error(f"Error checking participant access: {e}")
            return False

    async def join_channel(self, channel: Union[int, str, Channel]) -> Optional[Channel]:
        """Join a channel with rate limiting and error handling."""
        try:
            if isinstance(channel, (int, str)):
                channel = await self.get_entity(channel)
            
            if not isinstance(channel, Channel):
                logging.error("Entity is not a channel")
                return None
                
            await self.client(JoinChannelRequest(channel))
            await asyncio.sleep(self.rate_limit_delay)
            return channel
            
        except errors.FloodWaitError as e:
            logging.warning(f"Hit rate limit. Waiting {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self.join_channel(channel)
        except Exception as e:
            logging.error(f"Failed to join channel: {e}")
            return None

    async def get_chat_info(self, chat: Channel) -> Dict[str, Any]:
        """Get detailed chat information safely."""
        try:
            full_chat = await self.client(GetFullChannelRequest(channel=chat))
            return {
                'id': chat.id,
                'title': chat.title,
                'username': chat.username,
                'participants_count': getattr(full_chat.full_chat, 'participants_count', 0),
                'description': getattr(full_chat.full_chat, 'about', ''),
                'is_megagroup': chat.megagroup,
                'is_broadcast': chat.broadcast
            }
        except Exception as e:
            logging.error(f"Failed to get chat info: {e}")
            return {}

    async def process_participants(
        self, 
        group: Channel,
        callback: Optional[Callable[[User], None]] = None,
        limit: int = None
    ) -> List[Dict[str, Any]]:
        """Process group participants with callback support and rate limiting."""
        results = []
        try:
            participants = await self.client.get_participants(group, limit=limit)
            
            for participant in participants:
                if callback:
                    callback(participant)
                    
                user_info = self.extract_user_info(participant)
                results.append(user_info)
                
                await asyncio.sleep(0.1)  # Small delay between processing participants
                
            return results
            
        except errors.FloodWaitError as e:
            logging.warning(f"Hit rate limit. Waiting {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return await self.process_participants(group, callback, limit)
        except Exception as e:
            logging.error(f"Failed to process participants: {e}")
            return results

    async def smart_search(
        self,
        keywords: List[str],
        filters: Dict[str, Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Channel]:
        """Smart search for groups with filters and progress tracking."""
        try:
            results = []
            total_keywords = len(keywords)
            
            for index, keyword in enumerate(keywords):
                if progress_callback:
                    progress_callback(index, total_keywords)
                    
                search_results = await self.search_groups(
                    keywords=[keyword],
                    match_all=filters.get('match_all', False),
                    min_participants=filters.get('min_participants', 0),
                    max_participants=filters.get('max_participants'),
                    group_type=filters.get('group_type', 'all')
                )
                
                results.extend([r for r in search_results if r not in results])
                await asyncio.sleep(self.rate_limit_delay)
                
            return results
            
        except Exception as e:
            logging.error(f"Smart search failed: {e}")
            raise

    async def navigate_channel_history(self, channel: Channel, limit: int = 100) -> List[Any]:
        """Navigate through channel history with rate limiting."""
        try:
            messages = []
            async for message in self.client.iter_messages(channel, limit=limit):
                messages.append(message)
                await asyncio.sleep(0.1)  # Prevent flooding
            return messages
        except Exception as e:
            logging.error(f"Failed to navigate channel history: {e}")
            return []

    async def check_group_activity(self, group: Channel) -> Dict[str, Any]:
        """Check group activity metrics."""
        try:
            full_chat = await self.client(GetFullChannelRequest(channel=group))
            last_messages = await self.navigate_channel_history(group, limit=10)
            
            return {
                'members_online': getattr(full_chat.full_chat, 'online_count', 0),
                'total_members': getattr(full_chat.full_chat, 'participants_count', 0),
                'messages_per_day': len(last_messages),
                'has_recent_activity': bool(last_messages)
            }
        except Exception as e:
            logging.error(f"Failed to check group activity: {e}")
            return {}

    async def join_groups_batch(self, groups: List[Union[str, Channel]], delay: float = 2.0) -> List[Channel]:
        """Join multiple groups with rate limiting."""
        joined_groups = []
        for group in groups:
            try:
                result = await self.join_group(group)
                if result:
                    joined_groups.append(result)
                await asyncio.sleep(delay)  # Rate limiting delay
            except Exception as e:
                logging.error(f"Failed to join group {group}: {e}")
                continue
        return joined_groups

    async def verify_group_access(self, group: Channel) -> Dict[str, bool]:
        """Verify various access permissions for a group."""
        try:
            permissions = {
                'can_view_participants': await self.can_access_participants(group),
                'can_send_messages': group.creator or not group.left,
                'can_invite_users': group.creator or getattr(group, 'admin_rights', None) is not None,
                'is_banned': getattr(group, 'banned_rights', None) is not None
            }
            return permissions
        except Exception as e:
            logging.error(f"Failed to verify group access: {e}")
            return {}

    async def get_message_history(
        self, 
        channel: Channel,
        limit: int = 100,
        min_id: Optional[int] = None,
        max_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get message history with metadata."""
        messages = []
        try:
            async for message in self.client.iter_messages(
                channel,
                limit=limit,
                min_id=min_id,
                max_id=max_id
            ):
                messages.append({
                    'id': message.id,
                    'text': message.text,
                    'date': message.date,
                    'from_id': message.from_id,
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0)
                })
                await asyncio.sleep(0.1)  # Rate limiting
            return messages
        except Exception as e:
            logging.error(f"Failed to get message history: {e}")
            return []

    async def analyze_group_activity(self, group: Channel, days: int = 7) -> Dict[str, Any]:
        """Analyze group activity metrics over time."""
        try:
            messages = await self.get_message_history(group, limit=100)
            active_members = set()
            message_count = len(messages)
            
            stats = {
                'total_messages': message_count,
                'messages_per_day': message_count / days if days > 0 else 0,
                'unique_posters': len(active_members),
                'has_recent_activity': bool(messages),
                'last_message_date': messages[0]['date'] if messages else None
            }
            return stats
        except Exception as e:
            logging.error(f"Failed to analyze group activity: {e}")
            return {}

    async def get_filtered_participants(
        self,
        group: Channel,
        filter_criteria: Dict[str, Any],
        limit: Optional[int] = None
    ) -> List[User]:
        """Get participants filtered by criteria."""
        try:
            all_participants = await self.client.get_participants(group, limit=limit)
            filtered = []
            
            for participant in all_participants:
                if all(self._matches_criteria(participant, key, value) 
                      for key, value in filter_criteria.items()):
                    filtered.append(participant)
                await asyncio.sleep(0.05)  # Gentle rate limiting
                
            return filtered
        except Exception as e:
            logging.error(f"Failed to get filtered participants: {e}")
            return []

    def _matches_criteria(self, user: User, key: str, value: Any) -> bool:
        """Helper method to match user against criteria."""
        try:
            if key == 'has_username':
                return bool(user.username) == value
            elif key == 'is_bot':
                return user.bot == value
            elif key == 'has_phone':
                return bool(getattr(user, 'phone', None)) == value
            elif key == 'is_active':
                return isinstance(user.status, (UserStatusOnline, UserStatusRecently))
            return True
        except Exception:
            return False

    async def analyze_user_activity(self, user: User) -> Dict[str, Any]:
        """Analyze user activity patterns."""
        try:
            messages = []
            activity_times = []
            groups_count = 0
            
            async for dialog in self.client.iter_dialogs():
                if isinstance(dialog.entity, Channel):
                    groups_count += 1
                    try:
                        async for message in self.client.iter_messages(
                            dialog.entity, 
                            from_user=user.id, 
                            limit=100
                        ):
                            messages.append(message)
                            activity_times.append(message.date.hour)
                    except Exception:
                        continue
                        
            return {
                'total_messages': len(messages),
                'groups_participated': groups_count,
                'peak_activity_hour': max(set(activity_times), key=activity_times.count) if activity_times else None,
                'last_seen': getattr(user.status, 'was_online', None),
                'is_active': isinstance(user.status, (UserStatusOnline, UserStatusRecently))
            }
            
        except Exception as e:
            logging.error(f"Failed to analyze user activity: {e}")
            return {}

    async def export_group_data(self, group: Channel, export_path: str) -> bool:
        """Export group data to JSON format."""
        try:
            group_info = await self.get_chat_info(group)
            participants = await self.get_participants(group)
            messages = await self.get_message_history(group, limit=1000)
            
            export_data = {
                'group_info': group_info,
                'participants': [self.extract_user_info(p) for p in participants],
                'messages': messages,
                'exported_at': str(datetime.now())
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            return True
            
        except Exception as e:
            logging.error(f"Failed to export group data: {e}")
            return False

    async def monitor_group_changes(
        self, 
        group: Channel, 
        interval: int = 3600,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """Monitor group for changes with periodic checks."""
        try:
            initial_state = await self.get_chat_info(group)
            initial_members = len(await self.get_participants(group))
            
            while True:
                await asyncio.sleep(interval)
                
                current_state = await self.get_chat_info(group)
                current_members = len(await self.get_participants(group))
                
                changes = {
                    'title_changed': initial_state['title'] != current_state['title'],
                    'description_changed': initial_state['description'] != current_state['description'],
                    'members_delta': current_members - initial_members,
                    'timestamp': datetime.now()
                }
                
                if callback and any(changes.values()):
                    callback(changes)
                    
                initial_state = current_state
                initial_members = current_members
                
        except Exception as e:
            logging.error(f"Failed to monitor group changes: {e}")
            raise

    async def batch_process_groups(
        self,
        groups: List[Channel],
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Process multiple groups with specified action."""
        results = {
            'successful': [],
            'failed': [],
            'skipped': []
        }
        
        for group in groups:
            try:
                if action == 'join':
                    result = await self.join_group(group)
                elif action == 'leave':
                    result = await self.client(LeaveChannelRequest(group))
                elif action == 'analyze':
                    result = await self.analyze_group_activity(group)
                elif action == 'export':
                    result = await self.export_group_data(group, kwargs.get('export_path'))
                else:
                    results['skipped'].append({'group': group, 'reason': 'Unknown action'})
                    continue
                    
                if result:
                    results['successful'].append(group)
                else:
                    results['failed'].append(group)
                    
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logging.error(f"Error processing group {group.title}: {e}")
                results['failed'].append({'group': group, 'error': str(e)})
                
        return results

    async def find_similar_groups(
        self, 
        group: Channel,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Find groups similar to the given one based on various metrics."""
        try:
            base_info = await self.get_chat_info(group)
            base_participants = await self.get_participants(group)
            base_messages = await self.get_message_history(group, limit=100)
            
            similar_groups = []
            base_keywords = set(self._extract_keywords(base_info['title'] + ' ' + base_info['description']))
            
            async for dialog in self.client.iter_dialogs():
                if isinstance(dialog.entity, Channel) and dialog.entity.id != group.id:
                    try:
                        current_info = await self.get_chat_info(dialog.entity)
                        current_keywords = set(self._extract_keywords(
                            current_info['title'] + ' ' + current_info['description']
                        ))
                        
                        similarity = len(base_keywords & current_keywords) / len(base_keywords | current_keywords)
                        
                        if similarity >= min_similarity:
                            similar_groups.append({
                                'group': dialog.entity,
                                'similarity_score': similarity,
                                'info': current_info
                            })
                            
                    except Exception as e:
                        logging.error(f"Error processing group {dialog.entity.id}: {e}")
                        continue
                        
            return sorted(similar_groups, key=lambda x: x['similarity_score'], reverse=True)
            
        except Exception as e:
            logging.error(f"Failed to find similar groups: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text."""
        words = re.findall(r'\w+', text.lower())
        # Remove common words and short terms
        return [w for w in words if len(w) > 3 and w not in COMMON_WORDS]

    async def handle_rate_limit(self, e: errors.FloodWaitError) -> None:
        """Smart rate limit handling with exponential backoff."""
        wait_time = e.seconds * (1 + random.random() * 0.1)  # Add some randomness
        logging.warning(f"Rate limit hit. Waiting {wait_time:.2f} seconds")
        await asyncio.sleep(wait_time)

    async def collect_message_media(
        self, 
        channel: Channel,
        days_back: int = 7,
        media_types: List[str] = ['photo', 'document', 'video']
    ) -> List[Dict[str, Any]]:
        """Collect media from channel messages."""
        try:
            media_items = []
            async for message in self.client.iter_messages(
                channel,
                limit=None,
                offset_date=datetime.now() - timedelta(days=days_back)
            ):
                if not message.media:
                    continue
                    
                if (isinstance(message.media, MessageMediaPhoto) and 'photo' in media_types) or \
                   (isinstance(message.media, MessageMediaDocument) and \
                    any(t in media_types for t in ['document', 'video'])):
                    
                    media_items.append({
                        'message_id': message.id,
                        'date': message.date,
                        'type': type(message.media).__name__,
                        'file_size': getattr(message.media, 'size', None),
                        'mime_type': getattr(message.media, 'mime_type', None)
                    })
                    
                await asyncio.sleep(0.1)  # Rate limiting
                
            return media_items
            
        except Exception as e:
            logging.error(f"Failed to collect media: {e}")
            return []

    async def get_message_statistics(
        self, 
        channel: Channel,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """Get detailed message statistics."""
        try:
            messages = await self.get_message_history(
                channel,
                limit=None,
                min_id=None,
                max_id=None
            )
            
            stats = {
                'total_messages': len(messages),
                'media_messages': len([m for m in messages if m.get('media')]),
                'text_messages': len([m for m in messages if m.get('text')]),
                'average_length': sum(len(m.get('text', '')) for m in messages) / len(messages) if messages else 0,
                'active_hours': self._analyze_message_times([m['date'] for m in messages]),
                'engagement': {
                    'views': sum(m.get('views', 0) for m in messages),
                    'forwards': sum(m.get('forwards', 0) for m in messages)
                }
            }
            
            return stats
            
        except Exception as e:
            logging.error(f"Failed to get message statistics: {e}")
            return {}

    def _analyze_message_times(self, timestamps: List[datetime]) -> Dict[int, int]:
        """Analyze message timing patterns."""
        hour_counts = {}
        for ts in timestamps:
            hour = ts.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        return dict(sorted(hour_counts.items()))

    async def get_entity_safe(self, identifier: Any, retries: int = 3) -> Optional[Union[types.User, types.Chat, types.Channel]]:
        """Safely get entity with retries and error handling."""
        for attempt in range(retries):
            try:
                if not await self.ensure_connected():
                    raise Exception("Not connected to Telegram")
                
                entity = await self.client.get_entity(identifier)
                await asyncio.sleep(self.rate_limit_delay)  # Basic rate limiting
                return entity
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                logging.info(f"Sleeping for {wait_time}s on GetEntity flood wait")
                await asyncio.sleep(wait_time)
                continue
                
            except errors.UsernameNotOccupiedError:
                logging.warning(f"Username {identifier} not found")
                return None
                
            except (errors.RPCError, ValueError) as e:
                if attempt == retries - 1:
                    logging.error(f"Failed to get entity after {retries} attempts: {e}")
                    return None
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        return None

    async def get_full_channel_safe(self, channel: Channel, retries: int = 3) -> Optional[types.messages.ChatFull]:
        """Safely get full channel info with retries and error handling."""
        for attempt in range(retries):
            try:
                full = await self.client(GetFullChannelRequest(channel=channel))
                await asyncio.sleep(self.rate_limit_delay)
                return full
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                logging.info(f"Sleeping for {wait_time}s on GetFullChannel flood wait")
                await asyncio.sleep(wait_time)
                if attempt < retries - 1:
                    continue
                    
            except errors.ChannelPrivateError:
                logging.warning(f"Channel {channel.id} is private")
                return None
                
            except Exception as e:
                if attempt == retries - 1:
                    logging.error(f"Failed to get full channel info: {e}")
                    return None
                await asyncio.sleep(2 ** attempt)
                
        return None

    async def search_groups(self, keywords: List[str], match_all: bool = False,
                          min_participants: int = 0, max_participants: Optional[int] = None,
                          group_type: str = 'all', stop_flag: Optional[Callable[[], bool]] = None,
                          pause_flag: Optional[Callable[[], bool]] = None) -> List[Channel]:
        """Search for groups with improved error handling and rate limiting."""
        if not await self.ensure_connected():
            raise Exception("Failed to ensure connection")

        results = []
        try:
            for query in keywords:
                if stop_flag and stop_flag():
                    break

                while pause_flag and pause_flag():
                    await asyncio.sleep(0.1)
                    if stop_flag and stop_flag():
                        break

                try:
                    # Проверьте строку 1024 и исправьте синтаксические ошибки
                    def example_function():
                        pass  # Убедитесь, что все блоки корректно завершены

                    await self.client(functions.contacts.SearchRequest(
                        q=query,
                        limit=100
                    ))
                    await asyncio.sleep(self.rate_limit_delay)

                    for chat in getattr(search_results, 'chats', []):
                        if not isinstance(chat, Channel):
                            continue

                        if any(existing.id == chat.id for existing in results):
                            continue

                        try:
                            full_chat = await self.get_full_channel_safe(chat)
                            if not full_chat:
                                continue

                            participants_count = getattr(full_chat.full_chat, 'participants_count', 0)

                            if participants_count < min_participants:
                                continue
                            if max_participants and participants_count > max_participants:
                                continue

                            if group_type.lower() != 'all':
                                if group_type.lower() == 'megagroup' and not chat.megagroup:
                                    continue
                                if group_type.lower() == 'broadcast' and not chat.broadcast:
                                    continue

                            chat.participants_count = participants_count
                            results.append(chat)

                        except errors.FloodWaitError as e:
                            logging.warning(f"Hit rate limit, waiting {e.seconds} seconds")
                            await asyncio.sleep(e.seconds)
                            continue
                            
                        except Exception as e:
                            logging.error(f"Error processing channel {getattr(chat, 'id', 'unknown')}: {e}")
                            continue

                        await asyncio.sleep(self.rate_limit_delay)

                except Exception as e:
                    logging.error(f"Error during search iteration: {e}")
                    continue

            return sorted(results, key=lambda x: getattr(x, 'participants_count', 0) or 0, reverse=True)

        except Exception as e:
            logging.error(f"Error in search_groups: {e}")
            raise

    async def get_participants_with_fallback(self, group: Channel) -> List[User]:
        """Try to get participants using bot first, fall back to account if needed."""
        if self.bot_manager:
            try:
                await self.bot_manager.monitor_group(group.id, {'bot_workload': {
                    'max_monitored_members_per_group': 100
                }})
                if result and result['bot_accessible']:
                    return result['members']
            except Exception as e:
                logging.warning(f"Bot failed to get participants, falling back to account: {e}")
        
        return await self.get_participants(group)

    async def get_user_profile_with_fallback(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Try to get user profile using bot first, fall back to account if needed."""
        if self.bot_manager:
            try:
                await self.bot_manager.get_profile_data(user_id)
                if profile:
                    return profile
            except Exception as e:
                logging.warning(f"Bot failed to get profile, falling back to account: {e}")
        
        try:
            await self.client.get_entity(user_id)
            return self.extract_user_info(user)
        except Exception as e:
            logging.error(f"Failed to get user profile: {e}")
            return None

    async def is_bot_connected(self) -> bool:
        """Check if bot is connected and working."""
        try:
            if not self.bot_manager:
                return False
                
            return self.bot_manager._connected
            
        except Exception as e:
            logging.error(f"Error checking bot connection: {e}")
            return False

    async def check_bot_status(self, bot_token: str) -> bool:
        """Check if bot is active and responsive."""
        try:
            if not self.bot_manager:
                logging.warning("Bot manager not initialized")
                return False
                
            if self.bot_manager.bot_token == bot_token and self.bot_manager._connected:
                await self.bot_manager.check_status()
                return status['ok']
            
            if self.bot_manager.bot_token != bot_token:
                logging.info("Bot token changed, reinitializing bot manager")
                await self.bot_manager.stop()
                self.bot_manager = BotManager(
                    bot_token=bot_token,
                    api_id=self.api_id,
                    api_hash=self.api_hash
                )
                self.bot_manager.set_config_manager(self.config_manager)
            
            if not self.bot_manager._connected:
                logging.info("Connecting bot...")
                await self.bot_manager.start()
                
            await self.bot_manager.check_status()
            is_connected = status['ok']
            
            if is_connected:
                logging.info("Bot connection check successful")
            else:
                logging.warning(f"Bot connection check failed: {status.get('details', 'Unknown error')}")
                
            return is_connected
            
        except Exception as e:
            logging.error(f"Error checking bot status: {e}")
            if self.config_manager:
                self.config_manager.update_bot_status('error', str(e))
            return False

    async def get_bot_info(self, bot_token: str) -> Dict[str, Any]:
        """
        Get information about the bot.
        
        Args:
            bot_token: The bot's authentication token
            
        Returns:
            Dict containing bot information (name, username etc)
        """
        try:
            if not self.bot_manager or not await self.check_bot_status(bot_token):
                return {}
                
            await self.bot_manager.bot.get_me()
            
            return {
                'id': bot_user.id,
                'first_name': bot_user.first_name,
                'username': bot_user.username,
                'can_join_groups': bot_user.bot_chat_history,
                'can_read_messages': bot_user.bot_inline_geo,
                'supports_inline': bot_user.bot_inline_placeholder is not None
            }
            
        except Exception as e:
            logging.error(f"Error getting bot info: {e}")
            return {}

    async def is_bot_connected(self) -> bool:
        """Check if bot is currently connected."""
        try:
            if not self.bot_manager:
                return False
                
            return self.bot_manager._connected
            
        except Exception as e:
            logging.error(f"Error checking bot connection: {e}")
            return False

    async def delegate_task(self, task_type: str, target_id: int, **kwargs) -> Dict[str, Any]:
        """Умное делегирование задач между ботом и аккаунтом."""
        result = {
            'success': False,
            'data': None,
            'executor': None,
            'error': None
        }
        
        try:
            # Сначала пробуем через бота
            if self.bot_manager and await self.bot_manager.is_connected():
                try:
                    if task_type == 'get_participants':
                        result['data'] = await self.bot_manager.get_group_members(target_id)
                        result['executor'] = 'bot'
                        result['success'] = True
                        return result
                except Exception as e:
                    logging.warning(f"Bot failed task {task_type}: {e}, falling back to account")

            # Если бот не смог или недоступен - используем аккаунт
            if await self.is_connected():
                if task_type == 'get_participants':
                    entity = await self.get_entity(target_id)
                    result['data'] = await self.get_participants(entity)
                    result['executor'] = 'account'
                    result['success'] = True
                    return result
                    
            raise Exception("Neither bot nor account could complete the task")
            
        except Exception as e:
            result['error'] = str(e)
            logging.error(f"Task delegation failed: {e}")
            
        return result

    async def smart_scan_group(self, group_id: int) -> Dict[str, Any]:
        """Умное сканирование группы с автоматическим выбором метода."""
        scan_result = {
            'members': [],
            'method_used': None,
            'success': False,
            'error': None
        }
        
        try:
            # Проверяем конфигурацию и лимиты
            account_config = self.config_manager.get_account_config()
            bot_config = self.config_manager.get_bot_config()
            
            # Пробуем сначала через бота если он настроен
            if bot_config.get('token') and self.bot_manager:
                try:
                    members = await self.bot_manager.get_group_members(group_id)
                    if members:
                        scan_result['members'] = members
                        scan_result['method_used'] = 'bot'
                        scan_result['success'] = True
                        return scan_result
                except Exception as e:
                    logging.warning(f"Bot scan failed: {e}, trying account")

            # Если бот не справился или недоступен - используем аккаунт
            if account_config.get('backup_scan', {}).get('enabled', True):
                members = await self.get_participants(group_id)
                scan_result['members'] = members
                scan_result['method_used'] = 'account'
                scan_result['success'] = True
                return scan_result
                
        except Exception as e:
            scan_result['error'] = str(e)
            logging.error(f"Smart scan failed: {e}")
            
        return scan_result

    async def get_participants_with_fallback(self, group: Channel) -> List[User]:
        """Try to get participants using bot first, fall back to account if needed."""
        if self.bot_manager:
            try:
                await self.bot_manager.monitor_group(group.id, {'bot_workload': {
                    'max_monitored_members_per_group': 100
                }})
                if result and result['bot_accessible']:
                    return result['members']
            except Exception as e:
                logging.warning(f"Bot failed to get participants, falling back to account: {e}")
        
        return await self.get_participants(group)

    async def get_user_profile_with_fallback(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Try to get user profile using bot first, fall back to account if needed."""
        if self.bot_manager:
            try:
                await self.bot_manager.get_profile_data(user_id)
                if profile:
                    return profile
            except Exception as e:
                logging.warning(f"Bot failed to get profile, falling back to account: {e}")
        
        try:
            await self.client.get_entity(user_id)
            return self.extract_user_info(user)
        except Exception as e:
            logging.error(f"Failed to get user profile: {e}")
            return None

    async def is_bot_connected(self) -> bool:
        """Check if bot is connected and working."""
        try:
            if not self.bot_manager:
                return False
                
            return self.bot_manager._connected
            
        except Exception as e:
            logging.error(f"Error checking bot connection: {e}")
            return False

