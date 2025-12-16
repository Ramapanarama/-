import telebot
import random
import requests
from telebot import types
from urllib.parse import quote  # нужно для корректного кодирования FEN

API_TOKEN = "8578142479:AAEg0MB_vuBy3vLXCqLgaJ_5qiG7nKLIWdk"
DAILY_PUZZLE_API = "https://lichess.org/api/puzzle/daily"

bot = telebot.TeleBot(API_TOKEN)

user_puzzles = {}
user_stats = {}

TEST_PUZZLES = [
    {
        "fen": "r1bqkb1r/pp2pppp/2n5/3n4/3P4/5N2/PP2BPPP/RNBQ1RK1 b kq - 1 8",
        "solution": ["c8f5"],
        "rating": 1500
    },
    {
        "fen": "8/8/8/8/8/5P2/PP2E1P1/4K3 b - - 0 1",
        "solution": ["f7f6"],
        "rating": 1200
    },
    {
        "fen": "4rrk1/pppq2pp/3b4/3p1b2/3P4/2P2B2/PP1N1PPP/R2QR1K1 w - - 0 16",
        "solution": ["d1b3"],
        "rating": 1800
    }
]


def get_chessboard_image(fen):
    """Получаем изображение доски с chess.com API"""
    try:
        # Кодируем FEN для URL
        board_fen = fen.split(' ')[0]
        encoded_fen = quote(board_fen)
        
        # Chess.com URL для генерации доски
        chesscom_url = f"https://www.chess.com/dynboard?fen={encoded_fen}&board=blue&piece=neo&size=2"
        
        # Делаем запрос
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(chesscom_url, headers=headers, timeout=10)
        
        if response.status_code == 200 and response.content:
            return response.content
            
    except Exception as e:
        print(f"Ошибка при получении изображения: {e}")
    
    return None


