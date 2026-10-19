# 🎬 Dashboard de Filmes — Streamlit + Firestore + PostgreSQL

- **Firestore**: colección `movies` (name, genre, director, company).
- **PostgreSQL**: base `guests`, tabla `people` (email, comment) como libro de visitas.

## Funcionalidades
- Checkbox para visualizar todos los filmes.
- Búsqueda por título (que contenga, sin distinguir mayúsculas/minúsculas).
- Filtro por director con total de filmes encontrados.
- Formulario para insertar un nuevo filme en Firestore.
- Libro de visitas: registrar y visualizar comentarios en PostgreSQL.

## Archivos
- `app.py`: código del dashboard.
- `requirements.txt`: librerías de Python.
- `packages.txt`: PostgreSQL para el servidor.

Las credenciales se configuran en *Secrets* de Streamlit Cloud (no están en el repositorio).
