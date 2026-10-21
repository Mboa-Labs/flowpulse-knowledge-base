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
4. **Changer le statut** : `a_collecter` → `collecte` (fichier déposé) → `verifie` (métadonnées contrôlées par une deuxième personne). Seuls les documents `verifie` sont ingérés.
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

Chaque ligne de `registres/manques_reglementaires.csv` porte une catégorie du jury : `RESPONSABILITE_FLOUE`, `NORME_ABSENTE`, `VIDE_JURIDIQUE`, `COORDINATION`, `OBJECTIFS_CONTRADICTOIRES`. L'équipe y note les manques repérés en lisant les textes ; l'agent Politique y ajoute ceux qu'il détecte en fonctionnement. Les deux lignes actuelles sont des hypothèses à confirmer après lecture des textes.

## Installation

```bash
pip install chromadb ollama pymupdf
ollama pull nomic-embed-text
```

## Attention

Les références de `sources.csv` (intitulés, numéros, dates) ont été pré-remplies de mémoire. Elles sont toutes marquées « à vérifier » ou « à identifier » et doivent être confirmées sur le texte officiel avant de passer au statut `verifie`.
