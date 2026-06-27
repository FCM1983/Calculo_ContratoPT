param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectId,

  [string]$Region = "europe-west1",
  [string]$Service = "simulador-salarial"
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Comando '$Name' nao encontrado. Instale antes de executar este deploy."
  }
}

$gcloudCommand = Get-Command "gcloud.cmd" -ErrorAction SilentlyContinue
$firebaseCommand = Get-Command "firebase.cmd" -ErrorAction SilentlyContinue
if (-not $gcloudCommand) { $gcloudCommand = Get-Command "gcloud" -ErrorAction SilentlyContinue }
if (-not $firebaseCommand) { $firebaseCommand = Get-Command "firebase" -ErrorAction SilentlyContinue }
if ($gcloudCommand) { $gcloud = $gcloudCommand.Source }
if ($firebaseCommand) { $firebase = $firebaseCommand.Source }
if (-not $gcloud) { throw "Comando 'gcloud' nao encontrado. Instale o Google Cloud CLI antes do deploy." }
if (-not $firebase) { throw "Comando 'firebase' nao encontrado. Instale o Firebase CLI antes do deploy." }

& $gcloud config set project $ProjectId
& $gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

$smtpHost = Read-Host "SMTP_HOST"
$smtpPort = Read-Host "SMTP_PORT [587]"
if ([string]::IsNullOrWhiteSpace($smtpPort)) { $smtpPort = "587" }
$smtpUser = Read-Host "SMTP_USER"
$smtpPass = Read-Host "SMTP_PASS" -AsSecureString
$smtpFrom = Read-Host "SMTP_FROM [$smtpUser]"
if ([string]::IsNullOrWhiteSpace($smtpFrom)) { $smtpFrom = $smtpUser }
$smtpPassPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($smtpPass))

& $gcloud run deploy $Service `
  --source . `
  --region $Region `
  --allow-unauthenticated `
  --set-env-vars "SMTP_HOST=$smtpHost,SMTP_PORT=$smtpPort,SMTP_USER=$smtpUser,SMTP_PASS=$smtpPassPlain,SMTP_FROM=$smtpFrom,SMTP_TLS=true,OPEN_BROWSER=0"

& $firebase use $ProjectId
& $firebase deploy --only hosting

Write-Host ""
Write-Host "Deploy concluido."
Write-Host "URL Firebase Hosting: https://$ProjectId.web.app/"
