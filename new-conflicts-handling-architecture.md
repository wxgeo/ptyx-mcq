# Notes sur une nouvelle architecture potentielle de gestion des conflits



## Objectif

Garder l'accès à tous les conflits même *après* le scan.
Cela permet de relancer la résolution des conflits pour un ou plusieurs documents seulement.

## Nouvelle structure proposée
- Nouvelle commande `mcq fix doc <doc> <page>` ou `mcq fix doc <doc>` ou encore `mcq fix name <student-name-or-id>`.
  Cette nouvelle commande permet de déclencher une résolution de conflits manuelle pour la ou les pages en question.
- Génération d'un fichier `patchs/<doc-id>.scandata`.
  Un fichier du dossier `patch` a donc le même format qu'un fichier `.scandata` du dossier `data/`.
- Le dossier `data` est subdivisée en 3 sous-répertoires :
  * `data/auto` : data récupérées automatiquement
  * `data/conflicts` : un fichier récapitulant les conflits rencontrés.
  * `data/patchs` : data modifiées manuellement (via le processus de résolution des conflits)

On peut rajouter quelques outil en ligne de commande:
- un outil permettant de générer un rapport (à l'attention de l'utilisateur) résumant les conflits détectés.
  `mcq issues list` par exemple.
- un outil permettant de lancer une résolution manuelle des conflits:
  `mcq issues fix`

## Nouvel algorithme
On peut scinder en deux la phase de scan :
- extraction des infos brutes de chaque document : ID document, localisation dans la matrice des cases à cocher (ID étudiant et réponses).
- analyse des informations. Cela permet d'effectuer une analyse globale des documents, et non page par page, ce qui peut
  améliorer l'algo de détection des réponses.
  
Ensuite, on conserve la phase de résolution des conflits.

## Remarques :
- À partir d'un fichier `patchs/<doc-id>.scandata`, on peut retrouver toutes les actions correctives effectuées sur le document.
  * Les données de chaque page correspond à une action corrective.
  * La première page contient également le nom et l'identifiant de l'étudiant.
  Ainsi, s'il y a 2 pages, un fichier contient potentiellement 3 actions correctives.
- On peut aussi éditer manuellement des informations d'un fichier `patchs/<doc-id>.scandata`, pour modifier les données récupérées automatiquement.
- DONE: Il faut renommer `mcq fix` en `mcq update config-file` (plus explicite) et `mcq update` en `mcq update imports`.

## Autres actions envisagées
- Supprimer les données en double : actuellement, le nom et l'ID de l'étudiant sont à la fois stockées dans la 1re page
  et dans une clé à part des data du document.

## Et l'intégrité ?
Faut-il modifier la résolution des conflits d'intégrité (page présente en double avec des données différentes) ?

Une solution pourrait-être de générer des fichiers `<doc-id>-<N>.conflict` dans le dossier `data/` en cas de doublon.
Ensuite, pour consolider les données, lors de la résolution des conflits, 
on génère des fichiers `<doc-id>.merge` dans le dossier `patchs/`, indiquant quel(s) fichier(s) `.conflict` on prend en compte
(éventuellement aucun).
Exemple de contenu de fichier: 
si `5.merge` contient`1,3,4`, cela indique de prendre en compte les fichiers `5-1.conflict`, `5-3.conflict` et `5-4.conflict`.



