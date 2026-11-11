"""Schéma de la base. Le catalogue se reconstruit ; seul le cache persiste."""

import sqlite3

# Postes retenus pour relier les films entre eux (noms de TMDB).
POSTES_CLES = {
    "Director",
    "Director of Photography",
    "Editor",
    "Original Music Composer",
    "Screenplay",
    "Writer",
    "Story",
    "Production Design",
    "Costume Design",
    "Sound Designer",
}
# Dans la distribution, seuls les premiers rôles comptent comme liens.
ROLES_CLES = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    cle   TEXT PRIMARY KEY,
    corps TEXT NOT NULL,
    date  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS film (
    tmdb_id        INTEGER PRIMARY KEY,
    imdb_id        TEXT,
    titre          TEXT NOT NULL,
    titre_original TEXT,
    date_sortie    TEXT,
    annee          INTEGER,
    duree          INTEGER,
    pays           TEXT,
    langue         TEXT,
    synopsis       TEXT,
    affiche        TEXT,
    votes          INTEGER,
    saga_id        INTEGER,
    saga           TEXT,
    dans_plex      INTEGER NOT NULL DEFAULT 0,
    complet        INTEGER NOT NULL DEFAULT 0  -- 1 : générique entier ; 0 : connu par une filmographie
);
CREATE TABLE IF NOT EXISTS personne (
    tmdb_id       INTEGER PRIMARY KEY,
    imdb_id       TEXT,
    nom           TEXT NOT NULL,
    metier        TEXT,
    naissance     TEXT,
    deces         TEXT,
    lieu          TEXT,
    biographie    TEXT,
    photo         TEXT,
    filmographie  INTEGER NOT NULL DEFAULT 0  -- 1 : toute sa filmographie est dans la base
);
CREATE TABLE IF NOT EXISTS credit (
    film_id     INTEGER NOT NULL REFERENCES film(tmdb_id),
    personne_id INTEGER NOT NULL REFERENCES personne(tmdb_id),
    departement TEXT NOT NULL,
    poste       TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT '',
    ordre       INTEGER,
    cle         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (film_id, personne_id, departement, poste, role)
);
CREATE INDEX IF NOT EXISTS credit_personne ON credit(personne_id);
CREATE TABLE IF NOT EXISTS visionnage (
    film_id INTEGER NOT NULL REFERENCES film(tmdb_id),
    date    TEXT NOT NULL,
    source  TEXT NOT NULL,
    PRIMARY KEY (film_id, date, source)
);
CREATE TABLE IF NOT EXISTS note (
    film_id INTEGER PRIMARY KEY REFERENCES film(tmdb_id),
    note    INTEGER NOT NULL,
    date    TEXT
);
CREATE TABLE IF NOT EXISTS lien_film (
    film_a INTEGER NOT NULL REFERENCES film(tmdb_id),
    film_b INTEGER NOT NULL REFERENCES film(tmdb_id),
    type   TEXT NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (film_a, film_b, type)
);
CREATE VIEW IF NOT EXISTS vu AS
    SELECT film_id, COUNT(*) AS fois, MAX(date) AS dernier FROM visionnage GROUP BY film_id;
"""

TABLES_CATALOGUE = ("lien_film", "note", "visionnage", "credit", "personne", "film")


def ouvrir(chemin):
    con = sqlite3.connect(chemin)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def vider_catalogue(con):
    for table in TABLES_CATALOGUE:
        con.execute(f"DELETE FROM {table}")
