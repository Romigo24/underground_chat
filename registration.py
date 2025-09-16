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
        logging.FileHandler('register_user.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('register')


load_dotenv()


async def register_user(host, port, nickname, save_to_file):
    """Регистрирует нового пользователя и возвращает токен"""
    reader: StreamReader = None
    writer: StreamWriter = None

    try:
        logger.debug(f"Подключение к {host}:{port} для регистрации")
        reader, writer = await asyncio.open_connection(host, port)
        logger.debug("Соединение установлено")

        welcome_msg = await reader.readline()
        welcome_text = welcome_msg.decode().strip()
        logger.debug(f"Получено: {welcome_text}")
        print(welcome_text)

        writer.write(b'\n')
        await writer.drain()
        logger.debug("Отправлена пустая строка для создания аккаунта")
        print("Запрос нового аккаунта...")

        nickname_prompt = await reader.readline()
        nickname_text = nickname_prompt.decode().strip()
        logger.debug(f"Получено: {nickname_text}")
        print(nickname_text)

        if nickname is None:
            import random
            adjectives = ["Happy", "Clever", "Brave", "Kind", "Wise", "Funny", "Gentle", "Honest"]
            nouns = ["Cat", "Dog", "Fox", "Bear", "Eagle", "Lion", "Tiger", "Wolf"]
            nickname = f"{random.choice(adjectives)} {random.choice(nouns)}"

        writer.write((nickname + '\n').encode())
        await writer.drain()
        logger.debug(f"Отправлен никнейм: {nickname}")
        print(f"Отправлен никнейм: {nickname}")

        account_data = await reader.readline()
        account_text = account_data.decode().strip()
        logger.debug(f"Получены данные аккаунта: {account_text}")

        account_info = json.loads(account_text)

        if account_info is None:
            error_msg = "Ошибка при регистрации: сервер вернул null"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(f"Зарегистрирован новый аккаунт: {account_info['nickname']}")
        print(f"✅ Зарегистрирован новый пользователь: {account_info['nickname']}")
        print(f"🔑 Токен: {account_info['account_hash']}")

        welcome_chat = await reader.readline()
        welcome_chat_text = welcome_chat.decode().strip()
        logger.debug(f"Получено: {welcome_chat_text}")

        writer.close()
        await writer.wait_closed()
        logger.debug("Соединение закрыто")

        if save_to_file:
            with open('chat_account.hash', 'w', encoding='utf-8') as f:
                f.write(account_info['account_hash'])
            logger.info(f"Токен сохранен в файл: chat_account.hash")
            print(f"💾 Токен сохранен в файл: chat_account.hash")

        return account_info

    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        logger.error(f"Полученные данные: {account_text if 'account_text' in locals() else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при регистрации: {e}")
        raise
    finally:
        if writer and not writer.is_closing():
            writer.close()
            await writer.wait_closed()


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Регистрация нового пользователя в MineChat',
        epilog='Примеры использования:\n'
               '  python3 register_user.py\n'
               '  python3 register_user.py --nickname "My Cool Nickname"\n'
               '  python3 register_user.py --host minechat.dvmn.org --port 5050\n'
               '  python3 register_user.py --no-save'
    )

    default_host = os.environ['CHAT_HOST']
    default_port = os.environ['MESSAGE_CHAT_PORT']

    parser.add_argument('--host', '-H',
                       default=default_host,
                       help='Адрес сервера чата')

    parser.add_argument('--port', '-p',
                       type=int,
                       default=int(default_port),
                       help='Порт сервера чата')

    parser.add_argument('--nickname', '-n',
                       help='Желаемый никнейм (если не указан - будет сгенерирован случайный)')

    parser.add_argument('--no-save', '-x',
                       action='store_false',
                       dest='save_to_file',
                       help='Не сохранять токен в файл')

    parser.add_argument('--log-level', '-l',
                       default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Уровень логирования')

    return parser.parse_args()


async def main():
    args = parse_args()

    logger.setLevel(args.log_level.upper())

    logger.info(f"Запуск регистрации пользователя на {args.host}:{args.port}")
    print(f"Регистрация нового пользователя на {args.host}:{args.port}...")
    print()

    try:
        account_info = await register_user(
            args.host, 
            args.port, 
            args.nickname,
            args.save_to_file
        )

        print()
        print("🎉 Регистрация завершена успешно!")
        print(f"👤 Никнейм: {account_info['nickname']}")
        print(f"🔑 Токен: {account_info['account_hash']}")

        if args.save_to_file:
            print()
            print("Теперь вы можете отправлять сообщения используя сохраненный токен:")
            print("python3 send_message.py --message \"Ваше сообщение\"")

    except KeyboardInterrupt:
        logger.warning("Регистрация отменена пользователем")
        print("\n❌ Регистрация отменена")
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
        print(f"\n❌ Ошибка при регистрации: {e}")


if __name__ == '__main__':
    asyncio.run(main())