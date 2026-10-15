"""
Schémas Pydantic pour la ressource Objet (un objet trouvé).

Remarque importante : qr_code et statut n'apparaissent pas dans
ObjetCreate, car ces deux champs ne sont jamais fournis par la personne
qui enregistre l'objet : ils seront calculés automatiquement par le
router au moment de la création (voir étape suivante).
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutObjet, TypeEmplacement


class ObjetBase(BaseModel):
    categorie: str
    photo_url: Optional[str] = None
    date_heure_decouverte: datetime
    type_emplacement: Optional[TypeEmplacement] = None
    lieu_detail: Optional[str] = None


class ObjetCreate(ObjetBase):
    # L'organisation et l'agent ne sont plus fournis par le client : ils sont
    # déduits de la personne connectée (jeton), donc impossibles à falsifier.
    # Détail caché : accepté à la création, mais volontairement ABSENT de
    # ObjetRead pour qu'il ne sorte jamais dans les réponses publiques.
    detail_cache: Optional[str] = None


class ObjetRead(ObjetBase):
    id: uuid.UUID
    organisation_id: uuid.UUID
    agent_id: uuid.UUID
    qr_code: str
    statut: StatutObjet

    model_config = ConfigDict(from_attributes=True)
