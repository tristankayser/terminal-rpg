"""
game_lang.py — Multi-language support for Terminal-RPG.
20 languages: EN DE FR ES PT IT RU PL NL SV JA ZH KO AR TR CS HU RO FI NO

Usage:
    from game_lang import T, set_language, pick_language_screen, LANG
    T("combat.attack")              → "Attack"
    T("combat.damage", dmg=17)      → "You dealt 17 damage!"
    T("menu.inn", cost=20)          → "Rest & heal  (20 gold)"
"""

from __future__ import annotations

import os

_R="\033[0m"; _B="\033[1m"
def _fg(r,g,b): return f"\033[38;2;{r};{g};{b}m"
_GOLD=_fg(255,215,0); _WHITE=_fg(255,255,255); _DIM=_fg(100,100,100)
_GREEN=_fg(80,200,80); _RED=_fg(220,60,60); _CYAN=_fg(80,220,220)

# ── Current language (module-level global) ─────────────────────
LANG = "EN"

LANGUAGE_NAMES = {
    "EN": "English",
    "DE": "Deutsch",
    "FR": "Français",
    "ES": "Español",
    "PT": "Português",
    "IT": "Italiano",
    "RU": "Русский",
    "PL": "Polski",
    "NL": "Nederlands",
    "SV": "Svenska",
    "JA": "日本語",
    "ZH": "简体中文",
    "KO": "한국어",
    "AR": "العربية",
    "TR": "Türkçe",
    "CS": "Čeština",
    "HU": "Magyar",
    "RO": "Română",
    "FI": "Suomi",
    "NO": "Norsk",
}

LANG_ORDER = list(LANGUAGE_NAMES.keys())

def set_language(code: str):
    global LANG
    if code in LANGUAGE_NAMES:
        LANG = code

def get_language() -> str:
    return LANG

# ── Translation function ────────────────────────────────────────
def T(key: str, **kwargs) -> str:
    """
    Translate key to current language.
    STRINGS structure: { "key": { "EN": "...", "DE": "...", ... } }
    Falls back to English if key missing in chosen language.
    Supports {var} substitution via kwargs.
    """
    key_dict = STRINGS.get(key, {})
    text = key_dict.get(LANG) or key_dict.get("EN") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text

# ═══════════════════════════════════════════════════════════════
# TRANSLATION STRINGS
# ═══════════════════════════════════════════════════════════════
# Each key maps to a dict of language→string.
# Only EN is required; others fall back to EN if missing.

STRINGS: dict[str, dict[str, str]] = {}

def _add(**langs):
    """Add a batch of translations. First arg must be 'key'."""
    pass  # replaced below

