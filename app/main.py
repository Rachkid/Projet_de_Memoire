"""
Point d'entrée de l'application : assemble la base de données, les modèles
et les routers écrits dans les étapes précédentes en une seule application
FastAPI exécutable.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.openapi.docs import get_redoc_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import (  # noqa: F401 — l'import garantit que tous les modèles
    Organisation,          # sont enregistrés auprès de SQLAlchemy avant la
    Utilisateur,           # création des tables ci-dessous.
    Usager,
    Objet,
    Restitution,
    SignalementPerte,
)
from app.migrations_runner import appliquer_migrations
from app.routers import alertes, auth, historique, objets, organisations, photos, portail, restitutions, signalements, statistiques, usagers, utilisateurs

# 1) Crée les tables qui n'existent pas encore (base neuve).
Base.metadata.create_all(bind=engine)
# 2) Applique les migrations Alembic en attente (Étape 10) : met à niveau, sans rien perdre,
#    une base créée par une étape précédente (ajout de colonnes, par exemple).
appliquer_migrations()

app = FastAPI(
    title="Tsintuwa — Système de gestion des objets perdus",
    description=(
        "API du projet de mémoire de fin de cycle M2 Génie Logiciel — "
        "Institut Africain de Technologie (IAT), Niamey, Niger."
    ),
    version="0.11.0",
    redoc_url=None,  # remplacée plus bas par une version figée (voir page_redoc)
)

# Chaque router déclare lui-même son préfixe d'URL (ex. : /objets) ;
# il suffit donc de l'enregistrer ici pour que ses routes deviennent actives.
app.include_router(auth.router)
app.include_router(alertes.router)
app.include_router(organisations.router)
app.include_router(utilisateurs.router)
app.include_router(usagers.router)
app.include_router(objets.router)
app.include_router(signalements.router)
app.include_router(restitutions.router)
app.include_router(photos.router)
app.include_router(portail.router)
app.include_router(statistiques.router)
app.include_router(historique.router)

# Les photos d'OBJETS sont publiques : on expose leur dossier tel quel. Le
# dossier des photos de propriétaires n'est volontairement PAS exposé ici.
photos.DOSSIER_OBJETS.mkdir(parents=True, exist_ok=True)
app.mount("/fichiers/objets", StaticFiles(directory=photos.DOSSIER_OBJETS), name="photos_objets")


# Logos et photos de fond des organisations : publics aussi (page de connexion, portail, écran d'affichage).
organisations.DOSSIER_ORGANISATIONS.mkdir(parents=True, exist_ok=True)
app.mount(
    organisations.URL_ORGANISATIONS,
    StaticFiles(directory=organisations.DOSSIER_ORGANISATIONS),
    name="images_organisations",
)

# Pages de l'interface (portail public, puis interface agent et écran d'affichage).
DOSSIER_STATIC = Path(__file__).resolve().parent / "static"


@app.middleware("http")
async def toujours_reverifier_les_pages(request: Request, call_next):
    """
    Les pages (HTML) et leurs fichiers CSS/JS sont revérifiés par le navigateur à chaque
    ouverture (« no-cache » : il demande au serveur si le fichier a changé, et ne le
    retélécharge que si c'est le cas). Sans cela, après une mise à jour, un navigateur
    peut continuer à utiliser l'ancien JavaScript pendant des heures. Les photos et le
    code QR gardent leur propre règle.
    """
    reponse = await call_next(request)
    type_contenu = reponse.headers.get("content-type", "")
    if request.url.path.startswith("/static/") or type_contenu.startswith("text/html"):
        reponse.headers["Cache-Control"] = "no-cache"
    return reponse
app.mount("/static", StaticFiles(directory=DOSSIER_STATIC), name="static")


@app.get("/redoc", include_in_schema=False)
def page_redoc():
    """
    Documentation ReDoc. FastAPI charge par défaut la version « next » du script (en préparation) qui
    s'affichait en page blanche dans certains navigateurs : on fige ici une version stable.
    """
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js",
    )


@app.get("/", tags=["Racine"])
def accueil():
    """Simple point de contrôle confirmant que l'API est en ligne."""
    return {
        "message": "API Tsintuwa — Système de gestion des objets perdus.",
        "documentation_interactive": "/docs",
    }


@app.get("/{slug}/agent", include_in_schema=False)
def page_agent(slug: str, db: Session = Depends(get_db)):
    """Interface des agents d'une organisation (connexion, enregistrement, restitution) : une page pour toutes."""
    existe = db.query(Organisation.id).filter(Organisation.slug == slug.strip().lower()).first()
    if existe is None:
        return FileResponse(DOSSIER_STATIC / "portail" / "introuvable.html", status_code=404)
    return FileResponse(DOSSIER_STATIC / "agent" / "index.html")


@app.get("/{slug}/affichage", include_in_schema=False)
def page_affichage(slug: str, db: Session = Depends(get_db)):
    """Écran d'affichage du hall d'une organisation : objets trouvés en plein écran, sans interaction."""
    existe = db.query(Organisation.id).filter(Organisation.slug == slug.strip().lower()).first()
    if existe is None:
        return FileResponse(DOSSIER_STATIC / "portail" / "introuvable.html", status_code=404)
    return FileResponse(DOSSIER_STATIC / "affichage" / "index.html")


# DOIT rester la dernière route : « /{identifiant} » capte toute adresse à un seul niveau
# (ex. /iat). Les adresses réservées (/docs, /redoc, /openapi.json) sont déclarées plus tôt
# par FastAPI et gardent donc la priorité ; les identifiants réservés de la liste
# SLUGS_RESERVES empêchent qu'une organisation leur prenne leur nom.
@app.get("/{slug}", include_in_schema=False)
def page_portail(slug: str, db: Session = Depends(get_db)):
    """Portail public d'une organisation : la même page pour toutes, habillée par le navigateur."""
    existe = db.query(Organisation.id).filter(Organisation.slug == slug.strip().lower()).first()
    if existe is None:
        return FileResponse(DOSSIER_STATIC / "portail" / "introuvable.html", status_code=404)
    return FileResponse(DOSSIER_STATIC / "portail" / "index.html")
