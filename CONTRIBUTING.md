# Guide de contribution

[[_TOC_]]

## Gestion des branches

Les branches sont divisés en 3 catégories :

- Branches de suivi des environnements ( master , staging et production)

- Branches pour l'implémentation des nouvelles évolutions

- Branches pour la correction d'anomalies


### Branches d'environnements

Chaque branche correspond à un environnement :

- `master`
  - Branche de développement, à partir duquel sont créés les branches d'évolutions
  - Reçoit le code des évolutions et correctifs
  
- `staging`
  - Code de l'environnement d'intégration
  - Reçoit le code validé dans `master`
- `production`
  - Code de l'environnement de production
  - Reçoit le code validé dans `staging`


### Branches d'évolutions & de corrections

Chaque branche correspond à l'implémentation d'une évolution ou une correction

- Nomenclature : `[ID]-[Description courte]` où
    - `ID` corresspond au numéro de ticket de l'évolution dans `JIRA`
    - La `Description courte` ne doit pas dépasser les 5 mots
- Source : `master` : `git checkout -b [ID]-[Description courte] master`
- Chaque branche doit faire l'objet d'une PR