# Build strings as one big dict
_S: dict[str, dict[str, str]] = {

    # ── MAIN MENU ──────────────────────────────────────────────
    "menu.new_game":    {"EN":"New Game","DE":"Neues Spiel","FR":"Nouvelle Partie","ES":"Nueva Partida","PT":"Novo Jogo","IT":"Nuova Partita","RU":"Новая игра","PL":"Nowa Gra","NL":"Nieuw Spel","SV":"Nytt Spel","JA":"新しいゲーム","ZH":"新游戏","KO":"새 게임","AR":"لعبة جديدة","TR":"Yeni Oyun","CS":"Nová Hra","HU":"Új Játék","RO":"Joc Nou","FI":"Uusi Peli","NO":"Nytt Spill"},
    "menu.load_game":   {"EN":"Load Game","DE":"Spiel Laden","FR":"Charger Partie","ES":"Cargar Partida","PT":"Carregar Jogo","IT":"Carica Partita","RU":"Загрузить игру","PL":"Wczytaj Grę","NL":"Spel Laden","SV":"Ladda Spel","JA":"ゲームをロード","ZH":"载入游戏","KO":"게임 불러오기","AR":"تحميل اللعبة","TR":"Oyun Yükle","CS":"Načíst Hru","HU":"Játék Betöltése","RO":"Încarcă Jocul","FI":"Lataa Peli","NO":"Last Spill"},
    "menu.language":    {"EN":"Language","DE":"Sprache","FR":"Langue","ES":"Idioma","PT":"Idioma","IT":"Lingua","RU":"Язык","PL":"Język","NL":"Taal","SV":"Språk","JA":"言語","ZH":"语言","KO":"언어","AR":"اللغة","TR":"Dil","CS":"Jazyk","HU":"Nyelv","RO":"Limbă","FI":"Kieli","NO":"Språk"},
    "menu.quit":        {"EN":"Quit","DE":"Beenden","FR":"Quitter","ES":"Salir","PT":"Sair","IT":"Esci","RU":"Выйти","PL":"Wyjdź","NL":"Afsluiten","SV":"Avsluta","JA":"終了","ZH":"退出","KO":"종료","AR":"خروج","TR":"Çıkış","CS":"Konec","HU":"Kilépés","RO":"Ieșire","FI":"Lopeta","NO":"Avslutt"},
    "menu.save_found":  {"EN":"Save found: {name} Lv{level} {job} — {location}","DE":"Speicherstand: {name} Lv{level} {job} — {location}","FR":"Sauvegarde: {name} Niv.{level} {job} — {location}","ES":"Guardado: {name} Nv.{level} {job} — {location}","PT":"Salvo: {name} Nv.{level} {job} — {location}","IT":"Salvataggio: {name} Lv{level} {job} — {location}","RU":"Сохранение: {name} Ур.{level} {job} — {location}","PL":"Zapis: {name} Poz.{level} {job} — {location}","NL":"Opgeslagen: {name} Nv{level} {job} — {location}","SV":"Sparad: {name} Nv{level} {job} — {location}","JA":"セーブ: {name} Lv{level} {job} — {location}","ZH":"存档: {name} {level}级 {job} — {location}","KO":"저장됨: {name} Lv{level} {job} — {location}","AR":"حفظ: {name} مستوى {level} {job} — {location}","TR":"Kayıt: {name} Sv{level} {job} — {location}","CS":"Uloženo: {name} Úr.{level} {job} — {location}","HU":"Mentés: {name} Szint{level} {job} — {location}","RO":"Salvare: {name} Nv{level} {job} — {location}","FI":"Tallennus: {name} Taso{level} {job} — {location}","NO":"Lagret: {name} Nv{level} {job} — {location}"},
    "menu.no_save":     {"EN":"No save file found. Start a New Game first.","DE":"Keine Speicherdatei gefunden. Starte zuerst ein neues Spiel.","FR":"Aucune sauvegarde. Commencez une nouvelle partie.","ES":"No hay guardado. Inicia una nueva partida primero.","PT":"Nenhum arquivo salvo. Inicie um novo jogo primeiro.","IT":"Nessun salvataggio. Inizia prima una nuova partita.","RU":"Файл сохранения не найден. Сначала начните новую игру.","PL":"Brak zapisu. Najpierw zacznij nową grę.","NL":"Geen opgeslagen spel gevonden. Begin eerst een nieuw spel.","SV":"Ingen sparad fil. Börja ett nytt spel först.","JA":"セーブファイルが見つかりません。新しいゲームを始めてください。","ZH":"未找到存档，请先开始新游戏。","KO":"저장 파일 없음. 먼저 새 게임을 시작하세요.","AR":"لا يوجد ملف حفظ. ابدأ لعبة جديدة أولاً.","TR":"Kayıt dosyası bulunamadı. Önce Yeni Oyun başlatın.","CS":"Žádný uložený soubor. Začněte nejprve novou hru.","HU":"Nincs mentési fájl. Előbb kezdj új játékot.","RO":"Niciun fișier salvat. Începe mai întâi un joc nou.","FI":"Tallennustiedostoa ei löydy. Aloita ensin uusi peli.","NO":"Ingen lagringsfil funnet. Start et nytt spill først."},

    # ── CHARACTER CREATION ─────────────────────────────────────
    "create.title":         {"EN":"CREATE YOUR CHARACTER","DE":"FIGUR ERSTELLEN","FR":"CRÉER VOTRE PERSONNAGE","ES":"CREAR TU PERSONAJE","PT":"CRIAR SEU PERSONAGEM","IT":"CREA IL TUO PERSONAGGIO","RU":"СОЗДАНИЕ ПЕРСОНАЖА","PL":"STWÓRZ POSTAĆ","NL":"MAAK JE PERSONAGE","SV":"SKAPA DIN KARAKTÄR","JA":"キャラクター作成","ZH":"创建角色","KO":"캐릭터 만들기","AR":"إنشاء شخصيتك","TR":"KARAKTERİNİ OLUŞTUR","CS":"VYTVOŘTE POSTAVU","HU":"KARAKTER LÉTREHOZÁSA","RO":"CREEAZĂ-ȚI PERSONAJUL","FI":"LUO HAHMOSI","NO":"LAG DIN KARAKTER"},
    "create.name_prompt":   {"EN":"Enter your character's name:","DE":"Gib den Namen deiner Figur ein:","FR":"Entrez le nom de votre personnage:","ES":"Ingresa el nombre de tu personaje:","PT":"Digite o nome do seu personagem:","IT":"Inserisci il nome del tuo personaggio:","RU":"Введите имя персонажа:","PL":"Wprowadź imię postaci:","NL":"Voer de naam van je personage in:","SV":"Ange din karaktärs namn:","JA":"キャラクターの名前を入力してください：","ZH":"输入角色名称：","KO":"캐릭터 이름을 입력하세요:","AR":"أدخل اسم شخصيتك:","TR":"Karakterinin adını gir:","CS":"Zadejte jméno postavy:","HU":"Írd be a karakter nevét:","RO":"Introdu numele personajului:","FI":"Syötä hahmosi nimi:","NO":"Skriv inn karakterens navn:"},
    "create.choose_class":  {"EN":"CHOOSE YOUR CLASS","DE":"KLASSE WÄHLEN","FR":"CHOISISSEZ VOTRE CLASSE","ES":"ELIGE TU CLASE","PT":"ESCOLHA SUA CLASSE","IT":"SCEGLI LA TUA CLASSE","RU":"ВЫБЕРИТЕ КЛАСС","PL":"WYBIERZ KLASĘ","NL":"KIES JE KLASSE","SV":"VÄLJ DIN KLASS","JA":"クラスを選択","ZH":"选择职业","KO":"직업 선택","AR":"اختر فصيلتك","TR":"SINIFINI SEÇ","CS":"VYBERTE TŘÍDU","HU":"VÁLASSZ OSZTÁLYT","RO":"ALEGE-ȚI CLASA","FI":"VALITSE LUOKKASI","NO":"VELG DIN KLASSE"},
    "create.choose_1_to_5": {"EN":"Choose class (1-5):","DE":"Klasse wählen (1-5):","FR":"Choisissez la classe (1-5):","ES":"Elige la clase (1-5):","PT":"Escolha a classe (1-5):","IT":"Scegli la classe (1-5):","RU":"Выберите класс (1-5):","PL":"Wybierz klasę (1-5):","NL":"Kies klasse (1-5):","SV":"Välj klass (1-5):","JA":"クラスを選ぶ (1-5)：","ZH":"选择职业 (1-5)：","KO":"직업 선택 (1-5):","AR":"اختر الفصيلة (1-5):","TR":"Sınıf seç (1-5):","CS":"Vyberte třídu (1-5):","HU":"Válassz osztályt (1-5):","RO":"Alege clasa (1-5):","FI":"Valitse luokka (1-5):","NO":"Velg klasse (1-5):"},
    "create.starts_journey":{"EN":"{name} the {job} begins their journey!","DE":"{name} der {job} beginnt seine Reise!","FR":"{name} le/la {job} commence son voyage!","ES":"¡{name} el/la {job} comienza su viaje!","PT":"{name} o/a {job} começa sua jornada!","IT":"{name} il/la {job} inizia il suo viaggio!","RU":"{name} — {job} начинает своё путешествие!","PL":"{name} — {job} — wyrusza w podróż!","NL":"{name} de {job} begint zijn/haar reis!","SV":"{name} {job}en börjar sin resa!","JA":"{job}の{name}が旅を始める！","ZH":"{name}（{job}）开始了旅程！","KO":"{job} {name}이(가) 여정을 시작합니다!","AR":"يبدأ {name} {job} رحلته!","TR":"{job} {name} yolculuğuna başlıyor!","CS":"{name} {job} začíná svou cestu!","HU":"{name} a {job} megkezdi útját!","RO":"{name} {job}-ul îşi începe călătoria!","FI":"{job} {name} aloittaa matkansa!","NO":"{name} {job}en begynner sin reise!"},
    "create.god_potion_note":{"EN":"You carry 1 God Potion. Auto-activates at 0 HP. Guard it.","DE":"Du trägst 1 Gottestrank. Aktiviert sich automatisch bei 0 LP. Hüte ihn.","FR":"Vous portez 1 Potion Divine. S'active à 0 PV. Protégez-la.","ES":"Llevas 1 Poción Divina. Se activa a 0 PV. Cuídala.","PT":"Você carrega 1 Poção Divina. Ativa-se a 0 PV. Guarde-a.","IT":"Porti 1 Pozione Divina. Si attiva a 0 PF. Proteggila.","RU":"У вас 1 Божественное Зелье. Активируется при 0 HP. Берегите его.","PL":"Masz 1 Boski Eliksir. Aktywuje się przy 0 HP. Strzeż go.","NL":"Je draagt 1 Goddelijk Drankje. Activeert bij 0 LP. Bewaar het.","SV":"Du bär 1 Gudaporion. Aktiveras vid 0 HP. Skydda den.","JA":"神のポーションを1つ持っています。HP0で自動発動。大切に。","ZH":"你携带1个神灵药水。HP归零时自动触发，请珍藏。","KO":"신의 물약 1개 보유. HP 0시 자동 발동. 소중히 여기세요.","AR":"لديك 1 جرعة إلهية. تنشط عند 0 صحة. احتفظ بها.","TR":"1 Tanrı İksiri taşıyorsun. 0 HP'de otomatik aktif olur. Koru onu.","CS":"Máte 1 Božský Lektvar. Aktivuje se při 0 HP. Chraňte ho.","HU":"1 Isteni Bájitalt viszel. 0 HP-nél automatikusan aktiválódik. Óvd.","RO":"Ai 1 Poțiune Divină. Se activează la 0 HP. Păstrează-o.","FI":"Sinulla on 1 Jumalan Juoma. Aktivoituu 0 HP:llä. Varjele sitä.","NO":"Du bærer 1 Gudsdrikk. Aktiveres ved 0 HP. Vern om den."},

    # ── MOVEMENT MODE ──────────────────────────────────────────
    "move.title":       {"EN":"MOVEMENT MODE","DE":"BEWEGUNGSMODUS","FR":"MODE DE DÉPLACEMENT","ES":"MODO DE MOVIMIENTO","PT":"MODO DE MOVIMENTO","IT":"MODALITÀ MOVIMENTO","RU":"РЕЖИМ ДВИЖЕНИЯ","PL":"TRYB RUCHU","NL":"BEWEGINGSMODUS","SV":"RÖRELSLÄGE","JA":"移動モード","ZH":"移动模式","KO":"이동 모드","AR":"وضع الحركة","TR":"HAREKET MODU","CS":"REŽIM POHYBU","HU":"MOZGÁSMÓD","RO":"MOD DE MIȘCARE","FI":"LIIKETILA","NO":"BEVEGELSESMODUS"},
    "move.wasd":        {"EN":"WASD  (4 directions)","DE":"WASD  (4 Richtungen)","FR":"WASD  (4 directions)","ES":"WASD  (4 direcciones)","PT":"WASD  (4 direções)","IT":"WASD  (4 direzioni)","RU":"WASD  (4 направления)","PL":"WASD  (4 kierunki)","NL":"WASD  (4 richtingen)","SV":"WASD  (4 riktningar)","JA":"WASD（4方向）","ZH":"WASD（4方向）","KO":"WASD（4방향）","AR":"WASD (4 اتجاهات)","TR":"WASD (4 yön)","CS":"WASD  (4 směry)","HU":"WASD  (4 irány)","RO":"WASD  (4 direcții)","FI":"WASD  (4 suuntaa)","NO":"WASD  (4 retninger)"},
    "move.8dir":        {"EN":"8-Direction (Number keys 1-9)","DE":"8 Richtungen (1-9)","FR":"8 directions (touches 1-9)","ES":"8 Direcciones (1-9)","PT":"8 Direções (1-9)","IT":"8 Direzioni (1-9)","RU":"8 направлений (1-9)","PL":"8 Kierunków (1-9)","NL":"8 Richtingen (1-9)","SV":"8 Riktningar (1-9)","JA":"8方向（数字キー1-9）","ZH":"8方向（数字键1-9）","KO":"8방향（숫자 키 1-9）","AR":"8 اتجاهات (1-9)","TR":"8 Yön (1-9)","CS":"8 Směrů (1-9)","HU":"8 Irány (1-9)","RO":"8 Direcții (1-9)","FI":"8 Suuntaa (1-9)","NO":"8 Retninger (1-9)"},
    "move.arrow_note":  {"EN":"Arrow keys work in both modes.","DE":"Pfeiltasten funktionieren in beiden Modi.","FR":"Les touches fléchées fonctionnent dans les deux modes.","ES":"Las teclas de flecha funcionan en ambos modos.","PT":"As teclas de seta funcionam em ambos os modos.","IT":"I tasti freccia funzionano in entrambe le modalità.","RU":"Клавиши со стрелками работают в обоих режимах.","PL":"Klawisze strzałek działają w obu trybach.","NL":"Pijltjestoetsen werken in beide modi.","SV":"Piltangenterna fungerar i båda lägena.","JA":"矢印キーはどちらのモードでも使えます。","ZH":"两种模式均支持方向键。","KO":"화살표 키는 두 모드 모두 작동합니다.","AR":"مفاتيح الأسهم تعمل في كلا الوضعين.","TR":"Ok tuşları her iki modda da çalışır.","CS":"Šipky fungují v obou režimech.","HU":"A nyílbillentyűk mindkét módban működnek.","RO":"Tastele săgeată funcționează în ambele moduri.","FI":"Nuolinäppäimet toimivat molemmissa tiloissa.","NO":"Piltastene fungerer i begge moduser."},

    # ── WORLD MAP ──────────────────────────────────────────────
    "world.title":      {"EN":"Terminal-RPG","DE":"Terminal-RPG","FR":"Terminal-RPG","ES":"Terminal-RPG","PT":"Terminal-RPG","IT":"Terminal-RPG","RU":"Terminal-RPG","PL":"Terminal-RPG","NL":"Terminal-RPG","SV":"Terminal-RPG","JA":"ターミナルRPG","ZH":"终端RPG","KO":"터미널 RPG","AR":"Terminal-RPG","TR":"Terminal-RPG","CS":"Terminal-RPG","HU":"Terminal-RPG","RO":"Terminal-RPG","FI":"Terminal-RPG","NO":"Terminal-RPG"},
    "world.turn":       {"EN":"Turn {n}","DE":"Runde {n}","FR":"Tour {n}","ES":"Turno {n}","PT":"Rodada {n}","IT":"Turno {n}","RU":"Ход {n}","PL":"Tura {n}","NL":"Beurt {n}","SV":"Runda {n}","JA":"ターン {n}","ZH":"回合 {n}","KO":"턴 {n}","AR":"دور {n}","TR":"Tur {n}","CS":"Tah {n}","HU":"Kör {n}","RO":"Tur {n}","FI":"Vuoro {n}","NO":"Runde {n}"},
    "world.enter_prompt":{"EN":"[E] to enter.","DE":"[E] zum Betreten.","FR":"[E] pour entrer.","ES":"[E] para entrar.","PT":"[E] para entrar.","IT":"[E] per entrare.","RU":"[E] — войти.","PL":"[E] aby wejść.","NL":"[E] om binnen te gaan.","SV":"[E] för att gå in.","JA":"[E]で入る。","ZH":"按[E]进入。","KO":"[E] 눌러 입장.","AR":"[E] للدخول.","TR":"[E] girmek için.","CS":"[E] ke vstupu.","HU":"[E] a belépéshez.","RO":"[E] pentru a intra.","FI":"[E] syötä.","NO":"[E] for å gå inn."},
    "world.ocean_block":{"EN":"The sea blocks you. Find a port and board a ship.","DE":"Das Meer versperrt den Weg. Finde einen Hafen und board ein Schiff.","FR":"La mer vous bloque. Trouvez un port et montez à bord d'un navire.","ES":"El mar te bloquea. Encuentra un puerto y aborda un barco.","PT":"O mar bloqueia você. Encontre um porto e embarque em um navio.","IT":"Il mare ti blocca. Trova un porto e imbarca su una nave.","RU":"Море преграждает путь. Найдите порт и сядьте на корабль.","PL":"Morze blokuje drogę. Znajdź port i wsiądź na statek.","NL":"De zee blokkeert je. Vind een haven en ga aan boord van een schip.","SV":"Havet blockerar dig. Hitta en hamn och gå ombord på ett skepp.","JA":"海が道を塞いでいます。港を見つけて船に乗ってください。","ZH":"海洋阻挡了你。请找到港口并登船。","KO":"바다가 막혀있습니다. 항구를 찾아 배에 타세요.","AR":"البحر يسدّ طريقك. ابحث عن ميناء واستقل سفينة.","TR":"Deniz seni engelliyor. Bir liman bul ve gemiye bin.","CS":"Moře ti blokuje cestu. Najdi přístav a nastup na loď.","HU":"A tenger elzárja az utat. Keress kikötőt és szállj hajóra.","RO":"Marea te blochează. Găsește un port și urcă pe o navă.","FI":"Meri estää sinua. Löydä satama ja nouse laivaan.","NO":"Havet blokkerer deg. Finn en havn og gå ombord på et skip."},
    "world.edge":       {"EN":"Edge of the world.","DE":"Rand der Welt.","FR":"Bord du monde.","ES":"Borde del mundo.","PT":"Fim do mundo.","IT":"Bordo del mondo.","RU":"Край мира.","PL":"Kraniec świata.","NL":"Rand van de wereld.","SV":"Världens kant.","JA":"世界の端。","ZH":"世界边缘。","KO":"세상의 끝.","AR":"حافة العالم.","TR":"Dünyanın sonu.","CS":"Kraj světa.","HU":"A világ széle.","RO":"Marginea lumii.","FI":"Maailman reuna.","NO":"Verdens ende."},
    "world.saved":      {"EN":"Game saved!","DE":"Spiel gespeichert!","FR":"Partie sauvegardée!","ES":"¡Partida guardada!","PT":"Jogo salvo!","IT":"Partita salvata!","RU":"Игра сохранена!","PL":"Gra zapisana!","NL":"Spel opgeslagen!","SV":"Spelet sparat!","JA":"ゲームを保存しました！","ZH":"游戏已保存！","KO":"게임 저장됨!","AR":"تم حفظ اللعبة!","TR":"Oyun kaydedildi!","CS":"Hra uložena!","HU":"A játék mentve!","RO":"Joc salvat!","FI":"Peli tallennettu!","NO":"Spill lagret!"},
    "world.save_quit":  {"EN":"Save before quitting?","DE":"Vor dem Beenden speichern?","FR":"Sauvegarder avant de quitter?","ES":"¿Guardar antes de salir?","PT":"Salvar antes de sair?","IT":"Salvare prima di uscire?","RU":"Сохранить перед выходом?","PL":"Zapisać przed wyjściem?","NL":"Opslaan voor het afsluiten?","SV":"Spara innan du avslutar?","JA":"終了前に保存しますか？","ZH":"退出前保存吗？","KO":"종료 전 저장하시겠습니까?","AR":"حفظ قبل الخروج؟","TR":"Çıkmadan önce kaydet?","CS":"Uložit před ukončením?","HU":"Mentés kilépés előtt?","RO":"Salvezi înainte de ieșire?","FI":"Tallenna ennen lopettamista?","NO":"Lagre før du avslutter?"},
    "world.arrived_city":{"EN":"Arrived at {name}.","DE":"Angekommen in {name}.","FR":"Arrivé à {name}.","ES":"Llegaste a {name}.","PT":"Chegou a {name}.","IT":"Arrivato a {name}.","RU":"Вы прибыли в {name}.","PL":"Dotarłeś do {name}.","NL":"Aangekomen in {name}.","SV":"Anlänt till {name}.","JA":"{name}に到着。","ZH":"到达{name}。","KO":"{name}에 도착했습니다.","AR":"وصلت إلى {name}.","TR":"{name}'e ulaştın.","CS":"Přijel jsi do {name}.","HU":"Megérkeztél {name}-ba.","RO":"Ai ajuns la {name}.","FI":"Saavuit paikkaan {name}.","NO":"Ankom {name}."},
    "world.found_dungeon":{"EN":"Dungeon: {name}.","DE":"Verlies: {name}.","FR":"Donjon: {name}.","ES":"Mazmorra: {name}.","PT":"Masmorra: {name}.","IT":"Dungeon: {name}.","RU":"Подземелье: {name}.","PL":"Loch: {name}.","NL":"Kerker: {name}.","SV":"Fängelsehåla: {name}.","JA":"ダンジョン: {name}。","ZH":"地牢：{name}。","KO":"던전: {name}.","AR":"زنزانة: {name}.","TR":"Zindan: {name}.","CS":"Dungeon: {name}.","HU":"Dungeon: {name}.","RO":"Temniță: {name}.","FI":"Luola: {name}.","NO":"Fangehull: {name}."},
    "world.immunity_on":{"EN":"Enemies sense your divine protection and back away.","DE":"Feinde spüren deinen göttlichen Schutz und weichen zurück.","FR":"Les ennemis sentent votre protection divine et reculent.","ES":"Los enemigos sienten tu protección divina y retroceden.","PT":"Os inimigos sentem sua proteção divina e recuam.","IT":"I nemici percepiscono la tua protezione divina e si ritirano.","RU":"Враги чувствуют вашу защиту богов и отступают.","PL":"Wrogowie czują twoją boską ochronę i cofają się.","NL":"Vijanden voelen je goddelijke bescherming en wijken terug.","SV":"Fienderna känner ditt gudomliga skydd och drar sig tillbaka.","JA":"敵が神の加護を感じて退いた。","ZH":"敌人感受到神圣护盾，退后了。","KO":"적들이 신성한 보호를 감지하고 물러났습니다.","AR":"الأعداء يشعرون بحمايتك الإلهية ويتراجعون.","TR":"Düşmanlar ilahi korumanı hissedip geri çekiliyor.","CS":"Nepřátelé cítí tvou božskou ochranu a ustupují.","HU":"Az ellenségek érzik isteni védelmedet és visszavonulnak.","RO":"Dușmanii simt protecția ta divină și se retrag.","FI":"Viholliset tuntevat jumalallisen suojeluksesi ja vetäytyvät.","NO":"Fiendene kjenner din guddommelige beskyttelse og trekker seg tilbake."},
    "world.immunity_fade":{"EN":"Divine protection fades. Stay alert!","DE":"Göttlicher Schutz schwindet. Bleibe wachsam!","FR":"La protection divine s'efface. Restez vigilant!","ES":"La protección divina se desvanece. ¡Mantente alerta!","PT":"A proteção divina desaparece. Fique alerta!","IT":"La protezione divina svanisce. Rimani all'erta!","RU":"Защита богов угасает. Будьте осторожны!","PL":"Boska ochrona zanika. Bądź czujny!","NL":"Goddelijke bescherming vervaagt. Blijf alert!","SV":"Det gudomliga skyddet avtar. Var alert!","JA":"神の加護が消えた。油断するな！","ZH":"神圣保护消退，保持警惕！","KO":"신성한 보호가 사라졌습니다. 조심하세요!","AR":"الحماية الإلهية تتلاشى. ابقَ يقظاً!","TR":"İlahi koruma soluyor. Dikkatli ol!","CS":"Božská ochrana slábne. Buď ostražitý!","HU":"Az isteni védelem elhalványul. Maradj éber!","RO":"Protecția divină dispare. Rămâi vigilent!","FI":"Jumalallinen suojelu haalistuu. Pysy valppaana!","NO":"Guddommelig beskyttelse avtar. Hold deg på vakt!"},

    # ── COMBAT ─────────────────────────────────────────────────
    "combat.battle":    {"EN":"BATTLE: {name}","DE":"KAMPF: {name}","FR":"COMBAT: {name}","ES":"BATALLA: {name}","PT":"BATALHA: {name}","IT":"BATTAGLIA: {name}","RU":"БОЙ: {name}","PL":"WALKA: {name}","NL":"GEVECHT: {name}","SV":"STRID: {name}","JA":"バトル: {name}","ZH":"战斗：{name}","KO":"전투: {name}","AR":"معركة: {name}","TR":"SAVAŞ: {name}","CS":"SOUBOJ: {name}","HU":"HARC: {name}","RO":"LUPTĂ: {name}","FI":"TAISTELU: {name}","NO":"KAMP: {name}"},
    "combat.boss":      {"EN":"BOSS BATTLE: {name}","DE":"BOSSGEGNER: {name}","FR":"COMBAT DE BOSS: {name}","ES":"JEFE: {name}","PT":"CHEFÃO: {name}","IT":"BOSS: {name}","RU":"БОЙ С БОССОМ: {name}","PL":"BOSS: {name}","NL":"BAASGEVECHT: {name}","SV":"BOSSSTRID: {name}","JA":"ボスバトル: {name}","ZH":"BOSS战：{name}","KO":"보스 전투: {name}","AR":"معركة الزعيم: {name}","TR":"BOSS SAVAŞI: {name}","CS":"BOSS SOUBOJ: {name}","HU":"FŐELLENSÉG: {name}","RO":"LUPTĂ CU ȘEFUL: {name}","FI":"POMOTAISTELU: {name}","NO":"SJEFSSLÅSSKAMP: {name}"},
    "combat.attack":    {"EN":"Attack","DE":"Angriff","FR":"Attaquer","ES":"Atacar","PT":"Atacar","IT":"Attacca","RU":"Атаковать","PL":"Atak","NL":"Aanvallen","SV":"Attackera","JA":"攻撃","ZH":"攻击","KO":"공격","AR":"هجوم","TR":"Saldır","CS":"Útok","HU":"Támadás","RO":"Atac","FI":"Hyökkää","NO":"Angrip"},
    "combat.skill":     {"EN":"Skill","DE":"Fertigkeit","FR":"Compétence","ES":"Habilidad","PT":"Habilidade","IT":"Abilità","RU":"Умение","PL":"Umiejętność","NL":"Vaardigheid","SV":"Förmåga","JA":"スキル","ZH":"技能","KO":"스킬","AR":"مهارة","TR":"Beceri","CS":"Dovednost","HU":"Képesség","RO":"Abilitate","FI":"Taito","NO":"Ferdighet"},
    "combat.item":      {"EN":"Item","DE":"Gegenstand","FR":"Objet","ES":"Objeto","PT":"Item","IT":"Oggetto","RU":"Предмет","PL":"Przedmiot","NL":"Voorwerp","SV":"Föremål","JA":"アイテム","ZH":"道具","KO":"아이템","AR":"عنصر","TR":"Eşya","CS":"Předmět","HU":"Tárgy","RO":"Obiect","FI":"Esine","NO":"Gjenstand"},
    "combat.defend":    {"EN":"Defend","DE":"Verteidigen","FR":"Défendre","ES":"Defender","PT":"Defender","IT":"Difendi","RU":"Защищаться","PL":"Obrona","NL":"Verdedigen","SV":"Försvara","JA":"防御","ZH":"防御","KO":"방어","AR":"دفاع","TR":"Savun","CS":"Obrana","HU":"Védekezés","RO":"Apără","FI":"Puolusta","NO":"Forsvar"},
    "combat.run":       {"EN":"Run","DE":"Fliehen","FR":"Fuir","ES":"Huir","PT":"Fugir","IT":"Fuggi","RU":"Бежать","PL":"Uciekaj","NL":"Vluchten","SV":"Fly","JA":"逃げる","ZH":"逃跑","KO":"도망","AR":"اهرب","TR":"Kaç","CS":"Utéct","HU":"Menekülés","RO":"Fugi","FI":"Pakene","NO":"Rømm"},
    "combat.victory":   {"EN":"VICTORY!","DE":"SIEG!","FR":"VICTOIRE!","ES":"¡VICTORIA!","PT":"VITÓRIA!","IT":"VITTORIA!","RU":"ПОБЕДА!","PL":"ZWYCIĘSTWO!","NL":"OVERWINNING!","SV":"SEGER!","JA":"勝利！","ZH":"胜利！","KO":"승리!","AR":"انتصار!","TR":"ZAFERr!","CS":"VÍTĚZSTVÍ!","HU":"GYŐZELEM!","RO":"VICTORIE!","FI":"VOITTO!","NO":"SEIER!"},
    "combat.defeated":  {"EN":"DEFEATED","DE":"BESIEGT","FR":"DÉFAITE","ES":"DERROTADO","PT":"DERROTADO","IT":"SCONFITTO","RU":"ПОРАЖЕНИЕ","PL":"POKONANY","NL":"VERSLAGEN","SV":"BESEGRAD","JA":"敗北","ZH":"失败","KO":"패배","AR":"مهزوم","TR":"YENİLDİN","CS":"PORAŽEN","HU":"VERESÉG","RO":"ÎNFRÂNGERE","FI":"HÄVITTY","NO":"BESEIRET"},
    "combat.you_strike":{"EN":"You strike{crit} → {dmg} damage!","DE":"Du schlägst{crit} → {dmg} Schaden!","FR":"Vous frappez{crit} → {dmg} dégâts!","ES":"¡Golpeas{crit} → {dmg} de daño!","PT":"Você ataca{crit} → {dmg} de dano!","IT":"Attacchi{crit} → {dmg} danni!","RU":"Вы наносите{crit} → {dmg} урона!","PL":"Uderzasz{crit} → {dmg} obrażeń!","NL":"Je slaat{crit} → {dmg} schade!","SV":"Du slår{crit} → {dmg} skada!","JA":"攻撃{crit} → {dmg}ダメージ！","ZH":"你攻击{crit} → {dmg}伤害！","KO":"공격{crit} → {dmg} 데미지!","AR":"تضرب{crit} → ضرر {dmg}!","TR":"Vurdun{crit} → {dmg} hasar!","CS":"Útočíš{crit} → {dmg} zranění!","HU":"Ütsz{crit} → {dmg} sebzés!","RO":"Lovești{crit} → {dmg} daunz!","FI":"Lyöt{crit} → {dmg} vahinkoa!","NO":"Du slår{crit} → {dmg} skade!"},
    "combat.enemy_strikes":{"EN":"{name} attacks{crit} → {dmg} damage!","DE":"{name} greift an{crit} → {dmg} Schaden!","FR":"{name} attaque{crit} → {dmg} dégâts!","ES":"¡{name} ataca{crit} → {dmg} de daño!","PT":"{name} ataca{crit} → {dmg} de dano!","IT":"{name} attacca{crit} → {dmg} danni!","RU":"{name} атакует{crit} → {dmg} урона!","PL":"{name} atakuje{crit} → {dmg} obrażeń!","NL":"{name} valt aan{crit} → {dmg} schade!","SV":"{name} attackerar{crit} → {dmg} skada!","JA":"{name}の攻撃{crit} → {dmg}ダメージ！","ZH":"{name}攻击{crit} → {dmg}伤害！","KO":"{name} 공격{crit} → {dmg} 데미지!","AR":"{name} يهاجم{crit} → ضرر {dmg}!","TR":"{name} saldırdı{crit} → {dmg} hasar!","CS":"{name} útočí{crit} → {dmg} zranění!","HU":"{name} támad{crit} → {dmg} sebzés!","RO":"{name} atacă{crit} → {dmg} daune!","FI":"{name} hyökkää{crit} → {dmg} vahinkoa!","NO":"{name} angriper{crit} → {dmg} skade!"},
    "combat.dodged":    {"EN":"{name} dodged your strike!","DE":"{name} ist ausgewichen!","FR":"{name} a esquivé votre coup!","ES":"¡{name} esquivó tu golpe!","PT":"{name} esquivou do seu golpe!","IT":"{name} ha schivato il tuo colpo!","RU":"{name} уклонился от удара!","PL":"{name} uniknął twojego ciosu!","NL":"{name} ontweek je aanval!","SV":"{name} undvek din attack!","JA":"{name}は攻撃を回避した！","ZH":"{name}躲开了你的攻击！","KO":"{name}이(가) 공격을 피했습니다!","AR":"تملّص {name} من ضربتك!","TR":"{name} saldırını savuşturdu!","CS":"{name} se vyhnul tvému útoku!","HU":"{name} kitért a csapás elől!","RO":"{name} a evitat lovitura ta!","FI":"{name} väisti iskusi!","NO":"{name} unnvek angrepet ditt!"},
    "combat.stunned":   {"EN":"You are stunned and cannot act this turn!","DE":"Du bist betäubt und kannst diese Runde nicht handeln!","FR":"Vous êtes étourdi et ne pouvez pas agir ce tour!","ES":"¡Estás aturdido y no puedes actuar este turno!","PT":"Você está atordoado e não pode agir neste turno!","IT":"Sei stordito e non puoi agire questo turno!","RU":"Вы оглушены и не можете действовать в этот ход!","PL":"Jesteś ogłuszony i nie możesz działać w tej turze!","NL":"Je bent verdoofd en kunt deze beurt niet handelen!","SV":"Du är omtöcknad och kan inte agera denna runda!","JA":"スタン状態！このターンは行動できない！","ZH":"你被击晕，本回合无法行动！","KO":"기절 상태! 이번 턴에 행동할 수 없습니다!","AR":"أنت مذهول ولا يمكنك التصرف هذا الدور!","TR":"Sersemledin ve bu tur hareket edemiyorsun!","CS":"Jsi omráčen a nemůžeš jednat v tomto kole!","HU":"Megszédültél és nem cselekedhetsz ezen a körön!","RO":"Ești amețit și nu poți acționa în acest tur!","FI":"Olet taintunut etkä voi toimia tällä vuorolla!","NO":"Du er svimmel og kan ikke handle denne runden!"},
    "combat.fled":      {"EN":"You successfully flee!","DE":"Du bist erfolgreich geflohen!","FR":"Vous fuyez avec succès!","ES":"¡Huyes con éxito!","PT":"Você foge com sucesso!","IT":"Fuggi con successo!","RU":"Вы успешно сбегаете!","PL":"Udało ci się uciec!","NL":"Je vlucht succesvol!","SV":"Du flyr framgångsrikt!","JA":"うまく逃げ切った！","ZH":"你成功逃跑了！","KO":"성공적으로 도망쳤습니다!","AR":"فررت بنجاح!","TR":"Başarıyla kaçtın!","CS":"Úspěšně utíkáš!","HU":"Sikeresen elmenekülsz!","RO":"Fugi cu succes!","FI":"Pakenee onnistuneesti!","NO":"Du flykter vellykket!"},
    "combat.cant_flee": {"EN":"You couldn't escape!","DE":"Du konntest nicht entkommen!","FR":"Vous n'avez pas pu fuir!","ES":"¡No pudiste escapar!","PT":"Você não conseguiu escapar!","IT":"Non sei riuscito a fuggire!","RU":"Вам не удалось сбежать!","PL":"Nie udało ci się uciec!","NL":"Je kon niet ontsnappen!","SV":"Du kunde inte fly!","JA":"逃げられなかった！","ZH":"你没能逃掉！","KO":"도망칠 수 없었습니다!","AR":"لم تستطع الهروب!","TR":"Kaçamadın!","CS":"Nemohl jsi utéct!","HU":"Nem tudtál elmenekülni!","RO":"Nu ai putut scăpa!","FI":"Et päässyt pakenemaan!","NO":"Du kunne ikke flykte!"},
    "combat.gold_exp":  {"EN":"+{gold} Gold   +{exp} EXP","DE":"+{gold} Gold   +{exp} EP","FR":"+{gold} Or   +{exp} EXP","ES":"+{gold} Oro   +{exp} EXP","PT":"+{gold} Ouro   +{exp} EXP","IT":"+{gold} Oro   +{exp} EXP","RU":"+{gold} Золото   +{exp} Опыт","PL":"+{gold} Złoto   +{exp} Dośw.","NL":"+{gold} Goud   +{exp} ERV","SV":"+{gold} Guld   +{exp} EP","JA":"+{gold}G   +{exp}EXP","ZH":"+{gold}金币   +{exp}经验","KO":"+{gold} 골드   +{exp} EXP","AR":"+{gold} ذهب   +{exp} خبرة","TR":"+{gold} Altın   +{exp} EXP","CS":"+{gold} Zlato   +{exp} ZKU","HU":"+{gold} Arany   +{exp} TP","RO":"+{gold} Aur   +{exp} EXP","FI":"+{gold} Kulta   +{exp} KOK","NO":"+{gold} Gull   +{exp} EXP"},
    "combat.loot":      {"EN":"Loot dropped:","DE":"Beute erhalten:","FR":"Butin obtenu:","ES":"Botín obtenido:","PT":"Saque obtido:","IT":"Bottino ottenuto:","RU":"Добыча:","PL":"Zdobycz:","NL":"Buit verkregen:","SV":"Byte erhållet:","JA":"ドロップ品：","ZH":"战利品：","KO":"아이템 드롭:","AR":"غنائم مكتسبة:","TR":"Düşen eşyalar:","CS":"Získaná kořist:","HU":"Zsákmány:","RO":"Pradă obținută:","FI":"Saalis:","NO":"Utbytte falt:"},
    "combat.no_drops":  {"EN":"No items dropped.","DE":"Keine Gegenstände erhalten.","FR":"Aucun objet obtenu.","ES":"No se obtuvieron objetos.","PT":"Nenhum item foi obtido.","IT":"Nessun oggetto ottenuto.","RU":"Предметов не выпало.","PL":"Żadnych przedmiotów.","NL":"Geen voorwerpen verkregen.","SV":"Inga föremål föll.","JA":"アイテムはドロップしなかった。","ZH":"没有掉落物品。","KO":"아이템 드롭 없음.","AR":"لم تسقط أي عناصر.","TR":"Eşya düşmedi.","CS":"Žádné předměty nepadly.","HU":"Nem esett ki semmi.","RO":"Niciun obiect nu a căzut.","FI":"Ei esineitä pudotettu.","NO":"Ingen gjenstander droppet."},
    "combat.level_up":  {"EN":"LEVEL UP! {name} is now Level {level}!","DE":"LEVELAUFSTIEG! {name} ist jetzt Level {level}!","FR":"NIVEAU SUPÉRIEUR! {name} est maintenant niveau {level}!","ES":"¡SUBIDA DE NIVEL! ¡{name} ahora es nivel {level}!","PT":"SUBIU DE NÍVEL! {name} agora é nível {level}!","IT":"LIVELLO SUPERIORE! {name} è ora livello {level}!","RU":"ПОВЫШЕНИЕ УРОВНЯ! {name} теперь {level}-й уровень!","PL":"AWANS POZIOMU! {name} jest teraz poziomem {level}!","NL":"LEVEL OMHOOG! {name} is nu level {level}!","SV":"NIVÅ UPP! {name} är nu nivå {level}!","JA":"レベルアップ！{name}はレベル{level}になった！","ZH":"{name}升级了！现在是{level}级！","KO":"레벨 업! {name}이(가) 이제 레벨 {level}입니다!","AR":"ارتفع المستوى! {name} الآن مستوى {level}!","TR":"SEVİYE ATLADI! {name} artık {level}. seviye!","CS":"POSTUP NA ÚROVEŇ! {name} je nyní úroveň {level}!","HU":"SZINTLÉPÉS! {name} most {level}. szintű!","RO":"NIVEL NOU! {name} este acum nivelul {level}!","FI":"TASO NOUSI! {name} on nyt taso {level}!","NO":"NIVÅ OPP! {name} er nå nivå {level}!"},
    "combat.sneak_attack":{"EN":"SNEAK ATTACK!","DE":"HINTERHALTSANGRIFF!","FR":"ATTAQUE SOURNOISE!","ES":"¡ATAQUE FURTIVO!","PT":"ATAQUE FURTIVO!","IT":"ATTACCO FURTIVO!","RU":"ВНЕЗАПНАЯ АТАКА!","PL":"ATAK Z ZASKOCZENIA!","NL":"SLUIPANVAL!","SV":"SMYGATTACK!","JA":"スニークアタック！","ZH":"偷袭攻击！","KO":"몰래 공격!","AR":"هجوم مباغت!","TR":"GİZLİ SALDIRI!","CS":"ZÁKEŘNÝ ÚTOK!","HU":"ORVTÁMADÁS!","RO":"ATAC DIN UMBRĂ!","FI":"SALAHYÖKKÄYS!","NO":"LUREANGREP!"},

    # ── TOWN MENU ──────────────────────────────────────────────
    "town.inn":         {"EN":"Inn","DE":"Gasthaus","FR":"Auberge","ES":"Posada","PT":"Estalagem","IT":"Locanda","RU":"Таверна","PL":"Gospoda","NL":"Herberg","SV":"Värdshus","JA":"宿屋","ZH":"旅馆","KO":"여관","AR":"نزل","TR":"Han","CS":"Hospoda","HU":"Fogadó","RO":"Han","FI":"Majatalo","NO":"Vertshus"},
    "town.shop":        {"EN":"Shop","DE":"Laden","FR":"Boutique","ES":"Tienda","PT":"Loja","IT":"Negozio","RU":"Магазин","PL":"Sklep","NL":"Winkel","SV":"Butik","JA":"店","ZH":"商店","KO":"상점","AR":"متجر","TR":"Dükkan","CS":"Obchod","HU":"Bolt","RO":"Magazin","FI":"Kauppa","NO":"Butikk"},
    "town.quest_board": {"EN":"Quest Board","DE":"Auftragstafel","FR":"Tableau de Quêtes","ES":"Tablón de Misiones","PT":"Quadro de Missões","IT":"Bacheca Missioni","RU":"Доска заданий","PL":"Tablica Zadań","NL":"Opdrachtenboard","SV":"Uppdragstavla","JA":"クエストボード","ZH":"任务板","KO":"퀘스트 게시판","AR":"لوحة المهام","TR":"Görev Panosu","CS":"Nástěnka Úkolů","HU":"Küldetéstábla","RO":"Panou de Misiuni","FI":"Tehtävätaulu","NO":"Oppdragstavle"},
    "town.guild":       {"EN":"Adventurers Guild","DE":"Abenteurergilde","FR":"Guilde des Aventuriers","ES":"Gremio de Aventureros","PT":"Guilda dos Aventureiros","IT":"Gilda degli Avventurieri","RU":"Гильдия авантюристов","PL":"Gildia Poszukiwaczy","NL":"Avonturiersgilde","SV":"Äventyrargildet","JA":"冒険者ギルド","ZH":"冒险者工会","KO":"모험가 길드","AR":"نقابة المغامرين","TR":"Maceracılar Loncası","CS":"Cech Dobrodruhů","HU":"Kalandozók Céhe","RO":"Breasla Aventurierilor","FI":"Seikkailijoiden Kilta","NO":"Eventyrernes Laug"},
    "town.talk":        {"EN":"Talk to Townsfolk","DE":"Mit Stadtbewohnern sprechen","FR":"Parler aux habitants","ES":"Hablar con lugareños","PT":"Conversar com moradores","IT":"Parla con gli abitanti","RU":"Говорить с жителями","PL":"Rozmawiaj z mieszkańcami","NL":"Praat met de stadsbewoners","SV":"Tala med stadsborna","JA":"町の人と話す","ZH":"与居民交谈","KO":"마을 사람과 대화","AR":"تحدث مع سكان البلدة","TR":"Kasaba halkıyla konuş","CS":"Mluv s obyvateli","HU":"Beszélj a helyiekkel","RO":"Vorbește cu localnicii","FI":"Puhu kyläläisille","NO":"Snakk med innbyggerne"},
    "town.crafting":    {"EN":"Crafting Bench","DE":"Werkbank","FR":"Établi","ES":"Banco de Artesanía","PT":"Bancada de Criação","IT":"Tavolo da Lavoro","RU":"Верстак","PL":"Stół Rzemieślniczy","NL":"Werkbank","SV":"Hantverksbänk","JA":"作業台","ZH":"合成台","KO":"제작대","AR":"طاولة الصنع","TR":"El Sanatları Tezgahı","CS":"Řemeslný Stůl","HU":"Kézműves Pad","RO":"Bancul de Lucru","FI":"Käsityöpenkki","NO":"Håndverksbord"},
    "town.status":      {"EN":"Status","DE":"Status","FR":"Statut","ES":"Estado","PT":"Status","IT":"Stato","RU":"Состояние","PL":"Status","NL":"Status","SV":"Status","JA":"ステータス","ZH":"状态","KO":"상태","AR":"الحالة","TR":"Durum","CS":"Stav","HU":"Állapot","RO":"Stare","FI":"Tila","NO":"Status"},
    "town.inventory":   {"EN":"Inventory","DE":"Inventar","FR":"Inventaire","ES":"Inventario","PT":"Inventário","IT":"Inventario","RU":"Инвентарь","PL":"Ekwipunek","NL":"Inventaris","SV":"Inventarie","JA":"インベントリ","ZH":"物品栏","KO":"인벤토리","AR":"المخزون","TR":"Envanter","CS":"Inventář","HU":"Leltár","RO":"Inventar","FI":"Varasto","NO":"Inventar"},
    "town.save":        {"EN":"Save Game","DE":"Spiel Speichern","FR":"Sauvegarder","ES":"Guardar Partida","PT":"Salvar Jogo","IT":"Salva Partita","RU":"Сохранить игру","PL":"Zapisz Grę","NL":"Spel Opslaan","SV":"Spara Spel","JA":"ゲームを保存","ZH":"保存游戏","KO":"게임 저장","AR":"حفظ اللعبة","TR":"Oyunu Kaydet","CS":"Uložit Hru","HU":"Játék Mentése","RO":"Salvează Jocul","FI":"Tallenna Peli","NO":"Lagre Spill"},
    "town.recruit":     {"EN":"Recruit Companions","DE":"Gefährten Rekrutieren","FR":"Recruter des Compagnons","ES":"Reclutar Compañeros","PT":"Recrutar Companheiros","IT":"Recluta Compagni","RU":"Нанять соратников","PL":"Rekrutuj Towarzyszy","NL":"Metgezellen Werven","SV":"Rekrytera Följeslagare","JA":"仲間を雇う","ZH":"招募同伴","KO":"동료 모집","AR":"تجنيد الرفاق","TR":"Yoldaş Topla","CS":"Najmi Společníky","HU":"Társak Toborzása","RO":"Recrutează Tovarăși","FI":"Rekrytoi Seuralaisia","NO":"Verv Følgesvenner"},
    "town.trade":       {"EN":"Trade (Barter)","DE":"Handel (Tausch)","FR":"Commerce (Troc)","ES":"Comerciar (Trueque)","PT":"Negociar (Escambo)","IT":"Commercio (Baratto)","RU":"Торговля (Бартер)","PL":"Handel (Wymiana)","NL":"Handel (Ruil)","SV":"Handel (Byte)","JA":"交易（物々交換）","ZH":"交易（以物换物）","KO":"거래 (물물교환)","AR":"تجارة (مقايضة)","TR":"Ticaret (Takas)","CS":"Obchod (Bartér)","HU":"Kereskedelem (Csere)","RO":"Comerț (Troc)","FI":"Kauppa (Vaihtokauppa)","NO":"Handel (Bytte)"},
    "town.codex":       {"EN":"Encyclopedia","DE":"Enzyklopädie","FR":"Encyclopédie","ES":"Enciclopedia","PT":"Enciclopédia","IT":"Enciclopedia","RU":"Энциклопедия","PL":"Encyklopedia","NL":"Encyclopedie","SV":"Encyklopedi","JA":"百科事典","ZH":"百科全书","KO":"백과사전","AR":"موسوعة","TR":"Ansiklopedi","CS":"Encyklopedie","HU":"Enciklopédia","RO":"Enciclopedie","FI":"Ensyklopedia","NO":"Leksikon"},
    "town.base":        {"EN":"Your Base","DE":"Deine Basis","FR":"Votre Base","ES":"Tu Base","PT":"Sua Base","IT":"La Tua Base","RU":"Ваша база","PL":"Twoja Baza","NL":"Jouw Basis","SV":"Din Bas","JA":"あなたの拠点","ZH":"你的基地","KO":"내 기지","AR":"قاعدتك","TR":"Üssün","CS":"Tvá Základna","HU":"Az Alaptáborod","RO":"Baza Ta","FI":"Tukikohtasi","NO":"Din base"},
    "town.leave":       {"EN":"Leave Town","DE":"Stadt Verlassen","FR":"Quitter la Ville","ES":"Salir del Pueblo","PT":"Sair da Cidade","IT":"Lascia la Città","RU":"Покинуть город","PL":"Opuść Miasto","NL":"Stad Verlaten","SV":"Lämna Staden","JA":"町を出る","ZH":"离开城镇","KO":"마을 떠나기","AR":"غادر البلدة","TR":"Kasabadan Ayrıl","CS":"Odejdi z Města","HU":"Elhagyod a Várost","RO":"Părăsește Orașul","FI":"Poistu kaupungista","NO":"Forlat byen"},
    "town.rest_full":   {"EN":"Rest fully? HP & MP restored, status cleared.","DE":"Vollständig ausruhen? HP & MP wiederhergestellt, Status gelöscht.","FR":"Se reposer complètement? PV & PM restaurés, statuts effacés.","ES":"¿Descansar completamente? PV & PM restaurados, estados eliminados.","PT":"Descansar completamente? HP & MP restaurados, status limpos.","IT":"Riposare completamente? PF & PM restaurati, stati eliminati.","RU":"Отдохнуть полностью? HP и MP восстановлены, эффекты сняты.","PL":"Odpocząć całkowicie? HP i MP przywrócone, stany usunięte.","NL":"Volledig rusten? HP & MP hersteld, statussen gewist.","SV":"Vila helt? HP & MP återställt, statusar rensade.","JA":"完全休憩？HP&MP回復、状態異常解除。","ZH":"完全休息？HP和MP恢复，状态清除。","KO":"완전 휴식? HP와 MP 회복, 상태 이상 해제.","AR":"الاستراحة الكاملة؟ استعادة HP وMP ومسح الحالات.","TR":"Tam dinlen? HP & MP onarıldı, durumlar temizlendi.","CS":"Odpočinout si plně? HP i MP obnoveny, stavy zrušeny.","HU":"Teljes pihenés? HP és MP visszaállítva, állapotok törölve.","RO":"Odihnă completă? HP & MP restabilite, stările șterse.","FI":"Lepää täysin? HP ja MP palautettu, tilat puhdistettu.","NO":"Hvile helt? HP & MP gjenopprettet, statusene fjernet."},
    "town.inn_cost":    {"EN":"Full rest costs {cost} gold.","DE":"Vollständige Erholung kostet {cost} Gold.","FR":"Le repos complet coûte {cost} pièces d'or.","ES":"El descanso completo cuesta {cost} de oro.","PT":"O descanso completo custa {cost} ouro.","IT":"Il riposo completo costa {cost} oro.","RU":"Полный отдых стоит {cost} золота.","PL":"Pełny odpoczynek kosztuje {cost} złota.","NL":"Volledig rusten kost {cost} goud.","SV":"Fullständig vila kostar {cost} guld.","JA":"完全休息には{cost}ゴールドかかります。","ZH":"完全休息需要{cost}金币。","KO":"완전 휴식 비용: {cost} 골드.","AR":"الاستراحة الكاملة تكلف {cost} ذهباً.","TR":"Tam dinlenme {cost} altın maliyeti.","CS":"Plný odpočinek stojí {cost} zlata.","HU":"A teljes pihenés {cost} aranyba kerül.","RO":"Odihna completă costă {cost} aur.","FI":"Täysi lepo maksaa {cost} kultaa.","NO":"Full hvile koster {cost} gull."},

    # ── GOD POTION ─────────────────────────────────────────────
    "god.activated":    {"EN":"GOD POTION ACTIVATED!","DE":"GOTTESTRANK AKTIVIERT!","FR":"POTION DIVINE ACTIVÉE!","ES":"¡POCIÓN DIVINA ACTIVADA!","PT":"POÇÃO DIVINA ATIVADA!","IT":"POZIONE DIVINA ATTIVATA!","RU":"БОЖЕСТВЕННОЕ ЗЕЛЬЕ АКТИВИРОВАНО!","PL":"BOSKI ELIKSIR AKTYWOWANY!","NL":"GODDELIJK DRANKJE GEACTIVEERD!","SV":"GUDAPORION AKTIVERAD!","JA":"神のポーション発動！","ZH":"神灵药水激活！","KO":"신의 물약 발동!","AR":"الجرعة الإلهية نشطت!","TR":"TANRI İKSİRİ ETKİNLEŞTİ!","CS":"BOŽSKÝ LEKTVAR AKTIVOVÁN!","HU":"ISTENI BÁJITAL AKTIVÁLVA!","RO":"POȚIUNE DIVINĂ ACTIVATĂ!","FI":"JUMALAN JUOMA AKTIVOITU!","NO":"GUDSDRIKK AKTIVERT!"},
    "god.rises":        {"EN":"{name} rises again with {hp} HP!","DE":"{name} erhebt sich wieder mit {hp} LP!","FR":"{name} se relève avec {hp} PV!","ES":"¡{name} resucita con {hp} PV!","PT":"{name} ressurge com {hp} PV!","IT":"{name} si rialza con {hp} PF!","RU":"{name} поднимается снова с {hp} HP!","PL":"{name} powstaje ponownie z {hp} HP!","NL":"{name} staat weer op met {hp} LP!","SV":"{name} reser sig igen med {hp} HP!","JA":"{name}がHP{hp}で復活した！","ZH":"{name}以{hp}点HP重生！","KO":"{name}이(가) HP {hp}로 다시 일어났습니다!","AR":"{name} يعود بـ {hp} صحة!","TR":"{name} {hp} HP ile tekrar yükseliyor!","CS":"{name} vstává znovu s {hp} HP!","HU":"{name} ismét felkel {hp} HP-val!","RO":"{name} se ridică din nou cu {hp} HP!","FI":"{name} nousee jälleen {hp} HP:lla!","NO":"{name} reiser seg igjen med {hp} HP!"},
    "god.immunity":     {"EN":"Enemies will avoid you for 30 moves.","DE":"Feinde werden dir 30 Züge lang ausweichen.","FR":"Les ennemis vous éviteront pendant 30 tours.","ES":"Los enemigos te evitarán durante 30 movimientos.","PT":"Os inimigos vão te evitar por 30 movimentos.","IT":"I nemici ti eviteranno per 30 mosse.","RU":"Враги будут избегать вас 30 ходов.","PL":"Wrogowie będą cię unikać przez 30 ruchów.","NL":"Vijanden zullen je 30 bewegingen vermijden.","SV":"Fiender undviker dig i 30 drag.","JA":"30ターン間、敵があなたを避ける。","ZH":"30步内敌人将回避你。","KO":"30번의 이동 동안 적들이 피합니다.","AR":"سيتجنب الأعداء 30 حركة.","TR":"Düşmanlar 30 hamle boyunca senden kaçacak.","CS":"Nepřátelé se ti budou vyhýbat 30 tahů.","HU":"Az ellenségek 30 lépésen át elkerülnek téged.","RO":"Dușmanii te vor evita timp de 30 de mișcări.","FI":"Viholliset välttävät sinua 30 siirron ajan.","NO":"Fiendene vil unngå deg i 30 trekk."},

    # ── MISC UI ────────────────────────────────────────────────
    "ui.press_enter":   {"EN":"(Press Enter)","DE":"(Enter drücken)","FR":"(Appuyez sur Entrée)","ES":"(Presiona Enter)","PT":"(Pressione Enter)","IT":"(Premi Invio)","RU":"(Нажмите Enter)","PL":"(Naciśnij Enter)","NL":"(Druk op Enter)","SV":"(Tryck Enter)","JA":"（Enterキーを押してください）","ZH":"（按回车键）","KO":"(Enter 누르기)","AR":"(اضغط Enter)","TR":"(Enter'a bas)","CS":"(Stiskni Enter)","HU":"(Nyomd meg az Entert)","RO":"(Apasă Enter)","FI":"(Paina Enter)","NO":"(Trykk Enter)"},
    "ui.invalid":       {"EN":"Invalid choice.","DE":"Ungültige Auswahl.","FR":"Choix invalide.","ES":"Opción inválida.","PT":"Escolha inválida.","IT":"Scelta non valida.","RU":"Неверный выбор.","PL":"Nieprawidłowy wybór.","NL":"Ongeldige keuze.","SV":"Ogiltigt val.","JA":"無効な選択です。","ZH":"无效选择。","KO":"잘못된 선택입니다.","AR":"اختيار غير صالح.","TR":"Geçersiz seçim.","CS":"Neplatná volba.","HU":"Érvénytelen választás.","RO":"Alegere invalidă.","FI":"Virheellinen valinta.","NO":"Ugyldig valg."},
    "ui.cancel":        {"EN":"Cancel","DE":"Abbrechen","FR":"Annuler","ES":"Cancelar","PT":"Cancelar","IT":"Annulla","RU":"Отмена","PL":"Anuluj","NL":"Annuleren","SV":"Avbryt","JA":"キャンセル","ZH":"取消","KO":"취소","AR":"إلغاء","TR":"İptal","CS":"Zrušit","HU":"Mégse","RO":"Anulare","FI":"Peruuta","NO":"Avbryt"},
    "ui.back":          {"EN":"Back","DE":"Zurück","FR":"Retour","ES":"Volver","PT":"Voltar","IT":"Indietro","RU":"Назад","PL":"Wróć","NL":"Terug","SV":"Tillbaka","JA":"戻る","ZH":"返回","KO":"뒤로","AR":"رجوع","TR":"Geri","CS":"Zpět","HU":"Vissza","RO":"Înapoi","FI":"Takaisin","NO":"Tilbake"},
    "ui.confirm":       {"EN":"Confirm","DE":"Bestätigen","FR":"Confirmer","ES":"Confirmar","PT":"Confirmar","IT":"Conferma","RU":"Подтвердить","PL":"Potwierdź","NL":"Bevestigen","SV":"Bekräfta","JA":"確認","ZH":"确认","KO":"확인","AR":"تأكيد","TR":"Onayla","CS":"Potvrdit","HU":"Megerősítés","RO":"Confirmă","FI":"Vahvista","NO":"Bekreft"},
    "ui.yes":           {"EN":"Yes","DE":"Ja","FR":"Oui","ES":"Sí","PT":"Sim","IT":"Sì","RU":"Да","PL":"Tak","NL":"Ja","SV":"Ja","JA":"はい","ZH":"是","KO":"예","AR":"نعم","TR":"Evet","CS":"Ano","HU":"Igen","RO":"Da","FI":"Kyllä","NO":"Ja"},
    "ui.no":            {"EN":"No","DE":"Nein","FR":"Non","ES":"No","PT":"Não","IT":"No","RU":"Нет","PL":"Nie","NL":"Nee","SV":"Nej","JA":"いいえ","ZH":"否","KO":"아니요","AR":"لا","TR":"Hayır","CS":"Ne","HU":"Nem","RO":"Nu","FI":"Ei","NO":"Nei"},
    "ui.not_enough_gold":{"EN":"Not enough gold!","DE":"Nicht genug Gold!","FR":"Pas assez d'or!","ES":"¡No hay suficiente oro!","PT":"Ouro insuficiente!","IT":"Oro insufficiente!","RU":"Недостаточно золота!","PL":"Niewystarczająco złota!","NL":"Niet genoeg goud!","SV":"Inte tillräckligt med guld!","JA":"ゴールドが足りません！","ZH":"金币不足！","KO":"골드가 부족합니다!","AR":"لا يكفي الذهب!","TR":"Yeterli altın yok!","CS":"Nedostatek zlata!","HU":"Nincs elég arany!","RO":"Nu ai destul aur!","FI":"Ei tarpeeksi kultaa!","NO":"Ikke nok gull!"},
    "ui.gold":          {"EN":"Gold","DE":"Gold","FR":"Or","ES":"Oro","PT":"Ouro","IT":"Oro","RU":"Золото","PL":"Złoto","NL":"Goud","SV":"Guld","JA":"ゴールド","ZH":"金币","KO":"골드","AR":"ذهب","TR":"Altın","CS":"Zlato","HU":"Arany","RO":"Aur","FI":"Kulta","NO":"Gull"},
    "ui.level":         {"EN":"Lv","DE":"Lv","FR":"Niv","ES":"Nv","PT":"Nv","IT":"Lv","RU":"Ур","PL":"Poz","NL":"Nv","SV":"Nv","JA":"Lv","ZH":"级","KO":"Lv","AR":"مستوى","TR":"Sv","CS":"Úr","HU":"Szint","RO":"Nv","FI":"Taso","NO":"Nv"},
    "ui.rank":          {"EN":"Rank","DE":"Rang","FR":"Rang","ES":"Rango","PT":"Rank","IT":"Rango","RU":"Ранг","PL":"Ranga","NL":"Rang","SV":"Rang","JA":"ランク","ZH":"等级","KO":"랭크","AR":"رتبة","TR":"Rütbe","CS":"Hodnost","HU":"Rang","RO":"Rang","FI":"Sijoitus","NO":"Rang"},

    # ── LANGUAGE PICKER ────────────────────────────────────────
    "lang.title":       {"EN":"SELECT LANGUAGE","DE":"SPRACHE WÄHLEN","FR":"SÉLECTIONNER LA LANGUE","ES":"SELECCIONAR IDIOMA","PT":"SELECIONAR IDIOMA","IT":"SELEZIONA LINGUA","RU":"ВЫБОР ЯЗЫКА","PL":"WYBIERZ JĘZYK","NL":"TAAL SELECTEREN","SV":"VÄLJ SPRÅK","JA":"言語を選択","ZH":"选择语言","KO":"언어 선택","AR":"اختر اللغة","TR":"DİL SEÇ","CS":"VYBERTE JAZYK","HU":"VÁLASSZ NYELVET","RO":"SELECTEAZĂ LIMBA","FI":"VALITSE KIELI","NO":"VELG SPRÅK"},
    "lang.saved":       {"EN":"Language set to {lang}. Changes take effect immediately.","DE":"Sprache auf {lang} gesetzt.","FR":"Langue définie sur {lang}.","ES":"Idioma establecido en {lang}.","PT":"Idioma definido como {lang}.","IT":"Lingua impostata su {lang}.","RU":"Язык установлен: {lang}.","PL":"Język ustawiony na {lang}.","NL":"Taal ingesteld op {lang}.","SV":"Språk inställt till {lang}.","JA":"言語を{lang}に設定しました。","ZH":"语言已设置为{lang}。","KO":"언어가 {lang}로 설정되었습니다.","AR":"تم تعيين اللغة إلى {lang}.","TR":"Dil {lang} olarak ayarlandı.","CS":"Jazyk nastaven na {lang}.","HU":"A nyelv {lang}-re van állítva.","RO":"Limba setată la {lang}.","FI":"Kieli asetettu: {lang}.","NO":"Språk satt til {lang}."},

    # ── SHIP / SAILING ─────────────────────────────────────────
    "ship.title":       {"EN":"SHIP: {port}","DE":"SCHIFF: {port}","FR":"NAVIRE: {port}","ES":"BARCO: {port}","PT":"NAVIO: {port}","IT":"NAVE: {port}","RU":"КОРАБЛЬ: {port}","PL":"STATEK: {port}","NL":"SCHIP: {port}","SV":"SKEPP: {port}","JA":"船: {port}","ZH":"船只：{port}","KO":"배: {port}","AR":"سفينة: {port}","TR":"GEMİ: {port}","CS":"LOĎ: {port}","HU":"HAJÓ: {port}","RO":"CORABIE: {port}","FI":"LAIVA: {port}","NO":"SKIP: {port}"},
    "ship.setting_sail":{"EN":"Setting sail for {dest}...","DE":"Abfahrt nach {dest}...","FR":"En route pour {dest}...","ES":"Zarpando hacia {dest}...","PT":"Partindo para {dest}...","IT":"Salpando per {dest}...","RU":"Отплываем к {dest}...","PL":"Odpływamy do {dest}...","NL":"Op weg naar {dest}...","SV":"Seglar mot {dest}...","JA":"{dest}へ出航...","ZH":"启航前往{dest}...","KO":"{dest}으로 항해 중...","AR":"إبحار نحو {dest}...","TR":"{dest}'e yelken açılıyor...","CS":"Plujeme do {dest}...","HU":"Vitorlázunk {dest} felé...","RO":"Navigând spre {dest}...","FI":"Purjehtimassa kohti {dest}...","NO":"Seiler mot {dest}..."},
    "ship.arrived":     {"EN":"Arrived at {dest} by ship!","DE":"Per Schiff in {dest} angekommen!","FR":"Arrivé à {dest} par bateau!","ES":"¡Llegaste a {dest} en barco!","PT":"Chegou a {dest} de navio!","IT":"Arrivato a {dest} in nave!","RU":"Прибыли в {dest} на корабле!","PL":"Dotarłeś do {dest} statkiem!","NL":"Aangekomen in {dest} per schip!","SV":"Anlänt till {dest} med skepp!","JA":"船で{dest}に到着した！","ZH":"乘船到达{dest}！","KO":"배로 {dest}에 도착했습니다!","AR":"وصلت إلى {dest} بالسفينة!","TR":"Gemiyle {dest}'e ulaştın!","CS":"Přijel jsi do {dest} lodí!","HU":"Megérkeztél {dest}-ba hajóval!","RO":"Ai ajuns la {dest} cu corabia!","FI":"Saavuit paikkaan {dest} laivalla!","NO":"Ankom {dest} med skip!"},
    "ship.storm":       {"EN":"STORM! {dmg} damage, {gold} gold lost!","DE":"STURM! {dmg} Schaden, {gold} Gold verloren!","FR":"TEMPÊTE! {dmg} dégâts, {gold} or perdu!","ES":"¡TORMENTA! ¡{dmg} de daño, {gold} de oro perdido!","PT":"TEMPESTADE! {dmg} de dano, {gold} ouro perdido!","IT":"TEMPESTA! {dmg} danni, {gold} oro perso!","RU":"ШТОРМ! {dmg} урона, {gold} золота потеряно!","PL":"BURZA! {dmg} obrażeń, {gold} złota stracone!","NL":"STORM! {dmg} schade, {gold} goud verloren!","SV":"STORM! {dmg} skada, {gold} guld förlorat!","JA":"嵐！{dmg}ダメージ、{gold}Gを失った！","ZH":"风暴！损失{dmg}HP和{gold}金币！","KO":"폭풍! {dmg} 데미지, {gold} 골드 손실!","AR":"عاصفة! ضرر {dmg}، فقدت {gold} ذهباً!","TR":"FIRTINA! {dmg} hasar, {gold} altın kayboldu!","CS":"BOUŘE! {dmg} zranění, {gold} zlata ztraceno!","HU":"VIHAR! {dmg} sebzés, {gold} arany elveszett!","RO":"FURTUNĂ! {dmg} daune, {gold} aur pierdut!","FI":"MYRSKY! {dmg} vahinkoa, {gold} kultaa menetettiin!","NO":"STORM! {dmg} skade, {gold} gull mistet!"},
    "ship.fair_winds":  {"EN":"Fair winds! The voyage is smooth.","DE":"Guter Wind! Die Reise verläuft ruhig.","FR":"Vent favorable! La traversée est douce.","ES":"¡Vientos favorables! El viaje es tranquilo.","PT":"Ventos favoráveis! A viagem é tranquila.","IT":"Venti favorevoli! Il viaggio è tranquillo.","RU":"Попутный ветер! Плавание спокойное.","PL":"Pomyślny wiatr! Podróż jest spokojna.","NL":"Gunstige wind! De reis is rustig.","SV":"Goda vindar! Resan är lugn.","JA":"順風！航海は穏やかだ。","ZH":"顺风！航行一帆风顺。","KO":"순풍! 항해가 순조롭습니다.","AR":"رياح مواتية! الرحلة سلسة.","TR":"Uygun rüzgar! Yolculuk pürüzsüz.","CS":"Příznivý vítr! Plavba je klidná.","HU":"Kedvező szelek! Az utazás sima.","RO":"Vânturi bune! Călătoria e liniștită.","FI":"Suotuisa tuuli! Matka on sujuva.","NO":"God vind! Reisen er rolig."},
}

