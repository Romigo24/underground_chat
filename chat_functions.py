import asyncio
import json
import logging
from asyncio import StreamWriter, StreamReader
from typing import Dict


logger = logging.getLogger('chat_functions')


class InvalidToken(Exception):
    pass


async def authorise(reader: StreamReader, writer: StreamWriter, account_hash: str) -> Dict:
    try:
        await reader.readline()
        writer.write((account_hash + '\n').encode())
        await writer.drain()
        account_data = await reader.readline()
        account_info = json.loads(account_data.decode().strip())

        if account_info is None:
            raise InvalidToken('Неизвестный токен. Проверьте его или зарегистрируйте заново.')

        if 'nickname' in account_info:
            account_info['nickname'] = account_info['nickname'].replace('\\\\', '\\')
            account_info['nickname'] = account_info['nickname'].encode('utf-8').decode('unicode_escape')

        logger.info(f"Успешная авторизация: {account_info['nickname']}")
        return account_info

    except json.JSONDecodeError as e:
        logger.error(f'Ошибка парсинга JSON: {e}')
        raise
    except Exception as e:
        logger.error(f'Ошибка при авторизации: {e}')
        raise


async def open_connection(host: str, port: int):
    reader, writer = await asyncio.open_connection(host, port)
    return reader, writer


def reconnect(max_retries=10, initial_delay=1, max_delay=60):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retry_count = 0
            delay = initial_delay
            while retry_count < max_retries:
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, socket.gaierror, OSError, asyncio.TimeoutError) as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"❌ Превышено максимальное количество попыток переподключения: {max_retries}")
                        raise
                    logger.warning(f"🔄 Попытка переподключения {retry_count}/{max_retries} через {delay}с: {e}")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, max_delay)
                except Exception as e:
                    logger.error(f"❌ Неожиданная ошибка: {e}")
                    raise
        return wrapper
    return decorator