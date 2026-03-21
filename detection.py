import cv2
import mediapipe as mp
import math
import time
import pygame
import csv
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from config import GMAIL_EXPEDITEUR, GMAIL_MOT_PASSE, GMAIL_DESTINATAIRE

#  Initialiser le son 
pygame.mixer.init()
pygame.mixer.music.load("alarme.mp3")

#  Dossier de logs 
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

#  Initialiser le fichier CSV 
with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Horodatage", "Type_Alerte", "EAR", "MAR", "Angle", "Duree_s"])

def log_alerte(type_alerte, ear, mar, angle, duree):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            type_alerte,
            f"{ear:.3f}",
            f"{mar:.3f}",
            f"{angle:.1f}",
            f"{duree:.1f}"
        ])

#  Fonction pour envoyer un Email 
def envoyer_sms(message):
    try:
        msg = MIMEText(message)
        msg["Subject"] = "🚨 ALERTE DriverGuard"
        msg["From"]    = f"DriverGuard <{GMAIL_EXPEDITEUR}>"
        msg["To"]      = GMAIL_DESTINATAIRE
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_EXPEDITEUR, GMAIL_MOT_PASSE)
            smtp.send_message(msg)
        print(f"Email envoyé : {message}")
    except Exception as e:
        print(f"Erreur Email : {e}")

#  Indices des points des yeux 
OEIL_GAUCHE = [362, 385, 387, 263, 373, 380]
OEIL_DROIT  = [33,  160, 158, 133, 153, 144]

#  Indices des points de la bouche 
BOUCHE = [13, 14, 78, 308]

#  Indices pour la détection de la tête 
COIN_DROIT  = 33
COIN_GAUCHE = 263

#  Nez (pour détection regard hors route) 
NEZ_BOUT    = 4
NEZ_RACINE  = 6

#  Seuils 
SEUIL_EAR          = 0.25
SEUIL_MAR          = 0.5
SEUIL_ANGLE        = 20
SEUIL_TEMPS_YEUX   = 2.0
SEUIL_TEMPS_BOUCHE = 1.0
SEUIL_TEMPS_TETE   = 2.0
SEUIL_TEMPS_REGARD = 2.5   # Nouveau : regard détourné
SEUIL_CLIGNEMENTS  = 25    # Nouveau : clignements/min anormaux
DELAI_SMS          = 60

# Couleurs 
NOIR        = (0,   0,   0)
BLANC       = (255, 255, 255)
ROUGE       = (0,   0,   255)
VERT        = (0,   255, 0)
ORANGE      = (0,   165, 255)
JAUNE       = (0,   255, 255)
BLEU_FONCE  = (50,  50,  50)
GRIS        = (100, 100, 100)
CYAN        = (255, 255, 0)

