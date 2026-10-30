"""Tests de l'étape 19 (catégories personnalisées). Lancer : python -m unittest discover -s tests -v"""

import importlib.util
import unittest

from app.services.categories import categories_pour

AVEC_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None
if AVEC_SQLALCHEMY:
    from pydantic import ValidationError

    from app.schemas.categorie import CategorieCreate, CategorieUpdate, cle_nom


class TestCategoriesPerso(unittest.TestCase):
    def test_perso_ajoutees_avant_autre(self):
        liste = categories_pour("education", ["Casier de sport"])
        self.assertEqual(liste[-1], "Autre")
        self.assertIn("Casier de sport", liste)
        self.assertLess(liste.index("Casier de sport"), liste.index("Autre"))

    def test_sans_perso_inchange(self):
        self.assertEqual(categories_pour("transport"), categories_pour("transport", []))


@unittest.skipUnless(AVEC_SQLALCHEMY, "SQLAlchemy absent")
class TestSchemasCategorie(unittest.TestCase):
    def test_cle_nom(self):
        self.assertEqual(cle_nom("  Casier  de Sport "), cle_nom("casier de sport"))

    def test_nom_invalide(self):
        for nom in ("<b>x</b>", "a", "Autre"):
            with self.assertRaises(ValidationError):
                CategorieCreate(nom=nom, icone="sac")

    def test_icone_inconnue(self):
        with self.assertRaises(ValidationError):
            CategorieCreate(nom="Casier", icone="inexistante")

    def test_traduction_langue_inconnue(self):
        with self.assertRaises(ValidationError):
            CategorieCreate(nom="Casier", icone="sac", traductions={"zz": "x"})

    def test_valide(self):
        c = CategorieCreate(nom="Casier de sport", icone="sac", traductions={"en": "Sports locker"})
        self.assertEqual(c.nom, "Casier de sport")
        CategorieUpdate(actif=False)


if __name__ == "__main__":
    unittest.main()
