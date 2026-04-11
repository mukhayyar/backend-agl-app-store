#!/usr/bin/env python3
"""
AGL App Store — seed 365 apps across 12 categories.
"""
import psycopg2
from datetime import datetime, timedelta

DSN = "postgresql://pensagl:CHANGE_ME_DB_PASSWORD@localhost/agl_store"

DEVELOPERS = [
    "PENS Open Source",
    "AGL Community",
    "CarOS Labs",
    "Raspberry Pi Foundation",
    "Linux Apps Co",
    "Open IVI Project",
    "Embedded Systems Dev",
    "GTK Community",
    "FlatHub Collective",
    "AutoDev Studio",
]

LICENSES = ["GPL-2.0", "MIT", "Apache-2.0", "LGPL-2.1", "BSD-3-Clause", "MPL-2.0"]
FREE_LICENSES = {"GPL-2.0", "MIT", "Apache-2.0", "LGPL-2.1", "BSD-3-Clause", "MPL-2.0"}

RUNTIMES = [
    "org.gnome.Platform/x86_64/45",
    "org.gnome.Platform/x86_64/44",
    "org.kde.Platform/x86_64/5.15",
    "org.freedesktop.Platform/x86_64/22.08",
]

# 12 categories, 365 apps: 5 categories get 31, 7 get 30
# 12*30 = 360, need 5 extra -> first 5 categories get 31
CATEGORIES = [
    "AudioVideo",
    "Development",
    "Game",
    "Graphics",
    "Network",
    "Office",
    "Education",
    "Science",
    "System",
    "Utility",
    "Settings",
    "Accessibility",
]

