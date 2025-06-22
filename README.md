<p align="center">
  <img src="https://i.imgur.com/y4qnQQr.png" alt="Lei-Music Banner" width="300"/>
</p>

<p align="center">
  <a href="https://github.com/LE1DENFROST/Lei-Music/stargazers"><img src="https://img.shields.io/github/stars/LE1DENFROST/Lei-Music?style=for-the-badge&color=c955e8&logo=github" alt="Stars"></a>
  <a href="https://github.com/LE1DENFROST/Lei-Music/network/members"><img src="https://img.shields.io/github/forks/LE1DENFROST/Lei-Music?style=for-the-badge&color=81a1c1&logo=github" alt="Forks"></a>
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
  <a href="https://github.com/LE1DENFROST/Lei-Music/blob/main/LICENSE"><img src="https://img.shields.io/github/license/LE1DENFROST/Lei-Music?style=for-the-badge&color=a3be8c" alt="License"></a>
</p>

<p align="center">
  Your personal music universe, right on your desktop.
</p>

---

**Lei-Music** is an open-source, feature-rich desktop music player built with Python and PyQt6. It seamlessly bridges the vast library of YouTube Music with a sleek, modern, and highly customizable user interface. Discover new artists, craft your perfect playlists, and enjoy a premium listening experience without the premium price tag.

## ✨ Key Features

*   🎶 **Vast Music Library**: Instantly access millions of songs, albums, and artists via the YouTube Music API.
*   🔍 **Advanced Search**: Find exactly what you're looking for with dedicated search filters for songs, artists, and albums.
*   📚 **Your Personal Library**:
    *   Create, edit, and manage unlimited custom playlists.
    *   Assign custom cover images (including GIFs!) to your playlists for a personal touch.
    *   Keep all your favorite tracks in a dedicated "Favorites" list.
*   🎨 **Dynamic & Modern UI**:
    *   **Aura Panel**: The artist info panel dynamically adapts its color scheme based on the currently playing song's cover art.
    *   **Customizable Themes**: Choose from multiple built-in themes (Classic Dark, Light, Ocean, Synthwave) to match your mood.
    *   **Asynchronous by Design**: A buttery-smooth, non-blocking interface ensures a fluid user experience.
*   💾 **Offline Listening**: Cache your frequently played songs automatically or manually for playback without an internet connection.
*   🌐 **Discover Page**: Explore curated playlists across various genres and moods to discover your next favorite song.
*   🎛️ **Full Playback Control**: Enjoy features like repeat (list/track), shuffle, and drag-and-drop queue management.

## 📸 Gallery

| Discover Page | Player & Playlist View |
| :---: | :---: |
| <!-- EKRAN GÖRÜNTÜSÜ URL'Sİ BURAYA --> | <!-- EKRAN GÖRÜNTÜSÜ URL'Sİ BURAYA --> |

| Dynamic "Aura" Artist Panel | Settings & Theming |
| :---: | :---: |
| <!-- EKRAN GÖRÜNTÜSÜ URL'Sİ BURAYA --> | <!-- EKRAN GÖRÜNTÜSÜ URL'Sİ BURAYA --> |

## 🛠️ Tech Stack

*   **Framework**: PyQt6
*   **Music Source**: `ytmusicapi` & `yt-dlp`
*   **Metadata**: `wikipedia-api` & `musicbrainzngs`
*   **Audio Backend**: `python-vlc`
*   **Dynamic Theming**: `color-thief-py`

## 🚀 Installation & Setup

Get Lei-Music up and running on your system with these simple steps.

#### 1. Prerequisites
*   **Python 3.8** or newer.
*   **Git** version control.
*   **FFmpeg**: Required for audio conversion (caching).

#### 2. Clone The Repository
```bash
git clone https://github.com/LEIDENFROST/Lei-Music.git
cd Lei-Music
```

#### 3. Install Dependencies
Install all the required Python libraries using the `requirements.txt` file.
```bash
pip install -r requirements.txt
```

#### 4. Setting up FFmpeg
> **Note:** FFmpeg is crucial for the song caching feature.

**For Windows users (Recommended):**
1.  Download a release build from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) or the [official FFmpeg site](https://ffmpeg.org/download.html).
2.  Extract the downloaded `.zip` file.
3.  Navigate into the `bin` folder.
4.  Copy `ffmpeg.exe` and `ffprobe.exe` and paste them into the root directory of the Lei-Music project (the same folder where `main.py` is located).

The application will automatically detect and use them.

#### 5. Run The Application
You can now launch the application.

**From your terminal:**
```bash
python main.py
```
**For Windows users (easy way):**
Simply double-click the `start.bat` file.

## 💡 How to Use

1.  **Search**: Use the search bar at the top to find a song, artist, or album.
2.  **Play**: Double-click any song in a list to start playing.
3.  **Explore**: Right-click on a song to see more options, like adding it to a playlist, adding to favorites, or viewing the artist.
4.  **Organize**: Drag and drop songs within your own playlists to reorder them.

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".

1.  **Fork** the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a **Pull Request**

Don't forget to give the project a star! Thanks again!

## ⚖️ Disclaimer

Lei-Music is a personal, non-commercial project developed for educational purposes. Users are expected to respect the copyright laws of their country and the terms of service of any APIs used.

The developer assumes no liability for any misuse of this software. It is the user's sole responsibility to ensure that their use of Lei-Music does not infringe on any copyrights.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
