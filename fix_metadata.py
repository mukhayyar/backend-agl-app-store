#!/usr/bin/env python3
"""Inject /metadata into all 50 flatpak OSTree commits that are missing it."""
import subprocess, tempfile, os, shutil

REPO = "/srv/flatpak-repo"
GPG_KEY = "E9ADCFFF97CE5264"

MANIFESTS = {
    "com.pens.2048": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "game_2048", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.AsciiArt": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "ascii_art", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.AudioTimer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "audio_timer", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.BaseConverter": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "base_converter", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.BmiCalculator": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "bmi_calculator", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ChordFinder": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "chord_finder", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.ClickAssist": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "click_assist", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ColorBlindSim": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "color_blind_sim", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ColorPalette": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "color_palette", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.CurrencyConverter": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "currency_converter", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--share=network"]},
    "com.pens.DiffViewer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "diff_viewer", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.DrumMachine": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "drum_machine", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.FifteenPuzzle": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "fifteen_puzzle", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.FontBrowser": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "font_browser", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.FontSizeTool": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "font_size_tool", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.GrammarChecker": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "grammar_checker", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.HashTool": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "hash_tool", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.Histogram": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "histogram", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--filesystem=home"]},
    "com.pens.HttpTester": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "http_tester", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--share=network"]},
    "com.pens.IconBrowser": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "icon_browser", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ImageViewer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "image_viewer", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--filesystem=home"]},
    "com.pens.JsonFormatter": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "json_formatter", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.JwtDecoder": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "jwt_decoder", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.LanguageFlash": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "language_flash", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.MathQuiz": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "math_quiz", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.Metronome": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "metronome", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.Minesweeper": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "minesweeper", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.MorseCode": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "morse_code", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.MusicTheory": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "music_theory", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.OnScreenKeyboard": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "on_screen_keyboard", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.Paint": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "paint", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--filesystem=home"]},
    "com.pens.PeriodicTable": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "periodic_table", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.PitchTuner": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "pitch_tuner", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.QrGenerator": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "qr_generator", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.RadioPlayer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "radio_player", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio", "--share=network"]},
    "com.pens.Recorder": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "audio_recorder", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio", "--filesystem=home"]},
    "com.pens.RegexTester": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "regex_tester", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ScreenMagnifier": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "screen_magnifier", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.SketchPad": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "sketch_pad", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--filesystem=home"]},
    "com.pens.Snake": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "snake", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.SpectrumAnalyzer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "spectrum_analyzer", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.Sudoku": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "sudoku", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.SvgViewer": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "svg_viewer", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--filesystem=home"]},
    "com.pens.TimestampTool": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "timestamp_tool", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.TimezoneWorld": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "timezone_world", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.ToneGenerator": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "tone_generator", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio"]},
    "com.pens.TypingTutor": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "typing_tutor", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.UuidGenerator": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "uuid_generator", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
    "com.pens.VoiceNotes": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "voice_notes", "finish_args": ["--socket=wayland", "--socket=fallback-x11", "--socket=pulseaudio", "--filesystem=home"]},
    "com.pens.WordGuess": {"runtime": "org.gnome.Platform", "version": "45", "sdk": "org.gnome.Sdk", "command": "word_guess", "finish_args": ["--socket=wayland", "--socket=fallback-x11"]},
}

def make_metadata(app_id, info):
    lines = ["[Application]", f"name={app_id}",
             f"runtime={info['runtime']}/x86_64/{info['version']}",
             f"sdk={info['sdk']}/x86_64/{info['version']}",
             f"command={info['command']}", "", "[Context]"]
    shared, sockets, fs = [], [], []
    for fa in info['finish_args']:
        if fa.startswith("--share="): shared.append(fa[8:])
        elif fa.startswith("--socket="): sockets.append(fa[9:])
        elif fa.startswith("--filesystem="): fs.append(fa[13:])
    if shared:  lines.append("shared=" + ";".join(shared) + ";")
    if sockets: lines.append("sockets=" + ";".join(sockets) + ";")
    if fs:      lines.append("filesystems=" + ";".join(fs) + ";")
    return "\n".join(lines) + "\n"

fixed = 0
for app_id, info in MANIFESTS.items():
    ref = f"app/{app_id}/x86_64/master"
    r = subprocess.run(["ostree", "--repo="+REPO, "rev-parse", ref], capture_output=True)
    if r.returncode != 0:
        print(f"  SKIP {app_id} — not in repo")
        continue
    metadata_content = make_metadata(app_id, info)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Checkout the existing commit tree
        checkout_dir = os.path.join(tmpdir, "checkout")
        r = subprocess.run([
            "ostree", "--repo="+REPO, "checkout",
            "--union", ref, checkout_dir
        ], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ERR {app_id} checkout: {r.stderr.strip()[:120]}")
            continue
        # Write metadata file at root of checkout
        with open(os.path.join(checkout_dir, "metadata"), "w") as f:
            f.write(metadata_content)
        # Commit the directory back with xa.metadata
        r = subprocess.run([
            "ostree", "--repo="+REPO, "commit",
            "--branch="+ref,
            f"--tree=dir={checkout_dir}",
            f"--add-metadata-string=xa.metadata={metadata_content.strip()}",
            "--no-bindings",
            f"--subject=Inject metadata for {app_id}"
        ], capture_output=True, text=True)
        if r.returncode == 0:
            fixed += 1
            print(f"  OK  {app_id}")
        else:
            print(f"  ERR {app_id}: {r.stderr.strip()[:120]}")

print(f"\nFixed {fixed}/{len(MANIFESTS)}")
print("Rebuilding with GPG signing...")
r = subprocess.run(["flatpak", "build-update-repo",
    f"--gpg-sign={GPG_KEY}", "--gpg-homedir=/root/.gnupg",
    "--generate-static-deltas", REPO], capture_output=True, text=True)
print("Rebuild:", "OK" if r.returncode == 0 else r.stderr[:200])
print("Done — try: flatpak install penshub com.pens.AsciiArt")