# Assign to module-level STRINGS
STRINGS = _S


# ── Language picker screen ──────────────────────────────────────
def pick_language_screen():
    """Full-screen language selector. Returns chosen language code."""
    import shutil
    from game_term import clr
    clr()
    # Use C() from game_term for proper centring
    try:
        from game_term import C as _C
    except ImportError:
        cols = shutil.get_terminal_size((120,36)).columns
        pad = " " * max(0, (cols - min(cols, 120)) // 2)
        _C = lambda s: pad + s

    print(_C(f"\n{_GOLD}{_B}══════════════════════════════════════════════════{_R}"))
    print(_C(f"{_GOLD}{_B}   {T('lang.title')}  {_R}"))
    print(_C(f"{_GOLD}{_B}══════════════════════════════════════════════════{_R}\n"))

    codes = LANG_ORDER
    # Build grid rows: 2 columns, each entry ~32 chars wide
    # Print each entry on its own line, centred — avoids padding accumulation
    col_w = 2  # 2 columns
    rows_needed = (len(codes) + col_w - 1) // col_w
    for row in range(rows_needed):
        line_parts = []
        for col in range(col_w):
            idx = row + col * rows_needed
            if idx >= len(codes):
                line_parts.append(" " * 32)
                continue
            code = codes[idx]
            name = LANGUAGE_NAMES[code]
            mark = f" {_GREEN}✓{_R}" if code==LANG else "  "
            entry = f"{_GOLD}{_B}[{idx+1:>2}]{_R} {_WHITE}{code}{_R}  {name:<12}{mark}"
            line_parts.append(entry)
        print(_C("    ".join(line_parts)))
    print()

    print(_C(f"\n{_GOLD}[0]{_R} {_DIM}Keep current ({LANGUAGE_NAMES.get(LANG,'?')}){_R}\n"))
    ch = input(_C(f"{_GOLD}> {_R}")).strip()
    if ch == "0" or not ch.isdigit():
        return LANG
    idx = int(ch)-1
    if 0 <= idx < len(codes):
        chosen = codes[idx]
        set_language(chosen)
        print(_C(f"\n{_GREEN}{T('lang.saved', lang=LANGUAGE_NAMES[chosen])}{_R}"))
        input(_C(f"\n{_DIM}{T('ui.press_enter')}{_R}"))
        return chosen
    return LANG


_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang.cfg")

def save_language_pref(filename=_CFG_PATH):
    """Persist language choice across sessions."""
    try:
        with open(filename,"w",encoding="utf-8") as f: f.write(LANG)
    except Exception:
        pass


def load_language_pref(filename=_CFG_PATH):
    """Load saved language on startup."""
    try:
        with open(filename,encoding="utf-8") as f:
            code = f.read().strip()
            if code in LANGUAGE_NAMES:
                set_language(code)
    except Exception:
        pass
