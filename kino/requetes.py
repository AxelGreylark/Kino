"""Les questions qu'on pose au catalogue."""

from datetime import date

POSTES_FR = {
    "Director": "réalisation",
    "Director of Photography": "image",
    "Editor": "montage",
    "Original Music Composer": "musique",
    "Screenplay": "scénario",
    "Writer": "scénario",
    "Story": "histoire",
    "Production Design": "décors",
    "Costume Design": "costumes",
    "Sound Designer": "son",
    "Actor": "interprétation",
}


def poste_fr(poste):
    return POSTES_FR.get(poste, poste)


def _principal(texte):
    """Le poste le plus parlant quand une personne en cumule plusieurs sur un film."""
    postes = texte.split(",")
    return min(postes, key=lambda p: list(POSTES_FR).index(p) if p in POSTES_FR else len(POSTES_FR))


def _postes(texte):
    vus = []
    for poste in (texte or "").split(","):
        nom = poste_fr(poste)
        if nom not in vus:
            vus.append(nom)
    return ", ".join(vus)


def stats(con):
    un = lambda sql: con.execute(sql).fetchone()[0]
    return {
        "films vus": un("SELECT COUNT(*) FROM vu"),
        "visionnages": un("SELECT COUNT(*) FROM visionnage"),
        "films connus sans être vus": un(
            "SELECT COUNT(*) FROM film WHERE tmdb_id NOT IN (SELECT film_id FROM vu)"
        ),
        "personnes": un("SELECT COUNT(*) FROM personne"),
        "filmographies complètes": un("SELECT COUNT(*) FROM personne WHERE filmographie = 1"),
        "crédits": un("SELECT COUNT(*) FROM credit"),
    }


def techniciens(con, limite=30, departement=None, poste=None):
    """Qui revient le plus derrière la caméra dans mes films vus."""
    filtres, params = ["c.departement != 'Acting'"], []
    if departement:
        filtres.append("c.departement = ?")
        params.append(departement)
    if poste:
        filtres.append("c.poste = ?")
        params.append(poste)
    lignes = con.execute(
        f"""SELECT p.tmdb_id, p.nom, COUNT(DISTINCT c.film_id) AS films,
                   GROUP_CONCAT(DISTINCT c.poste) AS postes
            FROM credit c JOIN vu ON vu.film_id = c.film_id JOIN personne p ON p.tmdb_id = c.personne_id
            WHERE {' AND '.join(filtres)}
            GROUP BY p.tmdb_id ORDER BY films DESC, p.nom LIMIT ?""",
        (*params, limite),
    ).fetchall()
    return [
        {"id": l["tmdb_id"], "nom": l["nom"], "films": l["films"],
         "postes": _postes(l["postes"])}
        for l in lignes
    ]


def duos(con, limite=30, minimum=2, avec_distribution=False):
    """Les couples qui reviennent, à des postes clés, dans mes films vus."""
    acteurs = "" if avec_distribution else "AND NOT (a.departement = 'Acting' AND b.departement = 'Acting')"
    lignes = con.execute(
        f"""SELECT a.personne_id AS ida, b.personne_id AS idb, COUNT(DISTINCT a.film_id) AS films,
                   GROUP_CONCAT(DISTINCT a.poste) AS pa, GROUP_CONCAT(DISTINCT b.poste) AS pb
            FROM credit a
            JOIN credit b ON b.film_id = a.film_id AND b.personne_id > a.personne_id
            JOIN vu ON vu.film_id = a.film_id
            WHERE a.cle = 1 AND b.cle = 1 {acteurs}
            GROUP BY ida, idb HAVING films >= ? ORDER BY films DESC LIMIT ?""",
        (minimum, limite),
    ).fetchall()
    resultat = []
    for l in lignes:
        noms = dict(con.execute(
            "SELECT tmdb_id, nom FROM personne WHERE tmdb_id IN (?, ?)", (l["ida"], l["idb"])
        ).fetchall())
        # Films en commun (aux postes clés) sur toute leur carrière, si on connaît les deux filmographies.
        completes = con.execute(
            "SELECT COUNT(*) FROM personne WHERE filmographie = 1 AND tmdb_id IN (?, ?)",
            (l["ida"], l["idb"]),
        ).fetchone()[0] == 2
        communs = con.execute(
            """SELECT COUNT(DISTINCT a.film_id) FROM credit a JOIN credit b USING (film_id)
               WHERE a.personne_id = ? AND b.personne_id = ? AND a.cle = 1 AND b.cle = 1""",
            (l["ida"], l["idb"]),
        ).fetchone()[0] if completes else None
        resultat.append({
            "a": noms[l["ida"]], "postes_a": _postes(l["pa"]),
            "b": noms[l["idb"]], "postes_b": _postes(l["pb"]),
            "vus": l["films"], "communs": communs,
        })
    return resultat


