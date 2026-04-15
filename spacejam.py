# spacejam.py

import math
import os
import random

from panda3d.core import Vec3, ClockObject
from direct.showbase.ShowBase import ShowBase
from direct.showbase import ShowBaseGlobal

from direct.gui.DirectGui import DirectFrame, DirectButton, DirectLabel

from soundmanager import SoundManager
from menu import ExitMenu, AudioMenu, MenuManager, PauseMenu
from collisions import CollisionManager

from classes import (
    Planet,
    SpaceStation,
    Player,
    DroneDefender,
    Universe,
    DroneCounter,
)
from dronepatterns import (
    circleX_pattern,
    circleY_pattern,
    circleZ_pattern,
    cloud_pattern,
    baseball_seams_pattern,
)

# ---------------------------------------------------------
# GAMEPLAY CONSTANTS
# ---------------------------------------------------------
# How close the player must be to activate spinning/orbiting
PLANET_ACTIVATION_DISTANCE = 12000
PLANET_ATMOSPHERE_DISTANCE = 2000

# How close the player must be to activate drones (if used)
DRONE_ACTIVATION_DISTANCE = 2500

# How close drones must be to influence each other (swarm activation)
DRONE_SWARM_RADIUS = 2500
# ---------------------------------------------------------
# GLOBAL PERFORMANCE MODE
# ---------------------------------------------------------
# True  = fewer drones, fewer decorated planets, more culling, lighter CPU load
# False = full visual experience
PERFORMANCE_MODE = False

# Drone pattern functions used to decorate planets
PATTERN_FUNCTIONS = [
    circleX_pattern,
    circleY_pattern,
    circleZ_pattern,
    cloud_pattern,
    baseball_seams_pattern,
]

