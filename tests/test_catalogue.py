"""Le catalogue se construit sans réseau, à partir de réponses TMDB factices."""

import unittest

from kino import requetes
from kino.base import ouvrir
from kino.catalogue import construire
from kino.config import Config
from kino.sources import plex_films, trakt_visionnages
from kino.tmdb import TMDB


def equipe(*membres):
    return [{"id": i, "name": n, "department": d, "job": j} for i, n, d, j in membres]


DEAKINS = (10, "Roger Deakins", "Camera", "Director of Photography")
VILLENEUVE = (11, "Denis Villeneuve", "Directing", "Director")
WALKER = (12, "Joe Walker", "Editing", "Editor")
GRIP = (13, "Un Machiniste", "Camera", "Grip")

FILMS = {
    1: {"id": 1, "title": "Sicario", "release_date": "2015-09-17", "runtime": 121,
        "credits": {"cast": [{"id": 20, "name": "Emily Blunt", "character": "Kate", "order": 0}],
                    "crew": equipe(DEAKINS, VILLENEUVE, WALKER, GRIP)}},
    2: {"id": 2, "title": "Blade Runner 2049", "release_date": "2017-10-04",
        "belongs_to_collection": {"id": 90, "name": "Blade Runner"},
        "credits": {"cast": [], "crew": equipe(DEAKINS, VILLENEUVE, WALKER)}},
    3: {"id": 3, "title": "Skyfall", "release_date": "2012-10-24",
        "credits": {"cast": [], "crew": equipe(DEAKINS, GRIP)}},
}


def filmographie(personne, *films):
    ident, nom, departement, poste = personne
    return {"id": ident, "name": nom, "known_for_department": departement, "biography": "",
            "movie_credits": {"cast": [], "crew": [
                {"id": i, "title": t, "release_date": d, "vote_count": v,
                 "department": departement, "job": poste} for i, t, d, v in films]}}


VUS = [(1, "Sicario", "2015-09-17", 900), (2, "Blade Runner 2049", "2017-10-04", 900)]
PERSONNES = {
    10: filmographie(DEAKINS, *VUS, (3, "Skyfall", "2012-10-24", 900),
                     (4, "Prisoners", "2013-09-18", 900), (5, "Projet annoncé", "", 0),
                     (6, "Film futur", "2999-01-01", 900)),
    11: filmographie(VILLENEUVE, *VUS, (4, "Prisoners", "2013-09-18", 900),
                     (7, "Court confidentiel", "1994-01-01", 3)),
    12: filmographie(WALKER, *VUS),
}
SAGAS = {90: {"id": 90, "parts": [
    {"id": 2, "title": "Blade Runner 2049", "release_date": "2017-10-04"},
    {"id": 8, "title": "Blade Runner", "release_date": "1982-06-25"}]}}


class FauxTMDB:
    def __init__(self):
        self.urls = []

    def __call__(self, url, entetes=None):
        self.urls.append(url)
        chemin = url.split("/3", 1)[1].split("?")[0]
        _, genre, ident = chemin.split("/")
        if genre == "find":
            return {"movie_results": [{"id": 3}] if ident == "tt1074638" else []}
        return {"movie": FILMS, "person": PERSONNES, "collection": SAGAS}[genre].get(int(ident))


def catalogue(visionnages, **options):
    con = ouvrir(":memory:")
    faux = FauxTMDB()
    tmdb = TMDB(con, Config(tmdb_jeton="x"), lire=faux)
    ignores = construire(con, Config(), tmdb, visionnages, journal=lambda _: None, **options)
    return con, faux, tmdb, ignores


