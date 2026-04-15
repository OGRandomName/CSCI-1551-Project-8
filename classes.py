# classes.py
import random
from unittest import loader
from direct.showbase import ShowBaseGlobal
from panda3d.core import (
    Texture, ClockObject, Vec3, TextureStage, LODNode,
    CollisionNode, CollisionSphere, TransparencyAttrib
)
from direct.gui.OnscreenImage import OnscreenImage
from panda3d.core import CardMaker

# Collider metadata
from collisions import SphereCollideObj, BoxCollideObj, MultiBoxCollideObj

DEBUG_COLLIDERS = False  # Set to True to show colliders for debugging; False for normal play

# ============================================================
# Base Class: SpaceObject (visual only)
# ============================================================
class SpaceObject:
    def __init__(self, name, model_path, scale, position,
                 collider_type="sphere", health=100, texture_path=None):

        self.name = name
        self.model_path = model_path
        self.scale = scale
        self.position = position
        self.collider_type = collider_type
        self.health = health
        self.texture_path = texture_path

        # ROOT NODE (no scale!)
        self.node = ShowBaseGlobal.base.render.attachNewNode(self.name + "_ROOT")
        self.node.setPos(*self.position)

        # Load model under the root
        self.model = ShowBaseGlobal.base.loader.loadModel(self.model_path)
        self.model.reparentTo(self.node)

        # Apply scale to MODEL, not root
        self.model.setScale(self.scale)

        # Tag
        self.model.setTag("objectType", self.name)

        # Texture override
        if self.texture_path:
            tex = ShowBaseGlobal.base.loader.loadTexture(self.texture_path)
            if tex:
                self.model.setTexture(tex, 1)

    def set_position(self, pos):
        self.position = pos
        self.node.setPos(*pos)


# ============================================================
# Universe (no collisions)
# ============================================================
class Universe:
    def __init__(self, model_path, scale=15000, position=(0, 0, 0), texture_path=None):
        self.name = "Universe"
        self.model_path = model_path
        self.scale = scale
        self.position = position
        self.texture_path = texture_path

        self.collider_type = None
        self.debug_mode = False

        self.model = ShowBaseGlobal.base.loader.loadModel(self.model_path)
        self.model.reparentTo(ShowBaseGlobal.base.camera)
        self.model.setCompass()

        self.model.setPos(*self.position)
        self.model.setScale(self.scale)

        self.model.setTag("objectType", "Universe")

        if self.texture_path:
            tex = ShowBaseGlobal.base.loader.loadTexture(self.texture_path)
            if tex:
                self.model.setTexture(tex, 1)

        self.model.setTwoSided(True)


# ============================================================
# Planet (Sphere collider)
# ============================================================
import math

class Planet(SpaceObject, SphereCollideObj):
    def __init__(
        self,
        name,
        model_path,
        scale,
        position,
        texture_path=None,
        enable_collisions=True,
        health=100
    ):
        SpaceObject.__init__(
            self,
            name=name,
            model_path=model_path,
            scale=scale,
            position=position,
            collider_type="sphere",
            health=health
        )

        self.enable_collisions = enable_collisions

        if enable_collisions:
            # Planet model is scaled by self.scale, so collider must match radius = scale * 0.5
            SphereCollideObj.__init__(self, radius=scale * 0.5)

            self.debug_mode = False
        else:
            self.collider_type = "none"
            self.debug_mode = False

        if texture_path:
            tex = ShowBaseGlobal.base.loader.loadTexture(texture_path)
            self.model.setTexture(tex, 1)

        self.model.flattenStrong()
        self.model.setTwoSided(False)

        ShowBaseGlobal.base.taskMgr.add(self._distance_cull, f"planetCull_{name}")

    def _distance_cull(self, task):
        cam = ShowBaseGlobal.base.camera
        planet_pos = self.node.getPos(ShowBaseGlobal.base.render)
        cam_pos = cam.getPos(ShowBaseGlobal.base.render)

        dx = planet_pos.x - cam_pos.x
        dy = planet_pos.y - cam_pos.y
        dz = planet_pos.z - cam_pos.z
        dist_sq = dx*dx + dy*dy + dz*dz
        # Placeholder for future LOD / culling logic
        return task.cont

    def update_spin(self, dt, player_pos):
        planet_pos = self.node.getPos(ShowBaseGlobal.base.render)
        dist = (planet_pos - player_pos).length()

        if dist < 12000:
            self.model.setH(self.model.getH() + 10 * dt)


# ============================================================
# Space Station (Multi‑box collider)
# ============================================================
class SpaceStation(SpaceObject, MultiBoxCollideObj):
    def __init__(self, name, model_path, scale, position, box_list, health=100):
        SpaceObject.__init__(
            self,
            name=name,
            model_path=model_path,
            scale=scale,
            position=position,
            collider_type="multi_box",
            health=health
        )

        MultiBoxCollideObj.__init__(self, box_list)
        self.debug_mode = DEBUG_COLLIDERS


