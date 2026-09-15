# ETL météo

Ce projet collecte les villes marocaines et leurs prévisions météorologiques, puis conserve les réponses brutes dans la couche Bronze.

## Prérequis

- Python récent
- Les dépendances décrites dans `requirements.txt`

## Exécution

Installez les dépendances puis lancez le script d'extraction :

```powershell
python -m pip install -r requirements.txt
python Scripts/extract.py
```

Les fichiers source sont enregistrés dans `bronze` et les traces d'exécution dans `logs`. Ces répertoires sont volontairement exclus du suivi Git.

Les paramètres réseau peuvent être adaptés dans le script selon le contexte d'exécution.
