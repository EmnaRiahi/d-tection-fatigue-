import cv2
import mediapipe as mp
import math
import time
import pygame
import os
import json
import urllib.request
import threading

# --- INITIALISATION ---
pygame.mixer.init()
if os.path.exists("alarme.mp3"):
    pygame.mixer.music.load("alarme.mp3")

BACKEND_URL = "http://localhost:5000/api/driver-alerts"

def _async_backend(payload):
    try:
        req = urllib.request.Request(BACKEND_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=1)
    except: pass

def envoyer_alerte_backend(type_alerte, ear, mar, angle, duree):
    try:
        payload = json.dumps({"alert_type": type_alerte, "ear": round(ear, 3), "mar": round(mar, 3), "angle": round(angle, 1), "duration_s": round(duree, 1)}).encode("utf-8")
        threading.Thread(target=_async_backend, args=(payload,), daemon=True).start()
    except: pass

# --- RÉGLAGES DE STABILITÉ (CORRECTION BEUG) ---
SEUIL_EAR = 0.20        # Descendu de 0.22 à 0.20 (moins de fausses alertes yeux)
SEUIL_YAW = 0.08        # Augmenté (plus de liberté gauche/droite)
SEUIL_PITCH = 0.08      # Augmenté (plus de liberté haut/bas)
TIME_LIMIT = 1.8        # Un peu plus long pour confirmer le vrai danger
SMOOTH_FACTOR = 0.5     # Pour lisser les mouvements brusques

# Couleurs
NOIR, BLANC, ROUGE, VERT, ORANGE, GRIS, CYAN = (0,0,0), (255,255,255), (0,0,255), (0,255,0), (0,165,255), (100,100,100), (255,255,0)
BLEU_FONCE = (50, 50, 50)

