"""Telegram UI and callback routing for Movie Finder Pro."""
import asyncio
from html import escape
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from database.models import (Favorite, SearchHistory, User, WatchedMovie, Watchlist,
                             add_search, toggle_movie)
from keyboards.main_menu import back_menu, main_menu
from services.movie_api import MovieApi, MovieApiError
from services.recommendation import recommendation_filters
from utils.formatting import get_docs, movie_caption, movie_title

logger = logging.getLogger(__name__)
LISTS = {"favorite": (Favorite, "избранном", "❤️"),
         "watched": (WatchedMovie, "просмотренных", "👀"),
         "watchlist": (Watchlist, "списке «Хочу посмотреть»", "📌")}


def api(context: ContextTypes.DEFAULT_TYPE) -> MovieApi:
    return context.application.bot_data["movie_api"]


def ensure_user(update: Update) -> User:
    tg = update.effective_user
    return User.ensure(tg.id, tg.username, tg.first_name)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensure_user(update)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🎬 <b>Movie Finder Pro</b>\nНайдём фильм, сохраним подборки и поможем выбрать, что посмотреть.",
        parse_mode=ParseMode.HTML, reply_markup=main_menu())


async def show_home(query) -> None:
    await safe_edit(query, "🎬 <b>Movie Finder Pro</b>\nВыберите раздел:",
                    main_menu(), ParseMode.HTML)


async def safe_edit(query, text: str, markup=None, parse_mode=None) -> None:
    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode=parse_mode,
                                      disable_web_page_preview=True)
    except BadRequest as exc:
        message = str(exc).lower()
        if "message is not modified" in message:
            return
        if "there is no text in the message to edit" in message:
            await query.edit_message_caption(caption=text, reply_markup=markup,
                                            parse_mode=parse_mode)
            return
        raise


def result_keyboard(items: list[dict], page_mode: str | None = None,
                    has_prev: bool = False, has_next: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for item in items[:8]:
        mid = item.get("id")
        if mid is not None:
            title = movie_title(item)
            rows.append([InlineKeyboardButton(f"🎬 {title[:52]}", callback_data=f"movie:{mid}")])
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data="page:prev"))
    if has_next:
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data="page:next"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("⌂ Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(rows)


async def display_results(query, data: dict, context, title: str,
                          mode: str, state: dict[str, Any]) -> None:
    state["mode"] = mode
    items = get_docs(data)
    state["items"] = {str(x.get("id")): x for x in items if x.get("id") is not None}
    context.user_data["results"] = state
    if not items:
        await safe_edit(query, f"По запросу «{title}» ничего не найдено.", back_menu())
        return
    text = f"<b>{title}</b>\nНайдено: {len(items)}. Выберите фильм:"
    has_prev = bool(data.get("hasPrev")) or (mode == "title" and state.get("page", 1) > 1)
    has_next = (state.get("page", 1) < state.get("pages", data.get("pages", 1))) if mode == "title" else bool(data.get("hasNext"))
    await safe_edit(query, text, result_keyboard(items, mode, has_prev, has_next), ParseMode.HTML)


async def ask_text(query, context, mode: str, prompt: str) -> None:
    context.user_data["awaiting"] = mode
    await safe_edit(query, prompt, back_menu())


async def open_movie(query, context, movie: dict) -> None:
    mid = str(movie.get("id", ""))
    if not mid:
        await safe_edit(query, "Не удалось открыть фильм: в данных нет ID.", back_menu())
        return
    cached = context.user_data.get("movie_cache", {}).get(mid)
    if cached:
        movie = cached
    else:
        try:
            detailed = await asyncio.to_thread(api(context).get_movie, mid)
            movie = detailed
        except MovieApiError as exc:
            logger.info("Movie detail lookup failed for id=%s: %s", mid, exc)
    context.user_data.setdefault("movie_cache", {})[mid] = movie
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ Избранное", callback_data=f"favorite:{mid}"),
         InlineKeyboardButton("👀 Просмотрен", callback_data=f"watched:{mid}")],
        [InlineKeyboardButton("📌 Хочу посмотреть", callback_data=f"watchlist:{mid}")],
        [InlineKeyboardButton("➡️ Следующий фильм", callback_data="page:next"),
         InlineKeyboardButton("🔙 Назад", callback_data="back")],
        [InlineKeyboardButton("⌂ Главное меню", callback_data="home")],
    ])
    caption = movie_caption(movie)
    poster = movie.get("poster")
    poster_url = poster.get("url") if isinstance(poster, dict) else None
    try:
        if poster_url:
            await query.edit_message_media(InputMediaPhoto(poster_url, caption=caption,
                                                           parse_mode=ParseMode.HTML),
                                           reply_markup=markup)
        else:
            await safe_edit(query, caption, markup, ParseMode.HTML)
    except BadRequest:
        # A search result is usually a text message; replace it with a poster card when available.
        try:
            await query.message.delete()
        except TelegramError:
            pass
        if poster_url:
            try:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=poster_url,
                                             caption=caption, parse_mode=ParseMode.HTML,
                                             reply_markup=markup)
            except TelegramError:
                await context.bot.send_message(chat_id=query.message.chat_id, text=caption,
                                               parse_mode=ParseMode.HTML, reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=caption,
                                           parse_mode=ParseMode.HTML, reply_markup=markup)


