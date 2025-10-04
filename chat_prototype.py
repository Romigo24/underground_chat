import tkinter as tk
import asyncio
import aiofiles
import datetime
import os
import logging
import async_timeout
import socket
from dotenv import load_dotenv
import gui
from gui import NicknameReceived, ReadConnectionStateChanged, SendingConnectionStateChanged
from chat_functions import open_connection, authorise, reconnect, InvalidToken
import anyio


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('chat_prototype')
watchdog_logger = logging.getLogger('watchdog')


def load_account_hash():
    if os.path.exists('chat_account.hash'):
        with open('chat_account.hash', 'r', encoding='utf-8') as f:
            return f.read().strip()
    return os.environ.get('CHAT_HASH', '')


async def load_history(messages_queue, history_file):
    if not os.path.exists(history_file):
        return
    try:
        async with aiofiles.open(history_file, mode='r', encoding='utf-8') as f:
            content = await f.read()
            lines = content.strip().split('\n')
            for line in lines:
                if line.strip():
                    if '] ' in line:
                        message = line.split('] ', 1)[1]
                    else:
                        message = line
                    await messages_queue.put(message)
        logger.info(f"📖 Загружено {len(lines)} сообщений из истории")
    except Exception as e:
        logger.error(f"Ошибка загрузки истории: {e}")


async def save_messages(history_file, save_queue):
    logger.info(f"💾 Сохранение сообщений в файл: {history_file}")
    try:
        while True:
            message = await save_queue.get()
            timestamp = datetime.datetime.now().strftime("[%d.%m.%y %H:%M]")
            log_entry = f"{timestamp} {message}\n"
            async with aiofiles.open(history_file, mode='a', encoding='utf-8') as f:
                await f.write(log_entry)
                await f.flush()
            save_queue.task_done()
    except asyncio.CancelledError:
        logger.info("Задача сохранения сообщений остановлена")
    except Exception as e:
        logger.error(f"Ошибка сохранения сообщения: {e}")


async def watch_for_connection(watchdog_queue, timeout=15):
    watchdog_logger.info(f"🛡️ Watchdog запущен с таймаутом {timeout}с")
    while True:
        try:
            async with async_timeout.timeout(timeout) as cm:
                message = await watchdog_queue.get()
                timestamp = int(datetime.datetime.now().timestamp())
                if cm.expired:
                    watchdog_logger.warning(f"[{timestamp}] Позднее уведомление: {message}")
                else:
                    watchdog_logger.info(f"[{timestamp}] {message}")
                watchdog_queue.task_done()
        except asyncio.TimeoutError:
            if cm.expired:
                timestamp = int(datetime.datetime.now().timestamp())
                watchdog_logger.error(f"[{timestamp}] {timeout}s timeout exceeded - forcing connection close")
                raise ConnectionError(f"Сервер не отвечает {timeout} секунд")
        except Exception as e:
            watchdog_logger.error(f"Ошибка в watchdog: {e}")
            await asyncio.sleep(1)


async def ping_server(writer, watchdog_queue, ping_interval=10):
    logger.info(f"🏓 Ping task запущен с интервалом {ping_interval}с")
    while True:
        try:
            await asyncio.sleep(ping_interval)
            writer.write(b"\n\n")
            await writer.drain()
            await watchdog_queue.put("Connection is alive. Source: Ping sent")
        except (ConnectionError, BrokenPipeError, OSError) as e:
            logger.warning(f"Ошибка при отправке ping: {e}")
            await watchdog_queue.put(f"Ping error: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка в ping: {e}")
            await asyncio.sleep(1)