def dessiner_panneau(image, titre, valeur, statut, x, y):
    cv2.rectangle(image, (x, y), (x + 200, y + 60), BLEU_FONCE, -1)
    cv2.rectangle(image, (x, y), (x + 200, y + 60), GRIS, 1)
    couleur = VERT if statut == "ok" else (ORANGE if statut == "warning" else ROUGE)
    cv2.rectangle(image, (x, y), (x + 5, y + 60), couleur, -1)
    cv2.putText(image, titre, (x + 12, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, GRIS, 1)
    cv2.putText(image, valeur, (x + 12, y + 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)

def dessiner_barre_fatigue(image, score, x, y):
    cv2.rectangle(image, (x, y), (x + 200, y + 20), BLEU_FONCE, -1)
    fill = int((score / 100) * 200)
    couleur = VERT if score < 30 else (ORANGE if score < 60 else ROUGE)
    if fill > 0: cv2.rectangle(image, (x, y), (x + fill, y + 20), couleur, -1)
    cv2.putText(image, f"VIGILANCE: {100-score}%", (x + 5, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, BLANC, 1)

def distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

# --- INITIALISATION IA ---
mp_face = mp.solutions.face_mesh
detecteur = mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.7) # Confiance augmentée
# --- NOUVEAU CODE (ESP32-CAM) ---
# 1. Remplace l'adresse IP ci-dessous par celle de TON ESP32
url_esp32 = "http://10.15.246.74" 

print(f"🔗 Connexion au flux ESP32-CAM : {url_esp32}")
camera = cv2.VideoCapture(url_esp32)

# 2. OPTIMISATION : Supprimer le retard (Lag)
# On dit à OpenCV de ne pas garder d'images en mémoire tampon
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

temps_danger = None
alarme_active = False
arreter = [False]
historique_ear = []
yaw_prev = pitch_prev = 0

def clic_sur_stop(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and x >= 640 and y >= 430: param[0] = True

cv2.namedWindow("S.A.V.E.S - Stable Monitor")
cv2.setMouseCallback("S.A.V.E.S - Stable Monitor", clic_sur_stop, arreter)

while True:
    if arreter[0]: break
    ok, image = camera.read()
    if not ok: break
    
    image = cv2.flip(image, 1)
    h_img, w_img = image.shape[:2]
    cadre = cv2.copyMakeBorder(image, 0, 0, 0, 220, cv2.BORDER_CONSTANT, value=NOIR)
    x_panneau = w_img + 10

    # UI HEADER
    cv2.rectangle(cadre, (w_img, 0), (w_img + 220, 60), (30, 30, 30), -1)
    cv2.putText(cadre, "S.A.V.E.S", (x_panneau + 30, 35), 0, 0.8, VERT, 2)

    statut_yeux = statut_tete = "ok"
    valeur_yeux, valeur_tete = "Ouverts", "Route"
    danger_reel = False

    results = detecteur.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    if results.multi_face_landmarks:
        p = results.multi_face_landmarks[0].landmark
        
        # 1. EAR Lissé
        g = [p[i] for i in [362, 385, 387, 263, 373, 380]]
        d = [p[i] for i in [33, 160, 158, 133, 153, 144]]
        ear = ((distance(g[1], g[5]) + distance(g[2], g[4])) / (2.0 * distance(g[0], g[3])) + 
               (distance(d[1], d[5]) + distance(d[2], d[4])) / (2.0 * distance(d[0], d[3]))) / 2.0
        
        historique_ear.append(ear)
        if len(historique_ear) > 100: historique_ear.pop(0)

        # 2. Regard avec Zone de Tolérance
        eye_x = (p[33].x + p[263].x) / 2
        eye_y = (p[33].y + p[263].y) / 2
        yaw = (p[4].x - eye_x)
        pitch = (p[4].y - eye_y)

        # Logique de détection robuste
        if ear < SEUIL_EAR:
            valeur_yeux = "FERMES"
            danger_reel = True
        
        # On vérifie si on sort de la "Safe Zone" (le carré central)
        if abs(yaw) > SEUIL_YAW: 
            valeur_tete = "GAUCHE" if yaw < 0 else "DROITE"
            danger_reel = True
        elif pitch > SEUIL_PITCH: 
            valeur_tete = "BAS (TEL)"
            danger_reel = True
        elif pitch < -SEUIL_PITCH:
            valeur_tete = "HAUT"
            danger_reel = True

        # GESTION DES ALERTES (Anti-sursaut)
        if danger_reel:
            if temps_danger is None: temps_danger = time.time()
            duree = time.time() - temps_danger
            
            # Phase 1 : Warning visuel (Orange) après 0.5s
            if duree > 0.5:
                statut_yeux = statut_tete = "warning"
            
            # Phase 2 : Danger réel (Rouge + Son) après 1.8s
            if duree >= TIME_LIMIT:
                statut_yeux = statut_tete = "danger"
                if not alarme_active: 
                    pygame.mixer.music.play(-1)
                    alarme_active = True
                envoyer_alerte_backend("DANGER", ear, 0, yaw, duree)
        else:
            temps_danger = None
            if alarme_active:
                pygame.mixer.music.stop()
                alarme_active = False

        score_fatigue = int(min((1 - ear/0.3) * 100 if ear < 0.28 else 0, 100))

    # AFFICHAGE FINAL
    dessiner_panneau(cadre, "YEUX", valeur_yeux, statut_yeux, x_panneau, 75)
    dessiner_panneau(cadre, "REGARD", valeur_tete, statut_tete, x_panneau, 150)
    dessiner_barre_fatigue(cadre, score_fatigue, x_panneau, h_img - 155)

    # Graphique EAR
    if len(historique_ear) > 1:
        for i in range(1, len(historique_ear)):
            cv2.line(cadre, (w_img+10+i*2, h_img-20-int(historique_ear[i-1]*100)), 
                     (w_img+12+i*2, h_img-20-int(historique_ear[i]*100)), CYAN, 1)

    # Bouton STOP
    cv2.rectangle(cadre, (w_img, h_img - 50), (w_img + 220, h_img), ROUGE, -1)
    cv2.putText(cadre, "STOP", (x_panneau + 65, h_img - 15), 0, 0.7, BLANC, 2)

    cv2.imshow("S.A.V.E.S - Full Monitoring", cadre)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

camera.release()
cv2.destroyAllWindows()