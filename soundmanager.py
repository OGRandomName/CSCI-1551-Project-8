# soundmanager.py

from direct.showbase import ShowBaseGlobal
from direct.task import Task
import random
import os

class SoundManager:
    def __init__(self):
        self.sounds = {}          # named SFX
        self.sfx = {}             # raw SFX loaded by path
        self.music_banks = {}     # music banks
        self.current_track = None
        self.fade_task = None

        self.master_volume = 1.0
        self.music_volume = 0.7
        self.sfx_volume = 1.0

        loader = ShowBaseGlobal.base.loader

        # Preload boost SFX
        self.sfx["boost1"] = loader.loadSfx("Assets/sounds/boost.mp3")
        self.sfx["boost2"] = loader.loadSfx("Assets/sounds/boosted-rocket.mp3")

        # Preload explosion + rocket sounds if available
        self._safe_preload("explosion", "Assets/sounds/explosion.mp3")
        self._safe_preload("rocket_explosion", "Assets/sounds/rocket-explosion.mp3")
        self._safe_preload("player_move", "Assets/sounds/player.mp3")

    # ---------------------------------------------------------
    # INTERNAL SAFE LOAD
    # ---------------------------------------------------------
    def _safe_preload(self, key, path):
        """Load a sound safely and store it in self.sfx."""
        try:
            if os.path.exists(path):
                snd = ShowBaseGlobal.base.loader.loadSfx(path)
                self.sfx[key] = snd
        except Exception:
            pass

    # ---------------------------------------------------------
    # VOLUME APPLICATION
    # ---------------------------------------------------------
    def apply_volumes(self):
        for bank in self.music_banks.values():
            for snd in bank:
                snd.setVolume(self.master_volume * self.music_volume)

        for snd in self.sfx.values():
            snd.setVolume(self.master_volume * self.sfx_volume)

        for snd in self.sounds.values():
            snd.setVolume(self.master_volume * self.sfx_volume)

    # ---------------------------------------------------------
    # BASIC LOAD/PLAY
    # ---------------------------------------------------------
    def load(self, name, path, loop=False, volume=1.0):
        snd = ShowBaseGlobal.base.loader.loadSfx(path)
        snd.setLoop(loop)
        snd.setVolume(volume)
        self.sounds[name] = snd

    def play(self, name):
        if name in self.sounds:
            self.sounds[name].play()
            return self.sounds[name]
        return None

    def stop(self, name):
        if name in self.sounds:
            self.sounds[name].stop()

    # ---------------------------------------------------------
    # SFX BY FILE PATH (used by collisions + player)
    # ---------------------------------------------------------
    def play_sfx(self, path):
        """
        Play a one-shot SFX by file path.
        Returns AudioSound handle if possible.
        """
        try:
            # Reuse cached sound if already loaded
            if path in self.sfx:
                snd = self.sfx[path]
            else:
                snd = ShowBaseGlobal.base.loader.loadSfx(path)
                self.sfx[path] = snd

            snd.setVolume(self.master_volume * self.sfx_volume)
            snd.setLoop(False)
            snd.play()
            return snd

        except Exception:
            print(f"[SoundManager] Failed to play SFX: {path}")
            return None

    # ---------------------------------------------------------
    # PLAY FILE (looping or one-shot)
    # ---------------------------------------------------------
    def play_file(self, path, loop=False):
        """
        Load and play a sound file directly.
        Returns AudioSound handle.
        """
        try:
            snd = ShowBaseGlobal.base.loader.loadSfx(path)
            snd.setLoop(loop)
            snd.setVolume(self.master_volume * self.sfx_volume)
            snd.play()
            return snd
        except Exception:
            print(f"[SoundManager] Failed to play file: {path}")
            return None

    # ---------------------------------------------------------
    # MUSIC BANKS
    # ---------------------------------------------------------
    def load_bank(self, bank_name, file_list, loop=True, volume=1.0):
        self.music_banks[bank_name] = []
        for path in file_list:
            try:
                snd = ShowBaseGlobal.base.loader.loadSfx(path)
                snd.setLoop(loop)
                snd.setVolume(volume)
                self.music_banks[bank_name].append(snd)
            except Exception:
                print(f"[SoundManager] Failed to load music file: {path}")

    def play_random_from_bank(self, bank_name):
        if bank_name not in self.music_banks:
            return None

        if self.current_track:
            self.current_track.stop()

        snd = random.choice(self.music_banks[bank_name])
        snd.setVolume(self.master_volume * self.music_volume)
        snd.play()
        self.current_track = snd
        return snd

    # ---------------------------------------------------------
    # CROSSFADE
    # ---------------------------------------------------------
    def crossfade(self, from_bank, to_bank, duration=2.0):
        base = ShowBaseGlobal.base

        if self.fade_task:
            base.taskMgr.remove(self.fade_task)

        new_track = random.choice(self.music_banks[to_bank])
        new_track.setVolume(0)
        new_track.play()

        old_track = self.current_track
        self.current_track = new_track

        def fade_task(task):
            t = min(task.time / duration, 2.0)

            if old_track:
                old_track.setVolume((1.0 - t) * self.music_volume)

            new_track.setVolume(t * self.music_volume)

            if t >= 1.0:
                if old_track:
                    old_track.stop()
                return Task.done

            return Task.cont

        self.fade_task = base.taskMgr.add(fade_task, "musicCrossfade")

    # ---------------------------------------------------------
    # RANDOM BOOST SOUND
    # ---------------------------------------------------------
    def play_random_boost(self):
        choice = random.choice(["boost1", "boost2"])
        s = self.sfx.get(choice)
        if s:
            s.setVolume(self.master_volume * self.sfx_volume)
            s.play()
        # ---------------------------------------------------------
    # FADE OUT CURRENT MUSIC
    # ---------------------------------------------------------
    def fade_out_music(self, duration=3.0):
        """
        Smoothly fades out the currently playing music track.
        """
        base = ShowBaseGlobal.base

        if not self.current_track:
            return

        track = self.current_track
        start_volume = track.getVolume()

        # Cancel any existing fade task
        if self.fade_task:
            try:
                base.taskMgr.remove(self.fade_task)
            except:
                pass

        def fade_task(task):
            t = min(task.time / duration, 1.0)
            track.setVolume(start_volume * (1.0 - t))

            if t >= 1.0:
                track.stop()
                return Task.done

            return Task.cont

        self.fade_task = base.taskMgr.add(fade_task, "musicFadeOut")
   
    def fade_in_bank(self, bank_name, duration=2.0):
        """
        Fades in a random track from a music bank.
        """
        base = ShowBaseGlobal.base

        if bank_name not in self.music_banks:
            print(f"[Sound] Bank '{bank_name}' not found.")
            return

        # Stop current track if any
        if self.current_track:
            try:
                self.current_track.stop()
            except:
                pass

        new_track = random.choice(self.music_banks[bank_name])
        new_track.setVolume(0)
        new_track.play()
        self.current_track = new_track

        def fade_task(task):
            t = min(task.time / duration, 1.0)
            new_track.setVolume(t * self.music_volume)
            return Task.done if t >= 1.0 else Task.cont

        base.taskMgr.add(fade_task, f"fadeIn_{bank_name}")
