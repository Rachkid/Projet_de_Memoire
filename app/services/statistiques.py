"""
Calcul des chiffres du tableau de bord (Étape 14).

Principe : on ne renvoie JAMAIS d'objet ni de personne ici, uniquement des
totaux. Les calculs lourds (regroupement par jour) sont faits en Python sur
les 30 derniers jours seulement : le volume reste petit (quelques dizaines
d'objets par semaine), ce qui garde le code lisible et indépendant du moteur
de base de données.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import StatutObjet, StatutSignalement
from app.models.objet import Objet
from app.models.organisation import Organisation
from app.models.restitution import Restitution
from app.models.signalement_perte import SignalementPerte

# Le Niger est à UTC+1 toute l'année (pas d'heure d'été) : un décalage fixe suffit et
# évite de dépendre de la base des fuseaux horaires du système.
FUSEAU = timezone(timedelta(hours=1))
JOURS_SERIE = 30
PREAVIS_RETENTION_JOURS = 7


def _jour_local(instant: datetime):
    """Date du jour au Niger (et non en UTC) d'un instant."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(FUSEAU).date()


def statistiques_organisation(db: Session, organisation: Organisation) -> dict:
    org_id = organisation.id
    maintenant = datetime.now(timezone.utc)
    aujourdhui = _jour_local(maintenant)
    debut_mois = aujourdhui.replace(day=1)
    debut_serie = aujourdhui - timedelta(days=JOURS_SERIE - 1)

    # --- Objets par statut (une seule requête) ---
    par_statut = dict(
        db.query(Objet.statut, func.count(Objet.id)).filter(Objet.organisation_id == org_id).group_by(Objet.statut).all()
    )
    en_attente = par_statut.get(StatutObjet.EN_ATTENTE.value, 0)
    restitues = par_statut.get(StatutObjet.RESTITUE.value, 0)
    archives = par_statut.get(StatutObjet.ARCHIVE.value, 0)
    total = sum(par_statut.values())

    # --- Taux de restitution : parmi les objets qui ont connu une issue ou qui attendent ---
    # (les objets archivés, souvent des saisies erronées, sont exclus du calcul).
    base = en_attente + restitues
    taux = round(100 * restitues / base) if base else None

    # --- Restitutions : délai moyen et total du mois ---
    lignes = (
        db.query(Restitution.date_heure, Objet.date_heure_decouverte)
        .select_from(Restitution)
        .join(Objet, Objet.id == Restitution.objet_id)
        .filter(Objet.organisation_id == org_id)
        .all()
    )
    delais = []
    restitues_mois = 0
    restitues_par_jour: dict = {}
    for remise, decouverte in lignes:
        if remise.tzinfo is None:
            remise = remise.replace(tzinfo=timezone.utc)
        if decouverte.tzinfo is None:
            decouverte = decouverte.replace(tzinfo=timezone.utc)
        delais.append(max((remise - decouverte).total_seconds(), 0))
        jour = _jour_local(remise)
        if jour >= debut_mois:
            restitues_mois += 1
        if jour >= debut_serie:
            restitues_par_jour[jour] = restitues_par_jour.get(jour, 0) + 1
    delai_moyen_heures = round(sum(delais) / len(delais) / 3600, 1) if delais else None

    # --- Objets enregistrés par jour (30 derniers jours) + par catégorie (en attente) ---
    objets_recents = (
        db.query(Objet.date_heure_decouverte)
        .filter(Objet.organisation_id == org_id, Objet.date_heure_decouverte >= maintenant - timedelta(days=JOURS_SERIE + 1))
        .all()
    )
    trouves_par_jour: dict = {}
    for (quand,) in objets_recents:
        jour = _jour_local(quand)
        if jour >= debut_serie:
            trouves_par_jour[jour] = trouves_par_jour.get(jour, 0) + 1
    serie = []
    for i in range(JOURS_SERIE):
        jour = debut_serie + timedelta(days=i)
        serie.append({"date": jour.isoformat(), "trouves": trouves_par_jour.get(jour, 0), "restitues": restitues_par_jour.get(jour, 0)})

    categories = (
        db.query(Objet.categorie, func.count(Objet.id))
        .filter(Objet.organisation_id == org_id, Objet.statut == StatutObjet.EN_ATTENTE.value)
        .group_by(Objet.categorie)
        .order_by(func.count(Objet.id).desc(), Objet.categorie)
        .all()
    )

    # --- Déclarations de perte ---
    declarations_en_cours = (
        db.query(func.count(SignalementPerte.id))
        .filter(SignalementPerte.organisation_id == org_id, SignalementPerte.statut != StatutSignalement.CLOTURE.value)
        .scalar()
    )

    # --- Objets bientôt en fin de rétention ---
    delai = organisation.delai_retention_jours or 90
    limite = maintenant - timedelta(days=max(delai - PREAVIS_RETENTION_JOURS, 0))
    proches = (
        db.query(func.count(Objet.id))
        .filter(Objet.organisation_id == org_id, Objet.statut == StatutObjet.EN_ATTENTE.value, func.coalesce(Objet.retention_depuis, Objet.date_heure_decouverte) <= limite)
        .scalar()
    )

    return {
        "organisation_id": str(org_id),
        "organisation_nom": organisation.nom,
        "secteur": organisation.secteur,
        "delai_retention_jours": delai,
        "objets_en_attente": en_attente,
        "objets_restitues": restitues,
        "objets_archives": archives,
        "objets_total": total,
        "restitues_ce_mois": restitues_mois,
        "declarations_en_cours": declarations_en_cours or 0,
        "taux_restitution": taux,
        "delai_moyen_heures": delai_moyen_heures,
        "proches_fin_retention": proches or 0,
        "par_categorie": [{"categorie": c, "nombre": n} for c, n in categories],
        "serie_30_jours": serie,
    }
