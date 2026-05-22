const container = document.querySelector('.container');
const registerBtn = document.querySelector('.register-btn');
const loginBtn = document.querySelector('.login-btn');

if (registerBtn) {
  registerBtn.addEventListener('click', () => container?.classList.add('active'));
}
if (loginBtn) {
  loginBtn.addEventListener('click', () => container?.classList.remove('active'));
}

// Gestion des erreurs serveur
document.addEventListener('DOMContentLoaded', function() {
  // Si on a une erreur de connexion, on montre le formulaire de login
  const loginError = document.querySelector('.server-error')?.textContent;
  if (loginError) {
    container?.classList.remove('active');
    // Mettre le focus sur le champ username
    const usernameInput = document.querySelector('input[name="username"]');
    if (usernameInput) {
      usernameInput.focus();
      usernameInput.classList.add('server-invalid');
    }
  }
  
  // Si on a une erreur d'inscription, on montre le formulaire d'inscription
  const registerError = document.querySelector('.server-error')?.textContent;
  const registerSuccess = document.querySelector('.success-message')?.textContent;
  
  if ((registerError && !registerError.includes('login')) || registerSuccess) {
    container?.classList.add('active');
    // Mettre le focus sur le premier champ avec erreur
    const usernameInput = document.getElementById('registerUsername');
    const emailInput = document.getElementById('registerEmail');
    const passwordInput = document.getElementById('registerPassword');
    
    // Marquer les champs invalides si erreur
    if (registerError && !registerSuccess) {
      if (usernameInput) usernameInput.classList.add('server-invalid');
      if (emailInput) emailInput.classList.add('server-invalid');
      if (passwordInput) passwordInput.classList.add('server-invalid');
    }
    
    // Retirer la classe invalid quand l'utilisateur commence à taper
    [usernameInput, emailInput, passwordInput].forEach(input => {
      if (input) {
        input.addEventListener('input', function() {
          this.classList.remove('server-invalid');
        });
      }
    });
  }
});

/* ---------- Validation du formulaire d'inscription ---------- */
const registerForm = document.getElementById('registerForm');
const usernameInput = document.getElementById('registerUsername');
const passwordInput = document.getElementById('registerPassword');
const usernameError = document.getElementById('usernameError');
const passwordError = document.getElementById('passwordError');

/*
  Règles de mot de passe (recommandées):
  - min 8 caractères, 1 minuscule, 1 majuscule, 1 chiffre, 1 caractère spécial
*/
const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$/;

function validateUsername() {
  if (!usernameInput) return true;
  const v = usernameInput.value.trim();
  if (v.length < 4) {
    if (usernameError) usernameError.textContent = 'L\'identifiant doit contenir au moins 4 caractères.';
    usernameInput.classList.add('invalid');
    return false;
  }
  if (usernameError) usernameError.textContent = '';
  usernameInput.classList.remove('invalid');
  return true;
}

function validatePassword() {
  if (!passwordInput) return true;
  const p = passwordInput.value;
  if (!passwordRegex.test(p)) {
    if (passwordError) passwordError.textContent =
      'Mot de passe trop faible — min 8 caractères, 1 minuscule, 1 majuscule, 1 chiffre, 1 caractère spécial.';
    passwordInput.classList.add('invalid');
    return false;
  }
  if (passwordError) passwordError.textContent = '';
  passwordInput.classList.remove('invalid');
  return true;
}

/* Validation live */
usernameInput?.addEventListener('input', validateUsername);
passwordInput?.addEventListener('input', validatePassword);

/* Validation + nettoyage au submit */
registerForm?.addEventListener('submit', (e) => {
  if (usernameInput) usernameInput.value = usernameInput.value.trim();
  const okUsername = validateUsername();
  const okPassword = validatePassword();
  if (!okUsername || !okPassword) {
    e.preventDefault();
    (!okUsername ? usernameInput : passwordInput)?.focus();
  }
});

/* Horloge optionnelle (protégée) */
const timeEl = document.getElementById('currentTime');
function showTime() {
  if (timeEl) timeEl.textContent = new Date().toUTCString();
}
showTime();
setInterval(showTime, 1000);