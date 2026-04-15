# menu.py
from direct.gui.DirectGui import (
    DirectFrame, DirectButton, DirectLabel, DirectSlider
)
from panda3d.core import TextNode, WindowProperties
from direct.showbase import ShowBaseGlobal


# ============================================================
# MENU MANAGER
# ============================================================
class MenuManager:
    def __init__(self, game):
        self.game = game
        self.active_menu = None
        self._game_mouse_props = None

    def open(self, menu):
        # Fade to menu music only when first menu opens
        if self.active_menu is None:
            self.game.sound.crossfade("background", "menu_music", duration=1.0)

            # Save current mouse properties
            self._game_mouse_props = self.game.win.getProperties()

            # Switch to absolute mouse mode and show cursor
            props = WindowProperties()
            props.setMouseMode(WindowProperties.M_absolute)
            props.setCursorHidden(False)
            self.game.win.requestProperties(props)

        # Close previous menu
        if self.active_menu:
            self.active_menu.close()

        self.active_menu = menu
        menu.open()

        # Pause game logic
        self.game.taskMgr.remove("updateDroneOrbits")

        # Enter UI mode
        self.game.ui_mode = True

    def close(self):
        if self.active_menu:
            self.active_menu.close()
            self.active_menu = None

        # Resume game logic
        self.game.taskMgr.add(self.game.update_drone_orbits, "updateDroneOrbits")

        # Exit UI mode
        self.game.ui_mode = False

        # Restore mouse mode
        if self._game_mouse_props is not None:
            self.game.win.requestProperties(self._game_mouse_props)
            self._game_mouse_props = None

        # Fade back to background music
        self.game.sound.crossfade("menu_music", "background", duration=1.0)


# ============================================================
# EXIT MENU (YES/NO with Y/N shortcuts)
# ============================================================
class ExitMenu:
    def __init__(self, game):
        self.game = game
        self.opened = False

    def open(self):
        if self.opened:
            return
        self.opened = True

        base = ShowBaseGlobal.base

        # Light overlay
        self.overlay = DirectFrame(
            frameColor=(0, 0, 0, 0.3),
            frameSize=(-1.5, 1.5, -1, 1),
            parent=base.aspect2d
        )

        # Simple bright panel
        self.box = DirectFrame(
            frameColor=(0.1, 0.2, 0.5, 0.95),
            frameSize=(-0.8, 0.8, -0.4, 0.4),
            relief="raised",
            borderWidth=(0.01, 0.01),
            parent=self.overlay
        )

        DirectLabel(
            text="Do you wish to exit?",
            scale=0.09,
            pos=(0, 0, 0.2),
            parent=self.box
        )

        # YES button (Green)
        self.yes_button = DirectButton(
            text="YES (Y)",
            scale=0.07,
            pos=(-0.3, 0, -0.1),
            parent=self.box,
            frameColor=(0.1, 0.8, 0.1, 1),
            text_fg=(1, 1, 1, 1),
            command=self.game.userExit
        )

        # NO button (Red)
        self.no_button = DirectButton(
            text="NO (N)",
            scale=0.07,
            pos=(0.3, 0, -0.1),
            parent=self.box,
            frameColor=(0.8, 0.1, 0.1, 1),
            text_fg=(1, 1, 1, 1),
            command=self.game.menu_manager.close
        )

        # Keyboard shortcuts
        base.accept("y", self.game.userExit)
        base.accept("n", self.game.menu_manager.close)

    def close(self):
        base = ShowBaseGlobal.base
        base.ignore("y")
        base.ignore("n")

        self.overlay.destroy()
        self.opened = False


