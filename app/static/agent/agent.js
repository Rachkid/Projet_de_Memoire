/*
  Interface des agents — Étape 12.
  Une seule page pour toutes les organisations : elle lit l'identifiant court dans l'adresse
  (/iat/agent), demande l'habillage à l'API, puis fait travailler l'agent avec les routes
  déjà protégées par le serveur (jeton de connexion).

  Rappels de sécurité :
  - tout texte venant du serveur passe par textContent (jamais innerHTML) : un nom d'objet ou
    de personne ne peut pas injecter de code dans la page ;
  - le jeton de connexion est gardé dans sessionStorage : il disparaît à la fermeture de l'onglet,
    ce qui protège un poste partagé à l'accueil ;
  - l'interface ne décide de rien : les droits (enregistrement, restitution) et l'isolation entre
    organisations sont vérifiés par le serveur à chaque requête. Masquer un bouton n'est que du confort.
*/
(function () {
  "use strict";

  const slug = (location.pathname.split("/").filter(Boolean)[0] || "").toLowerCase();
  const CLE_JETON = "retrova_jeton_" + slug;
  const CATEGORIES_SECOURS = ["Téléphone", "Portefeuille", "Clés", "Sac", "Documents", "Carte bancaire", "Vêtement",
    "Lunettes", "Ordinateur", "Écouteurs", "Montre", "Bijou", "Livre ou cahier", "Autre"];
  const STATUTS = { en_attente: "En attente", reclame: "Réclamé", restitue: "Restitué", archive: "Archivé" };
  const ROLES = { agent: "Agent", administrateur: "Administrateur", super_administrateur: "Super-administrateur" };
  const PIECES = ["Carte d'identité", "Passeport", "Carte d'étudiant", "Permis de conduire", "Autre"];

  let org = null;
  let jeton = null;
  let moi = null;
  let categories = null;
  let objetsCharges = [];
  let filtreStatut = "en_attente";
  let dernierObjet = null;     // objet qui vient d'être enregistré
  let derniereRemise = null;   // texte de la dernière remise
  let photoObjet = null;       // photo réduite en attente d'envoi
  let photoObjetUrl = null;    // URL déjà envoyée au serveur (évite de renvoyer la photo si on réessaie)
  let objetCourant = null;     // objet affiché dans la fiche ou la restitution
  let candidats = [];

  const $ = (id) => document.getElementById(id);

  /* ---------- Outils ---------- */

  function el(tag, classe, texte) {
    const n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  function vider(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }

  function lireJeton() { try { return sessionStorage.getItem(CLE_JETON); } catch (e) { return null; } }
  function ecrireJeton(v) {
    try { if (v) sessionStorage.setItem(CLE_JETON, v); else sessionStorage.removeItem(CLE_JETON); } catch (e) { /* stockage bloqué : la session durera le temps de la page */ }
  }

  function messageErreur(donnees, statut) {
    if (statut >= 500) return "Le service est momentanément indisponible. Réessayez dans un instant.";
    if (donnees && typeof donnees.detail === "string") return donnees.detail;
    if (donnees && Array.isArray(donnees.detail) && donnees.detail[0] && donnees.detail[0].msg) {
      return "Une information n'est pas valable : " + donnees.detail[0].msg;
    }
    return "Une erreur est survenue (code " + statut + "). Réessayez dans un instant.";
  }

  /* corps : objet (JSON), FormData (fichier) ou chaîne (formulaire de connexion) */
  async function api(methode, chemin, corps, options) {
    options = options || {};
    const entetes = { Accept: options.blob ? "*/*" : "application/json" };
    if (jeton) entetes.Authorization = "Bearer " + jeton;
    const requete = { method: methode, headers: entetes };
    if (corps instanceof FormData) {
      requete.body = corps;
    } else if (typeof corps === "string") {
      entetes["Content-Type"] = "application/x-www-form-urlencoded";
      requete.body = corps;
    } else if (corps !== undefined) {
      entetes["Content-Type"] = "application/json";
      requete.body = JSON.stringify(corps);
    }
    let reponse;
    try {
      reponse = await fetch(chemin, requete);
    } catch (e) {
      const erreur = new Error("Connexion impossible. Vérifiez votre connexion internet puis réessayez.");
      erreur.status = 0;
      throw erreur;
    }
    if (options.blob && reponse.ok) return reponse.blob();
    const texte = await reponse.text();
    let donnees = null;
    try { donnees = texte ? JSON.parse(texte) : null; } catch (e) { donnees = null; }
    if (!reponse.ok) {
      if (reponse.status === 401 && jeton && !options.sansDeconnexion) {
        deconnecter("Votre session a expiré. Reconnectez-vous.");
      }
      const erreur = new Error(messageErreur(donnees, reponse.status));
      erreur.status = reponse.status;
      throw erreur;
    }
    return donnees;
  }

  function estImage(url) {
    return typeof url === "string" && (url.charAt(0) === "/" || /^https?:\/\//i.test(url));
  }

  const formatDateHeure = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const formatJour = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric" });

  function dateHeure(iso) { return formatDateHeure.format(new Date(iso)); }

  function normaliserTelephone(brut) {
    let t = brut.replace(/[\s.\-()]/g, "");
    if (t.indexOf("00") === 0) t = "+" + t.slice(2);
    if (t.charAt(0) === "+") return /^\+\d{8,15}$/.test(t) ? t : null;
    if (/^\d{8}$/.test(t)) return "+227" + t;
    if (/^227\d{8}$/.test(t)) return "+" + t;
    return null;
  }

  function afficherTelephone(t) {
    const m = /^\+227(\d{2})(\d{2})(\d{2})(\d{2})$/.exec(t);
    return m ? "+227 " + m.slice(1).join(" ") : t;
  }

  function montrerErreur(id, message) {
    const n = $(id);
    if (!message) { n.hidden = true; n.textContent = ""; return; }
    n.textContent = message;
    n.hidden = false;
  }

  function lienTel(telephone) {
    const a = el("a", "tel", afficherTelephone(telephone));
    a.href = "tel:" + telephone;
    return a;
  }

  function aDroit(nom) { return !!(moi && moi[nom]); }
  function estAdmin() { return !!(moi && (moi.role === "administrateur" || moi.role === "super_administrateur")); }

  /* Icônes au trait (viewBox 24). Une catégorie = un dessin : l'agent reconnaît l'objet d'un coup d'œil,
     même quand l'objet n'a pas de photo. */
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
    "autre": "M21 8l-9-5-9 5v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8",
    "recherche": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5"
  };

  function cleIcone(categorie) {
    const c = (categorie || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
    return ICONES[c] ? c : "autre";
  }

  function icone(cle) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", ICONES[cle] || ICONES.autre);
    svg.appendChild(p);
    return svg;
  }

  /* État vide : une carte avec une icône, pas un cadre en pointillés. */
  function vide(texte, cle) {
    const n = el("div", "vide");
    const pastille = el("span", "vide__icone");
    pastille.appendChild(icone(cle || "autre"));
    n.appendChild(pastille);
    n.appendChild(el("span", null, texte));
    return n;
  }

  /* Vignette d'une photo ; sans photo (ou photo introuvable), l'icône de la catégorie prend sa place. */
  function vignette(url, classeImage, categorie) {
    const cle = cleIcone(categorie);
    function remplacant() {
      const v = el("div", "carte__vide");
      v.appendChild(icone(cle));
      return v;
    }
    if (estImage(url)) {
      const img = el("img", classeImage);
      img.alt = "";
      img.loading = "lazy";
      img.src = url;
      img.addEventListener("error", function () { if (img.parentNode) img.parentNode.replaceChild(remplacant(), img); });
      return img;
    }
    return remplacant();
  }

  function photoCarte(url, categorie) {
    const zone = el("div", "objet-carte__photo");
    const cle = cleIcone(categorie);
    if (estImage(url)) {
      const img = el("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = url;
      img.addEventListener("error", function () { img.remove(); zone.appendChild(icone(cle)); });
      zone.appendChild(img);
    } else {
      zone.appendChild(icone(cle));
    }
    return zone;
  }

  function jourRelatif(iso) {
    const d = new Date(iso), auj = new Date();
    const ecart = Math.round((new Date(auj.getFullYear(), auj.getMonth(), auj.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    const heure = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    if (ecart <= 0) return "Aujourd'hui à " + heure;
    if (ecart === 1) return "Hier à " + heure;
    if (ecart < 7) return "Il y a " + ecart + " jours";
    return formatJour.format(d);
  }

  function badgeStatut(statut) {
    const b = el("span", "badge", STATUTS[statut] || statut);
    if (statut === "en_attente") b.classList.add("badge--vif");
    if (statut === "archive") b.classList.add("badge--gris");
    return b;
  }

  function ligneInfo(parent, titre, valeur) {
    const d = el("div");
    d.appendChild(el("dt", null, titre));
    const dd = el("dd");
    if (valeur instanceof Node) dd.appendChild(valeur); else dd.textContent = valeur;
    d.appendChild(dd);
    parent.appendChild(d);
  }

  function libelleEmplacement(valeur) {
    const transport = org && org.secteur === "transport";
    if (valeur === "vehicule") return transport ? "Dans un véhicule" : "Dans un véhicule";
    if (valeur === "locaux") return transport ? "En gare ou en agence" : "Dans l'établissement";
    return "";
  }

  /* ---------- Photos : réduction avant envoi ---------- */

  /* Une photo de téléphone pèse plusieurs Mo : on la réduit (1600 px, JPEG) dans le navigateur
     avant l'envoi, ce qui la rend légère même sur une connexion mobile lente. Si le navigateur
     ne sait pas la lire, on envoie le fichier tel quel : le serveur le vérifiera de toute façon. */
  async function reduirePhoto(fichier) {
    const MAX = 1600;
    try {
      let source, largeur, hauteur;
      if (window.createImageBitmap) {
        source = await createImageBitmap(fichier, { imageOrientation: "from-image" });
        largeur = source.width; hauteur = source.height;
      } else {
        source = await new Promise(function (ok, ko) {
          const img = new Image();
          const url = URL.createObjectURL(fichier);
          img.onload = function () { URL.revokeObjectURL(url); ok(img); };
          img.onerror = function () { URL.revokeObjectURL(url); ko(new Error("illisible")); };
          img.src = url;
        });
        largeur = source.naturalWidth; hauteur = source.naturalHeight;
      }
      const echelle = Math.min(1, MAX / Math.max(largeur, hauteur));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(largeur * echelle);
      canvas.height = Math.round(hauteur * echelle);
      canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise(function (ok) { canvas.toBlob(ok, "image/jpeg", 0.82); });
      return blob || fichier;
    } catch (e) {
      return fichier;
    }
  }

  function envoyerPhoto(chemin, blob) {
    const donnees = new FormData();
    donnees.append("fichier", blob, "photo.jpg");
    return api("POST", chemin, donnees).then(function (r) { return r.photo_url; });
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
    if (meta) meta.setAttribute("content", t.principale);
    document.title = "Espace agent — " + org.nom;

    if (estImage(org.fond_url)) racine.setProperty("--fond-image", 'url("' + org.fond_url + '")');
    $("haut-org").textContent = org.nom;
    $("connexion-org").textContent = org.nom;
    $("lien-public").href = "/" + slug;

    const plaque = vider($("connexion-plaque"));
    const logo = $("haut-logo");
    if (estImage(org.logo_url)) {
      const img = el("img");
      img.alt = "Logo de " + org.nom;
      img.src = org.logo_url;
      plaque.appendChild(img);
      const img2 = el("img");
      img2.alt = "";
      img2.src = org.logo_url;
      vider(logo).appendChild(img2);
      logo.hidden = false;
    } else {
      plaque.hidden = true;
    }
  }

  /* ---------- Affichage des vues ---------- */

  const VUES = ["connexion", "objets", "nouveau", "enregistre", "fiche", "restituer", "remis", "pertes", "compte"];

  function afficherVue(nom, titreId) {
    VUES.forEach(function (v) { $("vue-" + v).hidden = (v !== nom); });
    const connecte = nom !== "connexion";
    $("haut").hidden = !connecte;
    $("onglets").hidden = !connecte;
    document.body.classList.toggle("hors-session", !connecte);
    const cible = { objets: "objets", nouveau: "nouveau", enregistre: "nouveau", fiche: "objets", restituer: "objets", remis: "objets", pertes: "pertes" }[nom];
    document.querySelectorAll("#onglets a").forEach(function (a) {
      if (a.getAttribute("data-vue") === cible) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    window.scrollTo(0, 0);
    const titre = $(titreId);
    if (titre) titre.focus({ preventScroll: true });
  }

  function aller(hash) {
    if (location.hash === hash) router(); else location.hash = hash;
  }

  function router() {
    if (!org) return;
    const hash = location.hash.replace(/^#/, "");
    const morceaux = hash.split("/");
    const page = morceaux[0];

    if (!moi) { montrerConnexion(); return; }

    if (page === "" || page === "connexion") { aller("#objets"); return; }
    if (page === "objets") return pageObjets();
    if (page === "nouveau") return pageNouveau();
    if (page === "enregistre") return dernierObjet ? pageEnregistre() : aller("#objets");
    if (page === "objet" && morceaux[1]) return pageFiche(morceaux[1]);
    if (page === "restituer" && morceaux[1]) return pageRestituer(morceaux[1]);
    if (page === "remis") return derniereRemise ? pageRemis() : aller("#objets");
    if (page === "pertes") return pagePertes();
    if (page === "compte") return pageCompte();
    aller("#objets");
  }

  /* ---------- Connexion / déconnexion ---------- */

  function montrerConnexion(message) {
    afficherVue("connexion", "connexion-titre");
    montrerErreur("connexion-erreur", message || "");
    $("mot-de-passe").value = "";
  }

  function deconnecter(message) {
    jeton = null; moi = null;
    ecrireJeton(null);
    dernierObjet = null; derniereRemise = null; objetsCharges = []; objetCourant = null;
    montrerConnexion(message);
    if (location.hash !== "#connexion") history.replaceState(null, "", "#connexion");
  }

  async function ouvrirSession(nouveauJeton) {
    jeton = nouveauJeton;
    const profil = await api("GET", "/auth/moi", undefined, { sansDeconnexion: true });
    if (profil.organisation_id !== org.id) {
      jeton = null;
      throw new Error("Ce compte n'appartient pas à " + org.nom + ". Utilisez l'adresse de votre propre organisation.");
    }
    moi = profil;
    ecrireJeton(jeton);
    const compte = vider($("haut-compte"));
    const initiales = (moi.nom || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(function (m) { return m.charAt(0); }).join("").toUpperCase();
    compte.appendChild(el("span", "avatar", initiales));
    compte.appendChild(el("span", "haut__nom", moi.nom));
    $("onglet-nouveau").hidden = !aDroit("droit_enregistrement");
  }

  $("form-connexion").addEventListener("submit", async function (e) {
    e.preventDefault();
    montrerErreur("connexion-erreur", "");
    const identifiant = $("identifiant").value.trim();
    const mdp = $("mot-de-passe").value;
    if (!identifiant || !mdp) { montrerErreur("connexion-erreur", "Saisissez votre identifiant et votre mot de passe."); return; }
    const bouton = $("connexion-envoyer");
    bouton.disabled = true;
    try {
      const corps = "username=" + encodeURIComponent(identifiant) + "&password=" + encodeURIComponent(mdp);
      const r = await api("POST", "/auth/login", corps, { sansDeconnexion: true });
      await ouvrirSession(r.access_token);
      $("mot-de-passe").value = "";
      if (location.hash === "#connexion" || !location.hash) aller("#objets"); else router();
    } catch (err) {
      montrerErreur("connexion-erreur", err.message);
    } finally {
      bouton.disabled = false;
    }
  });

  $("deconnexion").addEventListener("click", function () { deconnecter(); });

  /* ---------- Objets ---------- */

  function construireFiltres() {
    const conteneur = vider($("filtres-statut"));
    [["en_attente", "À rendre"], ["restitue", "Restitués"], ["archive", "Archivés"]].forEach(function (f) {
      const lab = el("label", "puce");
      const inp = el("input");
      inp.type = "radio"; inp.name = "statut"; inp.value = f[0]; inp.checked = filtreStatut === f[0];
      inp.addEventListener("change", function () { filtreStatut = f[0]; chargerObjets(); });
      lab.appendChild(inp);
      lab.appendChild(el("span", null, f[1]));
      conteneur.appendChild(lab);
    });
  }

  async function pageObjets() {
    afficherVue("objets", "objets-titre");
    const prenom = (moi.nom || "").split(" ")[0];
    $("salut").textContent = "Bonjour" + (prenom ? ", " + prenom : "") + " · " + new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
    construireFiltres();
    await chargerObjets();
  }

  async function chargerObjets() {
    const etat = $("objets-etat");
    vider($("objets-liste"));
    etat.textContent = "Chargement…";
    try {
      objetsCharges = await api("GET", "/objets/?statut=" + encodeURIComponent(filtreStatut));
      etat.textContent = "";
      dessinerObjets();
    } catch (err) {
      etat.textContent = err.message;
    }
  }

  function dessinerObjets() {
    const liste = vider($("objets-liste"));
    const etat = $("objets-etat");
    const q = $("recherche").value.trim().toLowerCase();
    const visibles = objetsCharges.filter(function (o) {
      if (!q) return true;
      return [o.categorie, o.lieu_detail || "", o.qr_code].join(" ").toLowerCase().indexOf(q) !== -1;
    });
    if (!visibles.length) {
      etat.textContent = "";
      const titre = filtreStatut === "en_attente" ? "Aucun objet à rendre pour le moment." : "Aucun objet dans cette liste.";
      liste.appendChild(vide(q ? "Aucun objet ne correspond à votre recherche." : titre, q ? "recherche" : "autre"));
      return;
    }
    etat.textContent = visibles.length + (visibles.length > 1 ? " objets" : " objet");
    visibles.forEach(function (o) {
      const a = el("a", "objet-carte");
      a.href = "#objet/" + o.id;
      const photo = photoCarte(o.photo_url, o.categorie);
      if (o.statut !== "en_attente") {
        const b = badgeStatut(o.statut);
        b.classList.add("objet-carte__statut");
        photo.appendChild(b);
      }
      a.appendChild(photo);
      const corps = el("div", "objet-carte__corps");
      corps.appendChild(el("strong", null, o.categorie));
      corps.appendChild(el("span", "objet-carte__quand", jourRelatif(o.date_heure_decouverte)));
      const lieu = [libelleEmplacement(o.type_emplacement), o.lieu_detail].filter(Boolean).join(" — ");
      if (lieu) corps.appendChild(el("span", null, lieu));
      a.appendChild(corps);
      liste.appendChild(a);
    });
  }

  $("recherche").addEventListener("input", dessinerObjets);

  /* ---------- Enregistrer un objet ---------- */

  async function chargerCategories() {
    if (categories) return categories;
    try {
      const r = await api("GET", "/portail/categories", undefined, { sansDeconnexion: true });
      categories = Array.isArray(r) && r.length ? r : CATEGORIES_SECOURS;
    } catch (e) {
      categories = CATEGORIES_SECOURS;
    }
    return categories;
  }

  function puceRadio(conteneur, nom, valeur, libelle, coche) {
    const lab = el("label", "puce");
    const inp = el("input");
    inp.type = "radio"; inp.name = nom; inp.value = valeur; inp.checked = !!coche;
    lab.appendChild(inp);
    lab.appendChild(el("span", null, libelle));
    conteneur.appendChild(lab);
    return inp;
  }

  function valeurMaintenant() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
  }

  async function pageNouveau() {
    if (!aDroit("droit_enregistrement")) { aller("#objets"); return; }
    afficherVue("nouveau", "nouveau-titre");
    const liste = await chargerCategories();
    const puces = vider($("puces"));
    liste.forEach(function (c) {
      const lab = el("label", "tuile");
      const inp = el("input");
      inp.type = "radio"; inp.name = "categorie"; inp.value = c;
      lab.appendChild(inp);
      const corps = el("span", "tuile__corps");
      const pastille = el("span", "tuile__icone");
      pastille.appendChild(icone(cleIcone(c)));
      corps.appendChild(pastille);
      corps.appendChild(el("span", null, c));
      lab.appendChild(corps);
      puces.appendChild(lab);
    });

    const transport = org.secteur === "transport";
    $("champ-emplacement").hidden = !transport;
    const pe = vider($("puces-emplacement"));
    if (transport) {
      puceRadio(pe, "emplacement", "vehicule", "Dans un véhicule", false);
      puceRadio(pe, "emplacement", "locaux", "En gare ou en agence", false);
    }
    $("form-nouveau").reset();
    $("quand").value = valeurMaintenant();
    $("quand").max = valeurMaintenant();
    retirerPhotoObjet();
    ["erreur-categorie", "erreur-quand", "nouveau-erreur"].forEach(function (id) { montrerErreur(id, ""); });
  }

  function retirerPhotoObjet() {
    photoObjet = null; photoObjetUrl = null;
    $("photo").value = "";
    $("apercu").hidden = true;
    $("photo-cible").hidden = false;
    const img = $("apercu-img");
    if (img.src && img.src.indexOf("blob:") === 0) URL.revokeObjectURL(img.src);
    img.removeAttribute("src");
  }

  $("photo").addEventListener("change", async function () {
    const fichier = this.files && this.files[0];
    if (!fichier) { retirerPhotoObjet(); return; }
    photoObjetUrl = null;
    photoObjet = await reduirePhoto(fichier);
    const img = $("apercu-img");
    if (img.src && img.src.indexOf("blob:") === 0) URL.revokeObjectURL(img.src);
    img.src = URL.createObjectURL(photoObjet);
    $("apercu").hidden = false;
    $("photo-cible").hidden = true;
  });
  $("photo-retirer").addEventListener("click", retirerPhotoObjet);

  $("photo-proprietaire").addEventListener("change", function () {
    const fichier = this.files && this.files[0];
    $("titre-proprietaire").textContent = fichier ? "Photo ajoutée : " + fichier.name : "Ajouter une photo";
    this.closest(".photo-zone").classList.toggle("photo-zone--ajoutee", !!fichier);
  });

  $("form-nouveau").addEventListener("submit", async function (e) {
    e.preventDefault();
    ["erreur-categorie", "erreur-quand", "nouveau-erreur"].forEach(function (id) { montrerErreur(id, ""); });
    const choix = document.querySelector('input[name="categorie"]:checked');
    let ok = true;
    if (!choix) { montrerErreur("erreur-categorie", "Choisissez la catégorie de l'objet."); ok = false; }
    const quand = $("quand").value;
    if (!quand) { montrerErreur("erreur-quand", "Indiquez la date et l'heure de la découverte."); ok = false; }
    else if (new Date(quand).getTime() > Date.now() + 60000) { montrerErreur("erreur-quand", "La découverte ne peut pas être dans le futur."); ok = false; }
    if (!ok) return;

    const bouton = $("nouveau-envoyer");
    bouton.disabled = true;
    try {
      if (photoObjet && !photoObjetUrl) photoObjetUrl = await envoyerPhoto("/photos/objets", photoObjet);
      const corps = { categorie: choix.value, date_heure_decouverte: new Date(quand).toISOString() };
      if (photoObjetUrl) corps.photo_url = photoObjetUrl;
      const emplacement = org.secteur === "transport" ? document.querySelector('input[name="emplacement"]:checked') : null;
      if (emplacement) corps.type_emplacement = emplacement.value;
      else if (org.secteur !== "transport") corps.type_emplacement = "locaux";
      const lieu = $("lieu").value.trim();
      if (lieu) corps.lieu_detail = lieu;
      const secret = $("detail-cache").value.trim();
      if (secret) corps.detail_cache = secret;

      dernierObjet = await api("POST", "/objets/", corps);
      retirerPhotoObjet();
      aller("#enregistre");
    } catch (err) {
      montrerErreur("nouveau-erreur", err.message);
    } finally {
      bouton.disabled = false;
    }
  });

  function pageEnregistre() {
    afficherVue("enregistre", "enregistre-titre");
    const n = dernierObjet.signalements_correspondants || 0;
    let msg = dernierObjet.categorie + " enregistré. ";
    if (n === 0) msg += "Aucune déclaration de perte ne correspond pour le moment : si quelqu'un déclare cet objet plus tard, il sera prévenu aussitôt.";
    else if (n === 1) msg += "Une personne avait déclaré un objet semblable : elle a été prévenue.";
    else msg += n + " personnes avaient déclaré un objet semblable : elles ont été prévenues.";
    $("enregistre-statut").textContent = msg;
    $("enregistre-code").textContent = dernierObjet.qr_code;
    $("enregistre-voir").href = "#objet/" + dernierObjet.id;
  }

  /* ---------- Fiche d'un objet ---------- */

  let urlQr = null;

  async function pageFiche(id) {
    afficherVue("fiche", "fiche-titre");
    const titre = $("fiche-titre");
    titre.textContent = "Chargement…";
    vider($("fiche-photo")); vider($("fiche-infos")); vider($("fiche-actions")); vider($("fiche-attente"));
    $("etiquette-img").hidden = true;
    let objet;
    try {
      objet = await api("GET", "/objets/" + encodeURIComponent(id));
    } catch (err) {
      titre.textContent = "Objet introuvable";
      $("fiche-statut").textContent = "";
      $("fiche-infos").appendChild(vide(err.message));
      return;
    }
    objetCourant = objet;
    titre.textContent = objet.categorie;
    const statut = $("fiche-statut");
    statut.textContent = STATUTS[objet.statut] || objet.statut;
    statut.className = "badge" + (objet.statut === "en_attente" ? " badge--vif" : objet.statut === "archive" ? " badge--gris" : "");

    const photo = vignette(objet.photo_url, "", objet.categorie);
    $("fiche-photo").appendChild(photo);

    const infos = $("fiche-infos");
    ligneInfo(infos, "Trouvé le", dateHeure(objet.date_heure_decouverte));
    const lieu = [libelleEmplacement(objet.type_emplacement), objet.lieu_detail].filter(Boolean).join(" — ");
    if (lieu) ligneInfo(infos, "Lieu", lieu);
    ligneInfo(infos, "Code", objet.qr_code);
    $("etiquette-code").textContent = objet.qr_code;

    const actions = $("fiche-actions");
    if (objet.statut === "en_attente" && aDroit("droit_restitution")) {
      const a = el("a", "bouton bouton--accent bouton--plein", "Remettre à son propriétaire");
      a.href = "#restituer/" + objet.id;
      actions.appendChild(a);
    }
    if ((aDroit("droit_enregistrement") || estAdmin()) && objet.statut !== "restitue" && objet.statut !== "archive") {
      const b = el("button", "bouton bouton--discret bouton--plein", "Archiver cet objet");
      b.type = "button";
      b.addEventListener("click", function () { $("confirmer").showModal(); });
      actions.appendChild(b);
    }

    chargerAttente(objet);
    chargerQr(objet);
  }

  async function chargerAttente(objet) {
    const zone = $("fiche-attente");
    if (objet.statut !== "en_attente") {
      zone.appendChild(vide("Cet objet n'est plus en attente."));
      return;
    }
    try {
      const liste = await api("GET", "/objets/" + encodeURIComponent(objet.id) + "/signalements");
      if (!objetCourant || objetCourant.id !== objet.id) return;
      vider(zone);
      if (!liste.length) { zone.appendChild(vide("Personne n'a déclaré d'objet semblable pour le moment.", "recherche")); return; }
      liste.forEach(function (s) { zone.appendChild(carteSignalement(s)); });
    } catch (err) {
      zone.appendChild(vide(err.message));
    }
  }

  async function chargerQr(objet) {
    try {
      const blob = await api("GET", "/objets/" + encodeURIComponent(objet.id) + "/qrcode", undefined, { blob: true });
      if (!objetCourant || objetCourant.id !== objet.id) return;
      if (urlQr) URL.revokeObjectURL(urlQr);
      urlQr = URL.createObjectURL(blob);
      const img = $("etiquette-img");
      img.src = urlQr;
      img.hidden = false;
    } catch (e) { /* l'étiquette est un confort : la fiche reste utilisable sans elle */ }
  }

  $("imprimer").addEventListener("click", function () { window.print(); });

  $("confirmer-non").addEventListener("click", function () { $("confirmer").close(); });
  $("confirmer-oui").addEventListener("click", async function () {
    const bouton = this;
    bouton.disabled = true;
    try {
      await api("PATCH", "/objets/" + encodeURIComponent(objetCourant.id) + "/archiver");
      $("confirmer").close();
      aller("#objets");
    } catch (err) {
      $("confirmer").close();
      $("fiche-actions").appendChild(el("p", "alerte", err.message));
    } finally {
      bouton.disabled = false;
    }
  });

  function carteSignalement(s) {
    const c = el("div", "carte carte--bloc");
    const corps = el("div", "carte__corps");
    corps.appendChild(el("strong", null, s.usager_nom || "Nom non communiqué"));
    const tel = el("span");
    tel.appendChild(lienTel(s.usager_telephone));
    corps.appendChild(tel);
    corps.appendChild(el("span", null, s.categorie + (s.description ? " — " + s.description : "")));
    const details = [];
    if (s.date_perte) details.push("Perdu le " + formatJour.format(new Date(s.date_perte + "T12:00:00")));
    if (s.lieu_approximatif) details.push(s.lieu_approximatif);
    if (details.length) corps.appendChild(el("span", null, details.join(" — ")));
    c.appendChild(corps);
    return c;
  }

  /* ---------- Restitution ---------- */

  async function pageRestituer(id) {
    if (!aDroit("droit_restitution")) { aller("#objet/" + id); return; }
    afficherVue("restituer", "restituer-titre");
    $("restituer-retour").href = "#objet/" + id;
    $("form-restituer").reset();
    $("titre-proprietaire").textContent = "Ajouter une photo";
    $("cible-proprietaire").parentNode.classList.remove("photo-zone--ajoutee");
    ["erreur-autre", "erreur-piece", "restituer-erreur"].forEach(function (i) { montrerErreur(i, ""); });
    $("bloc-autre").hidden = true;
    $("secret").textContent = "Chargement…";
    vider($("candidats"));
    $("restituer-envoyer").disabled = true;

    let objet, secret;
    try {
      objet = await api("GET", "/objets/" + encodeURIComponent(id));
      if (objet.statut !== "en_attente") {
        $("restituer-objet").textContent = "Cet objet n'est plus en attente : il ne peut pas être remis.";
        $("secret").textContent = "—";
        return;
      }
      const r = await Promise.all([
        api("GET", "/restitutions/detail-cache/" + encodeURIComponent(id)),
        api("GET", "/objets/" + encodeURIComponent(id) + "/signalements")
      ]);
      secret = r[0].detail_cache;
      candidats = r[1];
    } catch (err) {
      $("restituer-objet").textContent = err.message;
      $("secret").textContent = "—";
      return;
    }
    objetCourant = objet;
    $("restituer-objet").textContent = objet.categorie + " — trouvé le " + dateHeure(objet.date_heure_decouverte) + " (code " + objet.qr_code + ")";
    $("secret").textContent = secret ? secret : "Aucun détail secret n'a été enregistré pour cet objet : demandez une description précise (marque, couleur, contenu, signe particulier).";

    const zone = $("candidats");
    candidats.forEach(function (s, i) {
      const lab = el("label");
      const inp = el("input");
      inp.type = "radio"; inp.name = "destinataire"; inp.value = "s" + i;
      lab.appendChild(inp);
      const t = el("span");
      t.appendChild(document.createTextNode(s.usager_nom || "Nom non communiqué"));
      t.appendChild(el("small", null, afficherTelephone(s.usager_telephone) + (s.description ? " — " + s.description : "")));
      lab.appendChild(t);
      zone.appendChild(lab);
    });
    const labAutre = el("label");
    const inpAutre = el("input");
    inpAutre.type = "radio"; inpAutre.name = "destinataire"; inpAutre.value = "autre";
    labAutre.appendChild(inpAutre);
    const ta = el("span");
    ta.appendChild(document.createTextNode("Une autre personne"));
    ta.appendChild(el("small", null, "Elle n'a pas déclaré cet objet : saisissez son numéro."));
    labAutre.appendChild(ta);
    zone.appendChild(labAutre);

    const pp = vider($("puces-piece"));
    PIECES.forEach(function (p) { puceRadio(pp, "piece", p, p, false); });
    $("restituer-envoyer").disabled = false;
  }

  document.addEventListener("change", function (e) {
    if (e.target && e.target.name === "destinataire") $("bloc-autre").hidden = e.target.value !== "autre";
  });

  $("form-restituer").addEventListener("submit", async function (e) {
    e.preventDefault();
    ["erreur-autre", "erreur-piece", "restituer-erreur"].forEach(function (i) { montrerErreur(i, ""); });
    if (!objetCourant) return;

    if (!$("detail-ok").checked) {
      montrerErreur("restituer-erreur", "Cochez la case une fois la description vérifiée. Si elle ne correspond pas, ne remettez pas l'objet.");
      return;
    }
    const dest = document.querySelector('input[name="destinataire"]:checked');
    if (!dest) { montrerErreur("restituer-erreur", "Indiquez à qui vous remettez l'objet."); return; }

    let telephone = null;
    if (dest.value === "autre") {
      telephone = normaliserTelephone($("autre-tel").value);
      if (!telephone) { montrerErreur("erreur-autre", "Saisissez un numéro valable : 8 chiffres pour le Niger, ou un numéro étranger commençant par +."); return; }
    }
    const piece = document.querySelector('input[name="piece"]:checked');
    const numero = $("numero-piece").value.trim();
    if (!piece || !numero) { montrerErreur("erreur-piece", "Indiquez le type et le numéro de la pièce d'identité présentée."); return; }

    const bouton = $("restituer-envoyer");
    bouton.disabled = true;
    try {
      let usagerId, signalementId = null, nomPersonne, telPersonne;
      if (telephone) {
        const corpsUsager = { telephone: telephone };
        const nom = $("autre-nom").value.trim();
        if (nom) corpsUsager.nom = nom;
        const u = await api("POST", "/usagers/", corpsUsager);
        usagerId = u.id; nomPersonne = u.nom || nom; telPersonne = u.telephone;
      } else {
        const s = candidats[parseInt(dest.value.slice(1), 10)];
        usagerId = s.usager_id; signalementId = s.id; nomPersonne = s.usager_nom; telPersonne = s.usager_telephone;
      }

      const corps = {
        objet_id: objetCourant.id,
        usager_id: usagerId,
        detail_controle_valide: true,
        type_piece_identite: piece.value,
        numero_piece: numero
      };
      const fichier = $("photo-proprietaire").files && $("photo-proprietaire").files[0];
      if (fichier) corps.photo_proprietaire_url = await envoyerPhoto("/photos/proprietaires", await reduirePhoto(fichier));

      await api("POST", "/restitutions/", corps);

      // La personne a retrouvé son objet : on clôture sa déclaration. Si cela échoue, la remise reste valable.
      if (signalementId) { try { await api("PATCH", "/signalements/" + encodeURIComponent(signalementId) + "/cloturer"); } catch (e2) { /* sans gravité */ } }

      derniereRemise = objetCourant.categorie + " remis à " + (nomPersonne || "la personne") + " (" + afficherTelephone(telPersonne) + "), pièce présentée : " + piece.value + " n° " + numero + ".";
      objetCourant = null;
      aller("#remis");
    } catch (err) {
      montrerErreur("restituer-erreur", err.message);
    } finally {
      bouton.disabled = false;
    }
  });

  function pageRemis() {
    afficherVue("remis", "remis-titre");
    $("remis-statut").textContent = derniereRemise;
  }

  /* ---------- Déclarations de perte ---------- */

  async function pagePertes() {
    afficherVue("pertes", "pertes-titre");
    const etat = $("pertes-etat");
    const liste = vider($("pertes-liste"));
    etat.textContent = "Chargement…";
    let signalements;
    try {
      signalements = await api("GET", "/signalements/");
    } catch (err) { etat.textContent = err.message; return; }
    if (!signalements.length) { etat.textContent = ""; liste.appendChild(vide("Aucune déclaration de perte en cours.", "documents")); return; }
    etat.textContent = signalements.length + (signalements.length > 1 ? " déclarations en cours" : " déclaration en cours");
    signalements.forEach(function (s) { liste.appendChild(cartePerte(s)); });
  }

  function cartePerte(s) {
    const c = carteSignalement(s);
    const corps = c.firstChild;
    const trouve = s.statut === "correspondance_trouvee";
    const badge = el("span", "badge" + (trouve ? " badge--vif" : ""), trouve ? "Un objet correspond" : "En attente");
    corps.insertBefore(badge, corps.firstChild);

    const zone = el("div", "liste liste--simple");
    corps.appendChild(zone);
    const actions = el("div", "actions-bas");
    if (trouve) {
      const voir = el("button", "bouton bouton--discret bouton--plein", "Voir les objets qui correspondent");
      voir.type = "button";
      voir.addEventListener("click", async function () {
        voir.disabled = true;
        try {
          const objets = await api("GET", "/signalements/" + encodeURIComponent(s.id) + "/correspondances");
          vider(zone);
          if (!objets.length) zone.appendChild(vide("Cet objet a été remis ou archivé entre-temps."));
          objets.forEach(function (o) {
            const a = el("a", "carte");
            a.href = "#objet/" + o.id;
            a.appendChild(vignette(o.photo_url, "carte__vignette", o.categorie));
            const k = el("div", "carte__corps");
            k.appendChild(el("strong", null, o.categorie));
            k.appendChild(el("span", null, dateHeure(o.date_heure_decouverte)));
            a.appendChild(k);
            zone.appendChild(a);
          });
        } catch (err) { zone.appendChild(el("p", "alerte", err.message)); }
        voir.disabled = false;
      });
      actions.appendChild(voir);
    }
    const clore = el("button", "bouton bouton--discret bouton--plein", "Clôturer cette déclaration");
    clore.type = "button";
    clore.addEventListener("click", async function () {
      clore.disabled = true;
      try {
        await api("PATCH", "/signalements/" + encodeURIComponent(s.id) + "/cloturer");
        c.remove();
      } catch (err) { zone.appendChild(el("p", "alerte", err.message)); clore.disabled = false; }
    });
    actions.appendChild(clore);
    corps.appendChild(actions);
    return c;
  }

  /* ---------- Mon compte ---------- */

  function pageCompte() {
    afficherVue("compte", "compte-titre");
    const infos = vider($("compte-infos"));
    ligneInfo(infos, "Nom", moi.nom);
    ligneInfo(infos, "Identifiant", moi.identifiant || "");
    ligneInfo(infos, "Rôle", ROLES[moi.role] || moi.role);
    const droits = [];
    if (moi.droit_enregistrement) droits.push("enregistrer les objets");
    if (moi.droit_restitution) droits.push("remettre les objets");
    ligneInfo(infos, "Droits", droits.length ? "Peut " + droits.join(" et ") : "Consultation seulement");
    $("form-mdp").reset();
    montrerErreur("mdp-erreur", ""); montrerErreur("mdp-ok", "");
  }

  $("form-mdp").addEventListener("submit", async function (e) {
    e.preventDefault();
    montrerErreur("mdp-erreur", ""); montrerErreur("mdp-ok", "");
    const ancien = $("ancien-mdp").value, nouveau = $("nouveau-mdp").value;
    if (!ancien) { montrerErreur("mdp-erreur", "Saisissez votre mot de passe actuel."); return; }
    if (nouveau.length < 8) { montrerErreur("mdp-erreur", "Le nouveau mot de passe doit contenir au moins 8 caractères."); return; }
    const bouton = $("mdp-envoyer");
    bouton.disabled = true;
    try {
      await api("POST", "/auth/mot-de-passe", { ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau });
      $("form-mdp").reset();
      montrerErreur("mdp-ok", "Mot de passe modifié.");
    } catch (err) {
      montrerErreur("mdp-erreur", err.message);
    } finally {
      bouton.disabled = false;
    }
  });

  /* ---------- Démarrage ---------- */

  async function demarrer() {
    try {
      org = await api("GET", "/organisations/par-slug/" + encodeURIComponent(slug), undefined, { sansDeconnexion: true });
    } catch (err) {
      $("chargement").textContent = err.status === 404 ? "Cette adresse ne correspond à aucune organisation." : err.message;
      return;
    }
    appliquerTheme();
    $("chargement").hidden = true;
    $("app").hidden = false;

    const enregistre = lireJeton();
    if (enregistre) {
      try { await ouvrirSession(enregistre); } catch (e) { jeton = null; moi = null; ecrireJeton(null); }
    }
    window.addEventListener("hashchange", router);
    router();
  }

  demarrer();
})();
