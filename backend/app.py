from flask import Flask, render_template, request, redirect, session, g, flash, url_for, abort
import requests
from mimetypes import guess_type
import os
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import base64
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError
import json
import secrets
import datetime
import random
import string
from dotenv import load_dotenv
import psycopg2
from werkzeug.utils import secure_filename
from uuid import uuid4
from datetime import timezone

# --- Dirs ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../backend
FRONT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "frontend"))

# Charger le fichier .env situé dans le même dossier que app.py
load_dotenv(os.path.join(BASE_DIR, ".env"))

# --- Flask app ---
app = Flask(
    __name__,
    template_folder=os.path.join(FRONT_DIR, "templates"),
    static_folder=os.path.join(FRONT_DIR, "static"),
    static_url_path="/static",
)

# Secret key (ENV > fallback)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")

# --- Supabase DB URL ---
NEON_DB = os.environ.get("NEON_DB")


def get_conn():
    """Connexion à la base Neon/Postgres."""
    if not NEON_DB:
        raise RuntimeError("NEON_DB is not configured in .env")
    return psycopg2.connect(NEON_DB)

def get_schedule_privacy_settings(username: str):
    """
    Retourne {"mode": "friends" | "everyone" | "none" | "custom",
              "allowed": [liste d'amis autorisés si custom]}
    """
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT mode FROM schedule_privacy WHERE user_name = %s",
        (username,),
    )
    row = c.fetchone()

    mode = (row[0] if row else "friends") or "friends"

    allowed = []
    if mode == "custom":
        c.execute(
            "SELECT friend FROM schedule_privacy_custom WHERE user_name = %s",
            (username,),
        )
        allowed = [r[0] for r in c.fetchall()]

    conn.close()
    return {"mode": mode, "allowed": allowed}


def can_view_friend_schedule(viewer_username: str, owner_username: str) -> bool:
    """
    Retourne True si `viewer_username` a le droit de voir le planning de `owner_username`.
    Règles alignées sur /api/planning :
      - owner peut toujours voir son propre planning
      - si mode = 'none'  -> personne ne voit
      - si mode = 'friends' -> tous ses amis le voient
      - si mode = 'everyone' -> tous ses amis le voient (chez toi c'est "all friends")
      - si mode = 'custom' -> seulement la liste de schedule_privacy_custom
    """
    # 1) même personne -> toujours OK
    if viewer_username == owner_username:
        return True

    # 2) récupère le réglage de confidentialité du owner
    info = get_schedule_privacy_settings(owner_username)
    mode = info["mode"]
    allowed = set(info["allowed"])

    if mode == "none":
        return False

    if mode == "custom":
        return viewer_username in allowed

    # 'friends' ou 'everyone' → OK (on suppose déjà qu'ils sont amis)
    return True


# --- DB init (no-op: le schéma est géré côté Supabase) ---
def init_db():
    """Les tables doivent être créées via la console SQL Supabase."""
    pass


def add_columns_if_missing():
    """Plus utilisé : la structure est gérée par Supabase."""
    pass


init_db()
add_columns_if_missing()


# -----------------------------------
# Helpers avatars (download -> base64)
# -----------------------------------
def download_image_as_base64(url: str, timeout: float = 5.0):
    """
    Télécharge une image (Google, Facebook, etc.) et renvoie:
      - base64_str : contenu encodé en base64 (sans préfixe data:)
      - content_type : ex 'image/png'

    Retourne (None, None) en cas d'erreur ou si ce n'est pas clairement une image.
    """
    if not url:
        return None, None

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return None, None

    content_type = resp.headers.get("Content-Type")
    if not content_type or not content_type.startswith("image/"):
        guessed, _ = guess_type(url)
        if not guessed or not guessed.startswith("image/"):
            return None, None
        content_type = guessed

    b64 = base64.b64encode(resp.content).decode("ascii")
    return b64, content_type


# ----------------------
#  Auth / user loading
# ----------------------
@app.before_request
def load_user():
    """Load the current user into g.user (or None)."""
    g.user = None
    uname = session.get("username")
    if not uname:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT username, profile_pic, bio, theme,
               primary_color, bg_color, ink_color, status
        FROM users
        WHERE username = %s
        """,
        (uname,),
    )
    row = c.fetchone()
    conn.close()
    if row:
        g.user = {
            "username": row[0],
            "profile_pic": row[1],
            "bio": row[2] or "",
            "theme": row[3] or "dark",
            "primary_color": row[4] or "#FFD400",
            "bg_color": row[5] or "#1a1a1a",
            "ink_color": row[6] or "#111111",
            "status": row[7] or "online",
        }


def get_unread_messages_count(username: str) -> int:
    """Retourne le nombre total de messages non lus pour un user."""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE to_user = %s
          AND is_read = FALSE
        """,
        (username,),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

@app.context_processor
def inject_globals():
    user = getattr(g, "user", None)
    theme = (user and user.get("theme")) or "dark"

    custom_css_vars = {}
    if theme == "custom" and user:
        custom_css_vars = {
            "--primary-color": user.get("primary_color") or "#FFD400",
            "--bg-dark-1": user.get("bg_color") or "#0b0b0b",
            "--bg-dark-2": user.get("bg_color") or "#1a1a1a",
            "--primary-ink": user.get("ink_color") or "#111111",
        }

    status = (user and user.get("status")) or "online"
    if status not in ("online", "idle", "dnd", "invisible"):
        status = "online"

    dot_class = {
        "online": "dot-online",
        "idle": "dot-idle",
        "dnd": "dot-dnd",
        "invisible": "dot-invisible",
    }.get(status, "dot-online")

    if status == "dnd":
        status_label = "Do Not Disturb"
    else:
        status_label = status.capitalize()

    avatar_url = None
    if user:
        pic = user.get("profile_pic")
        if pic:
            if pic.startswith("data:"):
                avatar_url = pic
            else:
                avatar_url = f"data:image/png;base64,{pic}"

    # ➜ NEW : nombre de messages non lus
    unread_messages_count = 0
    if user:
        unread_messages_count = get_unread_messages_count(user["username"])

    return {
        "user": user,
        "current_theme": theme,
        "custom_css_vars": custom_css_vars,
        "_status": status,
        "_dot": dot_class,
        "_status_label": status_label,
        "avatar_url": avatar_url,
        "unread_messages_count": unread_messages_count,
    }


# --- Fonctions MFA ---
def generate_mfa_code(length=6):
    """Génère un code MFA numérique."""
    return ''.join(random.choices(string.digits, k=length))

