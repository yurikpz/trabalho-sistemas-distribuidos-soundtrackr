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

    for col_sql in [
        'ALTER TABLE collection ADD COLUMN discogs_id TEXT',
        'ALTER TABLE collection ADD COLUMN year TEXT',
        'ALTER TABLE collection ADD COLUMN label TEXT',
        'ALTER TABLE collection ADD COLUMN catno TEXT',
        'ALTER TABLE collection ADD COLUMN country TEXT',
    ]:
        try:
            c.execute(col_sql)
            conn.commit()
        except Exception:
            conn.rollback()

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

    # LISTAS SALVAS
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

    try:
        c.execute('ALTER TABLE users ADD COLUMN lastfm_username TEXT')
        conn.commit()
    except Exception:
        conn.rollback()

    # ── FANDOMS ──────────────────────────────────────────────────────────────

    c.execute("""
    CREATE TABLE IF NOT EXISTS fandoms (
        id       SERIAL PRIMARY KEY,
        name     TEXT UNIQUE NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    for col_sql in [
        'ALTER TABLE fandoms ADD COLUMN artist_name TEXT',
        'ALTER TABLE fandoms ADD COLUMN color TEXT',
    ]:
        try:
            c.execute(col_sql)
            conn.commit()
        except Exception:
            conn.rollback()

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_fandoms (
        id         SERIAL PRIMARY KEY,
        user_id    INTEGER NOT NULL,
        fandom_id  INTEGER NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, fandom_id),
        FOREIGN KEY(user_id)   REFERENCES users(id),
        FOREIGN KEY(fandom_id) REFERENCES fandoms(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS fandom_posts (
        id         SERIAL PRIMARY KEY,
        fandom_id  INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        title      TEXT NOT NULL,
        text       TEXT,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(fandom_id) REFERENCES fandoms(id),
        FOREIGN KEY(user_id)   REFERENCES users(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS fandom_post_likes (
        id       SERIAL PRIMARY KEY,
        user_id  INTEGER NOT NULL,
        post_id  INTEGER NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, post_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES fandom_posts(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS fandom_post_comments (
        id       SERIAL PRIMARY KEY,
        post_id  INTEGER NOT NULL,
        user_id  INTEGER NOT NULL,
        text     TEXT NOT NULL,
        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(post_id) REFERENCES fandom_posts(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()

    # ── SEED: fandoms curados (nome, artista, cor) ────────────────────────────
    seed_fandoms = [
        # K-POP — grupos femininos
        ('FEARNOT', 'LE SSERAFIM', '#ff4d6d'),
        ('BLINK', 'BLACKPINK', '#ffb6d9'),
        ('ONCE', 'TWICE', '#ff9ecf'),
        ('NEVERLAND', '(G)I-DLE', '#ff5c5c'),
        ('DIVE', 'IVE', '#00c2c2'),
        ('MY', 'aespa', '#c9f2ff'),
        ('Bunnies', 'NewJeans', '#b5e8d5'),
        ('MIDZY', 'ITZY', '#ff2d55'),
        ('SONE', "Girls' Generation", '#c9a0dc'),
        ('Reveluv', 'Red Velvet', '#e63946'),
        ('Buddy', 'GFriend', '#87ceeb'),
        ('Panda', 'Apink', '#ffc0cb'),
        ('Wonderful', 'Wonder Girls', '#ff69b4'),
        ('Kep1ian', 'Kep1er', '#ffdd57'),
        ('Flover', 'fromis_9', '#ffb6c1'),
        ('Withmuu', 'MOMOLAND', '#ff8fa3'),
        ('Cracker', 'Weki Meki', '#9d4edd'),
        ('Baby', 'STAYC', '#fca3cc'),
        ('Nation', 'NMIXX', '#ff6f61'),
        ('Fanling', 'EVERGLOW', '#7b2ff7'),
        ('Zenith', 'WJSN', '#c8b6ff'),
        ('Somnia', 'aespa (alt)', '#9bf6ff'),
        ('Rose Blue', 'ROSÉ (solo)', '#e91e63'),
        ('Blossom', 'Jisoo (solo)', '#f8bbd0'),
        ('Aeri', 'IU', '#ffe066'),
        ('Winterland', 'Winter (solo)', '#a2d2ff'),
        ('Mystic', 'Taeyeon (solo)', '#ffd6a5'),

        # K-POP — grupos masculinos
        ('ARMY', 'BTS', '#6b5b95'),
        ('MOA', 'TOMORROW X TOGETHER', '#3d3d3d'),
        ('ENGENE', 'ENHYPEN', '#e0546e'),
        ('NCTzen', 'NCT', '#00e5ff'),
        ('Carat', 'SEVENTEEN', '#ff9800'),
        ('ATINY', 'ATEEZ', '#8a2be2'),
        ('STAY', 'Stray Kids', '#1e90ff'),
        ('ELF', 'Super Junior', '#007bb8'),
        ('Shawol', 'SHINee', '#a0d8ef'),
        ('VIP', 'BIGBANG', '#ffd700'),
        ('Inspirit', 'INFINITE', '#6a5acd'),
        ('Ahgase', 'GOT7', '#6ecb63'),
        ('Monbebe', 'MONSTA X', '#b71c1c'),
        ('Wannable', 'Wanna One', '#f4a261'),
        ('Angel128', 'NCT 127', '#00cfff'),
        ('Dreamer', 'NCT Dream', '#7ee8fa'),
        ('Zelo Fam', 'B.A.P', '#e63946'),
        ('Primero', 'The Boyz', '#c1121f'),
        ('OT8', 'ZEROBASEONE', '#4cc9f0'),
        ('Alpha', 'TREASURE', '#ff6b35'),
        ('Fantasy', 'ASTRO', '#8ecae6'),
        ('Aro', 'ATEEZ (alt) '.strip(), '#5a189a'),
        ('Boice', 'SF9', '#00b4d8'),
        ('Eclipse', 'Cravity', '#390099'),
        ('Namoo', 'DAY6', '#606c38'),
        ('Trainee', 'JBJ', '#ff9f1c'),

        # OCIDENTAL — POP
        ('Swifties', 'Taylor Swift', '#ff004d'),
        ('BeyHive', 'Beyoncé', '#f4c430'),
        ('Navy', 'Rihanna', '#003366'),
        ('Arianators', 'Ariana Grande', '#e0b0ff'),
        ('Barbz', 'Nicki Minaj', '#ff1493'),
        ('Bardi Gang', 'Cardi B', '#c0392b'),
        ('Little Monsters', 'Lady Gaga', '#ff69b4'),
        ('KatyCats', 'Katy Perry', '#00bcd4'),
        ('Selenators', 'Selena Gomez', '#ffb703'),
        ('Smilers', 'Miley Cyrus', '#ffdd00'),
        ('Beliebers', 'Justin Bieber', '#8ecae6'),
        ('Directioners', 'One Direction', '#e63946'),
        ('Harries', 'Harry Styles', '#ffb4a2'),
        ('Kittenz', 'Doja Cat', '#ff5c8a'),
        ('Hotties', 'Megan Thee Stallion', '#ff006e'),
        ('Rodrigo Fans', 'Olivia Rodrigo', '#8338ec'),
        ('Eilish Fans', 'Billie Eilish', '#7cb518'),
        ('Sheerios', 'Ed Sheeran', '#ff7f11'),
        ('Coldplayers', 'Coldplay', '#ffd166'),
        ('SZA Fans', 'SZA', '#7209b7'),
        ('Little Mixers', 'Little Mix', '#f72585'),
        ('Camilizers', 'Camila Cabello', '#ff9770'),
        ('Halsey Fans', 'Halsey', '#3a86ff'),
        ('Lizzo Fans', 'Lizzo', '#ffbe0b'),
        ('Adele Fans', 'Adele', '#264653'),
        ('Weeknd XO', 'The Weeknd', '#e63946'),
        ('Frank Ocean Fans', 'Frank Ocean', '#219ebc'),
        ('Bruno Mars Fans', 'Bruno Mars', '#fb8500'),
        ('Charlie Puth Fans', 'Charlie Puth', '#8ac926'),
        ('Shawn Mendes Fans', 'Shawn Mendes', '#ffca3a'),
        ('Dua Lipa Fans', 'Dua Lipa', '#ff595e'),
        ('Sabrina Stans', 'Sabrina Carpenter', '#ffafcc'),
        ('Chappell Fans', 'Chappell Roan', '#06d6a0'),

        # OCIDENTAL — HIP-HOP / R&B
        ('Stans', 'Eminem', '#495057'),
        ('Drakies', 'Drake', '#212529'),
        ('Kendrick Fans', 'Kendrick Lamar', '#606c38'),
        ('Dreamville', 'J. Cole', '#283618'),
        ('Cactus Jack', 'Travis Scott', '#6a4c93'),
        ('Posty Fans', 'Post Malone', '#adb5bd'),
        ('Yeezy Fans', 'Kanye West', '#343a40'),
        ('Hov Fans', 'JAY-Z', '#000000'),
        ('BeyGood', 'Beyoncé (alt)', '#ffd60a'),
        ('Lil Uzi Fans', 'Lil Uzi Vert', '#ff006e'),
        ('Playboi Cult', 'Playboi Carti', '#000000'),
        ('OVO Fans', 'OVO', '#8d99ae'),
        ('Migos Fam', 'Migos', '#7209b7'),
        ('Tyler Fans', 'Tyler, The Creator', '#ffb703'),
        ('Chance Fans', 'Chance the Rapper', '#f4a261'),
        ('SZA CTRL Fans', 'SZA (alt)', '#9d4edd'),
        ('H.E.R Fans', 'H.E.R.', '#ff6f59'),
        ('Summer Walker Fans', 'Summer Walker', '#c77dff'),

        # ROCK / ALTERNATIVO
        ('MCRmy', 'My Chemical Romance', '#000000'),
        ('P!ATD Fans', 'Panic! at the Disco', '#2b2d42'),
        ('Fall Out Boy Fans', 'Fall Out Boy', '#e63946'),
        ('Skeleton Clique', 'Twenty One Pilots', '#ffd60a'),
        ('Paramore Fans', 'Paramore', '#ff9770'),
        ('Green Day Fans', 'Green Day', '#2a9d8f'),
        ('Metallica Fans', 'Metallica', '#212529'),
        ('Linkin Park Fans', 'Linkin Park', '#e5383b'),
        ('Maggots', 'Slipknot', '#000000'),
        ('SOAD Fans', 'System of a Down', '#606c38'),
        ('Radiohead Fans', 'Radiohead', '#8d99ae'),
        ('Nirvana Fans', 'Nirvana', '#adb5bd'),
        ('Foo Fighters Fans', 'Foo Fighters', '#ffb703'),
        ('Imagine Dragons Fans', 'Imagine Dragons', '#457b9d'),
        ('Muse Fans', 'Muse', '#7209b7'),
        ('AC/DC Fans', 'AC/DC', '#000000'),
        ('Queen Fans', 'Queen', '#ffd60a'),
        ('Beatles Fans', 'The Beatles', '#003049'),
        ('Pink Floyd Fans', 'Pink Floyd', '#495057'),
        ('Arctic Monkeys Fans', 'Arctic Monkeys', '#1d3557'),
        ('The 1975 Fans', 'The 1975', '#f1faee'),

        # LATINO
        ('Bad Bunny Fans', 'Bad Bunny', '#00b4d8'),
        ('Karol G Fans', 'Karol G', '#ff006e'),
        ('Shakira Fans', 'Shakira', '#ffb703'),
        ('J Balvin Fans', 'J Balvin', '#ff9f1c'),
        ('Motomami', 'ROSALÍA', '#ff0054'),
        ('Daddy Yankee Fans', 'Daddy Yankee', '#adb5bd'),
        ('Maluma Fans', 'Maluma', '#ffbe0b'),
        ('Ozuna Fans', 'Ozuna', '#3a86ff'),
        ('Feid Fans', 'Feid', '#8338ec'),
        ('Rauw Alejandro Fans', 'Rauw Alejandro', '#ff5c8a'),
        ('Anitta Fans', 'Anitta', '#ff477e'),
        ('Luísa Fans', 'Luísa Sonza', '#ffafcc'),

        # BRASIL — GERAL
        ('Fandom Marília', 'Marília Mendonça', '#e63946'),
        ('Legião Urbana Fans', 'Legião Urbana', '#003049'),
        ('Racionais Fans', 'Racionais MC\'s', '#212529'),
        ('Djonga Fans', 'Djonga', '#5a189a'),
        ('Matuê Fans', 'Matuê', '#4361ee'),
        ('Ludmilla Fans', 'Ludmilla', '#ff006e'),
        ('Pabllo Fans', 'Pabllo Vittar', '#ff9770'),
        ('Iza Fans', 'Iza', '#f72585'),
        ('Gilberto Gil Fans', 'Gilberto Gil', '#ffbe0b'),
        ('Caetano Fans', 'Caetano Veloso', '#8ac926'),

        # J-POP / ANIME
        ('Arashians', 'Arashi', '#00b4d8'),
        ('BABYMETAL Fans', 'BABYMETAL', '#000000'),
        ('AKB48 Fans', 'AKB48', '#ff69b4'),
        ('Perfume Fans', 'Perfume', '#8ac926'),
        ('YOASOBI Fans', 'YOASOBI', '#ffd60a'),
        ('Kenshi Yonezu Fans', 'Kenshi Yonezu', '#264653'),
        ('LiSA Fans', 'LiSA', '#e63946'),

        # OUTROS GÊNEROS
        ('Deadheads', 'Grateful Dead', '#ffb703'),
        ('Parrotheads', 'Jimmy Buffett', '#00b4d8'),
        ('Swiftogatha', 'Taylor Swift (Eras)', '#ff004d'),
        ('Little Kids', 'Lana Del Rey', '#ffb4a2'),
        ('Beyhive Jr', 'Beyoncé (Renaissance)', '#f4c430'),
        ('Phish Phans', 'Phish', '#8ecae6'),
        ('Juice WRLD Fans', 'Juice WRLD', '#ff5c8a'),
        ('XXXTentacion Fans', 'XXXTENTACION', '#000000'),
        ('Mac Miller Fans', 'Mac Miller', '#ffb703'),
        ('Amy Winehouse Fans', 'Amy Winehouse', '#212529'),
        ('Prince Fans', 'Prince', '#800080'),
        ('MJ Fans', 'Michael Jackson', '#e63946'),
        ('Elvis Fans', 'Elvis Presley', '#003049'),
        ('Whitney Fans', 'Whitney Houston', '#ffd60a'),
        ('Madonna Fans', 'Madonna', '#ff006e'),
        ('Cher Fans', 'Cher', '#c77dff'),
        ('ABBA Fans', 'ABBA', '#ffbe0b'),
        ('Bee Gees Fans', 'Bee Gees', '#8ac926'),
        ('Fleetwood Mac Fans', 'Fleetwood Mac', '#606c38'),
        ('Eagles Fans', 'Eagles', '#adb5bd'),
        ('Bowie Fans', 'David Bowie', '#f4a261'),
        ('Springsteen Fans', 'Bruce Springsteen', '#264653'),
        ('U2 Fans', 'U2', '#2a9d8f'),
        ('R.E.M. Fans', 'R.E.M.', '#606c38'),
        ('Depeche Mode Fans', 'Depeche Mode', '#000000'),
        ('The Cure Fans', 'The Cure', '#212529'),
        ('Joy Division Fans', 'Joy Division', '#343a40'),
        ('Talking Heads Fans', 'Talking Heads', '#e63946'),
        ('Daft Punk Fans', 'Daft Punk', '#000000'),
        ('Justice Fans', 'Justice', '#ffd60a'),
        ('Calvin Harris Fans', 'Calvin Harris', '#00b4d8'),
        ('Avicii Fans', 'Avicii', '#8ecae6'),
        ('Skrillex Fans', 'Skrillex', '#7209b7'),
        ('Deadmau5 Fans', 'deadmau5', '#495057'),
        ('Marshmello Fans', 'Marshmello', '#ffffff'),
        ('ODESZA Fans', 'ODESZA', '#ff9f1c'),
        ('Flume Fans', 'Flume', '#4361ee'),
        ('Bonobo Fans', 'Bonobo', '#606c38'),
        ('Jazz Heads', 'Miles Davis', '#212529'),
        ('Coltrane Fans', 'John Coltrane', '#8d99ae'),
        ('Sinatra Fans', 'Frank Sinatra', '#003049'),
        ('Ella Fans', 'Ella Fitzgerald', '#ffb703'),
        ('Louis Fans', 'Louis Armstrong', '#e9c46a'),
        ('Country Roads', 'John Denver', '#8ac926'),
        ('Cash Fans', 'Johnny Cash', '#212529'),
        ('Dolly Fans', 'Dolly Parton', '#ff69b4'),
        ('Morgan Wallen Fans', 'Morgan Wallen', '#606c38'),
        ('Luke Combs Fans', 'Luke Combs', '#adb5bd'),
        ('Zach Bryan Fans', 'Zach Bryan', '#8d99ae'),
        ('Chris Stapleton Fans', 'Chris Stapleton', '#495057'),
        ('Fenix Fans', 'Fenix Furia', '#ff5c8a'),
    ]

    for name, artist, color in seed_fandoms:
        try:
            c.execute("""
                INSERT INTO fandoms (name, artist_name, color) VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET artist_name=EXCLUDED.artist_name, color=EXCLUDED.color
            """, (name, artist, color))
        except Exception:
            conn.rollback()

    conn.commit()
    conn.close()
    print("Banco de dados PostgreSQL inicializado!")