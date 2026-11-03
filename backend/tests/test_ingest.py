from app.ingest import clean_text, shared_genres


def test_shared_genres_maps_across_sources():
    assert shared_genres(["Science Fiction"]) == ["sci-fi"]  # TMDB
    assert shared_genres(["Sci-Fi", "Mecha"]) == ["sci-fi"]  # AniList
    assert shared_genres(["Fiction, science fiction, general"]) == ["sci-fi"]  # Open Library
    assert "mystery" in shared_genres(["Mystery and detective stories"])


def test_shared_genres_matches_whole_words_only():
    assert shared_genres(["Warriors", "Award winning"]) == []
    assert shared_genres(["Sports"]) == ["sports"]


def test_clean_text_strips_html_and_source_notes():
    assert clean_text("A boy.<br><br>\r\nHe fights. (Source: Crunchyroll)") == "A boy. He fights."
    assert clean_text("") is None