TRAKT = [
    {"tmdb": 1, "titre": "Sicario", "date": "2020-01-01T20:00:00.000Z"},
    {"tmdb": 1, "titre": "Sicario", "date": "2023-05-05T20:00:00.000Z"},
    {"tmdb": 2, "titre": "Blade Runner 2049", "date": "2021-02-02T20:00:00.000Z"},
    {"tmdb": None, "imdb": "tt1074638", "titre": "Skyfall", "date": "2022-03-03T20:00:00.000Z"},
    {"tmdb": None, "imdb": None, "titre": "Inconnu", "date": "2022-03-04T20:00:00.000Z"},
]


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.con, self.faux, self.tmdb, self.ignores = catalogue(TRAKT)
        self.addCleanup(self.con.close)

    def test_films_vus_et_visionnages(self):
        s = requetes.stats(self.con)
        self.assertEqual(s["films vus"], 3)          # Skyfall retrouvé par son identifiant IMDb
        self.assertEqual(s["visionnages"], 4)        # Sicario vu deux fois
        self.assertEqual(self.ignores, ["Inconnu"])

    def test_filmographies_seulement_pour_qui_revient(self):
        charges = {l["nom"] for l in self.con.execute("SELECT nom FROM personne WHERE filmographie = 1")}
        # Le machiniste revient deux fois mais pas à un poste clé ; Emily Blunt n'apparaît qu'une fois.
        self.assertEqual(charges, {"Roger Deakins", "Denis Villeneuve", "Joe Walker"})

    def test_techniciens(self):
        premier = requetes.techniciens(self.con)[0]
        self.assertEqual((premier["nom"], premier["films"], premier["postes"]), ("Roger Deakins", 3, "image"))
        self.assertEqual([l["nom"] for l in requetes.techniciens(self.con, poste="Editor")], ["Joe Walker"])

    def test_duos(self):
        duos = requetes.duos(self.con)
        self.assertEqual(len(duos), 3)
        paire = next(d for d in duos if {d["a"], d["b"]} == {"Roger Deakins", "Denis Villeneuve"})
        self.assertEqual((paire["vus"], paire["communs"]), (2, 3))   # Prisoners en commun, pas vu

    def test_a_voir(self):
        resultat = requetes.a_voir(self.con, aujourdhui="2026-01-01")
        # Ni le projet sans date, ni le film futur, ni le court à trois votes, ni la saga seule.
        self.assertEqual([l["titre"] for l in resultat], ["Prisoners"])
        self.assertEqual(resultat[0]["score"], 5)
        self.assertEqual(resultat[0]["raisons"],
                         ["Roger Deakins (image, 3 vus)", "Denis Villeneuve (réalisation, 2 vus)"])

    def test_personne_vus_sur_total(self):
        p = requetes.personne(self.con, "deakins")
        self.assertEqual((p["vus"], p["total"]), (3, 5))
        self.assertEqual([f["titre"] for f in p["films"] if f["vu"]],
                         ["Skyfall", "Sicario", "Blade Runner 2049"])
        self.assertIsNone(requetes.personne(self.con, "Blunt")["total"])

    def test_saga(self):
        liens = self.con.execute("SELECT film_a, film_b, type FROM lien_film").fetchall()
        self.assertEqual([tuple(l) for l in liens], [(2, 8, "saga")])

    def test_reconstruction_depuis_le_cache(self):
        avant = len(self.faux.urls)
        construire(self.con, Config(), self.tmdb, TRAKT[:1], journal=lambda _: None)
        self.assertEqual(len(self.faux.urls), avant)                 # aucun nouvel appel
        self.assertEqual(requetes.stats(self.con)["films vus"], 1)   # le catalogue suit la source

    def test_le_jeton_ne_va_pas_dans_le_cache(self):
        con = ouvrir(":memory:")
        self.addCleanup(con.close)
        TMDB(con, Config(tmdb_cle="SECRET"), lire=FauxTMDB()).film(1)
        self.assertNotIn("SECRET", con.execute("SELECT cle || corps FROM cache").fetchone()[0])


class Plex(unittest.TestCase):
    def test_plex_complete_trakt(self):
        plex = [
            {"tmdb": 1, "titre": "Sicario", "vu": True, "date": "2023-05-05T22:10:00Z"},   # déjà dans Trakt
            {"tmdb": 3, "titre": "Skyfall", "vu": True, "date": "2024-06-06T21:00:00Z"},   # Plex seul
            {"tmdb": 2, "titre": "Blade Runner 2049", "vu": False, "date": None},
        ]
        con, *_ = catalogue(TRAKT[:2], plex=plex)
        self.addCleanup(con.close)
        sources = [tuple(l) for l in con.execute(
            "SELECT film_id, source FROM visionnage ORDER BY film_id, date")]
        self.assertEqual(sources, [(1, "trakt"), (1, "trakt"), (3, "plex")])
        # Blade Runner 2049, pas vu, est connu par les filmographies : il est marqué disponible aussi.
        self.assertEqual(con.execute("SELECT COUNT(*) FROM film WHERE dans_plex = 1").fetchone()[0], 3)
        self.assertTrue(requetes.a_voir(con, votes_min=0)[0]["dans_plex"])

    def test_lecture_des_reponses(self):
        def lire(url, entetes=None):
            if url.endswith("/library/sections"):
                return {"MediaContainer": {"Directory": [{"type": "movie", "key": "1"},
                                                         {"type": "show", "key": "2"}]}}
            return {"MediaContainer": {"Metadata": [
                {"title": "Sicario", "viewCount": 1, "lastViewedAt": 1700000000,
                 "Guid": [{"id": "imdb://tt3397884"}, {"id": "tmdb://273481"}]},
                {"title": "Jamais vu", "Guid": []}]}}
        films = list(plex_films(Config(plex_url="http://plex", plex_jeton="x"), lire))
        self.assertEqual(films[0], {"tmdb": 273481, "imdb": "tt3397884", "titre": "Sicario",
                                    "vu": True, "date": "2023-11-14T22:13:20Z"})
        self.assertEqual((films[1]["tmdb"], films[1]["vu"]), (None, False))


class Trakt(unittest.TestCase):
    def test_pagination(self):
        pages = {1: [{"watched_at": "2020-01-01T00:00:00.000Z",
                      "movie": {"title": "Sicario", "ids": {"tmdb": 1, "imdb": "tt3397884"}}}], 2: []}
        appels = []

        def lire(url, entetes=None):
            appels.append((url, entetes))
            return pages[int(url.split("page=")[1].split("&")[0])]
        vus = list(trakt_visionnages(Config(trakt_client_id="id", trakt_utilisateur="moi"), lire))
        self.assertEqual(vus, [{"tmdb": 1, "imdb": "tt3397884", "titre": "Sicario",
                                "date": "2020-01-01T00:00:00.000Z"}])
        self.assertEqual(len(appels), 2)
        self.assertEqual(appels[0][1]["trakt-api-key"], "id")


if __name__ == "__main__":
    unittest.main()
