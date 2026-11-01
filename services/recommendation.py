"""Simple transparent genre-based recommendations."""
from collections import Counter

from database.models import Favorite, WatchedMovie, User


def preferred_genre(user: User) -> str | None:
    counts: Counter[str] = Counter()
    for model in (Favorite, WatchedMovie):
        for entry in model.select().where(model.user == user):
            for item in entry.movie.get("genres") or []:
                name = item.get("name") if isinstance(item, dict) else item
                if name:
                    counts[str(name)] += 1
    return counts.most_common(1)[0][0] if counts else None


def recommendation_filters(user: User) -> tuple[dict, str]:
    genre = preferred_genre(user)
    ratings = []
    for model in (Favorite, WatchedMovie):
        for entry in model.select().where(model.user == user):
            rating = entry.movie.get("rating")
            if isinstance(rating, dict) and isinstance(rating.get("kp"), (int, float)):
                ratings.append(float(rating["kp"]))
    rating_floor = max(1.0, round(sum(ratings) / len(ratings) - 1, 1)) if ratings else 7.0
    filters: dict = {"rating.kp": f"{rating_floor:g}-10", "sortField": "rating.kp",
                     "sortType": "-1", "limit": 8, "notNullFields": "id"}
    if genre:
        filters["genres.name"] = genre
        return filters, f"Подборка по жанру «{genre}» и рейтингу ваших списков"
    filters["rating.kp"] = f"{rating_floor:g}-10"
    filters["votes.kp"] = "1000-999999999"
    return filters, "Подборка по высокому рейтингу и числу голосов API"
