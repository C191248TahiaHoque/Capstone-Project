from flask import Flask, render_template, request, redirect, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import hashlib
from blockchain import Blockchain
import json
import time


print("Blockchain loaded from:")
import blockchain
print(blockchain.__file__)
blockchain = Blockchain()
#print(Blockchain)
#print(Blockchain.__module__)

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
    def __init__(self, index, data, previous_hash):

        self.index = index
        self.timestamp = str(datetime.now())
        self.data = data
        self.previous_hash = previous_hash

        self.hash = self.generate_hash()
        
    def calculate_hash(self):
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }
        
    def generate_hash(self):

        block_string = (
            str(self.index)
            + self.timestamp
            + str(self.data)
            + self.previous_hash
        )

        return hashlib.sha256(
            block_string.encode()
        ).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [Block(0, {"action": "genesis"}, "0")]

    def add_block(self, data):
        previous = self.chain[-1]

        block = Block(
            len(self.chain),
            data,
            previous.hash
        )

        self.chain.append(block)

    def is_valid(self):

        for i in range(1, len(self.chain)):

            current = self.chain[i]
            previous = self.chain[i - 1]

            # Verify link
            if current.previous_hash != previous.hash:
                return False

            # Verify hash
            if current.calculate_hash() != current.hash:
                return False

        return True

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

        user_id = hashlib.sha256(
        user.encode()
        ).hexdigest()[:12]
        #user = request.form["username"]
        pwd = request.form["password"]
        #user_id = hashlib.sha256(user.encode()).hexdigest()[:12]
        confirm = request.form["confirm"]

        if pwd != confirm:
            return render_template("register.html", error="Passwords do not match")

        users[user] = generate_password_hash(pwd)
        tokens[user] = 50

        blockchain.add_block({
            "user": user,
            "user_id": hashlib.sha256(user.encode()).hexdigest()[:12],
            "action": "Identity Created",
            "password_hash": users[user]
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
    result = None
    block_info = None

    if request.method == "POST":
        input_hash = request.form["hash"]

        for block in blockchain.chain:
            if block.hash == input_hash:
                block_info = block
                result = "✅ Valid Block Found"
                break

        if not block_info:
            result = "❌ Invalid Hash"

        return render_template(
            "manual_hash.html",
            result=result,
            block=block_info
        )

    return render_template("manual_hash.html")

def generate_hash(block):
    block_data = {
        "index": block["index"],
        "timestamp": block["timestamp"],
        "data": block["data"],
        "previous_hash": block["previous_hash"]
    }

    block_string = json.dumps(block_data, sort_keys=True)
    return hashlib.sha256(block_string.encode()).hexdigest()

def calculate_hash_from_block(block):
    block_data = {
        "index": block.index,
        "timestamp": block.timestamp,
        "data": block.data,
        "previous_hash": block.previous_hash
    }

    block_string = json.dumps(block_data, sort_keys=True)
    return hashlib.sha256(block_string.encode()).hexdigest()

@app.route("/verify_hash", methods=["POST"])
def verify_hash():
    user_hash = request.form["hash"]

    for block in blockchain.chain:
        if block.hash == user_hash:
            return {"status": "VALID"}

    return {"status": "INVALID"}

@app.route("/verify_block/<int:index>")
def verify_block(index):
    block = blockchain.chain[index]

    temp_data = {
        "index": block.index,
        "timestamp": block.timestamp,
        "data": block.data,
        "previous_hash": block.previous_hash
    }

    recomputed = hashlib.sha256(
        json.dumps(temp_data, sort_keys=True).encode()
    ).hexdigest()

    return {
        "stored_hash": block.hash,
        "recomputed_hash": recomputed,
        "valid": block.hash == recomputed
    }

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
def validate_chain():
    
    for i in range(1, len(blockchain.chain)):

        current = blockchain.chain[i]
        previous = blockchain.chain[i - 1]

        if current.previous_hash != previous.hash:
            return False

        if current.hash != current.generate_hash():
            return False

    return True

@app.route("/explorer")
def explorer():

    current_user = session.get("user")

    validated_chain = []

    for block in blockchain.chain:

        validated_chain.append({
            "index": block.index,
            "timestamp": block.timestamp,
            "data": block.data,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "valid": True  # assume valid, blockchain.is_valid() handles full check
        })

    chain_valid = blockchain.is_valid()

    return render_template(
        "explorer.html",
        chain=validated_chain,
        valid=chain_valid,
        current_user=current_user,
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
