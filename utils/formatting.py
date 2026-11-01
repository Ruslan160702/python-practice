from html import escape
from typing import Any


def _value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        amount = value.get("value")
        currency = value.get("currency")
        if amount is None:
            return None
        return f"{amount} {currency}".strip() if currency else str(amount)
    return str(value)


def _names(values: Any) -> str | None:
    if not isinstance(values, list):
        return _value(values)
    names = [str(x.get("name")) if isinstance(x, dict) and x.get("name") else str(x)
             for x in values if x]
    return ", ".join(names) or None


def movie_title(movie: dict) -> str:
    return str(movie.get("name") or movie.get("alternativeName") or movie.get("enName") or "Без названия")


def movie_caption(movie: dict) -> str:
    """Build compact HTML from fields actually present in the API response."""
    lines = [f"🎬 <b>{escape(movie_title(movie))}</b>"]
    original = movie.get("alternativeName") or movie.get("enName")
    if original and original != movie.get("name"):
        lines.append(f"🌐 Оригинальное название: <i>{escape(str(original))}</i>")
    fields = [
        ("Тип", _value(movie.get("type"))),
        ("Год", _value(movie.get("year"))),
        ("Жанр", _names(movie.get("genres"))),
        ("Рейтинг КП", _value((movie.get("rating") or {}).get("kp") if isinstance(movie.get("rating"), dict) else None)),
        ("Возраст", _value(movie.get("ageRating"))),
        ("Страна", _names(movie.get("countries"))),
        ("Длительность", _value(movie.get("movieLength"))),
        ("Бюджет", _value(movie.get("budget"))),
    ]
    for label, value in fields:
        if value:
            lines.append(f"{label}: {escape(value)}")
    persons = movie.get("persons") or []
    directors = [p.get("name") for p in persons if isinstance(p, dict)
                 and str(p.get("enProfession") or p.get("profession") or "").lower() in {"director", "режиссер", "режиссёр"}
                 and p.get("name")]
    if directors:
        lines.append(f"Режиссёр: {escape(', '.join(directors[:3]))}")
    description = movie.get("description") or movie.get("shortDescription")
    if description:
        text = str(description)
        if len(text) > 650:
            text = text[:647].rstrip() + "…"
        lines.extend(["", escape(text)])
    return "\n".join(lines)


def get_docs(data: dict) -> list[dict]:
    docs = data.get("docs")
    if isinstance(docs, list):
        return [x for x in docs if isinstance(x, dict)]
    if "id" in data:
        return [data]
    return []
