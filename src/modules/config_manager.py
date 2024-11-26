# modules/config_manager.py

import json
import logging
import os
import random
import tempfile
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class LoadBalancer:
    def __init__(self):
        self.last_request_time: Optional[datetime] = None
        self.request_count = 0
        self.time_window = timedelta(hours=1)  # Track requests per hour
        self.window_start = datetime.now()
        self.max_requests_per_window = float('inf')  # Unlimited requests
        
        # Dynamic delay parameters
        self.base_delay = 2.0  # Base delay in seconds
        self.max_delay = 10.0  # Maximum delay in seconds 
        self.backoff_factor = 1.5  # Multiplier for exponential backoff

    def calculate_delay(self) -> float:
        """Calculate dynamic delay based on request patterns."""
        current_time = datetime.now()
        
        # Reset counter for new time window
        if current_time - self.window_start > self.time_window:
            self.request_count = 0
            self.window_start = current_time

        # Calculate load factor (0.0 to 1.0)
        load_factor = self.request_count / (self.max_requests_per_window or 1)
        
        # 4 levels of load with proportional delays
        if load_factor < 0.25:
            delay = self.base_delay
        elif load_factor < 0.5:
            delay = self.base_delay * 2
        elif load_factor < 0.75:
            delay = self.base_delay * 3
        else:
            delay = self.base_delay * self.backoff_factor ** (load_factor * 10)
            
        # Add randomization (±20%)
        jitter = random.uniform(-0.2, 0.2) * delay
        final_delay = min(delay + jitter, self.max_delay)
        
        return max(final_delay, 0.5)  # Ensure minimum delay of 0.5s

    def add_jitter(self, delay: float, jitter_factor: float = 0.1) -> float:
        """Add random jitter to delay."""
        jitter = random.uniform(-jitter_factor, jitter_factor) * delay
        return delay + jitter

