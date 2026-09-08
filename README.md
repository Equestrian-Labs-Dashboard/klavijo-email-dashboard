# Klaviyo Email Marketing Dashboard

Dashboard estático (HTML/CSS/JS) del desempeño de email marketing de
**Klaviyo**, con el mismo layout/estructura visual que la sección
"EMAIL MARKETING" de la hoja **CORRO** (Corro Cavali 2026).

Vive en GitHub Pages. Los datos se actualizan automáticamente mediante un
workflow de GitHub Actions que lee la hoja de Google Sheets y reescribe
`data/data.json` — el sitio nunca llama a Google Sheets directamente desde el
navegador (por eso las credenciales están seguras aunque el repo sea público).

## Estructura

```
.
├── index.html                      # Dashboard
├── assets/css/style.css
├── assets/js/main.js               # Lee data/data.json y dibuja todo
├── data/data.json                  # Datos (semilla real, luego auto-actualizado)
├── scripts/
│   ├── fetch_sheet_data.py         # Se ejecuta en GitHub Actions, no localmente con tus credenciales reales
│   └── requirements.txt
├── .github/workflows/
│   ├── update-data.yml             # Cron diario: jala datos de Sheets -> data.json
│   └── deploy-pages.yml            # Publica el sitio en GitHub Pages en cada push
└── DESIGN_NOTES.md
```

## 🔐 Seguridad — dónde poner las credenciales (MUY IMPORTANTE)

El repo va a ser **público**, así que las credenciales de Google **jamás**
deben ir en el código ni en `data.json`. Van en **GitHub Secrets**, que están
cifrados y solo el workflow de Actions puede leerlos — nadie que vea el repo
en la web los puede ver.

**Dónde ponerlos:**

1. Entra al repo en GitHub → **Settings** → **Secrets and variables** →
   **Actions** → pestaña **Secrets** → **New repository secret**.
2. Crea estos dos secrets:

   | Name | Value |
   |---|---|
   | `SHEET_ID` | El ID del spreadsheet — la parte de la URL entre `/d/` y `/edit` (ej: `1RyJBTOBtwBMYfFM0kCfyei16ioQWq_IJ5ki8_HWzo8E`) |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | El contenido completo del archivo JSON de una **cuenta de servicio de Google Cloud** con acceso de solo lectura ("Viewer") a esa hoja |

3. (Opcional) En la pestaña **Variables** (no secret, es solo config) puedes
   agregar `SHEET_TAB` si la pestaña de Klaviyo no se llama `CORRO`.

**Cómo generar la cuenta de servicio** (una sola vez):
1. Google Cloud Console → crear proyecto (o usar uno existente) → habilitar
   **Google Sheets API**.
2. IAM & Admin → Service Accounts → **Create service account**.
3. Generar una **key** en formato JSON y descargarla.
4. Abrir la hoja de Google Sheets → **Compartir** → pegar el email de la
   cuenta de servicio (termina en `...iam.gserviceaccount.com`) con permiso
   **Lector**.
5. Copiar el contenido completo del JSON descargado y pegarlo como valor del
   secret `GOOGLE_SERVICE_ACCOUNT_JSON` (paso 2 arriba). Después, **borra el
   archivo JSON de tu computadora** o guárdalo en un lugar privado — no lo
   subas al repo.

El workflow `update-data.yml` corre todos los días a las 9:00 UTC (ajustable
en el cron) y también se puede disparar manualmente desde la pestaña
**Actions** → **Update Klaviyo data** → **Run workflow**.

## Publicar en GitHub Pages

1. Sube este proyecto a un repo nuevo en GitHub (ver comandos abajo).
2. En el repo → **Settings** → **Pages** → **Build and deployment** → Source:
   **GitHub Actions** (el workflow `deploy-pages.yml` ya está incluido).
3. Cada push a `main` publica el sitio automáticamente.

```bash
cd klavijo-email-dashboard
git init
git add .
git commit -m "Initial commit: Klaviyo Email Marketing Dashboard"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/<nombre-del-repo>.git
git push -u origin main
```

## Datos actuales

`data/data.json` viene con datos semilla reales (ene–ago 2026) tomados
manualmente de la hoja CORRO, sección Klaviyo, para que el dashboard se vea
funcionando desde el día uno. En cuanto configures los dos secrets, el primer
run del workflow los reemplaza con datos en vivo.

## Pendiente / a confirmar contigo

- Confirmar si la fuente real de **Klaviyo** vive en la misma hoja CORRO o en
  otro spreadsheet (el mapa de filas en `scripts/fetch_sheet_data.py` está
  armado sobre las filas 43–68 de la hoja que revisamos).
- La hoja no trae un conteo directo de "# de campañas enviadas por mes" — por
  ahora la tarjeta usa "destinatarios del último envío" como proxy. Si hay una
  fuente con el conteo real, se puede reemplazar fácilmente.
