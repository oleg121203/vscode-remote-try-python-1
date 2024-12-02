# modules/mdb1_database.py

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import aiomysql
import pymysql

with open('/workspaces/vscode-remote-try-python/config.json', 'r') as config_file:
    config = json.load(config_file)
    db_config = config['database']

print(f"Connecting to database with config: {db_config}")

# Remove the initial synchronous connection attempt
# connection = pymysql.connect(**db_config)
# cursor = connection.cursor()
# cursor.execute("SELECT DATABASE();")
# database_name = cursor.fetchone()
# print(f"Connected to database: {database_name}")
# cursor.close()
# connection.close()


class DatabaseModule:
    # Table schemas
    USERS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            username VARCHAR(255),
            phone VARCHAR(50),
            is_bot BOOLEAN,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_phone (phone)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """

    GROUPS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS `groups` (
            id BIGINT PRIMARY KEY,
            title VARCHAR(255),
            username VARCHAR(255),
            participants_count INT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_username (username),
            INDEX idx_participants (participants_count)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """

    PARTICIPANTS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS participants (
            user_id BIGINT,
            group_id BIGINT,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            username VARCHAR(255),
            phone VARCHAR(50),
            is_bot BOOLEAN,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, group_id),
            INDEX idx_user_id (user_id),
            INDEX idx_group_id (group_id)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """

    TABLE_SCHEMAS = {
        'users': USERS_TABLE_SCHEMA,
        'groups': GROUPS_TABLE_SCHEMA,
        'participants': PARTICIPANTS_TABLE_SCHEMA
    }

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port  # Add port parameter
        self.pool: Optional[aiomysql.Pool] = None
        self._is_closing = False

    async def connect(self):
        """Подключается к базе данных и создает пул соединений."""
        try:
            if self._is_closing:
                return
            
            logging.info(f"Attempting to connect to database at {self.host}:{self.port}")
            
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                charset='utf8mb4'
            )
            
            # Test the connection
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT VERSION()")
                    version = await cur.fetchone()
                    logging.info(f"Successfully connected to MySQL version: {version[0]}")
                    
            self._is_closing = False
            logging.info(f"Database connection pool created successfully")
            
        except Exception as e:
            logging.error(f"Failed to connect to database: {str(e)}")
            if 'Connection refused' in str(e):
                logging.error(f"Make sure MySQL is running and accessible at {self.host}:{self.port}")
            self.pool = None
            raise

    async def disconnect(self):
        """Закрывает пул соединений с базой данных."""
        if not self.pool or self._is_closing:
            return False
            
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
            return True
        except:
            return False

    async def ensure_connection(self):
        """Проверяет и восстанавливает соединение при необходимости."""
        if not await self.is_connected():
            await self.reopen()

    async def execute_with_retry(self, operation):
        """Выполняет операцию с базой данных, повторяя при ошибках соединения."""
        try:
            await self.ensure_connection()
            return await operation()
        except Exception as e:
            logging.error(f"Database operation failed: {e}")
            await self.reopen()
            return await operation()

    async def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT COUNT(*)
                        FROM information_schema.tables 
                        WHERE table_schema = %s 
                        AND table_name = %s
                    """, (self.database, table_name))
                    result = await cur.fetchone()
                    return result[0] > 0
        except Exception as e:
            logging.error(f"Error checking if table {table_name} exists: {e}")
            return False

    async def ensure_tables_exist(self):
        """Creates database tables if they don't exist, avoiding warnings."""
        if not self.pool:
            logging.error("Database connection is not established.")
            return
            
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Set connection character set
                    await cur.execute("SET NAMES utf8mb4")
                    await cur.execute("SET CHARACTER SET utf8mb4")
                    await cur.execute("SET character_set_connection=utf8mb4")
                    
                    # Create tables only if they don't exist
                    for table_name, schema in self.TABLE_SCHEMAS.items():
                        try:
                            exists = await self.check_table_exists(table_name)
                            if not exists:
                                await cur.execute(schema)
                                logging.info(f"Created new table '{table_name}'")
                            else:
                                logging.debug(f"Table '{table_name}' already exists")
                        except Exception as e:
                            logging.error(f"Error handling table '{table_name}': {e}")
                            raise
                            
                    await conn.commit()
                    
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            raise

    async def upsert_user(self, user_info: Dict[str, Any]):
        """Modified upsert to use new syntax with alias."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO users (id, first_name, last_name, username, phone, is_bot)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        AS new_user
                        ON DUPLICATE KEY UPDATE
                            first_name = new_user.first_name,
                            last_name = new_user.last_name,
                            username = new_user.username,
                            phone = new_user.phone,
                            is_bot = new_user.is_bot,
                            last_updated = CURRENT_TIMESTAMP
                    """, (
                        user_info['id'],
                        user_info.get('first_name'),
                        user_info.get('last_name'),
                        user_info.get('username'),
                        user_info.get('phone'),
                        user_info.get('is_bot', False)
                    ))
                    await conn.commit()
        except Exception as e:
            logging.error(f"Error upserting user {user_info['id']}: {e}")
            raise

    async def upsert_group(self, group_info: Dict[str, Any]):
        """Modified upsert to use new syntax with alias."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO `groups` (id, title, username, participants_count)
                        VALUES (%s, %s, %s, %s)
                        AS new_group
                        ON DUPLICATE KEY UPDATE
                            title = new_group.title,
                            username = new_group.username,
                            participants_count = new_group.participants_count,
                            last_updated = CURRENT_TIMESTAMP
                    """, (
                        group_info['id'],
                        group_info.get('title'),
                        group_info.get('username'),
                        group_info.get('participants_count')
                    ))
                    logging.debug(f"Group {group_info['id']} upserted.")
        except Exception as e:
            logging.error(f"Error upserting group {group_info['id']}: {e}")
            raise

    async def upsert_participant(self, participant_info: Dict[str, Any]):
        """Modified upsert to use new syntax with alias."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO participants (
                            user_id, group_id, first_name, last_name,
                            username, phone, is_bot
                        ) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        AS new_participant
                        ON DUPLICATE KEY UPDATE
                            first_name = new_participant.first_name,
                            last_name = new_participant.last_name,
                            username = new_participant.username,
                            phone = new_participant.phone,
                            is_bot = new_participant.is_bot,
                            last_updated = CURRENT_TIMESTAMP()
                    """
                    await cursor.execute(sql, (
                        participant_info['user_id'],
                        participant_info['group_id'],
                        participant_info.get('first_name'),
                        participant_info.get('last_name'),
                        participant_info.get('username'),
                        participant_info.get('phone'),
                        participant_info.get('is_bot'),
                    ))
        except Exception as e:
            logging.error(f"Failed to upsert participant: {e}")

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Отримує інформацію про користувача за його ID."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                    user = await cur.fetchone()
                    logging.debug(f"User fetched: {user}")
                    return user
        except Exception as e:
            logging.error(f"Error fetching user {user_id}: {e}")
            return None

    async def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """Отримує інформацію про групу за її ID."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM `groups` WHERE id = %s", (group_id,))
                    group = await cur.fetchone()
                    logging.debug(f"Group fetched: {group}")
                    return group
        except Exception as e:
            logging.error(f"Error fetching group {group_id}: {e}")
            return None

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Отримує список всіх користувачів."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM users")
                    users = await cur.fetchall()
                    logging.debug(f"Total users fetched: {len(users)}")
                    return users
        except Exception as e:
            logging.error(f"Error fetching all users: {e}")
            return []

    async def get_all_groups(self) -> List[Dict[str, Any]]:
        """Отримує список всіх груп."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute("SELECT * FROM `groups`")
                    groups = await cur.fetchall()
                    logging.debug(f"Total groups fetched: {len(groups)}")
                    return groups
        except Exception as e:
            logging.error(f"Error fetching all groups: {e}")
            return []

    async def delete_user(self, user_id: int):
        """Видаляє користувача за його ID."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                    logging.debug(f"User {user_id} deleted.")
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")
            raise

    async def delete_group(self, group_id: int):
        """Видаляє групу за її ID."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("DELETE FROM `groups` WHERE id = %s", (group_id,))
                    logging.debug(f"Group {group_id} deleted.")
        except Exception as e:
            logging.error(f"Error deleting group {group_id}: {e}")
            raise

    async def execute_custom_query(self, query: str, params: tuple = ()):
        """Виконує користувацький SQL-запит."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, params)
                    if query.strip().upper().startswith("SELECT"):
                        result = await cur.fetchall()
                        logging.debug(f"Custom query result: {result}")
                        return result
                    else:
                        logging.debug("Custom query executed.")
        except Exception as e:
            logging.error(f"Error executing custom query: {e}")
            raise

    async def cleanup_old_records(self, days: int = 30) -> int:
        """Clean up records older than specified days."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    cutoff_date = f"DATE_SUB(NOW(), INTERVAL {days} DAY)"
                    deleted_counts = {}
                    
                    for table in ['users', 'groups', 'participants']:
                        await cur.execute(f"""
                            DELETE FROM {table}
                            WHERE last_updated < {cutoff_date}
                        """)
                        deleted_counts[table] = cur.rowcount
                        
                    await conn.commit()
                    total_deleted = sum(deleted_counts.values())
                    logging.info(f"Cleaned up {total_deleted} old records")
                    return total_deleted
                    
        except Exception as e:
            logging.error(f"Failed to cleanup old records: {e}")
            return 0

    async def backup_table(self, table_name: str, backup_path: str) -> bool:
        """Backup a table to a SQL file."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Get table structure
                    await cur.execute(f"SHOW CREATE TABLE {table_name}")
                    table_structure = (await cur.fetchone())[1]
                    
                    # Get table data
                    await cur.execute(f"SELECT * FROM {table_name}")
                    rows = await cur.fetchall()
                    
                    with open(backup_path, 'w') as f:
                        f.write(f"{table_structure};\n\n")
                        
                        # Write data as INSERT statements
                        if rows:
                            columns = [d[0] for d in cur.description]
                            for row in rows:
                                values = ', '.join([
                                    'NULL' if v is None else f"'{str(v)}'" 
                                    for v in row
                                ])
                                f.write(
                                    f"INSERT INTO {table_name} "
                                    f"({', '.join(columns)}) VALUES ({values});\n"
                                )
                                
            logging.info(f"Successfully backed up table {table_name}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to backup table {table_name}: {e}")
            return False

    async def get_table_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about database tables."""
        try:
            stats = {}
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for table in ['users', 'groups', 'participants']:
                        await cur.execute(f"""
                            SELECT 
                                COUNT(*) as total,
                                COUNT(DISTINCT username) as unique_usernames,
                                COUNT(DISTINCT phone) as unique_phones,
                                SUM(CASE WHEN last_updated > DATE_SUB(NOW(), INTERVAL 24 HOUR)
                                    THEN 1 ELSE 0 END) as updated_24h
                            FROM {table}
                        """)
                        row = await cur.fetchone()
                        stats[table] = {
                            'total': row[0],
                            'unique_usernames': row[1],
                            'unique_phones': row[2],
                            'updated_24h': row[3]
                        }
            return stats
            
        except Exception as e:
            logging.error(f"Failed to get table stats: {e}")
            return {}

    async def optimize_tables(self) -> bool:
        """Optimize database tables."""
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for table in ['users', 'groups', 'participants']:
                        await cur.execute(f"OPTIMIZE TABLE {table}")
                    logging.info("Database tables optimized")
                    return True
                    
        except Exception as e:
            logging.error(f"Failed to optimize tables: {e}")
            return False

    async def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return status info."""
        status = {
            'connected': False,
            'version': None,
            'character_set': None,
            'error': None
        }
        
        try:
            if not self.pool:
                await self.connect()
                
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Check version
                    await cur.execute("SELECT VERSION()")
                    status['version'] = (await cur.fetchone())[0]
                    
                    # Check character set
                    await cur.execute("SHOW VARIABLES LIKE 'character_set_database'")
                    status['character_set'] = (await cur.fetchone())[1]
                    
                    status['connected'] = True
                    logging.info(f"Database connected successfully. Version: {status['version']}")
                    
        except Exception as e:
            status['error'] = str(e)
            logging.error(f"Connection test failed: {e}")
            
        return status

    async def is_connected(self) -> bool:
        """Check if database is connected."""
        if not self.pool:
            return False
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    return True
        except:
            return False

    # Додайте інші методи, які можуть бути необхідні для вашого додатку
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for table in ['users', 'groups', 'participants']:
                        await cur.execute(f"OPTIMIZE TABLE {table}")
                    logging.info("Database tables optimized")
                    return True
                    
        except Exception as e:
            logging.error(f"Failed to optimize tables: {e}")
            return False

    # Додайте інші методи, які можуть бути необхідні для вашого додатку