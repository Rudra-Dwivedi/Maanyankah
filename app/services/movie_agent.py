"""
Media & Cultural Intelligence Agent for Maanyankah (मान्यांकः).
Agent Name: चित्राङ्कः (Chitrankah)

Provides deep-dive descriptions, narrative/lyrical themes, artistic craft,
production trivia, and real community rating & sentiment distributions for
both MOVIES and SONGS in the Maanyankah catalog.
"""

import json
import re
import os
from flask import g
from app.db import get_db
from app.services.item_media import resolve_image_url
from app.services.settings_store import get_setting

# ---------------------------------------------------------------------------
# Comprehensive Knowledge Base for Movies
# ---------------------------------------------------------------------------
MOVIE_KNOWLEDGE_BASE = {
    "inception": {
        "director": "Christopher Nolan",
        "cast": "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page, Tom Hardy, Marion Cotillard, Cillian Murphy",
        "year": "2010",
        "runtime": "148 mins",
        "genres": ["Sci-Fi", "Action", "Psychological Thriller"],
        "synopsis": (
            "Dom Cobb is an elite extractor who steals valuable corporate secrets by infiltrating "
            "the subconscious minds of targets during the vulnerable dream state. Haunted by the memory "
            "of his deceased wife Mal, Cobb is offered an unprecedented deal by corporate titan Saito: "
            "in exchange for wiping his criminal record and reuniting him with his children, Cobb must perform "
            "'inception'—planting an idea into the mind of a rival CEO heir. Cobb assembles an elite squad across "
            "three recursive dream levels where the laws of physics bend and time dilates exponentially."
        ),
        "themes": "The architecture of memory, grief and unresolved guilt, the subjective boundary of reality, temporal dilation, and corporate manipulation.",
        "cinematic_craft": (
            "Shot with revolutionary practical sets by Chris Corbould (including a massive 100-foot rotating centrifuge "
            "hotel corridor for zero-gravity combat), paired with Wally Pfister's pristine cinematography and Hans Zimmer's "
            "iconic brass-driven score, famously built around extreme tempo-slowed brass motifs from Édith Piaf."
        ),
        "why_watch": "A rare modern sci-fi masterwork that unites labyrinthine intellectual storytelling with visceral blockbuster spectacle and emotional resonance.",
        "verdict": "Won 4 Academy Awards (Cinematography, Sound Editing, Sound Mixing, Visual Effects) and stands as one of the 21st century's defining cinema achievements.",
    },
    "the dark knight": {
        "director": "Christopher Nolan",
        "cast": "Christian Bale, Heath Ledger, Aaron Eckhart, Michael Caine, Gary Oldman, Morgan Freeman",
        "year": "2008",
        "runtime": "152 mins",
        "genres": ["Action", "Crime", "Neo-Noir Drama"],
        "synopsis": (
            "With the alliance of Lieutenant Jim Gordon and newly elected, crusading District Attorney Harvey Dent, "
            "Batman has tightened the grip on organized crime syndicates across Gotham City. However, the triumvirate "
            "is suddenly thrown into catastrophic disarray by the arrival of the Joker—a sadistic, anarchist criminal mastermind "
            "who seeks to plunge Gotham into moral nihilism. The Joker forces Batman, Dent, and Gotham's populace into devastating "
            "ethical dilemmas designed to prove that even the most noble souls can be corrupted by fear."
        ),
        "themes": "The fragile facade of social order, moral escalation, utilitarian ethics vs deontological justice, the cost of heroism, and the corrupting power of tragedy.",
        "cinematic_craft": (
            "Pioneered the use of 70mm IMAX cameras for mainstream theatrical filmmaking, capturing Chicago's towering architecture "
            "with gritty grandeur. Anchored by Heath Ledger's legendary, terrifyingly unpredictable Oscar-winning performance as the Joker."
        ),
        "why_watch": "Elevated the comic-book film into a profound, Shakespearean crime drama that forever reshaped modern cinema's approach to psychological villains.",
        "verdict": "Recipient of 2 Academy Awards; consistently ranked among the greatest motion pictures ever produced in world cinema history.",
    },
    "interstellar": {
        "director": "Christopher Nolan",
        "cast": "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine, Mackenzie Foy, Matt Damon",
        "year": "2014",
        "runtime": "169 mins",
        "genres": ["Sci-Fi", "Adventure", "Cosmic Drama"],
        "synopsis": (
            "In the mid-21st century, catastrophic blight and severe dust storms threaten human civilization with planetary starvation. "
            "Joseph Cooper, a widowed former NASA test pilot turned dust-bowl farmer, discovers gravitational anomalies that guide him to "
            "a secret underground NASA research outpost. Cooper is recruited for 'Project Lazarus'—a desperate voyage aboard the Endurance "
            "through a mysterious wormhole near Saturn to survey three candidate habitable worlds. To save humanity, Cooper must leave his beloved "
            "children behind, navigating relativistic time dilation where one hour on an ocean world equates to seven years on Earth."
        ),
        "themes": "Love as a quantifiable multi-dimensional force, the relentless arrow of relativistic time, parental sacrifice, environmental stewardship, and survivalism.",
        "cinematic_craft": (
            "Created in direct collaboration with Nobel laureate theoretical physicist Kip Thorne to generate physically accurate models "
            "of gravitational lensing and black hole accretion disks (Gargantua). Features Hans Zimmer's sublime, soul-shaking church organ score "
            "recorded at London's historic Temple Church."
        ),
        "why_watch": "A staggering cinematic journey that combines mind-expanding astrophysics with one of the most tear-inducing father-daughter relationships ever committed to film.",
        "verdict": "Won the Academy Award for Best Visual Effects; celebrated globally as a modern philosophical space odyssey akin to 2001: A Space Odyssey.",
    },
    "parasite": {
        "director": "Bong Joon-ho",
        "cast": "Song Kang-ho, Lee Sun-kyun, Cho Yeo-jeong, Choi Woo-shik, Park So-dam, Lee Jung-eun",
        "year": "2019",
        "runtime": "132 mins",
        "genres": ["Black Comedy", "Psychological Thriller", "Social Drama"],
        "synopsis": (
            "The destitute Kim family lives in a subterranean, damp semi-basement apartment in Seoul, scraping together a living by folding "
            "pizza boxes. When son Ki-woo is recommended to tutor the daughter of the ultra-wealthy Park family, the Kims hatch a calculated scheme: "
            "one by one, posing as sophisticated, unrelated experts (art therapist, chauffeur, master housekeeper), they infiltrate the luxurious Park "
            "household. However, when an unexpected dark secret hidden deep inside the mansion's subterranean fallout shelter is unearthed, the delicate "
            "symbiosis collapses into chaos."
        ),
        "themes": "Systemic wealth inequality, capitalist parasitism versus coexistence, societal class contempt (the 'smell of the subway'), and the tragedy of generational poverty.",
        "cinematic_craft": (
            "Masterful spatial storytelling contrasting the high, sunlit, architectural hilltops of the wealthy with the flooded, subterranean gutters "
            "of the poor. Bong Joon-ho's razor-sharp script transitions flawlessly from laugh-out-loud satire to heart-pounding suspense."
        ),
        "why_watch": "A thrilling roller coaster with brilliant visual pacing, shocking revelations, and a universal message that resonated with audiences across the globe.",
        "verdict": "Historic 4-time Oscar winner (including Best Picture, Best Director, and Best Original Screenplay); the first non-English-language Best Picture winner in Oscar history.",
    },
    "la la land": {
        "director": "Damien Chazelle",
        "cast": "Ryan Gosling, Emma Stone, John Legend, J.K. Simmons, Rosemarie DeWitt",
        "year": "2016",
        "runtime": "128 mins",
        "genres": ["Musical", "Romantic Drama", "Comedy"],
        "synopsis": (
            "Amidst the bustling, sun-bleached hustle of modern Los Angeles, two ambitious artists cross paths: Sebastian, a stubbornly traditional "
            "jazz pianist dreaming of opening his own club, and Mia, an aspiring actress enduring demoralizing audition rejections. They fall deeply in love, "
            "inspiring and sustaining each other through creative droughts. But as Sebastian joins a commercially successful pop-funk band and Mia writes her own "
            "one-woman play, their burgeoning successes drive them toward an agonizing choice between romantic commitment and lifelong creative fulfillment."
        ),
        "themes": "Artistic integrity vs commercial compromise, passion and sacrifice, serendipity in romance, nostalgia vs forward momentum, and the bittersweet beauty of paths not taken.",
        "cinematic_craft": (
            "Filmed in glorious CinemaScope with luminous, saturated primary colors and sweeping long-take choreography (from the freeway-spanning 'Another Day of Sun' "
            "to the Griffith Observatory waltz). Accompanied by Justin Hurwitz's timeless, haunting piano masterpiece 'City of Stars'."
        ),
        "why_watch": "An intoxicating, visually breathtaking homage to classic MGM and Jacques Demy musicals that grounds its spectacle in genuine modern human heartbreak.",
        "verdict": "Won 6 Academy Awards, including Best Director (making Damien Chazelle the youngest winner at age 32) and Best Actress for Emma Stone.",
    },
    "the grand budapest hotel": {
        "director": "Wes Anderson",
        "cast": "Ralph Fiennes, Tony Revolori, Saoirse Ronan, Willem Dafoe, Jeff Goldblum, Adrien Brody, Tilda Swinton",
        "year": "2014",
        "runtime": "99 mins",
        "genres": ["Comedy", "Adventure", "Capar / Period Drama"],
        "synopsis": (
            "Set in the fictional, idyllic European republic of Zubrowka between the world wars, Monsieur Gustave H. is the legendary, dapper, "
            "and utterly devoted concierge of the mountainside luxury Grand Budapest Hotel. When Madame D., an eccentric wealthy lover of Gustave, dies "
            "under mysterious circumstances and leaves him an invaluable Renaissance painting ('Boy with Apple'), her ruthless fascist heir frames Gustave for murder. "
            "With the steadfast assistance of his newly hired lobby boy and trusted confidant, Zero Moustafa, Gustave embarks on a whimsical, fast-paced escape."
        ),
        "themes": "The preservation of civility and grace in an encroaching world of fascism, intergenerational camaraderie, European nostalgia, and memory through storytelling.",
        "cinematic_craft": (
            "Shot across three distinct aspect ratios (1.37:1 Academy, 1.85:1 standard, and 2.35:1 widescreen) to visually reflect distinct historical eras. "
            "Packed with Anderson's hallmark symmetrical dollhouse framing, pastel pastry aesthetics, and Alexandre Desplat's energetic balalaika-infused score."
        ),
        "why_watch": "Ralph Fiennes delivers one of the most delightful, witty, and charming performances in recent comedy history within an impeccably constructed visual world.",
        "verdict": "Won 4 Academy Awards (Costume Design, Makeup/Hairstyling, Production Design, Original Score); universally beloved for its literary warmth.",
    },
    "pulp fiction": {
        "director": "Quentin Tarantino",
        "cast": "John Travolta, Samuel L. Jackson, Uma Thurman, Bruce Willis, Ving Rhames, Harvey Keitel, Christopher Walken",
        "year": "1994",
        "runtime": "154 mins",
        "genres": ["Crime", "Neo-Noir", "Black Comedy"],
        "synopsis": (
            "In the neon-drenched criminal underbelly of Los Angeles, four wildly disparate stories intersect in an inventive, non-chronological timeline: "
            "two hitmen with a penchant for philosophical banter (Vincent Vega and Jules Winnfield) tasked with retrieving a mysterious glowing briefcase; "
            "their powerful mob boss Marsellus Wallace whose glamorous wife Mia endures a perilous overdose; a proud aging boxer (Butch Coolidge) who double-crosses "
            "the mob on a fixed match; and a pair of romantic diner bandits (Pumpkin and Honey Bunny) who stage an ill-fated armed robbery."
        ),
        "themes": "Redemption and divine intervention, honor among criminals, pop culture mythology, non-linear destiny, and the capricious nature of fate.",
        "cinematic_craft": (
            "Forever changed American independent cinema through its non-linear circular screenplay, crackling musical soundtrack of forgotten 60s/70s surf rock "
            "and soul, rapid-fire pop culture dialogue, and iconic dance sequence at Jack Rabbit Slim's."
        ),
        "why_watch": "A kinetic, effortlessly cool masterpiece that redefined the vocabulary of modern screenwriting and cinematic cool.",
        "verdict": "Won the prestigious Palme d'Or at Cannes and the Academy Award for Best Original Screenplay; inducted into the National Film Registry.",
    },
    "whiplash": {
        "director": "Damien Chazelle",
        "cast": "Miles Teller, J.K. Simmons, Paul Reiser, Melissa Benoist, Austin Stowell",
        "year": "2014",
        "runtime": "107 mins",
        "genres": ["Psychological Drama", "Music Thriller"],
        "synopsis": (
            "Andrew Neiman is an ambitious 19-year-old jazz student at the prestigious Shaffer Conservatory of Music in New York, hungry to achieve musical immortality "
            "in the vein of Buddy Rich. He is recruited into the conservatory's premier competition jazz orchestra by the notorious Terence Fletcher. Fletcher utilizes "
            "ruthless psychological manipulation, verbal cruelty, and flying drum stools to drive his pupils beyond their human limits. As the tempo accelerates, "
            "Andrew descends into monomaniacal obsession, sacrificing his family, romance, and sanity to earn the ruthless maestro's nod of approval."
        ),
        "themes": "The agonizing price of creative genius, mentorship versus abusive megalomania, destructive perfectionism, and the myth of unconditional approval.",
        "cinematic_craft": (
            "Edited by Tom Cross with the visceral rhythm of a high-speed action thriller. Drum solos are shot like combat sequences with flying sweat, splattering blood, "
            "and snapping drumsticks, culminating in a jaw-dropping, heart-stopping 9-minute wordless finale on the Carnegie Hall stage."
        ),
        "why_watch": "An electrifying psychological duel featuring career-best performances from both Miles Teller and an intimidating, Oscar-winning J.K. Simmons.",
        "verdict": "Won 3 Academy Awards (Best Supporting Actor, Best Film Editing, Best Sound Mixing); widely hailed as one of the greatest films ever made about musical dedication.",
    },
}

