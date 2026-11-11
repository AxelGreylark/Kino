"""Lecture JSON par HTTP, avec reprises. Bibliothèque standard seulement."""

import json
import re
import time
import urllib.error
import urllib.request

AGENT = "kino/0.1"


class ErreurReseau(Exception):
    pass


def sans_secret(url):
    return re.sub(r"(api_key|X-Plex-Token)=[^&]+", r"\1=…", url)


def lire_json(url, entetes=None, essais=5, attente=time.sleep):
    """Renvoie le JSON décodé, ou None si la ressource n'existe pas (404)."""
    requete = urllib.request.Request(
        url, headers={"User-Agent": AGENT, "Accept": "application/json", **(entetes or {})}
    )
    derniere = None
    for essai in range(essais):
        try:
            with urllib.request.urlopen(requete, timeout=30) as reponse:
                return json.load(reponse)
        except urllib.error.HTTPError as erreur:
            if erreur.code == 404:
                return None
            if erreur.code != 429 and erreur.code < 500:
                raise ErreurReseau(f"HTTP {erreur.code} sur {sans_secret(url)}") from None
            derniere = f"HTTP {erreur.code}"
            try:
                pause = float(erreur.headers.get("Retry-After") or 2**essai)
            except ValueError:
                pause = 2**essai
        except (urllib.error.URLError, TimeoutError) as erreur:
            derniere = str(getattr(erreur, "reason", erreur))
            pause = 2**essai
        attente(min(pause, 30))
    raise ErreurReseau(f"{derniere} sur {sans_secret(url)} après {essais} essais")
