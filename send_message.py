import asyncio
import argparse
import os
import logging
from dotenv import load_dotenv

from chat_functions import open_connection, close_connection, authorise, submit_message


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('sender')


load_dotenv()


async def main():
    parser = argparse.ArgumentParser(description='Отправка сообщений в MineChat')

    default_host = os.environ['CHAT_HOST']
    default_port = os.environ['MESSAGE_CHAT_PORT']
    default_hash = os.environ.get('CHAT_HASH')

    if default_hash is None and os.path.exists('chat_account.hash'):
        try:
            with open('chat_account.hash', 'r', encoding='utf-8') as f:
                default_hash = f.read().strip()
        except Exception as e:
            logger.debug(f'Не удалось прочитать файл с токеном: {e}')

    parser.add_argument('--host', '-H', default=default_host, help='Адрес сервера чата')
    parser.add_argument('--port', '-p', type=int, default=int(default_port), help='Порт сервера чата')
    parser.add_argument('--hash', '-a', default=default_hash, help='Хеш аккаунта')
    parser.add_argument('--message', '-m', required=True, help='Сообщение для отправки')

    args = parser.parse_args()

    if not args.hash:
        print('❌ Требуется хеш аккаунта. Используйте --hash или создайте нового пользователя:')
        print('python3 registration.py')
        return

    logger.info(f'Отправка сообщения на {args.host}:{args.port}...')

    reader, writer = None, None
    try:
        reader, writer = await open_connection(args.host, args.port)

        account_info = await authorise(reader, writer, args.hash)
        logger.info(f"✅ Авторизован как: {account_info['nickname']}")

        await submit_message(reader, writer, args.message)
        logger.info('✅ Сообщение отправлено!')

    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения: {e}')
    finally:
        if writer:
            await close_connection(writer)


if __name__ == '__main__':
    asyncio.run(main())