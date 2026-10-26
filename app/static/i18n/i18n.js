/*
  Traductions (étape 15 ter) — module commun au portail public et à l'écran du hall.

  Principe : chaque texte a une CLÉ (ex. « declarer.titre »). Chaque langue a son fichier
  (fr.js, en.js, ha.js, dje.js, ar.js) qui donne le texte de chaque clé. Pour corriger une
  traduction, on modifie seulement le fichier de la langue : aucun autre code n'est touché.

  - Une clé absente d'une langue retombe sur le français : l'écran n'est jamais vide.
  - Une clé peut avoir une variante par secteur (« .transport » ou « .education ») : le
    secteur de l'organisation est donné par definirContexte({ secteur }).
  - Les catégories d'objets (Téléphone, Sac…) sont traduites par la clé « cat.<nom sans accent> » ;
    une catégorie inconnue (ajoutée par une organisation) est affichée telle quelle.
  - La langue choisie est mémorisée dans le navigateur (localStorage). L'arabe passe la page de
    droite à gauche (dir="rtl").
*/
(function () {
  "use strict";

  var R = window.Tsintuwa = window.Tsintuwa || {};
  var CLE_STOCKAGE = "tsintuwa_langue";

  var LANGUES = [
    { code: "fr", nom: "Français", dir: "ltr", locale: "fr-FR" },
    { code: "en", nom: "English", dir: "ltr", locale: "en-GB" },
    { code: "ha", nom: "Hausa", dir: "ltr", locale: "ha" },
    { code: "dje", nom: "Zarma", dir: "ltr", locale: "dje" },
    { code: "ar", nom: "العربية", dir: "rtl", locale: "ar-u-nu-latn" }
  ];

  var dictionnaires = {};
  var courante = "fr";
  var contexte = { secteur: "" };

  function info(code) {
    for (var i = 0; i < LANGUES.length; i++) if (LANGUES[i].code === code) return LANGUES[i];
    return LANGUES[0];
  }

  function ajouter(code, textes) { dictionnaires[code] = textes; }

  function chercher(code, cle) {
    var d = dictionnaires[code];
    return d && Object.prototype.hasOwnProperty.call(d, cle) ? d[cle] : undefined;
  }

  /* Le texte d'une clé : langue courante (variante du secteur, puis texte commun), puis français.
     Renvoie undefined si aucune langue n'a cette clé. */
  function resoudre(cle, variables) {
    var codes = courante === "fr" ? ["fr"] : [courante, "fr"];
    var texte;
    for (var i = 0; i < codes.length && texte === undefined; i++) {
      if (contexte.secteur) texte = chercher(codes[i], cle + "." + contexte.secteur);
      if (texte === undefined) texte = chercher(codes[i], cle);
    }
    if (texte !== undefined && variables) {
      texte = texte.replace(/\{(\w+)\}/g, function (m, nom) { return variables[nom] !== undefined ? variables[nom] : m; });
    }
    return texte;
  }

  function t(cle, variables) {
    var texte = resoudre(cle, variables);
    return texte === undefined ? cle : texte;
  }

  function normaliser(nom) {
    return String(nom || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase().replace(/\s+/g, "_");
  }

  /* Nom d'une catégorie dans la langue courante (sinon tel quel : catégorie ajoutée par l'organisation). */
  function categorie(nom) {
    var texte = chercher(courante, "cat." + normaliser(nom));
    return texte !== undefined ? texte : nom;
  }

  var formats = {};
  function formatteur(options) {
    var cle = courante + JSON.stringify(options);
    if (!formats[cle]) {
      var locale = info(courante).locale;
      try {
        // Une langue que le navigateur ne connaît pas (ex. zarma) emprunte le format français.
        if (!Intl.DateTimeFormat.supportedLocalesOf([locale]).length) locale = "fr-FR";
        formats[cle] = new Intl.DateTimeFormat(locale, options);
      } catch (e) { formats[cle] = new Intl.DateTimeFormat("fr-FR", options); }
    }
    return formats[cle];
  }

  function formaterJour(date, avecAnnee) {
    return formatteur(avecAnnee ? { day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "long" }).format(date);
  }
  function formaterHeure(date) { return formatteur({ hour: "2-digit", minute: "2-digit" }).format(date); }
  function formaterHeureSecondes(date) { return formatteur({ hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date); }
  function formaterJourComplet(date) { return formatteur({ weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(date); }
  function formaterJourSemaine(date) { return formatteur({ weekday: "long", day: "numeric", month: "long" }).format(date); }

  /* Remplit tous les éléments marqués d'un attribut data-i18n-… sous « racine ». */
  var ATTRIBUTS = { "data-i18n-ph": "placeholder", "data-i18n-aria": "aria-label", "data-i18n-alt": "alt", "data-i18n-title": "title" };
  function appliquer(racine) {
    racine = racine || document;
    var noeuds = racine.querySelectorAll("[data-i18n]");
    for (var i = 0; i < noeuds.length; i++) {
      var texte = resoudre(noeuds[i].getAttribute("data-i18n"));
      if (texte !== undefined) noeuds[i].textContent = texte; // clé pas encore résolue (secteur inconnu) : on garde le texte d'origine
    }
    Object.keys(ATTRIBUTS).forEach(function (attribut) {
      var liste = racine.querySelectorAll("[" + attribut + "]");
      for (var j = 0; j < liste.length; j++) {
        var valeur = resoudre(liste[j].getAttribute(attribut));
        if (valeur !== undefined) liste[j].setAttribute(ATTRIBUTS[attribut], valeur);
      }
    });
  }

  function remplirSelecteurs() {
    var selecteurs = document.querySelectorAll("select[data-langue]");
    for (var i = 0; i < selecteurs.length; i++) {
      var s = selecteurs[i];
      if (!s.options.length) {
        LANGUES.forEach(function (l) {
          var o = document.createElement("option");
          o.value = l.code; o.textContent = l.nom; o.lang = l.code === "dje" ? "fr" : l.code;
          s.appendChild(o);
        });
        s.addEventListener("change", function (e) { choisir(e.target.value, true); });
      }
      s.value = courante;
      s.setAttribute("aria-label", t("langue.libelle"));
    }
  }

  function lireStockage() { try { return localStorage.getItem(CLE_STOCKAGE); } catch (e) { return null; } }
  function ecrireStockage(code) { try { localStorage.setItem(CLE_STOCKAGE, code); } catch (e) { /* stockage bloqué : le choix durera le temps de la page */ } }

  function detecter() {
    var gardee = lireStockage();
    if (gardee && LANGUES.some(function (l) { return l.code === gardee; })) return gardee;
    var preferees = (navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || "fr"]);
    for (var i = 0; i < preferees.length; i++) {
      var prefixe = String(preferees[i]).slice(0, 2).toLowerCase();
      if (["fr", "en", "ha", "ar"].indexOf(prefixe) !== -1) return prefixe;
    }
    return "fr";
  }

  function choisir(code, memoriser) {
    var l = info(code);
    courante = l.code;
    document.documentElement.lang = l.code === "dje" ? "dje" : l.code;
    document.documentElement.dir = l.dir;
    if (memoriser) ecrireStockage(l.code);
    appliquer(document);
    remplirSelecteurs();
    document.dispatchEvent(new CustomEvent("tsintuwa:langue", { detail: { code: l.code } }));
  }

  /* Démarrage : langue forcée (écran du hall) ou langue mémorisée / du navigateur. */
  function demarrer(forcee) {
    courante = forcee ? info(forcee).code : detecter();
    var l = info(courante);
    document.documentElement.lang = l.code;
    document.documentElement.dir = l.dir;
    appliquer(document);
    remplirSelecteurs();
  }

  R.i18n = {
    langues: LANGUES,
    ajouter: ajouter,
    t: t,
    categorie: categorie,
    formaterJour: formaterJour,
    formaterHeure: formaterHeure,
    formaterJourSemaine: formaterJourSemaine,
    formaterHeureSecondes: formaterHeureSecondes,
    formaterJourComplet: formaterJourComplet,
    appliquer: appliquer,
    choisir: choisir,
    demarrer: demarrer,
    definirContexte: function (c) { contexte = c || { secteur: "" }; },
    code: function () { return courante; },
    chercher: chercher
  };
})();
