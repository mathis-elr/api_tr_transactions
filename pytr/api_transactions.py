import asyncio
import io
from pathlib import Path
from flask import Flask, jsonify, request, abort
from pytr.account import login
from pytr.timeline import Timeline
from pytr.event import Event
from pytr.transactions import TransactionExporter

app = Flask(__name__)
tr = None

# On définit une clé ultra secrète (change-la !)
API_KEY = "ton_code_ultra_secret_12345"

def check_auth():
    # On vérifie si la clé est dans les headers de la requête
    key = request.headers.get('X-API-KEY')
    if key != API_KEY:
        abort(401) # Erreur : Non autorisé

def init_tr():
    global tr
    if tr is None:
        try:
            print("Restauration de la session Web Trade Republic...")
            # On utilise la fonction de login de haut niveau de pytr.
            # web=True lui dit d'utiliser ton fichier cookies.txt
            # S'il le trouve, la connexion est instantanée sans mot de passe !
            tr = login(web=True)
            print("Connecté avec succès !")
        except Exception as e:
            print(f"Erreur de connexion : {e}")
            raise
    return tr


init_tr()


@app.route('/transactions', methods=['GET'])
def get_transactions():

    check_auth()

    try:
        api = init_tr()

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
    app.run(port=5000, debug=True)