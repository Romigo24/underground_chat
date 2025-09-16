import asyncio
import aiofiles
import datetime
import argparse
import os
import logging
from dotenv import load_dotenv
from asyncio import StreamReader, StreamWriter


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('chat_client')


load_dotenv()


async def log_message(message, log_file):
    timestamp = datetime.datetime.now().strftime("[%d.%m.%y %H:%M]")
    log_entry = f"{timestamp} {message}\n"
    
    async with aiofiles.open(log_file, mode='a', encoding='utf-8') as f:
        await f.write(log_entry)
        await f.flush()


async def chat_client(host, port, history_file):
    reconnect_delay = 1
    
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            logger.info(f'Подключились к чату {host}:{port}')
            await log_message('Установлено соединение', history_file)
            
            reconnect_delay = 1
            
            while True:
                data = await reader.readline()
                
                if not data:
                    break
                
                message = data.decode().strip()
                
                if message:
                    print(message)
                    await log_message(message, history_file)
                    
        except (ConnectionError, asyncio.TimeoutError) as e:
            error_msg = f'Ошибка соединения: {e}. Переподключение через {reconnect_delay} сек...'
            logger.warning(error_msg)
            await log_message(f'Разрыв соединения: {e}', history_file)
            await asyncio.sleep(reconnect_delay)

            reconnect_delay = min(reconnect_delay * 2, 60)
            
        except Exception as e:
            error_msg = f'Неожиданная ошибка: {e}'
            logger.error(error_msg)
            await log_message(error_msg, history_file)
            await asyncio.sleep(5)
            
        finally:
            if 'writer' in locals():
                writer.close()
                await writer.wait_closed()


def parse_args():
    parser = argparse.ArgumentParser(
        description='Клиент для мониторинга и сохранения переписки из чата',
        epilog='Примеры использования:\n'
               '  python3 chat_client.py\n'
               '  python3 chat_client.py --host 192.168.0.1 --port 5001 --history chat.log\n'
               '  CHAT_HOST=192.168.0.1 CHAT_PORT=5001 python3 chat_client.py\n'
               '\nПеременные окружения: CHAT_HOST, CHAT_PORT, CHAT_HISTORY'
    )

    default_host = os.environ['CHAT_HOST']
    default_port = os.environ['CHAT_PORT']
    default_history = os.environ['CHAT_HISTORY']

    parser.add_argument('--host', '-H',
                       default=default_host,
                       help='Адрес сервера чата')

    parser.add_argument('--port', '-p',
                       type=int,
                       default=int(default_port),
                       help='Порт сервера чата')

    parser.add_argument('--history', '-f',
                       default=default_history,
                       help='Путь к файлу для сохранения истории')

    return parser.parse_args()


async def main():
    args = parse_args()

    logger.info('Chat Logger запущен')
    logger.info(f'Сервер: {args.host}:{args.port}')
    logger.info(f'Файл истории: {args.history}')
    logger.info('Для остановки нажмите Ctrl+C\n')
    
    try:
        await chat_client(args.host, args.port, args.history)
    except KeyboardInterrupt:
        logger.info('Мониторинг остановлен по запросу пользователя')
        await log_message('Мониторинг остановлен', args.history)


if __name__ == '__main__':
    asyncio.run(main())