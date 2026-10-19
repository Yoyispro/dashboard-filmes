"""
Dashboard de Filmes - Streamlit + Firestore + PostgreSQL.

- Firestore: colección 'movies' (name, genre, director, company).
- PostgreSQL: base 'guests', tabla 'people' (email, comment) = libro de visitas.

Credenciales en st.secrets (Streamlit Cloud > Settings > Secrets):
  [firebase]  -> llave de cuenta de servicio de Firebase.
  [postgres]  -> (opcional) uri de un PostgreSQL en la nube, p. ej. Aiven.
Si no hay [postgres], se levanta un PostgreSQL local dentro del servidor.
"""
import glob
import os
import subprocess

import pandas as pd
import psycopg2
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Dashboard de Filmes", page_icon="🎬", layout="wide")


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
@st.cache_resource
def obtener_uri_postgres():
    """Devuelve la URI de PostgreSQL (secrets) o arranca uno local con la base 'guests'."""
    if "postgres" in st.secrets:
        return st.secrets["postgres"]["uri"]

    bins = sorted(glob.glob("/usr/lib/postgresql/*/bin"))
    if not bins:
        raise RuntimeError("PostgreSQL no está instalado en el servidor (revisa packages.txt).")
    pg = bins[-1]
    datos = "/tmp/pgdata"

    if not os.path.exists(os.path.join(datos, "PG_VERSION")):
        subprocess.run([f"{pg}/initdb", "-D", datos, "-U", "postgres", "--auth=trust"],
                       check=True, capture_output=True)
    if subprocess.run([f"{pg}/pg_ctl", "-D", datos, "status"], capture_output=True).returncode != 0:
        subprocess.run([f"{pg}/pg_ctl", "-D", datos, "-w", "-l", "/tmp/postgres.log",
                        "-o", "-k /tmp -c listen_addresses=localhost -p 5432", "start"],
                       check=True, capture_output=True)
    subprocess.run([f"{pg}/createdb", "-h", "localhost", "-U", "postgres", "guests"],
                   capture_output=True)  # si ya existe, no pasa nada
    return "postgresql://postgres@localhost:5432/guests"


def ejecutar_query_postgres(query, params=None, fetch=False):
    """Ejecuta una consulta en PostgreSQL; si fetch=True devuelve los registros."""
    conn = None
    try:
        conn = psycopg2.connect(obtener_uri_postgres())
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            resultados = cursor.fetchall() if fetch else None
        conn.commit()
        return resultados
    except Exception as e:
        st.sidebar.error(f"Error en base de datos: {e}")
        return None
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Firestore
# ---------------------------------------------------------------------------
@st.cache_resource
def conectar_firestore():
    """Inicializa Firebase una sola vez con la llave guardada en secrets."""
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(dict(st.secrets["firebase"])))
    return firestore.client()


@st.cache_data(ttl=60)
def cargar_datos_firestore():
    """Lee todos los documentos de la colección 'movies' en un DataFrame."""
    docs = conectar_firestore().collection("movies").stream()
    return pd.DataFrame([doc.to_dict() for doc in docs])


def buscar_por_titulo(df, texto):
    """Filmes cuyo título CONTIENE el texto, sin distinguir mayúsculas/minúsculas."""
    return df[df["name"].str.contains(texto, case=False, na=False, regex=False)]


def filtrar_por_director(df, director):
    """Filmes realizados por el director indicado."""
    return df[df["director"] == director]


# Tabla del libro de visitas (se crea si no existe)
ejecutar_query_postgres("""
    CREATE TABLE IF NOT EXISTS people (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        comment TEXT NOT NULL
    )
""")

# ---------------------------------------------------------------------------
# Dataset base: se carga al arrancar la aplicación
# ---------------------------------------------------------------------------
st.title("🎬 Dashboard de Filmes - Data Science")

try:
    db = conectar_firestore()
    df_movies = cargar_datos_firestore()
except Exception as e:
    st.error(f"No se pudo conectar a Firestore: {e}")
    db, df_movies = None, pd.DataFrame()

