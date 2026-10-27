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
    "telephone": "M9.5 2h5A2.5 2.5 0 0 1 17 4.5v15a2.5 2.5 0 0 1-2.5 2.5h-5A2.5 2.5 0 0 1 7 19.5v-15A2.5 2.5 0 0 1 9.5 2zM11 18.5h2",
    "portefeuille": "M3 7.5A2.5 2.5 0 0 1 5.5 5H18a1 1 0 0 1 1 1v2M3 7.5V17a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1H5.5A2.5 2.5 0 0 1 3 7.5zM16 13.5h.01",
    "cles": cercle(8, 15, 4) + "M10.85 12.15L19 4M18 5l3 3M15 8l2 2",
    "sac": "M6 8h12l1 12H5L6 8zM9 8V6a3 3 0 0 1 6 0v2",
    "documents": "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM14 3v5h5M9 13h6M9 17h6",
    "carte bancaire": "M4.5 5h15A2.5 2.5 0 0 1 22 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-15A2.5 2.5 0 0 1 2 16.5v-9A2.5 2.5 0 0 1 4.5 5zM2 10h20M6 15h4",
    "vetement": "M9 3L3 6l2.2 4.2L8 9v12h8V9l2.8 1.2L21 6l-6-3a3 3 0 0 1-6 0z",
    "lunettes": cercle(6.5, 14, 3.5) + cercle(17.5, 14, 3.5) + "M10 14h4M3 14l2-7M21 14l-2-7",
    "ordinateur": "M5 5h14a1 1 0 0 1 1 1v9H4V6a1 1 0 0 1 1-1zM2 19h20",
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
    "kit de maintenance et robotique": cercle(12, 12, 3) + "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2",
    "autre": "M21 8l-9-5-9 5v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8"
  };

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