async def show_list(query, user: User, kind: str) -> None:
    model, label, emoji = LISTS[kind]
    entries = list(model.select().where(model.user == user).order_by(model.created_at.desc()).limit(30))
    if not entries:
        await safe_edit(query, f"{emoji} В разделе «{label}» пока пусто.", back_menu())
        return
    rows = [[InlineKeyboardButton(f"🎬 {entry.title[:52]}", callback_data=f"movie:{entry.movie_id}")]
            for entry in entries]
    rows.append([InlineKeyboardButton("⌂ Главное меню", callback_data="home")])
    await safe_edit(query, f"{emoji} <b>Ваш список ({len(entries)})</b>\nНажмите на фильм, чтобы открыть карточку.",
                    InlineKeyboardMarkup(rows), ParseMode.HTML)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action_callback = (query.data or "").startswith(("favorite:", "watched:", "watchlist:"))
    if not action_callback:
        await query.answer()
    user = ensure_user(update)
    data = (query.data or "")[:64]
    if data in {"search", "budget_low", "budget_high", "rating", "year", "genres",
                "history", "random", "recommendations"}:
        context.user_data.pop("last_list", None)
    try:
        if data == "home":
            context.user_data.clear()
            await show_home(query)
        elif data == "back":
            if context.user_data.get("awaiting"):
                context.user_data.clear()
                await show_home(query)
            elif context.user_data.get("last_list") in LISTS:
                await show_list(query, user, context.user_data["last_list"])
            else:
                state = context.user_data.get("results")
                if state and state.get("items"):
                    items = list(state["items"].values())
                    title = f"Поиск: {state.get('query')}" if state.get("mode") == "title" else "Результаты поиска"
                    await safe_edit(query, f"<b>{title}</b>\nВыберите фильм:",
                                    result_keyboard(items, state.get("mode"),
                                                    bool(state.get("prev")) or state.get("page", 1) > 1,
                                                    bool(state.get("next")) or (state.get("mode") == "title" and state.get("page", 1) < state.get("pages", 1))),
                                    ParseMode.HTML)
                else:
                    await show_home(query)
        elif data == "search":
            context.user_data.pop("last_list", None)
            await ask_text(query, context, "title", "🔎 Напишите название фильма или сериала:")
        elif data in {"budget_low", "budget_high"}:
            context.user_data["budget_kind"] = data
            await ask_text(query, context, "budget", "Введите максимальный бюджет числом:" if data == "budget_low" else "Введите минимальный бюджет числом:")
        elif data == "rating":
            await ask_text(query, context, "rating", "Введите минимальный рейтинг от 1 до 10 (например, 7.5):")
        elif data == "year":
            await ask_text(query, context, "year", "Введите год выпуска, например 2020:")
        elif data == "genres":
            genres = await asyncio.to_thread(api(context).genres)
            items = genres.get("items", genres.get("docs", genres.get("genres", [])))
            if isinstance(items, dict):
                items = items.get("docs", [])
            buttons = []
            for item in items[:30] if isinstance(items, list) else []:
                name = item.get("name") if isinstance(item, dict) else str(item)
                if name:
                    buttons.append([InlineKeyboardButton(str(name)[:50], callback_data=f"genre:{str(name)[:45]}")])
            buttons += [[InlineKeyboardButton("⌂ Главное меню", callback_data="home")]]
            await safe_edit(query, "🎭 Выберите жанр из справочника PoiskKino:", InlineKeyboardMarkup(buttons))
        elif data.startswith("genre:"):
            genre = data[6:]
            filters_ = {"genres.name": genre, "limit": 8}
            result = await asyncio.to_thread(api(context).search_filter, filters_)
            await display_results(query, result, context, f"Жанр: {genre}", "filter",
                                  {"filters": filters_, "next": result.get("next"), "prev": result.get("prev"), "page": 1})
        elif data == "history":
            entries = list(SearchHistory.select().where(SearchHistory.user == user).order_by(SearchHistory.searched_at.desc()).limit(15))
            if not entries:
                await safe_edit(query, "🕘 История пока пуста.", back_menu())
            else:
                rows = [[InlineKeyboardButton(f"🔎 {e.query[:52]}", callback_data=f"repeat:{e.id}")] for e in entries]
                rows.append([InlineKeyboardButton("⌂ Главное меню", callback_data="home")])
                await safe_edit(query, "🕘 <b>Ваши последние запросы</b>", InlineKeyboardMarkup(rows), ParseMode.HTML)
        elif data.startswith("repeat:"):
            entry = SearchHistory.get_or_none((SearchHistory.id == int(data[7:])) & (SearchHistory.user == user))
            if entry:
                add_search(user, entry.query)
                result = await asyncio.to_thread(api(context).search_title, entry.query, 1, 8)
                await display_results(query, result, context, f"Поиск: {entry.query}", "title",
                                      {"query": entry.query, "page": 1, "pages": result.get("pages", 1)})
            else:
                await safe_edit(query, "Этот запрос уже недоступен.", back_menu())
        elif data in {"list_favorite", "list_watched", "list_watchlist"}:
            context.user_data["last_list"] = data[5:]
            await show_list(query, user, data[5:])
        elif data.startswith("movie:"):
            mid = data[6:]
            if not mid.isdigit():
                await safe_edit(query, "Некорректный идентификатор фильма.", back_menu())
                return
            movie = context.user_data.get("results", {}).get("items", {}).get(mid)
            if movie is None:
                movie = context.user_data.get("movie_cache", {}).get(mid, {"id": mid})
            await open_movie(query, context, movie)
        elif data.startswith(("favorite:", "watched:", "watchlist:")):
            kind, mid = data.split(":", 1)
            movie = context.user_data.get("movie_cache", {}).get(mid)
            if not movie:
                movie = await asyncio.to_thread(api(context).get_movie, mid)
                context.user_data.setdefault("movie_cache", {})[mid] = movie
            present = toggle_movie(LISTS[kind][0], user, movie)
            label = {"favorite": "избранное", "watched": "просмотренные", "watchlist": "список «Хочу посмотреть»"}[kind]
            await query.answer(("Добавлено в " if present else "Удалено из ") + label)
            await open_movie(query, context, movie)
        elif data.startswith("page:"):
            direction = data[5:]
            if direction not in {"next", "prev"}:
                await safe_edit(query, "Эта страница недоступна.", back_menu())
            else:
                await change_page(query, context, direction)
        elif data == "random":
            context.user_data.pop("results", None)
            context.user_data.pop("last_list", None)
            movie = await asyncio.to_thread(api(context).random_movie, {"notNullFields": "id"})
            await open_movie(query, context, movie)
        elif data == "recommendations":
            filters_, message = recommendation_filters(user)
            result = await asyncio.to_thread(api(context).search_filter, filters_)
            if not result.get("docs") and "genres.name" in filters_:
                filters_, message = recommendation_filters_without_history()
                result = await asyncio.to_thread(api(context).search_filter, filters_)
            await display_results(query, result, context, f"💡 {message}", "filter",
                                  {"filters": filters_, "next": result.get("next"), "prev": result.get("prev"), "page": 1})
        elif data == "help":
            await safe_edit(query, "ℹ️ Отправьте название для поиска. Рейтинг, год и бюджет задаются числом. Карточки можно сохранять в личные списки; они привязаны к вашему Telegram ID.", back_menu())
        else:
            await safe_edit(query, "Кнопка устарела. Откройте главное меню.", back_menu())
    except (MovieApiError, ValueError) as exc:
        logger.info("Handled callback error: %s", exc)
        await safe_edit(query, f"⚠️ {str(exc)}", back_menu())
    except TelegramError as exc:
        logger.warning("Telegram callback failed: %s", exc)


