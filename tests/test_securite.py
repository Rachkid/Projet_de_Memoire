"""
Tests automatiques de l'étape 16 (sécurité). Ils n'ont besoin ni de la base de données ni du serveur :
ils vérifient les règles « pures » (jetons, limitation, téléphone, mots de passe).

Lancer :  python -m unittest discover -s tests -v   (depuis le dossier du projet)
"""

import unittest
from datetime import datetime, timedelta, timezone

import jwt

from app.services.jetons import creer_jeton, lire_jeton, lire_jeton_complet
from app.services.limitation import Limiteur
from app.services.telephone import normaliser_telephone

CLE, ALGO = "cle-de-test-" + "x" * 32, "HS256"


class TestJetons(unittest.TestCase):
    def test_le_jeton_contient_la_generation_de_session(self):
        jeton = creer_jeton("abc", CLE, ALGO, 60, version=3)
        self.assertEqual(lire_jeton_complet(jeton, CLE, ALGO), ("abc", 3))

    def test_un_ancien_jeton_sans_generation_est_lu_comme_zero(self):
        ancien = jwt.encode({"sub": "abc", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, CLE, algorithm=ALGO)
        self.assertEqual(lire_jeton_complet(ancien, CLE, ALGO), ("abc", 0))

    def test_jeton_modifie_ou_expire_refuse(self):
        jeton = creer_jeton("abc", CLE, ALGO, 60)
        self.assertIsNone(lire_jeton(jeton[:-2] + "xx", CLE, ALGO))
        self.assertIsNone(lire_jeton(jeton, "autre-cle-" + "y" * 32, ALGO))
        expire = creer_jeton("abc", CLE, ALGO, 1, maintenant=datetime.now(timezone.utc) - timedelta(hours=2))
        self.assertIsNone(lire_jeton(expire, CLE, ALGO))

    def test_jeton_sans_signature_refuse(self):
        sans = jwt.encode({"sub": "abc", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, None, algorithm="none")
        self.assertIsNone(lire_jeton(sans, CLE, ALGO))

    def test_generation_invalide_refusee(self):
        faux = jwt.encode({"sub": "abc", "v": "3", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, CLE, algorithm=ALGO)
        self.assertIsNone(lire_jeton_complet(faux, CLE, ALGO))


class Horloge:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class TestLimiteur(unittest.TestCase):
    def test_bloque_apres_le_maximum_puis_libere(self):
        h = Horloge()
        lim = Limiteur(3, 60, horloge=h)
        for _ in range(3):
            self.assertEqual(lim.attente("a"), 0)
            lim.enregistrer("a")
        self.assertGreater(lim.attente("a"), 0)
        self.assertEqual(lim.attente("b"), 0)  # une autre clé n'est pas touchée
        h.t += 61
        self.assertEqual(lim.attente("a"), 0)

    def test_connexion_reussie_remet_a_zero(self):
        lim = Limiteur(2, 60, horloge=Horloge())
        lim.enregistrer("a"); lim.enregistrer("a")
        self.assertGreater(lim.attente("a"), 0)
        lim.oublier("a")
        self.assertEqual(lim.attente("a"), 0)


class TestTelephone(unittest.TestCase):
    def test_numeros_valides(self):
        self.assertEqual(normaliser_telephone("96 12 34 56"), "+22796123456")
        self.assertEqual(normaliser_telephone("22796123456"), "+22796123456")
        self.assertEqual(normaliser_telephone("00227 96-12-34-56"), "+22796123456")
        self.assertEqual(normaliser_telephone("+33 6 12 34 56 78"), "+33612345678")

    def test_numeros_invalides(self):
        for mauvais in ["12", "abc", "", "9612345", "+12", "96123456789012345", "96 12 34 5a", None]:
            self.assertIsNone(normaliser_telephone(mauvais), mauvais)


class TestSchemas(unittest.TestCase):
    def test_usager_telephone_normalise_ou_refuse(self):
        try:
            from pydantic import ValidationError
            from app.schemas.usager import UsagerCreate
        except Exception as erreur:  # noqa: BLE001 - base ou dépendances absentes : test ignoré hors Docker
            self.skipTest(f"Dépendances du projet absentes : {erreur}")

        self.assertEqual(UsagerCreate(telephone="96 12 34 56").telephone, "+22796123456")
        with self.assertRaises(ValidationError):
            UsagerCreate(telephone="pas un numero")

    def test_regles_du_mot_de_passe(self):
        try:
            from pydantic import ValidationError
            from app.schemas.utilisateur import ChangementMotDePasse
        except Exception as erreur:  # noqa: BLE001
            self.skipTest(f"Dépendances du projet absentes : {erreur}")

        ChangementMotDePasse(ancien_mot_de_passe="x", nouveau_mot_de_passe="12345678")
        with self.assertRaises(ValidationError):
            ChangementMotDePasse(ancien_mot_de_passe="x", nouveau_mot_de_passe="court")
        with self.assertRaises(ValidationError):
            ChangementMotDePasse(ancien_mot_de_passe="x", nouveau_mot_de_passe="é" * 40)


if __name__ == "__main__":
    unittest.main()
