import telebot
import random
import requests
import os
from telebot import types 

# Токен для доступа к Telegram API. 
# API_TOKEN = os.environ.get("TELEGRAM_API_TOKEN") 
API_TOKEN = "8578142479:AAEg0MB_vuBy3vLXCqLgaJ_5qiG7nKLIWdk"
# API Lichess, чтобы брать одну и ту же задачу раз в сутки
DAILY_PUZZLE_API = "https://lichess.org/api/puzzle/daily"

bot = telebot.TeleBot(API_TOKEN)
# Храним активную задачу каждого чата
user_puzzles = {} 
# Храним статистику (решено/провалено)
user_stats = {} 

# Наш запасной список тестовых задач (на случай, если Lichess не отвечает)
# Важно: для простой логики оставляем только один ход в решении!
TEST_PUZZLES = [
    {
        "fen": "r1bqkb1r/pp2pppp/2n5/3n4/3P4/5N2/PP2BPPP/RNBQ1RK1 b kq - 1 8", 
        "solution": ["c8f5"] 
    },
    {
        "fen": "8/8/8/8/8/5P2/PP2P1P1/4K3 b - - 0 1", 
        "solution": ["f7f6"]
    },
    {
        "fen": "4rrk1/pppq2pp/3b4/3p1b2/3P4/2P2B2/PP1N1PPP/R2QR1K1 w - - 0 16", 
        "solution": ["d1b3"]
    }
]

