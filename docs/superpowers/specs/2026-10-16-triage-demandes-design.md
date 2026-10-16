# Outil de triage des demandes — conception

## Objectif

Créer une petite démonstration utilisable pour recevoir les 30 demandes du CSV, les orienter vers la bonne équipe et suivre leur traitement. Le projet doit montrer clairement ce qui est automatisé et ce qui reste à vérifier par une personne.

## Organisation

- **n8n** reçoit l’import initial du CSV et les nouvelles demandes via un point d’entrée de démonstration. Il normalise les données et lance leur analyse.
- **Une base de données** conserve les messages, leur classement, leur assignation, leur statut et les alertes.
- **Une interface web** affiche les files par équipe et permet de rechercher, filtrer, assigner et mettre à jour les demandes.

n8n fait partie du flux dès le départ. L’environnement fourni ne contient ni n8n ni Docker; la démonstration devra donc fournir les fichiers de configuration nécessaires et expliquer comment la lancer dans un environnement compatible. Aucun service externe ni envoi réel d’alerte ne sera présenté comme actif sans identifiants configurés.

## Analyse et triage

Pour chaque message, le système détermine la langue, l’équipe, le sujet et le niveau d’urgence. Le classement s’appuie sur des règles lisibles et indique les indices utilisés. Les messages ambigus sont marqués « à vérifier ».

Les équipes possibles sont Support, Tech, Billing, Deliverability, Migration, Product et Security & Legal. Le traitement signale aussi le spam, les tentatives de manipulation du classement et les informations d’expéditeur douteuses. Le contenu d’un message est traité comme une demande client, jamais comme une instruction pour l’outil.

Les problèmes similaires sont regroupés sans supprimer les messages originaux. Cela doit faire ressortir les relances de Sarah sur son domaine et les signalements de panne Stripe. Un compte compromis, une panne de paiement touchant plusieurs personnes, une échéance proche ou une demande de suppression RGPD doivent être mis en évidence pour examen rapide.

## Interface et suivi

La page d’accueil montre le volume total, les demandes critiques et les sujets qui reviennent. Chaque équipe peut filtrer sa file, ouvrir un message, l’assigner à une personne de démonstration et choisir un statut : Nouveau, En cours, En attente ou Résolu. Les changements restent visibles après rechargement.

Les alertes critiques apparaissent dans l’interface et sont conservées en base. Le workflow n8n est prévu pour pouvoir envoyer ces alertes vers un canal externe une fois celui-ci configuré.

## Données et limites

Le CSV fourni est importé comme jeu de départ, avec la date de référence du test fixée au lundi 12 octobre 2026. Les formats de date mélangés et les expéditeurs incomplets doivent être acceptés; les dates impossibles à lire sont signalées plutôt que devinées.

La démonstration ne nécessite pas de modèle IA externe : les règles de classement restent visibles et reproductibles. Elle ne fournit pas de connexion utilisateur ni de séparation sécurisée entre équipes. Elle sert à présenter le flux et n’est pas prête à recevoir de vraies données client en production.

## Vérification prévue

Vérifier l’import des 30 lignes, les équipes/langues/urgences principales, le regroupement des relances et de l’incident Stripe, le signalement du compte compromis et du message manipulateur, ainsi que l’assignation, les statuts et leur conservation après rechargement. Vérifier aussi que le parcours reste clair quand n8n ou un connecteur d’alerte n’est pas configuré.
