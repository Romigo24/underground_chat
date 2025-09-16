import asyncio
import json
import random
import logging
from asyncio import StreamWriter, StreamReader
from typing import Optional, Dict


logger = logging.getLogger('chat_functions')


def escape_control_chars(text: str) -> str:
    return text.encode('unicode_escape').decode('utf-8')


def unescape_control_chars(text: str) -> str:
    return text.encode('utf-8').decode('unicode_escape')


async def register(reader: StreamReader, writer: StreamWriter, nickname: Optional[str] = None) -> Dict:
    try:
        welcome_msg = await reader.readline()
        welcome_text = welcome_msg.decode().strip()
        logger.debug(f'Получено: {welcome_text}')

        writer.write(b'\n')
        await writer.drain()
        logger.debug('Отправлена пустая строка для регистрации')

        nickname_prompt = await reader.readline()
        nickname_text = nickname_prompt.decode().strip()
        logger.debug(f'Получено: {nickname_text}')

        if nickname is None:
            adjectives = ['Happy', 'Clever', 'Brave', 'Kind', 'Wise', 'Funny', 'Gentle', 'Honest']
            nouns = ['Cat', 'Dog', 'Fox', 'Bear', 'Eagle', 'Lion', 'Tiger', 'Wolf']
            nickname = f"{random.choice(adjectives)} {random.choice(nouns)}"

        escaped_nickname = escape_control_chars(nickname)
        writer.write((escaped_nickname + '\n').encode())
        await writer.drain()
        logger.debug(f'Отправлен никнейм: {nickname} (экранированный: {escaped_nickname})')

        account_data = await reader.readline()
        account_text = account_data.decode().strip()
        logger.debug(f'Получены данные аккаунта: {account_text}')

        account_info = json.loads(account_text)

        if account_info is None:
            raise ValueError("Ошибка регистрации: сервер вернул null")

        if 'nickname' in account_info:
            account_info['nickname'] = unescape_control_chars(account_info['nickname'])

        logger.info(f"Зарегистрирован новый аккаунт: {account_info['nickname']}")
        return account_info

    except json.JSONDecodeError as e:
        logger.error(f'Ошибка парсинга JSON: {e}')
        raise
    except Exception as e:
        logger.error(f'Ошибка при регистрации: {e}')
        raise


async def authorise(reader: StreamReader, writer: StreamWriter, account_hash: str) -> Dict:
    try:
        welcome_msg = await reader.readline()
        welcome_text = welcome_msg.decode().strip()
        logger.debug(f'Получено: {welcome_text}')

        writer.write((account_hash + '\n').encode())
        await writer.drain()
        logger.debug(f'Отправлен хеш: {account_hash}')

        account_data = await reader.readline()
        account_text = account_data.decode().strip()
        logger.debug(f'Получены данные аккаунта: {account_text}')

        account_info = json.loads(account_text)

        if account_info is None:
            raise ValueError('Неизвестный токен. Проверьте его или зарегистрируйте заново.')

        logger.info(f"Успешная авторизация: {account_info['nickname']}")
        return account_info

    except json.JSONDecodeError as e:
        logger.error(f'Ошибка парсинга JSON: {e}')
        raise
    except Exception as e:
        logger.error(f'Ошибка при авторизации: {e}')
        raise


async def submit_message(reader: StreamReader, writer: StreamWriter, message: str) -> None:
    try:
        welcome_chat = await reader.readline()
        welcome_chat_text = welcome_chat.decode().strip()
        logger.debug(f'Получено: {welcome_chat_text}')

        escaped_message = escape_control_chars(message)
        writer.write((escaped_message + '\n\n').encode())
        await writer.drain()
        logger.debug(f'Отправлено сообщение: {message} (экранированное: {escaped_message})')

    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения: {e}')
        raise


async def open_connection(host: str, port: int) -> (StreamReader, StreamWriter):
    logger.debug(f'Подключение к {host}:{port}')
    reader, writer = await asyncio.open_connection(host, port)
    logger.debug('Соединение установлено')
    return reader, writer


async def close_connection(writer: StreamWriter) -> None:
    if writer and not writer.is_closing():
        writer.close()
        await writer.wait_closed()
        logger.debug("Соединение закрыто")