def send_mfa_email(email, username, code):
    """Envoie le code MFA par email."""
    try:
        msg = Message(
            subject="Your Login Verification Code",
            recipients=[email],
            sender=app.config["MAIL_DEFAULT_SENDER"]
        )
        
        msg.body = f"""Hello {username},

Your verification code is: {code}

Enter this code to complete your login.

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
Your App Team"""
        
        mail.send(msg)
        print(f"✓ MFA code sent to: {email}")
        return True
    except Exception as e:
        print(f"✗ Failed to send MFA email: {e}")
        return False

# ---------
# Routes
# ---------
@app.route("/")
def index():
    return render_template("authentification.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        return render_template("authentification.html",
                             register_error="Missing fields",
                             register_username=username,
                             register_email=email)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username = %s", (username,))
    if c.fetchone():
        conn.close()
        return render_template("authentification.html",
                             register_error="Username is already taken",
                             register_username=username,
                             register_email=email)

    c.execute("SELECT 1 FROM users WHERE email = %s", (email,))
    if c.fetchone():
        conn.close()
        return render_template("authentification.html",
                             register_error="Email is already used by another account",
                             register_username=username,
                             register_email=email)

    MAX_USERNAME_LEN = 20
    if len(username) > MAX_USERNAME_LEN:
        conn.close()
        return render_template("authentification.html",
                             register_error=f"Username must not exceed {MAX_USERNAME_LEN} characters.",
                             register_username=username,
                             register_email=email)

    MAX_LEN = 20
    import re
    pwd = password

    if " " in pwd:
        conn.close()
        return render_template("authentification.html",
                             register_error="Password must not contain spaces.",
                             register_username=username,
                             register_email=email)

    if len(pwd) > MAX_LEN:
        conn.close()
        return render_template("authentification.html",
                             register_error=f"Password must not exceed {MAX_LEN} characters.",
                             register_username=username,
                             register_email=email)

    # Existing rules: minimum length, one special char, one digit
    if len(pwd) < 8:
        conn.close()
        return render_template("authentification.html",
                             register_error="Password must be at least 8 characters long.",
                             register_username=username,
                             register_email=email)

    if not re.search(r"[0-9]", pwd):
        conn.close()
        return render_template("authentification.html",
                             register_error="Password must contain at least one digit.",
                             register_username=username,
                             register_email=email)

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>-_]", pwd):
        conn.close()
        return render_template("authentification.html",
                             register_error="Password must contain at least one special character.",
                             register_username=username,
                             register_email=email)

    hashed_password = generate_password_hash(password)
    c.execute(
        "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
        (username, email, hashed_password),
    )
    conn.commit()
    conn.close()
    
    # Si l'inscription réussit, on peut rediriger vers la page de connexion
    # ou afficher un message de succès
    return render_template("authentification.html",
                         register_success="Registration successful! You can now login.")


# Config SMTP (exemple avec Gmail)
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    
    if not username or not password:
        # Retourner un template avec l'erreur au lieu d'un texte brut
        return render_template("authentification.html", 
                             login_error="Missing credentials")
    
    conn = get_conn()
    c = conn.cursor()
    
    # Récupérer l'utilisateur avec son email et statut MFA
    c.execute("""
        SELECT id, username, email, password, mfa_enabled 
        FROM users 
        WHERE username = %s
    """, (username,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return render_template("authentification.html",
                             login_error="Incorrect username or password",
                             login_username=username)
    
    user_id, db_username, email, db_password_hash, mfa_enabled = row
    
    # Vérifier le mot de passe
    if not check_password_hash(db_password_hash, password):
        conn.close()
        return render_template("authentification.html",
                             login_error="Incorrect username or password",
                             login_username=username)
    
    # Si MFA est DÉSACTIVÉ → connexion directe
    if not mfa_enabled:
        conn.close()
        session["username"] = username
        return redirect("/home")
    
    # Si MFA est ACTIVÉ → envoyer un code
    mfa_code = generate_mfa_code()
    print(f"DEBUG: MFA code for {username}: {mfa_code}")
    
    # Hasher et stocker le code
    code_hash = generate_password_hash(mfa_code)
    expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=10)
    
    c.execute("""
        INSERT INTO mfa_codes (user_id, code_hash, expires_at)
        VALUES (%s, %s, %s)
    """, (user_id, code_hash, expires_at))
    
    conn.commit()
    conn.close()
    
    # Envoyer l'email
    if not send_mfa_email(email, username, mfa_code):
        return render_template("authentification.html",
                             login_error="Failed to send verification email",
                             login_username=username)
    
    # Stocker en session pour l'étape MFA
    session["pending_user_id"] = user_id
    session["pending_username"] = username
    
    return redirect("/mfa_verify")

@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            return render_template("forgot.html", error="Please enter your email address")
        
        conn = get_conn()
        c = conn.cursor()
        
        # Check if email exists in YOUR database
        c.execute("SELECT username, email FROM users WHERE email = %s", (email,))
        row = c.fetchone()
        conn.close()
        
        if row:
            username, user_email = row
            
            # Generate a secure reset token
            reset_token = secrets.token_urlsafe(32)
            
            # Store token in database with expiration
            conn = get_conn()
            c = conn.cursor()
            
            # Create password_resets table if not exists
            c.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    token VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Delete old tokens for this email
            c.execute("DELETE FROM password_resets WHERE email = %s", (email,))
            
            # Insert new token (valid for 1 hour)
            expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=1)
            c.execute(
                "INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)",
                (email, reset_token, expires_at)
            )
            
            conn.commit()
            conn.close()
            
            # Create reset link
            reset_link = url_for('reset_password', token=reset_token, _external=True)

            try:
                # Send email using Flask-Mail
                msg = Message(
                    subject="Password Reset Request",
                    recipients=[email],
                    sender=app.config["MAIL_DEFAULT_SENDER"]
                )
                
                msg.body = f"""Hello {username},

You requested a password reset for your account.

Please click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
Your App Team"""
                
                mail.send(msg)
                print(f"✓ Password reset email sent to: {email}")
                
                return render_template(
                    "forgot.html",
                    success="If an account with this email exists, a password reset link has been sent."
                )
                
            except Exception as e:
                print(f"✗ Email sending error: {str(e)}")
                return render_template(
                    "forgot.html",
                    error="Failed to send email. Please try again later."
                )
        else:
            # Still show success for security (don't reveal if email exists)
            return render_template(
                "forgot.html",
                success="If an account with this email exists, a password reset link has been sent."
            )
    
    return render_template("forgot.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get('token')
    print(f"DEBUG 1: Token from URL: {token}")
    
    if not token:
        print("DEBUG 2: No token in URL")
        flash('Invalid or expired reset link', 'error')
        return redirect('/forgot')
    
    conn = get_conn()
    c = conn.cursor()
    
    # Check if token exists and is valid
    c.execute(
        "SELECT email, expires_at, used FROM password_resets WHERE token = %s",
        (token,)
    )
    row = c.fetchone()
    
    print(f"DEBUG 3: Row from database: {row}")
    
    if not row:
        print("DEBUG 4: Token not found in database")
        flash('Invalid or expired reset link', 'error')
        conn.close()
        return redirect('/forgot')
    
    email, expires_at, used = row
    print(f"DEBUG 5: Email={email}, Expires={expires_at}, Used={used}")
    
    # Check if token is expired or already used
    from datetime import timezone
    now_utc = datetime.datetime.now(timezone.utc)
    
    # Ensure expires_at is timezone-aware for comparison
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = expires_at.astimezone(timezone.utc)
    
    print(f"DEBUG 6: Now UTC={now_utc}, Expires UTC={expires_at}")
    print(f"DEBUG 7: Is expired? {now_utc > expires_at}")
    print(f"DEBUG 8: Is used? {used}")
    
    if used or now_utc > expires_at:
        print(f"DEBUG 9: Token invalid - used={used}, expired={now_utc > expires_at}")
        flash('Reset link has expired or already been used', 'error')
        conn.close()
        return redirect('/forgot')
    
    print(f"DEBUG 10: Token is VALID! Proceeding...")
    
    # IMPORTANT: Close connection before rendering template
    conn.close()
    
    if request.method == 'GET':
        print(f"DEBUG 11: GET request - rendering reset form")
        # Store token in session for verification in POST
        session['reset_token'] = token
        session['reset_email'] = email
        return render_template("reset_password.html")
    
    # POST request (submitting new password)
    print(f"DEBUG 12: POST request - processing password change")
    print(f"DEBUG 12b: All form data received: {dict(request.form)}")
    
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")
    
    # Verify session token matches
    session_token = session.get('reset_token')
    session_email = session.get('reset_email')
    
    print(f"DEBUG 13: Session token={session_token}, Session email={session_email}")
    print(f"DEBUG 14: Password received: '{password}', Confirm: '{confirm_password}'")
    print(f"DEBUG 14b: Passwords match? {password == confirm_password}")
    print(f"DEBUG 14c: Password length: {len(password)}")
    
    if not session_token or session_token != token or session_email != email:
        print(f"DEBUG 14d: Session mismatch!")
        flash('Reset session expired', 'error')
        return redirect('/forgot')
    
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return render_template("reset_password.html")
    
    # Password validation
    import re
    if len(password) < 8:
        flash('Password must be at least 8 characters long', 'error')
        return render_template("reset_password.html")
    
    if not re.search(r"[0-9]", password):
        flash('Password must contain at least one digit', 'error')
        return render_template("reset_password.html")
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>-_]", password):
        flash('Password must contain at least one special character', 'error')
        return render_template("reset_password.html")
    
    print(f"DEBUG 15: Password passed all validations")
    
    # Re-open connection for update
    conn = get_conn()
    c = conn.cursor()
    
    print(f"DEBUG 16: Updating password for email: {email}")
    
    # Update password in users table
    hashed_password = generate_password_hash(password)
    c.execute(
        "UPDATE users SET password = %s WHERE email = %s RETURNING username",
        (hashed_password, email)
    )
    
    updated_user = c.fetchone()
    print(f"DEBUG 17: Password updated for user: {updated_user}")
    
    # Mark token as used
    c.execute(
        "UPDATE password_resets SET used = TRUE WHERE token = %s RETURNING email",
        (token,)
    )
    
    marked_token = c.fetchone()
    print(f"DEBUG 18: Token marked as used for email: {marked_token}")
    
    conn.commit()
    conn.close()
    
    print(f"DEBUG 19: Database updates committed successfully")
    
    # Clear session
    session.pop('reset_token', None)
    session.pop('reset_email', None)
    
    print(f"DEBUG 20: Session cleared, redirecting to login page")
    
    flash('Password reset successful! You can now login with your new password.', 'success')
    return redirect('/')  # Redirection vers la page de login

