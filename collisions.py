# collisions.py
from panda3d.core import (
    BitMask32, TransparencyAttrib, ClockObject,
    CollisionNode, CollisionSphere, CollisionBox,
    CollisionTraverser, CollisionHandlerPusher,
    CollisionHandlerEvent, CardMaker, Vec3, Point3
)

MASK_PLAYER  = BitMask32.bit(0)
MASK_PLANET  = BitMask32.bit(1)
MASK_DRONE   = BitMask32.bit(2)
MASK_STATIC  = BitMask32.bit(3)
MASK_MISSILE = BitMask32.bit(4)

# ----------------------------------------------------
# Collider metadata classes
# ----------------------------------------------------
class SphereCollideObj:
    def __init__(self, radius, debug=True):
        self.collider_type = "sphere"
        self.collider_radius = radius
        self.debug_mode = debug
        self.collider = None

class BoxCollideObj:
    def __init__(self, size_xyz, debug=True):
        self.collider_type = "box"
        self.collider_size = size_xyz
        self.debug_mode = debug
        self.collider = None

class MultiBoxCollideObj:
    def __init__(self, box_list, debug=True):
        self.collider_type = "multi_box"
        self.collider_boxes = box_list
        self.debug_mode = debug
        self.collider = None

# ----------------------------------------------------
# Collision Manager
# ----------------------------------------------------
class CollisionManager:
    def __init__(self, base):
        self.base = base

        self.traverser = CollisionTraverser("mainTraverser")
        self.base.cTrav = self.traverser

        self.pusher = CollisionHandlerPusher()
        self.events = CollisionHandlerEvent()
        self.events.addInPattern("%fn-into-%in")
        self.missile_prev_positions = {}


        print("\n[CollisionManager] Initialized.")


    # ----------------------------------------------------
    # Create collider for ANY object
    # ----------------------------------------------------
    def create_collider(self, obj):
        if not hasattr(obj, "collider_type"):
            print(f"[CollisionManager] WARNING: {obj} has no collider_type; skipping.")
            return None

        if obj.collider_type == "multi_box":
            cnode = CollisionNode(obj.name)
            for box in obj.collider_boxes:
                cx, cy, cz = box["center"]
                sx, sy, sz = box["size"]
                solid = CollisionBox((cx, cy, cz), sx, sy, sz)
                cnode.addSolid(solid)

        elif obj.collider_type == "sphere":
            cnode = CollisionNode(obj.name)
            solid = CollisionSphere(0, 0, 0, obj.collider_radius)
            cnode.addSolid(solid)

        elif obj.collider_type == "box":
            cnode = CollisionNode(obj.name)
            x, y, z = obj.collider_size
            solid = CollisionBox((0, 0, 0), x, y, z)
            cnode.addSolid(solid)

        elif obj.collider_type == "multi_sphere":
            cnode = CollisionNode(obj.name)
            for sphere in obj.collider_spheres:
                cx, cy, cz = sphere["center"]
                r = sphere["radius"]
                solid = CollisionSphere(cx, cy, cz, r)
                cnode.addSolid(solid)


        else:
            print(f"[CollisionManager] No collider created for {obj.name}.")
            return None

        cpath = obj.node.attachNewNode(cnode)
        cpath.show() if getattr(obj, "debug_mode", False) else cpath.hide()
        obj.collider = cpath
        cpath.setScale(1)  # NEW: prevents inheriting model scale

        return cpath


    # ----------------------------------------------------
    # PLAYER COLLIDER (push + events)
    # ----------------------------------------------------
    def register_player(self, player):
        cpath = self.create_collider(player)
        if not cpath:
            return

        # Player collider generates FROM events
        cpath.node().setFromCollideMask(MASK_PLAYER)

        # Player collider should NOT receive INTO collisions
        # The pusher only needs FROM on the player and INTO on statics/drones
        cpath.node().setIntoCollideMask(BitMask32.allOff())

        # Player MODEL should not collide
        player.node.setCollideMask(BitMask32.allOff())

        # Add to pusher
        self.pusher.addCollider(cpath, player.node)
        self.traverser.addCollider(cpath, self.pusher)

        # Also send events
        self.traverser.addCollider(cpath, self.events)

        print("[CollisionManager] Player collider registered.")


    # ----------------------------------------------------
    # STATIC OBJECTS (planets, station)
    # ----------------------------------------------------
    def register_static(self, obj):
        cpath = self.create_collider(obj)
        if not cpath:
            return

        # Static objects do NOT move
        cpath.node().setFromCollideMask(BitMask32.allOff())

        # They block:
        # - player
        # - drones
        # - missiles
        cpath.node().setIntoCollideMask(MASK_PLAYER | MASK_DRONE | MASK_MISSILE)


    # ----------------------------------------------------
    # DRONES (INTO only)
    # ----------------------------------------------------
    def register_drone(self, drone):
        cpath = self.create_collider(drone)
        if not cpath:
            return

        # Drones MOVE → they must be FROM
        cpath.node().setFromCollideMask(MASK_DRONE)

        # Drones collide with:
        # - planets
        # - station
        # - other drones
        # - player
        cpath.node().setIntoCollideMask(MASK_PLANET | MASK_STATIC | MASK_DRONE | MASK_PLAYER)

        # Add drone to pusher
        self.pusher.addCollider(cpath, drone.node)
        self.traverser.addCollider(cpath, self.pusher)

        # Also allow missile events
        self.traverser.addCollider(cpath, self.events)

        print(f"[CollisionManager] Drone collider registered: {drone.name}")



    # ----------------------------------------------------
    # MISSILES (FROM only)
    # ----------------------------------------------------
    def register_missile(self, missile):
        cpath = self.create_collider(missile)
        if not cpath:
            return

        cpath.node().setFromCollideMask(MASK_MISSILE)
        cpath.node().setIntoCollideMask(BitMask32.allOff())

        from classes import Missile
        Missile.Colliders[missile.name] = cpath

        if missile.debug_mode:
            cpath.show()
        else:
            cpath.hide()

        self.traverser.addCollider(cpath, self.events)

        print(f"[CollisionManager] Missile collider registered: {missile.name}")


        # ----------------------------------------------------
        # MISSILE → DRONE EVENT
        # ----------------------------------------------------
    def on_missile_hits_drone(self, entry):
        from_node = entry.getFromNode().getName()
        into_node = entry.getIntoNode().getName()

        print("[Collision] Missile hit drone:", into_node)

        # Destroy missile immediately
        self._destroy_missile_now(from_node)

        # Find drone object
        target = None
        for d in list(self.base.orbiting_drones):
            if into_node.startswith(d.name):
                target = d
                break

        if not target:
            print("[Collision] Drone object not found:", into_node)
            return

        pos = target.node.getPos(self.base.render)
                # Debris burst
        self.spawn_debris(pos, count=14)
        


        # ----------------------------------------------------
        # EXPLOSION SOUND
        # ----------------------------------------------------
        try:
            self.base.sound.play_sfx("Assets/sounds/explosion.mp3")
        except:
            print("[Sound] Could not play explosion.mp3")



        # ----------------------------------------------------
        # PARTICLE EXPLOSION EFFECT (3‑layer)
        # ----------------------------------------------------
        def make_card(scale, color, alpha):
            cm = CardMaker("fx")
            cm.setFrame(-0.5, 0.5, -0.5, 0.5)
            node = self.base.render.attachNewNode(cm.generate())
            node.setPos(pos)
            node.setBillboardPointEye()
            node.setScale(scale)
            node.setColorScale(*color, alpha)
            node.setTransparency(True)
            return node

        flash = make_card(0.4, (1.0, 0.9, 0.6), 1.0)
        puff  = make_card(0.8, (1.0, 0.5, 0.1), 0.9)
        smoke = make_card(1.2, (0.4, 0.4, 0.4), 0.7)

        def _fx(task):
            dt = ClockObject.getGlobalClock().getDt()

            # Flash: fast fade
            r,g,b,a = flash.getColorScale()
            flash.setColorScale(r,g,b,max(0,a-4*dt))
            flash.setScale(flash.getScale() + Vec3(6*dt))

            # Puff: medium fade
            r,g,b,a = puff.getColorScale()
            puff.setColorScale(r,g,b,max(0,a-2*dt))
            puff.setScale(puff.getScale() + Vec3(4*dt))

            # Smoke: slow fade
            r,g,b,a = smoke.getColorScale()
            smoke.setColorScale(r,g,b,max(0,a-1.2*dt))
            smoke.setScale(smoke.getScale() + Vec3(2*dt))

            # Remove when all invisible
            if flash.getColorScale()[3] <= 0 and puff.getColorScale()[3] <= 0 and smoke.getColorScale()[3] <= 0:
                flash.removeNode()
                puff.removeNode()
                smoke.removeNode()
                return task.done

            return task.cont

        self.base.taskMgr.add(_fx, f"fx_{into_node}")

        # Remove drone
        try:
            self.base.orbiting_drones.remove(target)
        except:
            pass

        target.node.removeNode()

    # ----------------------------------------------------
    # DEBRIS PARTICLE EFFECT
    # ----------------------------------------------------
    def spawn_debris(self, position, count=12):
        """
        Spawns flying debris shards at the given position.
        Uses simple quads with random velocity + fade-out.
        """
        from panda3d.core import CardMaker, Vec3, TransparencyAttrib
        import random

        debris_nodes = []

        for i in range(count):
            cm = CardMaker("debris")
            cm.setFrame(-0.2, 0.2, -0.2, 0.2)
            node = self.base.render.attachNewNode(cm.generate())
            node.setPos(position)
            node.setBillboardPointEye()
            node.setTransparency(TransparencyAttrib.MAlpha)

            # Random tint (metallic-ish)
            r = random.uniform(0.6, 1.0)
            g = random.uniform(0.4, 0.8)
            b = random.uniform(0.2, 0.5)
            node.setColorScale(r, g, b, 1.0)

            # Random velocity
            vel = Vec3(
                random.uniform(-12, 12),
                random.uniform(-12, 12),
                random.uniform(4, 18)
            )

            debris_nodes.append([node, vel, 1.0])  # node, velocity, alpha

        # Update task
        def _update(task):
            dt = ClockObject.getGlobalClock().getDt()

            for entry in list(debris_nodes):
                node, vel, alpha = entry

                # Move
                node.setPos(node.getPos() + vel * dt)

                # Gravity-like drop
                vel.z -= 20 * dt

                # Fade out
                alpha -= 1.2 * dt
                node.setColorScale(node.getColorScale()[0],
                                   node.getColorScale()[1],
                                   node.getColorScale()[2],
                                   max(0, alpha))

                # Shrink
                node.setScale(node.getScale() * (1 - 0.8 * dt))

                # Cleanup
                if alpha <= 0:
                    node.removeNode()
                    debris_nodes.remove(entry)

            if not debris_nodes:
                return task.done

            return task.cont

        self.base.taskMgr.add(_update, "debrisFX")

    # ----------------------------------------------------
    # MISSILE CLEANUP
    # ----------------------------------------------------
    def _destroy_missile_now(self, name):
        from classes import Missile

        # Play rocket explosion sound
        try:
            self.base.sound.play_sfx("Assets/sounds/rocket-explosion.mp3")
        except:
            print("[Sound] Could not play rocket-explosion.mp3")

        # Stop interval
        if name in Missile.Intervals:
            Missile.Intervals[name].finish()
            del Missile.Intervals[name]

        # Remove model
        if name in Missile.Models:
            Missile.Models[name].removeNode()
            del Missile.Models[name]

        # Remove collider
        if name in Missile.Colliders:
            Missile.Colliders[name].removeNode()
            del Missile.Colliders[name]

    # ----------------------------------------------------
    # MISSILE → PLANET / STATION
    # ----------------------------------------------------
    def on_missile_hits_planet(self, entry):
        self._destroy_missile_now(entry.getFromNode().getName())

    def on_missile_hits_station(self, entry):
        self._destroy_missile_now(entry.getFromNode().getName())

    # ----------------------------------------------------
    # EVENT HOOKS
    # ----------------------------------------------------
    def setup_events(self):
        self.base.accept("PlayerShip-into-Drone_*", self.on_player_hits_drone)
        self.base.accept("PlayerShip-into-PLANET*", self.on_player_hits_planet)
        self.base.accept("PlayerShip-into-MainStation", self.on_player_hits_station)

        self.base.accept("Missile_*-into-Drone_*", self.on_missile_hits_drone)
        self.base.accept("Missile_*-into-PLANET*", self.on_missile_hits_planet)
        self.base.accept("Missile_*-into-MainStation", self.on_missile_hits_station)

        print("[CollisionManager] Event hooks active.")


    # ----------------------------------------------------
    # PLAYER EVENTS
    # ----------------------------------------------------
    def on_player_hits_drone(self, entry):
        print("[Collision] Player hit drone:", entry.getIntoNode().getName())

    def on_player_hits_planet(self, entry):
        print("[Collision] Player hit planet:", entry.getIntoNode().getName())

    def on_player_hits_station(self, entry):
        print("[Collision] Player hit station!")

    # ----------------------------------------------------
    # UPDATE LOOP (collision + proximity fallback)
    # ----------------------------------------------------
    def update(self, task):
        self.traverser.traverse(self.base.render)

        from classes import Missile

        # Proximity kill for planets/station
        planet_kill = 250
        station_kill = 30

        planets = getattr(self.base, "planets", [])
        station = getattr(self.base, "station", None)

        for name, model in list(Missile.Models.items()):
            mnode = model.getParent()
            mpos = mnode.getPos(self.base.render)

            # Planets
            for p in planets:
                if (mpos - p.node.getPos(self.base.render)).length() <= planet_kill:
                    self._destroy_missile_now(name)
                    break

            if name not in Missile.Models:
                continue

            # Station
            if station and (mpos - station.node.getPos(self.base.render)).length() <= station_kill:
                self._destroy_missile_now(name)
                continue

        # Missile → Drone proximity fallback
        try:
            kill_dist = 14.0
            missiles = list(Missile.Models.items())
            drones = list(self.base.orbiting_drones)

            for name, model in missiles:
                if name not in Missile.Models:
                    continue

                mpos = model.getParent().getPos(self.base.render)

                for d in drones:
                    dpos = d.node.getPos(self.base.render)
                    if (mpos - dpos).length() <= kill_dist:
                        print(f"[Proximity] Missile {name} close to {d.name} — forcing hit")

                        class FakeEntry:
                            def __init__(self, f, i):
                                self.f = f
                                self.i = i
                            def getFromNode(self):
                                class N: 
                                    def __init__(self, n): self.n=n
                                    def getName(self): return self.n
                                return N(self.f)
                            def getIntoNode(self):
                                class N:
                                    def __init__(self, n): self.n=n
                                    def getName(self): return self.n
                                return N(self.i)

                        self.on_missile_hits_drone(FakeEntry(name, d.name))
                        break

        except Exception as e:
            print("[Collision] Proximity fallback error:", e)

        # ----------------------------------------------------
        # RAYCAST MISSILE → DRONE HYBRID COLLISION
        # ----------------------------------------------------
        def segment_sphere_intersect(p1, p2, center, radius):
            """Return True if line segment p1→p2 intersects sphere."""

            d = p2 - p1

            # Prevent division by zero when missile hasn't moved
            if d.length_squared() == 0:
                return False

            f = p1 - center

            a = d.dot(d)
            b = 2 * f.dot(d)
            c = f.dot(f) - radius * radius

            discriminant = b*b - 4*a*c
            if discriminant < 0:
                return False

            discriminant = discriminant ** 0.5
            t1 = (-b - discriminant) / (2*a)
            t2 = (-b + discriminant) / (2*a)

            return (0 <= t1 <= 1) or (0 <= t2 <= 1)


        # Missile → Drone raycast hybrid
        for name, model in list(Missile.Models.items()):
            if name not in Missile.Models:
                continue

            mnode = model.getParent()
            curr = mnode.getPos(self.base.render)

            # Use dictionary instead of NodePath attribute
            prev = self.missile_prev_positions.get(name, curr)
            self.missile_prev_positions[name] = curr

            # Check against all drones
            for drone in list(self.base.orbiting_drones):

                # Multi‑sphere collider support
                if hasattr(drone, "collider_spheres"):
                    spheres = drone.collider_spheres
                else:
                    spheres = getattr(drone, "collider_spheres", [{"center": (0,0,0), "radius": 6.0}])

                for sphere in spheres:
                    cx, cy, cz = sphere["center"]
                    r = sphere["radius"]

                    center = drone.node.getPos(self.base.render) + Point3(cx, cy, cz)

                    if segment_sphere_intersect(prev, curr, center, r):
                        print(f"[Raycast] Missile {name} hit {drone.name} via raycast")

                        class FakeEntry:
                            def __init__(self, f, i):
                                self.f = f
                                self.i = i
                            def getFromNode(self):
                                class N:
                                    def __init__(self, n): self.n=n
                                    def getName(self): return self.n
                                return N(self.f)
                            def getIntoNode(self):
                                class N:
                                    def __init__(self, n): self.n=n
                                    def getName(self): return self.n
                                return N(self.i)

                        self.on_missile_hits_drone(FakeEntry(name, drone.name))
                        break


        return task.cont