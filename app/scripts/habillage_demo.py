"""
Applique l'habillage de démonstration (logo, photo de fond, couleurs, identifiant
d'adresse) aux deux organisations de test : IAT et Rimbo.

C'est un raccourci pour la démonstration : tout ce que fait ce script peut aussi se
faire par l'API (PATCH /organisations/{id}, POST /organisations/{id}/logo et /fond).
Le script cherche les organisations par leur nom ; sans résultat ou en cas
d'ambiguïté, il l'indique et on lui donne l'identifiant à la main.

Utilisation :
    docker compose exec api python -m app.scripts.habillage_demo
    docker compose exec api python -m app.scripts.habillage_demo --iat <id> --rimbo <id>
"""

import argparse
import uuid
from pathlib import Path

from sqlalchemy import or_

from app.database import SessionLocal
from app.models import Organisation
from app.routers.organisations import DOSSIER_ORGANISATIONS, URL_ORGANISATIONS
from app.services.habillage import enregistrer_fond, enregistrer_logo, supprimer_ancien

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "demo"

# Couleurs choisies à partir du logo (IAT) et de la photo de fond (Rimbo).
DEMO = {
    "iat": {
        "motifs": ["iat", "institut africain"],
        "slug": "iat",
        "couleurs": ("#1a1ad6", "#f0a000", "#ffffff"),
        "logo": "iat_logo.jpg",
        "fond": "iat_fond.jpg",
    },
    "rimbo": {
        "motifs": ["rimbo"],
        "slug": "rimbo",
        "couleurs": ("#2a3a8c", "#c93700", "#efede4"),
        "logo": "rimbo_logo.jpg",
        "fond": "rimbo_fond.jpg",
    },
}


def _trouver(db, cle: str, identifiant: str | None):
    if identifiant:
        return db.get(Organisation, uuid.UUID(identifiant))
    motifs = DEMO[cle]["motifs"]
    trouvees = db.query(Organisation).filter(or_(*[Organisation.nom.ilike(f"%{m}%") for m in motifs])).all()
    if len(trouvees) == 1:
        return trouvees[0]
    print(f"[{cle}] {len(trouvees)} organisation(s) trouvée(s) pour {motifs} : précisez avec --{cle} <id>.")
    for o in db.query(Organisation).all():
        print(f"      {o.id}  {o.nom}")
    return None


def habiller(db, cle: str, organisation: Organisation) -> None:
    modele = DEMO[cle]
    autre = db.query(Organisation).filter(Organisation.slug == modele["slug"], Organisation.id != organisation.id).first()
    if autre is not None:
        print(f"[{cle}] l'identifiant « {modele['slug']} » est déjà pris par « {autre.nom} » : abandon.")
        return
    organisation.slug = modele["slug"]
    organisation.couleur_principale, organisation.couleur_accent, organisation.couleur_fond = modele["couleurs"]

    dossier = DOSSIER_ORGANISATIONS / str(organisation.id)
    ancien_logo, ancien_fond = organisation.logo_url, organisation.fond_url
    nom_logo = enregistrer_logo((ASSETS / modele["logo"]).read_bytes(), dossier, retirer_fond_blanc=True)
    nom_fond = enregistrer_fond((ASSETS / modele["fond"]).read_bytes(), dossier)
    organisation.logo_url = f"{URL_ORGANISATIONS}/{organisation.id}/{nom_logo}"
    organisation.fond_url = f"{URL_ORGANISATIONS}/{organisation.id}/{nom_fond}"
    db.commit()
    supprimer_ancien(ancien_logo, URL_ORGANISATIONS, DOSSIER_ORGANISATIONS)
    supprimer_ancien(ancien_fond, URL_ORGANISATIONS, DOSSIER_ORGANISATIONS)
    print(f"[{cle}] « {organisation.nom} » habillée : adresse « {organisation.slug} », logo et fond enregistrés.")


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Habillage de démonstration (IAT et Rimbo).")
    analyseur.add_argument("--iat", help="identifiant de l'organisation IAT (si le nom ne suffit pas)")
    analyseur.add_argument("--rimbo", help="identifiant de l'organisation Rimbo (si le nom ne suffit pas)")
    arguments = analyseur.parse_args()

    db = SessionLocal()
    try:
        for cle, identifiant in (("iat", arguments.iat), ("rimbo", arguments.rimbo)):
            organisation = _trouver(db, cle, identifiant)
            if organisation is not None:
                habiller(db, cle, organisation)
    finally:
        db.close()


if __name__ == "__main__":
    main()
