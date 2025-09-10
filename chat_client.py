import asyncio
from asyncio import StreamReader, StreamWriter


LOG_FILE = "chat_history.log"


async def chat_client(host: str, port: int):
    reader: StreamReader
    writer: StreamWriter
    reader, writer = await asyncio.open_connection(host, port)
    
    print(f"Подключились к чату {host}:{port}")
    
    with open(LOG_FILE, 'a', encoding='utf-8') as log_file:
        try:
            while True:
                data = await reader.readline()
                
                if not data:
                    break
                
                message = data.decode().strip()
                
                print(message)
                
                log_file.write(message + '\n')
                log_file.flush()
                
        except Exception as e:
            print(f"Произошла ошибка: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            print("Соединение закрыто")


async def main():
    host = 'minechat.dvmn.org'
    port = 5000
    
    try:
        await chat_client(host, port)
    except KeyboardInterrupt:
        print("\nВыход по запросу пользователя")
    except Exception as e:
        print(f"Не удалось подключиться: {e}")


if __name__ == '__main__':
    asyncio.run(main())