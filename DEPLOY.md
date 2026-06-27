# Publicacao em web hosting

Este projeto pode rodar localmente pelo `iniciar_simulador.bat` ou em hospedagem Python via WSGI.

## Entrada da aplicacao

Use:

```text
app:application
```

Em plataformas que usam `Procfile`, o comando ja esta configurado:

```text
web: gunicorn app:application --bind 0.0.0.0:$PORT
```

## Variaveis de ambiente

Configure no painel da hospedagem:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASS=sua_senha_de_app
SMTP_FROM=seu_email@gmail.com
SMTP_TLS=true
```

Nao envie o arquivo `smtp_config.json` para a hospedagem. Em servidor publicado, use variaveis de ambiente.

## Arquivos principais

- `app.py`: servidor local e aplicacao WSGI para hosting.
- `simulador.html`: interface e calculos.
- `requirements.txt`: dependencia de execucao em hosting.
- `Procfile`: comando de inicializacao para plataformas como Render, Railway, Heroku e similares.

## Uso local

Para uso no computador, continue executando:

```text
iniciar_simulador.bat
```