def recommendation_filters_without_history() -> tuple[dict, str]:
    return ({"rating.kp": "7-10", "votes.kp": "1000-999999999",
             "sortField": "rating.kp", "sortType": "-1", "limit": 8,
             "notNullFields": "id"}, "Подборка высоко оценённых фильмов по рейтингу и числу голосов API")


async def change_page(query, context, direction: str) -> None:
    state = context.user_data.get("results")
    if not state:
        movie = await asyncio.to_thread(api(context).random_movie, {"notNullFields": "id"})
        await open_movie(query, context, movie)
        return
    if state.get("mode") == "title":
        page = max(1, state.get("page", 1) + (1 if direction == "next" else -1))
        result = await asyncio.to_thread(api(context).search_title, state["query"], page, 8)
        new_state = {"mode": "title", "query": state["query"], "page": page,
                     "pages": result.get("pages", state.get("pages", page))}
        await display_results(query, result, context, f"Поиск: {state['query']} · страница {page}", "title", new_state)
    else:
        token = state.get(direction)
        if not token:
            await safe_edit(query, "Других страниц нет.", back_menu())
            return
        filters_ = dict(state["filters"])
        filters_["next" if direction == "next" else "prev"] = token
        result = await asyncio.to_thread(api(context).search_filter, filters_)
        new_state = {"mode": "filter", "filters": state["filters"],
                     "next": result.get("next"), "prev": result.get("prev"),
                     "page": state.get("page", 1) + (1 if direction == "next" else -1)}
        await display_results(query, result, context, "Результаты фильтра", "filter", new_state)