# --- Routes MFA ---
@app.route("/mfa_verify", methods=["GET", "POST"])
def mfa_verify():
    if "pending_user_id" not in session:
        return redirect("/")
    
    if request.method == "GET":
        return render_template("mfa_verify.html")
    
    # POST: Vérifier le code
    code = request.form.get("code", "").strip()
    
    if not code or len(code) != 6 or not code.isdigit():
        flash("Please enter a valid 6-digit code", "error")
        return render_template("mfa_verify.html")
    
    user_id = session["pending_user_id"]
    
    conn = get_conn()
    c = conn.cursor()
    
    # Récupérer le dernier code valide
    c.execute("""
        SELECT id, code_hash 
        FROM mfa_codes 
        WHERE user_id = %s 
          AND used = FALSE 
          AND expires_at > NOW()
        ORDER BY created_at DESC 
        LIMIT 1
    """, (user_id,))
    
    row = c.fetchone()
    
    if not row:
        conn.close()
        flash("Verification code expired or not found", "error")
        return render_template("mfa_verify.html")
    
    mfa_id, code_hash = row
    
    # Vérifier le code
    if not check_password_hash(code_hash, code):
        conn.close()
        flash("Invalid verification code", "error")
        return render_template("mfa_verify.html")
    
    # Marquer le code comme utilisé
    c.execute("UPDATE mfa_codes SET used = TRUE WHERE id = %s", (mfa_id,))
    conn.commit()
    conn.close()
    
    # Connexion réussie
    username = session["pending_username"]
    session.pop("pending_user_id", None)
    session.pop("pending_username", None)
    session["username"] = username
    
    flash("Login successful!", "success")
    return redirect("/home")

@app.route("/mfa_resend", methods=["POST"])
def mfa_resend():
    """Renvoyer un code MFA."""
    if "pending_user_id" not in session:
        return redirect("/")
    
    user_id = session["pending_user_id"]
    username = session["pending_username"]
    
    conn = get_conn()
    c = conn.cursor()
    
    # Récupérer l'email
    c.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        flash("User not found", "error")
        return redirect("/mfa_verify")
    
    email = row[0]
    
    # Générer un nouveau code
    mfa_code = generate_mfa_code()
    code_hash = generate_password_hash(mfa_code)
    expires_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(minutes=10)
    
    # Insérer le nouveau code
    c.execute("""
        INSERT INTO mfa_codes (user_id, code_hash, expires_at)
        VALUES (%s, %s, %s)
    """, (user_id, code_hash, expires_at))
    
    conn.commit()
    conn.close()
    
    # Envoyer
    if send_mfa_email(email, username, mfa_code):
        flash("New verification code sent!", "success")
    else:
        flash("Failed to send new code", "error")
    
    return redirect("/mfa_verify")

@app.route("/home")
def home():
    if "username" not in session:
        return redirect("/")
    return render_template("home.html")