def a_voir(con, limite=30, votes_min=20, aujourdhui=None):
    """Films non vus les plus reliés à mes films vus, chacun avec ses raisons."""
    aujourdhui = aujourdhui or date.today().isoformat()
    lignes = con.execute(
        """WITH poids AS (
               SELECT personne_id, COUNT(DISTINCT film_id) AS n
               FROM credit JOIN vu USING (film_id) WHERE cle = 1
               GROUP BY personne_id HAVING n >= 2),
           liens AS (
               SELECT c.film_id, c.personne_id, poids.n, MIN(c.poste) AS poste
               FROM credit c JOIN poids USING (personne_id)
               WHERE c.cle = 1 AND c.film_id NOT IN (SELECT film_id FROM vu)
               GROUP BY c.film_id, c.personne_id)
           SELECT f.tmdb_id, f.titre, f.annee, f.dans_plex, SUM(l.n) AS score,
                  COUNT(*) AS personnes
           FROM liens l JOIN film f ON f.tmdb_id = l.film_id
           WHERE f.date_sortie <= ? AND COALESCE(f.votes, 0) >= ?
           GROUP BY f.tmdb_id ORDER BY score DESC, personnes DESC, f.titre LIMIT ?""",
        (aujourdhui, votes_min, limite),
    ).fetchall()
    resultat = []
    for l in lignes:
        raisons = con.execute(
            """SELECT p.nom, GROUP_CONCAT(DISTINCT c.poste) AS postes,
                      (SELECT COUNT(DISTINCT c2.film_id) FROM credit c2 JOIN vu USING (film_id)
                       WHERE c2.personne_id = p.tmdb_id AND c2.cle = 1) AS n
               FROM credit c JOIN personne p ON p.tmdb_id = c.personne_id
               WHERE c.film_id = ? AND c.cle = 1
               GROUP BY p.tmdb_id HAVING n >= 2 ORDER BY n DESC, p.nom LIMIT 3""",
            (l["tmdb_id"],),
        ).fetchall()
        resultat.append({
            "id": l["tmdb_id"], "titre": l["titre"], "annee": l["annee"],
            "dans_plex": bool(l["dans_plex"]), "score": l["score"],
            "raisons": [f"{r['nom']} ({poste_fr(_principal(r['postes']))}, {r['n']} vus)" for r in raisons],
        })
    return resultat


def personne(con, nom):
    """Fiche d'une personne : sa filmographie, mes films vus cochés."""
    p = con.execute(
        """SELECT p.*, (SELECT COUNT(DISTINCT film_id) FROM credit JOIN vu USING (film_id)
                        WHERE personne_id = p.tmdb_id) AS vus
           FROM personne p WHERE p.nom LIKE ? ORDER BY vus DESC LIMIT 1""",
        (f"%{nom}%",),
    ).fetchone()
    if not p:
        return None
    films = con.execute(
        """SELECT f.titre, f.annee, GROUP_CONCAT(DISTINCT c.poste) AS postes,
                  EXISTS (SELECT 1 FROM vu WHERE film_id = f.tmdb_id) AS vu
           FROM credit c JOIN film f ON f.tmdb_id = c.film_id WHERE c.personne_id = ?
           GROUP BY f.tmdb_id ORDER BY f.date_sortie""",
        (p["tmdb_id"],),
    ).fetchall()
    return {
        "nom": p["nom"], "metier": p["metier"], "naissance": p["naissance"],
        "biographie": p["biographie"], "vus": p["vus"],
        "total": len(films) if p["filmographie"] else None,
        "films": [
            {"titre": f["titre"], "annee": f["annee"], "vu": bool(f["vu"]),
             "postes": _postes(f["postes"])}
            for f in films
        ],
    }