#  Fonction distance 
def distance(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

#  Fonction EAR 
def calculer_ear(points, indices):
    p1 = points[indices[0]]
    p2 = points[indices[1]]
    p3 = points[indices[2]]
    p4 = points[indices[3]]
    p5 = points[indices[4]]
    p6 = points[indices[5]]
    hauteur1 = distance(p2, p6)
    hauteur2 = distance(p3, p5)
    largeur  = distance(p1, p4)
    return (hauteur1 + hauteur2) / (2.0 * largeur)

#  Fonction MAR 
def calculer_mar(points, indices):
    haut   = points[indices[0]]
    bas    = points[indices[1]]
    gauche = points[indices[2]]
    droit  = points[indices[3]]
    hauteur = distance(haut, bas)
    largeur = distance(gauche, droit)
    if largeur == 0:
        return 0
    return hauteur / largeur

#  Fonction angle de la tête 
def calculer_angle_tete(points):
    oeil_droit  = points[COIN_DROIT]
    oeil_gauche = points[COIN_GAUCHE]
    dx = oeil_gauche.x - oeil_droit.x
    dy = oeil_gauche.y - oeil_droit.y
    return math.degrees(math.atan2(dy, dx))

#  Nouvelle : Détection du regard (pose de la tête verticale) 
def calculer_inclinaison_verticale(points):
    """Estime si la tête est penchée vers l'avant (assoupissement)."""
    nez_bout   = points[NEZ_BOUT]
    nez_racine = points[NEZ_RACINE]
    dy = nez_bout.y - nez_racine.y
    return dy  # > 0 = tête penchée vers le bas

#  Nouvelle : Score de fatigue global
def calculer_score_fatigue(ear, mar, angle, clignements_par_min, inclinaison):
    score = 0
    if ear < SEUIL_EAR:        score += 30
    elif ear < 0.28:           score += 10
    if mar > SEUIL_MAR:        score += 20
    elif mar > 0.35:           score += 5
    if abs(angle) > SEUIL_ANGLE: score += 25
    elif abs(angle) > 10:      score += 8
    if clignements_par_min > SEUIL_CLIGNEMENTS: score += 15
    if inclinaison > 0.08:     score += 10
    return min(score, 100)

#  Fonction dessiner un panneau d'information 
def dessiner_panneau(image, titre, valeur, statut, x, y, largeur=200, hauteur=60):
    cv2.rectangle(image, (x, y), (x + largeur, y + hauteur), BLEU_FONCE, -1)
    cv2.rectangle(image, (x, y), (x + largeur, y + hauteur), GRIS, 1)
    if statut == "ok":
        couleur = VERT
    elif statut == "warning":
        couleur = ORANGE
    else:
        couleur = ROUGE
    cv2.rectangle(image, (x, y), (x + 5, y + hauteur), couleur, -1)
    cv2.putText(image, titre,
        (x + 12, y + 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45, GRIS, 1)
    cv2.putText(image, valeur,
        (x + 12, y + 45),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)

# ---- Nouvelle : Barre de score de fatigue ----
def dessiner_barre_fatigue(image, score, x, y, largeur=200, hauteur=20):
    cv2.rectangle(image, (x, y), (x + largeur, y + hauteur), BLEU_FONCE, -1)
    cv2.rectangle(image, (x, y), (x + largeur, y + hauteur), GRIS, 1)
    fill = int((score / 100) * largeur)
    if score < 30:
        couleur = VERT
    elif score < 60:
        couleur = ORANGE
    else:
        couleur = ROUGE
    if fill > 0:
        cv2.rectangle(image, (x, y), (x + fill, y + hauteur), couleur, -1)
    cv2.putText(image, f"FATIGUE: {score}%",
        (x + 5, y + 14),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, BLANC, 1)

# ---- Fonction bouton STOP ----
def clic_sur_stop(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        if x >= 640 and y >= 430:
            param[0] = True

# ---- Configuration MediaPipe ----
mp_face   = mp.solutions.face_mesh
detecteur = mp_face.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ---- Ouvrir la caméra ----
camera = cv2.VideoCapture(0)

# ---- Variables de suivi ----
temps_yeux          = None
temps_bouche        = None
temps_tete          = None
temps_regard        = None
alarme_active       = False
arreter             = [False]
dernier_sms         = 0
compteur_alertes    = 0
heure_debut         = time.time()

# ---- Nouvelles variables ----
compteur_clignements    = 0
temps_dernier_clin      = time.time()
clignements_par_min     = 0
oeil_ouvert_precedent   = True
score_fatigue           = 0
historique_ear          = []   # Pour le graphique EAR
HISTORIQUE_MAX          = 100

cv2.namedWindow("DriverGuard - Detection Fatigue")
cv2.setMouseCallback("DriverGuard - Detection Fatigue", clic_sur_stop, arreter)

while True:

    if arreter[0]:
        break

    ok, image = camera.read()
    if not ok:
        break

    hauteur_img, largeur_img = image.shape[:2]
    panneau = 220
    cadre = cv2.copyMakeBorder(image, 0, 0, 0, panneau, cv2.BORDER_CONSTANT, value=NOIR)
    x_panneau = largeur_img + 10

    # ---- Logo et titre ----
    cv2.rectangle(cadre, (largeur_img, 0), (largeur_img + panneau, 60), (30, 30, 30), -1)
    cv2.putText(cadre, "DRIVE",
        (x_panneau, 30), cv2.FONT_HERSHEY_DUPLEX, 0.9, VERT, 2)
    cv2.putText(cadre, "Guard",
        (x_panneau + 65, 30), cv2.FONT_HERSHEY_DUPLEX, 0.9, BLANC, 2)
    cv2.putText(cadre, "Systeme anti-somnolence",
        (x_panneau, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.35, GRIS, 1)
    cv2.line(cadre, (largeur_img, 62), (largeur_img + panneau, 62), GRIS, 1)

    # ---- Statuts par défaut ----
    statut_yeux   = "ok"
    statut_bouche = "ok"
    statut_tete   = "ok"
    valeur_yeux   = "Ouverts"
    valeur_bouche = "Fermee"
    valeur_tete   = "Droite"
    ear_moyen     = 0.30
    mar           = 0.0
    angle         = 0.0
    inclinaison   = 0.0

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resultats = detecteur.process(image_rgb)

    if resultats.multi_face_landmarks:
        for visage in resultats.multi_face_landmarks:
            points = visage.landmark

            ear_gauche = calculer_ear(points, OEIL_GAUCHE)
            ear_droit  = calculer_ear(points, OEIL_DROIT)
            ear_moyen  = (ear_gauche + ear_droit) / 2.0
            mar        = calculer_mar(points, BOUCHE)
            angle      = calculer_angle_tete(points)
            inclinaison = calculer_inclinaison_verticale(points)

            # ---- Historique EAR pour mini-graphique ----
            historique_ear.append(ear_moyen)
            if len(historique_ear) > HISTORIQUE_MAX:
                historique_ear.pop(0)

            # ---- Comptage des clignements ----
            oeil_ouvert = ear_moyen >= SEUIL_EAR
            if not oeil_ouvert and oeil_ouvert_precedent:
                compteur_clignements += 1
            oeil_ouvert_precedent = oeil_ouvert

            # Recalculer clignements/min toutes les 10s
            elapsed = time.time() - temps_dernier_clin
            if elapsed >= 10:
                clignements_par_min = int(compteur_clignements * (60 / elapsed))
                compteur_clignements = 0
                temps_dernier_clin = time.time()

            # ---- Score de fatigue ----
            score_fatigue = calculer_score_fatigue(
                ear_moyen, mar, angle, clignements_par_min, inclinaison)

            # ---- Détection fatigue (yeux) ----
            if ear_moyen < SEUIL_EAR:
                if temps_yeux is None:
                    temps_yeux = time.time()
                duree_yeux = time.time() - temps_yeux
                statut_yeux = "warning" if duree_yeux < SEUIL_TEMPS_YEUX else "danger"
                valeur_yeux = f"Fermes {duree_yeux:.1f}s"
                if duree_yeux >= SEUIL_TEMPS_YEUX:
                    compteur_alertes += 1
                    log_alerte("YEUX_FERMES", ear_moyen, mar, angle, duree_yeux)
                    if not alarme_active:
                        pygame.mixer.music.play(-1)
                        alarme_active = True
                    if time.time() - dernier_sms > DELAI_SMS:
                        envoyer_sms("ALERTE DriverGuard : Conducteur fatigué ! Yeux fermés depuis 2 secondes.")
                        dernier_sms = time.time()
            else:
                temps_yeux = None
                if alarme_active and mar <= SEUIL_MAR and abs(angle) <= SEUIL_ANGLE:
                    pygame.mixer.music.stop()
                    alarme_active = False

            # ---- Détection bâillement ----
            if mar > SEUIL_MAR:
                if temps_bouche is None:
                    temps_bouche = time.time()
                duree_bouche = time.time() - temps_bouche
                statut_bouche = "warning" if duree_bouche < SEUIL_TEMPS_BOUCHE else "danger"
                valeur_bouche = f"Ouverte {duree_bouche:.1f}s"
                if duree_bouche >= SEUIL_TEMPS_BOUCHE:
                    compteur_alertes += 1
                    log_alerte("BAILLEMENT", ear_moyen, mar, angle, duree_bouche)
                    if not alarme_active:
                        pygame.mixer.music.play(-1)
                        alarme_active = True
                    if time.time() - dernier_sms > DELAI_SMS:
                        envoyer_sms("ALERTE DriverGuard : Conducteur bâille ! Signes de fatigue détectés.")
                        dernier_sms = time.time()
            else:
                temps_bouche = None
                if alarme_active and ear_moyen >= SEUIL_EAR and abs(angle) <= SEUIL_ANGLE:
                    pygame.mixer.music.stop()
                    alarme_active = False

            # ---- Détection tête penchée ----
            if abs(angle) > SEUIL_ANGLE:
                if temps_tete is None:
                    temps_tete = time.time()
                duree_tete = time.time() - temps_tete
                cote = "Gauche" if angle > 0 else "Droite"
                statut_tete = "warning" if duree_tete < SEUIL_TEMPS_TETE else "danger"
                valeur_tete = f"Penchee {cote}"
                if duree_tete >= SEUIL_TEMPS_TETE:
                    compteur_alertes += 1
                    log_alerte("TETE_PENCHEE", ear_moyen, mar, angle, duree_tete)
                    if not alarme_active:
                        pygame.mixer.music.play(-1)
                        alarme_active = True
                    if time.time() - dernier_sms > DELAI_SMS:
                        envoyer_sms("ALERTE DriverGuard : Tête du conducteur penche ! Risque de somnolence.")
                        dernier_sms = time.time()
            else:
                temps_tete = None
                if alarme_active and ear_moyen >= SEUIL_EAR and mar <= SEUIL_MAR:
                    pygame.mixer.music.stop()
                    alarme_active = False

            # ---- Nouvelle : Détection tête inclinée vers l'avant ----
            if inclinaison > 0.08:
                if temps_regard is None:
                    temps_regard = time.time()
                duree_regard = time.time() - temps_regard
                if duree_regard >= SEUIL_TEMPS_REGARD:
                    compteur_alertes += 1
                    log_alerte("TETE_AVANT", ear_moyen, mar, angle, duree_regard)
                    if not alarme_active:
                        pygame.mixer.music.play(-1)
                        alarme_active = True
                    if time.time() - dernier_sms > DELAI_SMS:
                        envoyer_sms("ALERTE DriverGuard : Tête du conducteur inclinée vers l'avant !")
                        dernier_sms = time.time()
            else:
                temps_regard = None

            # ---- EAR et MAR sur la vidéo ----
            couleur_ear = ROUGE if ear_moyen < SEUIL_EAR else VERT
            couleur_mar = ROUGE if mar > SEUIL_MAR else VERT
            label_ear   = "FERMES !" if ear_moyen < SEUIL_EAR else "Ouverts"
            label_mar   = "BAILLEMENT !" if mar > SEUIL_MAR else "Normal"

            # Fond EAR
            cv2.rectangle(cadre, (5, hauteur_img - 175), (320, hauteur_img - 150), (20, 20, 20), -1)
            # Texte EAR
            cv2.putText(cadre, f"EAR: {ear_moyen:.2f}  ->  {label_ear}",
                (10, hauteur_img - 155),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur_ear, 2)

            # Fond MAR
            cv2.rectangle(cadre, (5, hauteur_img - 148), (320, hauteur_img - 123), (20, 20, 20), -1)
            # Texte MAR
            cv2.putText(cadre, f"MAR: {mar:.2f}  ->  {label_mar}",
                (10, hauteur_img - 128),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur_mar, 2)

            # Clignements
            cv2.putText(cadre, f"Clin/min: {clignements_par_min}",
                (10, hauteur_img - 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, GRIS, 1)

            # ---- Mini graphique EAR ----
            if len(historique_ear) > 1:
                graph_x = 10
                graph_y = hauteur_img - 80
                graph_l = 200
                graph_h = 40
                cv2.rectangle(cadre, (graph_x, graph_y), (graph_x + graph_l, graph_y + graph_h), (20, 20, 20), -1)
                cv2.rectangle(cadre, (graph_x, graph_y), (graph_x + graph_l, graph_y + graph_h), GRIS, 1)
                # Ligne seuil EAR
                seuil_y = graph_y + int(graph_h * (1 - SEUIL_EAR / 0.5))
                cv2.line(cadre, (graph_x, seuil_y), (graph_x + graph_l, seuil_y), ROUGE, 1)
                # Courbe EAR
                step = graph_l / HISTORIQUE_MAX
                for i in range(1, len(historique_ear)):
                    x1 = graph_x + int((i - 1) * step)
                    x2 = graph_x + int(i * step)
                    y1 = graph_y + graph_h - int(historique_ear[i-1] / 0.5 * graph_h)
                    y2 = graph_y + graph_h - int(historique_ear[i] / 0.5 * graph_h)
                    y1 = max(graph_y, min(graph_y + graph_h, y1))
                    y2 = max(graph_y, min(graph_y + graph_h, y2))
                    cv2.line(cadre, (x1, y1), (x2, y2), CYAN, 1)
                cv2.putText(cadre, "EAR", (graph_x + 2, graph_y + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, GRIS, 1)

    else:
        statut_yeux   = "danger"
        valeur_yeux   = "Non detecte"
        statut_bouche = "danger"
        valeur_bouche = "Non detecte"
        statut_tete   = "danger"
        valeur_tete   = "Non detecte"

    # ---- Panneaux d'information ----
    dessiner_panneau(cadre, "YEUX", valeur_yeux, statut_yeux, x_panneau, 75)
    dessiner_panneau(cadre, "BOUCHE", valeur_bouche, statut_bouche, x_panneau, 150)
    dessiner_panneau(cadre, "TETE", valeur_tete, statut_tete, x_panneau, 225)
   

    # ---- Durée de session ----
    duree_session = int(time.time() - heure_debut)
    minutes = duree_session // 60
    secondes = duree_session % 60
    dessiner_panneau(cadre, "DUREE SESSION",
        f"{minutes:02d}:{secondes:02d}", "ok", x_panneau, 375)

    # ---- Barre score fatigue ----
    dessiner_barre_fatigue(cadre, score_fatigue, x_panneau, hauteur_img - 155)

    # ---- Statut alarme ----
    if alarme_active:
        cv2.rectangle(cadre, (largeur_img, hauteur_img - 100),
            (largeur_img + panneau, hauteur_img - 60), ROUGE, -1)
        cv2.putText(cadre, "ALARME ACTIVE !",
            (x_panneau, hauteur_img - 72),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, BLANC, 2)
    else:
        cv2.rectangle(cadre, (largeur_img, hauteur_img - 100),
            (largeur_img + panneau, hauteur_img - 60), (0, 80, 0), -1)
        cv2.putText(cadre, "Systeme actif",
            (x_panneau, hauteur_img - 72),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, VERT, 2)

    # ---- Bouton STOP ----
    cv2.rectangle(cadre, (largeur_img, hauteur_img - 50),
        (largeur_img + panneau, hauteur_img), ROUGE, -1)
    cv2.putText(cadre, "STOP  ",
        (x_panneau + 30, hauteur_img - 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, BLANC, 2)

    cv2.imshow("DriverGuard - Detection Fatigue", cadre)

    if cv2.waitKey(1) == ord('q'):
        break

# ---- Rapport de fin de session ----
duree_totale = int(time.time() - heure_debut)
print(f"\n{'='*40}")
print(f"  SESSION TERMINÉE — DriverGuard")
print(f"{'='*40}")
print(f"  Durée        : {duree_totale // 60}m {duree_totale % 60}s")
print(f"  Alertes      : {compteur_alertes}")
print(f"  Log sauvegardé : {LOG_FILE}")
print(f"{'='*40}\n")

camera.release()
cv2.destroyAllWindows()
pygame.mixer.quit()
print("Programme arrêté proprement ✅")