@app.route("/schedule")
def schedule():
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()
    # On récupère la liste d'amis pour la page Schedule
    c.execute(
        """
        SELECT u.username, u.profile_pic
        FROM friends f
        JOIN users u ON u.username = f.friend
        WHERE f.user_name = %s
        ORDER BY LOWER(u.username)
        """,
        (current,),
    )
    rows = c.fetchall()
    conn.close()

    friends = []
    for username, pic in rows:
        if pic and isinstance(pic, str) and pic.startswith("data:"):
            avatar = pic
        elif pic:
            avatar = f"data:image/png;base64,{pic}"
        else:
            avatar = None

        friends.append({
            "username": username,
            "avatar": avatar,
        })

    return render_template("schedule.html", friends=friends)



@app.route("/settings")
def settings():
    if "username" not in session:
        return redirect("/")
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT username, email, bio, profile_pic, theme, primary_color, bg_color, ink_color, mfa_enabled "
        "FROM users WHERE username = %s",
        (session["username"],),
    )
    u = c.fetchone()
    conn.close()
    if not u:
        return redirect("/")
    user_data = {
        "username": u[0],
        "email": u[1],
        "bio": u[2] or "",
        "profile_pic": u[3],
        "theme": u[4] or "dark",
        "primary_color": u[5] or "#FFD400",
        "bg_color": u[6] or "#1a1a1a",
        "ink_color": u[7] or "#111111",
        "mfa_enabled": u[8] or False,  
    }
    return render_template("settings.html", user=user_data)

@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "username" not in session:
        flash("You must be logged in to delete your account.", "error")
        return redirect(url_for("index"))

    username = session["username"]
    conn = get_conn()
    c = conn.cursor()

    try:
        # Supprimer l'utilisateur
        c.execute("DELETE FROM users WHERE username = %s", (username,))

        # Supprimer ses amis (les deux côtés)
        c.execute("DELETE FROM friends WHERE user_name = %s OR friend = %s", (username, username))

        # Supprimer ses demandes d'amis
        c.execute(
            "DELETE FROM friend_requests WHERE from_user = %s OR to_user = %s",
            (username, username),
        )

        # Supprimer ses plannings
        c.execute("DELETE FROM planning WHERE user_name = %s", (username,))

        conn.commit()
        conn.close()

        # Déconnexion
        session.pop("username", None)

        flash("Your account has been deleted.", "success")
        return redirect(url_for("index"))

    except Exception as e:
        conn.rollback()
        conn.close()
        flash("An error occurred while deleting your account.", "error")
        return redirect(url_for("settings"))


@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT username, bio, profile_pic FROM users WHERE username = %s",
        (session["username"],),
    )
    u = c.fetchone()
    conn.close()

    if not u:
        return redirect("/")

    user_data = {
        "username": u[0],
        "bio": u[1] or "",
        "profile_pic": u[2],
    }
    return render_template("profile.html", user=user_data)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