# ---------------------------------------------------------------------------
# Comprehensive Knowledge Base for Songs
# ---------------------------------------------------------------------------
SONG_KNOWLEDGE_BASE = {
    "blinding lights": {
        "artist": "The Weeknd (Abel Tesfaye)",
        "album": "After Hours",
        "year": "2019",
        "genres": ["Synthwave", "80s Pop", "Electropop"],
        "bpm_vibe": "171 BPM • High-energy retro synthwave overdrive with nocturnal melancholia",
        "lyrical_meaning": (
            "Depicts the desperate delirium of speeding through neon-soaked Las Vegas streets in the dead of night, "
            "experiencing emotional withdrawal while intoxicated, and realizing that only the presence of a lost lover can cure "
            "his internal void. The 'blinding lights' symbolize both the disorienting glare of fame and the clarity of raw romantic longing."
        ),
        "sonic_architecture": (
            "Engineered and co-written with Swedish pop mastermind Max Martin and Oscar Holter. Built upon an infectious, propulsive "
            "analog synthesizer hook, gated-reverb 80s drum machine patterns, and Abel Tesfaye's piercing, emotive tenor falsetto "
            "reminiscent of Michael Jackson and vintage new wave acts like A-ha."
        ),
        "accolades": "Officially crowned by Billboard as the #1 Greatest Hot 100 Hit of All Time, spending a historic 90 weeks on the chart and surpassing 4.3 billion streams on Spotify.",
        "why_listen": "An undisputed pop masterclass that kickstarted the worldwide synthwave renaissance; delivering irresistible kinetic energy that never grows stale.",
        "verdict": "A modern pop classic that seamlessly bridges 1980s nostalgia with cutting-edge 21st-century production.",
    },
    "humble.": {
        "artist": "Kendrick Lamar",
        "album": "DAMN.",
        "year": "2017",
        "genres": ["Hip-Hop", "Hardcore Rap", "Trap"],
        "bpm_vibe": "150 BPM • Menacing, minimalist 808 stomp with razor-sharp rhythmic precision",
        "lyrical_meaning": (
            "Kendrick turns a critical gaze both outward toward his rap competitors and inward at his own soaring ego. "
            "He rejects filtered Photoshop superficiality in favor of natural beauty, calls out industry deceit, and ironizes his own messianic status "
            "in modern culture with the hypnotic refrain: 'Be humble, sit down.'"
        ),
        "sonic_architecture": (
            "Produced by Mike WiLL Made-It with a sinister, sparse piano riff over thunderous 808 bass slides and cracking snare hits. "
            "Kendrick delivers his bars with aggressive, staccato cadence shifts, showcasing unmatched breath control and lyrical phrasing."
        ),
        "accolades": "Won 3 Grammy Awards (Best Rap Performance, Best Rap Song, Best Music Video). DAMN. made history by becoming the first non-classical, non-jazz work to win the Pulitzer Prize for Music.",
        "why_listen": "An electrifying hip-hop anthem that proves elite philosophical lyricism and massive club bangers can coexist without compromise.",
        "verdict": "A generational rap milestone celebrated for its iconic Dave Meyers visual direction and cultural resonance.",
    },
    "bohemian rhapsody": {
        "artist": "Queen (Freddie Mercury)",
        "album": "A Night at the Opera",
        "year": "1975",
        "genres": ["Progressive Rock", "Opera Rock", "Hard Rock"],
        "bpm_vibe": "Multi-tempo suite • From tender ballad (72 BPM) to frantic operatic whirlpool (144 BPM) to roaring hard rock",
        "lyrical_meaning": (
            "A surrealist, Faustian drama of a tormented young protagonist who confesses a murder to his mother ('Mama, just killed a man'), "
            "faces condemnation by religious and demonic inquisitors (Scaramouche, Galileo, Beelzebub), and ultimately submits to nihilistic resignation "
            "in the haunting coda: 'Nothing really matters to me, any way the wind blows.'"
        ),
        "sonic_architecture": (
            "Constructed in six distinct movements without a conventional pop chorus: A cappella intro, piano ballad, Brian May’s legendary guitar solo, "
            "a multi-layered operatic choir (comprising over 180 vocal overdubs that wore the analog tapes nearly transparent), an explosive hard rock section, "
            "and an introspective outro sealed with a gentle gong strike."
        ),
        "accolades": "Inducted into the Grammy Hall of Fame; certified Diamond by the RIAA; universally ranked among the greatest recorded songs in human musical history.",
        "why_listen": "A transcendent monument to artistic courage that shattered all radio conventions and showcased Freddie Mercury's peerless vocal genius.",
        "verdict": "Consistently voted the greatest rock composition of all time, uniting classical opera and arena rock into pure sonic magic.",
    },
    "starboy": {
        "artist": "The Weeknd ft. Daft Punk",
        "album": "Starboy",
        "year": "2016",
        "genres": ["R&B", "Electropop", "Synth-pop"],
        "bpm_vibe": "93 BPM • Sleek, confident nocturnal bounce with robotic electro sheen",
        "lyrical_meaning": (
            "Documents Abel Tesfaye's dramatic artistic rebirth—symbolically destroying his past tormented persona to embrace the swagger, "
            "unapologetic luxury, and perils of global superstardom. He flaunts exotic supercars ('P1 cleaner than your church shoes') while subtly acknowledging "
            "the predatory, corrupting nature of the celebrity machine."
        ),
        "sonic_architecture": (
            "Crafted in Paris by legendary electronic duo Daft Punk. Layers crisp electronic drum claps, pulsing analog Moog basslines, "
            "and signature Daft Punk robotic vocoder backing harmonies underneath Tesfaye's silky, effortless melodies."
        ),
        "accolades": "Topped the Billboard Hot 100 globally, certified Diamond in multiple territories, and stands as one of Daft Punk's final legendary co-productions before their retirement.",
        "why_listen": "The quintessential nocturnal cruising track that delivers effortless swagger and French Touch electronic polish.",
        "verdict": "A watershed crossover hit that cemented The Weeknd's reign atop the pop and R&B pantheon.",
    },
    "lose yourself": {
        "artist": "Eminem (Marshall Mathers)",
        "album": "8 Mile (Music from and Inspired by the Motion Picture)",
        "year": "2002",
        "genres": ["Hip-Hop", "Midwest Rap", "Hardcore Rap"],
        "bpm_vibe": "86 BPM • Tense, escalating rock-rap march with raw adrenaline and unstoppable momentum",
        "lyrical_meaning": (
            "Written in character as Jimmy 'B-Rabbit' Smith Jr. from the movie 8 Mile. Captures the agonizing dread of poverty, stage fright "
            "('palms are sweaty, knees weak, arms are heavy... mom's spaghetti'), and the life-defining urgency of seizing your one fleeting moment of destiny "
            "when surrender means starvation and failure."
        ),
        "sonic_architecture": (
            "Composed and recorded by Eminem in a portable trailer between takes on the 8 Mile film set. Features a tense, clean electric guitar ostinato, "
            "building piano chords, a relentless marching snare drum, and dense multi-syllabic rhyme schemes delivered with breathless, fierce conviction."
        ),
        "accolades": "The first rap song ever to win the Academy Award for Best Original Song. Also won 2 Grammy Awards, spent 12 weeks at #1 on the Hot 100, and is certified Diamond.",
        "why_listen": "Universally recognized as the most powerful motivational anthem ever recorded across any musical genre.",
        "verdict": "An unassailable masterpiece of rhythm, narrative urgency, and poetic rhyme density.",
    },
    "hotel california": {
        "artist": "Eagles (Don Henley, Glenn Frey, Don Felder)",
        "album": "Hotel California",
        "year": "1976",
        "genres": ["Classic Rock", "Soft Rock", "Folk Rock"],
        "bpm_vibe": "75 BPM • Hypnotic reggae-tinged Spanish rock groove culminating in an iconic guitar counterpoint duel",
        "lyrical_meaning": (
            "An allegorical dark fable of a weary traveler stranded at a deceptive desert oasis that turns into a gilded prison ('You can check out any time you like, but you can never leave'). "
            "Serves as a haunting critique of 1970s Southern California decadence, consumerist greed, and the disillusionment following the death of 1960s idealistic counterculture."
        ),
        "sonic_architecture": (
            "Opens with Don Felder’s signature 12-string acoustic guitar arpeggios, features Don Henley's rasping, world-weary lead vocal and steady drumming, "
            "and peaks in an unforgettable 2-minute harmonized guitar battle between Don Felder and Joe Walsh that is universally studied by musicians."
        ),
        "accolades": "Won the Grammy Award for Record of the Year; inducted into the Rock and Roll Hall of Fame; ranked among Rolling Stone's 500 Greatest Songs of All Time.",
        "why_listen": "Exquisite songwriting, timeless lyrical storytelling, and the gold standard of rock dual-guitar arrangements.",
        "verdict": "A legendary pillar of American music that remains just as mysterious and captivating half a century later.",
    },
    "get lucky": {
        "artist": "Daft Punk ft. Pharrell Williams & Nile Rodgers",
        "album": "Random Access Memories",
        "year": "2013",
        "genres": ["Disco", "Funk", "Dance-pop"],
        "bpm_vibe": "116 BPM • Warm, organic disco-funk bounce radiating pure sunshine and human connection",
        "lyrical_meaning": (
            "A celebration of romantic chemistry, serendipity, and the joy of dancing until dawn. The phrase 'get lucky' plays on both romantic spark "
            "and the sheer fortune of experiencing a magical night in good company."
        ),
        "sonic_architecture": (
            "A deliberate rejection of cold digital software synths in favor of warm, live analog recording gear. Driven by Chic icon Nile Rodgers' legendary "
            "'Hitmaker' Fender Stratocaster funk rhythm guitar, Pharrell Williams' silky falsetto, and Daft Punk's robotic talkbox vocal harmonies over Omar Hakim’s live drums."
        ),
        "accolades": "Swept the 56th Grammy Awards, winning Record of the Year and Best Pop Duo/Group Performance; sold over 9 million copies and became the definitive anthem of 2013.",
        "why_listen": "Pure, unadulterated musical joy and impeccable rhythmic craftsmanship that makes sitting still virtually impossible.",
        "verdict": "The golden triumph of 21st-century disco that proved live human musicianship will never be replaced by algorithms.",
    },
    "levitating": {
        "artist": "Dua Lipa",
        "album": "Future Nostalgia",
        "year": "2020",
        "genres": ["Nu-Disco", "Dance-pop", "Pop-funk"],
        "bpm_vibe": "103 BPM • Buoyant, roller-disco space-pop groove with infectious clap-along energy",
        "lyrical_meaning": (
            "A joyful, buoyant tribute to exhilarating romantic infatuation so intense and intoxicating it makes you feel like you are floating weightless "
            "across the cosmos among the stars."
        ),
        "sonic_architecture": (
            "Co-written with Clarence Coffee Jr. and Koz. Driven by an irresistible roller-disco bassline, analog Roland synth chords, talkbox textures, "
            "handclaps, and Dua Lipa’s rich, commanding alto vocal delivery that evokes vintage Studio 54 glamour."
        ),
        "accolades": "The #1 Billboard Hot 100 Song of the Year for 2021, spending 77 weeks on the chart and breaking records as the longest-charting song by a female artist in history.",
        "why_listen": "Flawless modern dance-pop songwriting executed with supreme style, swagger, and vibrant positivity.",
        "verdict": "The shining centerpiece of the 2020s disco-pop revival.",
    },
    "as it was": {
        "artist": "Harry Styles",
        "album": "Harry's House",
        "year": "2022",
        "genres": ["Synth-pop", "Indie Pop", "New Wave"],
        "bpm_vibe": "174 BPM • Double-time indie-pop synth gallop disguising poignant emotional solitude",
        "lyrical_meaning": (
            "A bittersweet, introspective look at personal transformation, loneliness, drifting away from past relationships, and the bittersweet acceptance "
            "that childhood innocence and departed connections will never be 'as it was'."
        ),
        "sonic_architecture": (
            "Co-produced with Kid Harpoon and Tyler Johnson. Starts with an endearing voice memo from Styles' goddaughter, followed by a sparkling "
            "80s-inspired synthesizer riff, brisk four-on-the-floor drumming, and Harry’s intimate, melancholic vocal phrasing, punctuated by celebratory church bells."
        ),
        "accolades": "Spent an extraordinary 15 weeks at #1 on the Billboard Hot 100 and set the Guinness World Record for the most streamed track on Spotify in 24 hours by a male artist.",
        "why_listen": "The rare mainstream pop single that marries an infectious, danceable indie bounce with poignant emotional honesty.",
        "verdict": "A generational pop benchmark that established Harry Styles as an artist of remarkable melodic range and lyrical maturity.",
    },
}

