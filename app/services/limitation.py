"""
Limitation des tentatives (étape 16) : freiner les essais en rafale.

Deux dangers visés :
  - quelqu'un qui essaie des milliers de mots de passe sur un compte (force brute) ;
  - un robot qui inonde les formulaires publics de fausses déclarations.

Principe : on garde, pour chaque « clé » (ex. adresse + identifiant), l'heure de ses derniers
événements. Au-delà du maximum autorisé dans la fenêtre de temps, on refuse jusqu'à ce que les plus
anciens événements sortent de la fenêtre.

Limite connue (à signaler dans le mémoire) : les compteurs sont gardés en mémoire du serveur. Ils sont
remis à zéro au redémarrage, et ne sont pas partagés si l'on lance plusieurs copies du serveur. Pour une
mise en service avec plusieurs copies, on les déplacerait dans une base rapide (Redis).

Ce module ne dépend ni de FastAPI ni de la base de données : il est testable seul.
"""

import math
import threading
import time
from collections import deque


class Limiteur:
    def __init__(self, maximum: int, fenetre_secondes: int, horloge=time.monotonic):
        self.maximum = maximum
        self.fenetre = fenetre_secondes
        self._horloge = horloge
        self._evenements: dict[str, deque[float]] = {}
        self._verrou = threading.Lock()

    def _purger(self, cle: str, maintenant: float) -> deque:
        file = self._evenements.get(cle)
        if file is None:
            return deque()
        while file and maintenant - file[0] >= self.fenetre:
            file.popleft()
        if not file:
            self._evenements.pop(cle, None)
        return file

    def attente(self, cle: str) -> int:
        """Secondes à attendre avant de pouvoir réessayer ; 0 si la clé n'est pas bloquée."""
        with self._verrou:
            maintenant = self._horloge()
            file = self._purger(cle, maintenant)
            if len(file) < self.maximum:
                return 0
            return max(1, math.ceil(self.fenetre - (maintenant - file[0])))

    def enregistrer(self, cle: str) -> None:
        """Note un événement (un échec de connexion, une déclaration reçue...)."""
        with self._verrou:
            maintenant = self._horloge()
            if len(self._evenements) > 20000:  # garde-fou : la mémoire ne doit pas grossir sans fin
                for k in list(self._evenements):
                    self._purger(k, maintenant)
            file = self._purger(cle, maintenant)
            file.append(maintenant)
            self._evenements[cle] = file

    def oublier(self, cle: str) -> None:
        """Efface les événements d'une clé (ex. après une connexion réussie)."""
        with self._verrou:
            self._evenements.pop(cle, None)
