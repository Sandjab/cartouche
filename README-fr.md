# Cartouche

> 🇬🇧 [English](README.md) · 🇫🇷 **Français** (vous êtes ici)

> Dashboards SVG façon dessin technique pour repos et profils GitHub.
> Primitives SVG pures, seize thèmes (variantes filigranées incluses), deux langues, intégrables dans tout README via `<picture>`.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/dashboard-dark.svg">
  <img src="assets/dashboard-light.svg" alt="Dashboard Cartouche pour le repo cartouche — rafraîchi toutes les 6 heures par GitHub Actions">
</picture>

Cartouche prend un repo GitHub (ou un profil entier) et en tire un dashboard
SVG dans l'esthétique du dessin technique : grille, double-cadre, courbes
d'étoiles annotées, radar de santé, métriques, et un bloc de titre type
*cartouche d'architecte* en bas à droite. Seize thèmes (light + dark, avec
des variantes filigranées Vellum + Davinci, Botanical + Floral, Blossom +
Kawai), deux langues built-in (en + fr) avec ajout de packs personnalisés
par fichier JSON, le tout prêt à être servi aux deux modes via la balise
`<picture>`.

## Pourquoi

Les solutions existantes (star-history.com, GitHub Charts, etc.) servent les
images via le proxy Camo, ce qui se traduit par du cache agressif côté
GitHub, des ratés de rafraîchissement, et zéro contrôle sur le rendu.
Cartouche prend l'autre côté du tradeoff : générer le SVG en local via une
GitHub Action, le commiter dans `assets/`, et le servir comme fichier
versionné — donc rafraîchi à la cadence de votre cron, lisible par tout le
monde, et stylisable à votre goût.

## Installation

```bash
pip install cartouche-svg
```

Aucune dépendance runtime — Cartouche utilise uniquement la stdlib (`urllib`
pour les appels API, `json`, `datetime`, `math`, `importlib.resources`).

## Utilisation en CLI

```bash
# Dashboard pour un repo (anglais par défaut)
cartouche repo Sandjab/Athanor --theme blueprint-light --out dashboard.svg

# Même dashboard en français
cartouche repo Sandjab/Athanor --theme blueprint-light --lang fr --out dashboard.svg

# Dashboard pour un profil
cartouche profile Sandjab --theme drafting-dark --out profile.svg

# Lister les thèmes et langues disponibles
cartouche themes
cartouche langs

# Tester sans toucher à l'API (données mockées)
cartouche repo Sandjab/Athanor --mock --theme vellum-light

# Surcharger une langue avec votre propre pack JSON
cartouche repo Sandjab/Athanor --lang fr --lang-file ./my-overrides.json

# Remplacer les callouts auto-détectés sur la courbe d'étoiles
cartouche repo Sandjab/Athanor --annotations-file ./events.json
```

Le CLI lit le token GitHub dans cet ordre : `--token`, `$GITHUB_TOKEN`,
`$GH_TOKEN`, sinon anonyme (60 req/h, suffit rarement pour un profil).

## Internationalisation

**Anglais par défaut.** Activez le français avec `--lang fr`.

### Packs built-in

```bash
cartouche langs   # → en, fr
```

### Ajouter une langue

Déposez un fichier `<code>.json` dans `src/cartouche/lang/`, en miroir du
schéma de `en.json` (clés `labels`, `templates`, `months_short`,
`months_long`). Le test `test_lang_has_all_required_keys` vous indique
quelles clés sont obligatoires. Une fois le fichier déposé et le wheel
reconstruit, `--lang <code>` est utilisable directement.

### Surcharger sans recompiler

Pour modifier ponctuellement quelques chaînes sans publier un nouveau pack,
créez un JSON d'overlay et passez-le via `--lang-file` :

```json
{
  "labels": {
    "fig_radar_health": "FIG. 02 — VITAL SIGNS",
    "drawn_by": "BY"
  },
  "templates": {
    "n_years": "{n} years"
  }
}
```

```bash
cartouche repo Sandjab/Athanor --lang en --lang-file my-overrides.json --out dashboard.svg
```

L'overlay est *deep-merged* sur le pack de base : seules les clés que vous
définissez sont remplacées, le reste reste inchangé.

### Schéma d'un pack de langue

```json
{
  "code": "xx",
  "name": "My language",
  "labels": {
    "drawn_by": "...",
    "fig_radar_health": "...",
    "card_stargazers": "...",
    ...
  },
  "templates": {
    "fig_star_history": "FIG. 01 — STAR HISTORY · {start} → {end}",
    "first_star_top": "// FIRST STAR — {date}",
    ...
  },
  "months_short": ["JAN", "FEB", ...],
  "months_long":  ["Jan", "Feb", ...]
}
```

