"""
Tests end-to-end (E2E) pour Checkpoint avec Selenium.

Structure de l'app (Flask) :
  - La PAGE de connexion s'affiche sur "/"  (template authentification.html)
  - La SOUMISSION du login se fait en POST sur "/login"
  - Apres un login valide SANS MFA -> redirection vers "/home"
  - Un login invalide reaffiche "/" avec un message d'erreur (.server-error)

Important : utiliser un compte de test SANS MFA, sinon le login redirige vers
/mfa_verify et attend un code envoye par email (non automatisable ici).

Prerequis :
    pip install selenium pytest
    (Selenium 4.6+ gere le driver Chrome automatiquement ; Chrome doit etre installe.)

Execution :
    BASE_URL=https://checkpoint-uh9x.onrender.com \
    TEST_USERNAME=ton_user TEST_PASSWORD=ton_mdp \
    pytest test_e2e_login.py -v
"""

import os
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = os.environ.get("BASE_URL", "https://checkpoint-uh9x.onrender.com")

TEST_USERNAME = os.environ.get("TEST_USERNAME", "test_user")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "MotDePasse123!")


@pytest.fixture
def driver():
    """Lance Chrome en mode headless puis le ferme a la fin du test."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")

    drv = webdriver.Chrome(options=options)
    drv.set_page_load_timeout(60)   # Render peut etre lent (cold start)
    drv.implicitly_wait(5)
    yield drv
    drv.quit()


def _open_login_page(driver):
    """Ouvre la page de connexion (sur la racine "/")."""
    driver.get(f"{BASE_URL}/")
    wait = WebDriverWait(driver, 20)
    return wait.until(EC.presence_of_element_located((By.ID, "loginForm")))


def _fill_login(driver, username, password):
    """Remplit et soumet le formulaire de login (#loginForm).

    La page contient aussi un formulaire register avec name='username' et
    name='password' ; on scope donc a l'interieur de #loginForm.
    """
    login_form = _open_login_page(driver)
    user_field = login_form.find_element(By.NAME, "username")
    pass_field = login_form.find_element(By.NAME, "password")
    submit_btn = login_form.find_element(By.CSS_SELECTOR, "button[type='submit']")

    user_field.clear()
    user_field.send_keys(username)
    pass_field.clear()
    pass_field.send_keys(password)
    submit_btn.click()


def test_login_page_loads(driver):
    """La page de connexion (/) doit afficher le formulaire de login."""
    login_form = _open_login_page(driver)
    user_field = login_form.find_element(By.NAME, "username")
    pass_field = login_form.find_element(By.NAME, "password")

    assert user_field.is_displayed()
    assert pass_field.is_displayed()


def test_login_success(driver):
    """Un login valide (compte sans MFA) doit rediriger vers /home."""
    _fill_login(driver, TEST_USERNAME, TEST_PASSWORD)

    # Apres succes sans MFA, l'app redirige vers /home
    WebDriverWait(driver, 20).until(EC.url_contains("/home"))
    assert "/home" in driver.current_url


def test_login_invalid_credentials(driver):
    """Un login invalide doit rester sur la page d'auth et afficher une erreur."""
    _fill_login(driver, "utilisateur_inexistant", "MauvaisMotDePasse123!")

    # L'app reaffiche authentification.html avec login_error -> message .server-error
    error = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".server-error"))
    )
    assert error.is_displayed()
    # On ne doit PAS etre arrive sur /home
    assert "/home" not in driver.current_url