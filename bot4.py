import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import serial
import serial.tools.list_ports  # Додано для пошуку портів
import time
import pyautogui
import random

# --- ГЛОБАЛЬНІ ЗМІННІ СТАНУ БОТА ---
bot_running = False
arduino = None


# --- ФУНКЦІЇ ДЛЯ ЛОГІВ ---
def log(message):
    """Додає текст у вікно логів"""
    root.after(0, _append_log, message)


def _append_log(message):
    text_log.config(state=tk.NORMAL)
    text_log.insert(tk.END, message + "\n")
    text_log.see(tk.END)  # Автоскрол донизу
    text_log.config(state=tk.DISABLED)


# --- ФУНКЦІЯ ПОШУКУ ARDUINO LEONARDO ---
def find_leonardo_port():
    """Шукає COM-порт, до якого підключено саме Arduino Leonardo."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        description = port.description.upper()
        hwid = port.hwid.upper()

        # Шукаємо за назвою "LEONARDO" або за стандартними VID:PID плати
        if "LEONARDO" in description or "2341:8036" in hwid or "2341:0036" in hwid:
            return port.device

    return ""  # Якщо не знайдено


# --- ІНСТРУМЕНТ ЗАХОПЛЕННЯ КООРДИНАТ І КОЛЬОРУ ---
def start_grabber():
    btn_grab.config(state=tk.DISABLED)
    log("\n Наведи курсор на червону смужку ХП моба!")
    countdown(3)


def countdown(sec):
    if sec > 0:
        log(f"Захоплення через {sec}...")
        root.after(1000, countdown, sec - 1)
    else:
        try:
            x, y = pyautogui.position()
            r, g, b = pyautogui.pixel(x, y)

            # Оновлюємо поля вводу
            entry_x.delete(0, tk.END)
            entry_x.insert(0, str(x))
            entry_y.delete(0, tk.END)
            entry_y.insert(0, str(y))
            entry_r.delete(0, tk.END)
            entry_r.insert(0, str(r))
            entry_g.delete(0, tk.END)
            entry_g.insert(0, str(g))
            entry_b.delete(0, tk.END)
            entry_b.insert(0, str(b))

            log(f"УСПІХ! Збережено: X={x}, Y={y}, Колір=({r}, {g}, {b})")
        except Exception as e:
            log(f"ПОМИЛКА захоплення: {e}")
        finally:
            btn_grab.config(state=tk.NORMAL)


# --- ЛОГІКА САМОГО БОТА ---
def is_mob_alive(base_x, base_y, target_color, tol):
    try:
        img = pyautogui.screenshot(region=(base_x, base_y, 11, 1))
        matches = 0

        # Використовуємо круглі дужки (кортеж), щоб чат не "з'їв" код
        points_to_check = (0, 5, 10)

        for px in points_to_check:
            pixel_color = img.getpixel((px, 0))

            # Розпаковуємо кольори у змінні R, G, B без квадратних дужок
            pr, pg, pb = pixel_color
            tr, tg, tb = target_color

            # Правильне математичне порівняння кольорів
            if abs(pr - tr) <= tol and abs(pg - tg) <= tol and abs(pb - tb) <= tol:
                matches += 1

        return matches >= 2
    except Exception:
        return False


def bot_loop():
    global bot_running, arduino

    # Зчитуємо налаштування з інтерфейсу
    try:
        com_port = entry_com.get()
        if not com_port or com_port == "Не знайдено":
            log("ПОМИЛКА: Вкажи правильний COM-порт!")
            bot_running = False
            root.after(0, lambda: btn_start.config(state=tk.NORMAL))
            return

        base_x = int(entry_x.get())
        base_y = int(entry_y.get())
        target_color = (int(entry_r.get()), int(entry_g.get()), int(entry_b.get()))
        tolerance = int(entry_tol.get())
        max_attack = int(entry_atk_time.get())
        max_search = int(entry_srch_time.get())
    except ValueError:
        log("ПОМИЛКА: Перевір правильність введених чисел!")
        bot_running = False
        root.after(0, lambda: btn_start.config(state=tk.NORMAL))
        return

    # Підключення до Arduino
    log(f"Підключаємось до {com_port}...")
    try:
        arduino = serial.Serial(com_port, 9600)
        time.sleep(2)
        log("Успішно! Arduino Leonardo підключено.")
    except Exception as e:
        log(f"ПОМИЛКА COM-порта: {e}")
        bot_running = False
        root.after(0, lambda: btn_start.config(state=tk.NORMAL))
        return

    log("БОТ ЗАПУЩЕНИЙ! Перемкнись на вікно з грою.")

    combat_start_time = None
    search_start_time = None
    was_in_combat = False

    try:
        while bot_running:
            if is_mob_alive(base_x, base_y, target_color, tolerance):
                # --- АТАКА ---
                was_in_combat = True
                search_start_time = None

                if combat_start_time is None:
                    combat_start_time = time.time()
                    log("Знайдено ціль! Атакуємо...")

                attack_duration = time.time() - combat_start_time

                if attack_duration > max_attack:
                    log(f"Б'ємо занадто довго ({int(attack_duration)}с). Скіпаємо (F3).")
                    arduino.write(b'3')
                    combat_start_time = None
                    time.sleep(random.uniform(0.2, 0.4))
                else:
                    arduino.write(b'1')  # Атака (F1+F2)
                    time.sleep(random.uniform(0.2, 0.4))
            else:
                # --- ПОШУК ---
                combat_start_time = None

                if was_in_combat:
                    log("Моб мертвий. Затримка реакції...")
                    time.sleep(random.uniform(0.2, 0.4))
                    was_in_combat = False
                    search_start_time = time.time()

                if search_start_time is None:
                    search_start_time = time.time()

                search_duration = time.time() - search_start_time

                if search_duration > max_search:
                    log(f"Немає мобів {int(search_duration)}с. Anti-Stuck (F4)!")
                    arduino.write(b'4')
                    search_start_time = time.time()
                    time.sleep(random.uniform(0.2, 0.4))
                else:
                    arduino.write(b'3')  # Next Target
                    time.sleep(random.uniform(0.2, 0.4))

    except Exception as e:
        log(f"КРИТИЧНА ПОМИЛКА: {e}")
    finally:
        if arduino and arduino.is_open:
            arduino.close()
        log("БОТ ЗУПИНЕНИЙ. Порт закрито.")

        # Повертаємо кнопки в початковий стан (безпечно з іншого потоку)
        root.after(0, lambda: btn_start.config(state=tk.NORMAL))
        root.after(0, lambda: btn_stop.config(state=tk.DISABLED))


# --- КЕРУВАННЯ ПОТОКОМ БОТА ---
def start_bot():
    global bot_running
    if not bot_running:
        bot_running = True
        btn_start.config(state=tk.DISABLED)
        btn_stop.config(state=tk.NORMAL)

        text_log.config(state=tk.NORMAL)
        text_log.delete(1.0, tk.END)  # Очищаємо лог перед стартом
        text_log.config(state=tk.DISABLED)

        # Запускаємо бота в окремому потоці, щоб не висло вікно
        threading.Thread(target=bot_loop, daemon=True).start()


def stop_bot():
    global bot_running
    log("\nЗупинка бота... (чекаємо завершення циклу)")
    bot_running = False


# ==========================================
# ============ ІНТЕРФЕЙС (GUI) =============
# ==========================================
root = tk.Tk()
root.title("L2 Arduino AutoFarm")
root.geometry("450x650")
root.resizable(False, False)

# --- Рамка налаштувань ---
frame_settings = tk.LabelFrame(root, text="Налаштування", padx=10, pady=10)
frame_settings.pack(padx=10, pady=10, fill="x")

# COM Port
tk.Label(frame_settings, text="COM Порт:").grid(row=0, column=0, sticky="e", pady=2)
entry_com = tk.Entry(frame_settings, width=15)

# Автоматичне визначення порту Leonardo при запуску
leonardo_port = find_leonardo_port()
if leonardo_port:
    entry_com.insert(0, leonardo_port)
else:
    entry_com.insert(0, "Не знайдено")

entry_com.grid(row=0, column=1, sticky="w", pady=2)

# Піпетка (Кнопка для координат)
btn_grab = tk.Button(frame_settings, text="Отримати координати ХП", bg="lightblue", command=start_grabber)
btn_grab.grid(row=1, column=0, columnspan=2, pady=10, sticky="we")

# X, Y
tk.Label(frame_settings, text="Координата X:").grid(row=2, column=0, sticky="e", pady=2)
entry_x = tk.Entry(frame_settings, width=10)
entry_x.insert(0, "1200")
entry_x.grid(row=2, column=1, sticky="w", pady=2)

tk.Label(frame_settings, text="Координата Y:").grid(row=3, column=0, sticky="e", pady=2)
entry_y = tk.Entry(frame_settings, width=10)
entry_y.insert(0, "84")
entry_y.grid(row=3, column=1, sticky="w", pady=2)

# RGB Колір
frame_rgb = tk.Frame(frame_settings)
frame_rgb.grid(row=4, column=0, columnspan=2, pady=5)
tk.Label(frame_rgb, text="Колір (R, G, B):").pack(side=tk.LEFT)
entry_r = tk.Entry(frame_rgb, width=4)
entry_r.insert(0, "128")
entry_r.pack(side=tk.LEFT, padx=2)
entry_g = tk.Entry(frame_rgb, width=4)
entry_g.insert(0, "26")
entry_g.pack(side=tk.LEFT, padx=2)
entry_b = tk.Entry(frame_rgb, width=4)
entry_b.insert(0, "22")
entry_b.pack(side=tk.LEFT, padx=2)

# Tolerance та Таймаути
tk.Label(frame_settings, text="Похибка кольору:").grid(row=5, column=0, sticky="e", pady=2)
entry_tol = tk.Entry(frame_settings, width=10)
entry_tol.insert(0, "25")
entry_tol.grid(row=5, column=1, sticky="w", pady=2)

tk.Label(frame_settings, text="Час атаки (сек):").grid(row=6, column=0, sticky="e", pady=2)
entry_atk_time = tk.Entry(frame_settings, width=10)
entry_atk_time.insert(0, "10")
entry_atk_time.grid(row=6, column=1, sticky="w", pady=2)

tk.Label(frame_settings, text="Час пошуку (сек):").grid(row=7, column=0, sticky="e", pady=2)
entry_srch_time = tk.Entry(frame_settings, width=10)
entry_srch_time.insert(0, "5")
entry_srch_time.grid(row=7, column=1, sticky="w", pady=2)

# --- Рамка керування ---
frame_controls = tk.Frame(root)
frame_controls.pack(pady=5)

btn_start = tk.Button(frame_controls, text="ЗАПУСТИТИ БОТА", font=("Arial", 12, "bold"), bg="#90EE90", width=15,
                      command=start_bot)
btn_start.pack(side=tk.LEFT, padx=10)

btn_stop = tk.Button(frame_controls, text="ЗУПИНИТИ", font=("Arial", 12, "bold"), bg="#FFB6C1", width=15,
                     state=tk.DISABLED, command=stop_bot)
btn_stop.pack(side=tk.LEFT, padx=10)

# --- Рамка логів ---
tk.Label(root, text="Логи роботи:").pack(anchor="w", padx=10)
text_log = scrolledtext.ScrolledText(root, height=12, state=tk.DISABLED, bg="#F0F0F0")
text_log.pack(padx=10, pady=5, fill="both", expand=True)

# Перевірка для виведення в лог після завантаження інтерфейсу
if leonardo_port:
    log(f"Знайдено Arduino Leonardo на порту: {leonardo_port}")
else:
    log("УВАГА: Arduino Leonardo не знайдено. Перевірте кабель або введіть порт вручну.")
log("Інтерфейс завантажено. Вкажи порт і натисни Старт.")

# Запуск вікна
root.mainloop()