"""
Liste des catégories d'objets proposées aux usagers (portail public) et, plus tard,
aux agents (formulaire d'enregistrement).

Pourquoi une liste fixe ? Le rapprochement automatique compare la catégorie déclarée
par l'usager à celle saisie par l'agent (voir services/rapprochement.py). Si chacun
écrivait librement « portable », « téléphone » ou « GSM », ils ne se retrouveraient
jamais. En proposant les mêmes mots des deux côtés, la correspondance devient fiable.

La catégorie reste un simple texte en base : cette liste est une aide à la saisie,
pas une contrainte. Les objets déjà enregistrés avec une autre catégorie continuent
de fonctionner.
"""

CATEGORIES: list[str] = [
    "Téléphone",
    "Portefeuille",
    "Clés",
    "Sac",
    "Documents",
    "Carte bancaire",
    "Vêtement",
    "Lunettes",
    "Ordinateur",
    "Écouteurs",
    "Montre",
    "Bijou",
    "Livre ou cahier",
    "Autre",
]