# ---------------------------------------------------------------------------
# Statistics and Rating Aggregation
# ---------------------------------------------------------------------------
def get_item_stats(db, item_id):
    """Compute detailed rating statistics, star breakdowns, and review sentiment for any item."""
    ratings = db.execute(
        """
        SELECT p.rating, u.username, u.avatar_url
        FROM user_preferences p
        JOIN users u ON p.user_id = u.id
        WHERE p.item_id = ?
        ORDER BY p.created_at DESC
        """,
        (item_id,),
    ).fetchall()

    total_ratings = len(ratings)
    avg_rating = round(sum(r["rating"] for r in ratings) / total_ratings, 1) if total_ratings > 0 else 0.0

    breakdown = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in ratings:
        breakdown[r["rating"]] = breakdown.get(r["rating"], 0) + 1

    pct_breakdown = {}
    for star in range(5, 0, -1):
        pct = round((breakdown[star] / total_ratings * 100), 1) if total_ratings > 0 else 0
        pct_breakdown[star] = {"count": breakdown[star], "pct": pct}

    posts = db.execute(
        """
        SELECT posts.content, posts.sentiment_score, posts.created_at, users.username, users.avatar_url
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.item_id = ?
        ORDER BY posts.created_at DESC
        LIMIT 6
        """,
        (item_id,),
    ).fetchall()

    positive_posts = sum(1 for p in posts if p["sentiment_score"] > 0.15)
    negative_posts = sum(1 for p in posts if p["sentiment_score"] < -0.15)
    neutral_posts = len(posts) - (positive_posts + negative_posts)

    if total_ratings == 0 and len(posts) == 0:
        sentiment_summary = "No ratings or community reviews logged yet on Maanyankah."
    elif avg_rating >= 4.5:
        sentiment_summary = "🔥 Overwhelmingly Revered — certified masterpiece consensus on Maanyankah!"
    elif avg_rating >= 3.8:
        sentiment_summary = "✨ Positively Received — widespread acclaim and admiration among members."
    elif avg_rating >= 2.8:
        sentiment_summary = "⚖️ Mixed Impressions — opinions are divided across the audience."
    else:
        sentiment_summary = "Critical reception — members have voiced reservations."

    return {
        "avg_rating": avg_rating,
        "rating_count": total_ratings,
        "breakdown": pct_breakdown,
        "recent_raters": [{"username": r["username"], "rating": r["rating"]} for r in ratings[:4]],
        "posts": [dict(p) for p in posts],
        "sentiment_summary": sentiment_summary,
        "sentiment_counts": {
            "positive": positive_posts,
            "neutral": neutral_posts,
            "negative": negative_posts,
        },
    }