# ---------------------------
# Appearance settings
# ---------------------------
@app.route("/settings/appearance", methods=["GET", "POST"])
def settings_appearance():
    if "username" not in session:
        return redirect("/")

    if request.method == "GET":
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT theme, primary_color, bg_color, ink_color FROM users WHERE username = %s",
            (session["username"],),
        )
        row = c.fetchone()
        conn.close()

        user_theme = {
            "theme": (row[0] if row and row[0] else "dark"),
            "primary_color": (row[1] if row and row[1] else "#FFD400"),
            "bg_color": (row[2] if row and row[2] else "#1a1a1a"),
            "ink_color": (row[3] if row and row[3] else "#111111"),
        }
        return render_template("settings_appearance.html", user=user_theme)

    # POST → save
    theme = (request.form.get("theme") or "dark").strip()
    primary_color = request.form.get("primary_color") or None
    bg_color = request.form.get("bg_color") or None
    ink_color = request.form.get("ink_color") or None

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE users
        SET theme = %s, primary_color = %s, bg_color = %s, ink_color = %s
        WHERE username = %s
        """,
        (theme, primary_color, bg_color, ink_color, session["username"]),
    )
    conn.commit()
    conn.close()

    return redirect("/settings/appearance")


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "username" not in session:
        return redirect("/")

    print(f"=== DEBUG UPDATE_PROFILE ===")
    print(f"Form data: {dict(request.form)}")
    print(f"Checkbox mfa_enabled present? {'mfa_enabled' in request.form}")
    
    mfa_enabled = "mfa_enabled" in request.form
    print(f"mfa_enabled value: {mfa_enabled}")
    
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    bio = request.form.get("bio", "").strip()

    avatar_file = request.files.get("avatar")
    profile_pic = None
    if avatar_file and avatar_file.filename:
        profile_pic = base64.b64encode(avatar_file.read()).decode("utf-8")

    if not username or not email:
        flash("Username and email are required", "error")
        return redirect("/settings")

    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT id FROM users WHERE email = %s AND username != %s",
        (email, session["username"]),
    )
    if c.fetchone():
        conn.close()
        flash("Email is already used by another account", "error")
        return redirect("/settings")

    MAX_USERNAME_LEN = 20
    if len(username) > MAX_USERNAME_LEN:
        conn.close()
        flash(f"Username must not exceed {MAX_USERNAME_LEN} characters.", "error")
        return redirect("/settings")

    hashed_password = None
    if password:
        MAX_LEN = 32
        import re

        pwd = password

        if " " in pwd:
            conn.close()
            flash("Password must not contain spaces.", "error")
            return redirect("/settings")

        if len(pwd) > MAX_LEN:
            conn.close()
            flash(f"Password must not exceed {MAX_LEN} characters.", "error")
            return redirect("/settings")

        if len(pwd) < 8:
            conn.close()
            flash("Password must be at least 8 characters long.", "error")
            return redirect("/settings")

        if not re.search(r"[0-9]", pwd):
            conn.close()
            flash("Password must contain at least one digit.", "error")
            return redirect("/settings")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>-_]", pwd):
            conn.close()
            flash("Password must contain at least one special character.", "error")
            return redirect("/settings")

        hashed_password = generate_password_hash(password)

    c.execute(
        "SELECT id FROM users WHERE username = %s AND username != %s",
        (username, session["username"]),
    )
    if c.fetchone():
        conn.close()
        flash("Username is already taken", "error")
        return redirect("/settings")

    fields = ["username = %s", "email = %s", "bio = %s", "mfa_enabled = %s"]
    params = [username, email, bio, mfa_enabled]

    if hashed_password is not None:
        fields.append("password = %s")
        params.append(hashed_password)

    if profile_pic:
        fields.append("profile_pic = %s")
        params.append(profile_pic)

    old_username = session["username"]

    params.append(old_username)
    sql = f"UPDATE users SET {', '.join(fields)} WHERE username = %s"
    c.execute(sql, tuple(params))

    if username != old_username:
        c.execute("UPDATE messages SET from_user = %s WHERE from_user = %s", (username, old_username))
        c.execute("UPDATE messages SET to_user   = %s WHERE to_user   = %s", (username, old_username))
        c.execute("UPDATE friends SET user_name  = %s WHERE user_name = %s", (username, old_username))
        c.execute("UPDATE friends SET friend     = %s WHERE friend    = %s", (username, old_username))
        c.execute("UPDATE friend_requests SET from_user = %s WHERE from_user = %s", (username, old_username))
        c.execute("UPDATE friend_requests SET to_user   = %s WHERE to_user   = %s", (username, old_username))
        c.execute("UPDATE planning SET user_name = %s WHERE user_name = %s", (username, old_username))
        c.execute("UPDATE schedule_privacy SET user_name = %s WHERE user_name = %s", (username, old_username))
        c.execute("UPDATE schedule_privacy_custom SET user_name = %s WHERE user_name = %s", (username, old_username))
        c.execute("UPDATE schedule_privacy_custom SET friend    = %s WHERE friend    = %s", (username, old_username))

    conn.commit()
    conn.close()

    session["username"] = username
    flash("Profile updated successfully!", "success")
    return redirect("/settings")


@app.route("/messages/<username>", methods=["GET", "POST"])
def messages(username):
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()

    # Vérifier que l'ami existe
    c.execute(
        "SELECT username, status, profile_pic FROM users WHERE username = %s",
        (username,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        abort(404)

    friend = {
        "username": row[0],
        "status": (row[1] or "online").lower(),
        "profile_pic": row[2],
    }

    # Limites
    MAX_TEXT_LEN   = 1000         # 1000 characters max
    MAX_FILE_SIZE  = 2 * 1024 * 1024  # 2 MB

    # -------------------------
    # POST = envoi de message
    # -------------------------
    if request.method == "POST":
        text = (request.form.get("message") or "").strip()

        # Sécurité serveur : tronquer au cas où le JS ne filtre pas
        if len(text) > MAX_TEXT_LEN:
            text = text[:MAX_TEXT_LEN]

        file = request.files.get("attachment")
        attachment_url = None
        attachment_name = None
        attachment_mime = None

        if file and file.filename:
            # Vérifier la taille du fichier (2 Mo max)
            size = file.content_length
            if size is None:
                # fallback si content_length n'est pas fourni
                file.stream.seek(0, os.SEEK_END)
                size = file.stream.tell()
                file.stream.seek(0)

            if size > MAX_FILE_SIZE:
                conn.close()
                flash("File is too large (maximum allowed size is 2 MB).", "error")
                return redirect(url_for("messages", username=username))

            # on accepte TOUT (image, pdf, txt, etc.)
            original_name = secure_filename(file.filename)
            ext = os.path.splitext(original_name)[1].lower()

            # dossier /static/uploads (crée s'il n'existe pas)
            upload_dir = os.path.join(app.static_folder, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            file_id = uuid4().hex
            stored_name = f"{file_id}{ext}"
            save_path = os.path.join(upload_dir, stored_name)

            file.save(save_path)

            # ce chemin est relatif à /static
            attachment_url = f"uploads/{stored_name}"
            attachment_name = original_name
            attachment_mime = file.mimetype or "application/octet-stream"

        # si pas de texte et pas de fichier → ne rien faire
        if not text and not attachment_url:
            conn.close()
            return redirect(url_for("messages", username=username))

        c.execute(
            """
            INSERT INTO messages (from_user, to_user, content,
                                  attachment_url, attachment_name, attachment_mime)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (current, username, text or "", attachment_url, attachment_name, attachment_mime),
        )
        conn.commit()
        conn.close()

        return redirect(url_for("messages", username=username))

    # -------------------------
    # GET = historique
    # -------------------------
    c.execute(
        """
        SELECT id, from_user, to_user, content, sent_at,
               attachment_url, attachment_name, attachment_mime
        FROM messages
        WHERE (from_user = %s AND to_user = %s)
           OR (from_user = %s AND to_user = %s)
        ORDER BY sent_at ASC, id ASC
        """,
        (current, username, username, current),
    )
    rows = c.fetchall()

    # Marquer comme lus tous les messages que L'AUTRE t'a envoyés
    c.execute(
        """
        UPDATE messages
        SET is_read = TRUE
        WHERE to_user = %s
          AND from_user = %s
          AND is_read = FALSE
        """,
        (current, username),
    )

    conn.commit()
    conn.close()

    messages_list = []
    for msg_id, from_user, to_user, content, sent_at, a_url, a_name, a_mime in rows:
        is_own = (from_user == current)
        time_str = sent_at.strftime("%H:%M") if sent_at else ""
        messages_list.append(
            {
                "id": msg_id,
                "is_own": is_own,
                "text": content,
                "sent_at": time_str,
                "attachment_url": a_url,
                "attachment_name": a_name,
                "attachment_type": a_mime,
            }
        )

    friends_list, incoming_requests, outgoing_requests = _get_friend_context(current)

    return render_template(
        "messages.html",
        friend=friend,
        friends=friends_list,
        messages=messages_list,
    )


@app.route("/messages/<username>/delete/<int:msg_id>", methods=["POST"])
def delete_message(username, msg_id):
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()

    # On ne peut supprimer QUE ses propres messages,
    # dans cette conversation.
    c.execute(
        """
        DELETE FROM messages
        WHERE id = %s
          AND from_user = %s
          AND (to_user = %s OR %s = %s)
        """,
        (msg_id, current, username, current, username),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("messages", username=username))


@app.route("/messages/<username>/edit/<int:msg_id>", methods=["POST"])
def edit_message(username, msg_id):
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    # nouveau nom de champ : "new_text"
    # on garde "new_content" en fallback au cas où
    new_text = (
        request.form.get("new_text")
        or request.form.get("new_content")
        or ""
    ).strip()

    if not new_text:
        return redirect(url_for("messages", username=username))

    conn = get_conn()
    c = conn.cursor()

    # On ne peut éditer QUE ses propres messages
    c.execute(
        """
        UPDATE messages
        SET content = %s
        WHERE id = %s
          AND from_user = %s
          AND (to_user = %s OR %s = %s)
        """,
        (new_text, msg_id, current, username, current, username),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("messages", username=username))

# ---------------------------
# Friends / friend requests
# ---------------------------


