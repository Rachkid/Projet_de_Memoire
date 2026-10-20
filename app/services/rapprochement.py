"""
Rapprochement automatique entre objets trouvés et signalements de perte
(cahier des charges, section 5.1.3).

Règle de correspondance (volontairement simple et explicable) : un objet et
un signalement correspondent si
  1. ils appartiennent à la même organisation ;
  2. leur catégorie est identique, sans tenir compte des majuscules ni des
     accents ("Téléphone" == "telephone") ;
  3. l'objet n'est pas déjà restitué ou archivé (il doit être "en_attente") ;
  4. si le signalement indique une date de perte, l'objet a été trouvé à
     moins de FENETRE_JOURS jours de cette date (la mémoire des gens est
     approximative, on reste donc tolérant).
"""

import unicodedata
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.enums import StatutObjet, StatutSignalement
from app.models.objet import Objet
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager
from app.services.notifications import notifier_correspondance

FENETRE_JOURS = 7


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans espaces superflus."""
    decompose = unicodedata.normalize("NFD", texte.strip().lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def correspond(signalement: SignalementPerte, objet: Objet) -> bool:
    """Applique les règles 1 à 4 à un couple (signalement, objet)."""
    if signalement.organisation_id != objet.organisation_id:
        return False
    if normaliser(signalement.categorie) != normaliser(objet.categorie):
        return False
    if objet.statut != StatutObjet.EN_ATTENTE.value:
        return False
    if signalement.date_perte is not None:
        ecart = objet.date_heure_decouverte.date() - signalement.date_perte
        if abs(ecart) > timedelta(days=FENETRE_JOURS):
            return False
    return True


def objets_correspondants(db: Session, signalement: SignalementPerte) -> list[Objet]:
    """Tous les objets en attente de la même organisation qui correspondent."""
    candidats = (
        db.query(Objet)
        .filter(
            Objet.organisation_id == signalement.organisation_id,
            Objet.statut == StatutObjet.EN_ATTENTE.value,
        )
        .order_by(Objet.date_heure_decouverte.desc())
        .all()
    )
    return [o for o in candidats if correspond(signalement, o)]


def signalements_correspondants(db: Session, objet: Objet) -> list[SignalementPerte]:
    """
    Sens inverse de objets_correspondants : les déclarations de perte encore ouvertes de la même
    organisation qui correspondent à cet objet. Sert à l'agent qui remet l'objet : il voit qui
    l'attend (nom, téléphone) au lieu de chercher dans toute la liste.
    """
    ouverts = (
        db.query(SignalementPerte)
        .filter(
            SignalementPerte.organisation_id == objet.organisation_id,
            SignalementPerte.statut != StatutSignalement.CLOTURE.value,
        )
        .all()
    )
    return [s for s in ouverts if correspond(s, objet)]


def traiter_nouveau_signalement(db: Session, signalement: SignalementPerte) -> list[Objet]:
    """À appeler après création d'un signalement : cherche, marque, notifie."""
    trouves = objets_correspondants(db, signalement)
    if trouves:
        signalement.statut = StatutSignalement.CORRESPONDANCE_TROUVEE.value
        db.commit()
        usager = db.get(Usager, signalement.usager_id)
        notifier_correspondance(usager, signalement, trouves[0])
    return trouves


def traiter_nouvel_objet(db: Session, objet: Objet) -> int:
    """
    À appeler après enregistrement d'un objet : cherche les signalements en
    attente qui lui correspondent, les marque et notifie leurs auteurs.
    Renvoie le nombre de signalements concernés.
    """
    en_attente = (
        db.query(SignalementPerte)
        .filter(
            SignalementPerte.organisation_id == objet.organisation_id,
            SignalementPerte.statut == StatutSignalement.EN_ATTENTE.value,
        )
        .all()
    )
    concernes = [s for s in en_attente if correspond(s, objet)]
    for s in concernes:
        s.statut = StatutSignalement.CORRESPONDANCE_TROUVEE.value
    if concernes:
        db.commit()
        for s in concernes:
            notifier_correspondance(db.get(Usager, s.usager_id), s, objet)
    return len(concernes)
