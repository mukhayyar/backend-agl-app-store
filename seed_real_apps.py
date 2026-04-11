#!/usr/bin/env python3
"""Seed 120 real apps from simple-flatpak-app-collections into AGL App Store DB."""

import psycopg2
from datetime import datetime, timedelta

# All 120 new folders (pre-filtered, sorted alphabetically)
ALL_FOLDERS = [
    "a11y-click-assist", "a11y-color-blind-sim", "a11y-contrast-checker",
    "a11y-font-size-tool", "a11y-high-contrast", "a11y-on-screen-keyboard",
    "a11y-reading-guide", "a11y-screen-magnifier", "a11y-text-to-speech",
    "a11y-voice-notes", "audio-audio-timer", "audio-chord-finder",
    "audio-drum-machine", "audio-metronome", "audio-music-theory",
    "audio-pitch-tuner", "audio-radio-player", "audio-recorder",
    "audio-spectrum-analyzer", "audio-tone-generator", "dev-ascii-art",
    "dev-base-converter", "dev-diff-viewer", "dev-hash-tool",
    "dev-http-tester", "dev-json-formatter", "dev-jwt-decoder",
    "dev-regex-tester", "dev-timestamp-tool", "dev-uuid-generator",
    "edu-bmi-calculator", "edu-currency-converter", "edu-grammar-checker",
    "edu-language-flash", "edu-math-quiz", "edu-morse-code",
    "edu-number-systems", "edu-periodic-table", "edu-timezone-world",
    "edu-typing-tutor", "game-2048", "game-breakout", "game-chess-clock",
    "game-fifteen-puzzle", "game-memory-match", "game-minesweeper",
    "game-paint", "game-snake", "game-sudoku", "game-word-guess",
    "gfx-color-palette", "gfx-font-browser", "gfx-fractal-viewer",
    "gfx-histogram", "gfx-icon-browser", "gfx-image-viewer",
    "gfx-pixel-editor", "gfx-qr-generator", "gfx-sketch-pad",
    "gfx-svg-viewer", "net-dns-lookup", "net-ip-info",
    "net-network-monitor", "net-ping-monitor", "net-port-scanner",
    "net-socket-tester", "net-speed-test", "net-traceroute-viewer",
    "net-url-checker", "net-wifi-info", "office-calendar-app",
    "office-contact-book", "office-expense-tracker", "office-flashcards",
    "office-habit-tracker", "office-invoice-maker", "office-notes",
    "office-password-manager", "office-time-tracker", "office-word-counter",
    "sci-binary-counter", "sci-function-plotter", "sci-logic-gates",
    "sci-matrix-calc", "sci-ohm-calculator", "sci-pendulum-sim",
    "sci-prime-sieve", "sci-statistics-calc", "sci-unit-science",
    "sci-wave-simulator", "set-display-info", "set-font-manager",
    "set-gtk-inspector", "set-keyboard-tester", "set-locale-info",
    "set-mouse-tester", "set-power-profiles", "set-proxy-settings",
    "set-shortcut-ref", "set-theme-switcher", "sys-boot-analyzer",
    "sys-cpu-benchmark", "sys-disk-usage", "sys-env-viewer",
    "sys-file-permissions", "sys-log-viewer", "sys-memory-map",
    "sys-process-viewer", "sys-service-monitor", "sys-startup-manager",
    "util-alarm-clock", "util-archive-viewer", "util-barcode-gen",
    "util-clipboard-manager", "util-date-calculator", "util-file-renamer",
    "util-random-tools", "util-screen-ruler", "util-stopwatch",
    "util-text-tools",
]

# Prefix → category mapping
PREFIX_CATEGORY = {
    "audio": "AudioVideo",
    "dev": "Development",
    "game": "Game",
    "gfx": "Graphics",
    "net": "Network",
    "office": "Office",
    "edu": "Education",
    "sci": "Science",
    "sys": "System",
    "util": "Utility",
    "set": "Settings",
    "a11y": "Accessibility",
}

