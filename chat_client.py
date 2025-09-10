import asyncio
import aiofiles
import datetime
from asyncio import StreamReader, StreamWriter


HOST = 'minechat.dvmn.org'
PORT = 5000
LOG_FILE = "chat_history.log"


async def log_message(message: str, log_file: str = LOG_FILE):
    """Асинхронно записывает сообщение в файл с временной меткой"""
    timestamp = datetime.datetime.now().strftime("[%d.%m.%y %H:%M]")
    log_entry = f"{timestamp} {message}\n"
    
    async with aiofiles.open(log_file, mode='a', encoding='utf-8') as f:
        await f.write(log_entry)
        await f.flush()


async def chat_client(host: str, port: int):
    """Основная функция клиента чата"""
    reconnect_delay = 1
    
    while True:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            print(f"Подключились к чату {host}:{port}")
            await log_message("Установлено соединение")
            
            reconnect_delay = 1
            
            while True:
                data = await reader.readline()
                
                if not data:
                    break
                
                message = data.decode().strip()
                
                if message:
                    print(message)
                    await log_message(message)
                    
        except (ConnectionError, asyncio.TimeoutError) as e:
            error_msg = f"Ошибка соединения: {e}. Переподключение через {reconnect_delay} сек..."
            print(error_msg)
            await log_message(f"Разрыв соединения: {e}")
            await asyncio.sleep(reconnect_delay)

            reconnect_delay = min(reconnect_delay * 2, 60)
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e}"
            print(error_msg)
            await log_message(error_msg)
            await asyncio.sleep(5)
            
        finally:
            if 'writer' in locals():
                writer.close()
                await writer.wait_closed()


async def main():
    """Главная функция"""
    print(f"Запуск мониторинга чата {HOST}:{PORT}")
    print(f"История сохраняется в файл: {LOG_FILE}")
    print("Для остановки нажмите Ctrl+C\n")
    
    try:
        await chat_client(HOST, PORT)
    except KeyboardInterrupt:
        print("\nМониторинг остановлен по запросу пользователя")
        await log_message("Мониторинг остановлен")


if __name__ == '__main__':
    asyncio.run(main())