async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.user_data.pop("awaiting", None)
    if not mode:
        return
    user = ensure_user(update)
    raw = (update.effective_message.text or "").strip()
    if not raw:
        await update.effective_message.reply_text("Введите непустое значение.", reply_markup=back_menu())
        return
    try:
        if mode == "title":
            query_text = raw[:100]
            add_search(user, query_text)
            data = await asyncio.to_thread(api(context).search_title, query_text, 1, 8)
            items = get_docs(data)
            if not items:
                await update.effective_message.reply_text(f"По запросу «{query_text}» ничего не найдено.", reply_markup=back_menu())
                return
            await update.effective_message.reply_text(
                f"<b>Поиск: {escape(query_text)}</b>", parse_mode=ParseMode.HTML,
                reply_markup=result_keyboard(items, "title", False, data.get("page", 1) < data.get("pages", 1)))
            context.user_data["results"] = {"mode": "title", "query": query_text, "page": 1,
                                              "pages": data.get("pages", 1),
                                              "items": {str(x.get("id")): x for x in items if x.get("id") is not None}}
        elif mode == "budget":
            amount = int(raw.replace(" ", ""))
            if amount < 0 or amount > 10**15:
                raise ValueError("Сумма должна быть от 0 до 10^15.")
            key = "budget_kind"
            filters_ = {"budget.value": f"0-{amount}" if context.user_data.pop(key, "budget_low") == "budget_low" else f"{amount}-999999999999999", "limit": 8}
            data = await asyncio.to_thread(api(context).search_filter, filters_)
            items = get_docs(data)
            if not items:
                await update.effective_message.reply_text("Фильмы с таким бюджетом не найдены.", reply_markup=back_menu())
                return
            await update.effective_message.reply_text("🎞️ Тайтлы по бюджету:", reply_markup=result_keyboard(items, "filter", False, bool(data.get("hasNext"))))
            context.user_data["results"] = {"mode": "filter", "filters": filters_, "next": data.get("next"), "prev": data.get("prev"), "page": 1,
                                              "items": {str(x.get("id")): x for x in get_docs(data) if x.get("id") is not None}}
        elif mode == "rating":
            rating = float(raw.replace(",", "."))
            if not 1 <= rating <= 10:
                raise ValueError("Рейтинг должен быть от 1 до 10.")
            filters_ = {"rating.kp": f"{rating}-10", "limit": 8}
            await show_text_filter(update, context, filters_, f"⭐ Рейтинг от {rating:g}")
        elif mode == "year":
            if not raw.isdigit() or not 1870 <= int(raw) <= 2100:
                raise ValueError("Укажите год от 1870 до 2100.")
            filters_ = {"year": raw, "limit": 8}
            await show_text_filter(update, context, filters_, f"📅 Год: {raw}")
    except (MovieApiError, ValueError) as exc:
        logger.info("User input rejected: %s", exc)
        await update.effective_message.reply_text(f"⚠️ {exc}", reply_markup=back_menu())


async def show_text_filter(update, context, filters_: dict, heading: str) -> None:
    data = await asyncio.to_thread(api(context).search_filter, filters_)
    items = get_docs(data)
    if not items:
        await update.effective_message.reply_text(f"По фильтру «{heading}» ничего не найдено.", reply_markup=back_menu())
        return
    context.user_data["results"] = {"mode": "filter", "filters": filters_, "next": data.get("next"),
                                     "prev": data.get("prev"), "page": 1,
                                     "items": {str(x.get("id")): x for x in items if x.get("id") is not None}}
    await update.effective_message.reply_text(heading, reply_markup=result_keyboard(items, "filter", False, bool(data.get("hasNext"))))


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))
