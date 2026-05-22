// ===========================
// 🔗 Configuration API
// ===========================
const API_BASE = "https://checkpoint-jczh.onrender.com"; 
// ⚠️ Mets ici ton vrai lien Render (par ex. https://checkpoint-backend.onrender.com)

// ===========================
// ⚙️ Fonction utilitaire générique
// ===========================
async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(`Erreur API (${res.status}): ${msg}`);
  }
  return res.json();
}

// ===========================
// 🧠 Vérification de connexion backend
// ===========================
window.addEventListener("load", () => {
  api("/health")
    .then(r => console.log("✅ API en ligne :", r))
    .catch(err => console.error("❌ API inaccessible :", err));
});

// ===========================
// 👤 Gestion du statut utilisateur
// ===========================
async function setStatus(status) {
  try {
    const res = await api("/me/status", {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    console.log("✅ Statut mis à jour :", res);
  } catch (e) {
    console.error("Erreur mise à jour statut:", e);
  }
}
window.setStatus = setStatus;

// ===========================
// 🔐 Authentification utilisateur
// ===========================
async function register(email, password, username) {
  try {
    const data = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, username })
    });
    console.log("✅ Inscription réussie :", data);
    return data;
  } catch (e) {
    console.error("❌ Erreur d’inscription :", e);
  }
}

async function login(email, password) {
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    console.log("✅ Connexion réussie :", data);
    return data;
  } catch (e) {
    console.error("❌ Erreur de connexion :", e);
  }
}

window.register = register;
window.login = login;
