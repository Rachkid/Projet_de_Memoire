/*
  Écran d'affichage du hall — Étape 13.
  Cette page ne demande rien à la personne qui la regarde : elle lit l'identifiant de l'organisation
  dans l'adresse (/iat/affichage), reprend ses couleurs, puis affiche en boucle les objets trouvés.

  Ce qu'elle fait toute seule :
  - recharge la liste toutes les 30 secondes (un objet rendu disparaît, un objet nouveau apparaît) ;
  - met en valeur un objet à la fois (zoom pendant 5 secondes), puis le suivant : une page de 6 objets dure donc
    30 secondes, après quoi l'on passe aux 6 suivants s'il y en a davantage ;
  - continue d'afficher les derniers objets reçus si la connexion est coupée (un petit point rouge l'indique) ;
  - se recharge entièrement toutes les 6 heures, pour reprendre un changement de couleurs ou de logo.

  Sécurité : les données viennent de /portail/{identifiant}/objets, la même route publique que le portail.
  Elle ne contient ni détail secret, ni code QR, ni lieu précis. Tout texte venant du serveur est inséré
  avec textContent (jamais en HTML).
*/
(function () {
  "use strict";

  const slug = (location.pathname.split("/").filter(Boolean)[0] || "").toLowerCase();
  const PAR_PAGE = 6;
  const DUREE_ZOOM_MS = 5000;   // un objet mis en valeur pendant 5 secondes
  const RAFRAICHIR_MS = 30000;
  const RECHARGER_PAGE_MS = 6 * 60 * 60 * 1000;

  let org = null;
  let objets = [];
  let signature = "";
  let consultationOuverte = true;
  let page = 0;
  let zoom = 0;          // position (dans la page) de l'objet mis en valeur
  let minuteur = null;

  const $ = (id) => document.getElementById(id);

  /* Langues (étape 15 ter). Par défaut : français seul, comme avant. Pour alterner plusieurs langues sur
     l'écran du hall, ajouter à l'adresse « ?langues=fr,en,ha,dje,ar » : la langue change quand tous les objets
     (toutes les pages) ont défilé dans la langue en cours.
     Le choix n'est jamais mémorisé : un écran de hall doit toujours redémarrer dans la même configuration. */
  const I18N = window.Tsintuwa.i18n;
  const t = I18N.t;
  const LANGUE_MS = 30000;   // sans défilement (0 ou 1 objet, ou page d'invitation) : changement toutes les 30 secondes
  const CODES = I18N.langues.map(function (l) { return l.code; });
  let langues = ["fr"];
  try {
    const demandees = (new URLSearchParams(location.search).get("langues") || "").toLowerCase().split(",")
      .map(function (c) { return c.trim(); }).filter(function (c, i, a) { return CODES.indexOf(c) !== -1 && a.indexOf(c) === i; });
    if (demandees.length) langues = demandees;
  } catch (e) { /* adresse illisible : français seul */ }
  I18N.demarrer(langues[0]);
  let rang = 0;                 // position de la langue en cours dans la liste
  let langueEnAttente = null;   // prochaine langue, appliquée pendant le fondu

  function el(tag, classe, texte) {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }
  function vider(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function estImage(url) { return typeof url === "string" && (url.charAt(0) === "/" || /^https?:\/\//i.test(url)); }

  async function lireJson(chemin) {
    const reponse = await fetch(chemin, { headers: { Accept: "application/json" }, cache: "no-store" });
    const texte = await reponse.text();
    let donnees = null;
    try { donnees = texte ? JSON.parse(texte) : null; } catch (e) { donnees = null; }
    if (!reponse.ok) { const e = new Error("http"); e.status = reponse.status; throw e; }
    return donnees;
  }

  /* ---------- Icônes de catégorie (quand un objet n'a pas de photo) ---------- */

  function cercle(cx, cy, r) { return "M" + (cx - r) + " " + cy + "a" + r + " " + r + " 0 1 0 " + (2 * r) + " 0a" + r + " " + r + " 0 1 0 " + (-2 * r) + " 0"; }
  const ICONES = {
    "ico-ballon": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "ico-casier": "M5 3h14v18H5zM12 3v18M9 11v2M15 11v2",
    "ico-boite": "M3 8l9-5 9 5v9l-9 5-9-5zM3 8l9 5 9-5M12 13v9",
    "ico-cadenas": "M6 11h12v10H6zM8.5 11V7.5a3.5 3.5 0 0 1 7 0V11M12 15v2",
    "ico-parapluie": "M3 12a9 9 0 0 1 18 0zM12 12v7a2 2 0 0 1-4 0",
    "ico-ampoule": "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
    "ico-appareil photo": "M4 8h3l2-3h6l2 3h3v12H4zM8.5 14a3.5 3.5 0 1 0 7.0 0a3.5 3.5 0 1 0 -7.0 0",
    "ico-velo": "M2 16a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M14 16a4 4 0 1 0 8 0a4 4 0 1 0 -8 0M6 16l4-8h5l3 8M10 8H8M15 8l-3 8",
    "ico-plante": "M12 21v-9M12 12c0-4-3-6-7-6 0 4 3 6 7 6zM12 15c0-3 2-5 6-5 0 3-2 5-6 5zM8 21h8",
    "ico-coeur": "M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.5A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z",
    "ico-etoile": "M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.2 6.5 20.2l1-6.2L3 9.6l6.2-.9z",
    "ico-cadeau": "M4 11h16v10H4zM3 7h18v4H3zM12 7v14M12 7c-2-4-6-3-5 0M12 7c2-4 6-3 5 0",
    "ico-reveil": "M4 13a8 8 0 1 0 16 0a8 8 0 1 0 -16 0M12 9v4l3 2M5 4l-2 2M19 4l2 2",
    "ico-tasse": "M5 8h11v7a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4zM16 10h2a2 2 0 0 1 0 4h-2M8 3v2M12 3v2",
    "ico-couverts": "M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 3c-2 2-2 6 0 8v10",
    "ico-biberon": "M9 3h6M10 3v3h4V3M9 6h6l1 3v11a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V9zM8 12h4M8 16h4",
    "ico-cubes": "M4 4h7v7H4zM13 13h7v7h-7zM13 4h7v7h-7zM4 13h7v7H4z",
    "ico-voiture": "M3 16v-4l2-5h14l2 5v4zM5 12h14M5.5 17a1.5 1.5 0 1 0 3.0 0a1.5 1.5 0 1 0 -3.0 0M15.5 17a1.5 1.5 0 1 0 3.0 0a1.5 1.5 0 1 0 -3.0 0",
    "ico-moto": "M2 16a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M16 16a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M5 16l3-6h5l3 6M13 10l2-3h3M8 10H6",
    "ico-bus": "M5 3h14a1 1 0 0 1 1 1v13H4V4a1 1 0 0 1 1-1zM4 11h16M7 17v3M17 17v3M8 14h.01M16 14h.01",
    "ico-valise": "M4 7h16v13H4zM9 7V4h6v3M4 13h16M11 13v2h2v-2",
    "ico-sac a dos": "M8 6a4 4 0 0 1 8 0M6 8h12a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zM9 14h6v4H9zM9 11h6",
    "ico-casque audio": "M4 15v-3a8 8 0 0 1 16 0v3M4 14h3v6H4zM17 14h3v6h-3z",
    "ico-micro": "M9 3h6v9a3 3 0 0 1-6 0zM5 11a7 7 0 0 0 14 0M12 18v3M9 21h6",
    "ico-haut-parleur": "M4 9h4l5-4v14l-5-4H4zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11",
    "ico-tablette": "M5 2h14v20H5zM11 19h2",
    "ico-ecran": "M3 5h18v12H3zM8 21h8M12 17v4",
    "ico-imprimante": "M7 8V3h10v5M5 8h14a2 2 0 0 1 2 2v6h-4M3 16V10a2 2 0 0 1 2-2M7 14h10v7H7z",
    "ico-manette": "M7 8h10a5 5 0 0 1 5 5v1a3 3 0 0 1-5.5 1.7L15 14H9l-1.5 1.7A3 3 0 0 1 2 14v-1a5 5 0 0 1 5-5zM7 11v3M5.5 12.5h3M16 11.5h.01M18 13.5h.01",
    "ico-crayon": "M4 20l1-4L16 5l3 3L8 19zM14 7l3 3",
    "ico-regle": "M3 15L15 3l6 6L9 21zM7 13l2 2M10 10l2 2M13 7l2 2",
    "ico-ciseaux": "M3 18a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M15 18a3 3 0 1 0 6 0a3 3 0 1 0 -6 0M8 16L20 3M16 16L4 3",
    "ico-loupe": "M4 10a6 6 0 1 0 12 0a6 6 0 1 0 -12 0M15 15l6 6",
    "ico-drapeau": "M5 21V4M5 4h12l-2 4 2 4H5",
    "ico-trophee": "M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M12 14v4M8 21h8M9 18h6",
    "ico-pilule": "M10.5 3.5l10 10a4.2 4.2 0 0 1-6 6l-10-10a4.2 4.2 0 0 1 6-6zM8 8l8 8",
    "ico-thermometre": "M10 4a2 2 0 0 1 4 0v10a4 4 0 1 1-4 0zM12 9v8",
    "ico-lune": "M20 14a8 8 0 1 1-9.5-10 6.5 6.5 0 0 0 9.5 10zM17 5l.8 1.7 1.7.8-1.7.8L17 10l-.8-1.7-1.7-.8 1.7-.8z",
    "ico-chapeau": "M3 17h18M6 17c0-6 2-10 6-10s6 4 6 10M6 14h12",
    "ico-cravate": "M9 3h6l-1 4 2 12-4 2-4-2 2-12zM9 3l3 3 3-3",
    "ico-ceinture": "M2 9h20v6H2zM15 9v6M17.5 12h.01M5 12h.01M8 12h.01",
    "ico-dossier": "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
    "ico-enveloppe": "M3 5h18v14H3zM3 6l9 7 9-7",
    "ico-panier": "M3 9h18l-2 11H5zM8 9l3-6M16 9l-3-6",
    "telephone": "M9.5 2h5A2.5 2.5 0 0 1 17 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19.5v-15A2.5 2.5 0 0 1 9.5 2zM11 18.5h2",
    "portefeuille": "M3 7.5A2.5 2.5 0 0 1 5.5 5H18a1 1 0 0 1 1 1v2M3 7.5V17a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1H5.5A2.5 2.5 0 0 1 3 7.5zM16 13.5h.01",
    "cles": cercle(8, 15, 4) + "M10.85 12.15L19 4M18 5l3 3M15 8l2 2",
    "sac": "M6 8h12l1 12H5L6 8zM9 8V6a3 3 0 0 1 6 0v2",
    "documents": "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5M9 13h6M9 17h6",
    "carte bancaire": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM2 10h20M6 15h4",
    "carte de credit": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM2 10h20M6 15h4",
    "batterie": "M3 8h16v10H3zM19 11h2v4h-2zM7 11v4M11 11v4",
    "objets electroniques": "M7 7h10v10H7zM10 10h4v4h-4zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
    "pieces mecaniques": "M14.7 6.3a4 4 0 0 0-5 5L3 18l3 3 6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-2.3-.7-.7-2.3z",
    "bazin ou tissu": "M3 5h18v14H3zM3 9h18M3 13h18M3 17h18M8 5v14M13 5v14M18 5v14",
    "outils de reparation": "M14.7 6.3a4 4 0 0 0-5 5L3 18l3 3 6.7-6.7a4 4 0 0 0 5-5l-2.4 2.4-2.3-.7-.7-2.3zM15 15l5 5",
    "pieces de telephone ou d'appareils": "M7 2h10a1 1 0 0 1 1 1v8M6 8v13a1 1 0 0 0 1 1h4M6 5v1M14 14l-2 2 2 2M18 14l2 2-2 2M12 22l4-8",
    "materiel electrique": "M13 2L4 14h7l-1 8 9-12h-7z",
    "kit ou objet pour bebe": "M12 3a4 4 0 0 0-4 4v2h8V7a4 4 0 0 0-4-4zM6 9h12l-1 5a5 5 0 0 1-10 0zM9 20h6",
    "materiel de plomberie": "M3 7h10a3 3 0 0 1 3 3v1h5v4h-5v1a3 3 0 0 1-3 3H3zM7 7v10M7 12h5",
    "materiel de soudure": "M14 3l7 7-3 3-7-7zM11 6L3 14l3 3 8-8M4 20l4-4M17 17l2 2M20 15l-1 1",
    "carte sim": "M6 2h8l4 4v16H6zM9 11h6v7H9zM9 14.5h6M12 11v7",
    "multiprise ou rallonge": "M3 8h18v8H3zM7 11v2M11 11v2M15 11v2M3 12H1M21 12h2",
    "masque ou niqab": "M4 8c0-2 3-3 8-3s8 1 8 3v4c0 4-3.5 7-8 7s-8-3-8-7zM2 10l2 1M22 10l-2 1M8 12h8",
    "coran": "M5 3h13a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5zM5 3v18M12 8l1.2 2.5L16 11l-2 2 .5 3-2.5-1.5L9.5 16l.5-3-2-2 2.8-.5z",
    "ceinture": "M2 9h20v6H2zM15 9v6M17 12h.01M6 12h5",
    "clavier": "M2 6h20v12H2zM6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10",
    "souris": "M12 2a6 6 0 0 1 6 6v8a6 6 0 0 1-12 0V8a6 6 0 0 1 6-6zM12 2v7M6 9h12",
    "outils informatiques": "M4 5h16v10H4zM2 19h20M9 15v4M15 15v4M10 8l-2 2 2 2M14 8l2 2-2 2",
    "memoire ram ou sd": "M7 2h8l4 4v16H7zM10 2v4M13 2v4M10 12h6M10 16h6",
    "tenue de sport": "M8 3L2 6l2 5 3-1v11h10V10l3 1 2-5-6-3a4 4 0 0 1-8 0zM9 21V13M15 21V13",
    "copie de devoir ou d'examen": "M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7M9 9h3",
    "releve de notes ou bulletin": "M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM8 8h8M8 12h3M13 12h3M8 16h3M13 16h3",
    "outils de chantier": "M2 21h20M4 21V11l8-6 8 6v10M9 21v-6h6v6M12 5V2",
    "vetement": "M9 3L3 6l2.2 4.2L8 9v12h8V9l2.8 1.2L21 6l-6-3a3 3 0 0 1-6 0z",
    "lunettes": cercle(6.5, 14, 3.5) + cercle(17.5, 14, 3.5) + "M10 14h4M3 14l2-7M21 14l-2-7",
    "ordinateur": "M5 5h14a1 1 0 0 1 1 1v9H4V6a1 1 0 0 1 1-1zM2 19h20",
    "ecouteurs ou baladeur": "M4 15v-3a8 8 0 0 1 16 0v3M4 15a2 2 0 0 1 2-2h1v6H6a2 2 0 0 1-2-2zM20 15a2 2 0 0 0-2-2h-1v6h1a2 2 0 0 0 2-2z",
    "ecouteurs": "M4 15v-3a8 8 0 0 1 16 0v3M4 15a2 2 0 0 1 2-2h1v6H6a2 2 0 0 1-2-2zM20 15a2 2 0 0 0-2-2h-1v6h1a2 2 0 0 0 2-2z",
    "montre": "M10 2.5h4l1 4M14 21.5h-4l-1-4M10 6.5h4a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3h-4a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3zM12 10v2.2l1.5 1",
    "bijou": "M6 3h12l4 6-10 12L2 9l4-6zM2 9h20M9 3L7 9l5 12 5-12-2-6",
    "livre ou cahier": "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zM4 19a2 2 0 0 0 2 2h13M8 7h7",
    "tapis de priere": "M6 3h12v18H6zM9 21V10a3 3 0 0 1 6 0v11",
    "casquette": "M5 15a7 7 0 0 1 14 0zM19 15h3M12 8V6",
    "bonnet": "M5 16a7 7 0 0 1 14 0zM4 16h16v3H4zM12 9V6",
    "chapelet": cercle(12, 5, 2) + cercle(6.5, 10, 2) + cercle(17.5, 10, 2) + cercle(8, 17, 2) + cercle(16, 17, 2),
    "gourde": "M10 2h4v3h-4zM8 5h8l1 4v11a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V9zM7 11h10",
    "sachet": "M6 7h12l1 13H5zM9 7a3 3 0 0 1 6 0",
    "tenue scolaire": "M9 3L3 6l2.2 4.2L8 9v12h8V9l2.8 1.2L21 6l-6-3a3 3 0 0 1-6 0zM12 12v5",
    "carte scolaire": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM15 10h4M15 14h4M5.5 16.5c.5-2 5.5-2 6 0" + cercle(8.5, 10.5, 1.8),
    "carte d'identite": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM15 10h4M15 14h4M5.5 16.5c.5-2 5.5-2 6 0" + cercle(8.5, 10.5, 1.8),
    "passeport": "M6 2h12a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM9 17h6" + cercle(12, 10, 3),
    "cle usb": "M9 2h6v6H9zM10 8v3M14 8v3M7 11h10v9a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2z",
    "disque dur": "M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM7 14h.01M11 14h6",
    "chargeur": "M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5",
    "argent": "M2 6h20v12H2zM5.5 12h.01M18.5 12h.01" + cercle(12, 12, 3),
    "pochette": "M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 11h18M10 11v2h4v-2",
    "bracelet": cercle(12, 12, 8) + cercle(12, 12, 5),
    "enveloppe": "M3 6h18v12H3zM3 7l9 7 9-7",
    "thermos": "M8 2h8v3H8zM7 5h10v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1zM7 10h10",
    "billet de voyage": "M3 7h18v3a2 2 0 0 0 0 4v3H3v-3a2 2 0 0 0 0-4zM14 7v10",
    "chaussures": "M3 16V8l5 2 3 3h6a4 4 0 0 1 4 4v0H3zM3 19h18",
    "permis de conduire": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM5.5 15.5h6M14 10h5M14 13.5h5" + cercle(8.5, 10, 1.8),
    "ensemble geometrique": "M3 20L12 4l9 16zM8 20l4-8M3 20h18",
    "bic": "M17 3l4 4L8 20l-5 1 1-5zM14 6l4 4",
    "calculatrice": "M6 2h12a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM8 6h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15h.01M8 18h.01M12 18h.01M16 18h.01",
    "kit de maintenance ou de robotique": cercle(12, 12, 3) + "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
    "kit de maintenance et robotique": cercle(12, 12, 3) + "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
    "hijab ou voile": "M12 3a6 6 0 0 0-6 6v4c0 3 1.5 5 3 6l3 2 3-2c1.5-1 3-3 3-6V9a6 6 0 0 0-6-6zM9 9.5a3 3 0 0 1 6 0v3a3 3 0 0 1-6 0z",
    "carte professionnelle": "M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM9 3v3h6V3M8 16h8" + cercle(12, 11, 2.2),
    "recu de paiement ou quittance": "M6 2h12v20l-3-2-3 2-3-2-3 2V2zM9 8h6M9 12h6M9 16h3",
    "chaussettes": "M8 2h7v9l5 5a3 3 0 0 1 0 4l-1 1a3 3 0 0 1-4 0l-7-6zM8 6h7",
    "produits medicaux": "M4 7h16v13H4zM9 7V4h6v3M12 11v6M9 14h6",
    "produits cosmetiques": "M9 3h6v6H9zM7 9h10v12H7zM7 14h10",
    "produits alimentaires": "M5 8h14l-1 13H6zM8 8a4 4 0 0 1 8 0M9 13h6",
    "produits d'hygiene": "M9 2h6v3H9zM7 5h10v17H7zM12 10c-2 2.5-2 4 0 5.5 2-1.5 2-3 0-5.5z",
    "produits menagers": "M7 3h6l2 3v3H7zM6 9h10v12H6zM16 6h3v3M6 14h10",
    "ustensiles de cuisine": "M6 2v8a2 2 0 0 0 2 2v10M10 2v8M6 6h4M17 2c-2 2-2 6 0 8v12",
    "parfums": "M10 2h4v3h-4zM8 5h8v3H8zM6 8h12v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1zM12 12v5",
    "amplificateur sonore": "M4 9h4l6-5v16l-6-5H4zM17 8a5 5 0 0 1 0 8M19.5 5.5a9 9 0 0 1 0 13",
    "boissons": "M7 3h10l-1 18H8zM7.5 9h9M12 3l2-2",
    "papiers de voiture ou moto": "M6 2h9l4 4v16H6zM14 2v5h5M9 12h7M9 16h7",
    "kit de maquillage": "M3 9h18v11H3zM8 9V6h8v3M12 13v3M9 14.5h6",
    "casque de moto": "M3 14a9 9 0 0 1 18 0v4H3zM3 14h18M12 5v9M14 14h7",
    "autre": "M21 8l-9-5-9 5v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8"
  };

  /* Catégories ajoutées par l'organisation : traductions, et icône choisie dans le catalogue (même clé de recherche que les autres). */
  function enregistrerCategoriesPerso(liste) {
    I18N.ajouterCategories(liste);
    (liste || []).forEach(function (c) {
      const cle = (c.nom || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
      if (cle && !ICONES[cle]) ICONES[cle] = ICONES[c.icone] || ICONES.autre;
    });
  }

  function icone(categorie) {
    const cle = (categorie || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", ICONES[cle] || ICONES.autre);
    svg.appendChild(p);
    return svg;
  }

  /* ---------- Textes selon le secteur ---------- */

  function textes() {
    return {
      sous: t("hall.sous"),
      aide: t("hall.aide"),
      videTitre: t("hall.vide_titre"),
      videTexte: t("hall.vide_texte"),
      fermeTitre: t("hall.ferme_titre"),
      fermeTexte: t("hall.ferme_texte")
    };
  }

  /* ---------- Habillage ---------- */

  /* Les textes qui dépendent de la langue et de l'organisation (relancé à chaque changement de langue). */
  function textesFixes() {
    document.title = t("hall.titre_page", { org: org.nom });
    $("sous-titre").textContent = textes().sous;
    $("pied-aide").textContent = textes().aide;
    const img = $("logo").querySelector("img");
    if (img) img.alt = t("hall.logo_alt", { org: org.nom });
  }

  function appliquerTheme() {
    const t = org.theme, racine = document.documentElement.style;
    racine.setProperty("--principale", t.principale);
    racine.setProperty("--accent", t.accent);
    racine.setProperty("--fond", t.fond);
    racine.setProperty("--sombre", t.sombre);
    racine.setProperty("--t-principale", t.texte_sur_principale);
    racine.setProperty("--t-accent", t.texte_sur_accent);
    racine.setProperty("--t-sombre", t.texte_sur_sombre);
    racine.setProperty("--t-fond", t.texte_sur_fond);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", t.sombre);
    $("nom-org").textContent = org.nom;
    textesFixes();

    if (estImage(org.logo_url)) {
      const img = el("img");
      img.src = org.logo_url;
      vider($("logo")).appendChild(img);
      $("logo").hidden = false;
    }

    const qr = $("qr");
    qr.addEventListener("error", function () { $("bloc-qr").hidden = true; });
    qr.src = "/portail/" + encodeURIComponent(slug) + "/qrcode";
    $("bloc-qr").hidden = false;
  }

  /* ---------- Horloge ---------- */

  function majHorloge() {
    const maintenant = new Date();
    $("heure").textContent = I18N.formaterHeureSecondes(maintenant);
    const jour = I18N.formaterJourComplet(maintenant);
    $("jour").textContent = jour.charAt(0).toUpperCase() + jour.slice(1);
  }

  /* ---------- Objets ---------- */

  function quand(iso) {
    const d = new Date(iso), auj = new Date();
    const ecart = Math.round((new Date(auj.getFullYear(), auj.getMonth(), auj.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    if (ecart <= 0) return t("trouve.auj");
    if (ecart === 1) return t("trouve.hier");
    if (ecart < 7) return t("trouve.jours", { n: ecart });
    return t("trouve.le", { date: I18N.formaterJour(d) });
  }

  function carte(objet) {
    const c = el("article", "carte");
    const photo = el("div", "carte__photo");
    if (estImage(objet.photo_url)) {
      photo.classList.add("cadre-photo");
      photo.style.setProperty("--photo", 'url("' + String(objet.photo_url).replace(/["'()\\\s]/g, function (c) { return "%" + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"); }) + '")');
      const img = el("img");
      img.alt = "";
      img.src = objet.photo_url;
      img.addEventListener("error", function () { img.remove(); photo.classList.remove("cadre-photo"); photo.appendChild(icone(objet.categorie)); });
      photo.appendChild(img);
    } else {
      photo.appendChild(icone(objet.categorie));
    }
    c.appendChild(photo);
    const texte = el("div", "carte__texte");
    texte.appendChild(el("p", "carte__categorie", I18N.categorie(objet.categorie)));
    texte.appendChild(el("p", "carte__quand", quand(objet.date_heure_decouverte)));
    if (objet.type_emplacement === "vehicule" || objet.type_emplacement === "locaux") {
      texte.appendChild(el("p", "carte__lieu", t("emplacement." + objet.type_emplacement)));
    }
    c.appendChild(texte);
    return c;
  }

  function nombrePages() { return Math.max(1, Math.ceil(objets.length / PAR_PAGE)); }

  /* Met en valeur l'objet « zoom » et atténue légèrement les autres. Avec un seul objet, rien à faire. */
  function appliquerZoom() {
    const cartes = $("grille").children;
    for (let i = 0; i < cartes.length; i++) {
      const actif = cartes.length > 1 && i === zoom;
      cartes[i].classList.toggle("carte--zoom", actif);
      cartes[i].classList.toggle("carte--attenuee", cartes.length > 1 && !actif);
    }
  }

  function dessinerPastilles() {
    const zone = vider($("pastilles"));
    const n = nombrePages();
    if (n < 2) return;
    for (let i = 0; i < n; i++) zone.appendChild(el("span", "pastille" + (i === page ? " active" : "")));
  }

  function remplirScene() {
    const grille = $("grille"), vide = $("accueil-vide");
    const t = textes();
    if (!consultationOuverte || !objets.length) {
      grille.hidden = true;
      vide.hidden = false;
      $("vide-titre").textContent = consultationOuverte ? t.videTitre : t.fermeTitre;
      $("vide-texte").textContent = consultationOuverte ? t.videTexte : t.fermeTexte;
      dessinerPastilles();
      return;
    }
    vide.hidden = true;
    grille.hidden = false;
    const visibles = objets.slice(page * PAR_PAGE, page * PAR_PAGE + PAR_PAGE);
    vider(grille);
    grille.setAttribute("data-n", String(visibles.length));
    visibles.forEach(function (o) { grille.appendChild(carte(o)); });
    if (zoom >= visibles.length) zoom = 0;
    appliquerZoom();
    dessinerPastilles();
  }

  /* Fondu de sortie, changement de contenu, fondu d'entrée. */
  function afficherPage(avecFondu) {
    const grille = $("grille");
    if (!avecFondu) { remplirScene(); return; }
    grille.classList.add("sort");
    setTimeout(function () {
      if (langueEnAttente) { const code = langueEnAttente; langueEnAttente = null; I18N.choisir(code, false); } // redessine via l'événement
      else remplirScene();
      grille.classList.remove("sort");
    }, 560);
  }

  /* Toutes les 5 secondes : objet suivant. Quand on a fait le tour de la page, on passe à la page suivante
     (s'il y en a une) : 6 objets x 5 secondes = 30 secondes par page. */
  function avancer() {
    const surLaPage = Math.min(PAR_PAGE, objets.length - page * PAR_PAGE);
    zoom += 1;
    if (zoom >= surLaPage) {
      zoom = 0;
      const dernierePage = page >= nombrePages() - 1;
      if (nombrePages() > 1) page = (page + 1) % nombrePages();
      // Tous les objets ont défilé : on passe à la langue suivante.
      if (dernierePage && langues.length > 1) { rang = (rang + 1) % langues.length; langueEnAttente = langues[rang]; }
      if (nombrePages() > 1 || langueEnAttente) {
        afficherPage(true);
        return;
      }
    }
    appliquerZoom();
  }

  function planifier() {
    clearInterval(minuteur);
    minuteur = null;
    if (consultationOuverte && objets.length > 1) minuteur = setInterval(avancer, DUREE_ZOOM_MS);
  }

  async function rafraichir() {
    try {
      const recus = await lireJson("/portail/" + encodeURIComponent(slug) + "/objets");
      consultationOuverte = true;
      $("hors-ligne").hidden = true;
      const nouvelle = recus.map(function (o) { return o.id; }).join(",");
      if (nouvelle !== signature || !$("ecran").dataset.pret) {
        signature = nouvelle;
        objets = recus;
        if (page >= nombrePages()) page = 0;
        zoom = 0;
        afficherPage(!!$("ecran").dataset.pret);
        planifier();
      }
    } catch (e) {
      if (e.status === 403) {
        // L'organisation n'expose pas ses objets : l'écran ne montre que l'invitation à déclarer.
        if (consultationOuverte || !$("ecran").dataset.pret) {
          consultationOuverte = false;
          objets = []; signature = "";
          afficherPage(false);
          planifier();
        }
        $("hors-ligne").hidden = true;
      } else {
        $("hors-ligne").hidden = false; // connexion perdue : on garde ce qui est déjà affiché
      }
    }
    $("ecran").dataset.pret = "1";
  }

  /* ---------- Confort d'un écran de hall ---------- */

  function basculerPleinEcran() {
    if (document.fullscreenElement) document.exitFullscreen(); else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
  }
  document.addEventListener("keydown", function (e) { if (e.key === "f" || e.key === "F") basculerPleinEcran(); });
  document.addEventListener("dblclick", basculerPleinEcran);

  let minuteurCurseur = null;
  document.addEventListener("mousemove", function () {
    document.body.classList.add("curseur");
    clearTimeout(minuteurCurseur);
    minuteurCurseur = setTimeout(function () { document.body.classList.remove("curseur"); }, 3000);
  });

  async function garderEcranAllume() {
    try { if (navigator.wakeLock) await navigator.wakeLock.request("screen"); } catch (e) { /* non pris en charge : sans gravité */ }
  }
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") garderEcranAllume(); });

  /* ---------- Démarrage ---------- */

  async function demarrer() {
    try {
      org = await lireJson("/organisations/par-slug/" + encodeURIComponent(slug));
    } catch (e) {
      $("chargement").textContent = e.status === 404 ? t("erreur.org_inconnue") : t("erreur.reseau");
      if (e.status !== 404) setTimeout(demarrer, 10000);
      return;
    }
    I18N.definirContexte({ secteur: org.secteur === "transport" ? "transport" : "education" });
    try { enregistrerCategoriesPerso(await lireJson("/portail/" + encodeURIComponent(slug) + "/categories/personnalisees")); } catch (e) { /* sans gravité : la liste standard suffit */ }
    appliquerTheme();
    $("chargement").hidden = true;
    $("ecran").hidden = false;
    majHorloge();
    setInterval(majHorloge, 1000);
    await rafraichir();
    setInterval(rafraichir, RAFRAICHIR_MS);
    setTimeout(function () { $("indice").classList.add("cache"); }, 12000);
    setTimeout(function () { location.reload(); }, RECHARGER_PAGE_MS);
    garderEcranAllume();

    // Alternance des langues, au rythme du défilement (seulement si plusieurs ont été demandées dans l'adresse).
    if (langues.length > 1) {
      setInterval(function () {
        if (objets.length > 1 && consultationOuverte) return; // le défilement décide lui-même
        rang = (rang + 1) % langues.length;
        langueEnAttente = langues[rang];
        afficherPage(true);
      }, LANGUE_MS);
    }
  }

  document.addEventListener("tsintuwa:langue", function () {
    if (!org) return;
    textesFixes();
    majHorloge();
    remplirScene();
  });

  demarrer();
})();
