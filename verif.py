import mediapipe as mp
try:
    test = mp.solutions.face_mesh
    print("✅ SUCCÈS : MediaPipe est bien installé et configuré !")
except Exception as e:
    print(f"❌ ERREUR : {e}")