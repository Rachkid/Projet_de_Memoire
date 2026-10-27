"""
Normalisation des numéros de téléphone (étape 16).

Le portail et l'interface agent normalisent déjà le numéro dans la page, mais une page n'est qu'un confort :
un appel direct à l'API pourrait envoyer n'importe quoi. Le serveur applique donc la même règle.

Règles (les mêmes que dans portail.js) :
  - on ignore espaces, points, tirets et parenthèses ;
  - « 00… » devient « +… » ;
  - un numéro commençant par « + » doit avoir 8 à 15 chiffres ensuite (numéro étranger) ;
  - 8 chiffres : numéro du Niger, on ajoute « +227 » ;
  - « 227 » suivi de 8 chiffres : on ajoute le « + ».
Tout le reste est refusé.

Ce module ne dépend ni de FastAPI ni de la base de données.
"""

import re


def normaliser_telephone(brut: str) -> str | None:
    """Renvoie le numéro au format « +227XXXXXXXX » (ou international), ou None s'il n'est pas valable."""
    if not isinstance(brut, str):
        return None
    texte = re.sub(r"[\s.\-()]", "", brut)
    if texte.startswith("00"):
        texte = "+" + texte[2:]
    if texte.startswith("+"):
        return texte if re.fullmatch(r"\+\d{8,15}", texte) else None
    if re.fullmatch(r"\d{8}", texte):
        return "+227" + texte
    if re.fullmatch(r"227\d{8}", texte):
        return "+" + texte
    return None
