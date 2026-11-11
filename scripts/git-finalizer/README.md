# Git Finalizer pour Windows

Ce lanceur utilise PowerShell 5.1 et Git deja installes. Il peut etre copie dans un autre depot; passe alors -RepoPath et -PlanPath.

## Utilisation dans Prospect

Double-clique sur scripts\Finaliser Git.bat, ou lance depuis PowerShell :

    .\scripts\Finalize-Git.ps1 -Action Preview
    .\scripts\Finalize-Git.ps1 -Action Commit
    .\scripts\Finalize-Git.ps1 -Action Push

Le manifeste par defaut est .git-finalizer-plan.json a la racine du depot. Pour preparer un autre lot, remplace son message et la liste exacte de chemins par des chemins relatifs litteraux; les jokers ne sont pas acceptes. Le manifeste est inclus dans le lot de Prospect. Les changements locaux sans rapport peuvent rester presents pendant le push; un fichier du manifeste modifie apres le commit bloque la publication. Pour un manifeste externe au depot, passe son chemin avec -PlanPath.

    {
      "commitMessage": "Fixer le calcul de remise",
      "validation": "Tests unitaires et build reussis; verifier le diff affiche avant commit.",
      "files": [
        "src/calcul-remise.ts",
        "src/calcul-remise.test.ts"
      ]
    }

## Controles

- L'apercu liste l'etat complet du depot, puis montre seulement le diff du manifeste. Tout fichier hors lot reste non touche.
- Le commit refuse un index deja stage et ne prepare que les chemins du manifeste. Il demande STAGE, affiche le diff stage, puis exige COMMIT.
- Les fichiers .env reels, cles, bases, sauvegardes, fichiers binaires, contacts evidents, secrets detectes, numeros de telephone explicites et emails non fictifs bloquent le lot. Aucun remplacement n'est ajoute au manifeste.
- Le push refuse un index deja stage, un fichier du manifeste modifie depuis le commit ou plus d'un commit sortant. Les autres changements locaux sont affiches et restent exclus. Il montre la destination sans identifiants, exige FETCH pour rafraichir l'amont, inspecte le seul commit, puis exige PUSH. Aucun force-push n'est utilise.
- Les erreurs Git sont affichees et journalisees dans %LOCALAPPDATA%\CodexGitFinalizer\operations.log; les secrets reconnus et les identifiants d'URL sont masques dans ce journal.

Les controles de contenu ne garantissent pas la detection de tous les secrets ou donnees privees. La liste exacte des chemins, l'apercu complet et les deux confirmations restent obligatoires.
