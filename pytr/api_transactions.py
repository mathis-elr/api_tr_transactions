import asyncio
import io
from pathlib import Path
from flask import Flask, jsonify, request, abort
from pytr.account import login
from pytr.timeline import Timeline
from pytr.event import Event
from pytr.transactions import TransactionExporter
from pytr.api import TradeRepublicApi
import json

app = Flask(__name__)
tr_api = None

# On définit une clé ultra secrète (change-la !)
API_KEY = "lesapicestcoolencoremieuxquandcestautomatique"

def check_auth():
    # On vérifie si la clé est dans les headers de la requête
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        abort(401) # Erreur : Non autorisé

def get_create_tr_api():
    global tr_api
    if tr_api is None:
        # Remplace par tes vrais identifiants
        tr_api = TradeRepublicApi(phone_no="+33779867060", pin="1938", save_cookies=True)

    is_connected = tr_api.resume_websession()
    return tr_api, is_connected

@app.route('/auth/request-sms', methods=['POST'])
def demande_code_sms():
    api, connected = get_create_tr_api()

    if(connected):
        try:
            # On tente une mini-requête réelle vers Trade Republic
            api.settings()
            # Si ça marche, on stoppe tout : l'utilisateur est déjà prêt
            return jsonify({"status": "already_connected", "message": "Session encore valide, pas de SMS requis."})
        except Exception:
            # Si ça plante, c'est que le fichier est expiré. On continue vers le SMS.
            print("Session disque expirée, déclenchement du SMS...")

    try:
        countdown = api.initiate_weblogin()
        return jsonify({"status": "sms_sent", "countdown": countdown})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auth/confirm-sms', methods=['POST'])
def get_code_sms():
    global tr_api
    data = request.json
    code_sms = data.get('code')

    if tr_api is None:
        return jsonify({"error": "Session non initialisée"}), 400

    try:
        # ON VALIDE LE CODE
        tr_api.complete_weblogin(code_sms)
        return jsonify({"status": "success", "message": "Authentification réussie"})
    except Exception as e:
        return jsonify({"error": f"Code invalide : {str(e)}"}), 401

@app.route('/transactions', methods=['GET'])
def get_transactions():
    api, connected = get_create_tr_api()
    if not connected:
        return jsonify({"error": "Authentification requise (SMS)"}), 403

    try:
        # --- GESTION PROPRE DE LA BOUCLE POUR SERVEUR ---
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        tl = Timeline(tr=api, output_path=Path("."), store_event_database=False)
        loop.run_until_complete(tl.tl_loop())
        loop.close()

        # Sécurité contre le bug 'startswith'
        events = []
        for ev in tl.events:
            try:
                events.append(Event.from_dict(ev))
            except:
                continue  # On ignore les transactions qui font bugger pytr

        exporter = TransactionExporter(lang="fr")
        output = io.StringIO()
        all_txns = exporter.export(output, events, format="json", sort=True)

        return jsonify(all_txns)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


    except Exception as e:
        print(f"ERREUR : {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000, debug=True)