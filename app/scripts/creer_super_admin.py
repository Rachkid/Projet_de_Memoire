"""
Création du TOUT PREMIER super-administrateur.

Pourquoi un script ? Depuis l'étape 8, créer un compte exige d'être déjà
connecté en tant qu'administrateur : il faut donc un premier compte créé
« de l'intérieur », sans passer par l'API. Ce script se lance à la main, une
seule fois, sur le serveur :

    docker compose exec api python -m app.scripts.creer_super_admin

Le mot de passe est saisi sans affichage à l'écran (getpass) : il ne figure
ni dans l'historique des commandes, ni dans un fichier.
"""

import getpass
import sys

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401 — enregistre les modèles avant create_all
from app.models.enums import RoleUtilisateur, SecteurOrganisation
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.schemas.utilisateur import UtilisateurCreate
from app.security import hacher_mot_de_passe

NOM_ORGANISATION_TECHNIQUE = "Administration de la plateforme"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        identifiant = input("Identifiant du super-administrateur : ").strip()
        nom = input("Nom complet : ").strip()
        mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
        if mot_de_passe != getpass.getpass("Confirmez le mot de passe : "):
            sys.exit("Les deux mots de passe ne sont pas identiques. Abandon.")

        # On réutilise les règles de validation du schéma : mêmes contraintes que l'API.
        try:
            donnees = UtilisateurCreate(
                identifiant=identifiant, nom=nom, role=RoleUtilisateur.SUPER_ADMINISTRATEUR,
                organisation_id="00000000-0000-0000-0000-000000000000", mot_de_passe=mot_de_passe,
            )
        except ValueError as erreur:
            sys.exit(f"Données invalides :\n{erreur}")

        if db.query(Utilisateur).filter(Utilisateur.identifiant == donnees.identifiant).first():
            sys.exit("Cet identifiant existe déjà. Abandon.")

        # Le super-administrateur doit appartenir à une organisation (colonne
        # obligatoire) : on utilise une organisation « technique ».
        organisation = db.query(Organisation).filter(Organisation.nom == NOM_ORGANISATION_TECHNIQUE).first()
        if organisation is None:
            organisation = Organisation(nom=NOM_ORGANISATION_TECHNIQUE, secteur=SecteurOrganisation.EDUCATION.value)
            db.add(organisation)
            db.flush()

        db.add(Utilisateur(
            organisation_id=organisation.id, identifiant=donnees.identifiant, nom=donnees.nom,
            role=RoleUtilisateur.SUPER_ADMINISTRATEUR.value,
            droit_enregistrement=False, droit_restitution=False,
            mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe),
        ))
        db.commit()
        print(f"Super-administrateur « {donnees.identifiant} » créé avec succès.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
