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

# Catégories communes à tous les secteurs (« Autre » est toujours placée en dernier).
CATEGORIES_COMMUNES: list[str] = [
    "Téléphone",
    "Portefeuille",
    "Clés",
    "Sac",
    "Documents",
    "Carte bancaire",
    "Vêtement",
    "Lunettes",
    "Ordinateur",
    "Écouteurs ou baladeur",
    "Montre",
    "Bijou",
    "Livre ou cahier",
    "Tapis de prière",
    "Casquette",
    "Bonnet",
    "Chapelet",
    "Gourde",
    "Sachet",
    "Carte scolaire",
    "Carte d'identité",
    "Passeport",
    "Clé USB",
    "Disque dur",
    "Chargeur",
    "Argent",
    "Pochette",
    "Bracelet",
    "Enveloppe",
    "Thermos",
    "Chaussures",
    "Permis de conduire",
    "Hijab ou voile",
    "Carte professionnelle",
    "Chaussettes",
    "Produits médicaux",
    "Produits cosmétiques",
    "Produits alimentaires",
    "Produits d'hygiène",
    "Produits ménagers",
    "Ustensiles de cuisine",
    "Parfums",
    "Amplificateur sonore",
    "Boissons",
    "Papiers de voiture ou moto",
    "Kit de maquillage",
    "Casque de moto",
    "Carte de crédit",
    "Batterie",
    "Objets électroniques",
    "Pièces mécaniques",
    "Outils de chantier",
    "Carte SIM",
    "Multiprise ou rallonge",
    "Masque ou niqab",
    "Coran",
    "Ceinture",
    "Clavier",
    "Souris",
    "Outils informatiques",
    "Mémoire RAM ou SD",
    "Tenue de sport",
    "Matériel électrique",
    "Kit ou objet pour bébé",
    "Pièces de téléphone ou d'appareils",
    "Bazin ou tissu",
    "Outils de réparation",
]

# Catégories propres à un secteur : insérées avant « Autre ».
CATEGORIES_PAR_SECTEUR: dict[str, list[str]] = {
    "education": [
        "Tenue scolaire",
        "Ensemble géométrique",
        "Bic",
        "Calculatrice",
        "Kit de maintenance ou de robotique",
        "Reçu de paiement ou quittance",
        "Copie de devoir ou d'examen",
        "Relevé de notes ou bulletin",
    ],
    "transport": ["Billet de voyage", "Matériel de plomberie", "Matériel de soudure"],
}


def categories_pour(secteur: str | None) -> list[str]:
    """Liste des catégories d'un secteur (éducation par défaut)."""
    propres = CATEGORIES_PAR_SECTEUR.get((secteur or "").strip().lower(), CATEGORIES_PAR_SECTEUR["education"])
    return [*CATEGORIES_COMMUNES, *propres, "Autre"]


# Liste par défaut (route /portail/categories, sans organisation précisée).
CATEGORIES: list[str] = categories_pour("education")
