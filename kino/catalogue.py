"""Reconstruit le catalogue : films vus → génériques → filmographies → sagas."""

from .base import POSTES_CLES, ROLES_CLES, vider_catalogue


def _annee(date):
    return int(date[:4]) if date and date[:4].isdigit() else None


def _film(con, f, complet):
    """Ajoute un film, ou complète une ligne connue seulement par une filmographie."""
    saga = f.get("belongs_to_collection") or {}
    valeurs = {
        "tmdb_id": f["id"],
        "imdb_id": f.get("imdb_id"),
        "titre": f.get("title") or f.get("original_title") or f"Film {f['id']}",
        "titre_original": f.get("original_title"),
        "date_sortie": f.get("release_date") or None,
        "annee": _annee(f.get("release_date")),
        "duree": f.get("runtime"),
        "pays": ", ".join(p["iso_3166_1"] for p in f.get("production_countries") or []) or None,
        "langue": f.get("original_language"),
        "synopsis": f.get("overview") or None,
        "affiche": f.get("poster_path"),
        "votes": f.get("vote_count"),
        "saga_id": saga.get("id"),
        "saga": saga.get("name"),
        "complet": int(complet),
    }
    if complet:
        con.execute(
            """INSERT INTO film (tmdb_id, imdb_id, titre, titre_original, date_sortie, annee, duree,
                   pays, langue, synopsis, affiche, votes, saga_id, saga, complet)
               VALUES (:tmdb_id, :imdb_id, :titre, :titre_original, :date_sortie, :annee, :duree,
                   :pays, :langue, :synopsis, :affiche, :votes, :saga_id, :saga, :complet)
               ON CONFLICT(tmdb_id) DO UPDATE SET imdb_id=excluded.imdb_id, titre=excluded.titre,
                   titre_original=excluded.titre_original, date_sortie=excluded.date_sortie,
                   annee=excluded.annee, duree=excluded.duree, pays=excluded.pays,
                   langue=excluded.langue, synopsis=excluded.synopsis, affiche=excluded.affiche,
                   votes=excluded.votes, saga_id=excluded.saga_id, saga=excluded.saga, complet=1""",
            valeurs,
        )
    else:
        con.execute(
            """INSERT OR IGNORE INTO film (tmdb_id, titre, titre_original, date_sortie, annee,
                   langue, synopsis, affiche, votes, complet)
               VALUES (:tmdb_id, :titre, :titre_original, :date_sortie, :annee,
                   :langue, :synopsis, :affiche, :votes, 0)""",
            valeurs,
        )


def _personne(con, p):
    con.execute(
        "INSERT OR IGNORE INTO personne (tmdb_id, nom, metier, photo) VALUES (?, ?, ?, ?)",
        (p["id"], p.get("name") or f"Personne {p['id']}", p.get("known_for_department"), p.get("profile_path")),
    )


def _credit(con, film_id, personne_id, c, distribution):
    if distribution:
        departement, poste = "Acting", "Actor"
        role, ordre = c.get("character") or "", c.get("order")
        cle = ordre is not None and ordre < ROLES_CLES
    else:
        departement, poste = c.get("department") or "?", c.get("job") or "?"
        role, ordre = "", None
        cle = poste in POSTES_CLES
    con.execute(
        "INSERT OR IGNORE INTO credit (film_id, personne_id, departement, poste, role, ordre, cle)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (film_id, personne_id, departement, poste, role, ordre, int(cle)),
    )


def _generique(con, f):
    credits = f.get("credits") or {}
    for distribution, liste in ((True, credits.get("cast")), (False, credits.get("crew"))):
        for c in liste or []:
            _personne(con, c)
            _credit(con, f["id"], c["id"], c, distribution)


def _filmographie(con, p):
    con.execute(
        """UPDATE personne SET imdb_id=?, nom=?, metier=?, naissance=?, deces=?, lieu=?,
               biographie=?, photo=?, filmographie=1 WHERE tmdb_id=?""",
        (
            p.get("imdb_id"), p.get("name"), p.get("known_for_department"), p.get("birthday"),
            p.get("deathday"), p.get("place_of_birth"), p.get("biography") or None,
            p.get("profile_path"), p["id"],
        ),
    )
    films = p.get("movie_credits") or {}
    for distribution, liste in ((True, films.get("cast")), (False, films.get("crew"))):
        for c in liste or []:
            if not c.get("release_date") or c.get("adult"):
                continue  # projets sans date de sortie : annoncés, abandonnés
            _film(con, c, complet=False)
            _credit(con, c["id"], p["id"], c, distribution)


