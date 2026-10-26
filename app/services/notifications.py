"""
Service de notification des usagers.

Deux canaux :
- le COURRIEL, réellement envoyé si l'usager a donné une adresse avec sa déclaration et si un serveur
  de courrier est configuré (voir services/courriel.py) ;
- le SMS, pas encore branché : il reste simulé (écrit dans les journaux). Quand un fournisseur de SMS
  sera choisi, seul ce fichier sera modifié ; le reste du code n'aura pas à changer.

Aucun message ne contient le détail caché, la photo ni la description précise d'un objet : un courriel
peut être lu par quelqu'un d'autre. Il indique seulement la catégorie et ce qu'il faut faire à l'accueil.
"""

import logging

from app.models.objet import Objet
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager
from app.services.courriel import envoyer_courriel

logger = logging.getLogger("objets_trouves.notifications")


def _nom_organisation(signalement: SignalementPerte) -> str:
    return signalement.organisation.nom if signalement.organisation else ""


def _salutation(usager: Usager) -> str:
    return f"Bonjour {usager.nom}," if usager and usager.nom else "Bonjour,"


def notifier_correspondance(usager: Usager, signalement: SignalementPerte, objet: Objet) -> str:
    """Prévient l'usager qu'un objet pouvant être le sien a été trouvé."""
    message = (
        f"Bonjour, un objet correspondant à votre signalement "
        f"({signalement.categorie}) a été enregistré. "
        f"Présentez-vous au service des objets trouvés avec une pièce d'identité."
    )
    logger.info("NOTIFICATION SMS (simulée) vers %s : %s [objet %s]", usager.telephone, message, objet.qr_code)

    organisation = _nom_organisation(signalement)
    reference = str(signalement.id).replace("-", "")[:8].upper()
    envoyer_courriel(
        signalement.email,
        f"Un objet pourrait être le vôtre — {organisation}".strip(" —"),
        [
            _salutation(usager),
            f"Un objet de la catégorie « {signalement.categorie} » a été enregistré et pourrait correspondre à votre déclaration.",
            "Présentez-vous au service des objets trouvés avec une pièce d'identité et la référence ci-dessous. "
            "On vous demandera de décrire l'objet pour vérifier qu'il est bien à vous.",
            f"Référence : {reference}",
        ],
        organisation,
    )
    return message


def notifier_declaration_enregistree(usager: Usager, signalement: SignalementPerte) -> None:
    """Courriel de confirmation : « votre déclaration est bien enregistrée »."""
    organisation = _nom_organisation(signalement)
    reference = str(signalement.id).replace("-", "")[:8].upper()
    envoyer_courriel(
        signalement.email,
        f"Votre déclaration est enregistrée — {organisation}".strip(" —"),
        [
            _salutation(usager),
            f"Nous avons bien enregistré votre déclaration de perte ({signalement.categorie}).",
            "Dès qu'un objet correspondant sera trouvé, nous vous préviendrons à cette adresse et par téléphone.",
            f"Référence à donner à l'accueil : {reference}",
        ],
        organisation,
    )