def _get_friend_context(username: str):
    """Return (friends_list, incoming_requests, outgoing_requests) for a user.

    friends_list = [{username, status, profile_pic}, ...]
    incoming_requests = [{id, from_user, profile_pic}, ...]
    """
    conn = get_conn()
    c = conn.cursor()

    # Accepted friends (with status + avatar)
    c.execute(
        """
        SELECT u.username, u.status, u.profile_pic
        FROM friends f
        JOIN users u ON u.username = f.friend
        WHERE f.user_name = %s
        ORDER BY LOWER(u.username)
        """,
        (username,),
    )
    friends_rows = c.fetchall()

    # Incoming requests (pending) + requester's avatar
    c.execute(
        """
        SELECT fr.id, fr.from_user, u.profile_pic
        FROM friend_requests fr
        JOIN users u ON u.username = fr.from_user
        WHERE fr.to_user = %s AND fr.status = 'pending'
        ORDER BY fr.created_at ASC
        """,
        (username,),
    )
    incoming_rows = c.fetchall()

    # Outgoing requests
    c.execute(
        "SELECT id, to_user, status FROM friend_requests "
        "WHERE from_user = %s ORDER BY created_at DESC",
        (username,),
    )
    outgoing_rows = c.fetchall()

    conn.close()

    friends_list = [
        {
            "username": r[0],
            "status": (r[1] or "online").lower(),
            "profile_pic": r[2],
        }
        for r in friends_rows
    ]

    incoming_requests = [{"id": r[0], "from_user": r[1], "profile_pic": r[2]} for r in incoming_rows]

    outgoing_requests = [{"id": r[0], "to_user": r[1], "status": r[2]} for r in outgoing_rows]

    return friends_list, incoming_requests, outgoing_requests



@app.route("/api/friends", methods=["GET"])
def api_friends():
    """Retourne la liste des amis du user courant (pour le modal de confidentialité)."""
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    current = session["username"]
    friends_list, _, _ = _get_friend_context(current)

    result = []
    for f in friends_list:
        raw_pic = f.get("profile_pic")
        avatar_url = None
        if raw_pic:
            if isinstance(raw_pic, str) and raw_pic.startswith("data:"):
                avatar_url = raw_pic
            else:
                avatar_url = f"data:image/png;base64,{raw_pic}"

        result.append({
            "username": f["username"],
            "status": f["status"],
            "avatar_url": avatar_url,
        })

    return {"friends": result}, 200


@app.route("/friends")
def friends():
    if "username" not in session:
        return redirect("/")

    username = session["username"]
    friends_list, incoming_requests, outgoing_requests = _get_friend_context(username)

    view = request.args.get("view", "online")
    if view not in ("online", "all"):
        view = "online"

    return render_template(
        "friends.html",
        friends=friends_list,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        view=view,
    )


@app.route("/friends/add")
def friends_add():
    if "username" not in session:
        return redirect("/")

    username = session["username"]
    friends_list, incoming_requests, outgoing_requests = _get_friend_context(username)

    return render_template(
        "friends_add.html",
        friends=friends_list,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
    )