class SpaceJam(ShowBase):

    def __init__(self):
        super().__init__()
        ShowBaseGlobal.base = self

        # ---------------------------------------------------------
        # CORE RUNTIME CONTAINERS
        # ---------------------------------------------------------
        # ui_mode: when True, input is "captured" by UI (menus) instead of gameplay.
        self.ui_mode = False

        # DroneCounter tracks how many drones have been spawned.
        self.drone_counter = DroneCounter()

        # Lists of active game objects
        self.orbiting_drones = []
        self.planets = []

        # ---------------------------------------------------------
        # CREATE SOUNDMANAGER EARLY
        # ---------------------------------------------------------
        # SoundManager handles:
        #   - SFX playback
        #   - Music banks
        #   - Crossfades and fades
        self.sound = SoundManager()
        # ---------------------------------------------------------
        # WORLD SETUP (NO AUDIO DEPENDENCY)
        # ---------------------------------------------------------
        self.setup_space_station()
        self.collision_manager = CollisionManager(self)
        self.setup_planets()
        self.setup_universe()
        self.setup_player()
        self.setup_camera()
        self.setup_lights()

        # ---------------------------------------------------------
        # MENUS (NEED SOUND)
        # ---------------------------------------------------------
        # Menus are created after SoundManager so they can play SFX/music if needed.
        self.menu_manager = MenuManager(self)
        self.pause_menu = PauseMenu(self)
        self.exit_menu = ExitMenu(self)
        self.audio_menu = AudioMenu(self)

        # Music state machine:
        #   "background" → normal space
        #   "bossfight"  → inside planet atmosphere
        self.music_state = "background"

        # ---------------------------------------------------------
        # LOAD AUDIO BANKS
        # ---------------------------------------------------------
        #   Assets/sounds/background/background1.mp3 ... backgroundN.mp3
        #   Assets/sounds/bossfight/bossfight1.mp3   ... bossfightN.mp3
        background_files = [
            f"background/background{i}.mp3" for i in range(1, 4)
        ]
        bossfight_files = [
            f"bossfight/bossfight{i}.mp3" for i in range(1, 4)
        ]

        # Music banks for in‑game music
        self.sound.load_bank("background", background_files, loop=True, volume=0.4)
        self.sound.load_bank("bossfight", bossfight_files, loop=True, volume=0.25)

        # Menu banks (not actively used for PM3, but kept for future)
        self.sound.load_bank(
            "menu_silence", ["Assets/sounds/silence.mp3"], loop=False, volume=0
        )
        self.sound.load_bank(
            "menu_music", ["Assets/sounds/menu.mp3"], loop=True, volume=0.2
        )

        # Apply master/music/SFX volumes after loading banks
        self.sound.apply_volumes()

        # ---------------------------------------------------------
        # START BACKGROUND MUSIC
        # ---------------------------------------------------------
        # Start a random background track at game start.
        try:
            track = self.sound.play_random_from_bank("background")
            if track:
                print("[Sound] Background music started.")
            else:
                print("[Sound] Background bank is empty — check filenames and paths.")
        except Exception as e:
            print("[Sound] Failed to start background music:", e)

        # ---------------------------------------------------------
        # COLLIDERS
        # ---------------------------------------------------------
        print("\n=== COLLISION MANAGER START ===")
        print("Planets in list:", len(self.planets))
        print("Drones in list:", len(self.orbiting_drones))

        # Player collider
        self.collision_manager.register_player(self.player)

        # Planets + station as static colliders
        for planet in self.planets:
            self.collision_manager.register_static(planet)

        self.collision_manager.register_static(self.station)

        # Drones as moving colliders
        for drone in self.orbiting_drones:
            self.collision_manager.register_drone(drone)

        # Event hooks + tasks
        self.collision_manager.setup_events()
        self.taskMgr.add(self.collision_manager.update, "collisionEngineUpdate")

        # Missile interval cleanup (removes finished missiles from active lists)
        self.taskMgr.add(self.player.CheckIntervals, "checkMissiles", priority=34)
        self.taskMgr.add(self.player.CheckIntervals, "checkProjectiles", priority=34)



        # Drone orbits + planet spin + music state machine
        self.taskMgr.add(self.update_drone_orbits, "updateDroneOrbits")

        # ---------------------------------------------------------
        # INPUT BINDINGS
        # ---------------------------------------------------------
        #  When ui_mode is True, gameplay input is ignored.
        self._setup_input_bindings()

        print("[SpaceJam] Initialization complete.")

    # ---------------------------------------------------------
    # INPUT BINDINGS
    # ---------------------------------------------------------
    def _setup_input_bindings(self):
        """
        Bind keyboard and mouse input to player controls.
        All controls are disabled when ui_mode is True.
        """

        # Forward thrust
        self.accept("w", lambda: self.player.Thrust(1) if not self.ui_mode else None)
        self.accept("w-up", lambda: self.player.Thrust(0) if not self.ui_mode else None)

        # Reverse thrust
        self.accept(
            "s", lambda: self.player.ReverseThrust(1) if not self.ui_mode else None
        )
        self.accept(
            "s-up", lambda: self.player.ReverseThrust(0) if not self.ui_mode else None
        )

        # Roll left/right
        self.accept("a", lambda: self.player.RollLeft(1) if not self.ui_mode else None)
        self.accept("a-up", lambda: self.player.RollLeft(0) if not self.ui_mode else None)

        self.accept("d", lambda: self.player.RollRight(1) if not self.ui_mode else None)
        self.accept(
            "d-up", lambda: self.player.RollRight(0) if not self.ui_mode else None
        )

        # Move up/down
        self.accept(
            "space", lambda: self.player.MoveUp(1) if not self.ui_mode else None
        )
        self.accept(
            "space-up", lambda: self.player.MoveUp(0) if not self.ui_mode else None
        )

        self.accept(
            "shift", lambda: self.player.MoveDown(1) if not self.ui_mode else None
        )
        self.accept(
            "shift-up", lambda: self.player.MoveDown(0) if not self.ui_mode else None
        )

        # Yaw left/right
        self.accept(
            "q", lambda: self.player.LeftTurn(1) if not self.ui_mode else None
        )
        self.accept(
            "q-up", lambda: self.player.LeftTurn(0) if not self.ui_mode else None
        )

        self.accept(
            "e", lambda: self.player.RightTurn(1) if not self.ui_mode else None
        )
        self.accept(
            "e-up", lambda: self.player.RightTurn(0) if not self.ui_mode else None
        )

        # Fire missile
        self.accept(
            "mouse1", lambda: self.player.Fire() if not self.ui_mode else None
        )

        # Activate boost
        self.accept("f", lambda: self.player.start_boost())
        self.accept("f-up", lambda: self.player.stop_boost())

        # Escape → open exit menu
        self.accept("escape", lambda: self.menu_manager.open(self.exit_menu))
        # Cycle weapons
        self.accept("tab", lambda: self.player.cycle_weapon())

    # ---------------------------------------------------------
    # CAMERA
    # ---------------------------------------------------------
    def setup_camera(self):
        """
        Attach the camera to the player's model if available.
        If the player isn't present yet, parent to render and schedule a one-time reparent.
        """
        # Disable default mouse-based camera control
        self.disableMouse()

        # If player already exists, attach camera to player model
        if hasattr(self, "player") and self.player is not None:
            try:
                self.camera.reparentTo(self.player.model)
                self.camera.setFluidPos(0, -40, 10)
                self.camera.setHpr(0, -10, 0)
                print("[Camera] Parent set to player.model")
            except Exception as e:
                print(
                    f"[Camera] Failed to parent to player.model: {e}; attaching to render instead."
                )
                self.camera.reparentTo(self.render)
                self.camera.setPos(0, -40, 10)
                self.camera.setHpr(0, -10, 0)
        else:
            # Fallback: attach to render until player is ready
            self.camera.reparentTo(self.render)
            self.camera.setPos(0, -40, 10)
            self.camera.setHpr(0, -10, 0)
            print(
                "[Camera] Player not present yet — camera attached to render temporarily."
            )

            # Deferred reparent task: waits until player exists, then reattaches camera
            def _attach_camera_when_ready(task):
                if hasattr(self, "player") and self.player is not None:
                    try:
                        self.camera.reparentTo(self.player.model)
                        self.camera.setFluidPos(0, -40, 10)
                        self.camera.setHpr(0, -10, 0)
                        print("[Camera] Reparented to player.model (deferred).")
                    except Exception as e:
                        print(f"[Camera] Deferred reparent failed: {e}")
                    return task.done
                return task.cont

            self.taskMgr.add(_attach_camera_when_ready, "attachCameraWhenPlayerReady")

    # ---------------------------------------------------------
    # Drone Ring Creator (optional helper)
    # ---------------------------------------------------------
    def create_drone_ring(self, center_pos, num_drones=6, radius=10):
        """
        Optional helper to spawn a simple ring of drones around a point.
        Not used by the planet patterns, but kept as a utility.
        """
        drones = []
        cx, cy, cz = center_pos

        for i in range(num_drones):
            angle = (2 * math.pi / num_drones) * i
            x = cx + radius * math.cos(angle)
            z = cz + radius * math.sin(angle)
            y = cy

            drone = DroneDefender(
                name=f"Drone_{i}",
                model_path="Assets/DroneDefender/DroneDefender.egg",
                scale=0.5,
                position=(x, y, z),
                orbit_radius=radius,
            )

            drone.orbit_center = center_pos
            drone.orbit_angle = angle
            drone.orbit_speed = 0.5

            drones.append(drone)
            self.orbiting_drones.append(drone)
            self.drone_counter.register_drone()

        return drones

    # ---------------------------------------------------------
    # Space Station
    # ---------------------------------------------------------
    def setup_space_station(self):
        """
        Create the main space station with a multi-box collider.
        The box_list defines approximate collision volumes for different parts.
        """
        station_boxes = [
            {"center": (3, -2, -4), "size": (16, 15, 30)},   # central tower
            {"center": (0, 0, -5), "size": (28, 28, 0.5)},   # ring middle
            {"center": (-30, 30, -15), "size": (12, 12, 6)}, # ring left
        ]

        self.station = SpaceStation(
            name="MainStation",
            model_path="Assets/space station/spaceStation.egg",
            scale=3.0,
            position=(20, 10, 0),
            box_list=station_boxes,
        )
        self.station.node.setHpr(0, 0, 0)

    # ---------------------------------------------------------
    # Universe (Skybox)
    # ---------------------------------------------------------
    def setup_universe(self):
        """
        Create the skybox universe model.
        This is a large sphere or cube that surrounds the scene.
        """
        try:
            self.universe = Universe(
                model_path="Assets/Universe/Universe.egg",
                scale=15000,
                position=(0, 0, 0),
            )
            print("[Universe] Skybox loaded.")
        except Exception as e:
            print(f"[Universe] Failed to load universe model: {e}")

    # ---------------------------------------------------------
    # Player (Spaceship)
    # ---------------------------------------------------------
    def setup_player(self):
        """
        Create the player ship.
        The Player class handles movement, missiles, and boost visuals.
        """
        self.player = Player(
            name="PlayerShip",
            model_path="Assets/spaceships/Dumbledore.egg",
            scale=1.5,
            position=(0, -30, 0),
        )

    # ---------------------------------------------------------
    # Lighting
    # ---------------------------------------------------------
    def setup_lights(self):
        """
        Basic ambient + directional lighting for the scene.
        """
        from panda3d.core import AmbientLight, DirectionalLight, Vec4

        # Soft ambient light
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.2, 0.2, 0.25, 1))
        ambient_np = self.render.attachNewNode(ambient)
        self.render.setLight(ambient_np)

        # Directional light (like a sun)
        dlight = DirectionalLight("dlight")
        dlight.setColor(Vec4(0.8, 0.8, 0.7, 1))
        dlight_np = self.render.attachNewNode(dlight)
        dlight_np.setHpr(45, -60, 0)
        self.render.setLight(dlight_np)

    # ---------------------------------------------------------
    # DRONE ORBIT UPDATE (single task for all drones)
    # ---------------------------------------------------------
    def update_drone_orbits(self, task):
        """
        Main per-frame update for:
          - Planet spin (only when player is near enough)
          - Music state machine (background ↔ bossfight)
          - Drone swarm activation
          - Drone orbit updates

        This runs as a Panda3D task, called every frame.
        """
        dt = ClockObject.getGlobalClock().getDt()
        player_pos = self.player.node.getPos(self.render)

        # PERFORMANCE_MODE: optionally skip some updates to reduce CPU load.
        if PERFORMANCE_MODE and random.random() < 0.5:
            return task.cont

        # -----------------------------------------------------
        # Planet spin (only when player is within activation distance)
        # -----------------------------------------------------
        for planet in self.planets:
            planet.update_spin(dt, player_pos)

        # -----------------------------------------------------
        # MUSIC STATE MACHINE
        # -----------------------------------------------------
        # We determine whether the player is inside ANY planet's atmosphere.
        in_atmosphere = False

        for planet in self.planets:
            dist = (planet.node.getPos(self.render) - player_pos).length()
            if dist < PLANET_ATMOSPHERE_DISTANCE:
                in_atmosphere = True
                break

        # Entering atmosphere → switch to bossfight music
        if in_atmosphere and self.music_state != "bossfight":
            print("[Music] Entered atmosphere → switching to bossfight music")
            self.sound.fade_out_music(2.0)
            self.sound.fade_in_bank("bossfight", 2.0)
            self.music_state = "bossfight"

        # Leaving atmosphere → switch back to background music
        elif not in_atmosphere and self.music_state != "background":
            print("[Music] Left atmosphere → switching to background music")
            self.sound.fade_out_music(2.0)
            self.sound.fade_in_bank("background", 2.0)
            self.music_state = "background"

        # -----------------------------------------------------
        # DRONE SWARM ACTIVATION
        # -----------------------------------------------------
        # Primary drone activation based on distance to player
        for drone in self.orbiting_drones:
            dist = (drone.node.getPos(self.render) - player_pos).length()
            drone.active = dist < DRONE_ACTIVATION_DISTANCE
   
       # If any drone is active, nearby drones within DRONE_SWARM_RADIUS
        # will also become active. This creates a "swarm wake-up" effect.
        for drone in self.orbiting_drones:
            if drone.active:
                for other in self.orbiting_drones:
                    if other is drone:
                        continue
                    if (
                        other.node.getPos(self.render)
                        - drone.node.getPos(self.render)
                    ).length() < DRONE_SWARM_RADIUS:
                        other.active = True

        # -----------------------------------------------------
        # DRONE ORBIT UPDATE
        # -----------------------------------------------------
        # Each drone updates its orbit and pattern internally.
        for drone in self.orbiting_drones:
            drone.update(dt, player_pos)

        return task.cont

    # ---------------------------------------------------------
    # Planets + Drone Patterns
    # ---------------------------------------------------------
    def setup_planets(self):
        """
        Generate planets at random positions around the origin, with:
          - Non-overlapping placement
          - Random scales
          - Random textures

        """
        print("\n=== SETUP PLANETS STARTED ===")

        planet_textures = [
            "planet-texture.png",
            "planet-texture1.png",
            "planet-texture2.png",
            "planet-texture3.png",
            "planet-texture4.png",
            "planet-texture5.png",
            "planet-texture6.png",
            "planet-texture7.png",
            "planet-texture8.png",
        ]

        placed_planets = []  # (x, y, z, radius) for overlap checks

        # Performance mode uses fewer planets and larger spacing
        if PERFORMANCE_MODE:
            min_distance_factor = 10
            distance_min, distance_max = 5000, 14000
            y_min, y_max = -2000, 5000
        else:
            min_distance_factor = 15
            distance_min, distance_max = 4000, 12000
            y_min, y_max = -2000, 5000

        planet_positions = []  # store (x, y, z, scale) for later decoration

        # -----------------------------------------------------
        # RANDOM PLANET GENERATION
        # -----------------------------------------------------
        for i, tex_name in enumerate(planet_textures):
            print(f"\n--- Generating planet {i + 1} ---")

            # Try multiple times to find a non-overlapping position
            for attempt in range(500):
                distance = random.uniform(distance_min, distance_max)
                angle = random.uniform(0, 2 * math.pi)
                y = random.uniform(y_min, y_max)
                z = random.uniform(-1000, 1000)
                x = distance * math.cos(angle)

                scale = random.uniform(200, 450)
                radius = scale / 2

                overlap = False
                for px, py, pz, pradius in placed_planets:
                    d = math.sqrt((x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2)
                    if d < min_distance_factor * (radius + pradius):
                        overlap = True
                        break

                if not overlap:
                    # Found a valid position
                    break

            print(
                f"Planet {i + 1} position: ({x:.1f}, {y:.1f}, {z:.1f}) "
                f"scale={scale:.1f}"
            )

            # Create the planet
            planet = Planet(
                name=f"PLANET{i + 1}",
                model_path="Assets/planets/protoPlanet.obj",
                scale=scale,
                position=(x, y, z),
                texture_path=os.path.join("Assets/planets", tex_name),
                enable_collisions=True,
            )

            print("Loaded planet model:", planet.model)

            placed_planets.append((x, y, z, radius))
            planet_positions.append((x, y, z, scale))
            self.planets.append(planet)

            print(f"Planet {i + 1} appended. Total so far: {len(self.planets)}")

        print("\n=== PLANET GENERATION COMPLETE ===")
        print("Total planets created:", len(self.planets))

        # -----------------------------------------------------
        # DECORATE SOME PLANETS WITH DRONE PATTERNS
        # -----------------------------------------------------
        if PERFORMANCE_MODE:
            num_planets_to_decorate = 4
        else:
            # Decorate between 3 and 6 planets, but not more than we have patterns
            num_planets_to_decorate = min(
                len(PATTERN_FUNCTIONS), random.randint(3, 6)
            )

        # Randomly choose which planets to decorate and which patterns to use
        chosen_planets = random.sample(planet_positions, num_planets_to_decorate)
        unique_patterns = random.sample(PATTERN_FUNCTIONS, num_planets_to_decorate)

        print(f"\nDecorating {num_planets_to_decorate} planets with patterns...")

        for (planet_data, pattern_func) in zip(chosen_planets, unique_patterns):
            px, py, pz, scale = planet_data
            print(
                f"Applying pattern {pattern_func.__name__} to planet at "
                f"({px:.1f}, {py:.1f}, {pz:.1f})"
            )

            # Fewer drones in performance mode
            drone_count = 8 if PERFORMANCE_MODE else random.randint(10, 25)

            # pattern_func is a helper from dronepatterns.py that returns a list of drones
            drones = pattern_func(
                self,
                center_pos=(px, py, pz),
                num_drones=drone_count,
                radius=scale * 2,
            )
            # Scale and register drones
            for drone in drones:
                self.orbiting_drones.append(drone)
                self.drone_counter.register_drone()

        print("\n=== SETUP PLANETS FINISHED ===")
        print("Total drones spawned:", self.drone_counter.get_count())
        print(
            f"Decorated {num_planets_to_decorate} planets with random patterns."
        )

app = SpaceJam()
app.run()
