from utils.formatting import get_docs, movie_caption


def test_card_escapes_html_and_omits_missing_values():
    caption = movie_caption({"id": 1, "name": "<Тест>", "alternativeName": "Original",
                            "year": 2024, "genres": [{"name": "драма"}],
                            "rating": {"kp": 8.1}, "description": "Описание"})
    assert "&lt;Тест&gt;" in caption
    assert "Original" in caption
    assert "2024" in caption
    assert "Бюджет" not in caption


def test_docs_supports_search_and_detail_responses():
    assert get_docs({"docs": [{"id": 1}]}) == [{"id": 1}]
    assert get_docs({"id": 2}) == [{"id": 2}]
