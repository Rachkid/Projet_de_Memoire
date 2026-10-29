"""
Envoi de courriels (étape 15).

Deux règles gouvernent ce fichier :

1. L'envoi ne doit JAMAIS faire attendre ni échouer la requête de l'utilisateur. Le courriel
   part donc dans un petit fil d'exécution séparé (thread) : la réponse revient tout de suite,
   même si le serveur de courrier est lent ou en panne.
2. Une panne d'envoi n'est jamais une erreur pour l'utilisateur : elle est seulement écrite dans
   les journaux. La notification par courriel est un confort ; la déclaration, elle, est déjà
   enregistrée et visible par le personnel.

Si SMTP_HOST est vide, aucun courriel n'est envoyé (le message est seulement journalisé) :
l'application fonctionne donc sans serveur de courrier.
"""

import html
import logging
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from app.config import settings

logger = logging.getLogger("objets_trouves.courriel")

DELAI_SMTP_SECONDES = 10  # au-delà, on abandonne : le fil se termine, rien d'autre n'est touché


def courriel_configure() -> bool:
    return bool(settings.smtp_host.strip())


def construire_message(destinataire: str, sujet: str, paragraphes: list[str], organisation_nom: str) -> EmailMessage:
    """
    Construit un courriel en deux versions (texte simple et page HTML légère) : le logiciel de
    messagerie affiche celle qu'il préfère. Tout texte inséré dans le HTML est « échappé » pour
    qu'un nom ou une catégorie ne puisse pas y glisser du code.
    """
    nom_expediteur, adresse_expediteur = parseaddr(settings.courriel_expediteur)
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = formataddr((organisation_nom or nom_expediteur, adresse_expediteur))
    message["To"] = destinataire
    message.set_content("\n\n".join(paragraphes) + f"\n\n{organisation_nom}\n(Message automatique, merci de ne pas y répondre.)")
    corps = "".join(f"<p style=\"margin:0 0 14px\">{html.escape(p)}</p>" for p in paragraphes)
    message.add_alternative(
        f"<div style=\"font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#1b2430;max-width:560px\">"
        f"{corps}<p style=\"margin:22px 0 0;color:#5b6674;font-size:14px\">{html.escape(organisation_nom)}<br>"
        f"Message automatique, merci de ne pas y répondre.</p></div>",
        subtype="html",
    )
    return message


def _envoyer_maintenant(message: EmailMessage) -> None:
    """Envoie réellement le message. Tout échec est journalisé, jamais propagé."""
    try:
        if settings.smtp_ssl:
            connexion = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=DELAI_SMTP_SECONDES)
        else:
            connexion = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=DELAI_SMTP_SECONDES)
        with connexion:
            if settings.smtp_starttls and not settings.smtp_ssl:
                connexion.starttls()
            if settings.smtp_utilisateur:
                connexion.login(settings.smtp_utilisateur, settings.smtp_mot_de_passe)
            connexion.send_message(message)
        logger.info("Courriel envoyé à %s (%s)", message["To"], message["Subject"])
    except Exception as erreur:  # noqa: BLE001 — volontaire : rien ne doit remonter jusqu'à l'utilisateur
        logger.warning("Échec d'envoi du courriel à %s : %s", message["To"], erreur)


def envoyer_courriel(destinataire: str | None, sujet: str, paragraphes: list[str], organisation_nom: str) -> bool:
    """
    Lance l'envoi en arrière-plan et rend la main aussitôt. Renvoie True si un envoi a été lancé
    (cela ne veut pas dire qu'il réussira : l'échec éventuel est dans les journaux).
    """
    if not destinataire:
        return False
    if not courriel_configure():
        logger.info("Courriel NON envoyé (SMTP_HOST vide) à %s : %s", destinataire, sujet)
        return False
    try:
        message = construire_message(destinataire, sujet, paragraphes, organisation_nom)
        threading.Thread(target=_envoyer_maintenant, args=(message,), daemon=True, name="courriel").start()
        return True
    except Exception as erreur:  # noqa: BLE001
        logger.warning("Courriel non préparé pour %s : %s", destinataire, erreur)
        return False
