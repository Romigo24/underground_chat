import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import aiofiles
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import threading
import re

from chat_functions import open_connection


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('register')
load_dotenv()


async def register(reader, writer, nickname):
    await reader.readline()
    writer.write(b'\n')
    await writer.drain()
    await reader.readline()
    writer.write((nickname + '\n').encode())
    await writer.drain()
    account_data = await reader.readline()
    import json
    account_info = json.loads(account_data.decode().strip())
    return account_info


class RegistrationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Регистрация в чате Майнкрафтера")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        self.registration_in_progress = False
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.center_window()
        self.setup_ui()


    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')


    def on_closing(self):
        if self.registration_in_progress:
            if not messagebox.askokcancel("Выход", "Регистрация еще не завершена. Вы уверены, что хотите выйти?"):
                return
        self.root.destroy()


    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="🎮 Регистрация в чате Майнкрафтера", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        input_frame = ttk.LabelFrame(main_frame, text="Данные для регистрации", padding="15")
        input_frame.pack(fill=tk.X, pady=10)

        ttk.Label(input_frame, text="Выберите имя пользователя:", font=("Arial", 10)).pack(anchor=tk.W)
        self.nickname_var = tk.StringVar()
        nickname_entry = ttk.Entry(input_frame, textvariable=self.nickname_var, font=("Arial", 12), width=40)
        nickname_entry.pack(fill=tk.X, pady=(5, 10))
        nickname_entry.focus()

        self.register_button = ttk.Button(input_frame, text="🚀 Зарегистрироваться", command=self.start_registration)
        self.register_button.pack(pady=15)

        self.progress = ttk.Progressbar(input_frame, mode='indeterminate', length=500)
        self.progress.pack(fill=tk.X, pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="Журнал регистрации", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        nickname_entry.bind('<Return>', lambda e: self.start_registration())


    def log_message(self, message):
        try:
            self.log_text.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.root.update()
        except tk.TclError:
            pass


    def set_ui_state(self, enabled):
        try:
            state = tk.NORMAL if enabled else tk.DISABLED
            self.register_button.config(state=state)
            if enabled:
                self.progress.stop()
                self.registration_in_progress = False
            else:
                self.progress.start()
                self.registration_in_progress = True
        except tk.TclError:
            pass


    def validate_nickname(self, nickname):
        if not nickname:
            return "Имя пользователя не может быть пустым"
        if len(nickname) < 3:
            return "Имя должно содержать минимум 3 символа"
        if len(nickname) > 20:
            return "Имя не должно превышать 20 символов"
        if not re.match(r'^[a-zA-Zа-яА-Я0-9\s]+$', nickname):
            return "Имя может содержать только буквы, цифры и пробелы"
        return None


    def start_registration(self):
        nickname = self.nickname_var.get().strip()
        error = self.validate_nickname(nickname)
        if error:
            messagebox.showerror("Ошибка", error)
            return
        thread = threading.Thread(target=self.run_async_registration, args=(nickname,))
        thread.daemon = True
        thread.start()


    def run_async_registration(self, nickname):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.async_register_user(nickname))
        except Exception as e:
            self.log_message(f"✗ Ошибка при запуске регистрации: {e}")


    async def async_register_user(self, nickname):
        reader, writer = None, None
        try:
            self.root.after(0, self.set_ui_state, False)
            self.root.after(0, self.log_message, f"Начата регистрация для пользователя: {nickname}")

            host = os.environ.get('CHAT_HOST', 'minechat.dvmn.org')
            port = int(os.environ.get('MESSAGE_CHAT_PORT', '5050'))
            self.root.after(0, self.log_message, f"Подключаемся к серверу {host}:{port}...")

            reader, writer = await open_connection(host, port)
            self.root.after(0, self.log_message, "✓ Соединение установлено")
            self.root.after(0, self.log_message, "Отправляем запрос на регистрацию...")

            account_info = await register(reader, writer, nickname)
            token = account_info['account_hash']
            registered_nickname = account_info['nickname']

            self.root.after(0, self.log_message, "✓ Регистрация успешна!")
            self.root.after(0, self.log_message, f"👤 Имя пользователя: {registered_nickname}")
            self.root.after(0, self.log_message, f"🔑 Токен: {token[:10]}...{token[-10:]}")

            async with aiofiles.open('chat_account.hash', 'w', encoding='utf-8') as f:
                await f.write(token)
            self.root.after(0, self.log_message, "✓ Токен сохранен в файл 'chat_account.hash'")

            success_text = f"✅ Регистрация успешно завершена!\n\n👤 Имя пользователя: {registered_nickname}\n🔑 Токен сохранен в файл 'chat_account.hash'\n\nТеперь вы можете запустить чат-клиент и начать общение!"
            self.root.after(0, lambda: messagebox.showinfo("Регистрация завершена", success_text))

        except Exception as e:
            self.root.after(0, self.log_message, f"✗ Ошибка регистрации: {e}")
            self.root.after(0, lambda: messagebox.showerror("Ошибка регистрации", f"Не удалось завершить регистрацию:\n{e}"))
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
            self.root.after(0, self.set_ui_state, True)


def main():
    try:
        root = tk.Tk()
        app = RegistrationApp(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        messagebox.showerror("Критическая ошибка", f"Программа завершилась с ошибкой:\n{e}")


if __name__ == "__main__":
    main()