def construire(con, config, tmdb, visionnages, notes=(), plex=(), seuil=2, journal=print):
    """Vide puis remplit le catalogue. Renvoie les titres laissés de côté."""
    ignores = []
    vus = {}      # tmdb_id -> {(date, source)}
    dans_plex = set()

    def identifiant(element):
        tmdb_id = element.get("tmdb")
        if not tmdb_id and element.get("imdb"):
            tmdb_id = tmdb.trouver_par_imdb(element["imdb"])
        if not tmdb_id:
            ignores.append(element.get("titre") or "?")
        return tmdb_id

    for v in visionnages:
        tmdb_id = identifiant(v)
        if tmdb_id and v.get("date"):
            vus.setdefault(tmdb_id, set()).add((v["date"], "trakt"))
    for p in plex:
        tmdb_id = identifiant(p)
        if not tmdb_id:
            continue
        dans_plex.add(tmdb_id)
        # Plex ne garde que la dernière lecture ; inutile si Trakt l'a déjà ce jour-là.
        jours = {date[:10] for date, _ in vus.get(tmdb_id, ())}
        if p.get("vu") and p["date"][:10] not in jours:
            vus.setdefault(tmdb_id, set()).add((p["date"], "plex"))

    journal(f"{len(vus)} films vus, {sum(len(d) for d in vus.values())} visionnages")
    tmdb.precharger([tmdb.demande_film(i) for i in vus])

    vider_catalogue(con)
    for tmdb_id, dates in vus.items():
        f = tmdb.film(tmdb_id)
        if not f:
            ignores.append(f"TMDB {tmdb_id}")
            continue
        _film(con, f, complet=True)
        _generique(con, f)
        con.executemany(
            "INSERT OR IGNORE INTO visionnage (film_id, date, source) VALUES (?, ?, ?)",
            [(tmdb_id, date, source) for date, source in dates],
        )
    for n in notes:
        con.execute(
            "INSERT OR REPLACE INTO note (film_id, note, date) SELECT ?, ?, ? WHERE EXISTS"
            " (SELECT 1 FROM film WHERE tmdb_id = ?)",
            (n["tmdb"], n["note"], n.get("date"), n["tmdb"]),
        )

    # Filmographies : seulement pour qui revient dans mes films à un poste clé.
    recurrents = [
        ligne["personne_id"]
        for ligne in con.execute(
            """SELECT personne_id FROM credit JOIN vu USING (film_id) WHERE cle = 1
               GROUP BY personne_id HAVING COUNT(DISTINCT film_id) >= ?""",
            (seuil,),
        )
    ]
    journal(f"{len(recurrents)} personnes reviennent dans au moins {seuil} films : filmographies")
    tmdb.precharger([tmdb.demande_personne(i) for i in recurrents])
    for personne_id in recurrents:
        p = tmdb.personne(personne_id)
        if p:
            _filmographie(con, p)

    # Sagas des films vus.
    sagas = [l["saga_id"] for l in con.execute(
        "SELECT DISTINCT saga_id FROM film JOIN vu ON film_id = tmdb_id WHERE saga_id IS NOT NULL"
    )]
    tmdb.precharger([tmdb.demande_saga(i) for i in sagas])
    for saga_id in sagas:
        saga = tmdb.saga(saga_id) or {}
        volets = [v for v in saga.get("parts") or [] if v.get("release_date")]
        for v in volets:
            _film(con, v, complet=False)
        for a in volets:
            for b in volets:
                if a["id"] < b["id"]:
                    con.execute(
                        "INSERT OR IGNORE INTO lien_film (film_a, film_b, type, source)"
                        " VALUES (?, ?, 'saga', 'tmdb')",
                        (a["id"], b["id"]),
                    )

    if dans_plex:
        con.executemany("UPDATE film SET dans_plex = 1 WHERE tmdb_id = ?", [(i,) for i in dans_plex])
    con.commit()
    return ignores
