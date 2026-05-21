# PyVision

PyVision est une application web de vidéosurveillance développée dans le cadre du projet BTS CIEL IR.

Le projet permet de superviser une caméra IP depuis une interface web sécurisée.  
L’utilisateur peut visualiser le flux vidéo en direct, consulter les événements détectés, accéder aux enregistrements vidéo et recevoir une alerte par mail lorsqu’un événement est détecté.

---

## Objectif du projet

L’objectif de PyVision est de mettre en place une solution de vidéosurveillance simple, sécurisée et accessible depuis un navigateur web.

Le système repose sur un serveur Linux qui héberge l’application web, la base de données et les services nécessaires au fonctionnement du projet.

Le projet répond aux besoins suivants :

- Visualiser le flux vidéo d’une caméra IP
- Détecter un mouvement ou une présence
- Enregistrer automatiquement une vidéo après détection
- Consulter les événements depuis une interface web
- Télécharger les enregistrements vidéo
- Envoyer une alerte par mail
- Journaliser les actions et connexions des utilisateurs

---

## Fonctionnalités

### Utilisateur

- Connexion sécurisée avec identifiant et mot de passe
- Accès à la page d’accueil
- Visualisation du flux caméra en direct
- Consultation des événements
- Filtrage des événements
- Consultation des enregistrements vidéo
- Téléchargement des vidéos enregistrées

### Administrateur

- Accès aux fonctions utilisateur
- Consultation du journal de bord
- Suivi des connexions au site
- Gestion des utilisateurs
- Supervision du système
- Accès à la base de données

### Système

- Détection de mouvement
- Création automatique d’événements
- Enregistrement vidéo après détection
- Envoi d’une alerte par mail
- Stockage des événements dans la base de données
- Conservation des vidéos sur le serveur

---

## Technologies utilisées

Le projet utilise les technologies suivantes :

- Linux Debian / Ubuntu
- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- MariaDB / MySQL
- Nginx
- Gunicorn
- OpenCV
- HTML
- CSS
- JavaScript
- SMTP pour l’envoi des mails
- Git / GitHub

---

## Prérequis

Avant d’installer et d’utiliser PyVision, il est nécessaire de disposer d’un environnement adapté.

### Matériel nécessaire

- Un serveur ou une machine virtuelle sous Linux
- Une caméra IP compatible RTSP ou HTTP
- Un poste client avec un navigateur web
- Un accès réseau entre la caméra et le serveur
- Une connexion Internet pour l’installation des dépendances

### Système recommandé

- Debian 12 ou Ubuntu Server
- 2 Go de RAM minimum
- 20 Go d’espace disque minimum
- Accès administrateur avec `sudo`

### Logiciels nécessaires

Le projet nécessite les éléments suivants :

- Git
- Python 3
- Python venv
- Python pip
- Nginx
- MariaDB ou MySQL
- Gunicorn
- FFmpeg
- Les dépendances Python présentes dans `requirements.txt`

### Informations à préparer

Avant de lancer l’installation, il faut préparer :

- L’adresse IP du serveur
- L’adresse RTSP de la caméra IP
- Les identifiants de connexion à la caméra
- Les identifiants SMTP pour l’envoi des mails
- L’adresse mail qui recevra les alertes
- Le nom de domaine si le site est publié en ligne

### Exemple d’adresse RTSP

```env
CAMERA_RTSP_URL=rtsp://utilisateur:motdepasse@192.168.1.50:554/stream1
