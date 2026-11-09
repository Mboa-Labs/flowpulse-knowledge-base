# Base de connaissances réglementaire — FlowPulse

La base de connaissances (KB) contient les textes officiels que l'agent Politique consulte avant de valider une recommandation. Chaque réponse de l'agent cite le document et l'article sur lesquels elle s'appuie. Le pipeline reprend celui du dépôt ITU [ITUAIReadiness](https://github.com/CrashingGuru/ITUAIReadiness) (`simulation/server/knowledge/ingest.py`).

## Structure

```
flowpulse-knowledge-base/
├── sources.csv                    Inventaire : une ligne par document (source de vérité des métadonnées)
├── schema_metadonnees.json        Champs attachés à chaque passage dans ChromaDB
├── InputDocs/                     Les fichiers eux-mêmes (PDF, txt, md, html)
│   ├── Cameroun/
│   │   ├── 01_Donnees_personnelles/
│   │   ├── 02_Communications_electroniques/
│   │   ├── 03_Cybersecurite/
│   │   ├── 04_Decentralisation/
│   │   ├── 05_Transport_urbain/
│   │   └── 06_Strategies_nationales/
│   ├── ITU/                       Y.3172, AI Readiness Framework 2.0
│   └── International/             Exemples de comparaison (UA, UE, Rwanda, EAU…)
├── registres/
│   └── manques_reglementaires.csv Manques détectés (catégories du jury ITU)
├── scripts/
│   ├── verifier_sources.py        Contrôle sources.csv ↔ fichiers
│   └── ingest.py                  Découpage + vecteurs + ChromaDB
└── chroma/                        Base vectorielle générée (non versionnée)
```

## Ajouter un document (procédure pour l'équipe)

1. **Trouver la version officielle** : Journal officiel, site du ministère, de l'ART, de la Communauté Urbaine, de l'ITU. Pas de résumé de blog.
2. **Déposer le fichier** dans le bon sous-dossier, avec un nom court sans espaces ni accents : `loi_2010_013_communications_electroniques.pdf`. Un `.docx` doit être converti en PDF.
3. **Compléter sa ligne dans `sources.csv`** : `fichier`, `reference` exacte, `autorite`, `date_adoption`, `url_source`. Remplacer chaque « à vérifier ».
4. **Changer le statut** : `a_collecter` → `collecte` (fichier déposé) → `verifie` (métadonnées contrôlées par une deuxième personne). Seuls les documents `verifie` sont ingérés. Le statut `exclu` garde un document dans l'inventaire sans jamais l'indexer (doublon ou hors sujet, avec la raison dans `notes`).
5. **Contrôler** : `python scripts/verifier_sources.py`
6. **Ingérer** : `python scripts/ingest.py --dry-run` pour voir le découpage, puis sans `--dry-run`. Le statut passe ensuite à `indexe`.

Un document absent de `sources.csv` est signalé par le script de vérification. Un document qui n'existe pas (par exemple une stratégie IA nationale non publiée) reste dans `sources.csv` avec une note : son absence est elle-même un manque réglementaire à enregistrer.

## Découpage et vecteurs

| Paramètre | Valeur | Origine |
| --- | --- | --- |
| Extraction PDF | PyMuPDF | dépôt ITU |
| Découpage juridique | par article (`Article 1er`, `Art. 12`…) puis par passages | FlowPulse |
| Taille d'un passage | 256 mots, recouvrement 30 mots, 2 000 caractères maximum | dépôt ITU |
| Modèle de vecteurs | `nomic-embed-text` via Ollama | dépôt ITU |
| Stockage | ChromaDB persistant, distance cosinus | dépôt ITU |

Collections :

| Collection | Contenu |
| --- | --- |
| `kb_reglementaire` | `InputDocs/Cameroun/` et `InputDocs/International/` |
| `kb_framework` | `InputDocs/ITU/` |
| `kb_manques` | `registres/manques_reglementaires.csv` |

## Registre des manques

Chaque ligne de `registres/manques_reglementaires.csv` porte une catégorie du jury : `RESPONSABILITE_FLOUE`, `NORME_ABSENTE`, `VIDE_JURIDIQUE`, `COORDINATION`, `OBJECTIFS_CONTRADICTOIRES`. L'équipe y note les manques repérés en lisant les textes ; l'agent Politique y ajoute ceux qu'il détecte en fonctionnement (verdict « aucun texte applicable »), visibles dans l'écran « Manques réglementaires ».

Le registre compte 7 manques identifiés par lecture des textes. Chacun indique les textes examinés (avec article ou page) et un exemple de politique d'un autre pays ou d'une organisation régionale :

| Id | Catégorie | Manque |
| --- | --- | --- |
| GAP-001 | Responsabilité floue | Qui autorise un opérateur télécom à fournir des données de mobilité agrégées à une collectivité |
| GAP-002 | Norme absente | Aucune norme nationale d'anonymisation des données de téléphonie mobile |
| GAP-003 | Responsabilité floue | Suivi de la performance de la mobilité urbaine non attribué ; observatoire sans mandat de collecte |
| GAP-004 | Coordination | Aucun mécanisme réunissant Communauté Urbaine, exploitant de bus et police pour un renfort en temps réel |
| GAP-005 | Norme absente | Aucun format ouvert imposé pour les données de l'offre de transport (lignes, arrêts, horaires) |
| GAP-006 | Vide juridique | Aucun cadre pour l'aide à la décision par l'IA dans un service public (contrôle humain, traçabilité) |
| GAP-007 | Objectifs contradictoires | Stratégies favorables aux données face à une mise en conformité sans doctrine sur les données agrégées |

Ces manques sont une lecture d'ingénieurs, pas un avis juridique : ils sont à confirmer par un juriste (statut `identifie_par_lecture`).

## Installation

```bash
pip install chromadb ollama pymupdf
ollama pull nomic-embed-text
```

## État de la base (9 novembre 2026)

| | Nombre |
| --- | --- |
| Textes inventoriés dans `sources.csv` | 21 (13 collectés, 7 à collecter, 1 exclu) |
| Textes indexés | 10 |
| Passages de textes nationaux et internationaux (`kb_reglementaire`) | 601 |
| Passages du cadre ITU (`kb_framework` : Y.3172, AI Readiness Framework 2.0) | 135 |
| Manques documentés (`kb_manques`) | 7 |

Chaque référence de `sources.csv` renvoie à sa source (site officiel quand il existe, sinon copie identifiée comme non officielle dans `notes`).

**Limites connues.**

- La loi n° 2024/017 sur les données personnelles et le Code général des CTD (loi n° 2019/024) sont des PDF scannés : sans reconnaissance de caractères (OCR), leur texte n'est pas encore exploitable par l'agent. Ce sont les deux priorités de la prochaine ingestion.
- Les textes non publiés en ligne (contrat d'exploitation des bus, Plan de Déplacements Urbains de Yaoundé, texte intégral de la Stratégie nationale de l'IA) restent dans l'inventaire au statut `a_collecter` : leur absence est elle-même relevée dans le registre des manques.
- Le recueil ART 2023 est exclu de l'indexation (464 pages de textes d'application des télécoms, sans rapport avec la mobilité) : il aurait représenté 77 % des passages et masqué les autres textes.

## Droits sur les documents

Les lois et décrets sont des textes officiels publics. Les autres documents restent la propriété de leurs auteurs (ITU, Union africaine, MobiliseYourCity pour la PNMU, MINICT Rwanda) : ils sont repris ici à des fins de recherche et de démonstration, avec leur source dans `sources.csv`. La SND30, dont la reproduction exige l'accord écrit du MINEPAT, n'est pas versionnée (`.gitignore`) : `sources.csv` donne son lien de téléchargement.