# ============================================================
# Missile Class (must appear BEFORE Player)
# ============================================================
class Missile(SphereCollideObj):
    missileCount = 0
    Models = {}
    Colliders = {}
    Intervals = {}

    def __init__(self, name, model_path, scale, position):
        Missile.missileCount += 1

        self.name = name
        self.model_path = model_path
        self.scale = scale
        self.position = position

        self.node = ShowBaseGlobal.base.render.attachNewNode(name + "_ROOT")
        self.node.setPos(*position)

        self.model = ShowBaseGlobal.base.loader.loadModel(model_path)
        self.model.reparentTo(self.node)
        self.model.setScale(scale)

        # Larger missile collider to avoid tunneling at high speed
        SphereCollideObj.__init__(self, radius=15.0)
        # Show collider while testing; set to False later
        self.debug_mode = DEBUG_COLLIDERS

        Missile.Models[name] = self.model

        print(f"[Missile] Created missile {name} (collider radius=10.0)")

# ============================================================
# Laser Projectile (fast, small hitbox, beam-style)
# ============================================================
class Laser(SphereCollideObj):
    laserCount = 0
    Models = {}
    Colliders = {}
    Intervals = {}

    def __init__(self, name, position, direction):
        Laser.laserCount += 1

        self.name = name
        self.position = position
        self.direction = direction.normalized()

        # Root node
        self.node = ShowBaseGlobal.base.render.attachNewNode(name + "_ROOT")
        self.node.setPos(position)

        # ----------------------------------------------------
        # VISUAL: Thin glowing beam
        # ----------------------------------------------------
        cm = CardMaker("laser_beam")
        cm.setFrame(-0.08, 0.08, -0.6, 0.6)  # thin vertical beam
        self.model = self.node.attachNewNode(cm.generate())
        self.model.setBillboardPointEye()
        self.model.setTransparency(TransparencyAttrib.MAlpha)
        self.model.setColorScale(1.0, 0.2, 0.2, 1.0)  # red beam

        # ----------------------------------------------------
        # COLLIDER: small sphere (much smaller than missile)
        # ----------------------------------------------------
        SphereCollideObj.__init__(self, radius=4.0)
        self.debug_mode = False  # set True to visualize hitbox

        Laser.Models[name] = self.model

        print(f"[Laser] Created {name} (radius=4.0)")