@app.route("/friends/<friend_username>/planning")
def friend_planning(friend_username):
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()

    # 1) Vérifier que l'utilisateur existe
    c.execute(
        "SELECT username, profile_pic FROM users WHERE username = %s",
        (friend_username,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return redirect("/friends")

    raw_pic = row[1]
    friend_avatar_url = None
    if raw_pic:
        if isinstance(raw_pic, str) and raw_pic.startswith("data:"):
            friend_avatar_url = raw_pic
        else:
            friend_avatar_url = f"data:image/png;base64,{raw_pic}"

    friend = {
        "username": row[0],
    }

    # 2) Vérifier que c'est bien ton ami
    c.execute(
        "SELECT 1 FROM friends WHERE user_name = %s AND friend = %s",
        (current, friend_username),
    )
    is_friend = c.fetchone() is not None

    if not is_friend and current != friend_username:
        conn.close()
        return redirect("/friends")

    conn.close()

    # 3) Vérifier les règles de confidentialité du planning de cet ami
    can_view = can_view_friend_schedule(current, friend_username)
    # si tu n'as pas mis le helper, tu peux ici recopier la même logique
    # que dans /api/planning basées sur get_schedule_privacy_settings()

    # 4) Toujours calculer les semaines (même si on ne montrera pas le détail)
    today = datetime.date.today()
    monday1 = today - datetime.timedelta(days=today.weekday())
    monday2 = monday1 + datetime.timedelta(days=7)

    week1_key = monday1.isoformat()
    week2_key = monday2.isoformat()

    first_week = [{"date": monday1 + datetime.timedelta(days=i)} for i in range(7)]
    second_week = [{"date": monday2 + datetime.timedelta(days=i)} for i in range(7)]

    return render_template(
        "friend_planning.html",
        friend=friend,
        friend_avatar_url=friend_avatar_url,
        first_week=first_week,
        second_week=second_week,
        week1_key=week1_key,
        week2_key=week2_key,
        can_view_schedule=can_view,
    )


@app.route("/add_friend", methods=["POST"])
def add_friend():
    """Create a friend request (pending) with feedback messages."""
    if "username" not in session:
        return redirect("/")

    current = session["username"]
    friend_name = (request.form.get("friend") or "").strip()

    if not friend_name:
        flash("Enter a username.", "error")
        return redirect("/friends/add")

    if friend_name == current:
        flash("You can't add yourself.", "error")
        return redirect("/friends/add")

    conn = get_conn()
    c = conn.cursor()

    # Check that the user exists
    c.execute("SELECT 1 FROM users WHERE username = %s", (friend_name,))
    if not c.fetchone():
        conn.close()
        flash("This user does not exist.", "error")
        return redirect("/friends/add")

    # Already friends?
    c.execute(
        "SELECT 1 FROM friends WHERE user_name = %s AND friend = %s",
        (current, friend_name),
    )
    if c.fetchone():
        conn.close()
        flash("You are already friends.", "info")
        return redirect("/friends/add")

    # Friend request already sent BY you and still pending?
    c.execute(
        """
        SELECT status FROM friend_requests
        WHERE from_user = %s AND to_user = %s
        ORDER BY id DESC LIMIT 1
        """,
        (current, friend_name),
    )
    row = c.fetchone()
    if row and row[0] == "pending":
        conn.close()
        flash("You already sent a friend request to this user.", "info")
        return redirect("/friends/add")

    # Existing pending incoming request from them?
    c.execute(
        """
        SELECT id, status FROM friend_requests
        WHERE from_user = %s AND to_user = %s
        ORDER BY id DESC LIMIT 1
        """,
        (friend_name, current),
    )
    row = c.fetchone()
    if row and row[1] == "pending":
        conn.close()
        flash(
            "This user already sent you a request. Go to the Messages tab to accept it.",
            "info",
        )
        return redirect("/friends/add")

    # Otherwise: create / reactivate a new request
    c.execute(
        """
        INSERT INTO friend_requests (from_user, to_user, status)
        VALUES (%s, %s, 'pending')
        ON CONFLICT(from_user, to_user)
        DO UPDATE SET status = 'pending', created_at = CURRENT_TIMESTAMP
        """,
        (current, friend_name),
    )

    conn.commit()
    conn.close()
    flash(f"Friend request sent to {friend_name}.", "success")
    return redirect("/friends/add")


@app.route("/friend_requests/<int:req_id>/accept", methods=["POST"])
def accept_friend_request(req_id):
    """Accept a friend request: create the friendship and mark request as accepted."""
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()

    # Fetch the request
    c.execute(
        "SELECT from_user, to_user, status FROM friend_requests WHERE id = %s",
        (req_id,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return redirect("/friends")

    from_user, to_user, status = row

    # Only the receiver can accept
    if to_user != current or status != "pending":
        conn.close()
        return redirect("/friends")

    # Mark as accepted
    c.execute(
        "UPDATE friend_requests SET status = 'accepted' WHERE id = %s",
        (req_id,),
    )

    # Create friendship links in both directions
    c.execute(
        """
        INSERT INTO friends (user_name, friend) VALUES (%s, %s)
        ON CONFLICT(user_name, friend) DO NOTHING
        """,
        (from_user, to_user),
    )
    c.execute(
        """
        INSERT INTO friends (user_name, friend) VALUES (%s, %s)
        ON CONFLICT(user_name, friend) DO NOTHING
        """,
        (to_user, from_user),
    )

    conn.commit()
    conn.close()
    return redirect("/friends")


@app.route("/remove_friend/<friend>", methods=["POST"])
def remove_friend(friend):
    """Remove the friendship in both directions, without flashing on Add Friend page."""
    if "username" not in session:
        return redirect("/")

    current = session["username"]

    conn = get_conn()
    c = conn.cursor()

    # Delete the relationship in both directions
    c.execute("DELETE FROM friends WHERE user_name = %s AND friend = %s", (current, friend))
    c.execute("DELETE FROM friends WHERE user_name = %s AND friend = %s", (friend, current))

    conn.commit()
    conn.close()

    # No flash, just go back to the friends list (All view)
    return redirect("/friends?view=all")


# ---------------------------
# Persistent status (profile panel)
# ---------------------------
@app.route("/set_status", methods=["POST"])
def set_status():
    """Update the current user's status."""
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    # Support JSON or form
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        new_status = (payload.get("status") or "").strip().lower()
    else:
        new_status = (request.form.get("status") or "").strip().lower()

    allowed = {"online", "idle", "dnd", "invisible"}
    if new_status not in allowed:
        return {"error": "invalid status"}, 400

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE users SET status = %s WHERE username = %s",
        (new_status, session["username"]),
    )
    conn.commit()
    conn.close()

    session["status"] = new_status
    return {"ok": True, "status": new_status}


oauth = OAuth(app)

# Google (OpenID complet)
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    api_base_url="https://openidconnect.googleapis.com/v1/",  # <- important
    client_kwargs={"scope": "openid email profile"},
)

# Facebook
oauth.register(
    name="facebook",
    client_id=os.environ.get("FACEBOOK_CLIENT_ID"),
    client_secret=os.environ.get("FACEBOOK_CLIENT_SECRET"),
    access_token_url="https://graph.facebook.com/v10.0/oauth/access_token",
    authorize_url="https://www.facebook.com/v10.0/dialog/oauth",
    api_base_url="https://graph.facebook.com/",
    client_kwargs={"scope": "email"},
)


# --- OAuth: start auth redirects ---
@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    print("Redirect URI =", redirect_uri)  # debug
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def auth_google_callback():
    # Si l'utilisateur clique sur "Annuler"
    if "error" in request.args:
        flash("Connexion Google annulée.", "error")
        return redirect("/")

    # Récupération du token + des infos user
    token = oauth.google.authorize_access_token()
    resp = oauth.google.get("userinfo")
    userinfo = resp.json()

    email = userinfo.get("email")
    google_pic_url = userinfo.get("picture")
    base_username = (email or "").split("@")[0]

    # Télécharger / convertir l'image de Google en base64
    google_pic_b64 = None
    if google_pic_url:
        google_pic_b64, _ = download_image_as_base64(google_pic_url)

    if not email:
        flash("Impossible de récupérer l'email depuis Google.", "error")
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    # 1) On cherche l'utilisateur EXISTANT par email
    c.execute(
        "SELECT id, username, profile_pic FROM users WHERE email = %s",
        (email,),
    )
    row = c.fetchone()

    if row is None:
        # 2) Nouvel utilisateur -> on doit trouver un username libre
        username = base_username
        suffix = 1
        while True:
            c.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            if not c.fetchone():
                break
            username = f"{base_username}{suffix}"
            suffix += 1

        c.execute(
            "INSERT INTO users (username, email, profile_pic) VALUES (%s, %s, %s)",
            (username, email, google_pic_b64),
        )
        conn.commit()
        session["username"] = username
    else:
        user_id, db_username, db_profile_pic = row

        # 3) Utilisateur déjà existant :
        #    - on garde SON username actuel (db_username)
        #    - on NE REMPLACE la photo QUE s'il n'en a pas encore
        if not db_profile_pic and google_pic_b64:
            c.execute(
                "UPDATE users SET profile_pic = %s WHERE id = %s",
                (google_pic_b64, user_id),
            )
            conn.commit()

        session["username"] = db_username

    conn.close()
    return redirect("/home")


@app.route("/auth/facebook")
def auth_facebook():
    redirect_uri = url_for("auth_facebook_callback", _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)


@app.route("/auth/facebook/callback")
def auth_facebook_callback():
    token = oauth.facebook.authorize_access_token()
    # get user info — request email and picture
    resp = oauth.facebook.get("me?fields=id,name,email,picture.type(large)")
    userinfo = resp.json()
    email = userinfo.get("email")
    name = userinfo.get("name", "")
    fb_id = userinfo.get("id")

    # username par défaut à partir de l'email ou du nom/ID
    default_username = (email or name or fb_id or "user").split("@")[0].replace(" ", "_")

    # Récupération de l'URL de la photo Facebook
    profile_pic_url = None
    pic = userinfo.get("picture")
    if pic and isinstance(pic, dict):
        data = pic.get("data")
        if data:
            profile_pic_url = data.get("url")

    # Télécharger / convertir l'image Facebook en base64
    profile_pic_b64 = None
    if profile_pic_url:
        profile_pic_b64, _ = download_image_as_base64(profile_pic_url)

    conn = get_conn()
    c = conn.cursor()

    # Comme pour Google : priorité à l'email si présent
    if email:
        c.execute("SELECT id, username FROM users WHERE email = %s", (email,))
        row = c.fetchone()
    else:
        # Pas d'email → on essaie via username par défaut
        c.execute("SELECT id, username FROM users WHERE username = %s", (default_username,))
        row = c.fetchone()

    if row:
        user_id, db_username = row
        if profile_pic_b64:
            c.execute(
                "UPDATE users SET profile_pic = %s WHERE id = %s",
                (profile_pic_b64, user_id),
            )
            conn.commit()
        conn.close()

        session["username"] = db_username
        return redirect("/home")

    # Sinon création d'un nouvel utilisateur, en s'assurant que le username est unique
    base_username = default_username or "user"
    candidate = base_username
    suffix = 1
    while True:
        c.execute("SELECT 1 FROM users WHERE username = %s", (candidate,))
        if not c.fetchone():
            break
        suffix += 1
        candidate = f"{base_username}{suffix}"

    username = candidate

    c.execute(
        "INSERT INTO users (username, email, profile_pic) VALUES (%s, %s, %s)",
        (username, email, profile_pic_b64),
    )
    conn.commit()
    conn.close()

    session["username"] = username
    return redirect("/home")


# ---------------------------
# API PLANNING (Schedule)
# ---------------------------

@app.route("/api/planning", methods=["GET"])
def api_get_planning():
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    current_user = session["username"]
    week = request.args.get("week")
    target_user = request.args.get("user") or current_user  # ami ou soi-même

    if not week:
        return {"error": "missing week"}, 400

    conn = get_conn()
    c = conn.cursor()

    # 1) Si je regarde le planning de quelqu'un d'autre,
    #    vérifier qu'on est amis
    if target_user != current_user:
        c.execute(
            "SELECT 1 FROM friends WHERE user_name = %s AND friend = %s",
            (current_user, target_user),
        )
        if not c.fetchone():
            conn.close()
            return {"error": "not_friends"}, 403

        # 2) Vérifier les réglages de confidentialité de CET utilisateur
        privacy = get_schedule_privacy_settings(target_user)
        mode = privacy["mode"]
        allowed = set(privacy["allowed"])

        # mode 'none' → personne ne voit
        if mode == "none":
            conn.close()
            return {"error": "schedule_hidden"}, 403

        # mode 'custom' → seulement certains amis
        if mode == "custom" and current_user not in allowed:
            conn.close()
            return {"error": "schedule_hidden"}, 403

        # mode 'friends' ou 'everyone' → OK (on a déjà checké friend plus haut)

    # 3) Récupérer les données de planning
    c.execute(
        """
        SELECT cell_id, content, state
        FROM planning
        WHERE user_name = %s AND week = %s
        ORDER BY cell_id ASC
        """,
        (target_user, week),
    )
    rows = c.fetchall()
    conn.close()

    items = [{"cell_id": r[0], "content": r[1] or "", "state": r[2]} for r in rows]
    return {"items": items}, 200


@app.route("/api/planning/user/<username>", methods=["GET"])
def api_get_planning_for_user(username):
    """
    Récupère le planning d'un utilisateur donné (lecture seule),
    pour une semaine précise.
    Utilisé pour consulter le planning d'un ami.
    """
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    current = session["username"]
    week = request.args.get("week")

    if not week:
        return {"error": "missing week"}, 400

    conn = get_conn()
    c = conn.cursor()

    # Vérifier que le user existe
    c.execute("SELECT 1 FROM users WHERE username = %s", (username,))
    if not c.fetchone():
        conn.close()
        return {"error": "user_not_found"}, 404

    # Optionnel : vérifier la relation d'amitié
    if username != current:
        c.execute(
            "SELECT 1 FROM friends WHERE user_name = %s AND friend = %s",
            (current, username),
        )
        if not c.fetchone():
            conn.close()
            return {"error": "not_friends"}, 403

    # Récupérer le planning de CET utilisateur pour CETTE semaine
    c.execute(
        """
        SELECT cell_id, content, state
        FROM planning
        WHERE user_name = %s AND week = %s
        ORDER BY cell_id ASC
        """,
        (username, week),
    )
    rows = c.fetchall()
    conn.close()

    items = [{"cell_id": r[0], "content": r[1] or "", "state": r[2]} for r in rows]

    return {"items": items}, 200




@app.route("/api/planning", methods=["POST"])
def api_save_planning():
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    username = session["username"]

    payload = request.get_json()
    week = payload.get("week")
    items = payload.get("items", [])

    if not week:
        return {"error": "missing week"}, 400

    conn = get_conn()
    c = conn.cursor()

    for it in items:
        cell_id = it["cell_id"]
        content = it["content"]
        state = it["state"]

        c.execute(
            """
            INSERT INTO planning (user_name, cell_id, content, state, week)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(user_name, cell_id, week)
            DO UPDATE SET
                content = EXCLUDED.content,
                state = EXCLUDED.state,
                updated_at = CURRENT_TIMESTAMP
            """,
            (username, cell_id, content, state, week),
        )

    conn.commit()
    conn.close()

    return {"ok": True}, 200

@app.route("/api/schedule/privacy", methods=["GET", "POST"])
def api_schedule_privacy():
    """Lire / sauvegarder les réglages de confidentialité du planning."""
    if "username" not in session:
        return {"error": "unauthenticated"}, 401

    current = session["username"]

    if request.method == "GET":
        info = get_schedule_privacy_settings(current)
        return {
            "mode": info["mode"],
            "allowed_friends": info["allowed"],
        }, 200

    # POST
    payload = request.get_json(silent=True) or {}
    mode = (payload.get("mode") or "friends").lower()
    allowed = payload.get("allowed_friends") or []

    allowed_modes = {"everyone", "friends", "none", "custom"}
    if mode not in allowed_modes:
        return {"error": "invalid_mode"}, 400

    conn = get_conn()
    c = conn.cursor()

    # upsert de la ligne principale
    c.execute(
        """
        INSERT INTO schedule_privacy (user_name, mode)
        VALUES (%s, %s)
        ON CONFLICT(user_name)
        DO UPDATE SET mode = EXCLUDED.mode
        """,
        (current, mode),
    )

    # on vide puis on recrée la liste custom
    c.execute(
        "DELETE FROM schedule_privacy_custom WHERE user_name = %s",
        (current,),
    )

    if mode == "custom" and allowed:
        for friend in allowed:
            c.execute(
                """
                INSERT INTO schedule_privacy_custom (user_name, friend)
                VALUES (%s, %s)
                ON CONFLICT(user_name, friend) DO NOTHING
                """,
                (current, friend),
            )

    conn.commit()
    conn.close()
    return {"ok": True}, 200



# -----------
# Run local
# -----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
