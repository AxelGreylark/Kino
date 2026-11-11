"""TMDB : films, personnes, sagas. Toute réponse passe par le cache."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from .reseau import lire_json

RACINE = "https://api.themoviedb.org/3"


class TMDB:
    def __init__(self, con, config, lire=lire_json, fraicheur_jours=30):
        if not (config.tmdb_jeton or config.tmdb_cle):
            raise SystemExit("TMDB : renseigner TMDB_JETON (ou TMDB_CLE) dans .env")
        self.con = con
        self.config = config
        self.lire = lire
        self.limite = (datetime.now(timezone.utc) - timedelta(days=fraicheur_jours)).isoformat()
        self.appels = 0

    # Une demande est un couple (chemin, paramètres) ; sa clé de cache ne contient aucun secret.
    def _cle(self, chemin, params):
        return f"{chemin}?{urlencode(sorted(params.items()))}"

    def _telecharger(self, chemin, params):
        entetes = {}
        if self.config.tmdb_jeton:
            entetes["Authorization"] = f"Bearer {self.config.tmdb_jeton}"
        else:
            params = {**params, "api_key": self.config.tmdb_cle}
        return self.lire(f"{RACINE}{chemin}?{urlencode(sorted(params.items()))}", entetes)

    def _en_cache(self, cle):
        ligne = self.con.execute(
            "SELECT corps FROM cache WHERE cle = ? AND date >= ?", (cle, self.limite)
        ).fetchone()
        return (True, json.loads(ligne["corps"])) if ligne else (False, None)

    def _ranger(self, cle, corps):
        self.con.execute(
            "INSERT OR REPLACE INTO cache (cle, corps, date) VALUES (?, ?, ?)",
            (cle, json.dumps(corps, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )

    def obtenir(self, chemin, **params):
        cle = self._cle(chemin, params)
        trouve, corps = self._en_cache(cle)
        if not trouve:
            corps = self._telecharger(chemin, params)
            self.appels += 1
            self._ranger(cle, corps)
        return corps

    def precharger(self, demandes, fils=6):
        """Télécharge en parallèle ce qui manque au cache ; l'écriture reste sur ce fil."""
        manquantes = [d for d in demandes if not self._en_cache(self._cle(*d))[0]]
        if not manquantes:
            return
        with ThreadPoolExecutor(max_workers=fils) as groupe:
            for (chemin, params), corps in zip(
                manquantes, groupe.map(lambda d: self._telecharger(*d), manquantes)
            ):
                self.appels += 1
                self._ranger(self._cle(chemin, params), corps)
        self.con.commit()

    def demande_film(self, tmdb_id):
        return (
            f"/movie/{tmdb_id}",
            {"language": self.config.langue, "append_to_response": "credits"},
        )

    def demande_personne(self, tmdb_id):
        return (
            f"/person/{tmdb_id}",
            {"language": self.config.langue, "append_to_response": "movie_credits"},
        )

    def demande_saga(self, saga_id):
        return (f"/collection/{saga_id}", {"language": self.config.langue})

    def film(self, tmdb_id):
        chemin, params = self.demande_film(tmdb_id)
        return self.obtenir(chemin, **params)

    def personne(self, tmdb_id):
        chemin, params = self.demande_personne(tmdb_id)
        return self.obtenir(chemin, **params)

    def saga(self, saga_id):
        chemin, params = self.demande_saga(saga_id)
        return self.obtenir(chemin, **params)

    def trouver_par_imdb(self, imdb_id):
        corps = self.obtenir(f"/find/{imdb_id}", external_source="imdb_id") or {}
        films = corps.get("movie_results") or []
        return films[0]["id"] if films else None