APP_NAMES = {
    "AudioVideo": [
        "SoundWave Player", "Podcast Studio", "Rhythm Box Pro", "VoiceRecorder", "StreamDeck",
        "AudioEdit Pro", "Music Visualizer", "Bass Booster", "CD Ripper", "Radio Tuner",
        "Equalizer FX", "Media Converter", "FLAC Player", "AudioBook Reader", "Mixer Console",
        "Beat Maker", "Karaoke Studio", "Audio Recorder", "Noise Reducer", "Waveform Editor",
        "SoundBoard", "Podcast Player", "MIDI Editor", "Live Looper", "Spectrum Analyzer",
        "MP3 Tag Editor", "Metronome Pro", "VoIP Dialer", "Screen Recorder Audio", "Video Audio Sync",
        "Surround Sound Config",
    ],
    "Development": [
        "CodeForge", "GitLens Desktop", "Terminal Pro", "DevDash", "SQLite Browser",
        "JSON Formatter", "API Tester", "Code Diff", "Hex Editor", "Markdown Editor",
        "Python IDE", "Bash Scripter", "Docker Desktop Lite", "Log Analyzer", "Regex Tester",
        "Schema Designer", "Build Monitor", "Snippet Manager", "Port Scanner", "SSH Manager",
        "Env Config Editor", "YAML Lint", "XML Editor", "Git GUI", "CI Dashboard",
        "Code Coverage", "Profiler Lite", "Unit Test Runner", "Dependency Graph", "Makefile Editor",
        "Debugger Console",
    ],
    "Game": [
        "Chess Master", "Tetrix", "Space Defender", "Puzzle Rush", "Mahjong Classic",
        "Solitaire Plus", "Sudoku Daily", "Minesweeper Pro", "Snake Reloaded", "Brick Breaker",
        "2048 Challenge", "Word Scramble", "Memory Match", "Frogger Retro", "Pong Deluxe",
        "Asteroids Redux", "Tower Defense", "Card Battle", "Dice Roller", "Crossword Puzzle",
        "Number Crunch", "Labyrinth Quest", "Pixel Dungeon", "Galaga Clone", "Pac-Maze",
        "Quiz Master", "Trivia Night", "Bubble Shooter", "Block Puzzle", "Flip Tiles",
        "Reversi Board",
    ],
    "Graphics": [
        "PixelCraft", "SVG Editor", "Color Studio", "3D Viewer", "Icon Designer",
        "Photo Editor Lite", "Vector Draw", "Bitmap Converter", "Palette Manager", "Font Browser",
        "Mockup Tool", "Diagram Studio", "Wireframe Maker", "Sprite Editor", "Texture Packer",
        "Image Resizer", "Screenshot Annotator", "QR Code Designer", "Barcode Generator", "Logo Maker",
        "Animation Editor", "Color Picker", "PDF to Image", "Sketch Pad", "Layer Manager",
        "Background Remover", "GIF Creator", "RAW Processor", "Gradient Designer", "Sticker Maker",
        "Wallpaper Manager",
    ],
    "Network": [
        "VPN Shield", "Web Browser Lite", "Email Client Pro", "FTP Manager", "DNS Lookup",
        "Ping Monitor", "Network Scanner", "Bandwidth Monitor", "Proxy Config", "SSH Tunnel",
        "Firewall Config", "Packet Sniffer Lite", "Wake On LAN", "IP Calculator", "HTTP Client",
        "Torrent Manager", "RSS Reader", "WebDAV Client", "SFTP Explorer", "VNC Viewer",
        "Remote Desktop", "Network Stats", "Speed Test", "Domain Checker", "URL Shortener",
        "Mail Filter", "SMTP Tester", "LDAP Browser", "Netstat Viewer", "Traceroute Tool",
        "Certificate Inspector",
    ],
    "Office": [
        "Docs Editor", "Spreadsheet Pro", "Presentation Studio", "PDF Annotator", "Note Pad",
        "Task Manager Office", "Calendar Sync", "Contact Book", "Mail Composer", "Invoice Maker",
        "Time Tracker", "Budget Planner", "Meeting Scheduler", "Document Scanner", "E-Sign",
        "Clipboard Notes", "Mind Map", "Gantt Chart", "Form Builder", "Report Designer",
        "Label Printer", "Business Card Maker", "Letter Template", "Fax Sender", "Archive Manager",
        "Dictionary Pro", "Thesaurus", "Grammar Check", "Font Manager Office", "Template Library",
    ],
    "Education": [
        "Math Trainer", "Language Tutor", "Science Lab", "History Atlas", "Typing Practice",
        "Flash Cards", "Quiz Builder", "Periodic Table Edu", "Geography Map", "Astronomy Guide Edu",
        "Grammar Tutor", "Spelling Bee", "Logic Puzzles", "Reading Helper", "Coding for Kids",
        "Fraction Trainer", "Algebra Solver", "Geometry Sketchpad", "Biology Explorer", "Physics Sim",
        "Chemistry Lab Edu", "World Languages", "Timeline Maker", "Essay Writer", "Cite Right",
        "Study Timer", "Note Organizer", "Exam Prep", "Vocabulary Builder", "Number Sense",
    ],
    "Science": [
        "Periodic Table", "Calculator Pro", "Unit Converter", "Astronomy Guide", "Chem Tools",
        "Graph Plotter", "Statistics Calc", "Matrix Solver", "Physics Constants", "Biology Atlas",
        "Molecule Viewer", "Circuit Simulator", "Signal Analyzer", "Data Logger", "Oscilloscope Sim",
        "Weather Station", "GPS Tracker", "Seismograph Viewer", "Telescope Controller", "Spectrometer",
        "Lab Notebook", "Formula Reference", "Equation Editor", "Numerical Methods", "Data Fit",
        "Chrono Timer", "Frequency Counter", "Resistor Calc", "Ohm's Law Tool", "Vector Calculator",
    ],
    "System": [
        "System Monitor", "Disk Manager", "Backup Tool", "Process Explorer", "Log Viewer",
        "Task Scheduler", "Boot Manager", "Driver Manager", "Update Manager", "Service Control",
        "Memory Optimizer", "Startup Manager", "Environment Editor", "Firewall Status", "Hardware Info",
        "Temperature Monitor", "Battery Monitor", "Power Manager", "Locale Config", "Date Time Config",
        "User Manager", "Group Manager", "Permission Manager", "Mount Manager", "Swap Config",
        "Kernel Log", "BIOS Info", "PCI Device List", "USB Device Manager", "Bluetooth Manager",
    ],
    "Utility": [
        "File Archiver", "Clipboard Manager", "Screenshot Tool", "Timer & Alarm", "QR Scanner",
        "Text Converter", "Bulk Rename", "Duplicate Finder", "Disk Usage Analyzer", "Password Manager",
        "OTP Authenticator", "Note Launcher", "Quick Launcher", "Hotkey Manager", "Calendar Widget",
        "World Clock", "Currency Converter", "Unit Calc", "Stopwatch", "Countdown Timer",
        "Barcode Scanner", "Color Dropper", "Magnifier Util", "Ruler Tool", "Network Util",
        "Hash Calculator", "Base64 Tool", "URL Encoder", "Diff Viewer", "JSON Viewer",
    ],
    "Settings": [
        "Display Config", "Network Manager", "Sound Config", "Theme Switcher", "Startup Apps",
        "Keyboard Layout", "Mouse Config", "Touchpad Config", "Power Settings", "Privacy Control",
        "Notification Config", "Language Settings", "Regional Config", "Accessibility Settings", "Security Config",
        "Printer Config", "Scanner Setup", "Bluetooth Config", "Wi-Fi Manager", "VPN Settings",
        "Time Zone Config", "Night Light Config", "Font Config", "Icon Theme", "Cursor Theme",
        "Wallpaper Config", "Screen Saver", "Login Screen Config", "Default Apps", "File Association",
    ],
    "Accessibility": [
        "Screen Reader", "Magnifier", "High Contrast", "Keyboard Assist", "Voice Control",
        "On-Screen Keyboard", "Sticky Keys", "Mouse Keys", "Slow Keys", "Bounce Keys",
        "Color Blind Filter", "Text to Speech", "Speech to Text", "Braille Output", "Caption Maker",
        "Focus Assist", "Reading Aid", "Motor Assist", "Eye Tracking Config", "Gesture Control",
        "Auto Click", "Switch Access", "Large Text Mode", "Pointer Enlarger", "Audio Description",
        "Sign Language Guide", "Simple Mode", "Dyslexia Font", "Screen Dimmer", "Tremor Filter",
    ],
}