# ============================================================
# AUDIO SETTINGS MENU
# ============================================================
class AudioMenu:
    def __init__(self, game):
        self.game = game
        self.opened = False

    def open(self):
        if self.opened:
            return
        self.opened = True

        base = ShowBaseGlobal.base

        self.overlay = DirectFrame(
            frameColor=(0, 0, 0, 0.3),
            frameSize=(-1.5, 1.5, -1, 1),
            parent=base.aspect2d
        )

        self.box = DirectFrame(
            frameColor=(0.1, 0.2, 0.5, 0.95),
            frameSize=(-0.9, 0.9, -0.65, 0.65),
            relief="raised",
            borderWidth=(0.01, 0.01),
            parent=self.overlay
        )

        DirectLabel(text="Audio Settings", scale=0.09, pos=(0, 0, 0.5), parent=self.box)

        # MASTER
        DirectLabel(text="Master Volume", scale=0.065, pos=(-0.45, 0, 0.28), parent=self.box)
        self.master_slider = DirectSlider(
            range=(0, 1), value=self.game.sound.master_volume,
            scale=0.45, pos=(0.25, 0, 0.28),
            command=self.update_master, parent=self.box
        )

        # MUSIC
        DirectLabel(text="Music Volume", scale=0.065, pos=(-0.45, 0, 0.08), parent=self.box)
        self.music_slider = DirectSlider(
            range=(0, 1), value=self.game.sound.music_volume,
            scale=0.45, pos=(0.25, 0, 0.08),
            command=self.update_music, parent=self.box
        )

        # SFX
        DirectLabel(text="SFX Volume", scale=0.065, pos=(-0.45, 0, -0.12), parent=self.box)
        self.sfx_slider = DirectSlider(
            range=(0, 1), value=self.game.sound.sfx_volume,
            scale=0.45, pos=(0.25, 0, -0.12),
            command=self.update_sfx, parent=self.box
        )

        DirectButton(
            text="Close",
            scale=0.07,
            pos=(0, 0, -0.45),
            parent=self.box,
            frameColor=(0.3, 0.3, 0.8, 1),
            text_fg=(1, 1, 1, 1),
            command=self.game.menu_manager.close
        )

    def update_master(self):
        self.game.sound.master_volume = self.master_slider['value']
        self.game.sound.apply_volumes()

    def update_music(self):
        self.game.sound.music_volume = self.music_slider['value']
        self.game.sound.apply_volumes()

    def update_sfx(self):
        self.game.sound.sfx_volume = self.sfx_slider['value']
        self.game.sound.apply_volumes()

    def close(self):
        self.overlay.destroy()
        self.opened = False


# ============================================================
# PAUSE MENU
# ============================================================
class PauseMenu:
    def __init__(self, game):
        self.game = game
        self.opened = False

    def open(self):
        if self.opened:
            return
        self.opened = True

        base = ShowBaseGlobal.base

        self.overlay = DirectFrame(
            frameColor=(0, 0, 0, 0.3),
            frameSize=(-1.5, 1.5, -1, 1),
            parent=base.aspect2d
        )

        self.box = DirectFrame(
            frameColor=(0.1, 0.2, 0.5, 0.95),
            frameSize=(-0.75, 0.75, -0.55, 0.55),
            relief="raised",
            borderWidth=(0.01, 0.01),
            parent=self.overlay
        )

        DirectLabel(text="Paused", scale=0.1, pos=(0, 0, 0.38), parent=self.box)

        DirectButton(
            text="Resume",
            scale=0.07,
            pos=(0, 0, 0.18),
            parent=self.box,
            frameColor=(0.1, 0.7, 0.1, 1),
            text_fg=(1, 1, 1, 1),
            command=self.game.menu_manager.close
        )

        DirectButton(
            text="Audio Settings",
            scale=0.07,
            pos=(0, 0, -0.02),
            parent=self.box,
            frameColor=(0.3, 0.3, 0.8, 1),
            text_fg=(1, 1, 1, 1),
            command=lambda: self.game.menu_manager.open(self.game.audio_menu)
        )

        DirectButton(
            text="Quit Game",
            scale=0.07,
            pos=(0, 0, -0.48),
            parent=self.box,
            frameColor=(0.8, 0.2, 0.2, 1),
            text_fg=(1, 1, 1, 1),
            command=lambda: self.game.menu_manager.open(self.game.exit_menu)
        )

    def close(self):
        self.overlay.destroy()
        self.opened = False
