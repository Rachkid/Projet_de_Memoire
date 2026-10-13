"""
Service de notification des usagers.

IMPORTANT : à cette étape, aucun SMS ni e-mail n'est réellement envoyé.
La fonction se contente d'écrire un message dans les journaux (logs) du
serveur. Elle isole volontairement l'envoi dans un seul endroit : quand le
projet branchera un vrai fournisseur (SMS, WhatsApp, e-mail), seul ce
fichier sera modifié ; le reste du code n'aura pas à changer.
"""

import logging

from app.models.objet import Objet
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager

logger = logging.getLogger("objets_trouves.notifications")


def notifier_correspondance(usager: Usager, signalement: SignalementPerte, objet: Objet) -> str:
    """Prévient l'usager qu'un objet pouvant être le sien a été trouvé."""
    message = (
        f"Bonjour, un objet correspondant à votre signalement "
        f"({signalement.categorie}) a été enregistré. "
        f"Présentez-vous au service des objets trouvés avec une pièce d'identité."
    )
    logger.info("NOTIFICATION (simulée) vers %s : %s [objet %s]", usager.telephone, message, objet.qr_code)
    return message
