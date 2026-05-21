# Installation du projet PyVision / Eryma

## 1. Présentation

PyVision est une application web de vidéosurveillance développée en Python avec Flask.  
Elle permet de visualiser un flux caméra, consulter les événements, accéder aux enregistrements vidéo et envoyer des alertes par mail lors d'une détection.

## 2. Prérequis

Le projet nécessite :

- un serveur Linux Debian ou Ubuntu,
- Python 3,
- MariaDB,
- Nginx,
- Git,
- une caméra IP compatible RTSP,
- un accès SMTP pour l'envoi des mails.

## 3. Installation rapide

Cloner le projet :

```bash
git clone https://github.com/Awekano/PyVision.git
cd PyVision
