from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MAIN_BUTTONS = [
    ("🔎 Найти фильм", "search"), ("⭐ Поиск по рейтингу", "rating"),
    ("💰 Низкий бюджет", "budget_low"), ("💎 Высокий бюджет", "budget_high"),
    ("🎭 Жанры", "genres"), ("📅 По году", "year"),
    ("❤️ Избранное", "list_favorite"),
    ("👀 Просмотренные", "list_watched"), ("📌 Хочу посмотреть", "list_watchlist"),
    ("🕘 История поиска", "history"), ("🎲 Случайный фильм", "random"),
    ("💡 Рекомендации", "recommendations"), ("ℹ️ Помощь", "help"),
]


def main_menu() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text, callback_data=data)
             for text, data in MAIN_BUTTONS[i:i + 2]]
            for i in range(0, len(MAIN_BUTTONS), 2)]
    return InlineKeyboardMarkup(rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⌂ Главное меню", callback_data="home")]])
