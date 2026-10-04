# 🚗 DriverGuard — Système de Détection de Fatigue au Volant

> Surveillance en temps réel du conducteur par vision par ordinateur et IA.

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 👁️ Yeux fermés (EAR) | Alerte si les yeux sont fermés plus de 2 secondes |
| 😮 Bâillement (MAR) | Alerte si la bouche reste ouverte plus d'1 seconde |
| 🙆 Tête penchée | Alerte si la tête penche latéralement (> 20°) |
| ⬇️ Tête vers l'avant | Détecte l'assoupissement progressif |
| 📊 Score de fatigue | Score 0–100% en temps réel |
| 📈 Graphique EAR | Mini-graphique en direct (historique EAR) |
| 👀 Compteur clignements | Clignements par minute (alerte si anormal) |
| 🔔 Alarme sonore | Déclenchement automatique (`alarme.mp3`) |
| 📧 Notification Email | Alerte automatique par Gmail (anti-spam 60s) |
| 📋 Log CSV | Chaque alerte est enregistrée avec horodatage |
| 🖥️ Interface graphique | Panneau latéral avec tous les indicateurs |

---

## 📁 Structure du projet

```
DriverGuard/
├── detection.py        # Script principal
├── alarme.mp3          # Son d'alarme
├── config.py           # ⚠️ Clés Gmail (ne pas partager !)
├── requirements.txt    # Dépendances Python
├── .gitignore
├── README.md
└── logs/               # Généré automatiquement
    └── session_YYYYMMDD_HHMMSS.csv
```

---

## 🚀 Installation

### 1. Prérequis
- Python 3.11
- Webcam

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

Ou manuellement :

```bash
pip install opencv-python mediapipe pygame
```

### 3. Configurer Gmail

1. Activez la **Vérification en 2 étapes** sur votre compte Google
2. Créez un mot de passe d'application ici :
   ```
   https://myaccount.google.com/apppasswords
   ```
3. Créez `config.py` avec vos informations :

```python
GMAIL_EXPEDITEUR   = "votre.email@gmail.com"
GMAIL_MOT_PASSE    = "abcdefghijklmnop"   # 16 caractères, sans espaces
GMAIL_DESTINATAIRE = "votre.email@gmail.com"
```

### 4. Lancer

```bash
py -3.11 detection.py
```

---

## 🎮 Contrôles

| Action | Commande |
|---|---|
| Quitter | `Q` au clavier |
| Quitter | Clic sur bouton **STOP** |

---

## 📊 Fichiers de log

À chaque session, un fichier CSV est créé dans `logs/` :

```
logs/session_20250620_143022.csv
```

Colonnes : `Horodatage`, `Type_Alerte`, `EAR`, `MAR`, `Angle`, `Duree_s`

---

## ⚙️ Paramètres ajustables (`detection.py`)

```python
SEUIL_EAR          = 0.25   # Sensibilité détection yeux
SEUIL_MAR          = 0.5    # Sensibilité bâillement
SEUIL_ANGLE        = 20     # Degrés max avant alerte tête
SEUIL_TEMPS_YEUX   = 2.0    # Secondes yeux fermés avant alarme
SEUIL_TEMPS_BOUCHE = 1.0    # Secondes bouche ouverte avant alarme
SEUIL_TEMPS_TETE   = 2.0    # Secondes tête penchée avant alarme
SEUIL_TEMPS_REGARD = 2.5    # Secondes tête vers l'avant avant alarme
SEUIL_CLIGNEMENTS  = 25     # Clignements/min max (au-delà = fatigue)
DELAI_EMAIL        = 60     # Anti-spam email (secondes)
```

---

## 🛠️ Technologies

- **Python 3.11**
- **OpenCV** — capture vidéo et interface graphique
- **MediaPipe** — détection des 468 points du visage
- **Pygame** — lecture de l'alarme sonore
- **smtplib** — notifications par email Gmail (intégré Python)
- **CSV** — journalisation des alertes

---

## 🔒 Sécurité

- `config.py` est dans `.gitignore` — vos identifiants ne seront **jamais** poussés sur GitHub
- Les logs sont également exclus du dépôt

---

## 📝 Licence


venv\Scripts\activate 