# Backward compatibility alias
get_movie_stats = get_item_stats


# ---------------------------------------------------------------------------
# Search and Matching Engine
# ---------------------------------------------------------------------------
def normalize_text(text):
    """Clean text for robust matching."""
    t = text.lower().strip()
    t = re.sub(r"[—–•\-]", " ", t)
    return " ".join(t.split())


def find_items_by_keyword(db, query):
    """Find catalog movies or songs matching a query string by title, track, or artist."""
    q_norm = query.strip().lower()
    
    # Strip common conversational query prefixes
    prefixes = [
        "tell me about", "what is the rating of", "what is the rating for",
        "what is", "what are", "ratings for", "rating of", "how good is",
        "details on", "tell about", "explain", "breakdown of", "who is",
        "information on", "song details for", "movie details for", "give me info on",
        "what do you know about"
    ]
    for prefix in prefixes:
        if q_norm.startswith(prefix):
            q_norm = q_norm[len(prefix):].strip()
            break

    q_clean = normalize_text(q_norm)
    all_items = db.execute("SELECT * FROM items ORDER BY id ASC").fetchall()

    matched = []
    for item in all_items:
        title_raw = item["title"]
        title_norm = normalize_text(title_raw)

        # Direct match or exact substring
        if q_clean == title_norm or q_clean in title_norm:
            matched.append(item)
            continue

        # Split artist/track if song has separator (e.g., 'Blinding Lights — The Weeknd')
        parts = re.split(r"[—–•\-]", title_raw)
        if len(parts) > 1:
            track_name = normalize_text(parts[0])
            artist_name = normalize_text(parts[1])
            if q_clean in track_name or q_clean in artist_name:
                matched.append(item)
                continue
            if track_name in q_clean or artist_name in q_clean:
                matched.append(item)
                continue

        # Substring match if query is at least 3 characters
        if len(q_clean) >= 3 and (q_clean in title_norm or title_norm in q_clean):
            matched.append(item)

    return matched


