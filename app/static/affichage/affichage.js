/*
  Écran d'affichage du hall — Étape 13.
  Cette page ne demande rien à la personne qui la regarde : elle lit l'identifiant de l'organisation
  dans l'adresse (/iat/affichage), reprend ses couleurs, puis affiche en boucle les objets trouvés.

  Ce qu'elle fait toute seule :
  - recharge la liste toutes les minutes (un objet rendu disparaît, un objet nouveau apparaît) ;
  - fait défiler les objets par groupes de 6 quand il y en a davantage ;
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
  const DUREE_PAGE_MS = 15000;
  const RAFRAICHIR_MS = 60000;
  const RECHARGER_PAGE_MS = 6 * 60 * 60 * 1000;

  let org = null;
  let objets = [];
  let signature = "";
  let consultationOuverte = true;
  let page = 0;
  let minuteur = null;

  const $ = (id) => document.getElementById(id);

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
    if (org.secteur === "transport") {
      return {
        sous: "Objets trouvés dans nos véhicules et nos gares",
        aide: "Scannez le code pour le déclarer depuis votre téléphone. Pour récupérer un objet, présentez-vous à l'agence avec une pièce d'identité.",
        videTitre: "Aucun objet à réclamer pour le moment",
        videTexte: "Un objet oublié pendant un voyage ? Déclarez-le : nous vous préviendrons dès qu'il sera retrouvé.",
        fermeTitre: "Un objet oublié pendant votre voyage ?",
        fermeTexte: "Déclarez-le avec le code ci-dessous, ou adressez-vous à l'agence : nous le comparerons aux objets retrouvés.",
        dans: { vehicule: "Trouvé dans un véhicule", locaux: "Trouvé en gare ou en agence" }
      };
    }
    return {
      sous: "Objets trouvés dans l'établissement",
      aide: "Scannez le code pour le déclarer depuis votre téléphone. Pour récupérer un objet, présentez-vous à l'accueil avec une pièce d'identité.",
      videTitre: "Aucun objet à réclamer pour le moment",
      videTexte: "Vous avez perdu quelque chose ? Déclarez-le : nous vous préviendrons dès qu'il sera retrouvé.",
      fermeTitre: "Un objet perdu dans l'établissement ?",
      fermeTexte: "Déclarez-le avec le code ci-dessous, ou adressez-vous à l'accueil : nous le comparerons aux objets retrouvés.",
      dans: { vehicule: "Trouvé dans un véhicule", locaux: "Trouvé dans l'établissement" }
    };
  }

  /* ---------- Habillage ---------- */

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
    document.title = org.nom + " — Objets trouvés";

    $("nom-org").textContent = org.nom;
    $("sous-titre").textContent = textes().sous;
    $("pied-aide").textContent = textes().aide;

    if (estImage(org.logo_url)) {
      const img = el("img");
      img.alt = "Logo de " + org.nom;
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

  const formatHeure = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const formatJour = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  function majHorloge() {
    const maintenant = new Date();
    $("heure").textContent = formatHeure.format(maintenant);
    const jour = formatJour.format(maintenant);
    $("jour").textContent = jour.charAt(0).toUpperCase() + jour.slice(1);
  }

  /* ---------- Objets ---------- */

  function quand(iso) {
    const d = new Date(iso), auj = new Date();
    const ecart = Math.round((new Date(auj.getFullYear(), auj.getMonth(), auj.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    if (ecart <= 0) return "Trouvé aujourd'hui";
    if (ecart === 1) return "Trouvé hier";
    if (ecart < 7) return "Trouvé il y a " + ecart + " jours";
    return "Trouvé le " + new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" }).format(d);
  }

  function carte(objet) {
    const c = el("article", "carte");
    const photo = el("div", "carte__photo");
    if (estImage(objet.photo_url)) {
      const img = el("img");
      img.alt = "";
      img.src = objet.photo_url;
      img.addEventListener("error", function () { img.remove(); photo.appendChild(icone(objet.categorie)); });
      photo.appendChild(img);
    } else {
      photo.appendChild(icone(objet.categorie));
    }
    c.appendChild(photo);
    const texte = el("div", "carte__texte");
    texte.appendChild(el("p", "carte__categorie", objet.categorie));
    texte.appendChild(el("p", "carte__quand", quand(objet.date_heure_decouverte)));
    const lieu = textes().dans[objet.type_emplacement];
    if (lieu) texte.appendChild(el("p", "carte__lieu", lieu));
    c.appendChild(texte);
    return c;
  }

  function nombrePages() { return Math.max(1, Math.ceil(objets.length / PAR_PAGE)); }

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
    dessinerPastilles();
  }

  /* Fondu de sortie, changement de contenu, fondu d'entrée. */
  function afficherPage(avecFondu) {
    const grille = $("grille");
    if (!avecFondu) { remplirScene(); return; }
    grille.classList.add("sort");
    setTimeout(function () { remplirScene(); grille.classList.remove("sort"); }, 560);
  }

  function planifier() {
    clearInterval(minuteur);
    minuteur = null;
    if (nombrePages() > 1 && consultationOuverte) {
      minuteur = setInterval(function () {
        page = (page + 1) % nombrePages();
        afficherPage(true);
      }, DUREE_PAGE_MS);
    }
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
      $("chargement").textContent = e.status === 404 ? "Cette adresse ne correspond à aucune organisation." : "Connexion impossible. Nouvelle tentative dans un instant…";
      if (e.status !== 404) setTimeout(demarrer, 10000);
      return;
    }
    appliquerTheme();
    $("chargement").hidden = true;
    $("ecran").hidden = false;
    majHorloge();
    setInterval(majHorloge, 20000);
    await rafraichir();
    setInterval(rafraichir, RAFRAICHIR_MS);
    setTimeout(function () { $("indice").classList.add("cache"); }, 12000);
    setTimeout(function () { location.reload(); }, RECHARGER_PAGE_MS);
    garderEcranAllume();
  }

  demarrer();
})();
