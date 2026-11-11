"""Films vus : Trakt (fait foi) et Plex (complément)."""

from datetime import datetime, timezone
from urllib.parse import quote

from .reseau import lire_json

TRAKT = "https://api.trakt.tv"


def _entetes_trakt(config):
    entetes = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": config.trakt_client_id,
    }
    if config.trakt_jeton:
        entetes["Authorization"] = f"Bearer {config.trakt_jeton}"
    return entetes


def trakt_visionnages(config, lire=lire_json):
    """Chaque lecture d'un film : {tmdb, imdb, titre, date}."""
    utilisateur = quote(config.trakt_utilisateur or "me")
    page = 1
    while True:
        lot = lire(
            f"{TRAKT}/users/{utilisateur}/history/movies?page={page}&limit=1000",
            _entetes_trakt(config),
        )
        if lot is None:
            raise SystemExit(f"Trakt : profil « {config.trakt_utilisateur} » introuvable ou privé")
        if not lot:
            return
        for element in lot:
            film = element.get("movie") or {}
            ids = film.get("ids") or {}
            yield {
                "tmdb": ids.get("tmdb"),
                "imdb": ids.get("imdb"),
                "titre": film.get("title"),
                "date": element.get("watched_at"),
            }
        page += 1


def trakt_notes(config, lire=lire_json):
    utilisateur = quote(config.trakt_utilisateur or "me")
    lot = lire(f"{TRAKT}/users/{utilisateur}/ratings/movies", _entetes_trakt(config)) or []
    for element in lot:
        ids = (element.get("movie") or {}).get("ids") or {}
        if ids.get("tmdb") and element.get("rating"):
            yield {"tmdb": ids["tmdb"], "note": element["rating"], "date": element.get("rated_at")}


def _ids_plex(film):
    ids = {}
    for guid in film.get("Guid") or []:
        nom, _, valeur = (guid.get("id") or "").partition("://")
        ids[nom] = valeur
    return ids


def plex_films(config, lire=lire_json):
    """Tous les films de Plex : {tmdb, imdb, titre, vu, date}."""
    entetes = {"X-Plex-Token": config.plex_jeton}
    sections = lire(f"{config.plex_url}/library/sections", entetes) or {}
    for section in (sections.get("MediaContainer") or {}).get("Directory") or []:
        if section.get("type") != "movie":
            continue
        contenu = lire(
            f"{config.plex_url}/library/sections/{section['key']}/all?type=1&includeGuids=1",
            entetes,
        ) or {}
        for film in (contenu.get("MediaContainer") or {}).get("Metadata") or []:
            ids = _ids_plex(film)
            vu = (film.get("viewCount") or 0) > 0 and film.get("lastViewedAt")
            yield {
                "tmdb": int(ids["tmdb"]) if ids.get("tmdb", "").isdigit() else None,
                "imdb": ids.get("imdb"),
                "titre": film.get("title"),
                "vu": bool(vu),
                "date": datetime.fromtimestamp(film["lastViewedAt"], timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
                if vu
                else None,
            }
