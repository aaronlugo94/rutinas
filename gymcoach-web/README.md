# GymCoach Web

PWA instalable. Híbrido con bot de Telegram.

## Deploy

### Backend (Railway — ya tienes)

Variables de entorno adicionales:
```
JWT_SECRET=una-cadena-aleatoria-larga-y-segura
API_PORT=8000
FRONTEND_URL=https://tu-app.vercel.app
```

El `main.py` ya arranca FastAPI en un thread separado.
No necesitas cambiar el Procfile.

### Frontend (Vercel)

1. Sube `gymcoach-web/` a un repositorio GitHub
2. Importa en vercel.com
3. Agrega variable de entorno:
   ```
   VITE_API_URL=https://tu-app.up.railway.app
   ```
4. Deploy automático

### Primer uso

El usuario necesita configurar su PIN en el bot:
```
/setpin 1234
```

Luego entra a la web con:
- Su Telegram ID (el bot se lo dice al hacer /setpin)
- Su PIN de 4 dígitos

## Estructura

```
gymcoach-web/
  src/
    pages/
      Login.jsx    — autenticación con user_id + PIN
      Hoy.jsx      — rutina del día, registro de pesos
      Progreso.jsx — historial por ejercicio con gráficas
      Plan.jsx     — las 4 semanas
      Stats.jsx    — racha, XP, badges, resumen semanal
    components/
      Layout.jsx   — navegación inferior
    lib/
      api.js       — cliente HTTP con JWT
      hooks.js     — custom hooks para data fetching
```
