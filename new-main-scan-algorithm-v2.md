# Nouvel algorithm de scan

## 1. Objectifs
- Garder l'accès à tous les conflits même *après* le scan.
  Cela permet de relancer la résolution des conflits pour un ou plusieurs documents seulement.
- Pouvoir afficher une synthèse de toutes les opérations effectuées, ou un log plus détaillé si besoin.

## 2. Étape 1 - Récupération et analyse des images scannées
### 2.1 Préliminaires
Extraction de toutes les images des PDF dans un dossier `.cache`.
On génère dans `.cache` un sous-dossier par PDF.
Le nom du sous-dossier est un hash du contenu du PDF.

Avant d'extraire le contenu du PDF, on vérifie si un dossier `.cache/<hash-pdf>` existe déjà.
- S'il n'existe pas, on le crée. Il servira à y stocker les images après traitement.
- Si le contenu est incorrect (moins d'images que de pages dans le pdf), on extrait uniquement les images manquantes 
  (l'extraction avait probablement été interrompue).

On doit aussi supprimer les anciens dossiers correspondant aux pdf supprimés, **ainsi que toutes les données associées** !
Tous les dossiers `.cache/<pdf-hash>` dont le hash ne correspond à plus aucun pdf sont ainsi supprimés.

### 2.2 Arborescence
Le dossier `<hash-pdf>` contiendra :
- toutes les pages du pdf après extraction et normalisation, sous forme d'image `.webp`.
- un sous-dossier `calibration`, contenant un fichier par image indiquant comment la calibration a été effectuée.
- un sous-dossier `identification`, contenant un fichier par image indiquant à quel document et quelle page du document original
  correspond l'image.
- un sous-dossier `checkboxes`, contenant un fichier par image indiquant les résultats de l'analyse de toutes les cases à cocher.
- un sous-dossier `students`, contenant un fichier pour chaque image correspondant à une 1re page, indiquant le nom et l'identifiant de l'étudiant. 
  
Exemple, pour un fichier pdf de hash `00d68ea2ab8af0932bee516ee60a79cdeb5fb1d0` et possédant 2 pages,
on aura généré à terme les dossiers et fichier suivants :
```
    .cache
    └── 00d68ea2ab8af0932bee516ee60a79cdeb5fb1d0
        ├── 0.webp
        ├── 1.webp
        ├── calibration
        │   ├── 0
        │   └── 1
        ├── identification
        │   ├── 0
        │   └── 1
        ├── checkboxes
        │   ├── 0
        │   └── 1
        └── students
            └── 0
```

### 2.3 Phase d'extraction des données
#### 2.3.1 Calibration des images
Chaque image extraite est :
- normalisée (convertie en niveaux de gris, avec un contraste augmenté).
- pivotée, après avoir détecté les 4 carrés de référence marquant les coins de la page.

Un fichier `.cache/<pdf-hash>/calibration/<num-page-scannée>` est généré, contenant :
- la résolution horizontale (px/mm)
- la résolution verticale (px/mm)
- la position des 4 coins (px)
- la position de la bande d'identification du document (px)

(En mémoire, ces données sont stockées dans un objet de classe `CalibrationData`). 

L'image rectifiée elle-même est alors stockée dans un fichier `.cache/<pdf-hash>/<pic-num>.webp`, pour éviter
de surcharger la mémoire. 
(Quant à l'image originale, c'est-à-dire avant rectification, elle n'est pas conservée). 

Si une page ne semble pas correspondre à une page de QCM (page vierge par exemple), 
on génère un fichier `.cache/<pdf-hash>/<pic-num>.skip` pour indiquer que la page a bien été traitée.

#### 2.3.2 Identification des images
Pour chaque image, on génère un fichier `.cache/<pdf-hash>/identification/<pic-num>`.
Celui-ci contient toutes les infos brutes de l'image :
- Le numéro du document
- Le numéro de page dans le document

(En mémoire, ces données sont stockées dans un objet de classe `IdentificationData`). 

#### 2.3.3 Indexation des images
Création de fichiers `.index/<doc-id>` associant à chaque identifiant de document 
et chaque page la ou les images correspondantes.
Remarque : il peut parfois arriver qu'il y ait plusieurs images associées au même document :
- soit qu'un document ait été scanné plusieurs fois (en partie ou en totalité), ce qui n'est pas bien grave.
- soit que plusieurs étudiants aient eu le même numéro de document, ce qui est beaucoup plus problématique.

Exemple de contenu de fichier : 
```
1: <pdf-hash>/1, <other-pdf-hash>/34, <pdf-hash>/12
2: <pdf-hash>/14
```
La 1re ligne du fichier liste les pages scannées correspondant à la 1re page du document,
la 2e ligne du fichier liste les pages scannées correspondant à la 2e page du document,
etc.

Idéalement, il ne devrait y avoir qu'une seule page scannée associée à chaque page du document,
sinon (voir remarque plus haut) c'est qu'il y a un conflit potentiel 
(il y aura effectivement conflit si le contenu diffère après analyse).

Ces fichiers ne sont pas utilisés ensuite, mais facilitent le débogage.

### 2.5 Analyse des données
#### 2.5.1 Récupération de la position des cases à cocher
On récupère la localisation (en pixels) dans l'image de toutes les cases à cocher :
  * la position du bloc d'identification (nom/identifiant de l'étudiant)
  * les cases correspondant aux réponses ((q, a) -> (ligne, colonne))

#### 2.5.2 Analyse automatique des checkboxes
À partir des données de l'image, on détecte si chaque case semble cochée ou non. 
L'interprétation se fait globalement sur l'ensemble des pages associées à un 
même document, et non page par page, ce qui augmente sa précision.
On génère ainsi pour image un fichier `<pdf-hash>/checkboxes/<pic-num>`.

Celui-ci contient le statut de chaque case (`UNCHECKED`, `CHECKED`, `PROBABLY_UNCHECKED`, `PROBABLY_CHECKED`).

Exemple de contenu de fichier :
```
[1]
1: UNCHECKED
2: CHECKED
3: PROBABLY_UNCHECKED

[2]
1: CHECKED
2: CHECKED
```

#### 2.5.3 Identification de l'étudiant
On récupère également le nom de l'étudiant via son identifiant.

On génère ainsi pour toutes les images correspondant à la 1re page d'un document un fichier `<pdf-hash>/students/<pic-num>`.

Celui-ci contient :
  1. le nom de l'étudiant
  2. l'identifiant de l'étudiant

Exemple de contenu de fichier :
```
William Shakespeare
5412241
```

### 2.6 Remarque

L'intérêt de générer un fichier par page scannée (et non par document ou par page du document initial) est de gérer 
plus facilement les conflits (pages scannées en double par exemple).

## 3. Détection des conflits
Génération de la liste des conflits :
- conflits d'intégrité (plusieurs images pour la même page)
- conflits de nom/identifiant (nom/identifiant incorrect, identifiants apparaissant plusieurs fois)
- cases au statut ambigu (`PROBABLY_UNCHECKED`, `PROBABLY_CHECKED`)

Les données de résolution de conflits sont sauvegardées dans le dossier `.fix`.

### Résolution automatique des conflits d'intégrité si possible
Si deux images contiennent les mêmes données (fichiers `<pdf-hash>/checkboxes/<num-page-scannée>` identiques,
et même étudiant s'il s'agit des 1res pages), on n'en garde qu'une seule.

### Résolution manuelle des conflits
- conflits d'intégrité (pages en double) :
  Pour chaque image non utilisée, on crée un fichier `.skip`.
  `.fix/<pdf-hash>/<num-page-scannée>.skip`
- conflits de nom/identifiant.
  Résolution sauvegardée dans un fichier `.fix/<pdf-hash>/student/<num-page-scannée>` contenant 2 lignes :
  ```
  <nom>
  <identifiant>
  ```
- cases au statut ambigu.
  Résolutions sauvegarde dans un fichier `.fix/<pdf-hash>/checkboxes/<num-page-scannée>` 
  contenant la liste des corrections :
  ```
  [5]
  2: UNCHECKED
  6: CHECKED
  
  [9]
  3: CHECKED
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

