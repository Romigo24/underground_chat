import asyncio
import argparse
import os
import json
import logging
from dotenv import load_dotenv
from asyncio import StreamWriter, StreamReader


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('send_message.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('sender')


load_dotenv()


async def send_message(host, port, account_hash, message):
    """Подключается к серверу, аутентифицируется и отправляет сообщение"""
    reader: StreamReader = None
    writer: StreamWriter = None

    try:
        logger.debug(f"Подключение к {host}:{port}")
        reader, writer = await asyncio.open_connection(host, port)
        logger.debug("Соединение установлено")

        welcome_msg = await reader.readline()
        welcome_text = welcome_msg.decode().strip()
        logger.debug(f"Получено: {welcome_text}")
        print(welcome_text)

        if account_hash:
            writer.write((account_hash + '\n').encode())
            await writer.drain()
            logger.debug(f"Отправлен хеш: {account_hash}")
            print(f"Отправлен хеш: {account_hash}")
        else:
            writer.write(b'\n')
            await writer.drain()
            logger.debug("Запрос нового аккаунта (пустая строка)")
            print("Запрос нового аккаунта...")

        account_data = await reader.readline()
        account_text = account_data.decode().strip()
        logger.debug(f"Получены данные аккаунта: {account_text}")

        account_info = json.loads(account_text)

        if account_info is None:
            error_msg = "Неизвестный токен. Проверьте его или зарегистрируйте заново."
            logger.error(error_msg)
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)

        logger.info(f"Аккаунт: {account_info['nickname']} (хеш: {account_info['account_hash']})")
        print(f"Аккаунт: {account_info['nickname']} (хеш: {account_info['account_hash']})")

        welcome_chat = await reader.readline()
        welcome_chat_text = welcome_chat.decode().strip()
        logger.debug(f"Получено: {welcome_chat_text}")
        print(welcome_chat_text)

        if message:
            writer.write((message + '\n\n').encode())
            await writer.drain()
            logger.debug(f"Отправлено сообщение: {message}")
            print(f"Отправлено сообщение: {message}")

        writer.close()
        await writer.wait_closed()
        logger.debug("Соединение закрыто")

        return account_info

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        logger.error(f"Полученные данные: {account_text if 'account_text' in locals() else 'N/A'}")
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        raise
    finally:
        if writer and not writer.is_closing():
            writer.close()
            await writer.wait_closed()


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Отправка сообщений в MineChat с аутентификацией',
        epilog='Примеры использования:\n'
               '  python3 send_message.py --message "Привет всем!"\n'
               '  python3 send_message.py --hash bbe0d4a6-8e85-11f0-a5a4-0242ac110003 --message "Сообщение"'
    )

    default_host = os.environ['CHAT_HOST']
    default_port = os.environ['MESSAGE_CHAT_PORT']
    default_hash = os.environ['CHAT_HASH']

    parser.add_argument('--host', '-H',
                       default=default_host,
                       help='Адрес сервера чата')

    parser.add_argument('--port', '-p',
                       type=int,
                       default=int(default_port),
                       help='Порт сервера чата')

    parser.add_argument('--hash', '-a',
                       default=default_hash,
                       help='Хеш аккаунта для аутентификации (если не указан - создается новый)')

    parser.add_argument('--message', '-m',
                       help='Сообщение для отправки в чат')

    parser.add_argument('--save-hash', '-s',
                       action='store_true',
                       help='Сохранить хеш аккаунта в файл')

    parser.add_argument('--log-level', '-l',
                       default='DEBUG',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Уровень логирования')

    return parser.parse_args()


async def main():
    """Главная функция"""
    args = parse_args()

    logger.setLevel(args.log_level.upper())

    logger.info(f"Запуск отправки сообщения на {args.host}:{args.port}")
    print(f"Подключение к чату {args.host}:{args.port}...")

    try:
        account_info = await send_message(
            args.host, 
            args.port, 
            args.hash, 
            args.message
        )

        if args.save_hash and not args.hash:
            with open('chat_account.hash', 'w', encoding='utf-8') as f:
                f.write(account_info['account_hash'])
            logger.info(f"Хеш сохранен в файл: chat_account.hash")
            print(f"Хеш сохранен в файл: chat_account.hash")

        logger.info(f"Успешно завершено. Ник: {account_info['nickname']}")
        print(f"\n✅ Успешно! Ваш ник: {account_info['nickname']}")

    except ValueError as e:
        logger.error(f"Ошибка аутентификации: {e}")
        print(f"\n❌ {e}")
        print("Попробуйте создать новый аккаунт без указания хеша:")
        print("python3 send_message.py --message \"Ваше сообщение\"")
    except KeyboardInterrupt:
        logger.warning("Отменено пользователем")
        print("\n❌ Отменено пользователем")
    except Exception as e:
        logger.error(f"Ошибка выполнения: {e}")
        print(f"\n❌ Ошибка: {e}")


if __name__ == '__main__':
    asyncio.run(main())