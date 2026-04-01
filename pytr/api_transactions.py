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

    check_auth()
    api, connected = get_create_tr_api()

    if not connected:
        return jsonify({"error": "Authentification requise (SMS)"}), 403

    try:
        # 1. Initialiser la Timeline en forçant tout en mémoire (pas de fichiers)
        tl = Timeline(
            tr=api,
            output_path=Path("."),
            not_before=0,
            not_after=float("inf"),
            store_event_database=False,
            scan_for_duplicates=False,
            dump_raw_data=False
        )

        asyncio.run(tl.tl_loop())

        # 1. On crée les objets Event (ceux qui ont maintenant le prix !)
        events = [Event.from_dict(ev) for ev in tl.events]

        # 2. On prépare l'exportateur
        exporter = TransactionExporter(lang="fr")

        # 3. LE TRUC MAGIQUE : On crée un fichier virtuel en mémoire
        output = io.StringIO()

        # 4. On appelle la fonction EXACTE du terminal
        all_txns = exporter.export(output, events, format="json", sort=True)

        # 5. On renvoie directement cette liste
        return jsonify(all_txns)


    except Exception as e:
        print(f"ERREUR : {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5000, debug=True)