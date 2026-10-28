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
  const CLE_JETON = "tsintuwa_jeton_" + slug;
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
  let lignesJournal = [];      // dernier journal des remises affiché (pour l'export)

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
  /* Adresse de photo à placer dans une variable CSS (l'adresse vient de notre serveur ; on neutralise quand même
     les caractères qui pourraient sortir de url("…")). */
  function urlCss(url) { return 'url("' + String(url).replace(/["'()\\\s]/g, function (c) { return "%" + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"); }) + '")'; }

  function vignette(url, classeImage, categorie) {
    const cle = cleIcone(categorie);
    function remplacant() {
      const v = el("div", "carte__vide");
      v.appendChild(icone(cle));
      return v;
    }
    if (estImage(url)) {
      const cadre = el("div", "cadre-photo" + (classeImage ? " " + classeImage : ""));
      cadre.style.setProperty("--photo", urlCss(url));
      const img = el("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = url;
      img.addEventListener("error", function () { if (cadre.parentNode) cadre.parentNode.replaceChild(remplacant(), cadre); });
      cadre.appendChild(img);
      return cadre;
    }
    return remplacant();
  }

  function photoCarte(url, categorie) {
    const zone = el("div", "objet-carte__photo");
    const cle = cleIcone(categorie);
    if (estImage(url)) {
      zone.classList.add("cadre-photo");
      zone.style.setProperty("--photo", urlCss(url));
      const img = el("img");
      img.alt = "";
      img.loading = "lazy";
      img.src = url;
      img.addEventListener("error", function () { img.remove(); zone.classList.remove("cadre-photo"); zone.appendChild(icone(cle)); });
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

  const VUES = ["connexion", "objets", "nouveau", "enregistre", "fiche", "restituer", "remis", "pertes", "bord", "historique", "journal", "compte"];

  function afficherVue(nom, titreId) {
    VUES.forEach(function (v) { $("vue-" + v).hidden = (v !== nom); });
    const connecte = nom !== "connexion";
    $("haut").hidden = !connecte;
    $("onglets").hidden = !connecte;
    document.body.classList.toggle("hors-session", !connecte);
    const cible = { objets: "objets", nouveau: "nouveau", enregistre: "nouveau", fiche: "objets", restituer: "objets", remis: "objets", pertes: "pertes", bord: "bord", historique: "historique", journal: "journal" }[nom];
    document.querySelectorAll("#onglets a").forEach(function (a) {
      if (a.getAttribute("data-vue") === cible) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    $("haut-titre").textContent = { objets: "Objets trouvés", nouveau: "Enregistrer un objet", pertes: "Déclarations", bord: "Tableau de bord", historique: "Historique", journal: "Journal d'audit", compte: "Mon compte" }[cible || (nom === "compte" ? "compte" : "")] || "";
    window.scrollTo(0, 0);
    const titre = $(titreId);
    if (titre) titre.focus({ preventScroll: true });
  }

  /* Première page après la connexion : le tableau de bord pour un administrateur, la liste des objets sinon. */
  function pageAccueil() { return estAdmin() ? "#bord" : "#objets"; }

  function aller(hash) {
    if (location.hash === hash) router(); else location.hash = hash;
  }

  function router() {
    if (!org) return;
    const hash = location.hash.replace(/^#/, "");
    const morceaux = hash.split("/");
    const page = morceaux[0];

    if (!moi) { montrerConnexion(); return; }

    // Étape 16 : mot de passe provisoire : seule la page « Mon compte » est accessible, le temps d'en choisir un.
    if (moi.doit_changer_mot_de_passe) { if (page !== "compte") { aller("#compte"); return; } return pageCompte(); }

    if (page === "" || page === "connexion") { aller(pageAccueil()); return; }
    if (page === "objets") return pageObjets();
    if (page === "nouveau") return pageNouveau();
    if (page === "enregistre") return dernierObjet ? pageEnregistre() : aller("#objets");
    if (page === "objet" && morceaux[1]) return pageFiche(morceaux[1]);
    if (page === "restituer" && morceaux[1]) return pageRestituer(morceaux[1]);
    if (page === "remis") return derniereRemise ? pageRemis() : aller("#objets");
    if (page === "pertes") return pagePertes();
    if (page === "bord") return estAdmin() ? pageBord() : aller("#objets");
    if (page === "historique") return estAdmin() ? pageHistorique(morceaux[1], morceaux[2]) : aller("#objets");
    if (page === "journal") return estAdmin() ? pageJournal() : aller("#objets");
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
    arreterAlertes();
    jeton = null; moi = null;
    ecrireJeton(null);
    dernierObjet = null; derniereRemise = null; objetsCharges = []; objetCourant = null; lignesJournal = [];
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
    document.querySelectorAll("#onglets a").forEach(function (a) { a.hidden = false; });
    $("onglet-nouveau").hidden = !aDroit("droit_enregistrement");
    $("onglet-bord").hidden = !estAdmin();
    $("onglet-historique").hidden = !estAdmin();
    $("onglet-journal").hidden = !estAdmin();
    if (moi.doit_changer_mot_de_passe) {
      // Mot de passe provisoire : aucun menu, pas d'alertes (le serveur les refuserait) tant qu'il n'est pas changé.
      document.querySelectorAll("#onglets a").forEach(function (a) { a.hidden = true; });
      $("cloche").hidden = true;
    } else {
      $("cloche").hidden = false;
      demarrerAlertes();
    }
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
      if (location.hash === "#connexion" || !location.hash) aller(pageAccueil()); else router();
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

  /* Date complète et heure avec secondes, mises à jour chaque seconde (tableau de bord et liste des objets). */
  let salutPrenom = "";
  const formatDateComplete = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const formatHeureSecondes = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  function dateEtHeure() {
    const maintenant = new Date();
    const jour = formatDateComplete.format(maintenant);
    return jour.charAt(0).toUpperCase() + jour.slice(1) + " · " + formatHeureSecondes.format(maintenant);
  }
  function majHorloges() {
    const salut = $("salut"), bord = $("bord-horloge");
    if (salut && !salut.closest("[hidden]")) salut.textContent = "Bonjour" + (salutPrenom ? ", " + salutPrenom : "") + " · " + dateEtHeure();
    if (bord && !bord.closest("[hidden]")) bord.textContent = dateEtHeure();
  }
  setInterval(majHorloges, 1000);

  async function pageObjets() {
    afficherVue("objets", "objets-titre");
    const prenom = (moi.nom || "").split(" ")[0];
    salutPrenom = prenom;
    majHorloges();
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
      const r = await api("GET", "/portail/" + encodeURIComponent(slug) + "/categories", undefined, { sansDeconnexion: true });
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
      const a = boutonIcone("a", "bouton bouton--accent bouton--plein", "Remettre à son propriétaire", "M5 12h14M13 6l6 6-6 6");
      a.href = "#restituer/" + objet.id;
      actions.appendChild(a);
    }
    if ((aDroit("droit_enregistrement") || estAdmin()) && objet.statut !== "restitue" && objet.statut !== "archive") {
      const b = boutonIcone("button", "bouton bouton--danger-doux bouton--plein", "Archiver cet objet", "M3 4h18v4H3zM5 8v12h14V8M10 12h4");
      b.type = "button";
      b.addEventListener("click", function () { $("confirmer").showModal(); });
      actions.appendChild(b);
    }

    chargerAttente(objet);
    chargerFrise(objet);
    chargerQr(objet);
  }

  async function chargerFrise(objet) {
    const bloc = $("bloc-frise");
    const liste = vider($("fiche-frise"));
    bloc.hidden = true;
    if (!estAdmin()) return;
    let donnees;
    try { donnees = await api("GET", "/historique/objets/" + encodeURIComponent(objet.id)); } catch (err) { return; }
    if (!objetCourant || objetCourant.id !== objet.id) return;
    donnees.etapes.forEach(function (e) {
      const li = el("li", "frise__etape frise__etape--" + e.type);
      li.appendChild(el("strong", null, e.titre));
      li.appendChild(el("span", "frise__date", dateHeure(e.date_heure)));
      if (e.acteur) li.appendChild(el("span", null, "Par " + e.acteur));
      if (e.detail) li.appendChild(el("span", null, e.detail));
      liste.appendChild(li);
    });
    if (donnees.statut === "en_attente") {
      const li = el("li", "frise__etape frise__etape--attente");
      li.appendChild(el("strong", null, "En attente de son propriétaire"));
      liste.appendChild(li);
    } else if (donnees.statut === "archive") {
      const li = el("li", "frise__etape frise__etape--archive");
      li.appendChild(el("strong", null, "Archivé"));
      liste.appendChild(li);
    }
    bloc.hidden = false;
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
    $("bloc-matricule").hidden = org.secteur !== "education";   // le matricule n'existe que dans les écoles
    montrerErreur("erreur-matricule", "");
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
    ["erreur-autre", "erreur-piece", "erreur-matricule", "restituer-erreur"].forEach(function (i) { montrerErreur(i, ""); });
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

    const matricule = $("bloc-matricule").hidden ? "" : $("matricule").value.trim();
    if (matricule && !/^[\p{L}\p{N}_ .\-/]{1,50}$/u.test(matricule)) {
      montrerErreur("erreur-matricule", "Matricule invalide : lettres, chiffres, point, tiret ou barre oblique seulement.");
      return;
    }

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
      if (matricule) corps.matricule_etudiant = matricule;
      const fichier = $("photo-proprietaire").files && $("photo-proprietaire").files[0];
      if (fichier) corps.photo_proprietaire_url = await envoyerPhoto("/photos/proprietaires", await reduirePhoto(fichier));

      await api("POST", "/restitutions/", corps);

      // La personne a retrouvé son objet : on clôture sa déclaration. Si cela échoue, la remise reste valable.
      if (signalementId) { try { await api("PATCH", "/signalements/" + encodeURIComponent(signalementId) + "/cloturer"); } catch (e2) { /* sans gravité */ } }

      derniereRemise = objetCourant.categorie + " remis à " + (nomPersonne || "la personne") + " (" + afficherTelephone(telPersonne) + "), pièce présentée : " + piece.value + " n° " + numero + (matricule ? ", matricule " + matricule : "") + ".";
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
      const voir = boutonIcone("button", "bouton bouton--accent bouton--plein", "Voir les objets qui correspondent", "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-5-5");
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
    const clore = boutonIcone("button", "bouton bouton--doux bouton--plein", "Clôturer cette déclaration", "M5 12l5 5 9-10");
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

  /* ---------- Tableau de bord (administrateurs) ---------- */

  const SVG_NS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, texte) {
    const n = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  function formaterNombre(n) { return Number(n).toLocaleString("fr-FR"); }

  function formaterDelai(heures) {
    if (heures === null || heures === undefined) return "—";
    if (heures < 1) return "< 1 h";
    if (heures < 48) return Math.round(heures) + " h";
    return (Math.round(heures / 2.4) / 10).toLocaleString("fr-FR") + " j";
  }

  /* Bouton avec une petite icône au trait devant le texte. */
  function boutonIcone(balise, classe, texte, chemin) {
    const b = el(balise, classe);
    const dessin = svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true", class: "bouton__icone" });
    dessin.appendChild(svg("path", { d: chemin }));
    b.appendChild(dessin);
    b.appendChild(el("span", null, texte));
    return b;
  }

  function tuileChiffre(valeur, libelle, aide, vif, decor) {
    const t = el("div", "kpi" + (vif ? " kpi--vif" : ""));
    t.appendChild(el("span", "kpi__valeur", valeur));
    t.appendChild(el("span", "kpi__libelle", libelle));
    if (aide) t.appendChild(el("span", "kpi__aide", aide));
    if (decor) t.appendChild(decor);
    return t;
  }

  /* Petite courbe sans axes, dans une tuile : la tendance sur 30 jours d'un coup d'œil. */
  function miniCourbe(valeurs, description) {
    const L = 100, H = 30, maxi = Math.max(1, ...valeurs);
    const pts = valeurs.map(function (v, i) { return [valeurs.length > 1 ? (L * i) / (valeurs.length - 1) : 0, H - 2 - (v / maxi) * (H - 6)]; });
    const ligne = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
    const racine = svg("svg", { viewBox: "0 0 " + L + " " + H, preserveAspectRatio: "none", class: "kpi__courbe", role: "img", "aria-label": description });
    racine.appendChild(svg("path", { d: ligne + " L" + L + " " + H + " L0 " + H + " Z", class: "zone" }));
    racine.appendChild(svg("path", { d: ligne, class: "trait" }));
    return racine;
  }

  /* Anneau de pourcentage (taux de remise). */
  function anneau(pourcent) {
    const R = 21, C = 2 * Math.PI * R;
    const racine = svg("svg", { viewBox: "0 0 52 52", class: "kpi__anneau", "aria-hidden": "true" });
    racine.appendChild(svg("circle", { cx: 26, cy: 26, r: R, class: "piste" }));
    racine.appendChild(svg("circle", { cx: 26, cy: 26, r: R, class: "plein", "stroke-dasharray": (C * Math.max(0, Math.min(100, pourcent)) / 100).toFixed(1) + " " + C.toFixed(1) }));
    return racine;
  }

  function graphiqueJours(serie) {
    const L = 640, H = 230, gauche = 34, bas = 26, haut = 10, droite = 8;
    const maxi = Math.max(4, ...serie.map(function (j) { return Math.max(j.trouves, j.restitues); }));
    const pas = maxi <= 8 ? 2 : Math.ceil(maxi / 4);
    const sommet = Math.ceil(maxi / pas) * pas;
    const zoneL = L - gauche - droite, zoneH = H - haut - bas;
    const x = function (i) { return gauche + (zoneL / serie.length) * (i + 0.5); };
    const y = function (v) { return haut + zoneH - (v / sommet) * zoneH; };
    const racine = svg("svg", { viewBox: "0 0 " + L + " " + H, role: "img", "aria-label": "Objets trouvés et objets remis par jour sur 30 jours", class: "graphe" });
    for (let v = 0; v <= sommet; v += pas) {
      racine.appendChild(svg("line", { x1: gauche, x2: L - droite, y1: y(v), y2: y(v), class: "graphe__grille" }));
      racine.appendChild(svg("text", { x: gauche - 6, y: y(v) + 4, "text-anchor": "end", class: "graphe__texte" }, String(v)));
    }
    const largeur = Math.max(4, (zoneL / serie.length) * 0.62);
    serie.forEach(function (j, i) {
      if (j.trouves > 0) {
        const b = svg("rect", { x: x(i) - largeur / 2, y: y(j.trouves), width: largeur, height: y(0) - y(j.trouves), rx: 2, class: "graphe__barre" });
        b.appendChild(svg("title", {}, j.date.split("-").reverse().join("/") + " : " + j.trouves + " trouvé(s)"));
        racine.appendChild(b);
      }
      if (i % 5 === 0 || i === serie.length - 1) {
        const [, m, d] = j.date.split("-");
        racine.appendChild(svg("text", { x: x(i), y: H - 7, "text-anchor": "middle", class: "graphe__texte" }, d + "/" + m));
      }
    });
    const points = serie.map(function (j, i) { return x(i) + "," + y(j.restitues); }).join(" ");
    racine.appendChild(svg("polyline", { points: points, class: "graphe__ligne" }));
    serie.forEach(function (j, i) {
      if (j.restitues > 0) {
        const c = svg("circle", { cx: x(i), cy: y(j.restitues), r: 4.5, class: "graphe__point" });
        c.appendChild(svg("title", {}, j.date.split("-").reverse().join("/") + " : " + j.restitues + " remis"));
        racine.appendChild(c);
      }
    });
    return racine;
  }

  function graphiqueCategories(liste) {
    const zone = el("div", "barres");
    if (!liste.length) { zone.appendChild(vide("Aucun objet en attente.", "objets")); return zone; }
    const maxi = Math.max.apply(null, liste.map(function (c) { return c.nombre; }));
    liste.forEach(function (c, i) {
      const ligne = el("div", "barres__ligne");
      ligne.appendChild(el("span", "barres__rang" + (i < 3 ? " barres__rang--haut" : ""), String(i + 1)));
      ligne.appendChild(el("span", "barres__nom", c.categorie));
      const piste = el("span", "barres__piste");
      const rempli = el("span", "barres__rempli");
      rempli.style.width = Math.max(4, Math.round(100 * c.nombre / maxi)) + "%";
      piste.appendChild(rempli);
      ligne.appendChild(piste);
      ligne.appendChild(el("span", "barres__nombre", formaterNombre(c.nombre)));
      zone.appendChild(ligne);
    });
    return zone;
  }

  function tableauComparaison(lignes) {
    const t = vider($("tab-comparaison"));
    const tete = el("thead"), tr = el("tr");
    ["Organisation", "En attente", "Remis ce mois", "Déclarations", "Taux de remise", "Délai moyen", "À traiter"].forEach(function (n, i) {
      const th = el("th", i ? "num" : null, n); th.scope = "col"; tr.appendChild(th);
    });
    tete.appendChild(tr); t.appendChild(tete);
    const corps = el("tbody");
    lignes.forEach(function (l) {
      const ligne = el("tr");
      const premiere = el("th"); premiere.scope = "row";
      const lien = el("button", "lien", l.organisation_nom); lien.type = "button";
      lien.addEventListener("click", function () { $("bord-org").value = l.organisation_id; chargerBord(l.organisation_id); window.scrollTo(0, 0); });
      premiere.appendChild(lien); ligne.appendChild(premiere);
      [formaterNombre(l.objets_en_attente), formaterNombre(l.restitues_ce_mois), formaterNombre(l.declarations_en_cours),
        l.taux_restitution === null ? "—" : l.taux_restitution + " %", formaterDelai(l.delai_moyen_heures), formaterNombre(l.proches_fin_retention)
      ].forEach(function (v) { ligne.appendChild(el("td", "num", v)); });
      corps.appendChild(ligne);
    });
    t.appendChild(corps);
  }

  async function pageBord() {
    afficherVue("bord", "bord-titre");
    const etat = $("bord-etat");
    const super_ = moi.role === "super_administrateur";
    $("bord-choix").hidden = !super_;
    $("bloc-comparaison").hidden = true;
    $("bord-contenu").hidden = true;
    majHorloges();
    etat.textContent = "Chargement…";
    if (super_) {
      try {
        const orgs = await api("GET", "/organisations/");
        const choix = vider($("bord-org"));
        orgs.forEach(function (o) {
          const opt = el("option", null, o.nom); opt.value = o.id; if (o.id === moi.organisation_id) opt.selected = true;
          choix.appendChild(opt);
        });
      } catch (err) { etat.textContent = err.message; return; }
    }
    await chargerBord(super_ ? $("bord-org").value : null);
    if (super_) {
      try { tableauComparaison(await api("GET", "/statistiques/comparaison")); $("bloc-comparaison").hidden = false; } catch (err) { /* la comparaison est facultative */ }
    }
  }

  $("bord-org").addEventListener("change", function () { chargerBord($("bord-org").value); });

  async function chargerBord(organisationId) {
    const etat = $("bord-etat");
    let s;
    try {
      s = await api("GET", "/statistiques/" + (organisationId ? "?organisation_id=" + encodeURIComponent(organisationId) : ""));
    } catch (err) { etat.textContent = err.message; $("bord-contenu").hidden = true; return; }
    etat.textContent = "";
    $("bord-contenu").hidden = false;
    $("bord-chapeau").textContent = s.organisation_nom + " — les chiffres sont recalculés à chaque ouverture de la page.";

    const trouvesJour = s.serie_30_jours.map(function (j) { return j.trouves; });
    const remisJour = s.serie_30_jours.map(function (j) { return j.restitues; });
    const somme = function (t) { return t.reduce(function (a, v) { return a + v; }, 0); };
    const kpis = vider($("kpis"));
    kpis.appendChild(tuileChiffre(formaterNombre(s.objets_en_attente), "Objets en attente", "À rendre à leur propriétaire", true));
    kpis.appendChild(tuileChiffre(formaterNombre(somme(trouvesJour)), "Trouvés en 30 jours", "Objets enregistrés", false,
      miniCourbe(trouvesJour, "Objets trouvés par jour sur 30 jours")));
    kpis.appendChild(tuileChiffre(formaterNombre(s.restitues_ce_mois), "Remis ce mois-ci", formaterNombre(s.objets_restitues) + " au total", false,
      miniCourbe(remisJour, "Objets remis par jour sur 30 jours")));
    kpis.appendChild(tuileChiffre(s.taux_restitution === null ? "—" : s.taux_restitution + " %", "Taux de remise", "Objets remis parmi ceux reçus", false,
      s.taux_restitution === null ? null : anneau(s.taux_restitution)));
    kpis.appendChild(tuileChiffre(formaterNombre(s.declarations_en_cours), "Déclarations en cours", "Personnes qui cherchent un objet"));
    kpis.appendChild(tuileChiffre(formaterDelai(s.delai_moyen_heures), "Délai moyen de remise", "Entre la découverte et la remise"));
    kpis.appendChild(tuileChiffre(formaterNombre(s.proches_fin_retention), "Bientôt à traiter",
      "Gardés depuis presque " + s.delai_retention_jours + " jours", s.proches_fin_retention > 0));
    kpis.appendChild(tuileChiffre(formaterNombre(s.objets_archives), "Objets archivés", "Retirés de la liste (erreur, délai dépassé)"));

    const g = vider($("graph-jours"));
    g.appendChild(graphiqueJours(s.serie_30_jours));
    const trouves = s.serie_30_jours.reduce(function (a, j) { return a + j.trouves; }, 0);
    const remis = s.serie_30_jours.reduce(function (a, j) { return a + j.restitues; }, 0);
    $("graph-jours-texte").textContent = "Sur 30 jours : " + formaterNombre(trouves) + " objet(s) trouvé(s) et " + formaterNombre(remis) + " remis.";
    vider($("graph-categories")).appendChild(graphiqueCategories(s.par_categorie));
  }

  /* ---------- Historique (administrateurs) ---------- */

  function choisirSegment(nom) {
    const journal = nom !== "personne";
    $("seg-journal").setAttribute("aria-pressed", String(journal));
    $("seg-personne").setAttribute("aria-pressed", String(!journal));
    $("panneau-journal").hidden = !journal;
    $("panneau-personne").hidden = journal;
  }
  $("seg-journal").addEventListener("click", function () { aller("#historique"); });
  $("seg-personne").addEventListener("click", function () { aller("#historique/personne"); });

  async function pageHistorique(mode, telephone) {
    afficherVue("historique", "historique-titre");
    if (mode === "personne") {
      choisirSegment("personne");
      $("pe-tel").value = telephone ? afficherTelephone(decodeURIComponent(telephone)) : "";
      montrerErreur("pe-erreur", "");
      vider($("personne-contenu")); $("personne-etat").textContent = "";
      if (telephone) chercherPersonne(decodeURIComponent(telephone));
      return;
    }
    choisirSegment("journal");
    const choixAgent = $("jr-agent");
    if (choixAgent.options.length <= 1) {
      try {
        (await api("GET", "/historique/agents")).forEach(function (a) { const o = el("option", null, a.nom); o.value = a.id; choixAgent.appendChild(o); });
      } catch (err) { /* le filtre par agent reste simplement vide */ }
    }
    chargerJournal();
  }

  function carteRemise(l) {
    const c = el("div", "carte carte--bloc remise");
    const corps = el("div", "carte__corps");
    const entete = el("a", "remise__objet", l.categorie);
    entete.href = "#objet/" + l.objet_id;
    corps.appendChild(entete);
    corps.appendChild(el("span", "remise__date", dateHeure(l.date_heure)));
    const qui = el("span");
    qui.appendChild(document.createTextNode("Remis à "));
    if (l.usager_telephone) {
      const a = el("a", null, (l.usager_nom ? l.usager_nom + " — " : "") + afficherTelephone(l.usager_telephone));
      a.href = "#historique/personne/" + encodeURIComponent(l.usager_telephone);
      qui.appendChild(a);
    } else qui.appendChild(document.createTextNode(l.usager_nom || "personne non renseignée"));
    corps.appendChild(qui);
    corps.appendChild(el("span", null, "Par " + l.agent_nom));
    corps.appendChild(el("span", null, (l.type_piece || "Pièce") + (l.numero_piece_masque ? " n° " + l.numero_piece_masque : "")));
    if (l.matricule_etudiant) corps.appendChild(el("span", null, "Matricule : " + l.matricule_etudiant));
    c.appendChild(corps);
    return c;
  }

  async function chargerJournal() {
    const etat = $("journal-etat");
    const liste = vider($("journal-liste"));
    etat.textContent = "Chargement…";
    const params = new URLSearchParams();
    if ($("jr-du").value) params.set("du", $("jr-du").value);
    if ($("jr-au").value) params.set("au", $("jr-au").value);
    if ($("jr-agent").value) params.set("agent_id", $("jr-agent").value);
    if ($("jr-q").value.trim()) params.set("q", $("jr-q").value.trim());
    let lignes;
    try { lignes = await api("GET", "/historique/remises" + (params.toString() ? "?" + params.toString() : "")); }
    catch (err) { etat.textContent = err.message; return; }
    lignesJournal = lignes;
    $("jr-export").disabled = !lignes.length;
    if (!lignes.length) { etat.textContent = ""; liste.appendChild(vide("Aucune remise ne correspond à ces critères.", "documents")); return; }
    etat.textContent = lignes.length + (lignes.length > 1 ? " remises" : " remise") + (lignes.length >= 500 ? " (les 500 plus récentes)" : "");
    lignes.forEach(function (l) { liste.appendChild(carteRemise(l)); });
  }

  $("form-journal").addEventListener("submit", function (e) { e.preventDefault(); chargerJournal(); });

  /* Export tableur : séparateur « ; » et BOM pour qu'Excel (version française) lise bien les accents.
     Une cellule qui commence par = + - @ serait prise pour une formule : on la neutralise. */
  function celluleCsv(v) {
    let t = v === null || v === undefined ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(t) && !/^[+\-]?\d[\d ]*$/.test(t)) t = "'" + t;   // un numéro (+227 96 12 34 56) reste lisible
    return '"' + t.replace(/"/g, '""') + '"';
  }

  $("jr-export").addEventListener("click", function () {
    if (!lignesJournal.length) return;
    const entete = ["Date", "Objet", "Remis à", "Téléphone", "Agent", "Pièce", "Numéro de pièce (masqué)", "Matricule"];
    const lignes = lignesJournal.map(function (l) {
      return [dateHeure(l.date_heure), l.categorie, l.usager_nom, l.usager_telephone, l.agent_nom, l.type_piece, l.numero_piece_masque, l.matricule_etudiant].map(celluleCsv).join(";");
    });
    const texte = "﻿" + [entete.map(celluleCsv).join(";")].concat(lignes).join("\r\n");
    const url = URL.createObjectURL(new Blob([texte], { type: "text/csv;charset=utf-8" }));
    const a = el("a"); a.href = url; a.download = "remises_" + slug + "_" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  });

  $("form-personne").addEventListener("submit", function (e) {
    e.preventDefault();
    montrerErreur("pe-erreur", "");
    const tel = normaliserTelephone($("pe-tel").value);
    if (!tel) { montrerErreur("pe-erreur", "Entrez un numéro valide, par exemple 90 12 34 56."); return; }
    aller("#historique/personne/" + encodeURIComponent(tel));
  });

  async function chercherPersonne(tel) {
    const etat = $("personne-etat");
    const zone = vider($("personne-contenu"));
    etat.textContent = "Recherche…";
    let r;
    try { r = await api("GET", "/historique/personnes?telephone=" + encodeURIComponent(tel)); }
    catch (err) { etat.textContent = err.message; return; }
    if (!r.trouve || (!r.declarations.length && !r.remises.length)) {
      etat.textContent = "";
      zone.appendChild(vide(r.trouve ? "Cette personne n'a aucune activité dans votre organisation." : "Aucune personne enregistrée avec ce numéro.", "documents"));
      return;
    }
    etat.textContent = "";
    const entete = el("div", "carte carte--bloc");
    const corps = el("div", "carte__corps");
    corps.appendChild(el("strong", null, r.personne.nom || "Nom non renseigné"));
    corps.appendChild(lienTel(r.personne.telephone));
    entete.appendChild(corps);
    zone.appendChild(entete);

    zone.appendChild(el("h3", "sous-titre", "Déclarations de perte (" + r.declarations.length + ")"));
    const dec = el("div", "liste liste--simple");
    if (!r.declarations.length) dec.appendChild(vide("Aucune déclaration."));
    r.declarations.forEach(function (d) {
      const c = el("div", "carte carte--bloc"), k = el("div", "carte__corps");
      k.appendChild(el("strong", null, d.categorie));
      k.appendChild(el("span", null, ({ en_attente: "En attente", correspondance_trouvee: "Un objet correspond", cloture: "Clôturée" })[d.statut] || d.statut));
      if (d.date_perte) k.appendChild(el("span", null, "Perdu le " + formatJour.format(new Date(d.date_perte + "T12:00:00"))));
      if (d.lieu_approximatif) k.appendChild(el("span", null, d.lieu_approximatif));
      if (d.description) k.appendChild(el("span", null, d.description));
      c.appendChild(k); dec.appendChild(c);
    });
    zone.appendChild(dec);

    zone.appendChild(el("h3", "sous-titre", "Objets remis à cette personne (" + r.remises.length + ")"));
    const rem = el("div", "liste liste--simple");
    if (!r.remises.length) rem.appendChild(vide("Aucun objet remis."));
    r.remises.forEach(function (l) { rem.appendChild(carteRemise(l)); });
    zone.appendChild(rem);
  }

  /* ---------- Cloche d'alertes ---------- */

  const ICONE_ALERTE = {
    correspondances: "M9 4h6l1 2h3a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h3l1-2zM9 13l2 2 4-4",
    fin_retention: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2"
  };
  let minuteurAlertes = null;
  let alertesCourantes = [];

  function cleVues() { return "tsintuwa_alertes_vues_" + slug + "_" + (moi ? moi.id : ""); }
  function lireVues() { try { return JSON.parse(localStorage.getItem(cleVues()) || "{}") || {}; } catch (e) { return {}; } }
  function ecrireVues(v) { try { localStorage.setItem(cleVues(), JSON.stringify(v)); } catch (e) { /* stockage bloqué : tout sera simplement considéré comme nouveau */ } }

  /* Ce que la personne n'a pas encore vu : pour chaque type d'alerte, la hausse depuis sa dernière lecture. */
  function nouveautes(alertes, vues) {
    const resultat = {};
    alertes.forEach(function (a) { resultat[a.type] = Math.max(a.nombre - (vues[a.type] || 0), 0); });
    return resultat;
  }

  function dessinerCloche(nouveau) {
    const total = alertesCourantes.reduce(function (a, x) { return a + (nouveau[x.type] || 0); }, 0);
    const badge = $("cloche-badge");
    badge.hidden = total === 0;
    badge.textContent = total > 99 ? "99+" : String(total);
    $("cloche").setAttribute("aria-label", total ? "Alertes : " + total + " nouvelle(s)" : "Alertes");
  }

  async function chargerAlertes() {
    if (!moi) return;
    let r;
    try { r = await api("GET", "/alertes/"); } catch (err) { return; /* la cloche est un confort : pas d'erreur affichée */ }
    if (!moi) return;
    alertesCourantes = r.alertes || [];
    // Si une alerte a diminué (traitée), on baisse la référence : la prochaine hausse comptera comme nouvelle.
    const vues = lireVues();
    let change = false;
    alertesCourantes.forEach(function (a) { if ((vues[a.type] || 0) > a.nombre) { vues[a.type] = a.nombre; change = true; } });
    Object.keys(vues).forEach(function (t) { if (!alertesCourantes.some(function (a) { return a.type === t; })) { delete vues[t]; change = true; } });
    if (change) ecrireVues(vues);
    dessinerCloche(nouveautes(alertesCourantes, vues));
    if (!$("cloche-panneau").hidden) remplirPanneau(nouveautes(alertesCourantes, vues));
  }

  function remplirPanneau(nouveau) {
    const liste = vider($("cloche-liste"));
    $("cloche-vide").hidden = alertesCourantes.length > 0;
    alertesCourantes.forEach(function (a) {
      const li = el("li");
      const lien = el("a", "alerte--" + (a.niveau === "attention" ? "attention" : "info"));
      lien.href = a.lien;
      const icone = el("span", "cloche__icone");
      const dessin = svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
      dessin.appendChild(svg("path", { d: ICONE_ALERTE[a.type] || ICONE_ALERTE.fin_retention }));
      icone.appendChild(dessin);
      lien.appendChild(icone);
      const texte = el("span", "cloche__texte");
      texte.appendChild(el("strong", null, a.titre));
      texte.appendChild(el("span", null, a.detail));
      lien.appendChild(texte);
      if (nouveau[a.type]) lien.appendChild(el("span", "cloche__nouveau"));
      lien.addEventListener("click", fermerCloche);
      li.appendChild(lien);
      liste.appendChild(li);
    });
  }

  function ouvrirCloche() {
    const nouveau = nouveautes(alertesCourantes, lireVues());
    remplirPanneau(nouveau);
    $("cloche-panneau").hidden = false;
    $("cloche").setAttribute("aria-expanded", "true");
    // Ouvrir la cloche = avoir vu : le badge repart à zéro, les pastilles rouges restent dans la liste ouverte.
    const vues = {};
    alertesCourantes.forEach(function (a) { vues[a.type] = a.nombre; });
    ecrireVues(vues);
    dessinerCloche({});
  }

  function fermerCloche() {
    $("cloche-panneau").hidden = true;
    $("cloche").setAttribute("aria-expanded", "false");
  }

  $("cloche").addEventListener("click", function (e) {
    e.stopPropagation();
    if ($("cloche-panneau").hidden) ouvrirCloche(); else fermerCloche();
  });
  document.addEventListener("click", function (e) {
    if (!$("cloche-panneau").hidden && !$("cloche-panneau").contains(e.target)) fermerCloche();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !$("cloche-panneau").hidden) { fermerCloche(); $("cloche").focus(); }
  });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) chargerAlertes(); });

  function demarrerAlertes() {
    arreterAlertes();
    chargerAlertes();
    minuteurAlertes = setInterval(function () { if (!document.hidden) chargerAlertes(); }, 60000);
  }

  function arreterAlertes() {
    if (minuteurAlertes) clearInterval(minuteurAlertes);
    minuteurAlertes = null;
    alertesCourantes = [];
    fermerCloche();
    $("cloche-badge").hidden = true;
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
    const force = !!moi.doit_changer_mot_de_passe;
    $("mdp-force").hidden = !force;
    $("ancien-mdp-libelle").textContent = force ? "Mot de passe provisoire (celui que vous avez reçu)" : "Mot de passe actuel";
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
      const r = await api("POST", "/auth/mot-de-passe", { ancien_mot_de_passe: ancien, nouveau_mot_de_passe: nouveau });
      $("form-mdp").reset();
      // Étape 16 : le serveur met fin à toutes les anciennes sessions et remet un nouveau jeton pour celle-ci.
      if (r && r.access_token) { jeton = r.access_token; ecrireJeton(jeton); }
      if (moi.doit_changer_mot_de_passe) {
        await ouvrirSession(jeton);   // recharge le profil : les menus apparaissent
        aller(pageAccueil());
        return;
      }
      montrerErreur("mdp-ok", "Mot de passe modifié. Vos autres appareils connectés ont été déconnectés.");
    } catch (err) {
      montrerErreur("mdp-erreur", err.message);
    } finally {
      bouton.disabled = false;
    }
  });

  /* ---------- Journal d'audit (administrateurs) ---------- */

  const ACTIONS_AUDIT = {
    connexion: "Connexion",
    connexion_echec: "Connexion échouée",
    connexion_bloquee: "Connexion bloquée (trop d'essais)",
    mot_de_passe_change: "Mot de passe changé",
    mot_de_passe_reinitialise: "Mot de passe réinitialisé",
    compte_cree: "Compte créé",
    compte_modifie: "Compte modifié",
    compte_desactive: "Compte désactivé",
    compte_reactive: "Compte réactivé",
    objet_archive: "Objet archivé",
    objet_archive_auto: "Archivage automatique"
  };
  const PAGE_AUDIT = 100;
  let decalageAudit = 0;

  async function pageJournal() {
    afficherVue("journal", "journal-titre");
    const choix = $("ja-action");
    if (choix.options.length <= 1) {
      Object.keys(ACTIONS_AUDIT).forEach(function (k) { const o = el("option", null, ACTIONS_AUDIT[k]); o.value = k; choix.appendChild(o); });
    }
    chargerAudit(true);
  }

  async function chargerAudit(depuisLeDebut) {
    const etat = $("audit-etat"), corps = $("audit-corps");
    if (depuisLeDebut) { decalageAudit = 0; vider(corps); }
    etat.textContent = "Chargement…";
    $("audit-plus").hidden = true;
    let r;
    try {
      const filtre = $("ja-action").value ? "&action=" + encodeURIComponent($("ja-action").value) : "";
      r = await api("GET", "/audit/?limite=" + PAGE_AUDIT + "&decalage=" + decalageAudit + filtre);
    } catch (err) { etat.textContent = err.message; return; }
    etat.textContent = r.total ? "" : "Aucune action enregistrée pour ce filtre.";
    r.lignes.forEach(function (l) {
      const tr = el("tr");
      [dateHeure(l.date_heure), ACTIONS_AUDIT[l.action] || l.action, l.acteur || "—", l.cible || "—", l.detail || "", l.adresse || ""].forEach(function (v) {
        tr.appendChild(el("td", null, v));
      });
      corps.appendChild(tr);
    });
    decalageAudit += r.lignes.length;
    $("audit-tableau").hidden = !corps.children.length;
    $("audit-plus").hidden = decalageAudit >= r.total;
  }
  $("ja-action").addEventListener("change", function () { chargerAudit(true); });
  $("audit-plus").addEventListener("click", function () { chargerAudit(false); });

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
