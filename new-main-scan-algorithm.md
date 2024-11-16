# Nouvel algorithm de scan

## Objectif
Garder l'accès à tous les conflits même *après* le scan.
Cela permet de relancer la résolution des conflits pour un ou plusieurs documents seulement.

## Étapes
### Récupération des images
Extraction de toutes les images des PDF dans un dossier `pic`.
On génère dans `pic` un sous-dossier par PDF.
Le nom du sous-dossier est un hash du contenu du PDF.

Avant d'extraire le contenu du PDF, on vérifie si un dossier `pic/<hash-pdf>` existe déjà.
- S'il n'existe pas, on le crée. Il servira à y stocker les images après traitement.
- Si le contenu est incorrect (moins d'images que de pages dans le pdf), on extrait uniquement les images manquantes 
  (l'extraction avait probablement été interrompue).

Chaque image extraite est :
- normalisée (convertie en niveaux de gris, avec un contraste augmenté).
- pivotée, après avoir détecté les 4 carrés de référence marquant les coins de la page.

Un fichier `<pdf-hash>/<pdf-page>.pic-calibration` est généré, contenant :
- la résolution horizontale (px/mm)
- la résolution verticale (px/mm)
- la position des 4 coins (px)
- la position de la bande d'identification du document (px)

L'image rectifiée est stockée dans un fichier `<pdf-hash>/<pdf-page>.webp` (l'image originale extraite - généralement du `.jpeg`-  n'est pas conservée). 

Si une page ne semble pas correspondre à une page de QCM (page vierge par exemple), on génère un fichier `<pdf-hash>/<pdf-page>.skip` pour indiquer qu'il ne s'agit pas d'une page manquante.

On doit aussi supprimer les anciens dossiers correspondant aux pdf supprimés, **ainsi que toutes les données associées** !
Tous les dossiers `pics/<pdf-hash>` dont le hash ne correspond à plus aucun dossier sont ainsi supprimés.


### Récupération des données des images
Pour chaque image, on génère (dans le même dossier `pic`) un fichier `<pdf-hash>/<num-image>.pic-data`.
Celui-ci contient toutes les infos brutes de l'image :
- Le numéro du document
- La localisation (en pixels) dans l'image de toutes les cases à cocher :
  * la position du bloc d'identification (nom/identifiant de l'étudiant)
  * les cases correspondant aux réponses ((q, a) -> (ligne, colonne))

### Consolidation des données.
Création de fichiers `.pic-index` dans un dossier `index` associant à chaque identifiant de document et chaque page la ou les images correspondantes.
(S'il y a plusieurs images associées au même document, il y a un conflit potentiel.)

Exemple : fichier `<num-document>.index`, contenant 1 ligne par page.
```
<pdf-hash>/1,<other-pdf-hash>/34,<pdf-hash>/12
<pdf-hash>/14
```

### Analyse automatique des checkboxes
À partir des données de l'image, on détecte si chaque case semble cochée ou non. 
L'analyse se fait globalement sur tout le document, et non page par page, ce qui augmente sa précision.
On récupère également ainsi le nom de l'étudiant et son identifiant.
On génère ainsi pour chaque image un fichier `<pdf-hash>/<num-image>.pic-review`.

Celui-ci contient :
- le cas échéant (page 1), l'identifiant de l'étudiant
- le cas échéant (page 1), le nom de l'étudiant
- le statut de chaque case (`UNCHECKED`, `CHECKED`, `PROBABLY_UNCHECKED`, `PROBABLY_CHECKED`)

### Détection des conflits
Génération de la liste des conflits :
- conflits d'intégrité (plusieurs images pour la même page)
- conflits de nom/identifiant (nom/identifiant incorrect, identifiants apparaissant plusieurs fois)
- cases au statut ambigu (`PROBABLY_UNCHECKED`, `PROBABLY_CHECKED`)

### Résolution automatique des conflits d'intégrité si possible
Si deux images contiennent les mêmes données (même fichier `<pdf-hash>/<num-image>.pic-review`), on n'en garde qu'une seule.

### Résolution manuelle des conflits
Dossier `fix`.
- conflits d'intégrité :
  Résolution sauvegardée dans un fichier `index.fix` contenant des lignes au format :
  `<num-document>-<page>:<pdf-hash>/<num-image>`
- conflits de nom/identifiant.
  Résolutions sauvegardée dans un fichier `<num-document>.fix-doc` contenant 2 lignes :
  ```
  <identifiant>
  <nom>
  ```
- cases au statut ambigu.
  Résolutions sauvegardée dans un fichier `<num-document>-<page>.fix-page` contenant la liste des corrections :
  ```
  (q, a): UNCHECKED, ...
  ```

### Calcul des scores

### Génération des corrigés personnalisés
On génère un pdf corrigé pour chaque document trouvé.

## Accès à l'historique de résolution des conflits
À partir des fichiers du dossier `fix`, on peut reconstruire toutes les résolutions de conflits,
et éventuellement les annuler/modifier.

### CLI
On peut rajouter quelques outil en ligne de commande à cet effet :
- un outil permettant de générer un rapport (à l'attention de l'utilisateur) résumant les conflits détectés.
  `mcq issues list` par exemple.
- un outil permettant de lancer une résolution manuelle des conflits:
  `mcq issues fix` 
- Nouvelle commande `mcq fix doc <doc> <page>` ou `mcq fix doc <doc>` ou encore `mcq fix name <student-name-or-id>`.
  Cette nouvelle commande permet de déclencher une résolution de conflits manuelle pour la ou les pages en question,
  même dans le cas où il n'y avait pas à priori de conflit.

