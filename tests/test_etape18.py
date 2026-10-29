"""
Tests automatiques de l'étape 18 (corrections, catégories, matricule). Règles « pures » : pas de base de données.

Lancer :  python -m unittest discover -s tests -v   (depuis le dossier du projet)
"""

import importlib.util
import unittest

from app.services.categories import CATEGORIES_COMMUNES, categories_pour

# Les schémas importent les modèles de la base : ces tests ont donc besoin de SQLAlchemy (présent dans l'image Docker).
AVEC_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None
if AVEC_SQLALCHEMY:
    from pydantic import ValidationError

    from app.schemas.restitution import RestitutionCreate
    from app.schemas.signalement_perte import SignalementPerteUpdate
    from app.schemas.utilisateur import UtilisateurUpdate


class TestCategories(unittest.TestCase):
    def test_pas_de_doublon_dans_chaque_secteur(self):
        for secteur in ("education", "transport"):
            liste = categories_pour(secteur)
            self.assertEqual(len(liste), len(set(liste)), secteur)

    def test_autre_est_toujours_en_dernier(self):
        for secteur in ("education", "transport"):
            self.assertEqual(categories_pour(secteur)[-1], "Autre")

    def test_categories_propres_a_un_secteur(self):
        edu, trans = categories_pour("education"), categories_pour("transport")
        self.assertIn("Relevé de notes ou bulletin", edu)
        self.assertNotIn("Relevé de notes ou bulletin", trans)
        self.assertIn("Matériel de plomberie", trans)
        self.assertNotIn("Matériel de plomberie", edu)
        self.assertIn("Billet de voyage", trans)

    def test_renommages_de_l_etape_18(self):
        self.assertIn("Écouteurs ou baladeur", CATEGORIES_COMMUNES)
        self.assertNotIn("Écouteurs", CATEGORIES_COMMUNES)
        self.assertIn("Kit de maintenance ou de robotique", categories_pour("education"))
        self.assertNotIn("Kit de maintenance et robotique", categories_pour("education"))

    def test_nouvelles_categories_communes(self):
        for nom in ("Bazin ou tissu", "Outils de réparation", "Carte de crédit", "Pièces mécaniques", "Outils de chantier"):
            self.assertIn(nom, CATEGORIES_COMMUNES)


@unittest.skipUnless(AVEC_SQLALCHEMY, "SQLAlchemy absent")
class TestCorrections(unittest.TestCase):
    def test_identifiant_normalise_et_controle(self):
        self.assertEqual(UtilisateurUpdate(identifiant="  Amina.Diallo ").identifiant, "amina.diallo")
        for mauvais in ("ab", "Amina Diallo", "été", "a" * 51):
            with self.assertRaises(ValidationError, msg=mauvais):
                UtilisateurUpdate(identifiant=mauvais)

    def test_identifiant_vide_refuse(self):
        with self.assertRaises(ValidationError):
            UtilisateurUpdate(identifiant=None)

    def test_nom_vide_refuse(self):
        with self.assertRaises(ValidationError):
            UtilisateurUpdate(nom="   ")

    def test_declaration_categorie_non_vide(self):
        self.assertEqual(SignalementPerteUpdate(categorie=" Clés ").categorie, "Clés")
        with self.assertRaises(ValidationError):
            SignalementPerteUpdate(categorie="  ")

    def test_declaration_champs_absents_non_envoyes(self):
        self.assertEqual(SignalementPerteUpdate(lieu_approximatif="Bus 15").model_dump(exclude_unset=True), {"lieu_approximatif": "Bus 15"})


@unittest.skipUnless(AVEC_SQLALCHEMY, "SQLAlchemy absent")
class TestMatricule(unittest.TestCase):
    BASE = dict(objet_id="11111111-1111-1111-1111-111111111111", usager_id="22222222-2222-2222-2222-222222222222",
                detail_controle_valide=True, type_piece_identite="Carte d'identité", numero_piece="123456")

    def test_matricule_facultatif_et_nettoye(self):
        self.assertIsNone(RestitutionCreate(**self.BASE).matricule_etudiant)
        self.assertIsNone(RestitutionCreate(**self.BASE, matricule_etudiant="   ").matricule_etudiant)
        self.assertEqual(RestitutionCreate(**self.BASE, matricule_etudiant=" 2024/IAT/0123 ").matricule_etudiant, "2024/IAT/0123")

    def test_matricule_invalide_refuse(self):
        with self.assertRaises(ValidationError):
            RestitutionCreate(**self.BASE, matricule_etudiant="2024/IAT/0123 !!")


if __name__ == "__main__":
    unittest.main()