def _send_new_puzzle(chat_id, fen, solution, is_daily, rating=None):
    """Сохраняем задачу и отправляем её с картинкой доски"""
    
    next_move = solution[0].lower()
    user_puzzles[chat_id] = {
        "fen": fen,
        "solution": solution,
        "next_move": next_move,
        "is_daily": is_daily
    }

    # Кнопки
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    hint_btn = types.InlineKeyboardButton("💡 Подсказка", callback_data="hint")
    solve_btn = types.InlineKeyboardButton("🚩 Решение", callback_data="solve")
    new_btn = types.InlineKeyboardButton("🆕 Новая", callback_data="new_puzzle")
    keyboard.add(hint_btn, solve_btn, new_btn)

    # Название задачи
    title = "🎯 Ежедневная задача Lichess" if is_daily else "♟️ Случайная задача"
    
    # Определяем, чей ход
    if 'w' in fen:
        move_color = "⚪ Белые"
        turn_text = "Ваш ход (белые)"
    else:
        move_color = "⚫ Чёрные" 
        turn_text = "Ваш ход (чёрные)"
    
    rating_text = f"📊 Рейтинг: {rating}" if rating else ""
    
    caption = f"{title}\n\n{turn_text}\n{rating_text}\n\nВведите ход в формате: **e2e4**"

    try:
        # Получаем изображение доски
        board_image = get_chessboard_image(fen)
        
        if board_image:
            # Отправляем изображение
            bot.send_photo(
                chat_id,
                board_image,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
        else:
            # Если не удалось получить изображение, отправляем FEN
            raise Exception("Не удалось загрузить изображение доски")
            
    except Exception as e:
        print(f"Ошибка при отправке изображения: {e}")
        
        # Запасной вариант: отправляем текстовое сообщение с FEN
        message_text = (
            f"{title}\n\n"
            f"{turn_text}\n{rating_text}\n\n"
            f"Позиция в формате FEN:\n`{fen}`\n\n"
            f"Введите ход в формате: **e2e4**\n\n"
            f"*Не удалось загрузить изображение доски*"
        )
        
        bot.send_message(
            chat_id,
            message_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )


@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Создаем кнопки для главного меню
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    puzzle_btn = types.KeyboardButton("🎲 Случайная задача")
    daily_btn = types.KeyboardButton("📅 Ежедневная")
    stats_btn = types.KeyboardButton("📊 Статистика")
    keyboard.add(puzzle_btn, daily_btn, stats_btn)
    
    bot.send_message(
        message.chat.id,
        "♟️ Привет! Я шахматный бот-тренер.\n\n"
        "Выбери действие:\n"
        "🎲 Случайная задача - тренировка\n"
        "📅 Ежедневная - задача дня от Lichess\n"
        "📊 Статистика - твои результаты\n\n"
        "Или используй команды:\n"
        "/puzzle - случайная задача\n"
        "/daily - ежедневная задача\n"
        "/stats - статистика",
        reply_markup=keyboard
    )


@bot.message_handler(commands=['daily'])
def send_daily_puzzle(message):
    chat_id = message.chat.id
    fen = None
    solution = None
    rating = None
    is_daily = False

    try:
        response = requests.get(DAILY_PUZZLE_API, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if ("puzzle" in data and "fen" in data["puzzle"] and
                    "solution" in data["puzzle"] and len(data["puzzle"]["solution"]) > 0):

                fen = data["puzzle"]["fen"]
                solution = data["puzzle"]["solution"]
                rating = data["puzzle"].get("rating", 1500)
                is_daily = True
            else:
                raise ValueError("Lichess вернул неполные данные.")
        else:
            raise ConnectionError(f"Lichess API вернул ошибку: {response.status_code}")

    except Exception as e:
        print(f"Ошибка при получении ежедневной задачи: {e}")
        puzzle_data = random.choice(TEST_PUZZLES)
        fen = puzzle_data["fen"]
        solution = puzzle_data["solution"]
        rating = puzzle_data.get("rating", 1500)
        is_daily = False
        
        bot.send_message(
            chat_id,
            f"⚠️ Не смогли взять ежедневную задачу Lichess. Даю случайную из набора.",
            parse_mode='Markdown'
        )

    _send_new_puzzle(chat_id, fen, solution, is_daily, rating)


@bot.message_handler(commands=['stats'])
def send_stats(message):
    chat_id = message.chat.id
    stats = user_stats.get(chat_id)

    if not stats:
        bot.send_message(chat_id, "📭 Статистики пока нет. Начни решать с /puzzle!")
        return

    solved = stats.get("solved", 0)
    failed = stats.get("failed", 0)
    total = solved + failed

    success_rate = (solved / total) * 100 if total > 0 else 0
    
    # Определяем уровень игрока
    if total == 0:
        level = "👶 Новичок"
    elif success_rate >= 80:
        level = "🎯 Эксперт"
    elif success_rate >= 60:
        level = "⭐ Продвинутый"
    elif success_rate >= 40:
        level = "📚 Ученик"
    else:
        level = "🎓 Начинающий"

    response_text = (
        f"📊 Твоя статистика\n\n"
        f"{level}\n\n"
        f"✅ Решено: {solved}\n"
        f"❌ Провалено: {failed}\n"
        f"📈 Успех: {success_rate:.1f}%\n\n"
        f"Продолжай тренироваться!"
    )

    bot.send_message(chat_id, response_text)


@bot.message_handler(commands=['puzzle'])
def send_puzzle(message):
    chat_id = message.chat.id

    try:
        puzzle_data = random.choice(TEST_PUZZLES)
        fen = puzzle_data["fen"]
        solution = puzzle_data["solution"]
        rating = puzzle_data.get("rating", 1500)
        _send_new_puzzle(chat_id, fen, solution, False, rating)
    except Exception as e:
        bot.reply_to(message, f"Что-то пошло не так при получении задачи: {e}")


@bot.message_handler(func=lambda message: message.chat.id in user_puzzles)
def check_move(message):
    """Обрабатываем ходы пользователя"""
    chat_id = message.chat.id
    user_move = message.text.strip().lower().replace(" ", "")

    current_puzzle = user_puzzles.get(chat_id)
    if not current_puzzle:
        return

    expected_move = current_puzzle["next_move"]

    print(f"Пользователь ввел: {user_move}, ожидалось: {expected_move}")  # Для отладки

    if user_move == expected_move:
        # Правильный ход
        stats = user_stats.setdefault(chat_id, {"solved": 0, "failed": 0})
        stats["solved"] += 1

        solution_str = " -> ".join(current_puzzle["solution"])
        
        # Удаляем задачу
        del user_puzzles[chat_id]
        
        # Отправляем поздравление
        bot.send_message(
            chat_id,
            f"✅ Отлично! Правильный ход!\n\n"
            f"Полное решение: {solution_str}\n\n"
            f"Нажми /puzzle для новой задачи или используй кнопку '🆕 Новая'."
        )
    else:
        # Неправильный ход
        bot.send_message(
            chat_id,
            f"❌ Неправильно. Ожидался ход: {expected_move}\n"
            f"Попробуй еще раз или нажми '💡 Подсказка'."
        )


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработка всех остальных сообщений"""
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Обработка кнопок главного меню
    if text == "🎲 Случайная задача":
        send_puzzle(message)
    elif text == "📅 Ежедневная":
        send_daily_puzzle(message)
    elif text == "📊 Статистика":
        send_stats(message)
    else:
        # Если не команда и не активная задача
        if chat_id not in user_puzzles:
            bot.send_message(
                chat_id,
                "Используй кнопки меню или команды:\n"
                "/puzzle - случайная задача\n"
                "/daily - ежедневная задача\n"
                "/stats - статистика\n\n"
                "Или начни задачу и введи ход в формате e2e4"
            )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    puzzle_data = user_puzzles.get(chat_id)

    bot.answer_callback_query(call.id)

    if call.data == "new_puzzle":
        # Пользователь хочет новую задачу
        send_puzzle(call.message)
        return
        
    elif call.data == "solve":
        # Пользователь хочет увидеть решение
        if puzzle_data:
            stats = user_stats.setdefault(chat_id, {"solved": 0, "failed": 0})
            stats["failed"] += 1
            
            solution_str = " -> ".join(puzzle_data["solution"])
            bot.send_message(
                chat_id,
                f"🚩 Решение задачи:\n\n{solution_str}\n\n"
                f"Нажми /puzzle для новой задачи."
            )
            del user_puzzles[chat_id]
        else:
            bot.send_message(chat_id, "Нет активной задачи. Начни новую с /puzzle")
        return
    
    if not puzzle_data:
        bot.send_message(chat_id, "⚠️ Нет активной задачи. Начни новую с /puzzle")
        return

    elif call.data == "hint":
        # Подсказка
        hint = puzzle_data["next_move"]
        bot.send_message(
            chat_id,
            f"💡 Подсказка: правильный ход начинается с **{hint[0:2]}**\n\n"
            f"Введи полный ход (4 буквы, например: {hint})",
            parse_mode='Markdown'
        )


if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True, timeout=60)