SUMMARIES = {
    "a11y-click-assist": "Assists users with click automation for improved accessibility.",
    "a11y-color-blind-sim": "Simulates color blindness modes to help design accessible content.",
    "a11y-contrast-checker": "Checks color contrast ratios for WCAG accessibility compliance.",
    "a11y-font-size-tool": "Adjusts and previews font sizes for better readability.",
    "a11y-high-contrast": "Applies high-contrast themes to improve screen visibility.",
    "a11y-on-screen-keyboard": "Provides a virtual on-screen keyboard for mouse-only input.",
    "a11y-reading-guide": "Highlights lines of text to assist reading focus.",
    "a11y-screen-magnifier": "Magnifies screen regions for users with low vision.",
    "a11y-text-to-speech": "Converts on-screen text to speech for audio accessibility.",
    "a11y-voice-notes": "Records and plays back voice notes for hands-free note-taking.",
    "audio-audio-timer": "A timer application with audio alerts for timed sessions.",
    "audio-chord-finder": "Identifies and displays guitar or piano chord fingerings.",
    "audio-drum-machine": "A simple drum machine for creating beat patterns.",
    "audio-metronome": "Provides a configurable metronome for music practice.",
    "audio-music-theory": "Teaches and visualizes fundamental music theory concepts.",
    "audio-pitch-tuner": "Tunes instruments by detecting and displaying pitch frequency.",
    "audio-radio-player": "Streams and plays internet radio stations.",
    "audio-recorder": "Records audio from the microphone and saves to file.",
    "audio-spectrum-analyzer": "Visualizes the frequency spectrum of audio input in real time.",
    "audio-tone-generator": "Generates pure tones at user-specified frequencies.",
    "dev-ascii-art": "Converts text or images into ASCII art representations.",
    "dev-base-converter": "Converts numbers between binary, octal, decimal, and hexadecimal.",
    "dev-diff-viewer": "Displays side-by-side diffs between two text files or snippets.",
    "dev-hash-tool": "Computes and verifies cryptographic hashes like MD5 and SHA-256.",
    "dev-http-tester": "Sends HTTP requests and inspects responses for API testing.",
    "dev-json-formatter": "Formats, validates, and pretty-prints JSON data.",
    "dev-jwt-decoder": "Decodes and inspects JSON Web Token (JWT) payloads.",
    "dev-regex-tester": "Tests and debugs regular expressions with live match highlighting.",
    "dev-timestamp-tool": "Converts between Unix timestamps and human-readable date formats.",
    "dev-uuid-generator": "Generates RFC-compliant UUIDs for use in development.",
    "edu-bmi-calculator": "Calculates Body Mass Index and provides health category feedback.",
    "edu-currency-converter": "Converts between world currencies using up-to-date exchange rates.",
    "edu-grammar-checker": "Checks English text for common grammar and spelling errors.",
    "edu-language-flash": "Flashcard app for learning vocabulary in foreign languages.",
    "edu-math-quiz": "Presents randomized math quizzes to practice arithmetic skills.",
    "edu-morse-code": "Translates text to Morse code and plays it back as audio.",
    "edu-number-systems": "Teaches and converts between different number systems.",
    "edu-periodic-table": "Displays an interactive periodic table of chemical elements.",
    "edu-timezone-world": "Shows current times across world time zones on a map.",
    "edu-typing-tutor": "Improves typing speed and accuracy with guided exercises.",
    "game-2048": "Slide tiles to combine numbers and reach the 2048 tile.",
    "game-breakout": "Classic breakout game where you destroy bricks with a bouncing ball.",
    "game-chess-clock": "Dual countdown chess clock for timed over-the-board games.",
    "game-fifteen-puzzle": "Solve the sliding 15-tile puzzle by arranging numbers in order.",
    "game-memory-match": "Flip cards to find matching pairs in this memory challenge.",
    "game-minesweeper": "Classic minesweeper game with configurable grid and mine count.",
    "game-paint": "Simple paint application for freehand drawing and doodling.",
    "game-snake": "Guide the growing snake to eat food without hitting walls.",
    "game-sudoku": "Solve classic 9x9 Sudoku puzzles with hint and validation support.",
    "game-word-guess": "Guess the hidden word one letter at a time before running out of tries.",
    "gfx-color-palette": "Generates and manages color palettes for design projects.",
    "gfx-font-browser": "Browses and previews installed system fonts.",
    "gfx-fractal-viewer": "Renders and explores fractal patterns like Mandelbrot sets.",
    "gfx-histogram": "Displays color histograms for image analysis.",
    "gfx-icon-browser": "Browses installed icon themes and copies icon names.",
    "gfx-image-viewer": "Lightweight image viewer supporting common raster formats.",
    "gfx-pixel-editor": "Pixel-level image editor for creating sprites and icons.",
    "gfx-qr-generator": "Generates QR codes from URLs or text input.",
    "gfx-sketch-pad": "Digital sketch pad for quick freehand drawings.",
    "gfx-svg-viewer": "Renders and inspects SVG vector graphics files.",
    "net-dns-lookup": "Performs DNS lookups and displays record details for any domain.",
    "net-ip-info": "Shows geolocation and ISP details for any IP address.",
    "net-network-monitor": "Monitors real-time network traffic and interface statistics.",
    "net-ping-monitor": "Pings hosts continuously and graphs latency over time.",
    "net-port-scanner": "Scans a host for open TCP/UDP ports.",
    "net-socket-tester": "Tests TCP/UDP socket connections for debugging network services.",
    "net-speed-test": "Measures internet download and upload speeds.",
    "net-traceroute-viewer": "Visualizes the network route to a host with latency per hop.",
    "net-url-checker": "Checks HTTP status codes and redirects for a list of URLs.",
    "net-wifi-info": "Displays details about the current Wi-Fi connection and signal strength.",
    "office-calendar-app": "A simple calendar for managing events and appointments.",
    "office-contact-book": "Stores and manages personal and professional contacts.",
    "office-expense-tracker": "Tracks daily expenses and visualizes spending categories.",
    "office-flashcards": "Creates and studies digital flashcard decks for any subject.",
    "office-habit-tracker": "Tracks daily habits and streaks to build lasting routines.",
    "office-invoice-maker": "Generates printable invoices for freelance or small business use.",
    "office-notes": "Lightweight note-taking app with markdown support.",
    "office-password-manager": "Stores and retrieves passwords securely with a master passphrase.",
    "office-time-tracker": "Logs time spent on tasks and projects with summary reports.",
    "office-word-counter": "Counts words, characters, and sentences in pasted text.",
    "sci-binary-counter": "Visualizes binary counting and bit-level representations.",
    "sci-function-plotter": "Plots mathematical functions on a 2D Cartesian graph.",
    "sci-logic-gates": "Simulates basic digital logic gates and circuit combinations.",
    "sci-matrix-calc": "Performs matrix arithmetic including multiplication and inversion.",
    "sci-ohm-calculator": "Calculates resistance, voltage, and current using Ohm's Law.",
    "sci-pendulum-sim": "Simulates simple and double pendulum physics in real time.",
    "sci-prime-sieve": "Visualizes the Sieve of Eratosthenes to find prime numbers.",
    "sci-statistics-calc": "Computes descriptive statistics like mean, median, and standard deviation.",
    "sci-unit-science": "Converts between scientific units across physics and chemistry.",
    "sci-wave-simulator": "Simulates wave interference and propagation patterns.",
    "set-display-info": "Shows detailed information about connected displays and resolutions.",
    "set-font-manager": "Manages and previews installed fonts system-wide.",
    "set-gtk-inspector": "Inspects GTK widget trees for theme debugging.",
    "set-keyboard-tester": "Tests keyboard key inputs and shows keycodes.",
    "set-locale-info": "Displays current locale settings and system language configuration.",
    "set-mouse-tester": "Tests mouse buttons, scroll, and pointer accuracy.",
    "set-power-profiles": "Switches between performance, balanced, and power-saver profiles.",
    "set-proxy-settings": "Configures and manages system-level network proxy settings.",
    "set-shortcut-ref": "Displays a searchable reference of keyboard shortcuts for apps.",
    "set-theme-switcher": "Switches between GTK and icon themes with live preview.",
    "sys-boot-analyzer": "Analyzes systemd boot times and identifies slow services.",
    "sys-cpu-benchmark": "Runs CPU benchmarks and reports performance scores.",
    "sys-disk-usage": "Visualizes disk space usage by directory with drill-down support.",
    "sys-env-viewer": "Displays current environment variables for the running session.",
    "sys-file-permissions": "Inspects and explains file permission bits and ACLs.",
    "sys-log-viewer": "Browses and filters system journal and log files.",
    "sys-memory-map": "Shows memory usage per process and system memory map.",
    "sys-process-viewer": "Lists and monitors running processes with CPU and RAM stats.",
    "sys-service-monitor": "Monitors systemd service status and restart counts.",
    "sys-startup-manager": "Manages applications that launch at user login.",
    "util-alarm-clock": "Sets one-shot or recurring alarms with custom alert sounds.",
    "util-archive-viewer": "Opens and extracts archive files like ZIP, TAR, and 7z.",
    "util-barcode-gen": "Generates 1D and 2D barcodes from user-supplied data.",
    "util-clipboard-manager": "Keeps a searchable history of clipboard entries.",
    "util-date-calculator": "Calculates the difference between dates and adds/subtracts durations.",
    "util-file-renamer": "Batch renames files using patterns and regular expressions.",
    "util-random-tools": "Generates random numbers, passwords, and UUIDs on demand.",
    "util-screen-ruler": "Measures pixel distances and element sizes on screen.",
    "util-stopwatch": "Stopwatch with lap timer and split-time recording.",
    "util-text-tools": "Provides common text transformations like case change and trimming.",
}


