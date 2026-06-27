# Simulador Salarial Portugal 2026

Aplicacao Python stand alone com interface web, baseada na planilha `Simulador_Salario_Liquido_Portugal_2026_FreelancerxContrato.xlsx`.

## Como executar

1. Instale Python 3.10 ou superior.
2. Na pasta do projeto, execute:

```powershell
python app.py
```

Ou use o atalho:

```powershell
.\iniciar_simulador.bat
```

O programa abre no navegador em `http://127.0.0.1:8080`.

## Se aparecer ERR_CONNECTION_REFUSED

Esse erro indica que o servidor nao esta rodando naquela porta.

Opcao mais simples:

1. Abra `simulador.html` diretamente no navegador.
2. Essa versao nao usa porta nem servidor local.

Opcao Python:

1. Execute `iniciar_simulador.bat`.
2. Abra `http://127.0.0.1:8080`.

Se a janela disser que Python nao foi encontrado, instale Python 3.10 ou superior em `https://www.python.org/downloads/` e marque a opcao `Add python.exe to PATH`.

## Funcionalidades

- Simulador de salario liquido para contrato.
- Calculo estimativo de IRS 2026 por escaloes legais e Seguranca Social.
- Deducao especifica Cat. A por IAS e deducao fixa por dependente.
- IRS Jovem parametrizado para 10 anos.
- Subsidio de alimentacao isento e tributavel.
- Comparador de cenarios de contrato.
- Comparador Freelancer vs Contrato com IVA, IRS Cat. B, retencao e Seguranca Social TI.
- Tela de parametros para ajustar taxas e deducoes.

O modelo e estimativo e nao substitui simulacao oficial da Autoridade Tributaria nem validacao com contabilista.

## Deploy Firebase

O projeto esta preparado para Firebase Hosting com backend Python no Cloud Run.

Consulte:

```text
FIREBASE_DEPLOY.md
```

Resumo:

```powershell
gcloud auth login
firebase login
.\deploy_firebase.ps1 -ProjectId "SEU_PROJECT_ID"
```