def get_top_rated_items(db, item_type=None, limit=6):
    """Return top items of a given type ranked by community average rating."""
    type_clause = "WHERE i.type = ?" if item_type else ""
    params = (item_type, limit) if item_type else (limit,)
    
    sql = f"""
        SELECT i.*, 
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        {type_clause}
        GROUP BY i.id
        ORDER BY avg_rating DESC, rating_count DESC, i.title ASC
        LIMIT ?
    """
    return db.execute(sql, params).fetchall()


# ---------------------------------------------------------------------------
# Main Agent Conversation Engine
# ---------------------------------------------------------------------------
def ask_movie_agent(query):
    """
    Main processing function for Chitrankah (चित्राङ्कः) AI Agent.
    Handles natural language queries, movie & song detailed breakdowns,
    community rating distributions, and recommendations.
    """
    db = get_db()
    clean_q = query.strip()
    lower_q = clean_q.lower()
    norm_q = normalize_text(lower_q)

    # 1. Check for Ranking / Leaderboard Requests
    ranking_triggers = [
        "top rated", "highest rated", "best movies", "best songs", "top movie",
        "top song", "leaderboard", "rankings", "highest rating", "best rated",
        "most popular", "highest score"
    ]
    if any(trigger in lower_q for trigger in ranking_triggers) and not any(k in lower_q for k in MOVIE_KNOWLEDGE_BASE) and not any(k in lower_q for k in SONG_KNOWLEDGE_BASE):
        is_song_rank = any(w in lower_q for w in ["song", "music", "track", "tune"])
        target_type = "song" if is_song_rank else "movie"
        top_items = get_top_rated_items(db, item_type=target_type, limit=6)

        items_payload = []
        for m in top_items:
            img = resolve_image_url(m)
            items_payload.append({
                "id": m["id"],
                "type": m["type"],
                "title": m["title"],
                "genres": m["genre_tags"],
                "avg_rating": m["avg_rating"],
                "rating_count": m["rating_count"],
                "image_url": img,
            })

        category_label = "Songs & Music" if target_type == "song" else "Movies & Cinema"
        return {
            "type": "ranking",
            "title": f"🏆 Highest Rated {category_label} on Maanyankah",
            "message": (
                f"Here are the top-rated {category_label.lower()} on Maanyankah based on verified community scores! "
                f"These selections have earned the greatest appreciation among our members:"
            ),
            "movies": items_payload,
            "suggestions": [
                "Tell me about Inception",
                "Tell me about Bohemian Rhapsody",
                "What are the top rated songs?",
                "Recommend a sci-fi thriller"
            ]
        }

    # 2. Check for Specific Movie or Song Direct Lookup
    matched_items = find_items_by_keyword(db, clean_q)
    if matched_items:
        primary_item = matched_items[0]
        item_type = primary_item["type"]
        item_title = primary_item["title"]
        stats = get_item_stats(db, primary_item["id"])
        image_url = resolve_image_url(primary_item)

        # Parse existing metadata JSON
        metadata = {}
        if primary_item["metadata"]:
            try:
                metadata = json.loads(primary_item["metadata"])
            except Exception:
                pass

        # -------------------------------------------------------------
        # Case A: Found a SONG
        # -------------------------------------------------------------
        if item_type == "song":
            # Extract track name and artist from title if separated by dash
            parts = re.split(r"[—–•\-]", item_title)
            raw_track = parts[0].strip() if len(parts) > 1 else item_title
            raw_artist = parts[1].strip() if len(parts) > 1 else metadata.get("artist", "Featured Artist")

            # Check song knowledge base
            kb_key = raw_track.lower().strip()
            kb = SONG_KNOWLEDGE_BASE.get(kb_key)
            if not kb:
                # Try finding in knowledge base via substring
                for k, v in SONG_KNOWLEDGE_BASE.items():
                    if k in kb_key or kb_key in k:
                        kb = v
                        break

            if kb:
                artist = kb["artist"]
                album = kb["album"]
                year = kb["year"]
                genres = kb["genres"]
                bpm_vibe = kb["bpm_vibe"]
                lyrical_meaning = kb["lyrical_meaning"]
                sonic_architecture = kb["sonic_architecture"]
                accolades = kb["accolades"]
                why_listen = kb["why_listen"]
                verdict = kb["verdict"]
            else:
                # Dynamic synthesis for new or uncataloged song
                artist = raw_artist
                album = metadata.get("album", "Original Release")
                year = metadata.get("year", "Contemporary")
                genres = [g.strip().title() for g in (primary_item["genre_tags"] or "Pop,Music").split(",") if g.strip()]
                bpm_vibe = f"Signature {', '.join(genres)} groove featuring distinctive vocal delivery and melodic dynamics."
                lyrical_meaning = f"Explores emotional themes and personal expression characteristic of {artist}'s songwriting."
                sonic_architecture = f"Crafted with modern acoustic and digital instrumentation, polished studio production, and layered harmonies."
                accolades = f"A popular highlight on Maanyankah with {stats['rating_count']} community rating(s)."
                why_listen = f"A standout track in the {', '.join(genres)} genre that showcases {artist}'s signature vocal style."
                verdict = stats["sentiment_summary"]

            song_data = {
                "id": primary_item["id"],
                "title": raw_track,
                "full_title": item_title,
                "artist": artist,
                "album": album,
                "year": year,
                "genres": genres,
                "bpm_vibe": bpm_vibe,
                "lyrical_meaning": lyrical_meaning,
                "sonic_architecture": sonic_architecture,
                "accolades": accolades,
                "why_listen": why_listen,
                "verdict": verdict,
                "image_url": image_url,
                "stats": stats,
            }

            return {
                "type": "song_detail",
                "song": song_data,
                "message": f"Here is an in-depth musical and thematic breakdown of **{raw_track}** by **{artist}**:",
                "suggestions": [
                    f"What is the average rating of {raw_track}?",
                    "What are the highest rated songs on Maanyankah?",
                    f"Recommend music like {raw_track}",
                    "Tell me about Bohemian Rhapsody"
                ]
            }

        # -------------------------------------------------------------
        # Case B: Found a MOVIE
        # -------------------------------------------------------------
        elif item_type == "movie":
            norm_title = item_title.lower().strip()
            kb = MOVIE_KNOWLEDGE_BASE.get(norm_title)
            if not kb:
                for k, v in MOVIE_KNOWLEDGE_BASE.items():
                    if k in norm_title or norm_title in k:
                        kb = v
                        break

            if kb:
                director = kb["director"]
                cast = kb.get("cast", "Acclaimed Ensemble")
                year = kb["year"]
                runtime = kb.get("runtime", "Feature Length")
                genres = kb["genres"]
                synopsis = kb["synopsis"]
                themes = kb["themes"]
                cinematic_craft = kb["cinematic_craft"]
                why_watch = kb["why_watch"]
                verdict = kb["verdict"]
            else:
                # Dynamic synthesis for new or uncataloged movie
                director = metadata.get("director", "Visionary Director")
                cast = metadata.get("cast", "Distinguished Cast")
                year = metadata.get("release_date", "")[:4] or "Modern Classic"
                runtime = metadata.get("runtime", "Feature Film")
                genres = [g.strip().title() for g in (primary_item["genre_tags"] or "Drama,Cinema").split(",") if g.strip()]
                synopsis = metadata.get("overview") or f"{item_title} is a prominent feature film within the Maanyankah catalog."
                themes = f"Explores complex human dynamics, personal ambition, and storytelling within the {', '.join(genres)} genres."
                cinematic_craft = "Exhibits evocative cinematography, thoughtful sound design, and compelling performances."
                why_watch = f"An engaging cinematic experience for fans of {', '.join(genres)}."
                verdict = stats["sentiment_summary"]

            movie_data = {
                "id": primary_item["id"],
                "title": item_title,
                "director": director,
                "cast": cast,
                "year": year,
                "runtime": runtime,
                "genres": genres,
                "synopsis": synopsis,
                "themes": themes,
                "cinematic_craft": cinematic_craft,
                "why_watch": why_watch,
                "verdict": verdict,
                "image_url": image_url,
                "stats": stats,
            }

            return {
                "type": "movie_detail",
                "movie": movie_data,
                "message": f"Here is the comprehensive cinematic analysis for **{item_title}**:",
                "suggestions": [
                    f"What is the average rating of {item_title}?",
                    "What are the top rated movies?",
                    f"Recommend something like {item_title}",
                    "Tell me about Interstellar"
                ]
            }

    # 3. Check for Creator / Director / Artist Inquiries
    creators = {
        "christopher nolan": ("movie", "Christopher Nolan", ["Inception", "The Dark Knight", "Interstellar"]),
        "nolan": ("movie", "Christopher Nolan", ["Inception", "The Dark Knight", "Interstellar"]),
        "damien chazelle": ("movie", "Damien Chazelle", ["La La Land", "Whiplash"]),
        "chazelle": ("movie", "Damien Chazelle", ["La La Land", "Whiplash"]),
        "bong joon ho": ("movie", "Bong Joon-ho", ["Parasite"]),
        "tarantino": ("movie", "Quentin Tarantino", ["Pulp Fiction"]),
        "wes anderson": ("movie", "Wes Anderson", ["The Grand Budapest Hotel"]),
        "the weeknd": ("song", "The Weeknd", ["Blinding Lights", "Starboy"]),
        "weeknd": ("song", "The Weeknd", ["Blinding Lights", "Starboy"]),
        "daft punk": ("song", "Daft Punk", ["Get Lucky", "Starboy"]),
        "queen": ("song", "Queen", ["Bohemian Rhapsody"]),
        "freddie mercury": ("song", "Queen", ["Bohemian Rhapsody"]),
        "eminem": ("song", "Eminem", ["Lose Yourself"]),
        "kendrick lamar": ("song", "Kendrick Lamar", ["HUMBLE."]),
        "kendrick": ("song", "Kendrick Lamar", ["HUMBLE."]),
        "harry styles": ("song", "Harry Styles", ["As It Was"]),
        "dua lipa": ("song", "Dua Lipa", ["Levitating"]),
        "eagles": ("song", "Eagles", ["Hotel California"]),
    }

    for key, (ctype, cname, works) in creators.items():
        if key in norm_q:
            work_items = []
            for w in works:
                m_row = db.execute("SELECT * FROM items WHERE LOWER(title) LIKE ?", (f"%{w.lower()}%",)).fetchone()
                if m_row:
                    work_items.append({
                        "id": m_row["id"],
                        "type": m_row["type"],
                        "title": m_row["title"],
                        "image_url": resolve_image_url(m_row),
                        "genres": m_row["genre_tags"],
                        "stats": get_item_stats(db, m_row["id"]),
                    })

            return {
                "type": "recommendations",
                "title": f"🎨 Spotlighting Works by {cname}",
                "message": (
                    f"**{cname}** is one of the most celebrated artists featured on Maanyankah! "
                    f"Here are their iconic works cataloged with live ratings and reviews:"
                ),
                "movies": work_items,
                "suggestions": [f"Tell me about {w}" for w in works[:3]] + ["What is the highest rated movie?"]
            }

    # 4. Check for Recommendations & Genre Inquiries
    genre_keywords = {
        "sci-fi": ("movie", "Sci-Fi"),
        "scifi": ("movie", "Sci-Fi"),
        "thriller": ("movie", "Thriller"),
        "drama": ("movie", "Drama"),
        "action": ("movie", "Action"),
        "comedy": ("movie", "Comedy"),
        "musical": ("movie", "Musical"),
        "pop": ("song", "Pop"),
        "rock": ("song", "Rock"),
        "hip-hop": ("song", "Hip-Hop"),
        "rap": ("song", "Rap"),
        "synthwave": ("song", "Synthwave"),
        "disco": ("song", "Disco"),
        "funk": ("song", "Funk"),
    }

    found_type = None
    found_genre = None
    for k, (g_type, g_label) in genre_keywords.items():
        if k in norm_q:
            found_type = g_type
            found_genre = g_label
            break

    is_rec = any(k in lower_q for k in ["recommend", "suggest", "what should i", "pick a", "give me a", "good"])
    if is_rec or found_genre:
        target_type = found_type or ("song" if "song" in lower_q or "music" in lower_q else "movie")
        if found_genre:
            sql = "SELECT * FROM items WHERE type = ? AND genre_tags LIKE ? ORDER BY title"
            rows = db.execute(sql, (target_type, f"%{found_genre.lower()}%")).fetchall()
        else:
            sql = "SELECT * FROM items WHERE type = ? ORDER BY RANDOM() LIMIT 4"
            rows = db.execute(sql, (target_type,)).fetchall()

        rec_payload = []
        for item in rows:
            img = resolve_image_url(item)
            stats = get_item_stats(db, item["id"])
            rec_payload.append({
                "id": item["id"],
                "type": item["type"],
                "title": item["title"],
                "genres": item["genre_tags"],
                "avg_rating": stats["avg_rating"],
                "rating_count": stats["rating_count"],
                "image_url": img,
            })

        category_title = f"{found_genre} " if found_genre else ""
        type_word = "Music & Songs" if target_type == "song" else "Films"
        return {
            "type": "recommendations",
            "title": f"✨ Recommended {category_title}{type_word}",
            "message": f"Looking for exceptional {category_title.lower()}{type_word.lower()}? Here are top picks from the Maanyankah catalog with real verified ratings:",
            "movies": rec_payload,
            "suggestions": [
                "Tell me about Inception",
                "Tell me about Bohemian Rhapsody",
                "What is the average rating of Interstellar?",
                "What are the highest rated movies?"
            ]
        }

    # 5. Default Fallback
    return {
        "type": "general",
        "title": "चित्राङ्कः (Chitrankah) — AI Cultural & Media Intelligence",
        "message": (
            "नमस्ते! I am **चित्राङ्कः (Chitrankah)**, your AI intelligence agent for films and music on **मान्यांकः (Maanyankah)**.\n\n"
            "I provide deep, multifaceted breakdowns for **both cinema and songs**—including directorial vision, "
            "narrative and lyrical themes, sonic architecture, cinematography, and **real-time community rating distributions**.\n\n"
            "Try asking about a movie (*Inception*, *Interstellar*, *Parasite*), a song (*Blinding Lights*, *Bohemian Rhapsody*, *HUMBLE.*), "
            "or an artist like *Christopher Nolan* or *The Weeknd*!"
        ),
        "suggestions": [
            "Tell me about Inception",
            "Tell me about Bohemian Rhapsody",
            "Tell me about Interstellar",
            "Tell me about The Weeknd",
            "What are the top rated movies?",
            "What are the top rated songs?",
            "Recommend a sci-fi thriller"
        ]
    }
