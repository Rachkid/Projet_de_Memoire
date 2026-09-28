"""
Ce fichier regroupe toutes les listes de valeurs fixes (énumérations)
utilisées par plusieurs modèles du projet : secteur d'une organisation,
rôle d'un utilisateur, type d'emplacement d'un objet, statut d'un objet,
statut d'un signalement de perte.

Centraliser ces énumérations ici évite de répéter des chaînes de caractères
"en dur" (et potentiellement mal orthographiées différemment) à plusieurs
endroits du code.
"""

import enum


class SecteurOrganisation(str, enum.Enum):
    EDUCATION = "education"
    TRANSPORT = "transport"


class RoleUtilisateur(str, enum.Enum):
    AGENT = "agent"
    ADMINISTRATEUR = "administrateur"
    SUPER_ADMINISTRATEUR = "super_administrateur"


class TypeEmplacement(str, enum.Enum):
    VEHICULE = "vehicule"
    LOCAUX = "locaux"


class StatutObjet(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    RECLAME = "reclame"
    RESTITUE = "restitue"
    ARCHIVE = "archive"


class StatutSignalement(str, enum.Enum):
    EN_ATTENTE = "en_attente"
    CORRESPONDANCE_TROUVEE = "correspondance_trouvee"
    CLOTURE = "cloture"