async def read_msgs(host, port, messages_queue, save_queue, status_updates_queue, watchdog_queue):
    await status_updates_queue.put(ReadConnectionStateChanged.INITIATED)
    logger.info("Устанавливаем соединение для чтения")
    try:
        reader, writer = await asyncio.open_connection(host, port)
        logger.info(f'✅ Подключились к чату {host}:{port}')
        await save_queue.put(f'Установлено соединение с {host}:{port}')
        await status_updates_queue.put(ReadConnectionStateChanged.ESTABLISHED)
        await watchdog_queue.put("Connection is alive. Source: Connection established for reading")

        while True:
            data = await reader.readline()
            if not data:
                await watchdog_queue.put("Connection closed by server")
                break
            message = data.decode().strip()
            if message:
                await messages_queue.put(message)
                await save_queue.put(message)
                await watchdog_queue.put("Connection is alive. Source: New message in chat")

    except Exception as e:
        error_msg = f'Ошибка чтения сообщений: {e}'
        logger.error(error_msg)
        await save_queue.put(error_msg)
        await status_updates_queue.put(ReadConnectionStateChanged.CLOSED)
        await watchdog_queue.put(f"Read error: {e}")
        raise
    finally:
        if 'writer' in locals():
            writer.close()
            await writer.wait_closed()


async def send_msgs_with_ping(host, port, account_hash, sending_queue, save_queue, status_updates_queue, watchdog_queue):
    logger.info(f"📤 Обработчик отправки с ping запущен для {host}:{port}")
    try:
        reader, writer = await asyncio.open_connection(host, port)
        logger.info(f'✅ Подключились для отправки сообщений к {host}:{port}')
        await save_queue.put(f'Установлено соединение для отправки с {host}:{port}')
        await status_updates_queue.put(SendingConnectionStateChanged.ESTABLISHED)
        await watchdog_queue.put("Connection is alive. Source: Connection established for sending")

        account_info = await authorise(reader, writer, account_hash)
        nickname = account_info['nickname']
        logger.info(f"🔐 Авторизованы как {nickname} для отправки")
        await watchdog_queue.put("Connection is alive. Source: Authorization done")

        async with anyio.create_task_group() as ping_group:
            ping_group.start_soon(ping_server, writer, watchdog_queue, 10)
            try:
                while True:
                    message = await sending_queue.get()
                    try:
                        writer.write(f"{message}\n\n".encode())
                        await writer.drain()
                        print(f"👤 Пользователь написал: {message}")
                        user_message = f"> {message}"
                        await save_queue.put(user_message)
                        logger.info(f"📤 Сообщение отправлено на сервер: '{message}'")
                        await watchdog_queue.put("Connection is alive. Source: Message sent")
                    except Exception as e:
                        error_msg = f"❌ Ошибка отправки сообщения: {e}"
                        logger.error(error_msg)
                        await save_queue.put(error_msg)
                        await watchdog_queue.put(f"Message sending error: {e}")
                        await sending_queue.put(message)
                        break
                    finally:
                        sending_queue.task_done()
            except Exception as e:
                logger.error(f"Ошибка в основной задаче отправки: {e}")
                raise

    except Exception as e:
        error_msg = f'Ошибка при отправке сообщений: {e}'
        logger.error(error_msg)
        await save_queue.put(error_msg)
        await status_updates_queue.put(SendingConnectionStateChanged.CLOSED)
        await watchdog_queue.put(f"Sending error: {e}")
        raise
    finally:
        if 'writer' in locals():
            writer.close()
            await writer.wait_closed()


@reconnect(max_retries=10, initial_delay=1, max_delay=60)
async def handle_connection(host, read_port, send_port, account_hash, messages_queue, sending_queue, 
                          save_queue, status_updates_queue, watchdog_queue):
    logger.info("🔄 Запускаем группу задач соединения")
    try:
        async with anyio.create_task_group() as connection_group:
            connection_group.start_soon(read_msgs, host, read_port, messages_queue, save_queue, status_updates_queue, watchdog_queue)
            connection_group.start_soon(send_msgs_with_ping, host, send_port, account_hash, sending_queue, save_queue, status_updates_queue, watchdog_queue)
            connection_group.start_soon(watch_for_connection, watchdog_queue, 15)
    except (ConnectionError, socket.gaierror, OSError, asyncio.TimeoutError) as e:
        logger.warning(f"🔌 Соединение разорвано: {e}")
        await save_queue.put(f"Соединение разорвано: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в handle_connection: {e}")
        await save_queue.put(f"Ошибка соединения: {e}")
        raise