# Flagship apps (index multiples of 18 across all apps) will be verified
FLAGSHIP_INDICES = set(range(0, 365, 18))  # ~20 apps

def make_app_id(category: str, name: str) -> str:
    slug = name.replace(" ", "").replace("-", "").replace("&", "And").replace("'", "").replace(".", "")
    return f"org.agl.{category}{slug}"

def make_homepage(app_id: str) -> str:
    return f"https://apps.agl.org/app/{app_id}"

def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # Get existing IDs to avoid duplicates
    cur.execute("SELECT id FROM apps;")
    existing_ids = {row[0] for row in cur.fetchall()}
    print(f"Existing apps: {len(existing_ids)}")

    now = datetime.utcnow()
    one_year = now + timedelta(days=365)

    # Build distribution: first 5 categories get 31, rest get 30
    counts = {}
    for i, cat in enumerate(CATEGORIES):
        counts[cat] = 31 if i < 5 else 30

    total_planned = sum(counts.values())
    print(f"Planned total: {total_planned}")

    apps_to_insert = []
    global_idx = 0

    for cat in CATEGORIES:
        cat_count = counts[cat]
        names = APP_NAMES[cat]
        # Ensure we have enough names (pad if needed)
        while len(names) < cat_count:
            names.append(f"{cat} App {len(names)+1}")

        for local_idx in range(cat_count):
            name = names[local_idx]
            app_id = make_app_id(cat, name)

            # Skip if already exists
            if app_id in existing_ids:
                print(f"  SKIP (exists): {app_id}")
                global_idx += 1
                continue

            published = (global_idx % 2 == 1)  # odd=published, even=unpublished
            is_verified = global_idx in FLAGSHIP_INDICES
            dev = DEVELOPERS[global_idx % len(DEVELOPERS)]
            lic = LICENSES[global_idx % len(LICENSES)]
            runtime = RUNTIMES[global_idx % len(RUNTIMES)]
            is_free = lic in FREE_LICENSES
            is_mobile = (global_idx % 3 == 0)

            expires = None if published else one_year

            apps_to_insert.append({
                "id": app_id,
                "name": name,
                "summary": f"{name} — a powerful {cat.lower()} application for your Linux desktop.",
                "description": (
                    f"{name} is a feature-rich {cat.lower()} application built for the "
                    f"AGL App Store ecosystem. It provides a clean, modern interface optimized "
                    f"for both desktop and in-vehicle infotainment systems. "
                    f"Developed by {dev}, this application is distributed under the {lic} license."
                ),
                "type": "desktop-application",
                "project_license": lic,
                "is_free_license": is_free,
                "developer_name": dev,
                "icon": f"https://flathub.org/repo/appstream/x86_64/icons/128x128/{app_id}.png",
                "runtime": runtime,
                "updated_at": now,
                "added_at": now - timedelta(days=global_idx % 365),
                "is_mobile_friendly": is_mobile,
                "verification_verified": is_verified,
                "published": published,
                "expires_at": expires,
                "is_verified": is_verified,
                "homepage": make_homepage(app_id),
                "category": cat,
                "global_idx": global_idx,
            })

            global_idx += 1

    print(f"Apps to insert: {len(apps_to_insert)}")

    inserted = 0
    for app in apps_to_insert:
        try:
            cur.execute("""
                INSERT INTO apps (
                    id, name, summary, description, type,
                    project_license, is_free_license, developer_name, icon, runtime,
                    updated_at, added_at, is_mobile_friendly,
                    verification_verified,
                    published, expires_at, is_verified
                ) VALUES (
                    %(id)s, %(name)s, %(summary)s, %(description)s, %(type)s,
                    %(project_license)s, %(is_free_license)s, %(developer_name)s, %(icon)s, %(runtime)s,
                    %(updated_at)s, %(added_at)s, %(is_mobile_friendly)s,
                    %(verification_verified)s,
                    %(published)s, %(expires_at)s, %(is_verified)s
                )
            """, app)

            # Primary category
            cur.execute(
                "INSERT INTO app_categories (app_id, category) VALUES (%s, %s)",
                (app["id"], app["category"])
            )

            # Secondary category for ~1 in 4 apps
            if app["global_idx"] % 4 == 0:
                sec_cat_idx = (CATEGORIES.index(app["category"]) + 1) % len(CATEGORIES)
                sec_cat = CATEGORIES[sec_cat_idx]
                cur.execute(
                    "INSERT INTO app_categories (app_id, category) VALUES (%s, %s)",
                    (app["id"], sec_cat)
                )

            inserted += 1
            if inserted % 50 == 0:
                print(f"  Inserted {inserted}...")
                conn.commit()

        except Exception as e:
            print(f"  ERROR inserting {app['id']}: {e}")
            conn.rollback()

    conn.commit()
    print(f"\nDone! Inserted {inserted} apps.")

    # Summary
    cur.execute("SELECT COUNT(*) FROM apps;")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM apps WHERE published = true;")
    pub = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM apps WHERE published = false;")
    unpub = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM app_categories;")
    cats = cur.fetchone()[0]

    print(f"\n=== DB Summary ===")
    print(f"Total apps:       {total}")
    print(f"Published:        {pub}")
    print(f"Unpublished:      {unpub}")
    print(f"Category entries: {cats}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