# ============================================================
# Player (movement + boost + missiles + lasers + FOV + VFX)
# ============================================================
class Player(SpaceObject, SphereCollideObj):
    def __init__(self, name, model_path, scale, position, health=100):
        # Visual base
        SpaceObject.__init__(self, name, model_path, scale, position, health)

        # Collider
        SphereCollideObj.__init__(self, radius=3.0)
        self.debug_mode = False

        # -------------------------------------------------------
        # MOVEMENT
        # -------------------------------------------------------
        self.base_speed = 150
        self.speed = self.base_speed
        self.boost_multiplier = 3.0
        self.turn_rate = 55

        # -------------------------------------------------------
        # CAMERA FOV BOOST EFFECT
        # -------------------------------------------------------
        self.normal_fov = 70
        self.boost_fov = 100
        self.fov_speed = 3.0

        self.lens = ShowBaseGlobal.base.cam.node().getLens()
        self.lens.setFov(self.normal_fov)
        ShowBaseGlobal.base.taskMgr.add(self.update_fov, "updateFOV")

        # -------------------------------------------------------
        # SPEED LINES VFX
        # -------------------------------------------------------
        self.speed_lines = []
        self.max_speed_lines = 18
        self.speed_line_spawn_timer = 0.0
        self.speed_line_spawn_rate = 0.03
        ShowBaseGlobal.base.taskMgr.add(self.update_speed_lines, "updateSpeedLines")

        # -------------------------------------------------------
        # RUNTIME FLAGS
        # -------------------------------------------------------
        self.thrusting = False
        self.boost_active = False
        self.boost_queued = False

        self.model.reparentTo(self.node)

        # -------------------------------------------------------
        # MISSILE SYSTEM
        # -------------------------------------------------------
        self.missileBay = 1
        self.maxMissiles = 1
        self.missileDistance = 1200
        self.reloading = False
        self.reloadTime = 0.3

        # -------------------------------------------------------
        # WEAPON SYSTEM
        # -------------------------------------------------------
        self.weapon_modes = ["missile", "laser"]
        self.weapon_index = 0
        self.current_weapon = self.weapon_modes[self.weapon_index]

        # Laser stats
        self.laser_fire_delay = 0.12
        self.last_laser_time = 0.0
        self.laser_stun_duration = 1.0  # seconds

        # -------------------------------------------------------
        # HUD
        # -------------------------------------------------------
        self.crosshair = OnscreenImage(
            image="Assets/crosshair.png",
            pos=(0, 0, 0),
            scale=0.05
        )
        self.crosshair.setTransparency(TransparencyAttrib.MAlpha)

        # -------------------------------------------------------
        # BOOST TRAIL
        # -------------------------------------------------------
        self.boost_trail = None

        # Roll stabilization
        ShowBaseGlobal.base.taskMgr.add(self.StabilizeRoll, "stabilize-roll")

    # -------------------------------------------------------
    # WEAPON CYCLING
    # -------------------------------------------------------
    def cycle_weapon(self):
        self.weapon_index = (self.weapon_index + 1) % len(self.weapon_modes)
        self.current_weapon = self.weapon_modes[self.weapon_index]
        print(f"[Weapon] Switched to: {self.current_weapon}")

    # -------------------------------------------------------
    # FIRE ROUTER
    # -------------------------------------------------------
    def Fire(self):
        if self.current_weapon == "missile":
            self.fire_missile()
        elif self.current_weapon == "laser":
            self.fire_laser()

    # -------------------------------------------------------
    # MISSILE FIRE
    # -------------------------------------------------------
    def fire_missile(self):
        base = ShowBaseGlobal.base

        if self.missileBay > 0:
            forward = self.node.getQuat(base.render).getForward().normalized()
            startPos = self.node.getPos(base.render) + forward * 8
            endPos = startPos + forward * self.missileDistance

            missileName = f"Missile_{Missile.missileCount + 1}"

            missile = Missile(
                name=missileName,
                model_path="Assets/Phaser/phaser.egg",
                scale=0.5,
                position=startPos
            )

            base.collision_manager.register_missile(missile)

            interval = missile.node.posInterval(
                2.0,
                endPos,
                startPos=startPos,
                fluid=1,
                name=f"MissileMove_{missileName}"
            )

            Missile.Intervals[missileName] = interval
            interval.start()

            self.missileBay -= 1
            print(f"[Missile] Fired {missileName}")

        else:
            if not self.reloading:
                self.reloading = True
                ShowBaseGlobal.base.taskMgr.doMethodLater(
                    0, self.Reload, "reloadTask"
                )

    # -------------------------------------------------------
    # LASER FIRE (with stun + impact VFX + sound)
    # -------------------------------------------------------
    def fire_laser(self):
        base = ShowBaseGlobal.base
        now = ClockObject.getGlobalClock().getFrameTime()

        # Fire rate limit
        if now - self.last_laser_time < self.laser_fire_delay:
            return
        self.last_laser_time = now

        forward = self.node.getQuat(base.render).getForward().normalized()
        startPos = self.node.getPos(base.render) + forward * 6
        max_range = 2000.0
        endPos = startPos + forward * max_range

        # ---------------------------------------------------
        # LASER SOUND
        # ---------------------------------------------------
        try:
            base.sound.play_sfx("Assets/sounds/laser.mp3")
        except Exception:
            print("[Sound] Could not play laser.mp3")

        # ---------------------------------------------------
        # RAYCAST‑STYLE HIT CHECK AGAINST DRONES
        # ---------------------------------------------------
        hit_drone = None
        hit_point = None
        hit_t = None

        drones = list(getattr(base, "orbiting_drones", []))

        for d in drones:
            # Multi‑sphere support
            if hasattr(d, "collider_spheres"):
                spheres = d.collider_spheres
            else:
                spheres = getattr(d, "collider_spheres", [{"center": (0, 0, 0), "radius": 6.0}])

            for sphere in spheres:
                cx, cy, cz = sphere["center"]
                r = sphere["radius"]
                center = d.node.getPos(base.render) + Vec3(cx, cy, cz)

                hit, point, t = self._segment_sphere_intersect(startPos, endPos, center, r)
                if hit and (hit_t is None or t < hit_t):
                    hit_t = t
                    hit_drone = d
                    hit_point = point

        # If we hit a drone, shorten beam and apply stun
        if hit_drone is not None and hit_point is not None:
            endPos = hit_point
            # Stun drone for configured duration
            now_time = ClockObject.getGlobalClock().getFrameTime()
            hit_drone.stunned_until = now_time + self.laser_stun_duration
            hit_drone.stunned = True
            print(f"[Laser] Stunned {hit_drone.name} for {self.laser_stun_duration} seconds")

            # Impact spark at drone
            self.spawn_laser_impact(hit_point)
        else:
            # No hit: impact spark at beam end (4A behavior)
            self.spawn_laser_impact(endPos)

        # ---------------------------------------------------
        # VISUAL LASER PROJECTILE
        # ---------------------------------------------------
        laserName = f"Laser_{Laser.laserCount + 1}"
        laser = Laser(
            name=laserName,
            position=startPos,
            direction=forward
        )

        # We do NOT register lasers with CollisionManager; we handle hits here.

        interval = laser.node.posInterval(
            0.4,
            endPos,
            startPos=startPos,
            fluid=1,
            name=f"LaserMove_{laserName}"
        )

        Laser.Intervals[laserName] = interval
        interval.start()

        print(f"[Laser] Fired {laserName}")

    # -------------------------------------------------------
    # LASER SEGMENT–SPHERE INTERSECTION
    # -------------------------------------------------------
    def _segment_sphere_intersect(self, p1, p2, center, radius):
        """
        Returns (hit: bool, point: Vec3 or None, t: float or None)
        where point = p1 + (p2 - p1) * t, 0 <= t <= 1.
        """
        d = p2 - p1
        f = p1 - center

        a = d.dot(d)
        if a == 0:
            return False, None, None

        b = 2 * f.dot(d)
        c = f.dot(f) - radius * radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return False, None, None

        discriminant = discriminant ** 0.5
        t1 = (-b - discriminant) / (2 * a)
        t2 = (-b + discriminant) / (2 * a)

        t_hit = None
        if 0.0 <= t1 <= 1.0:
            t_hit = t1
        elif 0.0 <= t2 <= 1.0:
            t_hit = t2

        if t_hit is None:
            return False, None, None

        hit_point = p1 + d * t_hit
        return True, hit_point, t_hit

    # -------------------------------------------------------
    # LASER IMPACT VFX (A2 + S3 + FX1)
    # -------------------------------------------------------
    def spawn_laser_impact(self, position):
        """
        Large, energetic impact:
        - Red/orange flash
        - Bright puff
        - Darker smoke
        - 10 sparks flying out
        All procedural (no particle system).
        """
        base = ShowBaseGlobal.base
        render = base.render

        # Helper to make a billboard card
        def make_card(scale, color, alpha):
            cm = CardMaker("laser_fx")
            cm.setFrame(-0.5, 0.5, -0.5, 0.5)
            node = render.attachNewNode(cm.generate())
            node.setPos(position)
            node.setBillboardPointEye()
            node.setScale(scale)
            node.setColorScale(*color, alpha)
            node.setTransparency(TransparencyAttrib.MAlpha)
            return node

        # Flash / puff / smoke (S3 scale)
        flash = make_card(1.2, (1.0, 0.3, 0.2), 1.0)
        puff  = make_card(1.4, (1.0, 0.6, 0.2), 0.9)
        smoke = make_card(1.8, (0.3, 0.3, 0.3), 0.7)

        # Sparks
        import random
        sparks = []
        for _ in range(10):
            cm = CardMaker("laser_spark")
            cm.setFrame(-0.1, 0.1, -0.1, 0.1)
            node = render.attachNewNode(cm.generate())
            node.setPos(position)
            node.setBillboardPointEye()
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setColorScale(1.0, 0.6, 0.2, 1.0)

            # Random outward velocity
            vel = Vec3(
                random.uniform(-25, 25),
                random.uniform(-25, 25),
                random.uniform(-10, 20)
            )
            sparks.append([node, vel, 1.0])

        # Update task
        def _fx(task):
            dt = ClockObject.getGlobalClock().getDt()

            # Flash: fast fade + expand
            r, g, b, a = flash.getColorScale()
            flash.setColorScale(r, g, b, max(0.0, a - 4.0 * dt))
            flash.setScale(flash.getScale() + Vec3(8 * dt))

            # Puff: medium fade + expand
            r, g, b, a = puff.getColorScale()
            puff.setColorScale(r, g, b, max(0.0, a - 2.5 * dt))
            puff.setScale(puff.getScale() + Vec3(5 * dt))

            # Smoke: slower fade + expand
            r, g, b, a = smoke.getColorScale()
            smoke.setColorScale(r, g, b, max(0.0, a - 1.5 * dt))
            smoke.setScale(smoke.getScale() + Vec3(3 * dt))

            # Sparks
            for entry in list(sparks):
                node, vel, alpha = entry
                node.setPos(node.getPos() + vel * dt)
                vel.z -= 30 * dt  # gravity‑like drop
                alpha -= 2.0 * dt
                node.setColorScale(1.0, 0.6, 0.2, max(0.0, alpha))
                node.setScale(node.getScale() * (1.0 - 1.5 * dt))
                entry[1] = vel
                entry[2] = alpha

                if alpha <= 0.0:
                    node.removeNode()
                    sparks.remove(entry)

            # Cleanup when all invisible
            if (flash.getColorScale()[3] <= 0.0 and
                puff.getColorScale()[3] <= 0.0 and
                smoke.getColorScale()[3] <= 0.0 and
                not sparks):
                flash.removeNode()
                puff.removeNode()
                smoke.removeNode()
                return task.done

            return task.cont

        ShowBaseGlobal.base.taskMgr.add(_fx, "laserImpactFX")

    # -------------------------------------------------------
    # MISSILE RELOAD
    # -------------------------------------------------------
    def Reload(self, task):
        if task.time >= self.reloadTime:
            self.missileBay = min(self.missileBay + 1, self.maxMissiles)
            self.reloading = False
            print(f"[Missile] Reload complete. Missiles in bay: {self.missileBay}")
            return task.done
        return task.cont

    # -------------------------------------------------------
    # MISSILE + LASER CLEANUP (intervals only)
    # -------------------------------------------------------
    def CheckIntervals(self, task):
        from classes import Missile, Laser

        # -------------------------
        # MISSILES
        # -------------------------
        for name, interval in list(Missile.Intervals.items()):
            # NEW: ignore intervals that haven't started moving yet
            if interval.getT() == 0:
                continue

            if interval.isStopped():
                print(f"[Missile] {name} finished — deleting")

                if name in Missile.Models:
                    Missile.Models[name].removeNode()
                    del Missile.Models[name]

                if name in Missile.Colliders:
                    Missile.Colliders[name].removeNode()
                    del Missile.Colliders[name]

                del Missile.Intervals[name]

        # -------------------------
        # LASERS
        # -------------------------
        for name, interval in list(Laser.Intervals.items()):
            # NEW: ignore intervals that haven't started moving yet
            if interval.getT() == 0:
                continue

            if interval.isStopped():
                print(f"[Laser] {name} finished — deleting")

                if name in Laser.Models:
                    Laser.Models[name].removeNode()
                    del Laser.Models[name]

                if name in Laser.Colliders:
                    Laser.Colliders[name].removeNode()
                    del Laser.Colliders[name]

                del Laser.Intervals[name]

        return task.cont

    # -------------------------------------------------------
    # MOVEMENT — always move the ROOT (self.node)
    # -------------------------------------------------------
    def Thrust(self, keyDown):
        if keyDown:
            if not self.thrusting:
                self.thrusting = True
                if self.boost_queued:
                    self._apply_boost_now()
                self._play_movement_sound()
                ShowBaseGlobal.base.taskMgr.add(self.ApplyThrust, "forward-thrust")
        else:
            if self.thrusting:
                self.thrusting = False
                ShowBaseGlobal.base.taskMgr.remove("forward-thrust")
                self._stop_movement_sound()
                if self.boost_active:
                    self._clear_boost()

    def ApplyThrust(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        cam_h = ShowBaseGlobal.base.camera.getH(ShowBaseGlobal.base.render)
        self.node.setH(cam_h)
        self.node.setY(self.node, self.speed * dt)
        return task.cont

    # -------------------------------------------------------
    # REVERSE THRUST
    # -------------------------------------------------------
    def ReverseThrust(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyReverseThrust, "reverse-thrust")
        else:
            ShowBaseGlobal.base.taskMgr.remove("reverse-thrust")

    def ApplyReverseThrust(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        cam_h = ShowBaseGlobal.base.camera.getH(ShowBaseGlobal.base.render)
        self.node.setH(cam_h)
        self.node.setY(self.node, -self.speed * dt)
        return task.cont

    # -------------------------------------------------------
    # VERTICAL MOVEMENT
    # -------------------------------------------------------
    def MoveUp(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyMoveUp, "move-up")
        else:
            ShowBaseGlobal.base.taskMgr.remove("move-up")

    def ApplyMoveUp(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setZ(self.node.getZ() + self.speed * dt)
        return task.cont

    def MoveDown(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyMoveDown, "move-down")
        else:
            ShowBaseGlobal.base.taskMgr.remove("move-down")

    def ApplyMoveDown(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setZ(self.node.getZ() - self.speed * dt)
        return task.cont

    # -------------------------------------------------------
    # YAW (TURN LEFT/RIGHT)
    # -------------------------------------------------------
    def LeftTurn(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyLeftTurn, "left-turn")
        else:
            ShowBaseGlobal.base.taskMgr.remove("left-turn")

    def ApplyLeftTurn(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setH(self.node.getH() + self.turn_rate * dt)
        return task.cont

    def RightTurn(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyRightTurn, "right-turn")
        else:
            ShowBaseGlobal.base.taskMgr.remove("right-turn")

    def ApplyRightTurn(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setH(self.node.getH() - self.turn_rate * dt)
        return task.cont

    # -------------------------------------------------------
    # ROLL (LEFT/RIGHT)
    # -------------------------------------------------------
    def RollLeft(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyRollLeft, "roll-left")
        else:
            ShowBaseGlobal.base.taskMgr.remove("roll-left")

    def ApplyRollLeft(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setR(self.node.getR() + self.turn_rate * dt)
        return task.cont

    def RollRight(self, keyDown):
        if keyDown:
            ShowBaseGlobal.base.taskMgr.add(self.ApplyRollRight, "roll-right")
        else:
            ShowBaseGlobal.base.taskMgr.remove("roll-right")

    def ApplyRollRight(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        self.node.setR(self.node.getR() - self.turn_rate * dt)
        return task.cont

    # -------------------------------------------------------
    # AUTO‑ROLL STABILIZATION
    # -------------------------------------------------------
    def StabilizeRoll(self, task):
        dt = ClockObject.getGlobalClock().getDt()
        current_r = self.node.getR()
        target_r = 0.0
        damping = 4.0
        new_r = current_r + (target_r - current_r) * damping * dt
        self.node.setR(new_r)
        return task.cont

    # -------------------------------------------------------
    # MOVEMENT SOUND (FADE IN/OUT)
    # -------------------------------------------------------
    def _play_movement_sound(self):
        sm = ShowBaseGlobal.base.sound

        if getattr(self, "_movement_sound", None):
            return
        if getattr(self, "_movement_fade_task", None):
            return

        snd = sm.play_file("Assets/sounds/player.mp3", loop=True)
        if not snd:
            return

        snd.setLoop(True)
        snd.setVolume(0.0)
        self._movement_sound = snd

        def fade_in(task):
            t = min(task.time / 0.35, 1.0)
            snd.setVolume(0.18 * t)
            if t >= 1.0:
                self._movement_fade_task = None
                return task.done
            return task.cont

        self._movement_fade_task = ShowBaseGlobal.base.taskMgr.add(
            fade_in, "movementFadeIn"
        )

    def _stop_movement_sound(self):
        snd = getattr(self, "_movement_sound", None)
        if not snd:
            return

        if getattr(self, "_movement_fade_task", None):
            try:
                ShowBaseGlobal.base.taskMgr.remove(self._movement_fade_task)
            except Exception:
                pass
            self._movement_fade_task = None

        start_volume = snd.getVolume()

        def fade_out(task):
            t = min(task.time / 0.35, 1.0)
            snd.setVolume(start_volume * (1.0 - t))
            if t >= 1.0:
                try:
                    snd.stop()
                except Exception:
                    pass
                self._movement_sound = None
                return task.done
            return task.cont

        ShowBaseGlobal.base.taskMgr.add(fade_out, "movementFadeOut")

    # -------------------------------------------------------
    # BOOST HELPERS
    # -------------------------------------------------------
    def _apply_boost_now(self):
        if not self.boost_active:
            self.boost_active = True
            self.boost_queued = False
            self.speed = self.base_speed * self.boost_multiplier
            self.enable_boost_trail()
            self.spawn_shockwave()
            print(f"[Player] Boost applied. Speed = {self.speed}")

    def _queue_boost(self):
        self.boost_queued = True
        print("[Player] Boost queued (will apply when you start thrusting).")

    def _clear_boost(self):
        self.boost_active = False
        self.boost_queued = False
        self.speed = self.base_speed
        self.disable_boost_trail()
        print("[Player] Boost cleared. Speed reset to base.")

    # -------------------------------------------------------
    # PUBLIC BOOST API (always‑available)
    # -------------------------------------------------------
    def start_boost(self):
        """
        Public boost trigger: called from input (F key).
        Boost is available anytime, no rings required.
        """
        if self.boost_active:
            return

        self._apply_boost_now()

        # Play a random boost sound if available
        try:
            ShowBaseGlobal.base.sound.play_random_boost()
        except Exception:
            try:
                ShowBaseGlobal.base.sound.play_sfx("Assets/sounds/boost.mp3")
            except Exception:
                print("[Boost] Could not play boost sound")

        print("[Boost] Boost ON (manual)")

    def stop_boost(self):
        """
        Public boost stop: called when boost key is released.
        """
        if not self.boost_active:
            return

        self._clear_boost()
        print("[Boost] Boost OFF (manual)")

        # Clear all speed lines immediately
        for entry in list(self.speed_lines):
            entry["node"].removeNode()
        self.speed_lines.clear()

    # -------------------------------------------------------
    # Boost Trail & Shockwave
    # -------------------------------------------------------
    def enable_boost_trail(self):
        # Remove old trail if it exists
        if hasattr(self, "boost_trail") and self.boost_trail:
            try:
                self.boost_trail.removeNode()
            except Exception:
                pass

        cm = CardMaker("boost_trail_card")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        card = self.node.attachNewNode(cm.generate())
        card.setTwoSided(True)
        card.setBillboardPointEye()
        card.setPos(0, -6, 0)

        card.setScale(0.4, 1.8, 0.4)
        card.setColorScale(1, 1, 1, 0.9)
        card.setTransparency(TransparencyAttrib.MAlpha)

        self.boost_trail = card

    def disable_boost_trail(self):
        if hasattr(self, "boost_trail") and self.boost_trail:
            self.boost_trail.removeNode()
            self.boost_trail = None

    def spawn_shockwave(self):
        cm = CardMaker("shockwave_card")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        card = self.node.attachNewNode(cm.generate())
        card.setPos(0, 6, 0)
        card.setScale(0.5)
        card.setBillboardPointEye()
        card.setColorScale(1.0, 0.6, 0.1, 0.9)
        card.setTransparency(TransparencyAttrib.MAlpha)

        def _grow(task, node=card):
            dt = ClockObject.getGlobalClock().getDt()
            s = node.getScale()
            node.setScale(s + Vec3(6 * dt))
            r, g, b, a = node.getColorScale()
            node.setColorScale(r, g, b, max(0.0, a - 2.0 * dt))
            if node.getColorScale()[3] <= 0.0:
                try:
                    node.removeNode()
                except Exception:
                    pass
                return task.done
            return task.cont

        ShowBaseGlobal.base.taskMgr.add(_grow, "shockwave_grow")

    # -------------------------------------------------------
    # FOV UPDATE
    # -------------------------------------------------------
    def update_fov(self, task):
        """Smoothly animate camera FOV based on boost state."""
        dt = ClockObject.getGlobalClock().getDt()

        # Safety: always use the real camera lens
        self.lens = ShowBaseGlobal.base.cam.node().getLens()

        current = self.lens.getFov()[0]
        target = self.boost_fov if self.boost_active else self.normal_fov
        new_fov = current + (target - current) * dt * self.fov_speed
        self.lens.setFov(new_fov)
        return task.cont

    # -------------------------------------------------------
    # SPEED LINES UPDATE
    # -------------------------------------------------------
    def update_speed_lines(self, task):
        dt = ClockObject.getGlobalClock().getDt()

        if self.boost_active:
            self.speed_line_spawn_timer += dt
            if self.speed_line_spawn_timer >= self.speed_line_spawn_rate:
                self.speed_line_spawn_timer = 0.0
                if len(self.speed_lines) < self.max_speed_lines:
                    self.spawn_speed_line()

        for entry in list(self.speed_lines):
            node = entry["node"]
            vel = entry["vel"]
            entry["life"] -= dt

            node.setPos(node.getPos() + vel * dt)

            r, g, b, a = node.getColorScale()
            node.setColorScale(r, g, b, max(0.0, a - dt * 3.0))

            if entry["life"] <= 0.0 or a <= 0.0:
                node.removeNode()
                self.speed_lines.remove(entry)

        return task.cont

    def spawn_speed_line(self):
        """
        Spawns a single speed line behind the player during boost.
        Simple quad that fades and moves backward.
        """
        cm = CardMaker("speed_line")
        cm.setFrame(-0.05, 0.05, -0.6, 0.6)
        node = self.node.attachNewNode(cm.generate())
        node.setBillboardPointEye()
        node.setPos(0, -8, 0)
        node.setColorScale(1.0, 1.0, 1.0, 0.9)
        node.setTransparency(TransparencyAttrib.MAlpha)

        vel = Vec3(0, -120, 0)
        entry = {
            "node": node,
            "vel": vel,
            "life": 0.5
        }
        self.speed_lines.append(entry)
    #-------------------------------------------------------
    # Boost helpers (apply while thrusting; cleared when stop)
    #-------------------------------------------------------
    def _apply_boost_now(self):
        if not self.boost_active:
            self.boost_active = True
            self.boost_queued = False
            self.speed = self.base_speed * self.boost_multiplier
            self.enable_boost_trail()
            self.spawn_shockwave()
            print(f"[Player] Boost applied. Speed = {self.speed}")

    def _queue_boost(self):
        self.boost_queued = True
        print("[Player] Boost queued (will apply when you start thrusting).")

    def _clear_boost(self):
        self.boost_active = False
        self.boost_queued = False
        self.speed = self.base_speed
        self.disable_boost_trail()
        print("[Player] Boost cleared. Speed reset to base.")

    #-------------------------------------------------------
    # NEW ALWAYS-AVAILABLE BOOST API
    #-------------------------------------------------------
    def start_boost(self):
        """
        Public boost trigger: called from input (F key).
        Boost is available anytime, no rings required.
        """
        if self.boost_active:
            return

        self._apply_boost_now()

        # Play a random boost sound if available
        try:
            ShowBaseGlobal.base.sound.play_random_boost()
        except Exception:
            try:
                ShowBaseGlobal.base.sound.play_sfx("Assets/sounds/boost.mp3")
            except Exception:
                print("[Boost] Could not play boost sound")

        print("[Boost] Boost ON (manual)")

    def stop_boost(self):
        """
        Public boost stop: called when boost key is released.
        """
        if not self.boost_active:
            return

        self._clear_boost()
        print("[Boost] Boost OFF (manual)")
        # Clear all speed lines immediately
        
        for entry in list(self.speed_lines):
            entry["node"].removeNode()
        self.speed_lines.clear()



    #-------------------------------------------------------
    # Boost Trail & Shockwave
    #-------------------------------------------------------
    def enable_boost_trail(self):
        # Remove old trail if it exists
        if hasattr(self, "boost_trail") and self.boost_trail:
            try:
                self.boost_trail.removeNode()
            except Exception:
                pass

        # Create a simple quad using CardMaker (no external model required)
        cm = CardMaker("boost_trail_card")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)  # unit quad
        card = self.node.attachNewNode(cm.generate())
        card.setTwoSided(True)
        card.setBillboardPointEye()
        card.setPos(0, -6, 0)

        # Stretch it into a long trail and tint it
        card.setScale(0.4, 1.8, 0.4)
        card.setColorScale(1, 1, 1, 0.9)
        card.setTransparency(TransparencyAttrib.MAlpha)

        self.boost_trail = card

    def disable_boost_trail(self):
        if hasattr(self, "boost_trail") and self.boost_trail:
            self.boost_trail.removeNode()
            self.boost_trail = None

    def spawn_shockwave(self):
        # Minimal procedural shockwave using CardMaker
        cm = CardMaker("shockwave_card")
        cm.setFrame(-0.5, 0.5, -0.5, 0.5)
        card = self.node.attachNewNode(cm.generate())
        card.setPos(0, 6, 0)
        card.setScale(0.5)
        card.setBillboardPointEye()
        card.setColorScale(1.0, 0.6, 0.1, 0.9)
        card.setTransparency(TransparencyAttrib.MAlpha)

        def _grow(task, node=card):
            dt = ClockObject.getGlobalClock().getDt()
            # expand uniformly
            s = node.getScale()
            node.setScale(s + Vec3(6 * dt))
            r, g, b, a = node.getColorScale()
            node.setColorScale(r, g, b, max(0.0, a - 2.0 * dt))
            if node.getColorScale()[3] <= 0:
                try:
                    node.removeNode()
                except Exception:
                    pass
                return task.done
            return task.cont

        ShowBaseGlobal.base.taskMgr.add(_grow, "shockwave_grow")

    def update_fov(self, task):
        """Smoothly animate camera FOV based on boost state."""
        dt = ClockObject.getGlobalClock().getDt()

        # Safety: always use the real camera lens
        self.lens = ShowBaseGlobal.base.cam.node().getLens()

        current = self.lens.getFov()[0]
        target = self.boost_fov if self.boost_active else self.normal_fov

        # Smooth interpolation
        new_fov = current + (target - current) * dt * self.fov_speed
        self.lens.setFov(new_fov)

        return task.cont


# ============================================================
# Drone (Multi‑sphere collider, drift‑free, smooth orbit)
# ============================================================
class DroneDefender(SpaceObject):
    def __init__(self, name, model_path, scale, position, orbit_radius=20, health=10):
        # Base visual object
        SpaceObject.__init__(self, name, model_path, scale, position, health)

        # ----------------------------------------------------
        # MULTI‑SPHERE COLLIDER SETUP
        # ----------------------------------------------------
        # Instead of one sphere, we use 3 spheres:
        #   - Core
        #   - Left wing
        #   - Right wing
        #
        # This dramatically improves hit accuracy without
        # requiring a complex mesh collider.
        # ----------------------------------------------------
        self.collider_type = "multi_sphere"
        self.debug_mode = DEBUG_COLLIDERS

        # Collider definitions (local offsets)
        self.collider_spheres = [
            {"center": (0, 0, 0), "radius": 10.0},   # core
            {"center": (6.5, 0, 0), "radius": 6.0},  # right wing
            {"center": (-6.5, 0, 0), "radius": 6.0}, # left wing
]


        # Fallback for raycast
        self.collider_radius = 6.0


        # Build collider nodes
        self.colliders = []
        for i, data in enumerate(self.collider_spheres):
            cx, cy, cz = data["center"]
            r = data["radius"]

            cnode = CollisionNode(f"{name}_C{i}")
            cnode.addSolid(CollisionSphere(cx, cy, cz, r))
            cpath = self.node.attachNewNode(cnode)

            if self.debug_mode:
                cpath.show()
            else:
                cpath.hide()

            self.colliders.append(cpath)

        # ----------------------------------------------------
        # ORBIT METADATA
        # ----------------------------------------------------
        self.orbit_center = position
        self.orbit_radius = orbit_radius
        self.orbit_angle = 0.0
        self.orbit_speed = 0.5

        # Pattern switching
        self.orbit_mode = "circleZ"
        self.pattern_timer = 0.0
        self.pattern_interval = random.uniform(10.0, 14.0)

        # Transition state
        self.transition_time = 0.0
        self.transition_duration = 5.0
        self.transition_active = False
        self.start_pos = None
        self.target_pos = None

        self.active = False  # set by SpaceJam
        self.model.reparentTo(self.node)

    # --------------------------------------------------------
    # FORCE COLLIDERS TO SYNC EVERY FRAME
    # --------------------------------------------------------
    def sync_colliders(self):
        """
        Ensures collider nodes stay perfectly aligned with the drone.
        Prevents 1‑frame lag that causes ghost misses.
        """
        for c in self.colliders:
            c.setPos(0, 0, 0)
            c.setHpr(0, 0, 0)

    # --------------------------------------------------------
    # PATTERN SWITCHING
    # --------------------------------------------------------
    def switch_pattern(self):
        modes = ["circleX", "circleY", "circleZ", "cloud", "seams"]
        self.orbit_mode = random.choice(modes)

        self.transition_time = 0.0
        self.transition_active = True
        self.start_pos = self.node.getPos()
        self.target_pos = None

        self.pattern_timer = 0.0
        self.pattern_interval = random.uniform(10.0, 14.0)

    # --------------------------------------------------------
    # UPDATE LOOP
    # --------------------------------------------------------
    def update(self, dt, player_pos):
        """
        Per-frame drone update:
        - respects stun (laser hit)
        - updates orbit using pattern helpers
        """
        from panda3d.core import ClockObject
        from dronepatterns import update_orbit, update_transition

        now = ClockObject.getGlobalClock().getFrameTime()

        # If stunned, skip movement until timer expires
        if getattr(self, "stunned", False):
            if now < getattr(self, "stunned_until", 0.0):
                return
            else:
                self.stunned = False

        # Normal orbit update
        orbit_target = update_orbit(self, dt)
        final_pos = update_transition(self, dt, orbit_target)

        # Apply position to root node
        self.node.setPos(final_pos)


# ============================================================
# Drone Counter
# ============================================================
class DroneCounter:
    def __init__(self):
        self.count = 0

    def register_drone(self):
        self.count += 1

    def get_count(self):
        return self.count