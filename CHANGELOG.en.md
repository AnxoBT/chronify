# Changelog

English version of `CHANGELOG.md` (shown in the app's "What's new" window when the interface is in English).

## v1.3.0 — 2026-11-17

- **How close you are to completing each album**: the card of albums you have part of shows the percentage and how many
  songs you have out of how many (e.g. "75 % · 6/8"), closest to complete first, and on hover how many are missing.
  Albums at 100 % are in their own list.
- New fun fact: how much of each album you have, on average.
- Fixed: on Windows, opening Statistics while albums were being looked up on MusicBrainz could fail for a moment.

## v1.2.0 — 2026-11-17

- **Your albums** in Statistics: the albums you have the most songs from, the ones you have most of (and the complete
  ones), the longest and shortest albums (by length and by number of songs), albums by decade, artists with the most
  albums and fun facts (albums you have only one song from, the oldest and newest album, how many of your songs come
  from singles or EPs). Each album's total songs and length come from MusicBrainz (free, no account) with the **Search
  MusicBrainz for albums** button: it takes about 2 seconds per album, you can stop it any time and what's found shows
  up right away. Albums already looked up aren't searched again.

## v1.1.1 — 2026-11-17

- The "Liked Songs · by date" playlist is renamed on Spotify when you change the app's language, and the playlists
  Chronify creates don't count in Statistics even if you rename them or an old zip has their previous name.
- Creating playlists on Spotify only uses the alternative method when the normal one isn't available; session, rate
  limit and Spotify server errors are reported as they are.
- More messages translated into English (sync and Wi-Fi errors, song counter).
- Security: a policy to report problems privately and automatic dependency alerts.

## v1.1.0 — 2026-11-16

- **Right version**: in Checks, live, remixed, compilation and reissued songs show the original album (from MusicBrainz,
  free and without an account) and, if you read through the API, that version on Spotify, with buttons to listen to it
  and swap it in all your playlists (same position and date). Without the API, a link to search for it on Spotify.
  Songs already looked up aren't searched again.
- **Songs no longer on Spotify** (greyed out): new warning in Checks (when reading through the API). If Spotify
  replaced your copy with another that plays, yours is still recognised.
- Song links open the **Spotify desktop app** if you have it installed.
- "Same song twice" also detects titles with the alternative name in brackets
  (e.g. *Bang A Gong (Get It On)* and *Get It On*).

## v1.0.1 — 2026-11-13

- When you fix an artist's country in Statistics, the map and rankings update by themselves (without leaving the tab
  or losing your place). Marking a date as correct now also updates Checks and Summary.
- The "Liked Songs · by date" playlist is created with its name in the app's language and is no longer counted as
  another playlist (it doesn't duplicate songs in Statistics or Checks).
- Ignored playlists are recognised even if the Exportify CSV name has underscores or no accents.
- Creating playlists in Spotify only falls back to the old method if the new one doesn't exist.

## v1.0.0 — 2026-11-13

First public release.

- **Sync over Wi-Fi** (Settings), at home and without a cable: one device waits and shows its address and a code, and
  the other connects. It does the same as over USB: merges both devices' data both ways, passes the newer Exportify
  zip and the new app version to the phone. Everything is encrypted with the code, which only works once and for 2
  minutes.
- **What's new after updating**: the first time you open Chronify after an update, a window sums up what changed
  since your version.
- **Welcome guide**: four steps the first time you open Chronify on each device, with a language picker; you can see
  it again in Settings.
- **Sort by real date** any Spotify playlist: copy and paste into Spotify on the PC or (with Premium) apply it through
  the API, which *moves* the songs without deleting them and keeps the date you added them.
- **Checks**: duplicates, the same song from different editions, live versions, remixes, compilations and barely
  played copies, with a button to swap them for the main one.
- **Your playlists**: a mix made of other playlists, eras, genres, fixed or ignored playlists, with suggestions and
  one-tap fixes. **Liked Songs** sorted by date into a new playlist.
- **Dates** proposed by MusicBrainz for songs without a verified date, and **shared knowledge** (dates and countries)
  that comes with every version; what you correct always wins.
- **Statistics**: map, years, decades, artists, genres, mood, tempo, keys, popularity, niche artists, "your year" and
  monthly evolution.
- **History** with undo, **backup** and PC ↔ phone sync over USB.
- On **Windows, macOS and Linux** (Python), **Android** and in the **browser** (iPhone too), in Spanish and English,
  with a welcome screen and new-version notices.
