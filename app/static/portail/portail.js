/*
  Portail public — Étape 11.
  Une seule page pour toutes les organisations : elle lit l'identifiant court dans l'adresse
  (ex. /iat), demande à l'API l'habillage de l'organisation et s'en revêt.

  Navigation : chaque page a son « # » dans l'adresse (#declarer, #objets, #recu). Ainsi le bouton
  « retour » du téléphone ramène à la page précédente au lieu de quitter le site.

  Sécurité : tout texte venant du serveur est inséré avec textContent (jamais innerHTML),
  pour qu'un nom d'objet ou d'organisation ne puisse pas injecter de code dans la page.
*/
(function () {
  "use strict";

  var slug = (location.pathname.split("/").filter(Boolean)[0] || "").toLowerCase();
  var org = null;
  var dernierRecu = null;

  var $ = function (id) { return document.getElementById(id); };

  /* Traductions : voir /static/i18n/. « t » donne le texte d'une clé dans la langue choisie. */
  var I18N = window.Tsintuwa.i18n;
  var t = function (cle, variables) { return I18N.t(cle, variables); };

  /* ---------- Outils ---------- */

  function el(tag, classe, texte) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    if (texte !== undefined) n.textContent = texte;
    return n;
  }

  function api(methode, chemin, corps) {
    var options = { method: methode, headers: { Accept: "application/json" } };
    if (corps !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(corps);
    }
    return fetch(chemin, options).then(function (reponse) {
      return reponse.text().then(function (texte) {
        var donnees = null;
        try { donnees = texte ? JSON.parse(texte) : null; } catch (e) { donnees = null; }
        if (!reponse.ok) {
          var erreur = new Error(messageErreur(donnees, reponse.status));
          erreur.status = reponse.status;
          throw erreur;
        }
        return donnees;
      });
    }, function () {
      var erreur = new Error(t("erreur.reseau"));
      erreur.status = 0;
      throw erreur;
    });
  }

  function messageErreur(donnees, statut) {
    if (statut >= 500) return t("erreur.serveur");
    if (donnees && typeof donnees.detail === "string") return donnees.detail;
    if (donnees && Array.isArray(donnees.detail) && donnees.detail[0] && donnees.detail[0].msg) {
      return t("erreur.champ", { msg: donnees.detail[0].msg });
    }
    return t("erreur.autre", { code: statut });
  }

  function estImage(url) {
    return typeof url === "string" && (url.charAt(0) === "/" || /^https?:\/\//i.test(url));
  }

  /* « court » : sans le mot « Trouvé » (ex. « hier »), pour la fiche détaillée. */
  function jourRelatif(iso, court) {
    var d = new Date(iso);
    var auj = new Date();
    var j0 = new Date(auj.getFullYear(), auj.getMonth(), auj.getDate());
    var j1 = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var ecart = Math.round((j0 - j1) / 86400000);
    var base = court ? "quand." : "trouve.";
    if (ecart <= 0) return t(base + "auj");
    if (ecart === 1) return t(base + "hier");
    if (ecart < 7) return t(base + "jours", { n: ecart });
    return t(base + "le", { date: I18N.formaterJour(d) });
  }

  /* Numéro du Niger : 8 chiffres (on ajoute +227). Numéro étranger : doit commencer par + ou 00. */
  function normaliserTelephone(brut) {
    var t = brut.replace(/[\s.\-()]/g, "");
    if (t.indexOf("00") === 0) t = "+" + t.slice(2);
    if (t.charAt(0) === "+") return /^\+\d{8,15}$/.test(t) ? t : null;
    if (/^\d{8}$/.test(t)) return "+227" + t;
    if (/^227\d{8}$/.test(t)) return "+" + t;
    return null;
  }

  function afficherTelephone(t) {
    var m = /^\+227(\d{2})(\d{2})(\d{2})(\d{2})$/.exec(t);
    return m ? "+227 " + m.slice(1).join(" ") : t;
  }

  /* ---------- Habillage ---------- */

  function appliquerTheme() {
    var th = org.theme, racine = document.documentElement.style;
    racine.setProperty("--principale", th.principale);
    racine.setProperty("--accent", th.accent);
    racine.setProperty("--fond", th.fond);
    racine.setProperty("--sombre", th.sombre);
    racine.setProperty("--t-principale", th.texte_sur_principale);
    racine.setProperty("--t-accent", th.texte_sur_accent);
    racine.setProperty("--t-sombre", th.texte_sur_sombre);
    racine.setProperty("--t-fond", th.texte_sur_fond);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", th.principale);
    document.title = t("portail.titre_page", { org: org.nom });

    var accueil = $("vue-accueil");
    if (estImage(org.fond_url)) {
      racine.setProperty("--fond-image", 'url("' + org.fond_url + '")');
    } else {
      accueil.classList.add("accueil--sans-photo");
    }
  }

  function logoOuInitiales(conteneur, classeImage) {
    if (estImage(org.logo_url)) {
      var img = document.createElement("img");
      img.src = org.logo_url;
      img.alt = t("hall.logo_alt", { org: org.nom });
      img.addEventListener("error", function () {
        conteneur.textContent = "";
        conteneur.appendChild(initiales());
      });
      conteneur.appendChild(img);
    } else {
      conteneur.appendChild(initiales());
    }
  }

  function initiales() {
    var mots = org.nom.split(/\s+/).filter(Boolean);
    var lettres = mots.slice(0, 2).map(function (m) { return m.charAt(0).toUpperCase(); }).join("");
    return el("span", "plaque__initiales", lettres);
  }

  function construireEntete() {
    $("accueil-titre").textContent = org.nom;
    logoOuInitiales($("plaque-logo"));

    $("barre-nom").textContent = org.nom;
    if (estImage(org.logo_url)) {
      var img = document.createElement("img");
      img.src = org.logo_url;
      img.alt = "";
      $("barre-logo").appendChild(img);
      $("barre-logo").hidden = false;
      $("barre").classList.add("barre--logo");
    }

    // Les textes (introduction, aide, note…) sont posés par les traductions : voir I18N.appliquer.
    $("lien-objets").hidden = !org.consultation_distance;
    $("note-objets").hidden = !!org.consultation_distance;
  }

  function construirePuces(categories) {
    var zone = $("puces");
    categories.forEach(function (nom, i) {
      var etiquette = el("label", "puce");
      var radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "categorie";
      radio.value = nom;
      radio.id = "cat-" + i;
      radio.addEventListener("change", function () { effacerErreur("categorie"); });
      etiquette.appendChild(radio);
      var libelle = el("span", "puce__texte", I18N.categorie(nom));
      libelle.setAttribute("data-categorie", nom);
      etiquette.appendChild(libelle);
      zone.appendChild(etiquette);
    });
    $("cat-recherche").addEventListener("input", trierEtFiltrerPuces);
    trierEtFiltrerPuces();
  }

  /* Tri alphabétique dans la langue choisie (« Autre » reste en dernier) + filtre de recherche. */
  function sansAccent(t) { return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim(); }

  function trierEtFiltrerPuces() {
    var zone = $("puces");
    if (!zone) return;
    var puces = Array.prototype.slice.call(zone.querySelectorAll(".puce"));
    var tri;
    try { tri = new Intl.Collator(I18N.code(), { sensitivity: "base" }); } catch (e) { tri = new Intl.Collator("fr", { sensitivity: "base" }); }
    puces.sort(function (a, b) {
      var an = a.querySelector(".puce__texte"), bn = b.querySelector(".puce__texte");
      var aAutre = an.getAttribute("data-categorie") === "Autre", bAutre = bn.getAttribute("data-categorie") === "Autre";
      if (aAutre !== bAutre) return aAutre ? 1 : -1;
      return tri.compare(an.textContent, bn.textContent);
    });
    var q = sansAccent($("cat-recherche").value);
    var visibles = 0;
    puces.forEach(function (p) {
      zone.appendChild(p);
      var texte = p.querySelector(".puce__texte");
      var autre = texte.getAttribute("data-categorie") === "Autre";
      var choisie = p.querySelector("input").checked;
      var ok = !q || autre || choisie || sansAccent(texte.textContent).indexOf(q) !== -1 || sansAccent(texte.getAttribute("data-categorie")).indexOf(q) !== -1;
      p.hidden = !ok;
      if (ok && !autre) visibles++;
    });
    $("cat-aucune").hidden = !q || visibles > 0;
  }

  /* ---------- Navigation ---------- */

  var VUES = { "": "accueil", declarer: "declarer", recu: "recu", objets: "objets" };

  function afficherVue() {
    var cle = location.hash.replace("#", "");
    var nom = VUES.hasOwnProperty(cle) ? VUES[cle] : "accueil";
    if (nom === "recu" && !dernierRecu) nom = "accueil";
    if (nom === "objets" && !org.consultation_distance) nom = "accueil";

    ["accueil", "declarer", "recu", "objets"].forEach(function (v) { $("vue-" + v).hidden = v !== nom; });
    $("barre").hidden = nom === "accueil";
    $("signature-bas").hidden = nom === "accueil";

    window.scrollTo(0, 0);
    var titre = $({ accueil: "accueil-titre", declarer: "declarer-titre", recu: "recu-titre", objets: "objets-titre" }[nom]);
    if (titre) titre.focus({ preventScroll: true });

    if (nom === "objets") chargerObjets();
    if (nom === "recu") remplirTalon();
  }

  /* ---------- Déclaration ---------- */

  function montrerErreur(champ, message) {
    var p = $("erreur-" + champ);
    p.textContent = message;
    p.hidden = false;
    var saisie = champ === "telephone" ? $("telephone") : champ === "email" ? $("email") : null;
    if (saisie) saisie.classList.add("invalide");
  }

  function effacerErreur(champ) {
    var p = $("erreur-" + champ);
    if (p) { p.hidden = true; p.textContent = ""; }
    if (champ === "telephone") $("telephone").classList.remove("invalide");
    if (champ === "email") $("email").classList.remove("invalide");
  }

  function lireFormulaire() {
    var choisie = document.querySelector('input[name="categorie"]:checked');
    return {
      categorie: choisie ? choisie.value : "",
      description: $("description").value.trim(),
      date: $("date").value,
      lieu: $("lieu").value.trim(),
      nom: $("nom").value.trim(),
      telephone: normaliserTelephone($("telephone").value),
      email: $("email").value.trim().toLowerCase()
    };
  }

  function envoyer(evenement) {
    evenement.preventDefault();
    effacerErreur("categorie");
    effacerErreur("telephone");
    effacerErreur("email");
    $("erreur-general").hidden = true;

    var f = lireFormulaire();
    var invalide = null;
    if (!f.categorie) {
      montrerErreur("categorie", t("erreur.categorie"));
      invalide = invalide || document.querySelector('input[name="categorie"]');
    }
    if (!f.telephone) {
      montrerErreur("telephone", t("erreur.telephone"));
      invalide = invalide || $("telephone");
    }
    if (f.email && !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(f.email)) {
      montrerErreur("email", t("erreur.email"));
      invalide = invalide || $("email");
    }
    if (invalide) { invalide.focus(); return; }

    var bouton = $("envoyer");
    bouton.disabled = true;
    bouton.textContent = t("declarer.envoi");

    api("POST", "/usagers/", { telephone: f.telephone, nom: f.nom || null })
      .then(function (usager) {
        return api("POST", "/signalements/", {
          organisation_id: org.id,
          usager_id: usager.id,
          categorie: f.categorie,
          description: f.description || null,
          date_perte: f.date || null,
          lieu_approximatif: f.lieu || null,
          email: f.email || null
        });
      })
      .then(function (signalement) {
        dernierRecu = { signalement: signalement, telephone: f.telephone, categorie: f.categorie, email: f.email };
        $("formulaire").reset();
        location.hash = "#recu";
      })
      .catch(function (erreur) {
        var zone = $("erreur-general");
        zone.textContent = erreur.message;
        zone.hidden = false;
      })
      .then(function () {
        bouton.disabled = false;
        bouton.textContent = t("declarer.envoyer");
      });
  }

  function remplirTalon() {
    var r = dernierRecu;
    $("talon-org").textContent = org.nom;
    $("talon-objet").textContent = I18N.categorie(r.categorie);
    $("talon-date").textContent = I18N.formaterJour(new Date(), true);
    $("talon-tel").textContent = afficherTelephone(r.telephone);
    $("talon-ref").textContent = r.signalement.id.replace(/-/g, "").slice(0, 8).toUpperCase();

    var talon = $("talon");
    talon.classList.remove("talon--neuf");
    void talon.offsetWidth; // relance l'animation si on revient sur la page
    talon.classList.add("talon--neuf");

    var tel = afficherTelephone(r.telephone);
    $("recu-statut").textContent = r.signalement.statut === "correspondance_trouvee"
      ? t("recu.statut.match", { lieu: t("lieu_accueil") })
      : (r.email ? t("recu.statut.attente_email", { tel: tel, email: r.email }) : t("recu.statut.attente", { tel: tel }));
  }

  /* ---------- Objets trouvés ---------- */

  var ICONE_OBJET =
    '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 8l-9-5-9 5v8l9 5 9-5V8z"/><path d="M3.3 7.6L12 12.5l8.7-4.9M12 22V12.5"/></svg>';

  function vignette(objet, classeImage, classeVide) {
    if (estImage(objet.photo_url)) {
      var cadre = el("div", "cadre-photo " + classeImage);
      cadre.style.setProperty("--photo", urlCss(objet.photo_url));
      var img = document.createElement("img");
      img.src = objet.photo_url;
      img.alt = t("objets.photo", { categorie: I18N.categorie(objet.categorie) });
      img.loading = "lazy";
      img.addEventListener("error", function () { cadre.replaceWith(vide(classeVide)); });
      cadre.appendChild(img);
      return cadre;
    }
    return vide(classeVide);
  }

  /* Adresse de photo à placer dans une variable CSS (neutralise les caractères qui sortiraient de url("…")). */
  function urlCss(url) { return 'url("' + String(url).replace(/["'()\\\s]/g, function (c) { return "%" + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"); }) + '")'; }

  function vide(classe) {
    var d = el("div", classe);
    d.innerHTML = ICONE_OBJET; // texte constant, aucune donnée du serveur
    return d;
  }

  function chargerObjets() {
    var etat = $("objets-etat"), liste = $("objets-liste");
    liste.textContent = "";
    etat.textContent = t("objets.chargement");
    api("GET", "/portail/" + encodeURIComponent(slug) + "/objets")
      .then(function (objets) {
        etat.textContent = "";
        if (!objets.length) {
          var titre = el("strong", "", t("objets.vide_titre"));
          etat.appendChild(titre);
          etat.appendChild(document.createTextNode(t("objets.vide_texte")));
          return;
        }
        objets.forEach(function (o) { liste.appendChild(carte(o)); });
      })
      .catch(function (erreur) {
        etat.textContent = "";
        etat.appendChild(el("strong", "", t("objets.erreur_titre")));
        etat.appendChild(document.createTextNode(erreur.message));
      });
  }

  function carte(objet) {
    var bouton = el("button", "objet");
    bouton.type = "button";
    bouton.appendChild(vignette(objet, "objet__image", "objet__vide"));
    var texte = el("div", "objet__texte");
    texte.appendChild(el("strong", "", I18N.categorie(objet.categorie)));
    texte.appendChild(el("span", "", jourRelatif(objet.date_heure_decouverte)));
    bouton.appendChild(texte);
    bouton.addEventListener("click", function () { ouvrirDetail(objet); });
    return bouton;
  }

  function ouvrirDetail(objet) {
    var d = $("detail");
    d.textContent = "";
    if (estImage(objet.photo_url)) {
      var cadre = el("div", "cadre-photo detail__image");
      cadre.style.setProperty("--photo", urlCss(objet.photo_url));
      var img = document.createElement("img");
      img.src = objet.photo_url;
      img.alt = t("objets.photo", { categorie: I18N.categorie(objet.categorie) });
      cadre.appendChild(img);
      d.appendChild(cadre);
    }
    var corps = el("div", "detail__corps");
    var titre = el("h3", "", I18N.categorie(objet.categorie));
    titre.id = "detail-titre";
    corps.appendChild(titre);
    var meta = jourRelatif(objet.date_heure_decouverte);
    if (objet.type_emplacement === "vehicule" || objet.type_emplacement === "locaux") {
      meta = t("emplacement." + objet.type_emplacement) + " · " + jourRelatif(objet.date_heure_decouverte, true);
    }
    corps.appendChild(el("p", "detail__meta", meta));
    corps.appendChild(el("p", "statut", t("objets.detail_texte", { lieu: t("lieu_accueil") })));
    var fermer = el("button", "bouton bouton--accent bouton--plein", t("objets.fermer"));
    fermer.type = "button";
    fermer.addEventListener("click", function () { d.close(); });
    corps.appendChild(fermer);
    d.appendChild(corps);
    if (typeof d.showModal === "function") d.showModal(); else d.setAttribute("open", "");
  }

  /* ---------- Démarrage ---------- */

  /* Quand la langue change : on réécrit tout ce que le JavaScript a construit lui-même. */
  function actualiserLangue() {
    if (!org) return;
    document.title = t("portail.titre_page", { org: org.nom });
    var libelles = document.querySelectorAll(".puce__texte");
    for (var i = 0; i < libelles.length; i++) libelles[i].textContent = I18N.categorie(libelles[i].getAttribute("data-categorie"));
    trierEtFiltrerPuces();
    ["categorie", "telephone", "email"].forEach(effacerErreur);
    $("erreur-general").hidden = true;
    if ($("detail").open) $("detail").close();
    if (!$("vue-recu").hidden) remplirTalon();
    if (!$("vue-objets").hidden) chargerObjets();
  }

  function demarrer() {
    I18N.demarrer();
    document.addEventListener("tsintuwa:langue", actualiserLangue);
    Promise.all([
      api("GET", "/organisations/par-slug/" + encodeURIComponent(slug)),
      api("GET", "/portail/" + encodeURIComponent(slug) + "/categories"),
      api("GET", "/portail/" + encodeURIComponent(slug) + "/categories/personnalisees").catch(function () { return []; })
    ]).then(function (resultats) {
      I18N.ajouterCategories(resultats[2]);
      org = resultats[0];
      I18N.definirContexte({ secteur: org.secteur === "transport" ? "transport" : "education" });
      appliquerTheme();
      construireEntete();
      construirePuces(resultats[1]);
      I18N.appliquer(document);

      var maintenant = new Date();
      var iso = maintenant.getFullYear() + "-" + String(maintenant.getMonth() + 1).padStart(2, "0") + "-" + String(maintenant.getDate()).padStart(2, "0");
      $("date").max = iso;

      $("formulaire").addEventListener("submit", envoyer);
      $("telephone").addEventListener("input", function () { effacerErreur("telephone"); });
      $("detail").addEventListener("click", function (e) { if (e.target === this) this.close(); });
      window.addEventListener("hashchange", afficherVue);

      $("chargement").hidden = true;
      $("app").hidden = false;
      afficherVue();
    }).catch(function (erreur) {
      $("chargement").textContent = erreur.status === 404
        ? t("erreur.org_inconnue")
        : erreur.message;
    });
  }

  demarrer();
})();
