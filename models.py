import psycopg2
import psycopg2.extras
import os
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # USUÁRIOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id       SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        fandom   TEXT,
        avatar   TEXT,
        bio      TEXT
    )
    """)

    # BIBLIOTECA
    c.execute("""
    CREATE TABLE IF NOT EXISTS library (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "collectionName" TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        "previewUrl"   TEXT,
        rating         INTEGER,
        note           TEXT,
        "addedAt"      TEXT,
        UNIQUE(user_id, "trackId")
    )
    """)

    # FAVORITOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        UNIQUE(user_id, "trackId")
    )
    """)

    # LISTAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS lists (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        name       TEXT NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, name)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS list_items (
        id             SERIAL PRIMARY KEY,
        list_id        INTEGER NOT NULL,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        "addedAt"      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(list_id, "trackId"),
        FOREIGN KEY(list_id) REFERENCES lists(id)
    )
    """)

    # HISTÓRICO DE OUVIDAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS listened (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        "listenedAt"   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # DIÁRIO
    c.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        "listenedAt"   TEXT
    )
    """)

    # REVIEWS
    c.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER,
        "trackId"  TEXT,
        username   TEXT,
        text       TEXT,
        "createdAt" TEXT
    )
    """)

    # FOLLOWS
    c.execute("""
    CREATE TABLE IF NOT EXISTS follows (
        id           SERIAL PRIMARY KEY,
        follower_id  INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        "createdAt"  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(follower_id, following_id),
        FOREIGN KEY(follower_id)  REFERENCES users(id),
        FOREIGN KEY(following_id) REFERENCES users(id)
    )
    """)

    # COLEÇÃO DE MÍDIAS FÍSICAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS collection (
        id             SERIAL PRIMARY KEY,
        user_id        INTEGER NOT NULL,
        "trackId"      TEXT,
        "trackName"    TEXT,
        "artistName"   TEXT,
        "artworkUrl100" TEXT,
        media_type     TEXT NOT NULL,
        photo          TEXT,
        is_public      INTEGER DEFAULT 1,
        "addedAt"      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # Colunas novas na tabela lists
    for col_sql in [
        'ALTER TABLE lists ADD COLUMN cover TEXT',
        'ALTER TABLE lists ADD COLUMN description TEXT',
        'ALTER TABLE lists ADD COLUMN is_public INTEGER DEFAULT 1',
    ]:
        try:
            c.execute(col_sql)
            conn.commit()
        except Exception:
            conn.rollback()

    # LIKES EM REVIEWS
    c.execute("""
    CREATE TABLE IF NOT EXISTS review_likes (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        review_id  INTEGER NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, review_id),
        FOREIGN KEY(user_id)   REFERENCES users(id),
        FOREIGN KEY(review_id) REFERENCES reviews(id)
    )
    """)

    # LIKES EM LISTAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS list_likes (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        list_id    INTEGER NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, list_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(list_id) REFERENCES lists(id)
    )
    """)

    # LISTAS SALVAS (bookmark)
    c.execute("""
    CREATE TABLE IF NOT EXISTS list_saves (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        list_id    INTEGER NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, list_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(list_id) REFERENCES lists(id)
    )
    """)

    # NOTIFICAÇÕES
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        type       TEXT NOT NULL,
        actor_id   INTEGER NOT NULL,
        target_id  INTEGER,
        is_read    INTEGER DEFAULT 0,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id)  REFERENCES users(id),
        FOREIGN KEY(actor_id) REFERENCES users(id)
    )
    """)
    conn.commit()

    # Adiciona coluna email na tabela users, se não existir
    try:
        c.execute('ALTER TABLE users ADD COLUMN email TEXT')
        conn.commit()
    except Exception:
        conn.rollback()

    # TOKENS DE RECUPERAÇÃO DE SENHA
    c.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        token      TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used       INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()
    print("Banco de dados PostgreSQL inicializado!")