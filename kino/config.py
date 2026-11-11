"""Réglages lus dans l'environnement, complétés par un fichier .env."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    tmdb_jeton: str = ""
    tmdb_cle: str = ""
    trakt_client_id: str = ""
    trakt_utilisateur: str = ""
    trakt_jeton: str = ""
    plex_url: str = ""
    plex_jeton: str = ""
    langue: str = "fr-FR"
    base: str = "kino.sqlite"


def lire_env(chemin):
    valeurs = {}
    fichier = Path(chemin)
    if not fichier.is_file():
        return valeurs
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        nom, valeur = ligne.split("=", 1)
        valeurs[nom.strip()] = valeur.strip().strip("\"'")
    return valeurs


def charger(env=None, fichier=".env"):
    """L'environnement l'emporte sur le fichier .env."""
    v = {**lire_env(fichier), **(os.environ if env is None else env)}
    return Config(
        tmdb_jeton=v.get("TMDB_JETON", ""),
        tmdb_cle=v.get("TMDB_CLE", ""),
        trakt_client_id=v.get("TRAKT_CLIENT_ID", ""),
        trakt_utilisateur=v.get("TRAKT_UTILISATEUR", ""),
        trakt_jeton=v.get("TRAKT_JETON", ""),
        plex_url=v.get("PLEX_URL", "").rstrip("/"),
        plex_jeton=v.get("PLEX_JETON", ""),
        langue=v.get("KINO_LANGUE", "") or "fr-FR",
        base=v.get("KINO_BASE", "") or "kino.sqlite",
    )