#  Общая функция для отправки задачи (чтобы не повторять код в /daily и /puzzle) 
def _send_new_puzzle(chat_id, fen, solution, is_daily):
    """Сохраняет состояние задачи и отправляет ее пользователю"""
    
    # Для проверки нам нужен только первый ход из решения
    next_move = solution[0].lower()
    user_puzzles[chat_id] = {
        "fen": fen,
        "solution": solution,
        "next_move": next_move # Храним ожидаемый ход
    }
    
    # Готовим кнопки
    keyboard = types.InlineKeyboardMarkup()
    hint_btn = types.InlineKeyboardButton("💡 Подсказка", callback_data="hint")
    solve_btn = types.InlineKeyboardButton("🚩 Показать решение", callback_data="solve")
    keyboard.add(hint_btn, solve_btn)
    
    # Кнопка "Новая задача" нужна только, если это не ежедневный пазл (там она нелогична)
    if not is_daily:
        new_btn = types.InlineKeyboardButton("⏭️ Новая задача", callback_data="new_puzzle")
        keyboard.add(new_btn)
        
    title = "Ежедневная задача Lichess" if is_daily else "Случайная Задача"
    
    bot.send_message(
        chat_id, 
        f"**♟️ {title}!**\n\n**FEN:** `{fen}`\n\nТвой ход?",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я шахматный бот. Напиши /puzzle чтобы получить случайную задачу, /daily для ежедневной, или /stats для просмотра своей статистики.")

# КОМАНДА: /daily (Берем с Lichess, или выдаем резервную)
@bot.message_handler(commands=['daily'])
def send_daily_puzzle(message):
    chat_id = message.chat.id
    fen = None
    solution = None
    is_daily = False 
    
    try:
        # Попытка получить задачу с Lichess
        response = requests.get(DAILY_PUZZLE_API)
        
        if response.status_code == 200:
            data = response.json()
            
            # Проверяем, что все данные на месте (FEN, решение и т.д.)
            if ("puzzle" in data and "fen" in data["puzzle"] and 
                "solution" in data["puzzle"] and len(data["puzzle"]["solution"]) > 0):
                
                fen = data["puzzle"]["fen"]
                solution = data["puzzle"]["solution"]
                is_daily = True
            else:
                raise ValueError("Lichess вернул неполные данные.")
        else:
            raise ConnectionError(f"Lichess API вернул ошибку: {response.status_code}")
            
    except (requests.exceptions.RequestException, ValueError, ConnectionError) as e:
        # --- РЕЗЕРВ (FALLBACK) ---
        # Если Lichess не ответил, выдаем задачу из нашего списка
        bot.send_message(chat_id, "⚠️ **Внимание:** Не смогли взять ежедневную задачу Lichess. Даю случайную из запасного набора.", parse_mode='Markdown')
        
        # Берем случайную задачу из локального списка
        puzzle_data = random.choice(TEST_PUZZLES)
        fen = puzzle_data["fen"]
        solution = puzzle_data["solution"]
    
    # Отправляем задачу, используя нашу общую функцию
    _send_new_puzzle(chat_id, fen, solution, is_daily)

# КОМАНДА: /stats 
@bot.message_handler(commands=['stats'])
def send_stats(message):
    chat_id = message.chat.id
    stats = user_stats.get(chat_id)
    
    if not stats:
        bot.send_message(chat_id, "Статистики пока нет. Начни решать с /puzzle!")
        return
        
    solved = stats.get("solved", 0)
    failed = stats.get("failed", 0)
    total = solved + failed
    
    success_rate = (solved / total) * 100 if total > 0 else 0
    
    response_text = (
        f"📊 **Твоя статистика**\n\n"
        f"🏆 Решено задач: **{solved}**\n"
        f"💀 Провалено задач: **{failed}**\n"
        f"📈 Общий процент успеха: **{success_rate:.2f}%**\n\n"
        f"Продолжай тренироваться с /puzzle!"
    )
    
    bot.send_message(chat_id, response_text, parse_mode='Markdown')


# КОМАНДА: /puzzle (Просто случайная задача из нашего списка)
@bot.message_handler(commands=['puzzle'])
def send_puzzle(message):
    chat_id = message.chat.id
    
    try:
        # Выбираем задачу
        puzzle_data = random.choice(TEST_PUZZLES)
        fen = puzzle_data["fen"]
        solution = puzzle_data["solution"]
        
        # Отправляем задачу, is_daily ставим False
        _send_new_puzzle(chat_id, fen, solution, False)
            
    except Exception as e:
        bot.reply_to(message, f"Что-то пошло не так при получении задачи: {e}")


# ОБРАБОТЧИК ТЕКСТА (Проверяем ход пользователя)
@bot.message_handler(func=lambda message: message.text and message.chat.id in user_puzzles)
def check_move(message):
    chat_id = message.chat.id
    # Приводим ход пользователя к нижнему регистру, чтобы сравнивать
    user_move = message.text.strip().lower() 
    
    current_puzzle = user_puzzles.get(chat_id)
    if not current_puzzle:
        return 
    
    expected_move = current_puzzle["next_move"] # Ожидаем только первый ход
    
    if user_move == expected_move:
        # Верно! Считаем задачу решенной
        stats = user_stats.setdefault(chat_id, {"solved": 0, "failed": 0})
        stats["solved"] += 1
        
        # Удаляем задачу, чтобы она не проверялась дальше
        del user_puzzles[chat_id] 
        bot.send_message(chat_id, "✅ **Верно!** Задача решена. Поздравляю!\n\n/puzzle чтобы получить новую.", parse_mode='Markdown')
        
    else:
        # Неправильно. Просим попробовать еще раз
        bot.send_message(chat_id, f"❌ **Неправильный ход.** Попробуй еще раз или нажми на 'Подсказку'.")


# ОБРАБОТЧИК КНОПОК (Подсказка, Решение, Новая задача)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    puzzle_data = user_puzzles.get(chat_id)
    
    # Убираем "часики" после нажатия
    bot.answer_callback_query(call.id) 

    if call.data == "new_puzzle" or call.data == "solve":
        # Если пользователь пропустил или попросил решение, считаем это провалом
        if puzzle_data:
            stats = user_stats.setdefault(chat_id, {"solved": 0, "failed": 0})
            stats["failed"] += 1
            del user_puzzles[chat_id] # Удаляем, чтобы не было активной задачи
            
            if call.data == "new_puzzle":
                bot.send_message(chat_id, "Задача пропущена. Приступаем к следующей...")
                # Вызываем отправку новой задачи
                send_puzzle(call.message) 
                return
            elif call.data == "solve":
                # Показываем полное решение
                solution_str = " -> ".join(puzzle_data["solution"])
                bot.send_message(
                    chat_id, 
                    f"🚩 **Решение:** \n\nПолная последовательность ходов: `{solution_str}`",
                    parse_mode='Markdown'
                )
                bot.send_message(chat_id, "Теперь ты знаешь решение. Напиши /puzzle, чтобы начать новую задачу.")
                return


    if not puzzle_data:
        # Срабатывает, если нажали кнопку после того, как задача уже была решена/пропущена
        bot.send_message(chat_id, "⚠️ У тебя нет активной задачи. Напиши /puzzle, чтобы начать.")
        return
        
    elif call.data == "hint":
        # Даем подсказку по первым двум символам хода
        hint = puzzle_data["next_move"]
        bot.send_message(chat_id, f"💡 **Подсказка:** Правильный ход начинается с `{hint[0:2]}`. Введи полный ход.", parse_mode='Markdown')
        
# Запускаем бота. Он будет постоянно слушать Telegram

bot.polling(none_stop=True)
