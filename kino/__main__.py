"""Ligne de commande : python3 -m kino <commande>."""

import argparse

from . import requetes
from .base import ouvrir
from .catalogue import construire
from .config import charger
from .sources import plex_films, trakt_notes, trakt_visionnages
from .tmdb import TMDB


def cmd_sync(con, config, args):
    if not config.trakt_client_id:
        raise SystemExit("Trakt : renseigner TRAKT_CLIENT_ID et TRAKT_UTILISATEUR dans .env")
    tmdb = TMDB(con, config, fraicheur_jours=args.fraicheur)
    plex = list(plex_films(config)) if config.plex_url and not args.sans_plex else []
    if plex:
        print(f"Plex : {len(plex)} films, dont {sum(p['vu'] for p in plex)} vus")
    visionnages = list(trakt_visionnages(config))
    if not visionnages and not any(p["vu"] for p in plex):
        raise SystemExit(
            f"Aucun film vu : l'historique Trakt de « {config.trakt_utilisateur} » est vide"
            " et Plex n'en apporte pas. Le catalogue n'a pas été modifié."
        )
    ignores = construire(
        con, config, tmdb,
        visionnages=visionnages,
        notes=list(trakt_notes(config)),
        plex=plex, seuil=args.seuil,
    )
    print(f"{tmdb.appels} appels à TMDB (le reste vient du cache)")
    if ignores:
        print(f"{len(ignores)} titres sans identifiant TMDB, laissés de côté : " + ", ".join(ignores[:20]))
    cmd_stats(con, config, args)


def cmd_stats(con, config, args):
    for nom, valeur in requetes.stats(con).items():
        print(f"{valeur:>8}  {nom}")


def cmd_techniciens(con, config, args):
    for l in requetes.techniciens(con, args.n, args.departement, args.poste):
        print(f"{l['films']:>4}  {l['nom']} — {l['postes']}")


def cmd_duos(con, config, args):
    for l in requetes.duos(con, args.n, args.minimum, args.distribution):
        total = f" sur {l['communs']} films en commun" if l["communs"] else ""
        print(f"{l['vus']:>4} vus{total}  {l['a']} ({l['postes_a']}) + {l['b']} ({l['postes_b']})")


def cmd_a_voir(con, config, args):
    for l in requetes.a_voir(con, args.n, args.votes):
        plex = "  [dans Plex]" if l["dans_plex"] else ""
        print(f"{l['score']:>4}  {l['titre']} ({l['annee']}){plex}\n        " + " · ".join(l["raisons"]))


def cmd_personne(con, config, args):
    p = requetes.personne(con, args.nom)
    if not p:
        raise SystemExit(f"Personne ne correspond à « {args.nom} »")
    total = f" sur {p['total']}" if p["total"] else " (filmographie non chargée)"
    print(f"{p['nom']} — {p['metier'] or '?'} — {p['vus']} vus{total}")
    for f in p["films"]:
        print(f"  {'✓' if f['vu'] else ' '} {f['annee'] or '    '}  {f['titre']} — {f['postes']}")


def main(argv=None):
    parseur = argparse.ArgumentParser(prog="kino", description=__doc__)
    sous = parseur.add_subparsers(dest="commande", required=True)

    s = sous.add_parser("sync", help="reconstruire le catalogue depuis Trakt, Plex et TMDB")
    s.add_argument("--seuil", type=int, default=2,
                   help="charger la filmographie de qui revient dans au moins N films vus (2)")
    s.add_argument("--fraicheur", type=int, default=30, help="durée de vie du cache TMDB, en jours (30)")
    s.add_argument("--sans-plex", action="store_true")
    s.set_defaults(action=cmd_sync)

    sous.add_parser("stats", help="taille du catalogue").set_defaults(action=cmd_stats)

    s = sous.add_parser("techniciens", help="qui revient le plus derrière la caméra")
    s.add_argument("-n", type=int, default=30)
    s.add_argument("--departement", help="nom TMDB : Camera, Editing, Sound, Art…")
    s.add_argument("--poste", help="nom TMDB : « Director of Photography », Editor…")
    s.set_defaults(action=cmd_techniciens)

    s = sous.add_parser("duos", help="les couples qui reviennent")
    s.add_argument("-n", type=int, default=30)
    s.add_argument("--minimum", type=int, default=2, help="films vus en commun (2)")
    s.add_argument("--distribution", action="store_true", help="garder aussi les couples d'interprètes")
    s.set_defaults(action=cmd_duos)

    s = sous.add_parser("a-voir", help="films non vus les plus reliés aux films vus")
    s.add_argument("-n", type=int, default=30)
    s.add_argument("--votes", type=int, default=20, help="écarter les films à moins de N votes TMDB (20)")
    s.set_defaults(action=cmd_a_voir)

    s = sous.add_parser("personne", help="fiche d'une personne : vus sur total")
    s.add_argument("nom")
    s.set_defaults(action=cmd_personne)

    args = parseur.parse_args(argv)
    config = charger()
    con = ouvrir(config.base)
    try:
        args.action(con, config, args)
    finally:
        con.close()


if __name__ == "__main__":
    main()
