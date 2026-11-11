# Kino

Un « Roon du cinéma » : partir de mes films vus, rendre chaque nom du générique
cliquable, relier les films et les techniciens entre eux.

Ce dépôt contient pour l'instant la première brique : **le catalogue**, une base
SQLite construite par un script à partir de Trakt, Plex et TMDB, et quelques
requêtes pour juger si les liens sont intéressants. L'app viendra lire cette base.

## Mise en route

Python 3.10 ou plus récent, sans aucune dépendance.

```sh
cp .env.exemple .env      # puis remplir les clés
python3 -m kino sync      # construit kino.sqlite
```

Il faut :

- **TMDB** : le « jeton d'accès en lecture à l'API » (Paramètres → API du compte).
- **Trakt** : le « Client ID » d'une application créée sur
  `trakt.tv/oauth/applications`, et le nom du profil. Le profil doit être public,
  sinon ajouter un jeton d'accès (`TRAKT_JETON`).
- **Plex** (facultatif) : l'adresse du serveur et son `X-Plex-Token`.

## Les questions

```sh
python3 -m kino stats                      # taille du catalogue
python3 -m kino techniciens                # qui revient le plus derrière la caméra
python3 -m kino techniciens --poste "Director of Photography"
python3 -m kino duos                       # les couples qui reviennent
python3 -m kino a-voir                     # films non vus les plus reliés, avec leurs raisons
python3 -m kino personne "Deakins"         # filmographie, films vus cochés, « vus 7 sur 23 »
```

## Comment ça marche

1. **Films vus.** Trakt fait foi (chaque lecture, avec sa date, et les notes).
   Plex complète : sa dernière lecture d'un film est ajoutée si Trakt ne l'a pas
   ce jour-là, et les films présents sur le serveur sont marqués `dans_plex`.
   Tout est rapproché par l'identifiant TMDB, jamais par le titre.
2. **Génériques.** Pour chaque film vu, TMDB donne la distribution et l'équipe
   entière, par département et par poste.
3. **Filmographies.** Seulement pour les personnes qui reviennent dans au moins
   deux films vus à un **poste clé** (réalisation, image, montage, musique,
   scénario, décors, costumes, son, ou l'un des cinq premiers rôles). C'est ce
   qui fait entrer les films non vus dans la base, et ce qui permet « vus sur total ».
4. **Sagas.** Les volets des sagas des films vus sont reliés entre eux.

Le catalogue est **jetable** : `sync` le vide et le reconstruit à chaque fois.
Seule la table `cache` persiste (réponses de TMDB, gardées 30 jours), ce qui rend
les reconstructions rapides. Rien de personnel ne doit donc être écrit dans cette
base : les notes vivront dans une base à part.

## La base

| Table | Contenu |
| --- | --- |
| `film` | un film ; `complet = 1` si son générique entier est chargé |
| `personne` | une personne ; `filmographie = 1` si toute sa filmographie est chargée |
| `credit` | film, personne, département, poste, rôle ; `cle = 1` pour les postes clés |
| `visionnage` | film, date, source (`trakt` ou `plex`) |
| `note` | note Trakt sur 10 |
| `lien_film` | lien entre deux films (pour l'instant : `saga`) |
| `vu` (vue) | films vus, nombre de fois, dernière date |

Les postes et départements gardent leurs noms TMDB (en anglais) dans la base ;
la traduction se fait à l'affichage.

## Tests

```sh
python3 -m unittest discover -s tests
```

Ils tournent sans réseau, sur des réponses factices.

## Ensuite

- Liens entre films par Wikidata (adaptation, remake, « inspiré de »).
- Coulisses : Wikipédia, et les passages des articles de Momo.
- Le chemin le plus court entre deux films.
- L'app SwiftUI, et la base des notes personnelles.

Données de films et de personnes fournies par TMDB ; ce projet n'est ni approuvé
ni certifié par TMDB.