Voir `src/cartouche/lang/en.json` pour la liste complète des clés.

## Thèmes

Seize thèmes en huit familles, chacune avec un pendant clair et sombre.
Les cinq premières familles sont des palettes nettes ; les trois dernières
sont des variantes filigranées qui posent un PNG livré (planche Da Vinci,
motif floral, perso kawaii) en arrière-plan, sous le calque de données, à
faible opacité. Voir [THEMES.md](THEMES.md) pour les aperçus light/dark
côte à côte de chaque variante.

| Famille                | Light                       | Dark                       |
|------------------------|-----------------------------|----------------------------|
| **Drafting**           | `drafting-light`            | `drafting-dark`            |
| **Blueprint**          | `blueprint-light`           | `blueprint-dark`           |
| **Vellum**             | `vellum-light`              | `vellum-dark`              |
| **Botanical**          | `botanical-light`           | `botanical-dark`           |
| **Blossom**            | `blossom-light`             | `blossom-dark`             |
| **Vellum + Davinci**   | `vellum-davinci-light`      | `vellum-davinci-dark`      |
| **Botanical + Floral** | `botanical-floral-light`    | `botanical-floral-dark`    |
| **Blossom + Kawai**    | `blossom-kawai-light`       | `blossom-kawai-dark`       |

- **Drafting** — papier blanc / encre indigo. Achromatique, neutre, le ton
  d'une note technique.
- **Blueprint** — cyanotype. Pâle bleu nuage clair, ou plongée nocturne dans
  le bleu de Prusse profond.
- **Vellum** — vélin crème / sépia. Côté sombre : cuir patiné et or. Pour
  qui veut un côté Beaux-Arts plutôt qu'ingénieur.
- **Botanical** — planche d'herbier 19e siècle. Encre sauge-et-fougère sur
  ivoire, ou forêt nocturne avec accents pollen-bougie.
- **Blossom** — sakura kawaii. Rose poudré sur ivoire gris perle, ou
  boudoir aubergine nocturne, données rose néon-doux et accents menthe.
- **Vellum + Davinci** — palette Vellum + filigrane planche Da Vinci. La
  surface lit comme un vieux codex où le carnet du maître transparaît.
- **Botanical + Floral** — palette Botanical + filigrane motif floral.
  L'esthétique d'herbier poussée vers un papier-peint floral.
- **Blossom + Kawai** — palette Blossom + filigrane perso kawaii. Pleine
  papeterie sakura, mascotte douce sous la grille du cartouche.

## Annotations personnalisées

Par défaut, le dashboard repo détecte automatiquement deux callouts sur la
courbe d'étoiles : la **première étoile** et le **plus gros pic single-step**.
Passez `--annotations-file path/to/events.json` pour les remplacer par votre
propre liste d'événements :

```json
[
  {"date": "2025-12-15", "label_top": "// HACKER NEWS", "label_bottom": "// front page"},
  {"date": "2026-04-01", "label_top": "// SHIPPED v1", "label_bottom": "// public release"},
  {"date": "2026-04-15", "count": 100, "label_top": "// MILESTONE", "label_bottom": "// 100 stars"}
]
```

- **`date`** (obligatoire, ISO `YYYY-MM-DD`) — point d'ancrage du callout
  sur l'axe.
- **`label_top`** / **`label_bottom`** (obligatoires) — les deux lignes de
  texte tracées à côté du fil de leader. Convention : `// PRÉFIXE` pour la
  première ligne, libellé descriptif pour la deuxième, mais tout passe.
- **`count`** (optionnel) — le total d'étoiles cumulé pour positionner le
  point sur la courbe. Si absent, Cartouche le déduit du `star_history` à
  la date la plus proche en amont.

Les annotations custom **remplacent** la paire auto-détectée — copiez-les
dans votre fichier si vous voulez les conserver. Disponible uniquement sur
le dashboard `repo` (la courbe `profile` n'a pas d'annotations).

## Embedding dans un README

Servir la bonne variante au visiteur selon le `prefers-color-scheme` de son
navigateur :

```markdown
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/dashboard-dark.svg">
  <img src="assets/dashboard-light.svg" alt="Cartouche dashboard">
</picture>
```

Important : utilisez un **chemin relatif** (`assets/...`), pas une URL
absolue. GitHub réécrit les images externes via son proxy Camo qui casse le
mécanisme `<picture>` light/dark ; les chemins relatifs sont servis tels
quels.

## Mise à jour automatique via GitHub Actions

Deux workflows prêts à l'emploi dans `examples/workflows/` :