st.sidebar.header("Opciones y Filtros")

# 1. Todos los filmes --------------------------------------------------------
if st.sidebar.checkbox("Visualizar todos los filmes"):
    st.header("Catálogo Completo de Filmes")
    if not df_movies.empty:
        st.dataframe(df_movies, use_container_width=True)
    else:
        st.info("La colección está vacía.")

st.sidebar.markdown("---")

# 2. Búsqueda por título -----------------------------------------------------
st.sidebar.subheader("Buscar Filme por Título")
titulo_buscar = st.sidebar.text_input("Ingrese el título:")
if st.sidebar.button("Buscar Título"):
    if df_movies.empty:
        st.warning("No hay datos cargados para buscar.")
    elif not titulo_buscar:
        st.warning("Ingrese un título para buscar.")
    else:
        df_filtrado = buscar_por_titulo(df_movies, titulo_buscar)
        st.subheader(f"Resultados de búsqueda: '{titulo_buscar}'")
        st.info(f"Total de filmes encontrados: {len(df_filtrado)}")
        st.dataframe(df_filtrado, use_container_width=True)

st.sidebar.markdown("---")

# 3. Filtro por director -----------------------------------------------------
st.sidebar.subheader("Filtrar por Director")
if not df_movies.empty and "director" in df_movies.columns:
    directores = sorted(df_movies["director"].dropna().unique().tolist())
    director_sel = st.sidebar.selectbox("Seleccione un director:", directores)
    if st.sidebar.button("Filtrar por Director"):
        df_director = filtrar_por_director(df_movies, director_sel)
        st.subheader(f"Filmes dirigidos por {director_sel}")
        st.info(f"Total de filmes encontrados: {len(df_director)}")
        st.dataframe(df_director, use_container_width=True)

st.sidebar.markdown("---")

# 4. Nuevo filme en Firestore ------------------------------------------------
st.sidebar.subheader("Agregar Nuevo Filme")
with st.sidebar.form("form_nuevo_filme", clear_on_submit=True):
    nuevo_nombre = st.text_input("Nombre (name)")
    nuevo_genero = st.text_input("Género (genre)")
    nuevo_director = st.text_input("Director (director)")
    nueva_compania = st.text_input("Compañía (company)")
    btn_insertar = st.form_submit_button("Insertar Filme")

if btn_insertar:
    if db and nuevo_nombre and nuevo_genero and nuevo_director and nueva_compania:
        db.collection("movies").add({
            "name": nuevo_nombre,
            "genre": nuevo_genero,
            "director": nuevo_director,
            "company": nueva_compania,
        })
        cargar_datos_firestore.clear()
        st.sidebar.success("¡Filme insertado en Firestore!")
    else:
        st.sidebar.warning("Llena todos los campos del filme.")

st.sidebar.markdown("---")

# 5. Libro de visitas en PostgreSQL ------------------------------------------
st.sidebar.subheader("Libro de Visitas")
with st.sidebar.form("form_visitas", clear_on_submit=True):
    email_visitante = st.text_input("Email")
    comentario_visitante = st.text_area("Comentario")
    btn_visita = st.form_submit_button("Registrar Comentario")

if btn_visita:
    if email_visitante and comentario_visitante:
        ejecutar_query_postgres(
            "INSERT INTO people (email, comment) VALUES (%s, %s)",
            (email_visitante, comentario_visitante),
        )
        st.sidebar.success("Comentario registrado en PostgreSQL.")
    else:
        st.sidebar.warning("Escribe tu email y tu comentario.")

if st.sidebar.button("Visualizar Comentarios"):
    st.subheader("Comentarios de Visitantes")
    filas = ejecutar_query_postgres("SELECT email, comment FROM people ORDER BY id", fetch=True)
    if filas:
        st.dataframe(pd.DataFrame(filas, columns=["Email", "Comentario"]), use_container_width=True)
    else:
        st.info("No hay comentarios registrados aún.")
