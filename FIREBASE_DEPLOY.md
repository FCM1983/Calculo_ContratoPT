# Deploy no Firebase

Este projeto usa Firebase Hosting encaminhando as requisicoes para um servico Python no Cloud Run.

O Firebase recomenda esta combinacao quando o site precisa de backend dinamico: o Cloud Run executa a aplicacao em container e o Hosting encaminha as requisicoes HTTPS para o servico.

## Pre-requisitos

1. Projeto Firebase criado.
2. Plano Blaze ativo, pois Cloud Run exige faturacao associada ao projeto.
3. Firebase CLI instalado.
4. Google Cloud CLI instalado.
5. Login feito nas duas CLIs:

```powershell
gcloud auth login
firebase login
```

## Arquivos criados

- `Dockerfile`: container Python com Chromium para gerar PDF.
- `firebase.json`: rewrite do Firebase Hosting para Cloud Run.
- `public/index.html`: pasta publica exigida pelo Hosting.
- `deploy_firebase.ps1`: script de deploy.

## Deploy

Execute a partir da pasta do projeto:

```powershell
.\deploy_firebase.ps1 -ProjectId "SEU_PROJECT_ID"
```

Por padrao, o servico sera publicado como:

```text
simulador-salarial
```

na regiao:

```text
europe-west1
```

Ao executar, o script pedira os dados SMTP. A senha nao deve ser salva no codigo.

## URL final

Depois do deploy:

```text
https://SEU_PROJECT_ID.web.app/
```

ou:

```text
https://SEU_PROJECT_ID.firebaseapp.com/
```