def to_pascal(folder_name: str) -> str:
    parts = folder_name.split("-", 1)
    rest = parts[1] if len(parts) > 1 else parts[0]
    return "".join(word.capitalize() for word in rest.split("-"))


def to_human_name(folder_name: str) -> str:
    parts = folder_name.split("-", 1)
    rest = parts[1] if len(parts) > 1 else parts[0]
    return " ".join(word.capitalize() for word in rest.split("-"))


def get_category(folder_name: str) -> str:
    prefix = folder_name.split("-")[0]
    return PREFIX_CATEGORY.get(prefix, "Utility")


def main():
    apps = sorted(ALL_FOLDERS)
    assert len(apps) == 120, f"Expected 120 apps, got {len(apps)}"
    print(f"Processing {len(apps)} apps...")

    conn = psycopg2.connect(
        host="localhost",
        dbname="agl_store",
        user="pensagl",
        password="CHANGE_ME_DB_PASSWORD"
    )
    cur = conn.cursor()

    now = datetime.utcnow()
    inserted = 0
    skipped = 0

    for i, folder in enumerate(apps):
        pascal = to_pascal(folder)
        app_id = f"com.pens.{pascal}"
        name = to_human_name(folder)
        category = get_category(folder)
        published = i < 60
        is_verified = (i % 12 == 0)
        added_at = now - timedelta(days=180 - i * 1.5)
        summary = SUMMARIES.get(folder, f"A {name} application for the AGL platform.")
        icon = f"https://raw.githubusercontent.com/mukhayyar/simple-flatpak-app-collections/main/{folder}/icon.png"

        try:
            cur.execute("""
                INSERT INTO apps (id, name, summary, developer_name, published, is_verified,
                                  added_at, updated_at, type, icon)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (app_id, name, summary, "PENS App Store Team", published, is_verified,
                  added_at, added_at, "desktop-application", icon))

            if cur.rowcount > 0:
                cur.execute("""
                    INSERT INTO app_categories (app_id, category)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (app_id, category))
                inserted += 1
                print(f"  [{i:3d}] {'PUB' if published else 'UNP'} {'VER' if is_verified else '   '} {app_id}")
            else:
                skipped += 1
                print(f"  SKIP {app_id} (already exists)")

        except Exception as e:
            print(f"  ERROR inserting {app_id}: {e}")
            conn.rollback()
            # Reconnect after rollback failure
            continue

    conn.commit()

    # Verification query
    cur.execute("SELECT COUNT(*), COUNT(*) FILTER(WHERE published), COUNT(*) FILTER(WHERE NOT published), COUNT(*) FILTER(WHERE is_verified) FROM apps WHERE id LIKE 'com.pens.%'")
    total, pub, unpub, verified = cur.fetchone()

    print(f"\n=== Results ===")
    print(f"Inserted this run: {inserted}, Skipped (already existed): {skipped}")
    print(f"Total com.pens.* apps in DB : {total}")
    print(f"  Published   : {pub}")
    print(f"  Unpublished : {unpub}")
    print(f"  Verified    : {verified}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