class MessageRateLimit:
    def __init__(self):
        self.message_count = 0
        self.last_reset = datetime.now()
        
    def reset_if_needed(self):
        now = datetime.now()
        if now.date() > self.last_reset.date():
            self.message_count = 0
            self.last_reset = now
            
    def can_send_message(self, max_messages: int) -> bool:
        self.reset_if_needed()
        return self.message_count < max_messages
        
    def increment(self):
        self.message_count += 1

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        
        # Initialize default configuration
        self.default_config = {
            'telegram': {
                'api_id': '',
                'api_hash': '',
                'phone_number': ''
            },
            'database': {
                'host': '127.0.0.1',
                'user': 'root',
                'password': '',
                'database': 'telegram_db'
            },
            'interface': {
                'transparency': 100,
                'language': 'uk',
                'theme': 'hacker'
            },
            'limits': {
                'max_accounts': 5,
                'max_groups_per_account': 20,
                'max_messages_per_day': 100,
                'delay_min': 2,
                'delay_max': 5,
                'delay_presets': {
                    'cautious': {
                        'base_delay': 3.0,
                        'max_delay': 15.0,
                        'requests_per_hour': 50
                    },
                    'normal': {
                        'base_delay': 2.0,
                        'max_delay': 10.0,
                        'requests_per_hour': 100
                    },
                    'aggressive': {
                        'base_delay': 1.0,
                        'max_delay': 5.0,
                        'requests_per_hour': 200
                    }
                }
            },
            # Add bot configuration to default_config
            'bot': {
                'token': '',
                'api_id': '',
                'api_hash': '',
                'description': 'Bot configuration',
                'max_daily_messages': 1000,
                'scan_delay_min': 5,
                'scan_delay_max': 10,
                'session_name': 'bot_session',
                'workload': {
                    'max_monitored_groups': 50,
                    'max_monitored_members_per_group': 100,
                },
                'profile_data': {
                    'enabled': True,
                    'description': 'Bot collects user profile data'
                }
            }
        }
        
        # Load configuration
        self.load_config()
        
        self.load_balancer = LoadBalancer()
        self.message_limiter = MessageRateLimit()

    def load_config(self):
        """Завантажує конфігурацію з файлу."""
        if os.path.exists(self.config_file):
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True)
                
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                
                # Ініціалізуємо відсутні секції значеннями за замовчуванням
                default_config = self.get_default_config()
                for section in default_config:
                    if section not in self.config:
                        self.config[section] = default_config[section]
                        logging.warning(f"Added missing section '{section}' with default values")
                
                # Перевірка наявності та правильності telegram.api_id
                telegram_api_id = self.config.get('telegram', {}).get('api_id')
                if telegram_api_id is None or telegram_api_id == '':
                    logging.error("Telegram API ID відсутній або порожній у конфігурації.")
                    raise ValueError("Telegram API ID відсутній або порожній у конфігурації.")
                
                if isinstance(telegram_api_id, str):
                    if telegram_api_id.strip() == '':
                        logging.error("Telegram API ID не може бути порожнім.")
                        raise ValueError("Telegram API ID не може бути порожнім.")
                    try:
                        self.config['telegram']['api_id'] = int(telegram_api_id)
                    except ValueError:
                        logging.error("Telegram API ID повинен бути цілим числом.")
                        raise
                
                elif isinstance(telegram_api_id, (int, float)):
                    self.config['telegram']['api_id'] = int(telegram_api_id)
                else:
                    logging.error("Невідповідний тип для Telegram API ID.")
                    raise TypeError("Невідповідний тип для Telegram API ID.")
                
                try:
                    self.config['telegram']['api_hash'] = str(self.config['telegram']['api_hash'])
                    self.config['telegram']['phone_number'] = str(self.config['telegram']['phone_number'])
                except (ValueError, TypeError):
                    logging.error("Неверный формат данных в разделе telegram.")
                    self.config['telegram']['api_hash'] = self.default_config['telegram']['api_hash']
                    self.config['telegram']['phone_number'] = self.default_config['telegram']['phone_number']
                
                logging.info(f"Configuration loaded from {self.config_file}")
                
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse config file: {e}")
                self.config = self.get_default_config()
            except (ValueError, TypeError) as e:
                logging.error(f"Configuration validation error: {e}")
                self.config = self.get_default_config()
            except Exception as e:
                logging.error(f"Failed to load configuration: {e}")
                self.config = self.get_default_config()
        else:
            logging.warning(f"Configuration file {self.config_file} does not exist. Creating with default settings.")
            self.config = self.get_default_config()
        
        # Always try to save after loading to ensure file exists and is valid
        try:
            self.save_config()
        except Exception as e:
            logging.error(f"Failed to save initial configuration: {e}")

    def save_config(self):
        """Зберігає поточну конфігурацію до файлу атомарно."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True)
        
        temp_path = None
        try:
            # Create temporary file in the same directory
            dir_path = os.path.dirname(os.path.abspath(self.config_file))
            temp_fd, temp_path = tempfile.mkstemp(
                prefix='.config_',
                suffix='.tmp',
                dir=dir_path
            )
            
            # Write to temporary file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as tf:
                json.dump(self.config, tf, indent=4, ensure_ascii=False)
                tf.flush()  # Ensure all data is written
                os.fsync(tf.fileno())  # Force write to disk
            
            # Atomic replace
            os.replace(temp_path, self.config_file)
            logging.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            logging.error(f"Failed to save configuration: {e}")
            raise

    def is_config_complete(self) -> bool:
        """Перевіряє, чи всі необхідні поля заповнені в конфігурації."""
        required_fields = {
            'telegram': ['api_id', 'api_hash', 'phone_number'],
            'database': ['host', 'user', 'password', 'database']
        }
        
        # Initialize missing sections
        default_config = self.get_default_config()
        modified = False
        
        for section, fields in required_fields.items():
            if section not in self.config:
                self.config[section] = default_config[section]
                logging.warning(f"Initialized missing section '{section}' with default values")
                modified = True
            
            for field in fields:
                if field not in self.config[section] or not self.config[section][field]:
                    if field in default_config[section]:
                        self.config[section][field] = default_config[section][field]
                        logging.warning(f"Initialized missing field '{field}' in section '{section}' with default value")
                        modified = True
        
        # Ensure other important sections exist
        for section in ['limits', 'interface']:
            if section not in self.config:
                self.config[section] = default_config[section]
                modified = True
        
        if modified:
            self.save_config()
            
        return True

    def get_telegram_config(self) -> Dict[str, Any]:
        """Повертає конфігурацію для Telegram."""
        return self.config.get('telegram', {})

    def get_database_config(self) -> Dict[str, Any]:
        """Повертає конфігурацію для бази даних."""
        return self.config.get('database', {})

    def get_interface_config(self) -> Dict[str, Any]:
        """Повертає конфігурацію інтерфейсу."""
        return self.config.get('interface', {})

    def get_limits_config(self) -> Dict[str, Any]:
        """Повертає конфігурацію лімітів."""
        return self.config.get('limits', self.get_default_config()['limits'])

    def set_telegram_config(self, api_id: int, api_hash: str, phone_number: str):
        """Встановлює конфігурацію для Telegram."""
        self.config['telegram'] = {
            'api_id': api_id,
            'api_hash': api_hash,
            'phone_number': phone_number
        }

    def set_database_config(self, host: str, user: str, password: str, database: str, port: int = 3306):
        """Встановлює конфігурацію для бази даних."""
        self.config['database'] = {
            'host': host,
            'port': port,  # Add port parameter
            'user': user,
            'password': password,
            'database': database,
            'charset': 'utf8mb4'
        }

    def set_interface_config(self, transparency: int, language: str, theme: str):
        """Встановлює конфігурацію інтерфейсу."""
        self.config['interface'] = {
            'transparency': transparency,
            'language': language,
            'theme': theme
        }

    def set_limits_config(self, max_accounts: int, max_groups_per_account: int, max_messages_per_day: int):
        """Встановлює конфігурацію лімітів."""
        self.config['limits'] = {
            'max_accounts': max_accounts,
            'max_groups_per_account': max_groups_per_account,
            'max_messages_per_day': max_messages_per_day
        }

    def get_default_config(self) -> Dict[str, Any]:
        """Returns default configuration with all required sections."""
        return {
            'telegram': {
                'api_id': '',
                'api_hash': '',
                'phone_number': ''
            },
            'database': {
                'host': '127.0.0.1',
                'user': 'root',
                'password': '',
                'database': 'telegram_db'
            },
            'interface': {
                'transparency': 100,
                'language': 'uk',
                'theme': 'hacker'
            },
            'limits': {
                'max_accounts': 5,
                'max_groups_per_account': 20,
                'max_messages_per_day': 100,
                'delay_min': 2,
                'delay_max': 5
            },
            'general': {
                'description': 'Загальна конфігурація для роботи акаунтів і ботів',
                'max_accounts': 30,
                'max_groups_per_account': 50,
                'max_messages_per_day': 200
            },
            'account': {
                'description': 'Налаштування для акаунтів',
                'max_groups_per_scan': 10,
                'max_members_per_scan': 30,
                'scan_interval': 10,
                'api_access': {
                    'token': '',
                    'api_id': '',
                    'api_hash': '',
                },
                'workload': {
                    'max_daily_scans': 100,
                    'max_scan_retries': 3,
                },
                'backup_scan': {
                    'enabled': True,
                    'description': 'Акаунт збирає дані, якщо бот не отримав доступ'
                }
            },
            'bot': {
                'description': 'Налаштування для бота',
                'bot_token': '',
                'bot_api_id': '',
                'bot_api_hash': '',
                'max_daily_messages': 1000,
                'bot_scan_delay_min': 5,
                'bot_scan_delay_max': 10,
                'session_name': 'bot_session',
                'bot_workload': {
                    'max_monitored_groups': 50,
                    'max_monitored_members_per_group': 100,
                },
                'profile_data': {
                    'enabled': True,
                    'description': 'Бот збирає профільні дані учасників'
                }
            },
            'data_sync': {
                'description': 'Налаштування для синхронізації даних',
                'sync_interval': 10,
                'sync_retry_limit': 3,
            },
            'monitoring': {
                'description': 'Налаштування для моніторингу активності',
                'max_members_per_scan': 50,
                'bot_retry_limit': 5,
            }
        }

    def get_limit_presets(self) -> Dict[str, Dict[str, Any]]:
        return {
            'minimum': {
                'description': 'Безопасные лимиты для минимальной активности',
                'account_limits': {
                    'max_accounts': 1,
                    'max_groups_per_account': 5,
                    'max_messages_per_day': 50,
                    'delay_min': 3,
                    'delay_max': 7
                },
                'bot_limits': {
                    'max_bots': 1,
                    'max_groups_per_bot': 5,
                    'max_messages_per_day': 50,
                    'delay_min': 3,
                    'delay_max': 7
                }
            },
            'standard': {
                'description': 'Сбалансированные лимиты для обычного использования',
                'account_limits': {
                    'max_accounts': 3,
                    'max_groups_per_account': 15,
                    'max_messages_per_day': 100,
                    'delay_min': 2,
                    'delay_max': 5
                },
                'bot_limits': {
                    'max_bots': 2,
                    'max_groups_per_bot': 15,
                    'max_messages_per_day': 100,
                    'delay_min': 2,
                    'delay_max': 5
                }
            },
            'maximum': {
                'description': 'Повышенные лимиты для продвинутого использования',
                'account_limits': {
                    'max_accounts': 5,
                    'max_groups_per_account': 30,
                    'max_messages_per_day': 150,
                    'delay_min': 1,
                    'delay_max': 3
                },
                'bot_limits': {
                    'max_bots': 3,
                    'max_groups_per_bot': 30,
                    'max_messages_per_day': 150,
                    'delay_min': 1,
                    'delay_max': 3
                }
            },
            'unlimited': {
                'description': 'Unlimited requests with smart delays',
                'max_accounts': float('inf'),
                'max_groups_per_account': float('inf'),
                'max_messages_per_day': float('inf'),
                'delay_min': 2,
                'delay_max': 10,
                'requests_per_hour': float('inf')
            }
        }

    def apply_limit_preset(self, preset_name: str) -> bool:
        presets = self.get_limit_presets()
        if (preset_name in presets):
            preset = presets[preset_name]
            self.config['limits'] = preset.copy()
            self.config['limits']['preset'] = preset_name  # Store selected preset name
            self.save_config()
            return True
        return False

    def get_delay(self) -> tuple[float, float]:
        """Повертає налаштування затримки."""
        limits = self.get_limits_config()
        return (
            float(limits.get('delay_min', self.default_config['limits']['delay_min'])),
            float(limits.get('delay_max', self.default_config['limits']['delay_max']))
        )

    def delay(self):
        """Виконує затримку згідно з поточними налаштуваннями."""
        delay_min, delay_max = self.get_delay()
        time.sleep(random.uniform(delay_min, delay_max))

    def smart_delay(self):
        """Execute smart delay with load balancing."""
        delay = self.load_balancer.calculate_delay()
        time.sleep(delay)
        self.load_balancer.request_count += 1

    def set_delay_preset(self, preset_name: str):
        """Set delay configuration from preset."""
        presets = self.config['limits']['delay_presets']
        if preset_name in presets:
            preset = presets[preset_name]
            self.load_balancer.base_delay = preset['base_delay']
            self.load_balancer.max_delay = preset['max_delay']
            self.load_balancer.max_requests_per_window = preset['requests_per_hour']
            return True
        return False

    async def execute_with_rate_limit(self, func, *args, **kwargs):
        """Execute function with smart rate limiting."""
        try:
            self.smart_delay()
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            # Increase delay on error
            self.load_balancer.base_delay = min(
                self.load_balancer.base_delay * self.load_balancer.backoff_factor,
                self.load_balancer.max_delay
            )
            raise e

    def get_load_stats(self) -> Dict[str, Any]:
        """Get current load balancing statistics."""
        current_time = datetime.now()
        time_in_window = (current_time - self.load_balancer.window_start).total_seconds() / 3600
        
        return {
            'requests_in_window': self.load_balancer.request_count,
            'requests_per_hour': self.load_balancer.request_count / time_in_window if time_in_window > 0 else 0,
            'current_delay': self.load_balancer.calculate_delay(),
            'window_usage': (self.load_balancer.request_count / self.load_balancer.max_requests_per_window) * 100
        }

    async def can_send_message(self) -> bool:
        """Check if we can send more messages today"""
        limits_config = self.get_limits_config()
        max_messages = limits_config.get('max_messages_per_day', 100)
        return self.message_limiter.can_send_message(max_messages)
        
    async def log_message_sent(self):
        """Record that a message was sent"""
        self.message_limiter.increment()

    async def get_remaining_messages(self) -> int:
        """Get how many messages we can still send today"""
        limits_config = self.get_limits_config()
        max_messages = limits_config.get('max_messages_per_day', 100)
        self.message_limiter.reset_if_needed()
        return max_messages - self.message_limiter.message_count

    def get_bot_config(self) -> Dict[str, Any]:
        """Returns bot-specific configuration with defaults."""
        bot_config = self.config.get('bot', {}).copy()
        default_bot = self.default_config['bot']
        for key, value in default_bot.items():
            if key not in bot_config:
                bot_config[key] = value

        # Ensure critical fields exist
        if 'token' not in bot_config:
            bot_config['token'] = ''

        return bot_config

    def set_bot_config(self, token: str, api_id: Optional[str] = None, api_hash: str = ''):
        """Sets bot configuration."""
        if 'bot' not in self.config:
            self.config['bot'] = {}

        self.config['bot'].update({
            'token': token,
            'api_id': api_id,
            'api_hash': api_hash,
            'created_at': datetime.now().isoformat()
        })
        self.save_config()

    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status from config."""
        try:
            bot_config = self.config.get('bot', {})
            return {
                'status': bot_config.get('status', 'unknown'),
                'last_error': bot_config.get('last_error'),
                'last_active': bot_config.get('last_active'),
                'created_at': bot_config.get('created_at'),
                'is_configured': bool(bot_config.get('token'))
            }
        except Exception as e:
            logging.error(f"Failed to get bot status: {e}")
            return {
                'status': 'error',
                'last_error': str(e),
                'is_configured': False
            }

    def update_bot_status(self, status: str, error: str = None):
        """
        Updates bot status information.
        
        Args:
            status: Current bot status (active/error/disconnected)
            error: Optional error message if status is error
        """
        try:
            if 'bot' not in self.config:
                self.config['bot'] = {}
            
            self.config['bot'].update({
                'status': status,
                'last_error': error if error else None,
                'last_active': datetime.now().isoformat() if status == 'active' else None
            })
            
            self.save_config()
            
        except Exception as e:
            logging.error(f"Failed to update bot status: {e}")

    def get_account_config(self) -> Dict[str, Any]:
        """Returns account-specific configuration."""
        return self.config.get('account', {})

    def get_sync_config(self) -> Dict[str, Any]:
        """Returns data synchronization configuration."""
        return self.config.get('data_sync', {})

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Returns monitoring configuration."""
        return self.config.get('monitoring', {})

    def get_config(self) -> Dict[str, Any]:
        """Returns the entire configuration."""
        return self.config

    def update_session_status(self, status: str) -> None:
        """Update session status in config."""
        self.config['bot']['session_status'] = status
        self.save_config()

class DatabaseModule:
    # ...existing code...

    async def ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        if not self.pool:
            logging.error("Database connection is not established.")
            return
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    for table_name, schema in self.TABLE_SCHEMAS.items():
                        await cursor.execute(schema)
        except Exception as e:
            logging.error(f"Failed to ensure tables exist: {e}")

if __name__ == "__main__":
    pass