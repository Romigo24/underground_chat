import asyncio
import argparse
import os
import logging
from dotenv import load_dotenv

from chat_functions import open_connection, close_connection, register


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('register')


load_dotenv()


async def main():
    parser = argparse.ArgumentParser(description='Регистрация нового пользователя в MineChat')
    default_host = os.environ['CHAT_HOST']
    default_port = os.environ['MESSAGE_CHAT_PORT']

    parser.add_argument('--host', '-H', default=default_host, help='Адрес сервера чата')
    parser.add_argument('--port', '-p', type=int, default=int(default_port), help='Порт сервера чата')
    parser.add_argument('--nickname', '-n', help='Желаемый никнейм')
    parser.add_argument('--no-save', '-x', action='store_false', dest='save_to_file', help='Не сохранять токен в файл')

    args = parser.parse_args()

    logger.info(f'Регистрация нового пользователя на {args.host}:{args.port}...')

    reader, writer = None, None
    try:
        reader, writer = await open_connection(args.host, args.port)

        account_info = await register(reader, writer, args.nickname)

        logger.info(f"✅ Зарегистрирован: {account_info['nickname']}")
        logger.info(f"🔑 Токен: {account_info['account_hash']}")

        if args.save_to_file:
            with open('chat_account.hash', 'w', encoding='utf-8') as f:
                f.write(account_info['account_hash'])
            logger.info('💾 Токен сохранен в chat_account.hash')

    except Exception as e:
        logger.error(f'❌ Ошибка: {e}')
    finally:
        if writer:
            await close_connection(writer)


if __name__ == '__main__':
    asyncio.run(main())