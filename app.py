from flask import Flask, render_template, request, redirect, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
app.secret_key = "secret"

# ================== DATA ==================
users = {}
user = {}
tokens = {}


failed_attempts = {}
user_attacks = {}
lock_until = {}
attack_data = []
last_attacked_user = None

# store attack attempts globally for graph
attack_data = []

# ================== BLOCKCHAIN ==================
class Block:
    def __init__(self, index, data, prev_hash):
        self.index = index
        self.timestamp = str(datetime.now())
        self.data = data
        self.prev_hash = prev_hash
        self.hash = self.generate_hash()

    def generate_hash(self):
        return hashlib.sha256(
            f"{self.index}{self.timestamp}{self.data}{self.prev_hash}".encode()
        ).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [Block(0, {"action": "genesis"}, "0")]

    def add_block(self, data):
        prev = self.chain[-1]
        block = Block(len(self.chain), data, prev.hash)
        self.chain.append(block)

blockchain = Blockchain()

# ================== ROUTES ==================

@app.route("/")
def index():
    return render_template("index.html")

# ================== REGISTER ==================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]
        confirm = request.form["confirm"]

        if pwd != confirm:
            return render_template("register.html", error="Passwords do not match")

        users[user] = generate_password_hash(pwd)
        tokens[user] = 50

        blockchain.add_block({
            "user": user,
            "action": "register"
        })

        return render_template("register.html", success=True)

    return render_template("register.html")

# ================== LOGIN ==================
@app.route("/login", methods=["GET", "POST"])
def login():
    global attack_data, lock_until, user_attacks, failed_attempts, last_attacked_user

    if request.method == "POST":

        user = request.form["username"]
        pwd = request.form["password"]

        # Initialize dictionaries
        failed_attempts.setdefault(user, 0)
        user_attacks.setdefault(user, 0)

        # 🔒 Lock Check
        if user in lock_until:

            if datetime.now() < lock_until[user]:

                remaining = int(
                    (lock_until[user] - datetime.now()).total_seconds()
                )

                return render_template(
                    "login.html",
                    error=f"🚨 Account Locked! Wait {remaining} seconds"
                )

            else:
                # Lock expired
                del lock_until[user]
                failed_attempts[user] = 0

        # ✅ Successful Login
        if user in users and check_password_hash(users[user], pwd):

            session["user"] = user

            # Reset failed attempts
            failed_attempts[user] = 0

            return redirect("/dashboard")

        # ❌ Failed Login
        last_attacked_user = user

        failed_attempts[user] += 1
        user_attacks[user] += 1

        attack_data.append(failed_attempts[user])

        print("FAILED USER:", user)
        print("FAILED ATTEMPTS:", failed_attempts[user])

        # 🔒 Lock after 5 attempts
        if failed_attempts[user] >= 5:

            lock_until[user] = datetime.now() + timedelta(seconds=30)

            print("LOCKED:", user)

            return render_template(
                "login.html",
                error="🚨 Account Locked for 30 seconds"
            )

        # Normal failed login
        return render_template(
            "login.html",
            error=f"❌ Unauthorize Access Identified " #(Attempts:  {failed_attempts[user]})"
        )

    # First page load
    return render_template("login.html")

# ================== DASHBOARD ==================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    
    total_attacks = user_attacks.get(user, 0)

    history = [tokens[user]-10, tokens[user]-5, tokens[user]]

    # ✅ get user-specific attacks
    attacks = user_attacks.get(user, 0)

    return render_template(
        "dashboard.html",
        user=user,
        token=tokens[user],
        chain=blockchain.chain,
        history=history,
        attacks=attack_data,      # for graph
        total_attacks=total_attacks     # for counter
    )
   
# ================== ATTACK STATUS ==================

@app.route("/attack_status")
def attack_status():

    global last_attacked_user

    user = session.get("user")

    # If not logged in, show attacks for the username currently being attacked
    if not user:
        user = last_attacked_user

    #attempts = user_attacks.get(user, 0)
    attempts = failed_attempts.get(user, 0) 
    
    threat_score = attempts * 3

    if threat_score < 2:
        status = "Low Risk ✅"
    elif threat_score < 5:
        status = "Medium Risk ⚠️"
    else:
        status = "High Risk 🚨"

    locked = False
    remaining = 0

    if user in lock_until:

        if datetime.now() < lock_until[user]:

            locked = True

            remaining = int(
                (lock_until[user] - datetime.now()).total_seconds()
            )

    return jsonify({
        "attempts": attempts,
        "status": status,
        "score": threat_score,
        "locked": locked,
        "remaining": remaining
    })
# ================== ATTACK GRAPH DATA ==================
@app.route("/attack_data")
def attack_data_api():
    return jsonify({"data": attack_data})

# ================== MANUAL HASH ==================
@app.route("/manual_hash", methods=["GET", "POST"])
def manual_hash():
    if request.method == "POST":
        user = request.form["username"]
        input_hash = request.form["hash"]

        if user in users and users[user] == input_hash:
            result = "✅ Hash Verified"
            blockchain.add_block({
                "user": user,
                "action": "manual_hash"
            })
        else:
            result = "❌ Invalid Hash"

        return render_template("manual_hash.html", result=result)

    return render_template("manual_hash.html")

# ================== DOWNLOAD LOG ==================
@app.route("/download_logs")
def download_logs():
    content = ""

    for block in blockchain.chain:
        content += f"{block.index} | {block.data}\n"

    with open("logs.txt", "w") as f:
        f.write(content)

    return send_file("logs.txt", as_attachment=True)

# ================== COMPARISON ==================
@app.route("/comparison")
def comparison():
    performance_data = {
        "traditional": [5, 4, 5, 3, 4],
        "blockchain": [9, 9, 8, 9, 9]
    }

    return render_template(
        "comparison.html",
        performance_data=performance_data
    )

# ================== EXPLORER ==================
@app.route("/explorer")
def explorer():
    return render_template(
        "explorer.html",
        chain=blockchain.chain,
        users=users
    )

# ================== LOGOUT ==================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================== RUN ==================
if __name__ == "__main__":
    app.run(debug=True)