- `repo-dashboard.yml` — à coller dans `.github/workflows/` du repo dont vous
  voulez le dashboard. Toutes les 6 heures, regénère et commite.
- `profile-dashboard.yml` — à coller dans votre **profile repo**
  (`<handle>/<handle>`). Toutes les 12 heures.

Les deux utilisent `secrets.GITHUB_TOKEN` (déjà disponible dans toute Action)
et fonctionnent sans configuration supplémentaire. Pour servir un dashboard
en français, ajoutez `--lang fr` aux commandes `cartouche` du workflow.

## API Python

```python
from cartouche import lang
from cartouche.render import repo
from cartouche.themes import get_theme

# Charger un pack de langue (avec overlay optionnel)
fr = lang.load("fr", overlay_path="my-overrides.json")  # overlay optional

# Charger des données (mock ou via fetch.repo_data())
from cartouche.mock import mock_repo
data = mock_repo("Sandjab", "Athanor", lang=fr)

# Rendre le SVG
svg = repo.render(data, theme=get_theme("vellum-light"), lang=fr)
```

## Architecture

```
src/cartouche/
├── themes.py            # registre des 16 thèmes (dict-of-dicts)
├── lang/
│   ├── __init__.py      # load(), list_builtin(), t(), tmpl()
│   ├── en.json          # langue par défaut
│   └── fr.json          # français
├── fetch.py             # wrappers GitHub REST + GraphQL, stdlib only
├── mock.py              # fixtures pour développement sans API
├── cli.py               # entry point argparse
└── render/
    ├── primitives.py    # cadre, grille, cartouche, axes, radar, texte
    ├── repo.py          # composeur du dashboard repo
    └── profile.py       # composeur du dashboard profil
```

Le moteur de rendu est *token-agnostic* (les couleurs viennent de `themes`)
et *literal-free* (les chaînes viennent de `lang`). Ajouter un septième
thème = ajouter ~12 lignes dans `THEMES`. Ajouter une langue = déposer un
JSON dans `lang/`. Voir [CLAUDE.md](CLAUDE.md) pour le détail des invariants
architecturaux.

## Données affichées

### Dashboard repo

- **FIG. 01** — Star history avec annotations de pic et endpoint marker
- **FIG. 02** — Radar 6 axes : stars, forks, commits, code, tests, docs
- **FIG. 03** — Cartes : stargazers, forks, issues, commits/30j + barre de
  langages

### Dashboard profil

- **FIG. 01** — Étoiles cumulées sur tous les repos publics du compte
- **FIG. 02** — Top 5 repos par stars, avec langage et commits/30j (les
  noms trop longs sont tronqués par `…` pour ne pas toucher les barres)
- **FIG. 03** — Radar profil 6 axes : reach, activity, breadth, depth,
  polyglot, engagement
- **FIG. 04** — Heatmap de contributions sur 53 semaines glissantes (via
  GraphQL — nécessite un token)
- **FIG. 05** — Indicateurs : total stars, total forks, commits/12 mois,
  ancienneté

Les deux dashboards portent une discrète signature `Proudly Clauded by
@<handle>` juste sous le cadre, en bas à droite. Le handle vient des
données, donc chaque utilisateur de la lib obtient automatiquement son
propre crédit. Pour l'enlever ou la reformuler, surchargez le template
`proudly_clauded` via `--lang-file`.

## Limitations connues

- Le dashboard profil interroge `/repos/.../stargazers` pour chaque repo
  public ; pour un compte avec beaucoup de repos très étoilés, l'opération
  peut prendre une minute. Une couche de cache incrémentale est prévue.
- Pas de support des dépôts forks dans les agrégats profil (filtrés). Le
  dashboard d'un fork individuel fonctionne normalement.
- Les polices web ne sont pas embarquées — GitHub les strippe au rendu des
  SVG dans les README. Le fallback est une stack monospace système.
- Les deux annotations auto-détectées (premier ★, plus gros pic) sont
  *remplacées* si vous passez `--annotations-file` ; pas de moyen
  d'*augmenter* la paire auto-détectée sans la lister manuellement dans
  votre overlay.

## Développement

```bash
git clone https://github.com/Sandjab/cartouche
cd cartouche
pip install -e ".[dev]"
pytest                                                 # 55 tests, ~0.2s
python -m cartouche repo Sandjab/Athanor --mock        # smoke test sans API
python -m cartouche profile Sandjab --mock --lang fr   # version FR
```

Pour Claude Code CLI : voir [CLAUDE.md](CLAUDE.md) pour l'architecture, les
invariants, et les tâches courantes.

## Licence

MIT — voir [LICENSE](LICENSE).
