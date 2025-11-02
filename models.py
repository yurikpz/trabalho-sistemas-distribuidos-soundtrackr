import sqlite3
from datetime import datetime

DB = 'music.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    
    #USUÁRIOS
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        fandom TEXT,
        avatar TEXT,
        bio TEXT
    )
    """)


    for col in ["bio TEXT"]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass

    
    #BIBLIOTECA (NOTAS E METADDADOS POR TRACKID)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        trackId TEXT,
        trackName TEXT,
        collectionName TEXT,
        artistName TEXT,
        artworkUrl100 TEXT,
        previewUrl TEXT,
        rating INTEGER,
        note TEXT,
        addedAt TEXT,
        UNIQUE(user_id, trackId)
    )
    """)

    #FAVORITOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        trackId TEXT,
        trackName TEXT,
        artistName TEXT,
        artworkUrl100 TEXT,
        UNIQUE(user_id, trackId)
    )
    """)

    #CORRIGE O BANCO ANTIGO
    for col in ["trackName TEXT", "artistName TEXT", "artworkUrl100 TEXT"]:
        try:
            c.execute(f"ALTER TABLE favorites ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass

    #LISTAS 
    c.execute("""
    CREATE TABLE IF NOT EXISTS lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        createdAt TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, name)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS list_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL,
        trackId TEXT,
        trackName TEXT,
        artistName TEXT,
        artworkUrl100 TEXT,
        addedAt TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(list_id, trackId),
        FOREIGN KEY(list_id) REFERENCES lists(id)
    )
    """)

    
    #HISTÓRICO DE OUVIDAS

    c.execute("""
    CREATE TABLE IF NOT EXISTS listened (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        trackId TEXT,
        trackName TEXT,
        artistName TEXT,
        artworkUrl100 TEXT,
        listenedAt TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)


    #DIÁRIO

    c.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        trackId TEXT,
        trackName TEXT,
        artistName TEXT,
        artworkUrl100 TEXT,
        listenedAt TEXT    -- YYYY-MM-DD ou timestamp completo
    )
    """)


    #REVIEWS

    c.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        trackId TEXT,
        username TEXT,
        text TEXT,
        createdAt TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado e atualizado com sucesso!")
