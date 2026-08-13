(() => {
  const STORAGE_KEY = "llm-cockpit-lang";
  const DEFAULT_LANG = "en";
  const textStore = new WeakMap();
  const attrStore = new WeakMap();

  const exact = new Map([
    ["Inventory", "Inventaire"],
    ["Dashboard", "Tableau de bord"],
    // Onglets de section
    ["Models", "Modèles"],
    ["Routing", "Routage"],
    ["Traffic", "Trafic"],
    ["Lab", "Labo"],
    ["Which model answers for which role", "Quel modèle répond pour quel rôle"],
    ["Measure, then improve: evaluations gate what RAG and adaptation are worth.",
     "Mesurer, puis améliorer : les évaluations valident ce que valent le RAG et l'adaptation."],
    ["Refresh", "Rafraîchir"],
    ["Test a model", "Tester un modèle"],
    ["Test", "Tester"],
    ["Model to test", "Modèle à tester"],
    ["Test prompt", "Invite de test"],
    ["The result appears in the action log below.", "Le résultat apparaît dans le journal d'actions ci-dessous."],
    ["Gateway activity — auto-refresh every 5 s", "Activité du gateway — rafraîchissement automatique toutes les 5 s"],
    ["Providers", "Fournisseurs"],
    ["Enabled", "Activé"],
    ["Status", "Statut"],
    ["Models", "Modèles"],
    ["Capabilities", "Capacités"],
    ["Kind", "Type"],
    ["Base URL", "URL de base"],
    ["Add", "Ajouter"],
    ["Provider ID", "ID du provider"],
    ["Provider kind", "Type de provider"],
    ["Registry unreadable:", "Registre illisible :"],
    ["the file is not overwritten automatically.", "le fichier n'est pas écrasé automatiquement."],
    ["Model", "Modèle"],
    ["State", "État"],
    ["Source", "Source"],
    ["Family", "Famille"],
    ["Size", "Taille"],
    ["Modified", "Modifié"],
    ["Expires", "Expire"],
    ["loaded", "chargé"],
    ["not loaded", "non chargé"],
    ["Unload", "Décharger"],
    ["Load", "Charger"],
    ["Roles", "Rôles"],
    ["Roles preferences unreadable:", "Préférences de rôles illisibles :"],
    ["Assigned model", "Modèle assigné"],
    ["Updated", "Mis à jour"],
    ["Test role", "Tester le rôle"],
    ["Model for role", "Modèle pour le rôle"],
    ["— unassigned —", "— non assigné —"],
    ["The result of a role test appears in the action log.", "Le résultat d'un test de rôle apparaît dans le journal d'actions."],
    ["Gateway", "Gateway"],
    ["active", "actif"],
    ["disabled", "désactivé"],
    ["Local OpenAI-compatible endpoint:", "Point de terminaison local compatible OpenAI :"],
    ["An app calls model:\"<role>\" or a real model.", "Une app appelle model:\"<role>\" ou un modèle réel."],
    ["Routing unavailable:", "Routage indisponible :"],
    ["Request (role)", "Requête (rôle)"],
    ["Resolves to", "Résout vers"],
    ["Reason", "Raison"],
    ["not routable", "non routable"],
    ["Action log", "Journal d'actions"],
    ["Actions disabled (ACTIONS_ENABLED=0).", "Actions désactivées (ACTIONS_ENABLED=0)."],
    ["No actions recorded.", "Aucune action enregistrée."],
    ["Timestamp", "Horodatage"],
    ["Detail", "Détail"],
    ["requests", "requêtes"],
    ["errors", "erreurs"],
    ["error rate", "taux d'erreur"],
    ["latency p50 (ms)", "latence p50 (ms)"],
    ["latency p95 (ms)", "latence p95 (ms)"],
    ["By model", "Par modèle"],
    ["By provider", "Par fournisseur"],
    ["By app", "Par application"],
    ["Latest requests", "Dernières requêtes"],
    ["No gateway requests recorded.", "Aucune requête gateway enregistrée."],
    ["Role", "Rôle"],
    ["App", "Appli"],
    ["Provider", "Fournisseur"],
    ["Latency", "Latence"],
    ["Evaluation scoreboard (by role / model)", "Scoreboard d'évaluation (par rôle / modèle)"],
    ["Evaluation suite", "Suite d'évaluation"],
    ["models separated by commas (or roles)", "modèles séparés par des virgules (ou rôles)"],
    ["Models to compare", "Modèles à comparer"],
    ["Run eval", "Lancer l'éval"],
    ["Evals go through the real gateway routing and never execute generated code.", "Les évals passent par le routage réel du gateway et n'exécutent jamais le code généré."],
    ["No evaluation results yet.", "Aucun résultat d'évaluation pour l'instant."],
    ["Success", "Réussite"],
    ["Cases", "Cas"],
    ["Avg. latency", "Latence moy."],
    ["Errors", "Erreurs"],
    ["Recent runs", "Runs récents"],
    ["Suite", "Suite"],
    ["Local RAG", "RAG local"],
    ["embeddings:", "embeddings :"],
    ["file under data/rag/docs (e.g. notes.md)", "fichier sous data/rag/docs (ex. notes.md)"],
    ["Document path", "Chemin du document"],
    ["Ingest", "Ingérer"],
    ["Ingested documents stay local (data/rag/), never committed.", "Les documents ingérés restent locaux (data/rag/), jamais committés."],
    ["No document ingested.", "Aucun document ingéré."],
    ["Remove", "Retirer"],
    ["Query the documents", "Interroger les documents"],
    ["RAG question", "Question RAG"],
    ["Role", "Rôle"],
    ["Ask", "Demander"],
    ["No local source cited.", "Aucune source locale citée."],
    ["Generation unavailable:", "Génération impossible :"],
    ["Model:", "Modèle :"],
    ["score", "score"],
    ["LoRA/QLoRA adaptation", "Adaptation LoRA/QLoRA"],
    ["runner configured", "runner configuré"],
    ["dry-run (no runner)", "dry-run (aucun runner)"],
    ["The cockpit orchestrates and measures; the real training runs in an allowlisted external runner. The baseline is never overwritten; promotion is gated by V6 evals.", "Le cockpit orchestre et mesure ; l'entraînement réel tourne dans un runner externe allowlisté. Le baseline n'est jamais écrasé ; la promotion est validée par les évals V6."],
    ["Datasets", "Datasets"],
    ["name", "nom"],
    [".jsonl file under data/datasets", "fichier .jsonl sous data/datasets"],
    ["Dataset name", "Nom du dataset"],
    ["Dataset path", "Chemin du dataset"],
    ["Validate", "Valider"],
    ["Rows", "Lignes"],
    ["Run a job", "Lancer un job"],
    ["Dataset ID", "ID du dataset"],
    ["Base model", "Modèle de base"],
    ["Method", "Méthode"],
    ["Run", "Lancer"],
    ["Cancel", "Annuler"],
    ["Jobs", "Jobs"],
    ["Model versions", "Versions de modèle"],
    ["\"Active\" = registry selection, not what the gateway serves. In V8, the gateway always serves the base model; the promoted adapter is not served by /v1/chat/completions.", "« Actif » = sélection dans le registry, pas ce que sert le gateway. En V8, le gateway sert toujours le modèle de base ; l'adapter promu n'est pas servi par /v1/chat/completions."],
    ["Active (registry)", "Actif (registry)"],
    ["Serving", "Serving"],
    ["Pass rate", "Taux de réussite"],
    ["Eval", "Éval"],
    ["served (base)", "servi (base)"],
    ["not served", "non servi"],
    ["Marks the version active in the registry (does not serve it).", "Marque la version active dans le registry (ne la sert pas)."],
    ["Promote (registry)", "Promouvoir (registry)"],
    ["Roll back", "Rollback"],
    ["Base", "Base"],
    ["Type", "Type"],
    ["Load", "Charger"],
    ["Unload", "Décharger"],
    ["Provider ID", "ID du provider"],
    ["provider id", "ID du provider"],
    ["provider kind", "type de provider"],
    ["yes", "oui"],
    ["no", "non"],
    ["reachable", "joignable"],
    ["unreachable", "injoignable"],
    ["active", "actif"],
    ["disabled", "désactivé"],
    ["not routable", "non routable"],
    ["routable", "routable"],
    // --- UI chrome ---
    ["Auto-refresh every 5 s", "Rafraîchissement auto toutes les 5 s"],
    ["← Inventory", "← Inventaire"],
    ["Inventory → control → roles → registry → gateway → observability → evals → RAG → adaptation",
     "Inventaire → contrôle → rôles → registry → gateway → observabilité → évals → RAG → adaptation"],
    ["role (optional, e.g. chat)", "rôle (optionnel, ex. chat)"],
    [". An app calls", ". Une app appelle"],
    ["or a real model.", "ou un modèle réel."],
    // --- GPU capacity ---
    ["GPU memory", "Mémoire GPU"],
    ["free", "libre"],
    ["fits", "tient"],
    ["tight", "juste"],
    ["too large", "trop gros"],
    ["Fit", "Tient ?"],
    ["Fits in the memory free right now", "Tient dans la mémoire libre en ce moment"],
    ["Fits on the card, but not in the memory free right now",
     "Tient sur la carte, mais pas dans la mémoire libre en ce moment"],
    ["Larger than this GPU: it will spill over to the CPU",
     "Plus gros que ce GPU : le modèle débordera sur le CPU"],
    // --- Backend messages (routing, actions, checks) ---
    ["role not assigned", "rôle non assigné"],
    ["role model unavailable (provider unreachable or model missing)",
     "modèle du rôle indisponible (provider injoignable ou absent)"],
    ["model not found in the aggregated inventory", "modèle introuvable dans l'inventaire agrégé"],
    ["actions disabled", "actions désactivées"],
    ["action not in allowlist", "action hors allowlist"],
    ["empty model name", "nom de modèle vide"],
    ["model not installed", "modèle non installé"],
    ["model not loaded", "modèle non chargé"],
    ["model loaded", "modèle chargé"],
    ["model unloaded", "modèle déchargé"],
    ["provider unreachable", "provider injoignable"],
    ["gateway disabled", "gateway désactivé"],
    ["load is not supported by an OpenAI-compatible provider",
     "load non supporté par un provider OpenAI-compatible"],
    ["unload is not supported by an OpenAI-compatible provider",
     "unload non supporté par un provider OpenAI-compatible"],
    ["No relevant source found in the local documents.",
     "Aucune source pertinente trouvée dans les documents locaux."],
    // --- Eval check details ---
    ["non-empty", "non vide"],
    ["empty response", "réponse vide"],
    ["valid JSON", "JSON valide"],
    ["invalid JSON", "JSON invalide"],
    ["equal", "égal"],
    ["different", "différent"],
    ["unknown latency", "latence inconnue"],
  ]);

  const prefixRules = [
    [/^Registry unreadable:/, "Registre illisible :"],
    [/^Roles preferences unreadable:/, "Préférences de rôles illisibles :"],
    [/^Model for role /, "Modèle pour le rôle "],
    [/^Routing unavailable:/, "Routage indisponible :"],
    [/^Generation unavailable:/, "Génération impossible :"],
    [/^Model:/, "Modèle :"],
    [/^The result appears in the action log below\./, "Le résultat apparaît dans le journal d'actions ci-dessous."],
    [/^Gateway activity — auto-refresh every 5 s$/, "Activité du gateway — rafraîchissement automatique toutes les 5 s"],
    [/^Ollama is unreachable\. No inventory is available\./, "Ollama est injoignable. Aucun inventaire n'est disponible."],
    [/^Check that the service listens on /, "Vérifie que le service écoute sur "],
    [/^Ollama is reachable, but no model is installed\./, "Ollama est joignable, mais aucun modèle n'est installé."],
    [/^An app calls model:\"<role>\" or a real model\./, "Une app appelle model:\"<role>\" ou un modèle réel."],
    [/^The cockpit orchestrates and measures; the real training runs in an allowlisted external runner\. The baseline is never overwritten; promotion is gated by V6 evals\./, "Le cockpit orchestre et mesure ; l'entraînement réel tourne dans un runner externe allowlisté. Le baseline n'est jamais écrasé ; la promotion est validée par les évals V6."],
    [/^\"Active\" = registry selection, not what the gateway serves\./, "« Actif » = sélection dans le registry, pas ce que sert le gateway."],
    [/^role '/, "rôle '"],
    [/^real model → /, "modèle réel → "],
    [/^unknown role: /, "rôle inconnu : "],
    [/^unknown check: /, "check inconnu : "],
    [/^unknown version: /, "version inconnue : "],
    [/^unknown job: /, "job inconnu : "],
    [/^unsupported method: /, "méthode non supportée : "],
    [/^unsupported file type: /, "type de fichier non supporté : "],
    [/^Ollama HTTP error /, "erreur HTTP Ollama "],
    [/^contains '/, "contient '"],
    [/^does not contain '/, "ne contient pas '"],
    [/^no match \//, "pas de match /"],
    [/^length (\d+) \(min /, "longueur $1 (min "],
    [/^length (\d+) \(max /, "longueur $1 (max "],
    [/^(\d+) validated examples$/, "$1 exemples validés"],
    [/^dry-run: no TRAIN_RUNNER configured\. Command that would have run: /,
     "dry-run : aucun TRAIN_RUNNER configuré. Commande qui aurait été lancée : "],
    [/^file not found: /, "fichier introuvable : "],
    [/^path outside the allowed directory: /, "chemin hors du dossier autorisé : "],
    [/^model not installed: /, "modèle non installé : "],
    [/^role not assigned: /, "rôle non assigné : "],
    [/^embedding model not installed: /, "modèle d'embedding non installé : "],
    [/^embeddings: /, "embeddings : "],
    [/^of /, "sur "],
  ];

  function normalize(text) {
    return text.replace(/\s+/g, " ").trim();
  }

  function translate(text) {
    const key = normalize(text);
    if (exact.has(key)) return exact.get(key);
    for (const [pattern, replacement] of prefixRules) {
      if (pattern.test(key)) {
        return key.replace(pattern, replacement);
      }
    }
    return text;
  }

  function translateTextNodes(root, lang) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (!parent) continue;
      if (["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA"].includes(parent.tagName)) continue;
      if (!textStore.has(node)) textStore.set(node, node.nodeValue);
      node.nodeValue = lang === "fr" ? translate(textStore.get(node)) : textStore.get(node);
    }
  }

  function translateAttributes(root, lang) {
    const elements = root.querySelectorAll("[placeholder], [aria-label], [title]");
    for (const el of elements) {
      const key = el;
      const store = attrStore.get(key) || {};
      for (const attr of ["placeholder", "aria-label", "title"]) {
        if (!el.hasAttribute(attr)) continue;
        if (!(attr in store)) store[attr] = el.getAttribute(attr);
        const original = store[attr];
        el.setAttribute(attr, lang === "fr" ? translate(original) : original);
      }
      attrStore.set(key, store);
    }
  }

  function applyLanguage(lang) {
    const target = lang === "fr" ? "fr" : DEFAULT_LANG;
    document.documentElement.lang = target;
    document.body.dataset.lang = target;
    translateTextNodes(document.body, target);
    translateAttributes(document.body, target);
    document.querySelectorAll("[data-lang]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.lang === target);
    });
    localStorage.setItem(STORAGE_KEY, target);
  }

  function init() {
    const saved = localStorage.getItem(STORAGE_KEY);
    const lang = saved === "fr" ? "fr" : DEFAULT_LANG;

    document.querySelectorAll("[data-lang]").forEach((button) => {
      button.addEventListener("click", () => applyLanguage(button.dataset.lang));
    });

    applyLanguage(lang);

    document.addEventListener("htmx:afterSwap", () => applyLanguage(localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