async def handle_authorisation(host, port, account_hash, status_updates_queue, save_queue, watchdog_queue):
    try:
        logger.info("🔐 Выполняем авторизацию на сервере...")
        await status_updates_queue.put(SendingConnectionStateChanged.INITIATED)
        reader, writer = await open_connection(host, port)
        account_info = await authorise(reader, writer, account_hash)
        nickname = account_info['nickname']
        print(f"✅ Выполнена авторизация. Пользователь {nickname}.")
        await status_updates_queue.put(NicknameReceived(nickname))
        await status_updates_queue.put(SendingConnectionStateChanged.ESTABLISHED)
        await save_queue.put(f"Авторизованы как: {nickname}")
        await watchdog_queue.put("Connection is alive. Source: Authorization successful")
        logger.info(f"👤 Успешная авторизация: {nickname}")
        writer.close()
        await writer.wait_closed()
        return nickname
    except InvalidToken as e:
        await watchdog_queue.put("Authorization failed: Invalid token")
        raise
    except Exception as e:
        error_msg = f"❌ Ошибка авторизации: {e}"
        logger.error(error_msg)
        await save_queue.put(error_msg)
        await status_updates_queue.put(SendingConnectionStateChanged.CLOSED)
        await watchdog_queue.put(f"Authorization error: {e}")
        raise


async def start_chat():
    account_hash = load_account_hash()
    if not account_hash:
        print("❌ Токен не найден. Запустите registration.py для регистрации.")
        return

    host = os.environ.get('CHAT_HOST', 'minechat.dvmn.org')
    read_port = int(os.environ.get('LISTEN_CHAT_PORT', '5000'))
    send_port = int(os.environ.get('MESSAGE_CHAT_PORT', '5050'))
    history_file = os.environ.get('CHAT_HISTORY', 'chat_history.txt')

    print("🚀 Запуск графического чата...")

    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    save_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()

    await load_history(messages_queue, history_file)

    try:
        nickname = await handle_authorisation(host, send_port, account_hash, status_updates_queue, save_queue, watchdog_queue)
    except InvalidToken as e:
        print(f"❌ {e}")
        print("Пожалуйста, проверьте токен или зарегистрируйтесь заново.")
        try:
            root = tk.Tk()
            root.withdraw()
            gui.show_token_error()
            root.destroy()
        except Exception as gui_error:
            print(f"Не удалось показать GUI-уведомление: {gui_error}")
        return
    except Exception as e:
        print(f"❌ Не удалось запустить приложение: {e}")
        return

    try:
        async with anyio.create_task_group() as main_group:
            main_group.start_soon(gui.draw, messages_queue, sending_queue, status_updates_queue)
            main_group.start_soon(save_messages, history_file, save_queue)
            main_group.start_soon(handle_connection, host, read_port, send_port, account_hash,
                                messages_queue, sending_queue, save_queue, status_updates_queue, watchdog_queue)
    except (gui.TkAppClosed, KeyboardInterrupt):
        print("👋 Приложение завершено пользователем")
        await save_queue.put("Приложение закрыто пользователем")
    except Exception as e:
        if not isinstance(e, (ConnectionError, socket.gaierror, OSError, asyncio.TimeoutError)):
            error_msg = f"Произошла непредвиденная ошибка: {e}"
            print(error_msg)
            await save_queue.put(error_msg)
        else:
            print(f"🔌 Соединение прервано: {e}")
    finally:
        await save_queue.join()
        print("✅ Все задачи завершены")


def main():
    try:
        asyncio.run(start_chat())
    except KeyboardInterrupt:
        print("\n⏹️ Приложение завершено по команде пользователя")
    except Exception as e:
        if not isinstance(e, (ConnectionError, gui.TkAppClosed)):
            print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()